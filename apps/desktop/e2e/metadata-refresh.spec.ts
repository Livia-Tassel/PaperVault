import { test, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const api = 'http://127.0.0.1:8765/api/v1';
const headers = { Authorization: 'Bearer dev-token' };

test('polling server metadata updates untouched fields while retaining an unsaved note', async ({ page, request }) => {
  const imported = await (await request.post(`${api}/papers/import-paths`, { headers, data: {
    paths: [path.resolve('../../tests/fixtures/geometry.pdf')], recursive: false,
  } })).json();
  expect(imported.errors).toHaveLength(0);
  const paper = imported.items[0] || imported.duplicates[0];
  const stamp = Date.now();
  const oldTitle = `Initial metadata ${stamp}`;
  const newTitle = `Updated server metadata ${stamp}`;
  const draftNote = `Unsaved local note ${stamp}`;
  const initial = await request.patch(`${api}/papers/${paper.id}`, { headers, data: { title: oldTitle, authors: ['Initial Author'], notes: '' } });
  expect(initial.ok()).toBeTruthy();
  await page.goto('/');
  await page.getByLabel('搜索论文', { exact: true }).fill('geometry.pdf');
  await expect(page.locator('.paper-primary')).toHaveCount(1);
  await page.locator('.paper-primary').click();
  await expect(page.getByRole('textbox', { name: '标题', exact: true })).toHaveValue(oldTitle);
  await page.getByRole('textbox', { name: '个人备注', exact: true }).fill(draftNote);
  const changed = await request.patch(`${api}/papers/${paper.id}`, { headers, data: { title: newTitle, authors: ['Updated Author', 'Second Author'] } });
  expect(changed.ok()).toBeTruthy();
  await expect(page.getByRole('textbox', { name: '标题', exact: true })).toHaveValue(newTitle, { timeout: 12000 });
  await expect(page.getByRole('textbox', { name: '作者（逗号分隔）', exact: true })).toHaveValue('Updated Author, Second Author');
  await expect(page.getByRole('textbox', { name: '个人备注', exact: true })).toHaveValue(draftNote);
  // A revision refresh from the native favorite control must not remount the form.
  const star = page.getByRole('button', { name: '切换收藏', exact: true }).locator('svg');
  const previousFill = await star.getAttribute('fill');
  await page.getByRole('button', { name: '切换收藏', exact: true }).click();
  await expect(star).toHaveAttribute('fill', previousFill === 'none' ? 'currentColor' : 'none');
  await expect(page.getByRole('textbox', { name: '个人备注', exact: true })).toHaveValue(draftNote);
  const saved = page.waitForResponse(response => response.url().endsWith(`/papers/${paper.id}`) && response.request().method() === 'PATCH' && 'notes' in (response.request().postDataJSON() || {}));
  await page.getByRole('button', { name: '保存修改', exact: true }).click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toEqual({ notes: draftNote });
  const stored = await (await request.get(`${api}/papers/${paper.id}`, { headers })).json();
  expect(stored.title).toBe(newTitle);
  expect(stored.authors).toEqual(['Updated Author', 'Second Author']);
  expect(stored.notes).toBe(draftNote);
  await mkdir(path.resolve('../../artifacts'), { recursive: true });
  await writeFile(path.resolve('../../artifacts/metadata-refresh-ui.json'), `${JSON.stringify({
    status: 'passed', measured_at: new Date().toISOString(),
    method: 'Real API PATCH changes effective server metadata, then the existing five-second polling updates the same React form; no parser completion is claimed by this test.',
    title_and_authors_refreshed: true, unsaved_note_preserved: true,
    favorite_revision_does_not_discard_draft: true, saved_patch_fields: ['notes'],
  }, null, 2)}\n`);
});
