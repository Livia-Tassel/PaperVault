/** Visual review against existing services and an existing test library.
 * Automatic reading-state PATCH requests are real and explicitly authorized.
 * All content mutations and library switching remain blocked.
 */
import { createRequire } from 'node:module';
import { parseArgs } from 'node:util';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(new URL('../apps/desktop/package.json', import.meta.url));
const { chromium, expect } = require('@playwright/test');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { values } = parseArgs({ options: {
  url: { type: 'string', default: process.env.PAPERVAULT_UI_URL || 'http://127.0.0.1:1420' },
  api: { type: 'string', default: process.env.PAPERVAULT_E2E_API_URL || 'http://127.0.0.1:8765/api/v1' },
  token: { type: 'string', default: process.env.PAPERVAULT_E2E_TOKEN || 'dev-token' },
  output: { type: 'string', default: path.join(root, 'artifacts', 'ui-review-v02') },
  query: { type: 'string' }, paper: { type: 'string' },
  'keyboard-only': { type: 'boolean', default: false },
  channel: { type: 'string', default: process.env.PAPERVAULT_BROWSER || (process.platform === 'win32' ? 'msedge' : '') },
} });
const apiBase = values.api.replace(/\/$/, ''), output = path.resolve(values.output);
const report = { status: 'running', started_at: new Date().toISOString(), url: values.url, api: apiBase,
  method: 'Real API content and real authorized reading-state autosaves. Paper/resource/note content mutations and library switching are blocked. No mocked responses.',
  cases: [], javascript_errors: [], failed_requests: [], blocked_mutations: [], reading_state_writes: [], accessibility: [], findings: [], notes_preview_samples: [] };
await mkdir(output, { recursive: true });
async function get(endpoint) {
  const response = await fetch(`${apiBase}${endpoint}`, { headers: { Authorization: `Bearer ${values.token}` } });
  if (!response.ok) throw new Error(`Existing API ${endpoint}: HTTP ${response.status}`);
  return response.json();
}
const library = await get('/library');
if (!library.path?.replaceAll('\\', '/').toLowerCase().includes('/.test-data/')) throw new Error('Review requires an existing .test-data library.');
const papers = await get('/papers?limit=200');
const paper = papers.items.find(item => values.paper && [item.id, item.filename].includes(values.paper))
  || papers.items.find(item => item.filename.toLowerCase() === 'academic.pdf')
  || papers.items.find(item => item.status === 'completed');
if (!paper) throw new Error('No existing parsed PDF is available.');
const [resources, jobs, notes, paperNotes, recent, originalReading, originalPaper] = await Promise.all([
  get(`/resources?paper_id=${encodeURIComponent(paper.id)}&limit=200`), get('/jobs'), get('/annotations?limit=200'),
  get(`/annotations?paper_id=${encodeURIComponent(paper.id)}&limit=200`), get('/papers?opened=true&sort=last_opened&limit=30'), get(`/papers/${paper.id}/reading-state`), get(`/papers/${paper.id}`),
]);
let query = values.query;
for (const candidate of query ? [] : ['research', 'pipeline', 'Docling', '深度']) {
  const found = await get(`/search?q=${encodeURIComponent(candidate)}`);
  if (['papers', 'figures', 'tables', 'content', 'notes'].some(key => found[key]?.length)) { query = candidate; break; }
}
if (!query) throw new Error('No populated real search query found.');
report.library = { id: library.id, path: library.path, papers: papers.total, resource_count: resources.total, jobs: jobs.total ?? jobs.items.length,
  notes: notes.total, paper_notes: paperNotes.total, recently_opened: recent.total, selected_paper: { id: paper.id, filename: paper.filename, title: paper.title }, query };
