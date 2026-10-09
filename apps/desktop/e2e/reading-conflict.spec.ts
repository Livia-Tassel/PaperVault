import { test, expect } from '@playwright/test';
import path from 'node:path';
import { readFile, writeFile } from 'node:fs/promises';

const base = 'http://127.0.0.1:8765/api/v1';
const headers = { Authorization: 'Bearer dev-token' };

test('reading conflict decisions preserve the visible view or actually adopt the remote view', async ({ page, request }, info) => {
  const fixture = path.resolve(`../../.test-data/reading-conflict-${Date.now()}.pdf`);
  const original = await readFile(path.resolve('../../tests/fixtures/academic.pdf'));
  await writeFile(fixture, Buffer.concat([original, Buffer.from(`\n% reading-conflict-${Date.now()}\n`)]));
  const imported = await (await request.post(`${base}/papers/import-paths`, { headers, data: { paths: [fixture] } })).json();
  expect(imported.errors).toEqual([]);
  const paper = imported.items[0];
  const jobs = await (await request.get(`${base}/jobs`, { headers })).json();
  for (const job of jobs.items.filter((job: { paper_id: string; status: string }) => job.paper_id === paper.id && ['queued', 'running'].includes(job.status)))
    await request.post(`${base}/jobs/${job.id}/cancel`, { headers });
  await page.goto('/');
  await page.getByRole('button', { name: '论文库', exact: true }).click();
  await page.getByLabel('搜索论文', { exact: true }).fill(path.basename(fixture));
  await expect(page.locator('.paper-primary')).toHaveCount(1);
  await page.locator('.paper-primary').click();
  await expect(page.getByLabel('PDF 页码', { exact: true })).toHaveValue('1');
  const state = async () => (await request.get(`${base}/papers/${paper.id}/reading-state`, { headers })).json();
  await expect.poll(async () => (await state()).anchor).not.toBeNull();
  let current = await state();
  const external = await request.patch(`${base}/papers/${paper.id}/reading-state`, { headers, data: {
    expected_version: current.version, page_index: 1, anchor: [100, 600], scale: 1.4, rotation: 0, fit_mode: 'custom',
  } });
  expect(external.ok()).toBeTruthy();
  await page.getByRole('button', { name: '放大', exact: true }).click();
  await expect(page.locator('.reading-save-error')).toBeVisible();
  await page.getByRole('button', { name: '保存当前位置', exact: true }).click();
  await expect.poll(async () => { const value = await state(); return [value.page_index, value.scale]; }).toEqual([0, 1.15]);
  await expect(page.locator('.reading-save-error')).toHaveCount(0);

  current = await state();
  const second = await request.patch(`${base}/papers/${paper.id}/reading-state`, { headers, data: {
    expected_version: current.version, page_index: 1, anchor: [100, 500], scale: 1.7, rotation: 90, fit_mode: 'custom',
  } });
  expect(second.ok()).toBeTruthy();
  await page.getByRole('button', { name: '放大', exact: true }).click();
  await expect(page.locator('.reading-save-error')).toBeVisible();
  await page.getByRole('button', { name: '采用已保存记录', exact: true }).click();
  await expect(page.locator('.pdf-reader .zoom-label')).toHaveText('170%');
  await expect(page.getByLabel('PDF 页码', { exact: true })).toHaveValue('2');
  await expect.poll(async () => { const value = await state(); return [value.page_index, value.scale, value.rotation]; }).toEqual([1, 1.7, 90]);
  await page.screenshot({ path: info.outputPath('adopted-remote-reading.png') });
});
