import { describe, expect, it, vi } from 'vitest';
vi.mock('./PdfViewer', () => ({ PdfViewer: () => null }));
vi.mock('./api', () => ({ exportAssets: vi.fn(), updatePaper: vi.fn(), post: vi.fn(), api: vi.fn(), request: vi.fn() }));
import { changeSectionPage, outlineChanges } from './PaperDetail';

describe('non-destructive outline editing', () => {
  const section = { title: 'Introduction', level: 1, location: { page_index: 2, bbox: [10, 20, 100, 200] as [number, number, number, number] } };
  it('preserves the original location when editing a heading and only patches sections', () => {
    const next = { ...section, title: 'Corrected introduction', level: 2 };
    const changes = outlineChanges([section], [next], ['A reference'], 'A reference');
    expect(changes).toEqual({ sections: [next] });
    expect(changes.sections?.[0].location).toEqual(section.location);
  });
  it('does not drop a valid box when the same page is entered again', () => {
    expect(changeSectionPage(section, 2)).toBe(section);
  });
  it('clears only the stale box when a section is moved to another page', () => {
    expect(changeSectionPage(section, 0)).toEqual({ ...section, page_index: 0, location: { page_index: 0, bbox: null } });
    expect(section.location.bbox).toEqual([10, 20, 100, 200]);
  });
  it('allows references to be edited or intentionally cleared without overriding sections', () => {
    expect(outlineChanges([section], [section], ['Old reference'], ' A new reference\r\n\n B ')).toEqual({ references: ['A new reference', 'B'] });
    expect(outlineChanges([section], [section], ['Old reference'], '')).toEqual({ references: [] });
  });
  it('keeps automatic multiline reference text untouched unless it was edited', () => {
    expect(outlineChanges([section], [section], ['Citation\ncontinued'], 'Citation\ncontinued')).toEqual({});
  });
});