const browser = await chromium.launch({ headless: true, ...(values.channel ? { channel: values.channel } : {}) });
report.browser = browser.version();
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'light', reducedMotion: 'reduce' });
  const page = await context.newPage(); page.setDefaultTimeout(20000);
  page.on('pageerror', error => report.javascript_errors.push(error.message));
  page.on('response', response => { if (response.status() >= 400 && response.url().includes('/api/v1/')) report.failed_requests.push({ url: response.url(), status: response.status() }); });
  page.on('requestfailed', request => { if (request.failure()?.errorText !== 'net::ERR_ABORTED') report.failed_requests.push({ url: request.url(), error: request.failure()?.errorText }); });
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), original = new URL(request.url()), suffix = original.pathname.split('/api/v1')[1] || '';
    const readingWrite = /^\/papers\/[^/]+\/reading-state$/.test(suffix) && request.method() === 'PATCH';
    if (readingWrite) report.reading_state_writes.push({ endpoint: suffix, fields: Object.keys(request.postDataJSON()).filter(key => key !== 'expected_version') });
    if (!readingWrite && !['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      report.blocked_mutations.push({ method: request.method(), url: request.url() }); await route.abort('blockedbyclient'); return;
    }
    await route.continue({ url: `${apiBase}${suffix}${original.search}`, headers: { ...request.headers(), authorization: `Bearer ${values.token}` } });
  });
  await page.goto(values.url);
  await expect(page.getByRole('heading', { name: '论文库', exact: true })).toBeVisible();

  async function nav(name) {
    if (await page.getByRole('dialog').count()) { await page.keyboard.press('Escape'); await expect(page.getByRole('dialog')).toHaveCount(0); }
    await page.locator('.sidebar').getByRole('button', { name, exact: true }).click();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  }
  async function snapshot(name, theme, extra = {}) {
    await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(130);
    const geometry = await page.evaluate(() => {
      const metrics = selector => {
        const element = document.querySelector(selector); if (!element) return null;
        const box = element.getBoundingClientRect(), css = getComputedStyle(element);
        return { x: box.x, y: box.y, width: box.width, height: box.height, scroll_width: element.scrollWidth, client_width: element.clientWidth,
          font_size: css.fontSize, line_height: css.lineHeight, background: css.backgroundColor };
      };
      const toolbarProblems = [];
      for (const toolbar of document.querySelectorAll('.pdf-toolbar, .notebook-toolbar, .page-header, .detail-topbar')) {
        const bounds = toolbar.getBoundingClientRect();
        for (const child of toolbar.querySelectorAll('button, input, select')) {
          if (!child.getClientRects().length) continue;
          const rect = child.getBoundingClientRect();
          if (rect.left < bounds.left - 1 || rect.right > bounds.right + 1 || rect.top < bounds.top - 1 || rect.bottom > bounds.bottom + 1)
            toolbarProblems.push({ toolbar: toolbar.className, label: child.getAttribute('aria-label') || child.textContent, left: rect.left, right: rect.right, toolbarRight: bounds.right });
        }
      }
      return { html_theme: document.documentElement.dataset.theme, viewport: { width: innerWidth, height: innerHeight },
        body: metrics('body'), sidebar: metrics('.sidebar'), main: metrics('.main-area'), toolbar: metrics('.pdf-toolbar'), reader: metrics('.pdf-reader'), reader_panel: metrics('.paper-side'),
        first_paper: metrics('.paper-item'), first_note: metrics('.annotation-row'), first_result: metrics('.search-result'),
        toolbar_problems: toolbarProblems, broken_images: [...document.querySelectorAll('img')].filter(image => image.complete && image.naturalWidth === 0).length,
        visible_text_characters: document.querySelector('.main-area')?.innerText.trim().length || 0 };
    });
    const size = geometry.viewport, destination = path.join(output, `${size.width}x${size.height}-${theme}-${name}.png`);
    await page.screenshot({ path: destination, animations: 'disabled' });
    const result = { name, theme, screenshot: path.relative(root, destination).replaceAll('\\', '/'), geometry, ...extra };
    report.cases.push(result);
    if (geometry.toolbar_problems.length || geometry.main?.scroll_width > geometry.main?.client_width + 1 || geometry.broken_images) report.findings.push({ name, theme, viewport: size, toolbar: geometry.toolbar_problems, broken_images: geometry.broken_images, main_overflow: geometry.main?.scroll_width - geometry.main?.client_width });
    await writeFile(path.join(output, 'review.json'), JSON.stringify(report, null, 2));
    console.log(`Captured ${destination}`);
  }
  async function openReader() {
    await nav('论文库'); await page.getByLabel('搜索论文', { exact: true }).fill(paper.filename);
    await expect(page.locator('.paper-primary')).toHaveCount(1); await page.locator('.paper-primary').click();
    await expect(page.getByRole('region', { name: 'PDF 阅读器', exact: true })).toBeVisible();
    await expect(page.getByRole('tablist', { name: '打开的论文' }).getByRole('tab', { selected: true })).toHaveCount(1);
    if (await page.getByRole('button', { name: '展开信息栏', exact: true }).count()) await page.getByRole('button', { name: '展开信息栏', exact: true }).click();
    await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).fill('1'); await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).press('Enter');
    await expect.poll(() => page.locator('[data-page="1"] canvas').evaluate(element => element.width)).toBeGreaterThan(0);
  }
  async function keyboardCheck() {
    const tabs = page.getByRole('tablist', { name: '论文面板' }).getByRole('tab');
    await tabs.first().focus(); await expect(tabs.first()).toBeFocused();
    await page.keyboard.press('Tab');
    report.accessibility.push({ test: 'reader-panel-tab-key', focus: await page.evaluate(() => ({ role: document.activeElement?.getAttribute('role'), label: document.activeElement?.getAttribute('aria-label') || document.activeElement?.textContent, outline: getComputedStyle(document.activeElement).outlineStyle })) });
    await tabs.first().focus(); await page.keyboard.press('ArrowRight');
    const moved = await tabs.nth(1).evaluate(element => element === document.activeElement);
    report.accessibility.push({ test: 'reader-panel-arrow-navigation', moved });
    if (!moved) report.findings.push({ area: 'reader-tabs', severity: 'usability', issue: 'role=tablist does not move focus with ArrowRight; Tab/Enter remains usable.' });
    if (moved) {
      await expect(tabs.first()).toHaveAttribute('aria-selected', 'true');
      await page.keyboard.press('Enter'); await expect(tabs.nth(1)).toHaveAttribute('aria-selected', 'true');
      const tabId = await tabs.nth(1).getAttribute('id'), panelId = await tabs.nth(1).getAttribute('aria-controls');
      await expect(page.locator(`[id="${panelId}"]`)).toHaveAttribute('aria-labelledby', tabId);
      await expect(page.locator(`[id="${panelId}"]`)).toHaveAttribute('role', 'tabpanel');
      if (values['keyboard-only']) await snapshot('reader-keyboard-tabs', 'light');
      await page.keyboard.press('End'); await expect(tabs.last()).toBeFocused();
      await page.keyboard.press('Home'); await expect(tabs.first()).toBeFocused();
      await page.keyboard.press('ArrowLeft'); await expect(tabs.last()).toBeFocused();
      await page.keyboard.press('Home'); await page.keyboard.press('Enter');
      report.accessibility.push({ test: 'reader-tab-home-end-wrap-and-manual-activation', passed: true, panel_labelledby: tabId });
    }
    await page.getByRole('button', { name: '查找 PDF 文字', exact: true }).focus(); await page.keyboard.press('Enter');
    await expect(page.getByRole('textbox', { name: '查找 PDF 中的文字' })).toBeFocused();
    await page.keyboard.press('Escape'); await expect(page.getByRole('search', { name: 'PDF 文字查找' })).toHaveCount(0);
    report.accessibility.push({ test: 'reader-search-keyboard-open-close', passed: true });
    const workspaceTabs = page.getByRole('tablist', { name: '打开的论文' }).getByRole('tab');
    await workspaceTabs.first().focus(); await page.keyboard.press('ArrowRight');
    const workspaceMoved = await workspaceTabs.nth(1).evaluate(element => element === document.activeElement);
    report.accessibility.push({ test: 'workspace-arrow-navigation', moved: workspaceMoved });
    if (!workspaceMoved) report.findings.push({ area: 'workspace-tabs', severity: 'usability', issue: 'role=tablist does not move focus with ArrowRight; Tab/Enter remains usable.' });
    if (workspaceMoved) {
      await page.keyboard.press('Home'); await expect(workspaceTabs.first()).toBeFocused();
      await page.keyboard.press('Enter'); await expect(workspaceTabs.first()).toHaveAttribute('aria-selected', 'true');
      await expect(page.getByRole('region', { name: 'PDF 阅读器', exact: true })).toHaveCount(0);
      await page.keyboard.press('ArrowRight'); await expect(workspaceTabs.nth(1)).toBeFocused();
      await expect(workspaceTabs.first()).toHaveAttribute('aria-selected', 'true');
      if (values['keyboard-only']) await snapshot('workspace-keyboard-tabs', 'light');
      await page.keyboard.press('End'); await expect(workspaceTabs.last()).toBeFocused();
      await page.keyboard.press('Enter'); await expect(page.getByRole('region', { name: 'PDF 阅读器', exact: true })).toBeVisible();
      report.accessibility.push({ test: 'workspace-home-end-and-manual-activation', passed: true });
    }
  }
  async function checkNotesText() {
    if (report.notes_preview_samples.length) return;
    for (const note of notes.items.filter(note => /[<>&]|javascript:/i.test(`${note.title} ${note.quote} ${note.body}`))) {
      const preview = page.locator(`[data-workspace-focus="note:${note.id}"]`);
      if (!await preview.count()) continue;
      const result = await preview.evaluate((element, note) => ({ id: note.id,
        title_literal: !note.title || element.textContent.includes(note.title),
        quote_literal: !note.quote || element.textContent.includes(note.quote),
        body_literal: !note.body || element.textContent.includes(note.body),
        injected_elements: element.querySelectorAll('script,img,iframe,svg,object,embed').length,
        escaped_script: !note.body.includes('<script>') || element.innerHTML.includes('&lt;script&gt;'),
      }), note);
      expect(result.title_literal && result.quote_literal && result.body_literal && result.escaped_script).toBeTruthy();
      expect(result.injected_elements).toBe(0); report.notes_preview_samples.push(result);
    }
  }

  if (values['keyboard-only']) { await openReader(); await keyboardCheck(); }
  for (const viewport of values['keyboard-only'] ? [] : [{ width: 1440, height: 1000 }, { width: 1280, height: 800 }]) {
    await page.setViewportSize(viewport);
    for (const theme of ['light', 'dark']) {
      await nav('设置'); await page.getByRole('button', { name: theme === 'light' ? '浅色' : '深色', exact: true }).click();
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
      await nav('论文库'); await page.getByLabel('搜索论文', { exact: true }).fill('');
      await expect(page.locator('.collection-subline strong')).toHaveText(String(papers.total));
      await expect(page.locator('.paper-item')).toHaveCount(Math.min(30, papers.total));
      await page.locator('.page-content').evaluate(element => { element.scrollTop = 0; }); await snapshot('library', theme);
      await nav('最近阅读'); if (recent.total) await expect(page.locator('.paper-item').first()).toBeVisible(); await snapshot('recent-reading', theme);
      await openReader();
      await page.getByRole('combobox', { name: '页面适应方式' }).selectOption('page'); await snapshot('reader-fit-page', theme);
      await page.getByRole('combobox', { name: '页面适应方式' }).selectOption('width'); await snapshot('reader-fit-width', theme);
      await page.getByRole('tablist', { name: '论文面板' }).getByRole('tab', { name: /^笔记/ }).click();
      if (paperNotes.total) await expect(page.locator('.paper-note-item').first()).toBeVisible(); else await expect(page.getByText('暂无笔记', { exact: true })).toBeVisible();
      await snapshot('reader-notes-panel', theme);
      if (viewport.width === 1440 && theme === 'light') await keyboardCheck();
      await nav('笔记与书签');
      if (notes.total) await expect(page.locator('.annotation-row').first()).toBeVisible();
      await snapshot('notebook', theme);
      await checkNotesText();
      if (await page.locator('.annotation-open').count()) {
        await page.locator('.annotation-open').first().click(); await expect(page.getByRole('dialog', { name: '编辑笔记' })).toBeVisible();
        await snapshot('note-detail', theme); await page.keyboard.press('Escape');
      }
      await page.keyboard.press('Control+k'); const search = page.getByLabel('全局全文搜索', { exact: true });
      await expect(search).toBeFocused(); await search.fill(query); await expect(page.locator('.search-result').first()).toBeVisible(); await snapshot('search', theme);
      await nav('解析任务'); if (jobs.items.length) await expect(page.locator('.job-card').first()).toBeVisible(); await snapshot('tasks', theme);
      await nav('设置'); await page.locator('.page-content').evaluate(element => { element.scrollTop = 0; }); await snapshot('settings', theme);
      await page.getByRole('button', { name: '跟随系统', exact: true }).scrollIntoViewIfNeeded(); await snapshot('settings-preferences', theme);
    }
  }
  const finalPaper = await get(`/papers/${paper.id}`), finalNotes = await get(`/annotations?paper_id=${encodeURIComponent(paper.id)}&limit=200`);
  const content = ({ reading_state, reading_status, last_opened, ...paper }) => paper;
  report.content_preservation = { paper_content_unchanged: JSON.stringify(content(originalPaper)) === JSON.stringify(content(finalPaper)),
    paper_notes_unchanged: JSON.stringify(paperNotes) === JSON.stringify(finalNotes), library_unchanged: (await get('/library')).id === library.id,
    reading_state_before: originalReading, reading_state_after: await get(`/papers/${paper.id}/reading-state`),
    explanation: 'This review intentionally saved real reading position/zoom/status in the existing test library. It did not alter paper, resource, or note content.' };
  const annotationSource = await readFile(path.join(root, 'apps/desktop/src/AnnotationEditor.tsx'), 'utf8');
  const notebookSource = await readFile(path.join(root, 'apps/desktop/src/NotebookPage.tsx'), 'utf8');
  const panelSource = await readFile(path.join(root, 'apps/desktop/src/PaperNotes.tsx'), 'utf8');
  report.notes_preview_security = { source_review: ![annotationSource, notebookSource, panelSource].some(source => /dangerouslySetInnerHTML/.test(source)),
    existing_special_character_records: notes.items.filter(note => /[<>&]|javascript:/i.test(`${note.title} ${note.quote} ${note.body}`)).map(note => note.id),
    explanation: 'Existing list previews render React text nodes, and editors use input/textarea values. No note content or metadata is created or changed by this review.' };
  report.status = report.javascript_errors.length || report.failed_requests.length || report.blocked_mutations.length || report.findings.length ? 'needs-review' : 'captured';
  await context.close();
} catch (error) { report.status = 'failed'; report.error = error.stack || String(error); process.exitCode = 1; }
finally {
  report.finished_at = new Date().toISOString(); await writeFile(path.join(output, 'review.json'), JSON.stringify(report, null, 2)); await browser.close();
  console.log(JSON.stringify({ status: report.status, screenshots: report.cases.length, findings: report.findings, report: path.join(output, 'review.json'), error: report.error }, null, 2));
}
