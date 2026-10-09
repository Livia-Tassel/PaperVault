import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const base = 'http://127.0.0.1:8765/api/v1';
const headers = { Authorization: 'Bearer dev-token' };

test('export waits for a dirty table decision and includes the saved cells', async ({ page, request }, info) => {
  const papers = await (await request.get(`${base}/papers?limit=1000`, { headers })).json();
  const paper = papers.items.find((item: { filename: string }) => item.filename === 'academic.pdf');
  expect(paper).toBeTruthy();
  const name = `Manual export guard ${Date.now()}`;
  const created = await request.post(`${base}/papers/${paper.id}/resources`, { headers, data: {
    kind: 'table', name, caption: 'Synthetic manual table for export persistence verification', dpi: 150,
    location: { page_index: 0, bbox: [20, 20, 200, 100] },
  } });
  expect(created.ok()).toBeTruthy();
  const resource = await created.json();
  const seeded = await request.patch(`${base}/resources/${resource.id}`, { headers, data: {
    table: { rows: [['Heading'], ['Before export']], cells: [], header_rows: 1 },
  } });
  expect(seeded.ok()).toBeTruthy();
  await page.goto('/');
  await page.getByRole('button', { name: '表格库', exact: true }).click();
  await page.getByLabel('搜索表格', { exact: true }).fill(name);
  await expect(page.locator('.resource-card')).toHaveCount(1);
  await page.locator('.resource-card-image').click();
  const editor = page.getByRole('dialog').filter({ has: page.getByLabel('Caption', { exact: true }) });
  await editor.getByRole('button', { name: '编辑单元格 / 行列', exact: true }).click();
  await editor.getByLabel('第 2 行第 1 列', { exact: true }).fill('Updated export 中文');
  const downloads: string[] = [];
  page.on('download', download => downloads.push(download.suggestedFilename()));
  await editor.getByRole('button', { name: 'CSV', exact: true }).click();
  const guard = page.getByRole('dialog', { name: '有未保存的修改' });
  await expect(guard).toBeVisible();
  await guard.getByRole('button', { name: '继续编辑', exact: true }).click();
  await expect(editor.getByLabel('第 2 行第 1 列', { exact: true })).toHaveValue('Updated export 中文');
  expect(downloads).toEqual([]);
  await editor.getByRole('button', { name: 'CSV', exact: true }).click();
  const downloading = page.waitForEvent('download');
  await guard.getByRole('button', { name: '保存并继续', exact: true }).click();
  const download = await downloading;
  const output = info.outputPath('saved-table.csv'); await download.saveAs(output);
  const csv = await readFile(output, 'utf-8');
  expect(csv).toContain('Updated export 中文'); expect(csv).not.toContain('Before export');
  const stored = await (await request.get(`${base}/resources/${resource.id}`, { headers })).json();
  expect(stored.table.rows[1][0]).toBe('Updated export 中文');
  await expect(editor.getByRole('button', { name: '保存人工修改', exact: true })).toBeDisabled();
});

test('removing a page bookmark first preserves its edited note and undo restores that version', async ({ page, request }) => {
  const papers = await (await request.get(`${base}/papers?limit=1000`, { headers })).json();
  const paper = papers.items.find((item: { filename: string }) => item.filename === 'academic.pdf');
  const title = `Bookmark guard ${Date.now()}`;
  const response = await request.post(`${base}/papers/${paper.id}/annotations`, { headers, data: {
    kind: 'bookmark', title, body: 'Saved bookmark', locations: [{ page_index: 0, bbox: null }],
  } });
  expect(response.ok()).toBeTruthy();
  const bookmark = await response.json();
  await page.goto('/');
  await page.getByRole('button', { name: '笔记与书签', exact: true }).click();
  await page.getByLabel('搜索笔记', { exact: true }).fill(title);
  await expect(page.locator('.annotation-row')).toHaveCount(1);
  await page.locator('.annotation-row').getByRole('button', { name: '原文', exact: true }).click();
  await expect(page.locator('.paper-side').getByLabel('笔记内容', { exact: true })).toHaveValue('Saved bookmark');
  await page.locator('.paper-side').getByLabel('笔记内容', { exact: true }).fill('Edited before removal');
  await page.getByRole('button', { name: '移除本页书签', exact: true }).click();
  const guard = page.getByRole('dialog', { name: '有未保存的修改' });
  await expect(guard).toBeVisible();
  await guard.getByRole('button', { name: '保存并继续', exact: true }).click();
  await expect(page.locator('.annotation-undo')).toBeVisible();
  await page.locator('.annotation-undo').getByRole('button', { name: '撤销', exact: true }).click();
  await expect.poll(async () => (await request.get(`${base}/annotations/${bookmark.id}`, { headers })).status()).toBe(200);
  const stored = await (await request.get(`${base}/annotations/${bookmark.id}`, { headers })).json();
  expect(stored.deleted).toBe(false); expect(stored.body).toBe('Edited before removal');
});
