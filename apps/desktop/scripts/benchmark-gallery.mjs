/** Real browser/API measurement. API port forwarding is not a response mock. */
import { chromium } from '@playwright/test';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import os from 'node:os';

const workspace = new URL('../../../', import.meta.url);
const datasetPath = process.env.PAPERVAULT_GALLERY_DATASET || fileURLToPath(new URL('.test-data/gallery-benchmark-library/benchmark-dataset.json', workspace));
const dataset = JSON.parse(await readFile(datasetPath, 'utf8'));
const api = process.env.PAPERVAULT_GALLERY_API || 'http://127.0.0.1:8766/api/v1';
const token = process.env.PAPERVAULT_GALLERY_TOKEN || 'dev-token';
const frontend = process.env.PAPERVAULT_GALLERY_FRONTEND || 'http://127.0.0.1:1420';
const health = await fetch(`${api}/library`, { headers: { Authorization: `Bearer ${token}` } });
if (!health.ok) throw new Error(`Benchmark backend unavailable (${health.status})`);
const info = await health.json();
if (info.figure_count !== dataset.figures) throw new Error(`Expected ${dataset.figures} resources, got ${info.figure_count}`);
const browser = await chromium.launch({ channel: process.env.PAPERVAULT_BROWSER || 'msedge', headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const errors = [];
  const failedResponses = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => { if (response.status() >= 400) failedResponses.push({ url: response.url(), status: response.status() }); });
  await page.route('http://127.0.0.1:8765/api/v1/**', route => route.continue({
    url: route.request().url().replace('http://127.0.0.1:8765/api/v1', api),
    headers: { ...route.request().headers(), authorization: `Bearer ${token}` },
  }));
  const navigationStart = performance.now();
  await page.goto(frontend);
  await page.getByRole('heading', { name: '论文库', exact: true }).waitFor();
  const appReadyMs = performance.now() - navigationStart;
  const galleryStart = await page.evaluate(() => performance.now());
  await page.getByRole('button', { name: /^图片库/ }).click();
  await page.waitForFunction(() => document.querySelectorAll('.resource-card').length === 24);
  await page.waitForFunction(() => {
    const images = [...document.querySelectorAll('.resource-card-image img')];
    const visible = images.filter(image => { const r = image.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight && r.right > 224 && r.left < innerWidth; });
    return visible.length > 0 && visible.every(image => image.complete && image.naturalWidth > 0);
  });
  const firstScreen = await page.evaluate(start => {
    const imgs = [...document.querySelectorAll('.resource-card-image img')];
    const visible = imgs.filter(img => { const r = img.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight && r.right > 224 && r.left < innerWidth; });
    return { ready_ms: performance.now() - start, visible_images: visible.length,
      visible_images_decoded: visible.filter(img => img.complete && img.naturalWidth > 0).length,
      page_dom_images: imgs.length, page_dom_cards: document.querySelectorAll('.resource-card').length };
  }, galleryStart);
  const scrollPasses = [];
  for (let pass = 0; pass < 3; pass++) {
    const result = await page.evaluate(async ({ duration, pass }) => {
      const scroller = document.querySelector('.main-area');
      if (!scroller) throw new Error('Missing gallery scroll container');
      const maxScroll = scroller.scrollHeight - scroller.clientHeight;
      if (maxScroll <= 0) throw new Error('Gallery does not scroll at the benchmark viewport');
      scroller.scrollTop = 0;
      const intervals = [];
      const frameChecks = [];
      const decodedIds = new Set();
      const start = performance.now();
      let previous;
      let maxDomImages = 0;
      let visibleFailures = 0;
      await new Promise(resolve => {
        const tick = timestamp => {
          if (previous !== undefined) intervals.push(timestamp - previous);
          previous = timestamp;
          const progress = Math.min(1, (timestamp - start) / duration);
          scroller.scrollTop = maxScroll * (progress < .5 ? progress * 2 : (1 - progress) * 2);
          const images = [...document.querySelectorAll('.resource-card-image img')];
          maxDomImages = Math.max(maxDomImages, images.length);
          let visible = 0;
          let decoded = 0;
          for (const image of images) {
            const bounds = image.getBoundingClientRect();
            if (bounds.bottom > 0 && bounds.top < innerHeight && bounds.right > 224 && bounds.left < innerWidth) {
              visible++;
              if (image.complete && image.naturalWidth > 0) { decoded++; decodedIds.add(image.src); }
              else visibleFailures++;
            }
          }
          frameChecks.push({ visible, decoded });
          if (progress < 1) requestAnimationFrame(tick);
          else resolve();
        };
        requestAnimationFrame(tick);
      });
      return { pass, duration_ms: performance.now() - start, max_scroll_px: maxScroll,
        intervals, max_dom_images: maxDomImages, unique_visible_images_decoded: decodedIds.size,
        visible_image_checks: frameChecks.reduce((n, f) => n + f.visible, 0),
        visible_image_decode_successes: frameChecks.reduce((n, f) => n + f.decoded, 0),
        visible_image_not_ready_checks: visibleFailures };
    }, { duration: 6000, pass: pass + 1 });
    scrollPasses.push(result);
  }
  const nextStart = await page.evaluate(() => performance.now());
  const beforeTitle = await page.locator('.resource-title').first().textContent();
  await page.getByRole('button', { name: '下一页', exact: true }).click();
  await page.waitForFunction(previous => document.querySelector('.resource-title')?.textContent !== previous, beforeTitle);
  await page.evaluate(() => { document.querySelector('.main-area').scrollTop = 0; });
  await page.waitForFunction(() => {
    const visible = [...document.querySelectorAll('.resource-card-image img')].filter(img => { const r = img.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; });
    return visible.length > 0 && visible.every(img => img.complete && img.naturalWidth > 0);
  });
  const paginationMs = await page.evaluate(start => performance.now() - start, nextStart);
  const frameIntervals = scrollPasses.flatMap(pass => pass.intervals);
  const percentile = (values, p) => [...values].sort((a, b) => a - b)[Math.max(0, Math.ceil(values.length * p) - 1)];
  const round = value => Math.round(value * 1000) / 1000;
  const summarize = values => ({ count: values.length, p50_ms: round(percentile(values, .5)), p95_ms: round(percentile(values, .95)), max_ms: round(Math.max(...values)), frames_over_33_4_ms: values.filter(v => v > 33.4).length });
  const report = {
    measured_at: new Date().toISOString(), dataset,
    machine: { ...dataset.machine, node: process.version, cpu_model: os.cpus()[0]?.model, browser: await browser.version(),
      browser_channel: process.env.PAPERVAULT_BROWSER || 'msedge', headless: true, viewport: { width: 1440, height: 1000 }, device_scale_factor: 1 },
    method: { frontend, runtime: 'Vite development server, actual React application', backend: api,
      api_routing: 'Browser test redirects default API port 8765 to isolated 8766; all responses and images come from the real backend, no mocks',
      first_screen: 'New browser context; navigation click to 24 cards and all currently visible images loaded and decoded',
      scroll: 'Three six-second requestAnimationFrame passes down and back up the real gallery scroll container; rAF intervals measured in page context',
      limitation: '1000 library records, 24 resources per real pagination page; this does not measure 1000 simultaneous images, physical input latency, desktop install startup, parser accuracy or uncached diverse-image decoding' },
    application_ready_ms: round(appReadyMs), first_screen: { ...firstScreen, ready_ms: round(firstScreen.ready_ms) },
    next_page_visible_decoded_ms: round(paginationMs), scroll_frame_intervals: summarize(frameIntervals),
    scroll_passes: scrollPasses.map(({ intervals, ...pass }) => ({ ...pass, duration_ms: round(pass.duration_ms), frame_intervals: summarize(intervals) })),
    javascript_errors: errors, failed_http_responses: failedResponses,
  };
  const output = new URL('artifacts/gallery-benchmark.json', workspace);
  await mkdir(new URL('artifacts/', workspace), { recursive: true });
  await writeFile(output, `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (errors.length || failedResponses.length || firstScreen.visible_images !== firstScreen.visible_images_decoded) throw new Error('Gallery benchmark encountered rendering/network errors; see report');
} finally {
  await browser.close();
}
