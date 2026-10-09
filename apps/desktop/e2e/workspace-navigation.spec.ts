import { expect, test, type APIRequestContext, type Page, type Route } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const api = 'http://127.0.0.1:8765/api/v1';
const headers = { Authorization: 'Bearer dev-token' };
const runId = `${Date.now()}${Math.floor(Math.random() * 10000)}`;
const prefix = `WorkspaceNav${runId}`;
let a: { id: string; title: string }, b: { id: string; title: string };
let resources: Array<{ id: string; name: string; caption: string }> = [];
const results: Array<{ title: string; status: string | undefined; duration_ms: number }> = [];

async function json(request: APIRequestContext, route: string, method = 'GET', data?: unknown) {
  const response = await request.fetch(api + route, { method, headers, data });
  expect(response.ok(), `${method} ${route}: ${await response.text()}`).toBeTruthy();
  return response.json();
}
async function home(page: Page) {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '论文库', exact: true })).toBeVisible();
}
async function openFromLibrary(page: Page, paper: { id: string; title: string }) {
  await page.locator('aside.sidebar').getByRole('button', { name: '论文库', exact: true }).click();
  await page.getByLabel('搜索论文', { exact: true }).fill(prefix);
  await page.locator(`.paper-primary[data-workspace-focus="paper:${paper.id}"]`).click();
  await expect(page.getByRole('textbox', { name: '标题', exact: true })).toHaveValue(paper.title);
}
const tab = (page: Page, paper: { title: string }) => page.locator('.workspace-tabs').getByRole('tab', { name: paper.title, exact: true, includeHidden: true });
const guard = (page: Page) => page.getByRole('dialog', { name: '有未保存的修改' });
async function chooseGuard(page: Page, label: '继续编辑' | '放弃修改' | '保存并继续') {
  await expect(guard(page)).toBeVisible();
  await guard(page).getByRole('button', { name: label, exact: true }).click();
}
async function selectGalleryPaper(page: Page) {
  await page.locator('aside.sidebar').getByRole('button', { name: '图片库', exact: true }).click();
  await page.getByRole('combobox', { name: '按论文筛选', exact: true }).fill(a.title);
  await page.getByRole('option').filter({ hasText: a.title }).click();
  await expect(page.locator('.resource-card')).toHaveCount(24);
}
async function rejectOneSave(page: Page, endpoint: string) {
  let rejected = false;
  const handler = async (route: Route) => {
    if (!rejected && route.request().method() === 'PATCH') {
      rejected = true;
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: '故障注入：保存暂不可用' }) });
    } else await route.continue();
  };
  await page.route(api + endpoint, handler);
  return async () => { expect(rejected).toBe(true); await page.unroute(api + endpoint, handler); };
}

