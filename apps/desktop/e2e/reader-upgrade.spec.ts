import { test, expect, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const fixturePath = path.resolve('../../artifacts/reader-upgrade/reader-coordinates.pdf');
test.beforeAll(async () => {
  await mkdir(path.dirname(fixturePath), { recursive: true });
  execFileSync(path.resolve('../../.venv/Scripts/python.exe'), ['-c', `
import io, sys
from reportlab.pdfgen.canvas import Canvas
from pypdf import PdfReader, PdfWriter
from pypdf.generic import FloatObject, NameObject, RectangleObject
stream=io.BytesIO()
c=Canvas(stream,pagesize=(400,500),invariant=1)
for i in range(4):
 c.setFillColorRGB(1,0,0); c.setFont('Helvetica',18)
 c.drawString(80,350,'Glyph alignment')
 c.setFillColorRGB(0,0,0); c.setFont('Helvetica',12)
 c.drawString(80,300,'Research evidence spans multiple lines.')
 c.drawString(80,270,'Search phrase repeated.')
 c.drawString(80,230,'Selection continues here.')
 c.drawString(80,130,'End of page '+str(i+1)+'.')
 c.showPage()
c.save(); stream.seek(0); writer=PdfWriter()
for i,page in enumerate(PdfReader(stream).pages):
 page.mediabox=RectangleObject([20,30,400,500]); page.cropbox=RectangleObject([50,70,350,450])
 page[NameObject('/UserUnit')]=FloatObject(2); page.rotate(i*90); writer.add_page(page)
writer.write(sys.argv[1])
`, fixturePath], { windowsHide: true });
});

async function mount(page: Page, options: unknown = {}) {
  await page.route('**/papers/reader-fixture/pdf', route => route.fulfill({ contentType: 'application/pdf', path: fixturePath }));
  await page.goto('/');
  await page.evaluate(async options => {
    const { mountReader } = await import('/e2e/reader-harness.tsx'); mountReader(options);
  }, options);
  await expect(page.locator('#reader-test-root [data-page="1"]')).toHaveAttribute('data-text-ready', 'true');
}
async function snapshot(page: Page) { return page.evaluate(() => (window as any).readerHarness.snapshot()); }
async function zoom(page: Page, value: number) {
  await page.getByRole('button', { name: '设置缩放比例', exact: true }).click();
  await page.getByRole('spinbutton', { name: '自定义缩放百分比' }).fill(String(value));
  await page.getByRole('button', { name: '应用', exact: true }).click();
  await expect(page.locator('#reader-test-root .zoom-label')).toHaveText(`${value}%`);
}
async function selectText(page: Page, first: number, last: number, backward = false) {
  await page.evaluate(({ first, last, backward }) => {
    const start = document.querySelector(`#reader-test-root [data-page="${first}"] .textLayer span`)!.firstChild!;
    const spans = document.querySelectorAll(`#reader-test-root [data-page="${last}"] .textLayer span`);
    const end = spans[spans.length - 1].firstChild!;
    const selection = window.getSelection()!; selection.removeAllRanges();
    if (backward) selection.setBaseAndExtent(end, end.textContent!.length, start, 2);
    else selection.setBaseAndExtent(start, 2, end, end.textContent!.length);
  }, { first, last, backward });
  await expect(page.getByRole('toolbar', { name: '文本选区操作' })).toBeVisible();
}

for (const dpr of [1, 2]) test(`actual glyphs, rotated CropBox/UserUnit text selection and search at DPR ${dpr}`, async ({ browser }, info) => {
  test.setTimeout(180000);
  const context = await browser.newContext({ viewport: { width: 1100, height: 900 }, deviceScaleFactor: dpr });
  const page = await context.newPage(), errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await mount(page);
  const measurements: unknown[] = [];
  for (let index = 0; index < 4; index++) {
    await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).fill(String(index + 1));
    await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).press('Enter');
    for (const scale of [50, 100, 200]) {
      await zoom(page, scale);
      const element = page.locator(`#reader-test-root [data-page="${index + 1}"]`);
      await element.scrollIntoViewIfNeeded();
      await expect(element).toHaveAttribute('data-text-ready', 'true');
      await expect.poll(async () => element.locator('canvas').evaluate((canvas: HTMLCanvasElement) => canvas.width > 0)).toBeTruthy();
      const measurement = await element.evaluate((element, dpr) => {
        const canvas = element.querySelector('canvas')!, context = canvas.getContext('2d')!;
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
        let x0 = canvas.width, y0 = canvas.height, x1 = -1, y1 = -1;
        for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
          const i = (y * canvas.width + x) * 4;
          if (pixels[i] > 170 && pixels[i + 1] < 120 && pixels[i + 2] < 120 && pixels[i + 3] > 200) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
        }
        const span = [...element.querySelectorAll('.textLayer span')].find(span => span.textContent === 'Glyph alignment')!;
        const range = document.createRange(); range.selectNodeContents(span);
        const text = range.getBoundingClientRect(), bounds = element.getBoundingClientRect();
        return { ink: [x0 / dpr, y0 / dpr, (x1 + 1) / dpr, (y1 + 1) / dpr], text: [text.left - bounds.left, text.top - bounds.top, text.right - bounds.left, text.bottom - bounds.top], font: getComputedStyle(span).fontSize, found: x1 >= x0 };
      }, dpr);
      expect(measurement.found).toBeTruthy();
      expect(measurement.font).toBe(`${36 * scale / 100}px`);
      const [x0, y0, x1, y1] = measurement.ink, [tx0, ty0, tx1, ty1] = measurement.text;
      expect(x0).toBeGreaterThanOrEqual(tx0 - 2); expect(y0).toBeGreaterThanOrEqual(ty0 - 2);
      expect(x1).toBeLessThanOrEqual(tx1 + 2); expect(y1).toBeLessThanOrEqual(ty1 + 2);
      expect(Math.max(Math.abs(tx0 - x0), Math.abs(ty0 - y0), Math.abs(tx1 - x1), Math.abs(ty1 - y1)), JSON.stringify({ index, scale, dpr, ...measurement })).toBeLessThan(12 * scale / 100);
      measurements.push({ page: index + 1, scale, dpr, ...measurement });
    }
  }
  await zoom(page, 100);
  await page.getByRole('button', { name: '查找 PDF 文字', exact: true }).click();
  await page.getByRole('textbox', { name: '查找 PDF 中的文字' }).fill('Search phrase');
  await expect(page.locator('#reader-test-root .reader-find [role=status]')).toHaveText('1 / 4');
  for (let index = 1; index <= 4; index++) {
    const hit = page.locator(`#reader-test-root [data-page="${index}"] .reader-search-hit.is-active`).first();
    await expect(hit).toBeVisible(); await expect(hit).toBeInViewport();
    if (index < 4) await page.getByRole('button', { name: '下一个匹配' }).click();
  }
  await page.getByRole('textbox', { name: '查找 PDF 中的文字' }).fill('missing phrase');
  await page.getByRole('textbox', { name: '查找 PDF 中的文字' }).fill('Glyph alignment');
  await expect(page.locator('#reader-test-root .reader-find [role=status]')).toHaveText('1 / 4');
  await page.getByRole('button', { name: '关闭 PDF 查找' }).click();
  await zoom(page, 50);
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).fill('1');
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).press('Enter');
  await selectText(page, 1, 2, dpr === 2);
  await page.getByRole('button', { name: '高亮', exact: true }).click();
  const state = await snapshot(page), selection = state.selections[0];
  expect(selection.kind).toBe('highlight'); expect(new Set(selection.locations.map((value: any) => value.page_index)).size).toBe(2);
  expect(selection.quote).toContain('Research evidence'); expect(selection.quote).not.toMatch(/\n1\n/);
  for (const location of selection.locations) {
    const [x0, y0, x1, y1] = location.bbox;
    expect(x0).toBeGreaterThanOrEqual(50); expect(y0).toBeGreaterThanOrEqual(70); expect(x1).toBeLessThanOrEqual(350); expect(y1).toBeLessThanOrEqual(450);
  }
  expect(selection.locations.length).toBeGreaterThanOrEqual(10);
  await expect(page.locator('#reader-test-root .reader-annotation-rect')).toHaveCount(selection.locations.length);
  await zoom(page, 100);
  await page.getByRole('button', { name: '旋转 PDF' }).click();
  await expect(page.locator('#reader-test-root .reader-annotation-rect')).toHaveCount(selection.locations.length);
  for (const index of [1, 2]) {
    const element = page.locator(`#reader-test-root [data-page="${index}"]`);
    await expect(element).toHaveAttribute('data-text-ready', 'true');
    const errors = await element.evaluate((element, firstPage) => {
      const spans = [...element.querySelectorAll('.textLayer span')];
      const boxes = [...element.querySelectorAll('.reader-annotation-rect')].map(node => node.getBoundingClientRect());
      return spans.map((span, index) => {
        const range = document.createRange(); range.selectNodeContents(span);
        if (firstPage && index === 0) range.setStart(span.firstChild!, 2);
        const rect = range.getBoundingClientRect(), box = boxes[index];
        return Math.max(Math.abs(rect.left - box.left), Math.abs(rect.top - box.top), Math.abs(rect.right - box.right), Math.abs(rect.bottom - box.bottom));
      });
    }, index === 1);
    expect(Math.max(...errors)).toBeLessThan(2);
  }
  await page.screenshot({ path: info.outputPath(`reader-selection-dpr${dpr}.png`) });
  await page.screenshot({ path: path.resolve(`../../artifacts/reader-upgrade/reader-selection-dpr${dpr}.png`) });
  await writeFile(path.resolve(`../../artifacts/reader-upgrade/glyph-measurements-dpr${dpr}.json`), JSON.stringify(measurements, null, 2));
  await info.attach(`glyph-measurements-dpr${dpr}`, { body: JSON.stringify(measurements, null, 2), contentType: 'application/json' });
  expect(errors).toEqual([]); await context.close();
});

