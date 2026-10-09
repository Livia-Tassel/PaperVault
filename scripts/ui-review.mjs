/** Read-only visual review against an already-running UI and real test library.
 * Does not launch services, import papers, modify metadata, or fabricate data.
 * node scripts/ui-review.mjs --url http://127.0.0.1:1420 --api http://127.0.0.1:8765/api/v1
 */
import { createRequire } from 'node:module';
import { parseArgs } from 'node:util';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(new URL('../apps/desktop/package.json', import.meta.url));
const { chromium, expect } = require('@playwright/test');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { values } = parseArgs({ options: {
  url: { type: 'string', default: process.env.PAPERVAULT_UI_URL || 'http://127.0.0.1:1420' },
  api: { type: 'string', default: process.env.PAPERVAULT_E2E_API_URL || 'http://127.0.0.1:8765/api/v1' },
  token: { type: 'string', default: process.env.PAPERVAULT_E2E_TOKEN || 'dev-token' },
  output: { type: 'string', default: path.join(root, 'artifacts', 'ui-review') },
  query: { type: 'string' },
  paper: { type: 'string' },
  channel: { type: 'string', default: process.env.PAPERVAULT_BROWSER || (process.platform === 'win32' ? 'msedge' : '') },
} });
const apiBase = values.api.replace(/\/$/, '');
const output = path.resolve(values.output);
const report = { status: 'running', started_at: new Date().toISOString(), url: values.url,
  api: apiBase, method: 'Read-only UI navigation and screenshots using existing parsed PDFs and persisted resources; no mocked API responses.',
  cases: [], javascript_errors: [], failed_requests: [], blocked_mutations: [] };
await mkdir(output, { recursive: true });

async function get(endpoint) {
  const response = await fetch(`${apiBase}${endpoint}`, { headers: { Authorization: `Bearer ${values.token}` } });
  if (!response.ok) throw new Error(`Existing API ${endpoint}: HTTP ${response.status}`);
  return response.json();
}

const library = await get('/library');
if (!library.path || !library.path.replaceAll('\\', '/').toLowerCase().includes('/.test-data/')) {
  throw new Error('Visual review requires an already-open real library under this workspace .test-data directory.');
}
const papers = await get('/papers?limit=200');
const paper = papers.items.find(item => values.paper && (item.id === values.paper || item.filename === values.paper))
  || papers.items.find(item => ['completed', 'partial', 'partial_success'].includes(item.status) && !/benchmark/i.test(item.filename))
  || papers.items.find(item => !/benchmark/i.test(item.filename));
if (!paper) throw new Error('No existing paper is available for the reader screenshot.');
const resources = await get(`/resources?paper_id=${encodeURIComponent(paper.id)}&limit=200`);
const jobs = await get('/jobs');
let query = values.query;
if (!query) {
  for (const candidate of ['pipeline', 'Docling', '深度', 'research']) {
    const hits = await get(`/search?q=${encodeURIComponent(candidate)}`);
    if (['papers', 'figures', 'tables', 'content'].some(key => hits[key]?.length)) { query = candidate; break; }
  }
}
if (!query) throw new Error('Could not find a real populated search result; pass --query with an existing term.');
report.library = { path: library.path, papers: papers.total, resource_count: resources.total,
  jobs: jobs.total ?? jobs.items.length, selected_paper: { id: paper.id, filename: paper.filename, status: paper.status }, query };

