import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const output = path.resolve('../../artifacts/reader-performance');
test('real 81-page PDF bounds bitmap allocation at 800% and retains selections after raster eviction', async ({ browser }, info) => {
  test.setTimeout(180000);
  await mkdir(output, { recursive: true });
  const fixture = path.join(output, 'long-and-wide.pdf');
  execFileSync(path.resolve('../../.venv/Scripts/python.exe'), ['-c', `
import sys
from reportlab.pdfgen.canvas import Canvas
c=Canvas(sys.argv[1],pagesize=(612,792),invariant=1)
for page in range(80):
 c.setFont('Helvetica',14)
 for line in range(10): c.drawString(50,730-line*58,f'Page {page+1:02d} line {line+1:02d}: Selection survives raster recycling.')
 c.showPage()
c.setPageSize((14000,144));c.setFont('Helvetica',24);c.drawString(30,90,'Very wide source page; bounded bitmap side.');c.showPage();c.save()
`, fixture], { windowsHide: true });
  const context = await browser.newContext({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2 });
  const page = await context.newPage(), errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/papers/reader-fixture/pdf', route => route.fulfill({ contentType: 'application/pdf', path: fixture }));
  await page.goto('/');
  await page.evaluate(async () => { const { mountReader } = await import('/e2e/reader-harness.tsx'); mountReader(); });
  const reader = page.locator('#reader-test-root');
  await expect(reader.locator('[data-page="1"]')).toHaveAttribute('data-text-ready', 'true');
  const cdp = await browser.newBrowserCDPSession();
  const samples: any[] = [];
  const sample = async (label: string) => {
    const raster = await reader.evaluate(root => {
      const pages = [...root.querySelectorAll<HTMLCanvasElement>('canvas')].filter(canvas => canvas.width && canvas.height).map(canvas => ({ page: Number(canvas.closest('[data-page]')?.getAttribute('data-page')), width: canvas.width, height: canvas.height, pixels: canvas.width * canvas.height, ratio: Number(canvas.dataset.rasterScale), reduced: canvas.dataset.rasterReduced === 'true' }));
      return { pages, totalPixels: pages.reduce((sum, page) => sum + page.pixels, 0), heap: (performance as any).memory?.usedJSHeapSize ?? null };
    });
    const processes = await cdp.send('SystemInfo.getProcessInfo');
    const ids = processes.processInfo.map(process => process.id).filter(id => Number.isSafeInteger(id) && id > 0);
    const memory = JSON.parse(execFileSync('powershell.exe', ['-NoProfile', '-Command', `@(Get-Process -Id ${ids.join(',')} -ErrorAction SilentlyContinue | Select-Object Id,WorkingSet64,PrivateMemorySize64,PeakWorkingSet64) | ConvertTo-Json -Compress`], { windowsHide: true, encoding: 'utf8' }));
    samples.push({ label, ...raster, estimatedBitmapBytes: raster.totalPixels * 4, processMemory: memory });
    return raster;
  };
  await sample('baseline-100-percent');
  await page.getByRole('button', { name: '设置缩放比例', exact: true }).click();
  await page.getByRole('spinbutton', { name: '自定义缩放百分比' }).fill('800');
  await page.getByRole('button', { name: '应用', exact: true }).click();
  await expect(reader.locator('.reader-quality')).toBeVisible();
  for (const index of [1, 2, 10, 30, 60, 80, 81]) {
    await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).fill(String(index));
    await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).press('Enter');
    await expect(reader.locator(`[data-page="${index}"]`)).toHaveAttribute('data-text-ready', 'true');
    await expect.poll(async () => reader.locator(`[data-page="${index}"] canvas`).evaluate((canvas: HTMLCanvasElement) => canvas.width > 0)).toBeTruthy();
    const raster = await sample(`800-percent-page-${index}`);
    for (const bitmap of raster.pages) { expect(bitmap.width).toBeLessThanOrEqual(8192); expect(bitmap.height).toBeLessThanOrEqual(8192); expect(bitmap.pixels).toBeLessThanOrEqual(16_777_216); }
    expect(raster.totalPixels).toBeLessThanOrEqual(3 * 16_777_216);
  }
  const lastCanvas = reader.locator('[data-page="81"] canvas');
  expect(await lastCanvas.evaluate((canvas: HTMLCanvasElement) => canvas.width)).toBe(8192);
  await page.getByTitle('恢复 100%', { exact: true }).click();
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).fill('1');
  await page.getByRole('textbox', { name: 'PDF 页码', exact: true }).press('Enter');
  await expect(reader.locator('[data-page="1"]')).toHaveAttribute('data-text-ready', 'true');
  await page.evaluate(() => {
    const text = document.querySelector('#reader-test-root [data-page="1"] .textLayer span')!.firstChild!;
    window.getSelection()!.setBaseAndExtent(text, 0, text, 4);
  });
  for (let index = 2; index <= 8; index++) {
    await reader.locator(`[data-page="${index}"]`).evaluate(node => node.scrollIntoView({ block: 'start' }));
    await expect(reader.locator(`[data-page="${index}"]`)).toHaveAttribute('data-text-ready', 'true');
    expect(await page.evaluate(() => window.getSelection()!.anchorNode?.isConnected)).toBeTruthy();
    expect(await page.evaluate(() => window.getSelection()!.toString())).toBe('Page');
  }
  await expect.poll(async () => reader.locator('[data-page="1"] canvas').evaluate((canvas: HTMLCanvasElement) => canvas.width)).toBe(0);
  await page.evaluate(() => {
    const start = window.getSelection()!.anchorNode!, spans = document.querySelectorAll('#reader-test-root [data-page="8"] .textLayer span');
    const end = spans[spans.length - 1].firstChild!; window.getSelection()!.setBaseAndExtent(start, 0, end, end.textContent!.length);
  });
  await expect(page.getByRole('toolbar', { name: '文本选区操作' })).toBeVisible();
  await page.getByRole('button', { name: '高亮', exact: true }).click();
  const selection = await page.evaluate(() => (window as any).readerHarness.snapshot().selections.at(-1));
  await expect(page.getByRole('textbox', { name: 'PDF 页码', exact: true })).toHaveValue('8');
  expect(new Set(selection.locations.map((location: any) => location.page_index)).size).toBe(8);
  for (let index = 1; index <= 8; index++) expect(selection.quote).toContain(`Page ${String(index).padStart(2, '0')} line 01`);
  await sample('selection-eight-pages-after-raster-eviction');
  await page.screenshot({ path: path.join(output, 'selection-eight-pages.png') });
  const report = { devicePixelRatio: 2, pageCount: 81, maximumAllowedBitmapPixels: 16_777_216, maximumAllowedBitmapSide: 8192,
    memoryScope: 'Entire Playwright browser process tree from CDP SystemInfo. Sampled working set, not a hard process memory bound. Canvas bytes estimate RGBA backing only.',
    peakSampledWorkingSetBytes: Math.max(...samples.map(sample => sample.processMemory.reduce((sum: number, process: any) => sum + process.WorkingSet64, 0))),
    peakSampledPrivateBytes: Math.max(...samples.map(sample => sample.processMemory.reduce((sum: number, process: any) => sum + process.PrivateMemorySize64, 0))),
    peakCanvasPixels: Math.max(...samples.map(sample => sample.totalPixels)), peakEstimatedBitmapBytes: Math.max(...samples.map(sample => sample.estimatedBitmapBytes)), samples, selectionPages: 8, selectionLocations: selection.locations.length, browserErrors: errors };
  await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  await info.attach('bitmap-memory-report', { body: JSON.stringify(report, null, 2), contentType: 'application/json' });
  expect(errors).toEqual([]); await context.close();
});
