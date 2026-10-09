export interface ViewportTransform { convertToViewportPoint: (x: number, y: number) => number[]; convertToPdfPoint: (x: number, y: number) => number[] }
export type Box = [number, number, number, number];
export function normalizeBox(box: Box): Box { return [Math.min(box[0], box[2]), Math.min(box[1], box[3]), Math.max(box[0], box[2]), Math.max(box[1], box[3])]; }
export function transformBox(box: Box, transform: (x: number, y: number) => number[]): Box {
  const points = [transform(box[0], box[1]), transform(box[2], box[1]), transform(box[2], box[3]), transform(box[0], box[3])];
  return [Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])), Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1]))];
}
export const toViewportBox = (box: Box, viewport: ViewportTransform): Box => transformBox(box, (x, y) => viewport.convertToViewportPoint(x, y));
export const toPdfBox = (box: Box, viewport: ViewportTransform): Box => transformBox(box, (x, y) => viewport.convertToPdfPoint(x, y));

/** Intersect in PDF user space: CropBox offsets and UserUnit belong to the viewport. */
export function intersectBox(box: Box, bounds: Box): Box | null {
  const a = normalizeBox(box), b = normalizeBox(bounds);
  const result: Box = [Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])];
  return result.every(Number.isFinite) && result[2] > result[0] && result[3] > result[1] ? result : null;
}

/** DOM coordinates are CSS pixels. Canvas DPR must never enter this transform. */
export function clientRectToPdf(rect: Pick<DOMRect, 'left' | 'top' | 'right' | 'bottom'>,
  pageRect: Pick<DOMRect, 'left' | 'top' | 'width' | 'height'>,
  viewport: ViewportTransform & { width: number; height: number; viewBox: number[] }): Box | null {
  if (pageRect.width <= 0 || pageRect.height <= 0) return null;
  const x = viewport.width / pageRect.width, y = viewport.height / pageRect.height;
  const clipped = intersectBox([(rect.left - pageRect.left) * x, (rect.top - pageRect.top) * y,
    (rect.right - pageRect.left) * x, (rect.bottom - pageRect.top) * y], [0, 0, viewport.width, viewport.height]);
  return clipped ? intersectBox(toPdfBox(clipped, viewport), viewport.viewBox as Box) : null;
}