test('reading anchors, one-shot explicit navigation, fitting, region notes and bookmark toggles', async ({ page }) => {
  await mount(page, { initialState: { page_index: 2, anchor: [120, 300], scale: 1.2, rotation: 90, fit_mode: 'custom' } });
  await expect.poll(async () => (await snapshot(page)).latest?.page_index).toBe(2);
  await expect(page.locator('#reader-test-root .zoom-label')).toHaveText('120%');
  await page.evaluate(() => (window as any).readerHarness.location({ page_index: 1, bbox: [80, 270, 160, 290] }));
  await expect(page.locator('#reader-test-root [data-page="2"] .pdf-highlight')).toBeInViewport();
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).fill('4');
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).press('Enter');
  await expect.poll(async () => (await snapshot(page)).latest?.page_index).toBe(3);
  await page.getByRole('button', { name: '添加本页书签' }).click();
  await expect(page.getByRole('button', { name: '移除本页书签' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '移除本页书签' }).click();
  await expect(page.getByRole('button', { name: '添加本页书签' })).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('combobox', { name: '页面适应方式' }).selectOption('width');
  const before = await snapshot(page);
  await page.setViewportSize({ width: 1000, height: 800 });
  await expect.poll(async () => (await snapshot(page)).latest?.scale).not.toBe(before.latest.scale);
  await page.getByRole('combobox', { name: '页面适应方式' }).selectOption('page');
  const pageElement = page.locator('#reader-test-root [data-page="4"]'); await pageElement.scrollIntoViewIfNeeded();
  await page.getByRole('button', { name: '框选区域笔记' }).click();
  const bounds = await pageElement.boundingBox();
  await page.mouse.move(bounds!.x + 50, bounds!.y + 50); await page.mouse.down(); await page.mouse.move(bounds!.x + 150, bounds!.y + 120); await page.mouse.up();
  await expect.poll(async () => (await snapshot(page)).selections.filter((item: any) => item.kind === 'note').length).toBe(1);
  expect((await snapshot(page)).crops).toHaveLength(0);
  await page.getByRole('button', { name: '框选区域笔记' }).click();
  await page.getByRole('button', { name: '框选图片区域', exact: true }).click();
  await expect(page.getByRole('button', { name: '框选区域笔记' })).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('button', { name: '取消框选' }).click();
  await page.getByRole('button', { name: '框选区域笔记' }).click();
  const cancelBounds = await pageElement.boundingBox();
  await page.mouse.move(cancelBounds!.x + 50, cancelBounds!.y + 50); await page.mouse.down();
  await page.mouse.move(cancelBounds!.x + 140, cancelBounds!.y + 100); await page.keyboard.press('Escape'); await page.mouse.up();
  expect((await snapshot(page)).crops).toHaveLength(0);
  expect((await snapshot(page)).selections.filter((item: any) => item.kind === 'note')).toHaveLength(1);
  // A later parent save must not leak read-only API metadata through onViewState.
  const latest = (await snapshot(page)).latest;
  expect(Object.keys(latest).sort()).toEqual(['anchor', 'fit_mode', 'page_index', 'rotation', 'scale']);
});

