import { describe, it, expect } from 'vitest';
import { toPdfBox, toViewportBox, normalizeBox, type Box, type ViewportTransform } from './geometry';

describe('PDF user-space to viewport mapping', () => {
  const source: Box = [42, 130, 222, 370];
  const transforms: ViewportTransform[] = [
    { convertToViewportPoint: (x, y) => [2 * (x - 12), 2 * (800 - y)], convertToPdfPoint: (x, y) => [x / 2 + 12, 800 - y / 2] },
    { convertToViewportPoint: (x, y) => [y * 1.5, x * 1.5], convertToPdfPoint: (x, y) => [y / 1.5, x / 1.5] },
    { convertToViewportPoint: (x, y) => [600 - x, y], convertToPdfPoint: (x, y) => [600 - x, y] },
    { convertToViewportPoint: (x, y) => [800 - y, 600 - x], convertToPdfPoint: (x, y) => [600 - y, 800 - x] },
  ];
  it.each(transforms)('round-trips a crop through scale, rotation and crop-box offsets', viewport => {
    const rendered = toViewportBox(source, viewport);
    expect(rendered[0]).toBeLessThan(rendered[2]); expect(rendered[1]).toBeLessThan(rendered[3]);
    expect(toPdfBox(rendered, viewport)).toEqual(source);
  });
  it('accepts a drag from bottom-right to top-left', () => expect(normalizeBox([200, 300, 20, 30])).toEqual([20, 30, 200, 300]));
});
