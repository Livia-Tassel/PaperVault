import { describe, expect, it } from 'vitest';
import { indexAnnotationsByPage } from './reader-annotations';
import type { Annotation } from './reading';

const record = (id: string, locations: Annotation['locations'], deleted = false): Annotation => ({
  id, locations, deleted, paper_id: 'paper', paper_title: '', kind: 'highlight', title: '', body: '', quote: '', color: 'amber', tags: [], version: 1, created_at: '', updated_at: '',
});
describe('annotation page index', () => {
  it('keeps one record per page, preserving all per-line rectangles and original objects', () => {
    const locations: Annotation['locations'] = [{ page_index: 3, bbox: [1, 2, 3, 4] }, { page_index: 0, bbox: [5, 6, 7, 8] }, { page_index: 3, bbox: [8, 9, 10, 11] }];
    const annotation = record('cross-page', locations), index = indexAnnotationsByPage([annotation]);
    expect(index.get(3)).toHaveLength(1); expect(index.get(3)![0].annotation).toBe(annotation);
    expect(index.get(3)![0].locations).toEqual([locations[0], locations[2]]);
    expect(index.get(0)![0].locations[0]).toBe(locations[1]); expect(index.has(1)).toBe(false);
  });
  it('omits deleted and unlocated notes while retaining page bookmarks', () => {
    const bookmark = { ...record('bookmark', [{ page_index: 7, bbox: null }]), kind: 'bookmark' as const };
    const index = indexAnnotationsByPage([record('deleted', [{ page_index: 1 }], true), record('unlocated', []), bookmark]);
    expect([...index.keys()]).toEqual([7]); expect(index.get(7)![0].annotation).toBe(bookmark);
  });
});