test('keyboard respects inputs, dialogs and IME; restores the full supported zoom range', async ({ page }) => {
  await mount(page, { initialState: { page_index: 0, anchor: null, scale: .05, rotation: 0, fit_mode: 'custom', version: 17, updated_at: 'server-only' } });
  await expect(page.locator('#reader-test-root .zoom-label')).toHaveText('5%');
  await zoom(page, 800); await expect(page.locator('#reader-test-root .zoom-label')).toHaveText('800%');
  await zoom(page, 100);
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).focus();
  await page.keyboard.press('Control+f');
  await expect(page.getByRole('search', { name: 'PDF 文字查找' })).toHaveCount(0);
  await page.evaluate(() => { (document.activeElement as HTMLElement).blur(); document.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true, isComposing: true, bubbles: true })); });
  await expect(page.getByRole('search', { name: 'PDF 文字查找' })).toHaveCount(0);
  await page.keyboard.press('Control+f');
  await expect(page.getByRole('textbox', { name: '查找 PDF 中的文字' })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(page.getByRole('search', { name: 'PDF 文字查找' })).toHaveCount(0);
  await page.evaluate(() => { const dialog = document.createElement('div'); dialog.setAttribute('role', 'dialog'); dialog.setAttribute('data-state', 'open'); dialog.id = 'reader-modal-check'; document.body.append(dialog); });
  await page.keyboard.press('Control+f'); await expect(page.getByRole('search', { name: 'PDF 文字查找' })).toHaveCount(0);
  expect(Object.keys((await snapshot(page)).latest).sort()).toEqual(['anchor', 'fit_mode', 'page_index', 'rotation', 'scale']);
});

