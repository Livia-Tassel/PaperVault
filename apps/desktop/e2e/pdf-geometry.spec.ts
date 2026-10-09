import { test, expect } from '@playwright/test';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

test.use({ deviceScaleFactor: 2, viewport: { width: 1440, height: 1050 } });
const api = 'http://127.0.0.1:8765/api/v1';
const headers = { Authorization: 'Bearer dev-token' };
const box = [101, 131, 179, 189];
const redBox = [100, 130, 180, 190];

function viewportBox(source: number[], scale: number, rotation: number): number[] {
  const point = (x: number, y: number) => {
    const factor = 2 * scale; // Fixture /UserUnit, separate from deviceScaleFactor.
    if (rotation === 90) return [(y - 70) * factor, (x - 50) * factor];
    if (rotation === 180) return [(350 - x) * factor, (y - 70) * factor];
    if (rotation === 270) return [(450 - y) * factor, (350 - x) * factor];
    return [(x - 50) * factor, (450 - y) * factor];
  };
  const corners = [point(source[0], source[1]), point(source[2], source[1]), point(source[2], source[3]), point(source[0], source[3])];
  return [Math.min(...corners.map(p => p[0])), Math.min(...corners.map(p => p[1])), Math.max(...corners.map(p => p[0])), Math.max(...corners.map(p => p[1]))];
}

