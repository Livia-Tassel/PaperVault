import { test, expect } from '@playwright/test';
import path from 'node:path';
import { readFile, writeFile } from 'node:fs/promises';

test('clicking the same outline target again returns after manual reading', async ({ page, request }) => {
  const base = 'http://127.0.0.1:8765/api/v1', headers = { Authorization: 'Bearer dev-token' };
  const name = `Repeated location ${Date.now()}`;
  const fixture = path.resolve(`../../.test-data/repeated-location-${Date.now()}.pdf`);
  await writeFile(fixture, Buffer.concat([await readFile(path.resolve('../../tests/fixtures/academic.pdf')), Buffer.from(`\n% ${name}\n`)]));
  const batch = await (await request.post(`${base}/papers/import-paths`, { headers, data: { paths: [fixture] } })).json();
  const paper = batch.items[0]; expect(paper).toBeTruthy();
  const jobs = await (await request.get(`${base}/jobs`, { headers })).json();
  for (const job of jobs.items.filter((job: { paper_id: string; status: string }) => job.paper_id === paper.id && ['queued', 'running'].includes(job.status)))
    await request.post(`${base}/jobs/${job.id}/cancel`, { headers });
  const edited = await request.patch(`${base}/papers/${paper.id}`, { headers, data: { title: name, sections: [
    { title: '定位第一节', level: 1, location: { page_index: 0, bbox: [50, 650, 550, 720] } },
  ] } }); expect(edited.ok()).toBeTruthy();
  await page.goto('/');
  await page.getByRole('button', { name: '论文库', exact: true }).click();
  await page.getByLabel('搜索论文', { exact: true }).fill(name);
  await expect(page.locator('.paper-primary')).toHaveCount(1);
  await page.locator('.paper-primary').click();
  await page.getByRole('tab', { name: '目录', exact: true }).click();
  const target = page.locator('.outline').getByRole('button', { name: '定位第一节', exact: true });
  await target.click();
  await expect(page.locator('.pdf-highlight')).toBeVisible();
  await page.getByLabel('PDF 页码', { exact: true }).fill('2');
  await page.getByLabel('PDF 页码', { exact: true }).press('Enter');
  await expect.poll(() => page.locator('.pdf-scroll').evaluate(element => element.scrollTop)).toBeGreaterThan(700);
  await target.click();
  await expect.poll(() => page.locator('.pdf-scroll').evaluate(element => element.scrollTop), { timeout: 3000 }).toBeLessThan(300);
  await expect(page.getByLabel('PDF 页码', { exact: true })).toHaveValue('1');
});
