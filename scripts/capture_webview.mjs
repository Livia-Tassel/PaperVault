/** Record the actual PaperVault WebView compositor through CDP, without packages. */
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { access, mkdir, stat, writeFile, appendFile, rename } from 'node:fs/promises';
import path from 'node:path';

const argv = process.argv.slice(2);
const options = {};
for (let index = 0; index < argv.length; index += 2) {
  if (!['--debugger-address', '--output-dir', '--ffmpeg', '--height'].includes(argv[index]) || !argv[index + 1]) {
    throw new Error('Usage: node capture_webview.mjs --debugger-address localhost:PORT --output-dir ABS --ffmpeg ABS [--height 960|1080]');
  }
  options[argv[index].slice(2)] = argv[index + 1];
}
if (!['debugger-address', 'output-dir', 'ffmpeg'].every(key => options[key])) throw new Error('All three required command-line arguments are required');
const height = Number(options.height || 960);
if (![960, 1080].includes(height)) throw new Error('Height must be 960 or 1080');
if (!/^(?:localhost|127\.0\.0\.1):\d+$/.test(options['debugger-address'])) {
  throw new Error('The debugger address must be a loopback localhost:PORT address');
}
if (!path.isAbsolute(options['output-dir']) || !path.isAbsolute(options.ffmpeg)) {
  throw new Error('Output directory and FFmpeg path must be absolute');
}

const output = path.resolve(options['output-dir']);
const framesDirectory = path.join(output, 'frames');
const ffmpeg = path.resolve(options.ffmpeg);
const names = ['frames', 'frame-index.json', 'capture.ffconcat', 'capture.mp4', 'capture.partial.mp4',
  'capture-webview-report.json', 'capture-encode.log', 'capture-decode.log'];
const startedAt = new Date().toISOString();
const frames = [];
let socket;
let epoch;
let stoppedAt;
let endReason;
let nextId = 0;
let writing = Promise.resolve();
let fatalError;
let firstImage;
let pendingBytes = 0;
const requests = new Map();
let resolveReady;
let rejectReady;
let resolveStop;
const ready = new Promise((resolve, reject) => { resolveReady = resolve; rejectReady = reject; });
// Attach a rejection handler immediately: startup may fail before main awaits it.
ready.catch(() => {});
const stopped = new Promise(resolve => { resolveStop = resolve; });

function emit(value) { process.stdout.write(JSON.stringify(value) + '\n'); }
function requestStop(reason) {
  if (stoppedAt !== undefined) return;
  stoppedAt = Date.now();
  endReason = reason;
  resolveStop();
}
function fail(error) {
  if (!fatalError) fatalError = error instanceof Error ? error : new Error(String(error));
  rejectReady(fatalError);
  requestStop('error');
}
function send(method, params = {}) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return Promise.reject(new Error('CDP socket is closed'));
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { requests.delete(id); reject(new Error(`CDP command timed out: ${method}`)); }, 15000);
    requests.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
