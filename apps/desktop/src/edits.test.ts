import { describe, expect, it } from 'vitest';
import { changedFields } from './edits';

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
