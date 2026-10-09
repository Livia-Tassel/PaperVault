import { describe, expect, it } from 'vitest';
import { buildTextIndex, findTextMatches } from './reader-selection';
import { clientRectToPdf, intersectBox } from './geometry';

describe('PDF text search offsets', () => {
  it('maps split words and wrapped whitespace to native text-item offsets', () => {
    const index = buildTextIndex([{ str: 'Re' }, { str: 'search', hasEOL: true }, { str: '  Paper', hasEOL: true }]);
    expect(findTextMatches(index, 'SEARCH paper')).toEqual([{ start: { item: 1, offset: 0 }, end: { item: 2, offset: 7 }, quote: 'search\n  Paper' }]);
    expect(findTextMatches(index, 'research')[0]).toMatchObject({ start: { item: 0, offset: 0 }, end: { item: 1, offset: 6 } });
  });
  it('keeps offsets after compatibility ligatures, supplementary characters and case expansion', () => {
    const index = buildTextIndex([{ str: '🧪 ﬁnd İTEM and ﬁnd' }]);
    expect(findTextMatches(index, 'find').map(match => [match.start.offset, match.end.offset])).toEqual([[3, 6], [16, 19]]);
    expect(findTextMatches(index, '🧪')[0]).toMatchObject({ start: { item: 0, offset: 0 }, end: { item: 0, offset: 2 } });
    expect(findTextMatches(index, 'İTEM')[0].quote).toBe('İTEM');
  });
  it('skips marked-content entries but retains empty text-item numbering', () => {
    const index = buildTextIndex([{ type: 'beginMarkedContent' }, { str: '' }, { str: 'Ab Ab' }, { type: 'endMarkedContent' }]);
    expect(findTextMatches(index, 'ab').map(match => match.start)).toEqual([{ item: 1, offset: 0 }, { item: 1, offset: 3 }]);
    expect(findTextMatches(index, '  ')).toEqual([]);
    expect(findTextMatches(index, '[')).toEqual([]);
  });
});

describe('CSS selection rectangles to PDF coordinates', () => {
  const viewport = { width: 600, height: 760, viewBox: [50, 70, 350, 450],
    convertToViewportPoint: (x: number, y: number) => [(x - 50) * 2, (450 - y) * 2],
    convertToPdfPoint: (x: number, y: number) => [x / 2 + 50, 450 - y / 2] };
  it('preserves CropBox offset and UserUnit while ignoring raster DPR', () => {
    expect(clientRectToPdf({ left: 300, top: 620, right: 460, bottom: 740 }, { left: 200, top: 100, width: 600, height: 760 }, viewport)).toEqual([100, 130, 180, 190]);
  });
  it('handles ancestor CSS scaling and clamps to the actual CropBox', () => {
    expect(clientRectToPdf({ left: 50, top: 60, right: 450, bottom: 500 }, { left: 100, top: 100, width: 300, height: 380 }, viewport)).toEqual([50, 70, 350, 450]);
    expect(intersectBox([0, 0, 40, 40], [50, 70, 350, 450])).toBeNull();
  });
});