function acknowledge(sessionId) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ id: ++nextId, method: 'Page.screencastFrameAck', params: { sessionId } }));
  }
}
function jpegSize(buffer) {
  if (buffer[0] !== 0xff || buffer[1] !== 0xd8) throw new Error('CDP frame is not a JPEG');
  let offset = 2;
  const dimensions = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]);
  while (offset < buffer.length - 9) {
    if (buffer[offset] !== 0xff) throw new Error('Invalid JPEG marker');
    while (buffer[offset] === 0xff) offset++;
    const marker = buffer[offset++];
    if (marker === 0xd9 || marker === 0xda) break;
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd8)) continue;
    const length = buffer.readUInt16BE(offset);
    if (length < 2 || offset + length > buffer.length) throw new Error('Truncated JPEG');
    if (dimensions.has(marker)) return { height: buffer.readUInt16BE(offset + 3), width: buffer.readUInt16BE(offset + 5) };
    offset += length;
  }
  throw new Error('JPEG frame has no dimensions');
}
function onFrame(params) {
  const received = Date.now();
  acknowledge(params.sessionId); // Do not wait for disk I/O before releasing the next frame.
  if (stoppedAt !== undefined || fatalError) return;
  try {
    const buffer = Buffer.from(params.data, 'base64');
    const dimensions = jpegSize(buffer);
    if (!firstImage) firstImage = dimensions;
    if (dimensions.width !== firstImage.width || dimensions.height !== firstImage.height) {
      throw new Error('WebView changed dimensions during capture');
    }
    const isFirst = epoch === undefined;
    if (isFirst) epoch = received;
    const sequence = frames.length + 1;
    const file = `frames/frame-${String(sequence).padStart(6, '0')}.jpg`;
    const entry = {
      sequence, file, received_epoch_ms: received, seconds: (received - epoch) / 1000,
      source_timestamp: params.metadata?.timestamp ?? null,
      source_monotonic_timestamp: params.metadata?.monotonicTimestamp ?? null,
      metadata: params.metadata || {}, sha256: createHash('sha256').update(buffer).digest('hex'), bytes: buffer.length,
    };
    frames.push(entry);
    pendingBytes += buffer.length;
    if (pendingBytes > 128 * 1024 * 1024) throw new Error('Frame storage cannot keep up with the recorder');
    writing = writing.then(async () => {
      await writeFile(path.join(output, file), buffer, { flag: 'wx' });
      await appendFile(path.join(framesDirectory, 'index.ndjson'), JSON.stringify(entry) + '\n', 'utf8');
      pendingBytes -= buffer.length;
    }).catch(fail);
    if (isFirst) {
      emit({ type: 'ready', epoch_ms: epoch });
      resolveReady();
    }
  } catch (error) { fail(error); }
}
async function readJson(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`CDP discovery returned HTTP ${response.status}`);
  return response.json();
}
async function runFfmpeg(args, logName) {
  const log = createWriteStream(path.join(output, logName), { flags: 'wx' });
  let tail = '';
  const code = await new Promise((resolve, reject) => {
    const child = spawn(ffmpeg, args, { cwd: output, windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
    child.stderr.on('data', data => { log.write(data); tail = (tail + data.toString('utf8')).slice(-24000); });
    child.once('error', reject);
    child.once('close', resolve);
  }).finally(() => new Promise(resolve => log.end(resolve)));
  if (code !== 0) throw new Error(`FFmpeg failed with exit code ${code}; inspect ${logName}`);
  return tail;
}
async function main() {
  await access(ffmpeg);
  await mkdir(output, { recursive: true });
  for (const name of names) {
    try {
      await access(path.join(output, name));
      throw new Error(`Refusing to overwrite existing capture output: ${name}`);
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  const origin = `http://${options['debugger-address']}`;
  const candidates = await readJson(`${origin}/json/list`);
  const targets = candidates.filter(target => {
    if (target.type !== 'page') return false;
    try {
      const url = new URL(target.url);
      return ['http:', 'https:'].includes(url.protocol) && url.hostname === 'tauri.localhost';
    } catch { return false; }
  });
  if (targets.length !== 1) throw new Error(`Expected one tauri.localhost page target, found ${targets.length}`);
  const target = targets[0];
  const websocketUrl = new URL(target.webSocketDebuggerUrl);
  if (!['localhost', '127.0.0.1', '[::1]'].includes(websocketUrl.hostname)) throw new Error('CDP endpoint is not loopback');
  const protocol = await readJson(`${origin}/json/protocol`);
  const pageCommands = protocol.domains.find(domain => domain.domain === 'Page')?.commands || [];
  for (const name of ['startScreencast', 'screencastFrameAck', 'stopScreencast']) {
    if (!pageCommands.some(command => command.name === name)) throw new Error(`Runtime does not support Page.${name}`);
  }
  await mkdir(framesDirectory);
  await writeFile(path.join(framesDirectory, 'index.ndjson'), '', { flag: 'wx' });
  socket = new WebSocket(websocketUrl);
  socket.addEventListener('message', event => {
    try {
      const message = JSON.parse(event.data);
      if (message.method === 'Page.screencastFrame') onFrame(message.params);
      const request = requests.get(message.id);
      if (request) {
        clearTimeout(request.timer);
        requests.delete(message.id);
        if (message.error) request.reject(new Error(`CDP command failed (${message.error.code})`));
        else request.resolve(message.result);
      }
    } catch (error) { fail(error); }
  });
  socket.addEventListener('error', () => fail(new Error('CDP WebSocket error')));
  socket.addEventListener('close', () => {
    if (stoppedAt === undefined) fail(new Error('CDP WebSocket closed during recording'));
    for (const request of requests.values()) { clearTimeout(request.timer); request.reject(new Error('CDP socket closed')); }
    requests.clear();
  });
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('CDP connection timed out')), 10000);
    socket.addEventListener('open', () => { clearTimeout(timeout); resolve(); }, { once: true });
    socket.addEventListener('error', () => { clearTimeout(timeout); reject(new Error('Could not connect to CDP')); }, { once: true });
  });
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', data => { if (data.includes('q')) requestStop('q'); });
  process.stdin.on('end', () => requestStop('stdin_closed'));
  process.on('SIGINT', () => requestStop('SIGINT'));
  process.on('SIGTERM', () => requestStop('SIGTERM'));
  await send('Page.enable');
  await send('Page.startScreencast', { format: 'jpeg', quality: 95, maxWidth: 1920, maxHeight: height, everyNthFrame: 1 });
  const readyTimeout = setTimeout(() => fail(new Error('No screencast frame arrived within 20 seconds')), 20000);
  await ready.finally(() => clearTimeout(readyTimeout));
  await stopped;
  await send('Page.stopScreencast').catch(error => { if (!fatalError) fatalError = error; });
  socket.close();
  await writing;
  if (fatalError) throw fatalError;
  if (!frames.length || epoch === undefined || stoppedAt <= epoch) throw new Error('No usable recording duration');
  const duration = (stoppedAt - epoch) / 1000;
  // Two compositor events can arrive in the same millisecond. Keep the latest
  // of those for encoding while retaining every original JPEG in the index.
  const visibleFrames = [];
  for (const frame of frames) {
    if (visibleFrames.at(-1)?.received_epoch_ms === frame.received_epoch_ms) visibleFrames[visibleFrames.length - 1] = frame;
    else visibleFrames.push(frame);
  }
  const concat = ['ffconcat version 1.0'];
  for (let index = 0; index < visibleFrames.length; index++) {
    const frame = visibleFrames[index];
    const next = visibleFrames[index + 1]?.seconds ?? duration;
    concat.push(`file '${frame.file}'`, 'option framerate 1000', `duration ${Math.max(0.000001, next - frame.seconds).toFixed(6)}`);
  }
  concat.push(`file '${visibleFrames.at(-1).file}'`, 'option framerate 1000');
  await writeFile(path.join(output, 'capture.ffconcat'), concat.join('\n') + '\n', { flag: 'wx' });
  await writeFile(path.join(output, 'frame-index.json'), JSON.stringify({ epoch_ms: epoch, stop_epoch_ms: stoppedAt, duration, frames }, null, 2) + '\n', { flag: 'wx' });
  // Chromium JPEGs decode as full-range BT.601 YCbCr. Convert samples as well
  // as metadata: merely requesting yuv420p leaves the JPEG full-range flag and
  // can produce an MP4 that decodes as yuvj420p with incorrect video levels.
  const encodeArgs = ['-hide_banner', '-nostdin', '-n', '-safe', '0', '-f', 'concat', '-i', 'capture.ffconcat',
    '-vf', `scale=1920:${height}:force_original_aspect_ratio=decrease:force_divisible_by=2:in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p,pad=1920:${height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30`,
    '-t', duration.toFixed(6), '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', '4',
    '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
    '-fps_mode', 'cfr', '-movflags', '+faststart', 'capture.partial.mp4'];
  await runFfmpeg(encodeArgs, 'capture-encode.log');
  const decoded = await runFfmpeg(['-hide_banner', '-nostdin', '-i', 'capture.partial.mp4', '-map', '0:v:0', '-an', '-f', 'null', '-'], 'capture-decode.log');
  if (!new RegExp(`Video: h264.*yuv420p\\(tv, bt709.*1920x${height}`).test(decoded) || /Stream #\d+:\d+.*Audio:/.test(decoded)) {
    throw new Error('Encoded recording has unexpected dimensions, codec, pixel format, or audio');
  }
  if (/error while|invalid data|corrupt decoded|decoding error/i.test(decoded)) throw new Error('Encoded recording did not decode cleanly');
  const decodedFrameMatches = [...decoded.matchAll(/frame=\s*(\d+)/g)];
  const encodedFrames = Number(decodedFrameMatches.at(-1)?.[1]);
  if (!encodedFrames || Math.abs(encodedFrames / 30 - duration) > 0.1) throw new Error('Encoded duration does not match wall-clock duration');
  await rename(path.join(output, 'capture.partial.mp4'), path.join(output, 'capture.mp4'));
  const report = {
    passed: true, started_at_utc: startedAt, finished_at_utc: new Date().toISOString(), end_reason: endReason,
    recording_method: 'WebView2 Page.startScreencast compositor frames', target_url: target.url,
    epoch_ms: epoch, stop_epoch_ms: stoppedAt, duration, encoded_duration: encodedFrames / 30,
    fps: 30, frames: frames.length, encoded_frames: encodedFrames, unique_hashes: new Set(frames.map(frame => frame.sha256)).size,
    source_dimensions: firstImage, output_dimensions: { width: 1920, height }, full_decode_passed: true,
    color_conversion: 'JPEG full-range BT.601 to limited-range BT.709; actual sample conversion and matching H.264 metadata',
    raw_video: path.join(output, 'capture.mp4'), raw_video_bytes: (await stat(path.join(output, 'capture.mp4'))).size,
    timing: 'Frame reception wall-clock time, with the final frame held until q; static frames are repeated, not time-compressed.',
    limitations: ['Only the actual WebView content is captured; native Save dialogs, window borders, and the system pointer are outside this recording.'],
  };
  await writeFile(path.join(output, 'capture-webview-report.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  emit({ type: 'finished', ...report });
}

main().catch(async error => {
  requestStop('error');
  if (socket?.readyState === WebSocket.OPEN) {
    await send('Page.stopScreencast').catch(() => {});
    socket.close();
  }
  await writing.catch(() => {});
  const report = { passed: false, started_at_utc: startedAt, finished_at_utc: new Date().toISOString(),
    end_reason: 'error', error: error.message, epoch_ms: epoch ?? null, frames: frames.length };
  // Preserve existing outputs even when startup rejected an occupied directory.
  await writeFile(path.join(output, 'capture-webview-report.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' }).catch(() => {});
  process.stderr.write(`Capture failed: ${error.message}\n`);
  process.exitCode = 1;
}).finally(() => {
  for (const request of requests.values()) clearTimeout(request.timer);
  requests.clear();
  process.stdin.pause();
});