test('real PDF.js highlight and raster alignment at DPR 2, CropBox offsets, UserUnit 2 and four rotations', async ({ page, request, browser }, info) => {
  test.setTimeout(180000);
  const fixture = path.resolve('../../tests/fixtures/geometry.pdf');
  const imported = await request.post(`${api}/papers/import-paths`, { headers, data: { paths: [fixture], recursive: false } });
  expect(imported.ok()).toBeTruthy();
  const importedData = await imported.json();
  expect(importedData.errors).toHaveLength(0);
  const paper = importedData.items[0] || importedData.duplicates[0];
  const jobs = await (await request.get(`${api}/jobs`, { headers })).json();
  for (const job of jobs.items.filter((j: { paper_id: string; status: string }) => j.paper_id === paper.id && ['queued', 'running'].includes(j.status))) {
    await request.post(`${api}/jobs/${job.id}/cancel`, { headers });
  }
  const resources: Array<{ id: string; name: string }> = [];
  const existing = await (await request.get(`${api}/resources?paper_id=${paper.id}&limit=1000`, { headers })).json();
  for (let index = 0; index < 4; index++) {
    const name = `Geometry DPR2 page ${index + 1} rotation ${index * 90}`;
    const old = existing.items.find((r: { name: string }) => r.name === name);
    if (old) resources.push(old);
    else {
      const created = await request.post(`${api}/papers/${paper.id}/resources`, { headers, data: {
        kind: 'figure', name, caption: 'Geometry acceptance resource: actual red rectangle in generated PDF',
        location: { page_index: index, bbox: box }, dpi: 150,
      } });
      expect(created.ok(), await created.text()).toBeTruthy();
      resources.push(await created.json());
    }
  }
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: '论文库', exact: true }).click();
  await expect(page.getByRole('heading', { name: '论文库', exact: true })).toBeVisible();
  expect(await page.evaluate(() => devicePixelRatio)).toBe(2);
  const cases: unknown[] = [];
  for (let index = 0; index < 4; index++) {
    await page.getByRole('button', { name: /^图片库/ }).click();
    await page.getByRole('combobox', { name: '按论文筛选', exact: true }).fill('geometry.pdf');
    const choices = page.getByRole('listbox', { name: '论文匹配结果' }).getByRole('option');
    await expect(choices).toHaveCount(1);
    await choices.first().click();
    await page.getByRole('button', { name: resources[index].name, exact: true }).click();
    await page.getByRole('button', { name: '查看原文', exact: true }).click();
    const highlight = page.locator(`[data-page="${index + 1}"] .pdf-highlight`);
    await expect(highlight).toBeVisible();
    for (const [scale, extraRotation] of [[.55, 0], [1, 0], [2.05, 0], [1, 90]]) {
      // 0.2 restores persisted reader state. Reset through actual controls before
      // applying each independent expected transform instead of assuming a mount reset.
      const textLayer = page.locator(`[data-page="${index + 1}"] .textLayer`);
      await expect(textLayer).toHaveAttribute('data-main-rotation', /^(0|90|180|270)$/);
      for (let remaining = 4; Number(await textLayer.getAttribute('data-main-rotation')) !== index * 90 && remaining > 0; remaining--) {
        const previous = Number(await textLayer.getAttribute('data-main-rotation'));
        await page.getByRole('button', { name: '旋转 PDF', exact: true }).click();
        await expect(textLayer).toHaveAttribute('data-main-rotation', String((previous + 90) % 360));
      }
      await expect(textLayer).toHaveAttribute('data-main-rotation', String(index * 90));
      await page.getByTitle('恢复 100%', { exact: true }).click();
      if (scale < 1) for (let click = 0; click < 3; click++) await page.getByRole('button', { name: '缩小', exact: true }).click();
      if (scale > 1) for (let click = 0; click < 7; click++) await page.getByRole('button', { name: '放大', exact: true }).click();
      if (extraRotation) await page.getByRole('button', { name: '旋转 PDF', exact: true }).click();
      await expect(textLayer).toHaveAttribute('data-main-rotation', String((index * 90 + extraRotation) % 360));
      await expect(page.locator('.zoom-label')).toHaveText(`${Math.round(scale * 100)}%`);
      await highlight.scrollIntoViewIfNeeded();
      const rotation = (index * 90 + extraRotation) % 360;
      const expectedHighlight = viewportBox(box, scale, rotation);
      const expectedRed = viewportBox(redBox, scale, rotation);
      const expectedWidth = (rotation % 180 ? 380 : 300) * 2 * scale;
      const canvas = page.locator(`[data-page="${index + 1}"] canvas`);
      await expect.poll(async () => canvas.evaluate((element: HTMLCanvasElement, values) => {
        if (Math.abs(element.width - Math.ceil(values.width * 2)) > 1 || !element.height) return false;
        const [x0, y0, x1, y1] = values.red;
        const sample = element.getContext('2d')!.getImageData(Math.floor((x0 + x1) * .5 * 2), Math.floor((y0 + y1) * .5 * 2), 1, 1).data;
        return sample[0] > 200 && sample[1] < 100 && sample[2] < 100;
      }, { width: expectedWidth, red: expectedRed }), { timeout: 20000 }).toBeTruthy();
      const measured = await page.locator(`[data-page="${index + 1}"]`).evaluate((element, dpr) => {
        const canvas = element.querySelector('canvas')!;
        const context = canvas.getContext('2d')!;
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
        let x0 = canvas.width, y0 = canvas.height, x1 = -1, y1 = -1;
        for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
          const i = (y * canvas.width + x) * 4;
          if (pixels[i] > 200 && pixels[i + 1] < 100 && pixels[i + 2] < 100 && pixels[i + 3] > 200) {
            x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
          }
        }
        const pageBounds = element.getBoundingClientRect();
        const bounds = element.querySelector('.pdf-highlight')!.getBoundingClientRect();
        return { highlight: [bounds.left - pageBounds.left, bounds.top - pageBounds.top, bounds.right - pageBounds.left, bounds.bottom - pageBounds.top],
          red: [x0 / dpr, y0 / dpr, (x1 + 1) / dpr, (y1 + 1) / dpr],
          canvas_width_pixels: canvas.width, canvas_height_pixels: canvas.height, red_found: x1 >= x0 };
      }, 2);
      expect(measured.red_found).toBeTruthy();
      const highlightError = Math.max(...measured.highlight.map((value, i) => Math.abs(value - expectedHighlight[i])));
      const rasterError = Math.max(...measured.red.map((value, i) => Math.abs(value - expectedRed[i])));
      expect(highlightError).toBeLessThanOrEqual(2);
      expect(rasterError).toBeLessThanOrEqual(2);
      cases.push({ page: index + 1, native_rotation: index * 90, viewer_extra_rotation: extraRotation, scale, device_pixel_ratio: 2,
        expected_highlight: expectedHighlight, actual_highlight: measured.highlight, highlight_error_css_px: highlightError,
        expected_red_pixels_in_css: expectedRed, actual_red_pixels_in_css: measured.red, raster_error_css_px: rasterError,
        canvas_width_pixels: measured.canvas_width_pixels, canvas_height_pixels: measured.canvas_height_pixels });
      if (scale === 1 && extraRotation === 0) await page.screenshot({ path: info.outputPath(`rotation-${index * 90}-dpr2.png`) });
    }
  }
  const matrixChecks = await page.evaluate(async ({ api, paperId, bbox }) => {
    // A separate real PDF.js document validates exact requested scales without
    // mutating the application's 15%-step zoom control or its React state.
    const pdfjs = await import(/* @vite-ignore */ '/node_modules/pdfjs-dist/build/pdf.mjs');
    pdfjs.GlobalWorkerOptions.workerSrc = '/node_modules/pdfjs-dist/build/pdf.worker.mjs';
    const response = await fetch(`${api}/papers/${paperId}/pdf`, { headers: { Authorization: 'Bearer dev-token' } });
    const loading = pdfjs.getDocument({ data: new Uint8Array(await response.arrayBuffer()), enableXfa: false });
    const pdf = await loading.promise;
    const results = [];
    for (let pageIndex = 0; pageIndex < 4; pageIndex++) {
      const pdfPage = await pdf.getPage(pageIndex + 1);
      for (const scale of [.5, 1, 2]) {
        const viewport = pdfPage.getViewport({ scale });
        let error = 0;
        const points = [[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]]];
        const transformed = points.map(([x, y]) => {
          const screen = viewport.convertToViewportPoint(x, y);
          const restored = viewport.convertToPdfPoint(screen[0], screen[1]);
          error = Math.max(error, Math.abs(restored[0] - x), Math.abs(restored[1] - y));
          return screen;
        });
        results.push({ page: pageIndex + 1, scale, rotation: pdfPage.rotate, user_unit: pdfPage.userUnit,
          crop_box: pdfPage.view, max_roundtrip_error_pdf_points: error,
          rectangle: [Math.min(...transformed.map(p => p[0])), Math.min(...transformed.map(p => p[1])), Math.max(...transformed.map(p => p[0])), Math.max(...transformed.map(p => p[1]))] });
      }
    }
    await loading.destroy();
    return results;
  }, { api, paperId: paper.id, bbox: box });
  for (const check of matrixChecks) {
    expect(check.user_unit).toBe(2);
    expect(check.crop_box).toEqual([50, 70, 350, 450]);
    expect(check.max_roundtrip_error_pdf_points).toBeLessThanOrEqual(1e-8);
    const expected = viewportBox(box, check.scale, check.rotation);
    expect(Math.max(...check.rectangle.map((value: number, index: number) => Math.abs(value - expected[index])))).toBeLessThanOrEqual(1e-8);
  }
  expect(errors).toEqual([]);
  const report = { measured_at: new Date().toISOString(), fixture: 'tests/fixtures/geometry.pdf',
    fixture_sha256: createHash('sha256').update(await readFile(fixture)).digest('hex'),
    browser: await browser.version(), platform: os.platform(), cpu: os.cpus()[0]?.model,
    method: 'Real authenticated API import and four manual resources; actual PDF.js canvas pixels scanned for red rectangle and compared to DOM highlight plus independent CropBox/UserUnit/rotation formula',
    dpi_scope: 'Browser deviceScaleFactor=2 emulation, canvas DPR=2 verified. Actual Windows system DPI and display scaling were not changed.',
    ui_scales: [0.55, 1, 2.05], ui_scale_note: 'Each case explicitly resets persisted rotation through visible controls and resets zoom to 100%; then tests 55/100/205% using 15% steps.',
    supplemental_matrix_scales: [0.5, 1, 2], css_pixel_error_tolerance: 2,
    ui_cases: cases, matrix_checks: matrixChecks, javascript_errors: errors, status: 'passed' };
  await mkdir(path.resolve('../../artifacts'), { recursive: true });
  await writeFile(path.resolve('../../artifacts/pdf-geometry-browser.json'), `${JSON.stringify(report, null, 2)}\n`);
});