test.describe('real workspace navigation and edit protection', () => {
  test.describe.configure({ mode: 'serial' });
  test.afterEach(async ({}, info) => { results.push({ title: info.title, status: info.status, duration_ms: info.duration }); });
  test.afterAll(async () => {
    await mkdir(path.resolve('../../artifacts'), { recursive: true });
    await writeFile(path.resolve('../../artifacts/workspace-navigation-ui.json'), JSON.stringify({
      passed: results.length === 5 && results.every(result => result.status === 'passed'),
      measured_at: new Date().toISOString(), runId, tests: results,
      fixture: { paper_a: a?.id, paper_b: b?.id, manual_figure_count: resources.length },
      scope: 'Real API and UI. GET B delay and one 503 per editor are explicit transport fault injection; no fabricated successful responses. No library switch or edits to pre-existing records.',
    }, null, 2));
  });
  test.beforeAll(async ({ request }) => {
    test.setTimeout(180000);
    expect((await request.get('http://127.0.0.1:1420/src/ui.tsx')).ok(), 'Vite must compile the shared form primitives before creating test records').toBe(true);
    const folder = path.resolve(`../../.test-data/workspace-navigation/${runId}`);
    await mkdir(folder, { recursive: true });
    const source = await readFile(path.resolve('../../tests/fixtures/academic.pdf'));
    const paths = ['a', 'b'].map(name => path.join(folder, `workspace-${name}.pdf`));
    for (let index = 0; index < paths.length; index++) {
      // Each owned PDF has a distinct hash; the original academic fixture is unchanged.
      await writeFile(paths[index], Buffer.concat([source, Buffer.from(`\n% Workspace test ${runId}-${index}\n`)]));
    }
    const imported = await json(request, '/papers/import-paths', 'POST', { paths, recursive: false });
    expect(imported.errors).toEqual([]);
    expect(imported.items).toHaveLength(2);
    const ownIds = new Set(imported.items.map((paper: { id: string }) => paper.id));
    for (const job of (await json(request, '/jobs')).items) {
      if (ownIds.has(job.paper_id) && ['queued', 'running', 'waiting_models'].includes(job.status)) await json(request, `/jobs/${job.id}/cancel`, 'POST');
    }
    await expect.poll(async () => (await json(request, '/jobs')).items.filter((job: { paper_id: string; status: string }) =>
      ownIds.has(job.paper_id) && ['queued', 'running', 'cancel_requested', 'publishing'].includes(job.status)).length, { timeout: 30000 }).toBe(0);
    [a, b] = await Promise.all(imported.items.map((paper: { id: string }, index: number) => json(request, `/papers/${paper.id}`, 'PATCH', {
      title: `${prefix} ${index ? 'B' : 'A'}`, authors: ['Workspace regression'], year: index ? 2024 : 2023, notes: '',
      sections: [{ title: 'Original section', level: 1, page_index: 0, location: { page_index: 0, bbox: [50, 600, 300, 625] } }],
      references: ['Original reference'],
    })));
    for (let index = 0; index < 49; index++) resources.push(await json(request, `/papers/${a.id}/resources`, 'POST', {
      kind: 'figure', name: `${prefix} Figure ${String(index + 1).padStart(2, '0')}`, caption: `${prefix} manual crop ${index + 1}`,
      dpi: 150, location: { page_index: 0, bbox: [80, 350, 500, 435] },
    }));
    await mkdir(path.resolve('../../artifacts'), { recursive: true });
    await writeFile(path.resolve('../../artifacts/workspace-navigation-fixture.json'), JSON.stringify({ runId, a: a.id, b: b.id, resources: resources.map(resource => resource.id), scope: 'Only newly imported, uniquely hashed test papers; current shared library is never switched.' }, null, 2));
  });

  test('deduplicated reader tabs, keyboard history, cached search and list controls', async ({ page }, info) => {
    await home(page);
    await openFromLibrary(page, a);
    await openFromLibrary(page, b);
    await expect(page.locator('.workspace-tab')).toHaveCount(2);
    await page.keyboard.press('Control+Tab');
    await expect(tab(page, a)).toHaveAttribute('aria-selected', 'true');
    await page.keyboard.press('Alt+ArrowLeft');
    await expect(tab(page, b)).toHaveAttribute('aria-selected', 'true');
    await page.keyboard.press('Alt+ArrowRight');
    await expect(tab(page, a)).toHaveAttribute('aria-selected', 'true');
    await openFromLibrary(page, a);
    await expect(page.locator('.workspace-tab')).toHaveCount(2);

    await page.keyboard.press('Control+k');
    await page.getByLabel('全局全文搜索', { exact: true }).fill(prefix);
    await page.locator('.search-tabs').getByRole('button', { name: /^论文 2$/ }).click();
    await expect(page.locator('.search-result')).toHaveCount(2);
    await page.locator(`[data-workspace-focus="search:papers:${a.id}"]`).click();
    await expect(tab(page, a)).toHaveAttribute('aria-selected', 'true');
    await page.getByRole('tab', { name: '返回工作区', exact: true }).click();
    await expect(page.getByLabel('全局全文搜索', { exact: true })).toHaveValue(prefix);
    await expect(page.locator('.search-tabs button.active')).toHaveText('论文 2');
    await expect(page.locator('.search-result')).toHaveCount(2);
    await expect(page.locator(`[data-workspace-focus="search:papers:${a.id}"]`)).toBeFocused();

    await page.locator('aside.sidebar').getByRole('button', { name: '论文库', exact: true }).click();
    await page.getByLabel('搜索论文', { exact: true }).fill(prefix);
    await page.getByLabel('论文排序', { exact: true }).selectOption('year');
    await page.getByRole('button', { name: '卡片视图', exact: true }).click();
    await page.locator(`.paper-primary[data-workspace-focus="paper:${a.id}"]`).click();
    await page.getByRole('tab', { name: '返回工作区', exact: true }).click();
    await expect(page.getByLabel('搜索论文', { exact: true })).toHaveValue(prefix);
    await expect(page.getByLabel('论文排序', { exact: true })).toHaveValue('year');
    await expect(page.locator('.papers-grid')).toBeVisible();
    await expect(page.locator(`.paper-primary[data-workspace-focus="paper:${a.id}"]`)).toBeFocused();
    await page.screenshot({ path: info.outputPath('workspace-returned-library.png') });
  });

  test('gallery restores paper/query/year filters, page two, scroll and focused resource after reading', async ({ page }, info) => {
    await home(page);
    await selectGalleryPaper(page);
    const filtered = page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname.endsWith('/resources') && url.searchParams.get('q') === prefix && url.searchParams.get('year') === '2023' && response.status() === 200;
    });
    await page.getByLabel('搜索图片', { exact: true }).fill(prefix);
    await page.getByRole('spinbutton', { name: '发表年份', exact: true }).fill('2023');
    await filtered;
    await expect(page.locator('.collection-subline')).toContainText('49');
    const secondPage = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/resources') && new URL(response.url()).searchParams.get('offset') === '24' && response.status() === 200);
    await page.getByRole('button', { name: '下一页', exact: true }).click();
    await secondPage;
    await expect(page.locator('.pager')).toContainText('第 2 / 3 页');
    await expect(page.locator('.resource-card')).toHaveCount(24);
    const target = page.locator('.resource-card-image').nth(16);
    await target.focus();
    await target.scrollIntoViewIfNeeded();
    const focus = await target.getAttribute('data-workspace-focus');
    await target.click();
    const top = await page.locator('.page-content').evaluate(element => element.scrollTop);
    expect(top).toBeGreaterThan(100);
    await page.getByRole('dialog').getByRole('button', { name: '查看原文', exact: true }).click();
    await expect(page.locator('.pdf-highlight').first()).toBeVisible();
    await page.getByRole('tab', { name: '返回工作区', exact: true }).click();
    await expect(page.getByRole('combobox', { name: '按论文筛选', exact: true })).toHaveValue(a.title);
    await expect(page.getByLabel('搜索图片', { exact: true })).toHaveValue(prefix);
    await expect(page.getByRole('spinbutton', { name: '发表年份', exact: true })).toHaveValue('2023');
    await expect(page.locator('.pager')).toContainText('第 2 / 3 页');
    await expect(page.locator(`[data-workspace-focus="${focus}"]`)).toBeFocused();
    await expect.poll(async () => Math.abs(await page.locator('.page-content').evaluate(element => element.scrollTop) - top)).toBeLessThan(4);
    await page.screenshot({ path: info.outputPath('gallery-restored-page-scroll.png') });
  });

  test('a delayed paper B response never exposes an editable paper A snapshot', async ({ page }) => {
    await home(page);
    await openFromLibrary(page, b);
    await openFromLibrary(page, a);
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    let intercepted = false;
    await page.route(`${api}/papers/${b.id}`, async route => {
      if (route.request().method() !== 'GET') return route.continue();
      const response = await route.fetch(); intercepted = true;
      await gate; await route.fulfill({ response });
    });
    try {
      await tab(page, b).click();
      await expect.poll(() => intercepted).toBe(true);
      await expect(page.getByRole('textbox', { name: '标题', exact: true })).toHaveCount(0);
      await expect(page.locator('.detail-topbar')).not.toContainText(a.title);
    } finally { release(); }
    await expect(page.getByRole('textbox', { name: '标题', exact: true })).toHaveValue(b.title);
  });

  test('metadata and outline guards support cancel/discard/save, and failed saves do not navigate', async ({ page, request }, info) => {
    await home(page);
    await openFromLibrary(page, b);
    await openFromLibrary(page, a);
    const notes = page.getByRole('textbox', { name: '个人备注', exact: true });
    await notes.fill('Unfinished metadata draft');
    await tab(page, b).click();
    await chooseGuard(page, '继续编辑');
    await expect(notes).toHaveValue('Unfinished metadata draft');
    await expect(tab(page, a)).toHaveAttribute('aria-selected', 'true');
    await tab(page, b).click(); await chooseGuard(page, '放弃修改');
    await expect(tab(page, b)).toHaveAttribute('aria-selected', 'true');
    expect((await json(request, `/papers/${a.id}`)).notes).toBe('');
    await tab(page, a).click(); await notes.fill('Saved metadata draft');
    const restoreMetadata = await rejectOneSave(page, `/papers/${a.id}`);
    await tab(page, b).click(); await chooseGuard(page, '保存并继续');
    await expect(guard(page).getByRole('alert')).toContainText('保存未完成');
    await expect(tab(page, a)).toHaveAttribute('aria-selected', 'true');
    expect((await json(request, `/papers/${a.id}`)).notes).toBe('');
    await restoreMetadata();
    await chooseGuard(page, '保存并继续');
    await expect(tab(page, b)).toHaveAttribute('aria-selected', 'true');
    expect((await json(request, `/papers/${a.id}`)).notes).toBe('Saved metadata draft');

    await tab(page, a).click();
    await page.getByRole('tab', { name: '目录', exact: true }).click();
    await page.getByRole('button', { name: '编辑目录与参考文献', exact: true }).click();
    await page.getByLabel('章节 1 标题', { exact: true }).fill('Unfinished section');
    await page.getByRole('tab', { name: '论文信息', exact: true }).click(); await chooseGuard(page, '继续编辑');
    await expect(page.getByLabel('章节 1 标题', { exact: true })).toHaveValue('Unfinished section');
    await page.getByRole('tab', { name: '论文信息', exact: true }).click(); await chooseGuard(page, '放弃修改');
    expect((await json(request, `/papers/${a.id}`)).sections[0].title).toBe('Original section');
    await page.getByRole('tab', { name: '目录', exact: true }).click();
    await page.getByRole('button', { name: '编辑目录与参考文献', exact: true }).click();
    await page.getByLabel('章节 1 标题', { exact: true }).fill('Saved section');
    const restoreOutline = await rejectOneSave(page, `/papers/${a.id}`);
    await page.getByRole('tab', { name: '论文信息', exact: true }).click(); await chooseGuard(page, '保存并继续');
    await expect(guard(page).getByRole('alert')).toContainText('保存未完成');
    await expect(page.getByRole('tab', { name: '目录', exact: true, includeHidden: true })).toHaveAttribute('aria-selected', 'true');
    await restoreOutline(); await chooseGuard(page, '保存并继续');
    await expect(page.getByRole('tab', { name: '论文信息', exact: true })).toHaveAttribute('aria-selected', 'true');
    expect((await json(request, `/papers/${a.id}`)).sections[0].title).toBe('Saved section');
    await page.screenshot({ path: info.outputPath('guarded-metadata-and-outline.png') });
  });

  test('resource close guard retains drafts on cancel/failure and only persists after successful save', async ({ page, request }, info) => {
    await home(page); await selectGalleryPaper(page);
    await page.locator('.resource-card-image').first().click();
    const resourceDialog = page.getByRole('dialog').filter({ has: page.getByLabel('Caption', { exact: true }) });
    const initialName = await resourceDialog.getByLabel('资源名称', { exact: true }).inputValue();
    const resource = resources.find(item => item.name === initialName)!;
    expect(resource).toBeTruthy();
    const caption = resourceDialog.getByLabel('Caption', { exact: true });
    await caption.fill('Unfinished caption');
    await resourceDialog.getByRole('button', { name: '关闭对话框', exact: true }).click(); await chooseGuard(page, '继续编辑');
    await expect(caption).toHaveValue('Unfinished caption');
    await resourceDialog.getByRole('button', { name: '关闭对话框', exact: true }).click(); await chooseGuard(page, '放弃修改');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect((await json(request, `/resources/${resource.id}`)).caption).toBe(resource.caption);
    await page.locator('.resource-card-image').first().click();
    await caption.fill('Saved resource caption');
    const restoreResource = await rejectOneSave(page, `/resources/${resource.id}`);
    await resourceDialog.getByRole('button', { name: '关闭对话框', exact: true }).click(); await chooseGuard(page, '保存并继续');
    await expect(guard(page).getByRole('alert')).toContainText('保存未完成');
    expect((await json(request, `/resources/${resource.id}`)).caption).toBe(resource.caption);
    await page.screenshot({ path: info.outputPath('resource-save-failure-retains-draft.png') });
    await restoreResource(); await chooseGuard(page, '保存并继续');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect((await json(request, `/resources/${resource.id}`)).caption).toBe('Saved resource caption');
  });
});
