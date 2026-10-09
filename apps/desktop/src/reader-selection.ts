import { clientRectToPdf, type ViewportTransform } from './geometry';
import type { Location } from './types';

export interface TextPoint { item: number; offset: number }
export interface TextMatch { start: TextPoint; end: TextPoint; quote: string }
export interface PageTextIndex {
  source: string;
  normalized: string;
  starts: number[];
  ends: number[];
  items: { start: number; end: number; item: number }[];
}
export interface TextPage {
  index: number;
  element: HTMLElement;
  textDivs: HTMLElement[];
  viewport: ViewportTransform & { width: number; height: number; viewBox: number[] };
}

function normalizeWithOffsets(source: string) {
  let normalized = '';
  const starts: number[] = [], ends: number[] = [];
  for (let offset = 0; offset < source.length;) {
    const character = String.fromCodePoint(source.codePointAt(offset)!);
    const end = offset + character.length;
    for (const value of character.normalize('NFKC').toLocaleLowerCase()) {
      if (/\s/u.test(value)) {
        if (normalized.endsWith(' ')) { ends[ends.length - 1] = end; continue; }
        normalized += ' '; starts.push(offset); ends.push(end);
      } else {
        normalized += value;
        // String offsets, Range offsets, and indexOf all use UTF-16 code units.
        for (let unit = 0; unit < value.length; unit++) { starts.push(offset); ends.push(end); }
      }
    }
    offset = end;
  }
  return { normalized, starts, ends };
}

export function buildTextIndex(content: ({ str: string; hasEOL?: boolean } | { type: string })[]): PageTextIndex {
  let source = '', item = 0;
  const items: PageTextIndex['items'] = [];
  for (const entry of content) {
    if (!('str' in entry)) continue;
    const start = source.length;
    source += entry.str;
    items.push({ start, end: source.length, item: item++ });
    if (entry.hasEOL) source += '\n';
  }
  return { source, items, ...normalizeWithOffsets(source) };
}

export function findTextMatches(index: PageTextIndex, query: string): TextMatch[] {
  const needle = normalizeWithOffsets(query).normalized.trim();
  if (!needle) return [];
  const matches: TextMatch[] = [];
  for (let at = index.normalized.indexOf(needle); at >= 0; at = index.normalized.indexOf(needle, at + needle.length)) {
    const start = index.starts[at], end = index.ends[at + needle.length - 1];
    const first = index.items.find(item => item.end > start);
    let last: PageTextIndex['items'][number] | undefined;
    for (let item = index.items.length - 1; item >= 0; item--) {
      if (index.items[item].start < end && index.items[item].end > index.items[item].start) { last = index.items[item]; break; }
    }
    if (!first || !last) continue;
    matches.push({ start: { item: first.item, offset: Math.max(0, start - first.start) },
      end: { item: last.item, offset: Math.min(last.end, end) - last.start }, quote: index.source.slice(start, end) });
  }
  return matches;
}

function pdfLocations(page: TextPage, rects: DOMRectList | DOMRect[]): Location[] {
  const pageRect = page.element.getBoundingClientRect();
  const boxes = Array.from(rects).filter(rect => rect.width > .1 && rect.height > .1)
    .map(rect => clientRectToPdf(rect, pageRect, page.viewport)).filter(box => box !== null);
  const seen = new Set<string>();
  return boxes.filter(box => { const key = box.map(n => n.toFixed(3)).join(','); if (seen.has(key)) return false; seen.add(key); return true; })
    .map(bbox => ({ page_index: page.index, bbox }));
}

/** Resolve PDF.js item offsets against its real text spans, preserving native glyph layout. */
export function matchLocations(page: TextPage, match: TextMatch): Location[] {
  const locations: Location[] = [];
  for (let item = match.start.item; item <= match.end.item; item++) {
    const node = page.textDivs[item]?.firstChild;
    if (!node || node.nodeType !== Node.TEXT_NODE || !node.isConnected) continue;
    const range = document.createRange();
    const length = node.textContent?.length || 0;
    range.setStart(node, Math.min(length, item === match.start.item ? match.start.offset : 0));
    range.setEnd(node, Math.min(length, item === match.end.item ? match.end.offset : length));
    if (!range.collapsed) locations.push(...pdfLocations(page, range.getClientRects()));
  }
  return locations;
}

export interface CapturedSelection { quote: string; locations: Location[]; clientX: number; clientY: number }

/** Split the browser's forward OR backward selection at text-span and page boundaries. */
export function captureTextSelection(selection: Selection, pages: TextPage[]): CapturedSelection | null {
  if (selection.isCollapsed || !selection.rangeCount) return null;
  const selected = selection.getRangeAt(0);
  const locations: Location[] = [], quotes: string[] = [];
  let clientX = 0, clientY = 0, found = false;
  for (const page of [...pages].sort((a, b) => a.index - b.index)) {
    let quote = '';
    for (const span of page.textDivs) {
      const node = span.firstChild;
      if (!node || node.nodeType !== Node.TEXT_NODE || !node.isConnected || !selected.intersectsNode(node)) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      if (selected.compareBoundaryPoints(Range.START_TO_START, range) > 0) range.setStart(selected.startContainer, selected.startOffset);
      if (selected.compareBoundaryPoints(Range.END_TO_END, range) < 0) range.setEnd(selected.endContainer, selected.endOffset);
      if (range.collapsed) continue;
      const rects = range.getClientRects(), parts = pdfLocations(page, rects);
      if (!parts.length) continue;
      if (!found) { clientX = rects[0].left; clientY = rects[0].top; found = true; }
      locations.push(...parts); quote += range.toString();
      if (span.nextSibling?.nodeName === 'BR') quote += '\n';
      if (locations.length > 512) throw new Error('选区过长，请每次选择不超过 512 个文本片段。');
    }
    if (quote.trim()) quotes.push(quote.trim());
  }
  const quote = quotes.join('\n');
  if (quote.length > 20000) throw new Error('选中文字超过 20,000 字，请缩小选区后重试。');
  return quote && locations.length ? { quote, locations, clientX, clientY } : null;
}