const browser = await chromium.launch({ headless: true, ...(values.channel ? { channel: values.channel } : {}) });
report.browser = browser.version();
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1,
    colorScheme: 'light', reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  page.on('pageerror', error => report.javascript_errors.push(error.message));
  page.on('response', response => {
    if (response.status() >= 400 && response.url().includes('/api/v1/'))
      report.failed_requests.push({ url: response.url(), status: response.status() });
  });
  page.on('requestfailed', request => {
    if (request.failure()?.errorText !== 'net::ERR_ABORTED')
      report.failed_requests.push({ url: request.url(), error: request.failure()?.errorText });
  });
  // Keep the data read-only, even if a redesign accidentally wires a nav control
  // to a mutating action. The review controls only ephemeral browser preferences.
  await page.route('**/api/v1/**', async route => {
    const request = route.request();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      report.blocked_mutations.push({ method: request.method(), url: request.url() });
      await route.abort('blockedbyclient');
      return;
    }
    const original = new URL(request.url());
    const suffix = original.pathname.split('/api/v1')[1] || '';
    await route.continue({ url: `${apiBase}${suffix}${original.search}`,
      headers: { ...request.headers(), authorization: `Bearer ${values.token}` } });
  });
  await page.goto(values.url);
  await expect(page.getByRole('heading', { name: '论文库', exact: true })).toBeVisible();

  async function nav(name) {
    if (await page.getByRole('dialog').count()) {
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);
    }
    await page.locator('.sidebar').getByRole('button', { name: new RegExp(`^${name}`) }).first().click();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  }

  async function settle() {
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(180);
  }

  async function snapshot(name, theme, extra = {}) {
    await settle();
    const geometry = await page.evaluate(() => {
      const metrics = selector => {
        const element = document.querySelector(selector);
        if (!element) return null;
        const box = element.getBoundingClientRect();
        const css = getComputedStyle(element);
        return { x: box.x, y: box.y, width: box.width, height: box.height,
          scroll_width: element.scrollWidth, client_width: element.clientWidth,
          min_width: css.minWidth, border_radius: css.borderRadius, box_shadow: css.boxShadow,
          font_size: css.fontSize, line_height: css.lineHeight, background: css.backgroundColor };
      };
      return { html_theme: document.documentElement.dataset.theme, viewport: { width: innerWidth, height: innerHeight },
        body: metrics('body'), sidebar: metrics('.sidebar'), header: metrics('.page-header'), main: metrics('.main-area'),
        reader: metrics('.pdf-reader'), reader_panel: metrics('.paper-side'),
        first_paper: metrics('.paper-item'), first_result: metrics('.search-result'),
        broken_images: [...document.querySelectorAll('img')].filter(image => image.complete && image.naturalWidth === 0).length };
    });
    const destination = path.join(output, `${theme}-${name}.png`);
    await page.screenshot({ path: destination, animations: 'disabled' });
    report.cases.push({ name, theme, screenshot: path.relative(root, destination).replaceAll('\\', '/'), geometry, ...extra });
    await writeFile(path.join(output, 'review.json'), JSON.stringify(report, null, 2));
  }

  async function openReader() {
    await nav('论文库');
    await page.getByLabel('搜索论文', { exact: true }).fill(paper.filename);
    await expect(page.locator('.paper-primary')).toHaveCount(1);
    await page.locator('.paper-primary').click();
    await expect(page.getByRole('region', { name: 'PDF 阅读器', exact: true })).toBeVisible();
    const canvas = page.locator('.pdf-page canvas').first();
    await expect(canvas).toBeVisible();
    await expect.poll(() => canvas.evaluate(element => element.width)).toBeGreaterThan(0);
  }

  for (const theme of ['light', 'dark']) {
    await nav('设置');
    await page.getByRole('button', { name: theme === 'light' ? '浅色' : '深色', exact: true }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await expect(page.locator('.paper-item').first()).toBeVisible();
    await snapshot('library', theme);
    const expandedWidth = await page.locator('.sidebar').evaluate(element => element.getBoundingClientRect().width);
    await page.getByRole('button', { name: '收起侧栏', exact: true }).click();
    await expect(page.getByRole('button', { name: '展开侧栏', exact: true })).toHaveAttribute('aria-expanded', 'false');
    await page.reload();
    await expect(page.getByRole('button', { name: '展开侧栏', exact: true })).toHaveAttribute('aria-expanded', 'false');
    const collapsedWidth = await page.locator('.sidebar').evaluate(element => element.getBoundingClientRect().width);
    expect(collapsedWidth).toBe(56);
    expect(await page.evaluate(() => localStorage.getItem('papervault-sidebar'))).toBe('collapsed');
    await snapshot('library-sidebar-collapsed', theme, { expanded_width: expandedWidth, collapsed_width: collapsedWidth });
    await page.getByRole('button', { name: '展开侧栏', exact: true }).click();
    await page.reload();
    await expect(page.getByRole('button', { name: '收起侧栏', exact: true })).toHaveAttribute('aria-expanded', 'true');
    expect(await page.evaluate(() => localStorage.getItem('papervault-sidebar'))).toBe('expanded');
    report.sidebar_persistence = { collapsed_after_reload: true, expanded_after_reload: true };

    await openReader();
    await snapshot('reader', theme);
    const outline = page.getByRole('button', { name: '目录', exact: true });
    if (await outline.count()) {
      await outline.click();
      await snapshot('reader-outline', theme);
    }

    for (const [label, name] of [['图片库', 'figures'], ['表格库', 'tables']]) {
      await nav(label);
      const expectedKind = name === 'figures' ? 'figure' : 'table';
      if (resources.items.some(resource => resource.kind === expectedKind))
        await expect(page.locator('.resource-card').first()).toBeVisible();
      if (await page.locator('.resource-card').count()) {
        const image = page.locator('.resource-card img').first();
        if (await image.count()) await expect.poll(() => image.evaluate(element => element.naturalWidth)).toBeGreaterThan(0);
      }
      await snapshot(name, theme);
      if (name === 'tables' && await page.locator('.resource-card-image').count()) {
        await page.locator('.resource-card-image').first().click();
        await expect(page.getByRole('dialog')).toBeVisible();
        await expect(page.locator('.table-scroll')).toBeVisible();
        await snapshot('table-detail', theme);
        await page.keyboard.press('Escape');
      }
    }

    await page.keyboard.press('Control+k');
    const search = page.getByLabel('全局全文搜索', { exact: true });
    await expect(search).toBeFocused();
    await search.fill(query);
    await expect(page.locator('.search-result').first()).toBeVisible();
    await snapshot('search', theme);

    await nav('解析任务');
    if (jobs.items.length) await expect(page.locator('.job-card').first()).toBeVisible();
    await snapshot('tasks', theme);
    await nav('设置');
    await page.locator('.main-area').evaluate(element => { element.scrollTop = 0; });
    await snapshot('settings', theme);
    await page.getByRole('button', { name: '跟随系统', exact: true }).scrollIntoViewIfNeeded();
    await snapshot('settings-preferences', theme);

    await page.setViewportSize({ width: 1280, height: 800 });
    await nav('论文库');
    await expect(page.locator('.paper-item').first()).toBeVisible();
    await snapshot('library-compact', theme);
    await openReader();
    await snapshot('reader-compact', theme);
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  report.status = report.javascript_errors.length || report.blocked_mutations.length || report.failed_requests.length ? 'needs-review' : 'captured';
  await context.close();
} catch (error) {
  report.status = 'failed';
  report.error = error.stack || String(error);
  process.exitCode = 1;
} finally {
  report.finished_at = new Date().toISOString();
  await writeFile(path.join(output, 'review.json'), JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify({ status: report.status, screenshots: report.cases.length,
    report: path.join(output, 'review.json'), error: report.error }, null, 2));
}
