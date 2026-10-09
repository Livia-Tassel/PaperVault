import { describe, expect, it } from 'vitest';
import { changedFields, mergeUntouchedFields } from './edits';

describe('non-destructive manual edits', () => {
  it('does not turn untouched automatic metadata into manual overrides', () => {
    const original = { title: 'Extracted title', authors: ['A', 'B'], notes: '' };
    expect(changedFields(original, { ...original, authors: ['A', 'B'], notes: 'Read again' })).toEqual({ notes: 'Read again' });
  });
  it('preserves intentional clearing instead of dropping null and empty values', () => {
    expect(changedFields({ title: 'Auto' as string | null, tags: ['old'] }, { title: null, tags: [] })).toEqual({ title: null, tags: [] });
  });
  it('detects a table edit independently of whether the editor is still open', () => {
    expect(changedFields({ table: { rows: [['A', '1']] } }, { table: { rows: [['A', '2']] } })).toEqual({ table: { rows: [['A', '2']] } });
  });
});

describe('live metadata refresh with an unsaved draft', () => {
  const baseline = { title: 'Initial automatic title', authors: 'A', notes: '', folders: [] as string[] };
  it('refreshes automatic title/authors but preserves unsaved notes and only patches notes', () => {
    const draft = { ...baseline, notes: 'Unfinished reading note' };
    const incoming = { ...baseline, title: 'Parsed automatic title', authors: 'A, B' };
    const merged = mergeUntouchedFields(baseline, draft, incoming);
    expect(merged).toEqual({ ...incoming, notes: 'Unfinished reading note' });
    expect(changedFields(incoming, merged)).toEqual({ notes: 'Unfinished reading note' });
    expect(baseline.title).toBe('Initial automatic title');
  });
  it('keeps a manually drafted title while accepting untouched fields', () => {
    const incoming = { ...baseline, title: 'New automatic title', authors: 'A, C', folders: ['server-folder'] };
    const draft = { ...baseline, title: 'My unsaved title' };
    expect(mergeUntouchedFields(baseline, draft, incoming)).toEqual({ ...incoming, title: 'My unsaved title' });
  });
  it('continues refreshing on a second poll after advancing the baseline', () => {
    const first = { ...baseline, title: 'First parsed title' };
    const current = mergeUntouchedFields(baseline, { ...baseline, notes: 'Draft' }, first);
    const second = { ...first, title: 'Improved parsed title', authors: 'A, B, C' };
    const merged = mergeUntouchedFields(first, current, second);
    expect(merged).toEqual({ ...second, notes: 'Draft' });
    expect(changedFields(second, merged)).toEqual({ notes: 'Draft' });
  });
});
