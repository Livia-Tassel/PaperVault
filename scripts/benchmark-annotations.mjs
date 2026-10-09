/** Real local API + production UI benchmark, isolated from the shared dev library.
 * Creates explicitly SYNTHETIC annotations on ONE genuine academic.pdf copy.
 * No production source is edited. Re-run: node scripts/benchmark-annotations.mjs
 */
import { createRequire } from 'node:module';
import { spawn, execFileSync } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';
import { createWriteStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(new URL('../apps/desktop/package.json', import.meta.url));
const { chromium, expect } = require('@playwright/test');
const { values } = parseArgs({ options: { count: { type: 'string', default: '1000' }, output: { type: 'string', default: path.join(root, 'artifacts/annotation-benchmark') }, channel: { type: 'string', default: process.platform === 'win32' ? 'msedge' : '' } } });
const count = Number(values.count);
if (!Number.isInteger(count) || count < 1000 || count > 10000) throw new Error('Use 1000–10000 explicitly synthetic annotations.');
const output = path.resolve(values.output), runId = Date.now();
const dataset = path.join(root, '.test-data', `annotation-benchmark-${runId}`), libraryPath = path.join(dataset, 'library');
const dist = path.join(root, 'apps/desktop/dist'), fixture = path.join(root, 'tests/fixtures/academic.pdf');
await mkdir(output, { recursive: true }); await mkdir(dataset, { recursive: true });
const bundleIndex = await readFile(path.join(dist, 'index.html'));
const entry = bundleIndex.toString().match(/src="([^"]+\.js)"/)?.[1];
if (!entry) throw new Error('Build the production UI first; this benchmark does not modify/build it.');
const entryBytes = await readFile(path.join(dist, entry));
const report = { status: 'running', started_at: new Date().toISOString(), synthetic_data: true,
  scope: 'ONE real academic.pdf copy; synthetic annotation metadata/rectangles are a rendering workload, not extracted facts or parser accuracy evidence.',
  source_pdf: path.relative(root, fixture), source_pdf_sha256: createHash('sha256').update(await readFile(fixture)).digest('hex'),
  library: libraryPath, annotation_count: count, locations_per_annotation: 3,
  runtime: 'Existing production dist assets fulfilled from disk at the approved 1420 origin; all API responses come from a separate real sidecar. No shared 8765 requests.',
  browser_harness_permission: 'local-network-access granted only to the isolated test context at http://127.0.0.1:1420; necessary because a disk-fulfilled document has no address-space classification.',
  production_bundle: { entry, sha256: createHash('sha256').update(entryBytes).digest('hex'), bytes: entryBytes.length, modified_at: (await stat(path.join(dist, entry))).mtime.toISOString() },
  machine: { platform: os.platform(), release: os.release(), cpu: os.cpus()[0]?.model, logical_cpus: os.cpus().length, ram_bytes: os.totalmem() },
  thresholds_declared_before_run: { ui_action_warning_ms: 1000, reader_open_warning_ms: 3000, scrolling_frame_p95_warning_ms: 33.4, sustained_long_task_warning_ms: 200 },
  api_measurements: [], browser_phases: [], memory_samples: [], browser_errors: [], api_errors: [], findings: [],
  source_review: [
    'Current source builds a memoized page index per annotation snapshot and memoizes PdfPage plus annotation layers/items, with stable callback props.',
    'Annotation overlays are gated by the near-viewport observer; visited text layers remain mounted to preserve cross-page Selection. The archived before report describes the earlier full-DOM rendering.',
    'usePaperAnnotations reads all annotations in 200-record API pages; global and paper note lists render 30 records at a time.',
  ],
};
const token = randomBytes(24).toString('hex');
const log = createWriteStream(path.join(output, 'backend.log'));
const backend = spawn(path.join(root, '.venv/Scripts/python.exe'), ['-m', 'papervault', '--library', libraryPath, '--config', path.join(dataset, 'config'), '--models', path.join(dataset, 'models')], { cwd: root, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
const exited = new Promise(resolve => backend.once('exit', (code, signal) => resolve({ code, signal })));
backend.stderr.pipe(log, { end: false });
const ready = new Promise((resolve, reject) => {
  let buffered = ''; const timer = setTimeout(() => reject(new Error('Isolated sidecar startup timed out')), 30000);
  backend.stdout.on('data', data => {
    log.write(data); buffered += data.toString();
    for (let newline; (newline = buffered.indexOf('\n')) >= 0;) {
      const line = buffered.slice(0, newline); buffered = buffered.slice(newline + 1);
      try { const event = JSON.parse(line); if (event.type === 'ready') { clearTimeout(timer); resolve(event.port); } } catch {}
    }
  });
  backend.once('error', reject); backend.once('exit', () => { clearTimeout(timer); reject(new Error('Sidecar exited before readiness')); });
});
backend.stdin.write(`${JSON.stringify({ token })}\n`);
let browser, page, api, scope;
async function call(endpoint, method = 'GET', body) {
  const response = await fetch(`${api}${endpoint}`, { method, headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}), ...(scope && method !== 'GET' ? { 'X-PaperVault-Library': encodeURIComponent(scope) } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const value = await response.json(); if (!response.ok) throw new Error(`${method} ${endpoint}: ${response.status} ${JSON.stringify(value)}`); return value;
}
const percentile = (values, fraction) => values.length ? [...values].sort((a, b) => a - b)[Math.min(values.length - 1, Math.floor(values.length * fraction))] : 0;
try {
  const port = await ready; api = `http://127.0.0.1:${port}/api/v1`; report.backend_port = port;
  const library = await call('/library'); scope = `${library.id}:${library.path}`;
  const imported = await call('/papers/import-paths', 'POST', { paths: [fixture], recursive: false });
  const paper = imported.items[0] || imported.duplicates[0]; report.paper_id = paper.id;
  for (const job of (await call('/jobs')).items.filter(job => job.paper_id === paper.id && ['queued', 'running'].includes(job.status))) await call(`/jobs/${job.id}/cancel`, 'POST');
  await call(`/papers/${paper.id}`, 'PATCH', { title: `[SYNTHETIC LOAD] One PDF, ${count} annotations`, authors: ['Synthetic annotation benchmark'] });
  browser = await chromium.launch({ headless: true, ...(values.channel ? { channel: values.channel } : {}) }); report.browser = browser.version();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2, reducedMotion: 'reduce' });
  // Disk-fulfilled documents have no network address-space classification.
  // Grant only this test origin access to its explicitly local isolated sidecar.
  await context.grantPermissions(['local-network-access'], { origin: 'http://127.0.0.1:1420' });
  const mime = { '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.wasm': 'application/wasm', '.png': 'image/png' };
  await context.route('http://127.0.0.1:1420/**', async route => {
    const url = new URL(route.request().url()), relative = decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname);
    const file = path.resolve(dist, `.${relative}`);
    if (!file.startsWith(`${dist}${path.sep}`)) throw new Error('Invalid static asset path');
    await route.fulfill({ path: file, contentType: mime[path.extname(file)] || 'application/octet-stream' });
  });
  await context.addInitScript(() => {
    window.__annotationBench = { phase: null, tasks: [] };
    new PerformanceObserver(list => { for (const task of list.getEntries()) window.__annotationBench.tasks.push({ start: task.startTime, duration: task.duration }); }).observe({ type: 'longtask', buffered: true });
    const frame = now => { const phase = window.__annotationBench.phase; if (phase) { if (phase.last !== null) phase.frames.push(now - phase.last); phase.last = now; } requestAnimationFrame(frame); };
    requestAnimationFrame(frame);
  });
  page = await context.newPage(); page.setDefaultTimeout(30000);
  report.console_errors = []; report.failed_requests = []; report.request_urls = [];
  page.on('console', message => { if (message.type() === 'error') report.console_errors.push(message.text()); });
  page.on('requestfailed', request => report.failed_requests.push({ url: request.url(), error: request.failure()?.errorText }));
  page.on('request', request => report.request_urls.push(request.url()));
  const requests = [];
  page.on('pageerror', error => report.browser_errors.push(error.message));
  page.on('response', response => { if (response.url().includes('/api/v1/')) { requests.push({ url: response.url(), status: response.status() }); if (response.status() >= 400) report.api_errors.push({ url: response.url(), status: response.status() }); } });
  await page.route('**/api/v1/**', route => {
    const original = new URL(route.request().url()), suffix = original.pathname.split('/api/v1')[1];
    return route.continue({ url: `${api}${suffix}${original.search}`, headers: { ...route.request().headers(), authorization: `Bearer ${token}` } });
  });
  const browserCdp = await browser.newBrowserCDPSession(), pageCdp = await context.newCDPSession(page);
  await pageCdp.send('Performance.enable');
  const metrics = async () => Object.fromEntries((await pageCdp.send('Performance.getMetrics')).metrics.map(metric => [metric.name, metric.value]));
  async function begin(label) {
    const before = await metrics();
    await page.evaluate(label => { window.__annotationBench.phase = { label, start: performance.now(), last: null, frames: [] }; }, label);
    return before;
  }
  async function finish(before, extra = {}) {
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const phase = await page.evaluate(() => {
      const bench = window.__annotationBench, phase = bench.phase, end = performance.now(); bench.phase = null;
      return { label: phase.label, elapsed_ms: end - phase.start, frames: phase.frames, long_tasks: bench.tasks.filter(task => task.start >= phase.start && task.start <= end),
        dom_nodes: document.querySelectorAll('*').length, annotation_wrappers: document.querySelectorAll('.reader-annotation').length,
        annotation_rectangles: document.querySelectorAll('.reader-annotation-rect').length, annotation_markers: document.querySelectorAll('.reader-annotation-marker').length,
        visible_note_rows: document.querySelectorAll('.annotation-row').length, js_heap_bytes: performance.memory?.usedJSHeapSize ?? null };
    });
    const after = await metrics();
    const result = { ...phase, frame_p50_ms: percentile(phase.frames, .5), frame_p95_ms: percentile(phase.frames, .95), frame_max_ms: Math.max(0, ...phase.frames),
      frames_above_33ms: phase.frames.filter(value => value > 33.4).length, frames_above_50ms: phase.frames.filter(value => value > 50).length,
      long_task_count: phase.long_tasks.length, max_long_task_ms: Math.max(0, ...phase.long_tasks.map(task => task.duration)),
      cdp_delta_seconds: Object.fromEntries(['TaskDuration', 'ScriptDuration', 'LayoutDuration', 'RecalcStyleDuration'].map(name => [name, after[name] - before[name]])), ...extra };
    delete result.frames; report.browser_phases.push(result); console.log(`${result.label}: ${result.elapsed_ms.toFixed(0)} ms; frame p95 ${result.frame_p95_ms.toFixed(1)} ms; longest task ${result.max_long_task_ms.toFixed(1)} ms; annotation DOM ${result.annotation_rectangles}`);
    await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2)); return result;
  }
  async function memory(label) {
    const processes = await browserCdp.send('SystemInfo.getProcessInfo'), ids = processes.processInfo.map(process => process.id).filter(id => Number.isSafeInteger(id) && id > 0);
    const processMemory = JSON.parse(execFileSync('powershell.exe', ['-NoProfile', '-Command', `@(Get-Process -Id ${ids.join(',')} -ErrorAction SilentlyContinue | Select-Object Id,WorkingSet64,PrivateMemorySize64) | ConvertTo-Json -Compress`], { windowsHide: true, encoding: 'utf8' }));
    const browserState = await metrics();
    report.memory_samples.push({ label, process_memory: processMemory, working_set_bytes: processMemory.reduce((sum, process) => sum + process.WorkingSet64, 0), private_bytes: processMemory.reduce((sum, process) => sum + process.PrivateMemorySize64, 0), cdp_js_heap_bytes: browserState.JSHeapUsedSize, cdp_nodes: browserState.Nodes });
  }
  async function scroll(label) {
    const before = await begin(label);
    await page.evaluate(() => new Promise(resolve => {
      const element = document.querySelector('.pdf-scroll'), start = performance.now(), maximum = element.scrollHeight - element.clientHeight;
      const step = now => { const elapsed = now - start; element.scrollTop = maximum * (.5 - .5 * Math.cos(elapsed / 1000 * Math.PI)); if (elapsed >= 6000) resolve(); else requestAnimationFrame(step); };
      requestAnimationFrame(step);
    }));
    return finish(before, { scripted_scroll_seconds: 6 });
  }
  await page.goto('http://127.0.0.1:1420/'); await expect(page.locator('.paper-primary')).toHaveCount(1);
  let before = await begin('reader-open-0-annotations'); await page.locator('.paper-primary').click();
  await expect(page.locator('[data-page="1"]')).toHaveAttribute('data-text-ready', 'true'); await finish(before); await memory('baseline-reader-0');
  await scroll('reader-scroll-0-annotations');
  await page.getByRole('button', { name: '论文库', exact: true }).click();
  console.log(`Creating ${count} synthetic annotations through the real API...`);
  const started = performance.now(), ids = [], colors = ['amber', 'green', 'blue', 'pink', 'purple']; let bodyCharacters = 0;
  for (let index = 0; index < count; index++) {
    const slot = Math.floor(index / 2) % 500, x = 36 + slot % 10 * 52, y = 66 + Math.floor(slot / 10) * 13, pageIndex = index % 2;
    const body = `[SYNTHETIC BENCHMARK] benchmarktoken${String(index + 1).padStart(4, '0')} cohort${String(index % 20).padStart(2, '0')}. ` +
      'This artificial note exercises local persistence, search, pagination and annotation rendering. It does not state findings from the source paper. '.repeat(4);
    bodyCharacters += body.length;
    const annotation = await call(`/papers/${paper.id}/annotations`, 'POST', { kind: index % 5 === 0 ? 'note' : 'highlight', title: `Synthetic annotation ${String(index + 1).padStart(4, '0')} [benchmark]`,
      quote: index % 5 === 0 ? '' : `Synthetic excerpt ${index + 1}; this is test metadata, not an extracted quotation.`, body, color: colors[index % 5], tags: ['synthetic-benchmark', `cohort${String(index % 20).padStart(2, '0')}`],
      locations: [[x, y, x + 42, y + 3], [x, y + 4, x + 38, y + 7], [x, y + 8, x + 26, y + 11]].map(bbox => ({ page_index: pageIndex, bbox })) });
    ids.push(annotation.id); if ((index + 1) % 200 === 0) console.log(`Created ${index + 1}/${count}`);
  }
  report.creation = { milliseconds: performance.now() - started, mean_body_characters: bodyCharacters / count, highlights: Math.floor(count * .8), notes: Math.ceil(count * .2), total_locations: count * 3 };
  for (const [label, endpoint] of [['first-page', '/annotations?limit=30'], ['last-page', `/annotations?limit=30&offset=${count - 10}`], ['cohort-search', '/annotations?q=cohort07&limit=30'], ['unique-search', '/annotations?q=benchmarktoken0721&limit=30']]) {
    const timings = []; let result;
    for (let sample = 0; sample < 5; sample++) { const start = performance.now(); result = await call(endpoint); timings.push(performance.now() - start); }
    report.api_measurements.push({ label, endpoint, total: result.total, returned: result.items.length, milliseconds: timings, median_ms: percentile(timings, .5) });
  }
  before = await begin('notebook-open-1000'); await page.getByRole('button', { name: '笔记与书签', exact: true }).click();
  await expect(page.locator('.annotation-row')).toHaveCount(30); await expect(page.locator('.collection-subline')).toContainText(`${count} 条`); await finish(before); await memory('notebook-1000');
  await page.screenshot({ path: path.join(output, 'notebook-first-page.png') });
  for (let index = 1; index <= 8; index++) {
    before = await begin(`notebook-page-${index + 1}`); await page.getByRole('button', { name: '下一页', exact: true }).click();
    await expect(page.locator('.annotation-open').first()).toHaveAttribute('data-workspace-focus', `note:${ids[count - 1 - index * 30]}`); await finish(before);
  }
  await page.screenshot({ path: path.join(output, 'notebook-page-nine.png') });
  for (const [term, total] of [['cohort07', count / 20], ['benchmarktoken0721', 1], ['', count]]) {
    before = await begin(`notebook-search-${term || 'clear'}`); await page.getByRole('textbox', { name: '搜索笔记' }).fill(term);
    await expect(page.locator('.collection-subline')).toContainText(`${total} 条`); await expect(page.locator('.annotation-row')).toHaveCount(Math.min(30, total)); await finish(before, { debounce_included: true });
  }
  const requestStart = requests.length;
  before = await begin('reader-open-1000-annotations'); await page.locator('.annotation-row').first().getByRole('button', { name: '原文', exact: true }).click();
  await expect(page.getByRole('tablist', { name: '论文面板' }).getByRole('tab', { name: `笔记 ${count}`, exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(count => {
    const nearPages = document.querySelectorAll('.pdf-page[data-near="true"]').length;
    return nearPages > 0 && document.querySelectorAll('.reader-annotation').length === nearPages * count / 2 && document.querySelectorAll('.reader-annotation-rect').length === nearPages * count / 2 * 3;
  }, count)).toBeTruthy();
  await expect(page.locator('[data-page="2"]')).toHaveAttribute('data-text-ready', 'true'); await finish(before, { annotation_requests: requests.slice(requestStart).filter(request => request.url.includes('/annotations?')).length });
  await memory('reader-1000'); await page.screenshot({ path: path.join(output, 'reader-1000-annotations.png') });
  await scroll('reader-scroll-1000-annotations');
  before = await begin('reader-zoom-1000-annotations'); await page.getByRole('button', { name: '放大', exact: true }).click();
  await expect(page.locator('.zoom-label')).toHaveText('115%'); await expect(page.locator('[data-page="1"]')).toHaveAttribute('data-text-ready', 'true'); await finish(before);
  before = await begin('reader-select-annotation'); await page.locator('.reader-annotation-marker').first().focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('textbox', { name: '笔记标题', exact: true })).toBeVisible(); await finish(before);
  await memory('reader-after-scroll-zoom-selection');
  for (const phase of report.browser_phases) {
    if (phase.label.includes('scroll') && phase.frame_p95_ms > report.thresholds_declared_before_run.scrolling_frame_p95_warning_ms) report.findings.push({ phase: phase.label, issue: 'scroll-frame-p95', actual_ms: phase.frame_p95_ms, threshold_ms: 33.4 });
    if (phase.label.includes('1000') && !phase.label.includes('scroll') && phase.elapsed_ms > (phase.label.startsWith('reader-open') ? 3000 : 1000)) report.findings.push({ phase: phase.label, issue: 'interaction-latency', actual_ms: phase.elapsed_ms });
    if (phase.label.includes('scroll') && phase.max_long_task_ms > 200) report.findings.push({ phase: phase.label, issue: 'sustained-main-thread-block', actual_ms: phase.max_long_task_ms, threshold_ms: 200 });
  }
  report.predeclared_latency_gates_passed = report.findings.length === 0;
  const baselineScroll = report.browser_phases.find(phase => phase.label === 'reader-scroll-0-annotations');
  const annotatedScroll = report.browser_phases.find(phase => phase.label === 'reader-scroll-1000-annotations');
  report.scaling_analysis = {
    baseline_main_thread_fraction: baselineScroll.cdp_delta_seconds.TaskDuration / (baselineScroll.elapsed_ms / 1000),
    annotated_main_thread_fraction: annotatedScroll.cdp_delta_seconds.TaskDuration / (annotatedScroll.elapsed_ms / 1000),
    main_thread_work_ratio: annotatedScroll.cdp_delta_seconds.TaskDuration / baselineScroll.cdp_delta_seconds.TaskDuration,
    interpretation: 'Frame-rate thresholds and API correctness alone do not establish inexpensive rendering. Compare sustained main-thread work and DOM/RSS with the archived before report.',
  };
  if (report.scaling_analysis.annotated_main_thread_fraction > .5 && report.scaling_analysis.main_thread_work_ratio > 3) report.findings.push({
    issue: 'high-sustained-main-thread-work', ...report.scaling_analysis,
    classification: 'Post-measurement scaling diagnosis, separate from the predeclared latency gates; requires review before claiming broad low-end performance.',
  });
  report.annotation_get_requests = requests.filter(request => request.url.includes('/annotations?')).length;
  report.status = report.findings.length || report.browser_errors.length || report.api_errors.length ? 'needs-review' : 'passed';
  await context.close();
} catch (error) {
  report.status = 'failed'; report.error = error.stack || String(error); process.exitCode = 1;
  if (page && !page.isClosed()) { report.failure_page_text = await page.locator('body').innerText().catch(() => ''); await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {}); }
}
finally {
  if (browser) await browser.close();
  if (backend.exitCode === null) backend.stdin.end(`${JSON.stringify({ type: 'shutdown' })}\n`);
  let shutdown = await Promise.race([exited, new Promise(resolve => setTimeout(() => resolve(null), 10000))]);
  if (!shutdown) { backend.kill(); shutdown = await exited; }
  report.backend_shutdown = shutdown; report.finished_at = new Date().toISOString(); log.end();
  await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ status: report.status, report: path.join(output, 'report.json'), library: libraryPath, findings: report.findings, error: report.error }, null, 2));
}
