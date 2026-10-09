import { test, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const api = 'http://127.0.0.1:8765/api/v1';
const headers = { Authorization: 'Bearer dev-token' };

test('chapter and reference corrections preserve location and survive a real save/reload', async ({ page, request }, info) => {
  const imported = await (await request.post(`${api}/papers/import-paths`, { headers,
    data: { paths: [path.resolve('../../tests/fixtures/academic.pdf')], recursive: false } })).json();
  expect(imported.errors).toHaveLength(0);
  const paper = imported.items[0] || imported.duplicates[0];
  const original = await (await request.get(`${api}/papers/${paper.id}`, { headers })).json();
  expect(original.sections.length).toBeGreaterThan(0);
  const originalLocation = original.sections[0].location;
  const unique = Date.now();
  const addedTitle = `E2E 新增章节 ${unique}`;
  const correctedReferences = [`[1] Synthetic reference A, 2026. Run ${unique}.`, '[2] 人工修订参考文献 B。'];
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('搜索论文', { exact: true }).fill('academic.pdf');
  await expect(page.locator('.paper-primary')).toHaveCount(1);
  await page.locator('.paper-primary').click();
  await page.getByRole('button', { name: '目录', exact: true }).click();
  await page.getByRole('button', { name: '编辑目录与参考文献', exact: true }).click();
  await page.getByRole('textbox', { name: '章节 1 标题', exact: true }).fill('E2E 修订章节');
  await page.getByRole('spinbutton', { name: '章节 1 层级', exact: true }).fill('2');
  await page.getByRole('button', { name: '添加章节', exact: true }).click();
  const newIndex = original.sections.length + 1;
  await page.getByRole('textbox', { name: `章节 ${newIndex} 标题`, exact: true }).fill(addedTitle);
  await page.getByRole('spinbutton', { name: `章节 ${newIndex} 页码`, exact: true }).fill('2');
  await page.getByRole('button', { name: '添加章节', exact: true }).click();
  await page.getByRole('button', { name: `删除章节 ${newIndex + 1}`, exact: true }).click();
  await page.getByRole('textbox', { name: '参考文献（每行一条）', exact: true }).fill(correctedReferences.join('\n'));
  const saved = page.waitForResponse(response => response.url().endsWith(`/papers/${paper.id}`) && response.request().method() === 'PATCH');
  await page.getByRole('button', { name: '保存目录与参考文献', exact: true }).click();
  const response = await saved;
  expect(response.ok()).toBeTruthy();
  expect(Object.keys(response.request().postDataJSON()).sort()).toEqual(['references', 'sections']);
  const updated = await response.json();
  expect(updated.sections[0].location).toEqual(originalLocation);
  expect(updated.sections[0].title).toBe('E2E 修订章节');
  expect(updated.sections[0].level).toBe(2);
  expect(updated.sections).toHaveLength(newIndex);
  expect(updated.sections.at(-1).location).toEqual({ page_index: 1, bbox: null });
  expect(updated.references).toEqual(correctedReferences);
  await page.reload();
  await page.getByLabel('搜索论文', { exact: true }).fill('academic.pdf');
  await expect(page.locator('.paper-primary')).toHaveCount(1);
  await page.locator('.paper-primary').click();
  await page.getByRole('button', { name: '目录', exact: true }).click();
  await expect(page.getByRole('button', { name: 'E2E 修订章节', exact: true })).toBeVisible();
  await expect(page.locator('.outline')).toContainText('人工修订参考文献 B。');
  await page.getByRole('button', { name: addedTitle, exact: true }).click();
  await expect(page.getByLabel('PDF 页码', { exact: true })).toHaveValue('2');
  await expect.poll(() => page.evaluate(() => {
    const scroller = document.querySelector('.pdf-scroll')!.getBoundingClientRect();
    const target = document.querySelector('[data-page="2"]')!.getBoundingClientRect();
    return target.top >= scroller.top - 10 && target.top <= scroller.top + 35;
  })).toBeTruthy();
  await page.screenshot({ path: info.outputPath('corrected-outline.png'), fullPage: true });
  expect(errors).toEqual([]);
  await mkdir(path.resolve('../../artifacts'), { recursive: true });
  await writeFile(path.resolve('../../artifacts/outline-ui-acceptance.json'), JSON.stringify({
    measured_at: new Date().toISOString(), status: 'passed', fixture: 'tests/fixtures/academic.pdf',
    changed_fields_only: ['sections', 'references'], first_section_location_preserved: true,
    added_section_page: 2, add_and_remove_draft_section: true, saved_and_reloaded: true,
    references: 2, page_navigation_verified: true, javascript_errors: errors,
  }, null, 2));
});

test('paper detail pagination can reach resource 201 in the real 1000-image gallery fixture', async ({ page }) => {
  const galleryApi = process.env.PAPERVAULT_GALLERY_API;
  test.skip(!galleryApi, 'Requires the isolated, explicitly synthetic gallery benchmark backend.');
  await page.route('http://127.0.0.1:8765/api/v1/**', route => route.continue({ url: route.request().url().replace(api, galleryApi!) }));
  await page.goto('/');
  await expect(page.locator('.paper-primary')).toHaveCount(1);
  await page.locator('.paper-primary').click();
  await page.getByRole('button', { name: '图片 1000', exact: true }).click();
  await expect(page.locator('.detail-resource')).toHaveCount(24);
  for (let index = 1; index <= 8; index++) {
    const response = page.waitForResponse(value => value.url().includes(`/resources?`) && value.url().includes(`offset=${index * 24}`));
    await page.locator('.paper-side').getByRole('button', { name: '下一页', exact: true }).click();
    expect((await response).ok()).toBeTruthy();
    await expect(page.locator('.detail-resource strong').first()).toHaveText(`Synthetic Figure ${String(index * 24 + 1).padStart(4, '0')} [benchmark]`);
    await expect(page.locator('.detail-resource')).toHaveCount(24);
  }
  await expect(page.locator('.detail-resource strong').nth(8)).toHaveText('Synthetic Figure 0201 [benchmark]');
  await page.locator('.paper-side').getByRole('button', { name: '上一页', exact: true }).click();
  await expect(page.locator('.detail-resource strong').first()).toHaveText('Synthetic Figure 0169 [benchmark]');
});