test('real library persists cross-page highlights, region notes and reading view across reload', async ({ page, request }, info) => {
  const api = 'http://127.0.0.1:8765/api/v1', headers = { Authorization: 'Bearer dev-token' };
  const imported = await request.post(`${api}/papers/import-paths`, { headers, data: { paths: [fixturePath], recursive: false } });
  expect(imported.ok(), await imported.text()).toBeTruthy();
  const result = await imported.json(), paper = result.items[0] || result.duplicates[0];
  const jobs = await (await request.get(`${api}/jobs`, { headers })).json();
  for (const job of jobs.items.filter((job: any) => job.paper_id === paper.id && ['queued', 'running'].includes(job.status))) await request.post(`${api}/jobs/${job.id}/cancel`, { headers });
  const title = `Reader persistence ${Date.now()}`;
  await request.patch(`${api}/papers/${paper.id}`, { headers, data: { title } });
  const previousView = await (await request.get(`${api}/papers/${paper.id}/reading-state`, { headers })).json();
  const resetView = await request.patch(`${api}/papers/${paper.id}/reading-state`, { headers, data: {
    expected_version: previousView.version, page_index: 0, anchor: null, scale: 1, rotation: 0, fit_mode: 'custom',
  } });
  expect(resetView.ok(), await resetView.text()).toBeTruthy();
  const errors: string[] = [], apiErrors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => { if (response.url().includes('/api/v1/') && response.status() >= 400) apiErrors.push(`${response.status()} ${response.url()}`); });
  await page.goto('/');
  await page.getByRole('button', { name: /^论文库/ }).click();
  await page.getByRole('textbox', { name: '搜索论文', exact: true }).fill(title);
  await page.getByRole('button', { name: new RegExp(`^${title}`) }).click();
  const reader = page.getByRole('region', { name: 'PDF 阅读器' });
  await expect(reader.locator('[data-page="1"]')).toHaveAttribute('data-text-ready', 'true');
  await page.getByRole('button', { name: '设置缩放比例', exact: true }).click();
  await page.getByRole('spinbutton', { name: '自定义缩放百分比' }).fill('50');
  await page.getByRole('button', { name: '应用', exact: true }).click();
  await expect(reader.locator('[data-page="2"]')).toHaveAttribute('data-text-ready', 'true');
  await page.evaluate(() => {
    const first = document.querySelector('[data-page="1"] .textLayer span')!.firstChild!;
    const second = document.querySelectorAll('[data-page="2"] .textLayer span');
    const last = second[second.length - 1].firstChild!;
    window.getSelection()!.setBaseAndExtent(first, 2, last, last.textContent!.length);
  });
  await expect(page.getByRole('toolbar', { name: '文本选区操作' })).toBeVisible();
  const highlightResponse = page.waitForResponse(response => response.url().endsWith(`/papers/${paper.id}/annotations`) && response.request().method() === 'POST');
  await page.getByRole('button', { name: '高亮', exact: true }).click();
  const highlightResult = await highlightResponse; expect(highlightResult.ok(), await highlightResult.text()).toBeTruthy();
  const highlight = await highlightResult.json();
  expect(new Set(highlight.locations.map((value: any) => value.page_index)).size).toBe(2);
  await expect(reader.locator(`[data-annotation-id="${highlight.id}"]`)).toHaveCount(2);
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).fill('2');
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).press('Enter');
  await page.getByRole('button', { name: '框选区域笔记' }).click();
  const bounds = await reader.locator('[data-page="2"]').boundingBox();
  await page.mouse.move(bounds!.x + 70, bounds!.y + 50); await page.mouse.down(); await page.mouse.move(bounds!.x + 170, bounds!.y + 120); await page.mouse.up();
  const dialog = page.getByRole('dialog', { name: '区域笔记' }); await expect(dialog).toBeVisible();
  await dialog.getByLabel('笔记标题').fill('Geometry region note');
  await dialog.getByLabel('笔记内容').fill('Saved through the real local API, with unrotated PDF coordinates.');
  await dialog.getByRole('button', { name: '绿色', exact: true }).click();
  const noteResponse = page.waitForResponse(response => response.url().endsWith(`/papers/${paper.id}/annotations`) && response.request().method() === 'POST');
  await dialog.getByRole('button', { name: '保存笔记' }).click();
  const noteResult = await noteResponse; expect(noteResult.ok(), await noteResult.text()).toBeTruthy();
  const note = await noteResult.json(); await expect(dialog).not.toBeVisible();
  expect(note.color).toBe('green'); expect(note.locations[0].page_index).toBe(1);
  await page.getByRole('button', { name: '设置缩放比例', exact: true }).click();
  await page.getByRole('spinbutton', { name: '自定义缩放百分比' }).fill('125');
  await page.getByRole('button', { name: '应用', exact: true }).click();
  await page.getByRole('button', { name: '旋转 PDF' }).click();
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).fill('3');
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).press('Enter');
  await expect.poll(async () => {
    const state = await (await request.get(`${api}/papers/${paper.id}/reading-state`, { headers })).json();
    return { page: state.page_index, scale: state.scale, rotation: state.rotation };
  }).toEqual({ page: 2, scale: 1.25, rotation: 90 });
  const savedState = await (await request.get(`${api}/papers/${paper.id}/reading-state`, { headers })).json();
  await page.reload();
  await expect(page.locator('.pdf-reader .zoom-label')).toHaveText('125%');
  await expect(page.getByRole('textbox', { name: 'PDF 页码', exact: true })).toHaveValue('3');
  await expect(reader.locator(`[data-annotation-id="${highlight.id}"]`)).toHaveCount(2);
  await expect(reader.locator(`[data-annotation-id="${note.id}"]`)).toHaveCount(1);
  const storedNote = await (await request.get(`${api}/annotations/${note.id}`, { headers })).json();
  expect(storedNote.locations).toEqual(note.locations);
  await expect.poll(async () => {
    const state = await (await request.get(`${api}/papers/${paper.id}/reading-state`, { headers })).json();
    return Math.max(...state.anchor.map((value: number, index: number) => Math.abs(value - savedState.anchor[index])));
  }).toBeLessThan(1);
  await page.screenshot({ path: info.outputPath('real-library-reading-restored.png') });
  await page.screenshot({ path: path.resolve('../../artifacts/reader-upgrade/real-library-reading-restored.png') });
  expect(errors).toEqual([]); expect(apiErrors).toEqual([]);
});
