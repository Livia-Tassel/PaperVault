export interface ViewportTransform { convertToViewportPoint: (x: number, y: number) => number[]; convertToPdfPoint: (x: number, y: number) => number[] }
export type Box = [number, number, number, number];
export function normalizeBox(box: Box): Box { return [Math.min(box[0], box[2]), Math.min(box[1], box[3]), Math.max(box[0], box[2]), Math.max(box[1], box[3])]; }
export function transformBox(box: Box, transform: (x: number, y: number) => number[]): Box {
  const points = [transform(box[0], box[1]), transform(box[2], box[1]), transform(box[2], box[3]), transform(box[0], box[3])];
  return [Math.min(...points.map(p => p[0])), Math.min(...points.map(p => p[1])), Math.max(...points.map(p => p[0])), Math.max(...points.map(p => p[1]))];
}
export const toViewportBox = (box: Box, viewport: ViewportTransform): Box => transformBox(box, (x, y) => viewport.convertToViewportPoint(x, y));
export const toPdfBox = (box: Box, viewport: ViewportTransform): Box => transformBox(box, (x, y) => viewport.convertToPdfPoint(x, y));
