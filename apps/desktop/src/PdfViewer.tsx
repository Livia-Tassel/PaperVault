import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { Bookmark, ChevronDown, ChevronLeft, ChevronRight, Crop, Highlighter, Maximize, MessageSquarePlus, Minus, Plus, RotateCw, Search, X } from 'lucide-react';
import { getDocument, GlobalWorkerOptions, TextLayer, type PDFDocumentProxy, type PDFPageProxy } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import 'pdfjs-dist/web/pdf_viewer.css';
import './reader.css';
import { request } from './api';
import { ErrorMessage, Spinner } from './ui';
import { toPdfBox, toViewportBox, normalizeBox, intersectBox, type Box } from './geometry';
import { buildTextIndex, captureTextSelection, findTextMatches, matchLocations, type CapturedSelection, type PageTextIndex, type TextMatch, type TextPage } from './reader-selection';
import type { Location } from './types';
import type { Annotation, AnnotationSelection, ReaderViewState } from './reading';
import { indexAnnotationsByPage, type PageAnnotation } from './reader-annotations';

GlobalWorkerOptions.workerSrc = workerUrl;
type Viewport = ReturnType<PDFPageProxy['getViewport']>;
interface PageEntry extends TextPage { page: PDFPageProxy; viewport: Viewport; ready: boolean }
interface SearchHit extends TextMatch { pageIndex: number; id: number }
interface Navigation { pageIndex: number; anchor?: [number, number] | null; bbox?: Box | null; searchId?: number }
interface PdfProps {
  paperId: string; location?: Location | null; onCrop: (location: Location) => void; cropMode?: boolean; onCropMode: (value: boolean) => void;
  initialState?: ReaderViewState | null; onViewState?: (state: ReaderViewState) => void;
  annotations?: Annotation[]; selectedAnnotationId?: string | null; onAnnotationSelect?: (annotation: Annotation) => void;
  onAnnotate?: (selection: AnnotationSelection) => void; onBookmark?: (pageIndex: number) => void;
}
const defaultView: ReaderViewState = { page_index: 0, anchor: null, scale: 1, rotation: 0, fit_mode: 'custom' };
const readerState = (state?: ReaderViewState | null): ReaderViewState => state ? {
  page_index: state.page_index, anchor: state.anchor, scale: state.scale, rotation: state.rotation, fit_mode: state.fit_mode,
} : { ...defaultView };
const clampScale = (scale: number) => Math.min(8, Math.max(.05, scale));
const MAX_CANVAS_PIXELS = 16_777_216;
const MAX_CANVAS_SIDE = 8192;
const EMPTY_ANNOTATIONS: Annotation[] = [];
const EMPTY_PAGE_ANNOTATIONS: readonly PageAnnotation[] = [];
const EMPTY_HITS: readonly SearchHit[] = [];
const styleBox = (box: Box): CSSProperties => ({ left: box[0], top: box[1], width: box[2] - box[0], height: box[3] - box[1] });

interface PageProps {
  pdf: PDFDocumentProxy; index: number; scale: number; rotation: number; location?: Location | null; cropMode: boolean;
  onCrop: (location: Location) => void; register: (index: number, entry: PageEntry | null) => void;
  onRasterReduced: (index: number, reduced: boolean) => void;
  annotations: readonly PageAnnotation[]; selectedAnnotationId?: string | null; onAnnotationSelect: (annotation: Annotation) => void;
  hits: readonly SearchHit[]; activeHitId?: number;
}
const AnnotationOverlay = memo(function AnnotationOverlay({ entry, viewport, selected, onSelect }: {
  entry: PageAnnotation; viewport: Viewport; selected: boolean; onSelect: (annotation: Annotation) => void;
}) {
  const { annotation, locations } = entry;
  const rectangles = useMemo(() => locations.filter(location => location.bbox).map(location => toViewportBox(location.bbox!, viewport)), [locations, viewport]);
  const first = locations[0], marker = first?.bbox ? toViewportBox(first.bbox, viewport) : [4, 4, 4, 4];
  return <div className={`reader-annotation reader-color-${annotation.color} ${selected ? 'is-selected' : ''}`} data-annotation-id={annotation.id}>
    {rectangles.map((box, part) => <div key={part} className={`reader-annotation-rect ${annotation.kind === 'note' && !annotation.quote ? 'reader-area-note' : ''}`} style={styleBox(box)} />)}
    <button className="reader-annotation-marker" aria-label={`${annotation.kind === 'bookmark' ? '书签' : annotation.kind === 'highlight' ? '高亮' : '笔记'}：${annotation.title || annotation.quote.slice(0, 50) || `第 ${first.page_index + 1} 页`}`} title={annotation.title || annotation.quote || annotation.body || '页书签'} style={{ left: Math.max(0, Math.min(viewport.width - 22, marker[0] - 22)), top: Math.max(0, marker[1]) }} onClick={event => { event.stopPropagation(); onSelect(annotation); }}>{annotation.kind === 'bookmark' ? <Bookmark size={13} /> : annotation.kind === 'highlight' ? <Highlighter size={13} /> : <MessageSquarePlus size={13} />}</button>
  </div>;
});
const AnnotationLayer = memo(function AnnotationLayer({ entries, viewport, selectedId, onSelect }: {
  entries: readonly PageAnnotation[]; viewport: Viewport; selectedId?: string | null; onSelect: (annotation: Annotation) => void;
}) {
  return <>{entries.map(entry => <AnnotationOverlay key={entry.annotation.id} entry={entry} viewport={viewport} selected={selectedId === entry.annotation.id} onSelect={onSelect} />)}</>;
});
const PdfPage = memo(function PdfPage({ pdf, index, scale, rotation, location, cropMode, onCrop, register, onRasterReduced, annotations, selectedAnnotationId, onAnnotationSelect, hits, activeHitId }: PageProps) {
  const [page, setPage] = useState<PDFPageProxy | null>(null);
  const [near, setNear] = useState(index === 0), [visited, setVisited] = useState(index === 0);
  const [error, setError] = useState(''), [selection, setSelection] = useState<Box | null>(null), [textRevision, setTextRevision] = useState(0);
  const [readyViewport, setReadyViewport] = useState<Viewport | null>(null);
  const box = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null), text = useRef<HTMLDivElement>(null);
  const textDivs = useRef<HTMLElement[]>([]), drag = useRef<[number, number] | null>(null);
  const viewport = useMemo(() => page?.getViewport({ scale, rotation: (page.rotate + rotation) % 360 }), [page, scale, rotation]);
  useEffect(() => { if (!cropMode) { drag.current = null; setSelection(null); } }, [cropMode]);
  useEffect(() => { let disposed = false; void pdf.getPage(index + 1).then(value => { if (!disposed) setPage(value); }).catch(cause => { if (!disposed) setError(String(cause)); }); return () => { disposed = true; }; }, [pdf, index]);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => { const visible = entries[0].isIntersecting; setNear(visible); if (visible) setVisited(true); }, { root: box.current?.closest('.pdf-scroll'), rootMargin: '800px 0px' });
    if (box.current) observer.observe(box.current); return () => observer.disconnect();
  }, []);
  useLayoutEffect(() => {
    if (page && viewport && box.current) register(index, { index, page, viewport, element: box.current, textDivs: [], ready: false });
    return () => register(index, null);
  }, [page, viewport, index, register]);
  useEffect(() => {
    if (!page || !near || !viewport || !canvas.current) return;
    // Bound raster allocation at extreme zoom. Text and coordinates retain full CSS resolution.
    const requestedRatio = window.devicePixelRatio || 1;
    const pixelRatio = Math.min(requestedRatio, Math.sqrt(MAX_CANVAS_PIXELS / (viewport.width * viewport.height)), MAX_CANVAS_SIDE / Math.max(viewport.width, viewport.height));
    const reduced = pixelRatio < requestedRatio - .0001, round = reduced ? Math.floor : Math.ceil;
    const node = canvas.current; node.width = Math.max(1, round(viewport.width * pixelRatio)); node.height = Math.max(1, round(viewport.height * pixelRatio));
    node.dataset.rasterScale = String(pixelRatio); node.dataset.rasterReduced = String(reduced);
    onRasterReduced(index, reduced);
    const context = node.getContext('2d'); if (!context) return;
    const render = page.render({ canvas: node, canvasContext: context, viewport, transform: [pixelRatio, 0, 0, pixelRatio, 0, 0] });
    let cancelled = false;
    void render.promise.catch(cause => { if (!cancelled && cause?.name !== 'RenderingCancelledException') setError(String(cause)); });
    return () => { cancelled = true; render.cancel(); node.width = 0; node.height = 0; onRasterReduced(index, false); };
  }, [page, near, viewport, index, onRasterReduced]);
  useEffect(() => {
    if (!page || !visited || !viewport || !text.current || !box.current) return;
    const textNode = text.current; textNode.replaceChildren(); textDivs.current = [];
    let layer: TextLayer | undefined;
    let cancelled = false;
    void page.getTextContent().then(async content => {
      if (cancelled) return;
      // Match PDF.js's measuring canvas language. Inheriting the app's zh-CN
      // changes generic Latin fonts on Windows and corrupts span widths.
      // Explicit "und" is essential: Chrome's DOM and canvas disagree for
      // an empty lang attribute under an inherited Chinese UI language.
      textNode.lang = content.lang || 'und';
      layer = new TextLayer({ textContentSource: content, container: textNode, viewport });
      await layer.render();
      if (cancelled || !box.current) return;
      textDivs.current = layer.textDivs;
      register(index, { index, page, viewport, element: box.current, textDivs: layer.textDivs, ready: true });
      setReadyViewport(viewport);
      setTextRevision(value => value + 1);
    }).catch(cause => { if (!cancelled && cause?.name !== 'AbortException') setError(String(cause)); });
    // Retain visited text layers while scrolling so cross-page selections keep their anchor.
    return () => { cancelled = true; layer?.cancel(); textDivs.current = []; textNode.replaceChildren(); };
  }, [page, visited, viewport, index, register]);
  const searchLocations = useMemo(() => {
    if (!viewport || readyViewport !== viewport || !box.current) return [];
    const entry = { index, viewport, element: box.current, textDivs: textDivs.current };
    return hits.flatMap(hit => matchLocations(entry, hit).map((location, part) => ({ location, active: hit.id === activeHitId, key: `${hit.id}-${part}` })));
  }, [hits, activeHitId, textRevision, viewport, readyViewport, index]);
  const rect = location?.bbox && viewport ? toViewportBox(location.bbox, viewport) : null;
  const point = (event: React.PointerEvent): [number, number] => {
    const bounds = box.current!.getBoundingClientRect();
    return [Math.max(0, Math.min(viewport!.width, (event.clientX - bounds.left) * viewport!.width / bounds.width)), Math.max(0, Math.min(viewport!.height, (event.clientY - bounds.top) * viewport!.height / bounds.height))];
  };
  const pageStyle = { width: viewport?.width || 612 * scale, height: viewport?.height || 792 * scale,
    '--scale-factor': scale, '--user-unit': page?.userUnit || 1, '--total-scale-factor': scale * (page?.userUnit || 1), '--scale-round-x': '1px', '--scale-round-y': '1px' } as CSSProperties;
  return <div className="pdf-page-wrap"><div data-page={index + 1} data-near={near ? 'true' : 'false'} data-text-ready={readyViewport === viewport && textDivs.current.length ? 'true' : 'false'} className="pdf-page" ref={box} style={pageStyle}
    onPointerDown={event => { if (!cropMode || !viewport || event.button !== 0) return; event.preventDefault(); box.current?.setPointerCapture(event.pointerId); const p = point(event); drag.current = p; setSelection([p[0], p[1], p[0], p[1]]); }}
    onPointerMove={event => { if (drag.current) setSelection(normalizeBox([...drag.current, ...point(event)] as Box)); }}
    onPointerCancel={() => { drag.current = null; setSelection(null); }}
    onPointerUp={event => {
      if (!drag.current || !viewport) return;
      const selected = normalizeBox([...drag.current, ...point(event)] as Box); drag.current = null; setSelection(null);
      if (box.current?.hasPointerCapture(event.pointerId)) box.current.releasePointerCapture(event.pointerId);
      const bbox = intersectBox(toPdfBox(selected, viewport), viewport.viewBox as Box);
      if (bbox && selected[2] - selected[0] >= 5 && selected[3] - selected[1] >= 5) onCrop({ page_index: index, bbox });
    }}>
    {error ? <ErrorMessage message={error} /> : <><canvas ref={canvas} width={0} height={0} style={{ width: viewport?.width, height: viewport?.height }} /><div ref={text} className="textLayer" />
      {near && viewport && <AnnotationLayer entries={annotations} viewport={viewport} selectedId={selectedAnnotationId} onSelect={onAnnotationSelect} />}
      {near && viewport && searchLocations.map(hit => <div key={hit.key} className={`reader-search-hit ${hit.active ? 'is-active' : ''}`} style={styleBox(toViewportBox(hit.location.bbox!, viewport))} />)}
      {rect && <div className="pdf-highlight" style={styleBox(rect)} aria-label="资源所在区域" />}{selection && <div className="pdf-selection" style={styleBox(selection)} />}
    </>}
  </div><span className="page-number">{index + 1}</span></div>;
});

export function PdfViewer({ paperId, location, onCrop, cropMode, onCropMode, initialState, onViewState,
  annotations = EMPTY_ANNOTATIONS, selectedAnnotationId, onAnnotationSelect, onAnnotate, onBookmark }: PdfProps) {
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState('');
  const [view, setView] = useState<ReaderViewState>(() => readerState(initialState));
  const [pageNumber, setPageNumber] = useState((initialState?.page_index || 0) + 1);
  const [pageDraft, setPageDraft] = useState(String((initialState?.page_index || 0) + 1));
  const [revision, setRevision] = useState(0);
  const [navigationVersion, setNavigationVersion] = useState(0);
  const [areaNote, setAreaNote] = useState(false);
  const [selection, setSelection] = useState<CapturedSelection | null>(null);
  const [selectionError, setSelectionError] = useState('');
  const [zoomOpen, setZoomOpen] = useState(false);
  const [zoomDraft, setZoomDraft] = useState('100');
  const [findOpen, setFindOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [activeHit, setActiveHit] = useState(0);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [reducedPages, setReducedPages] = useState<Set<number>>(() => new Set());
  const root = useRef<HTMLElement>(null), scroll = useRef<HTMLDivElement>(null), findInput = useRef<HTMLInputElement>(null);
  const registry = useRef(new Map<number, PageEntry>()), indexes = useRef(new Map<number, PageTextIndex>());
  const pending = useRef<Navigation | null>(null), lastLocation = useRef<Location | null | undefined>(undefined);
  const viewRef = useRef(view); viewRef.current = view;
  const hitsRef = useRef(hits); hitsRef.current = hits;
  const onViewRef = useRef(onViewState); onViewRef.current = onViewState;
  const callbacks = useRef({ onCrop, onAnnotate, onAnnotationSelect, areaNote }); callbacks.current = { onCrop, onAnnotate, onAnnotationSelect, areaNote };
  const annotationsByPage = useMemo(() => indexAnnotationsByPage(annotations), [annotations]);
  const hitsByPage = useMemo(() => {
    const pages = new Map<number, SearchHit[]>();
    for (const hit of hits) { const current = pages.get(hit.pageIndex); if (current) current.push(hit); else pages.set(hit.pageIndex, [hit]); }
    return pages;
  }, [hits]);
  const lastReported = useRef(''), restoring = useRef(true), scrollFrame = useRef(0);

  const readPosition = useCallback((): ReaderViewState | null => {
    const container = scroll.current; if (!container) return null;
    const bounds = container.getBoundingClientRect();
    const entries = [...registry.current.values()].sort((a, b) => a.index - b.index);
    const entry = entries.find(value => value.element.getBoundingClientRect().bottom > bounds.top + 19) || entries.at(-1);
    if (!entry) return null;
    const box = entry.element.getBoundingClientRect();
    const x = Math.max(0, Math.min(entry.viewport.width, bounds.left + 14 - box.left));
    const y = Math.max(0, Math.min(entry.viewport.height, bounds.top + 18 - box.top));
    const point = entry.viewport.convertToPdfPoint(x, y);
    return { ...viewRef.current, page_index: entry.index, anchor: [point[0], point[1]] };
  }, []);
  const syncPosition = useCallback(() => {
    if (pending.current || restoring.current) return;
    const state = readPosition(); if (!state) return;
    setPageNumber(state.page_index + 1);
    setPageDraft(current => globalThis.document.activeElement?.getAttribute('aria-label') === 'PDF 页码' ? current : String(state.page_index + 1));
    const key = JSON.stringify({ ...state, anchor: state.anchor?.map(n => Math.round(n * 1000) / 1000) });
    if (key !== lastReported.current) { lastReported.current = key; onViewRef.current?.(state); }
  }, [readPosition]);
  const schedulePosition = useCallback(() => {
    cancelAnimationFrame(scrollFrame.current); scrollFrame.current = requestAnimationFrame(syncPosition);
  }, [syncPosition]);
  const register = useCallback((index: number, entry: PageEntry | null) => {
    if (entry) registry.current.set(index, entry); else registry.current.delete(index);
    setRevision(value => value + 1);
  }, []);
  const rasterReduced = useCallback((index: number, reduced: boolean) => {
    setReducedPages(current => {
      if (current.has(index) === reduced) return current;
      const next = new Set(current); if (reduced) next.add(index); else next.delete(index); return next;
    });
  }, []);
  const navigate = useCallback((target: Navigation) => {
    pending.current = target;
    setPageNumber(target.pageIndex + 1); setPageDraft(String(target.pageIndex + 1));
    setNavigationVersion(value => value + 1);
  }, []);

  useEffect(() => {
    let disposed = false; let task: ReturnType<typeof getDocument> | undefined;
    const controller = new AbortController(), restored = readerState(initialState);
    setPdf(null); setError(''); registry.current.clear(); indexes.current.clear();
    restoring.current = true; lastReported.current = ''; lastLocation.current = location;
    setView(restored); setQuery(''); setHits([]); setSelection(null); setAreaNote(false); setReducedPages(new Set());
    pending.current = location ? { pageIndex: location.page_index, bbox: location.bbox } : { pageIndex: restored.page_index, anchor: restored.anchor };
    void request(`/papers/${paperId}/pdf`, { signal: controller.signal }).then(response => response.arrayBuffer()).then(data => {
      if (disposed) return;
      task = getDocument({ data: new Uint8Array(data), enableXfa: false, useSystemFonts: true,
        cMapUrl: '/pdfjs/cmaps/', cMapPacked: true, standardFontDataUrl: '/pdfjs/standard_fonts/', wasmUrl: '/pdfjs/wasm/' });
      return task.promise;
    }).then(value => {
      if (!disposed && value) { if (pending.current) pending.current.pageIndex = Math.min(value.numPages - 1, Math.max(0, pending.current.pageIndex)); setPdf(value); }
    }).catch(e => { if (!disposed) setError(e instanceof Error ? e.message : String(e)); });
    return () => { disposed = true; controller.abort(); cancelAnimationFrame(scrollFrame.current); void task?.destroy(); };
    // Restore once per paper; parent saves must not rewind the reader.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperId]);
  useEffect(() => {
    if (!pdf || location === lastLocation.current) return;
    lastLocation.current = location;
    if (location) navigate({ pageIndex: Math.max(0, Math.min(pdf.numPages - 1, location.page_index)), bbox: location.bbox });
  }, [pdf, location, navigate]);

  useLayoutEffect(() => {
    const target = pending.current, container = scroll.current;
    if (!target || !container || !pdf) return;
    const entry = registry.current.get(target.pageIndex);
    if (!entry || entry.viewport.scale !== view.scale || entry.viewport.rotation !== (entry.page.rotate + view.rotation) % 360) return;
    // Earlier page dimensions must settle before restoring an offset on a later page.
    if (Array.from({ length: target.pageIndex }, (_, i) => registry.current.get(i)).some(value => !value || value.viewport.scale !== view.scale)) return;
    let targetBox = target.bbox;
    if (target.searchId !== undefined) {
      if (!entry.ready) {
        const bounds = entry.element.getBoundingClientRect(), parent = container.getBoundingClientRect();
        container.scrollTop += bounds.top - parent.top - 18; return;
      }
      const hit = hitsRef.current.find(value => value.id === target.searchId);
      targetBox = hit ? matchLocations(entry, hit)[0]?.bbox : null;
    }
    const bounds = entry.element.getBoundingClientRect(), parent = container.getBoundingClientRect();
    let point = [0, 0], alignY = 18, alignX = 14;
    if (targetBox) {
      const box = toViewportBox(targetBox, entry.viewport); point = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2];
      alignY = container.clientHeight / 2; alignX = container.clientWidth / 2;
    } else if (target.anchor) point = entry.viewport.convertToViewportPoint(...target.anchor);
    container.scrollTop += bounds.top - parent.top + point[1] - alignY;
    container.scrollLeft += bounds.left - parent.left + point[0] - alignX;
    pending.current = null; restoring.current = false; schedulePosition();
  }, [pdf, revision, navigationVersion, view, schedulePosition]);

  const fitScale = useCallback((mode: 'width' | 'page', rotation: number, index: number) => {
    const entry = registry.current.get(index), container = scroll.current; if (!entry || !container) return null;
    const viewport = entry.page.getViewport({ scale: 1, rotation: (entry.page.rotate + rotation) % 360 });
    const width = (container.clientWidth - 28) / viewport.width;
    return clampScale(mode === 'width' ? width : Math.min(width, (container.clientHeight - 54) / viewport.height));
  }, []);
  const changeView = useCallback((patch: Partial<ReaderViewState>) => {
    const position = readPosition(), next = { ...viewRef.current, ...patch };
    const index = pending.current?.pageIndex ?? position?.page_index ?? pageNumber - 1;
    if (next.fit_mode !== 'custom') next.scale = fitScale(next.fit_mode, next.rotation, index) ?? next.scale;
    next.scale = clampScale(next.scale);
    pending.current ??= { pageIndex: index, anchor: position?.anchor };
    setSelection(null); globalThis.getSelection()?.removeAllRanges(); setView(next); setNavigationVersion(value => value + 1);
  }, [fitScale, pageNumber, readPosition]);
  useEffect(() => {
    const node = scroll.current; if (!node) return;
    const observer = new ResizeObserver(() => {
      const current = viewRef.current;
      if (current.fit_mode !== 'custom') {
        const position = readPosition(), index = pending.current?.pageIndex ?? position?.page_index ?? current.page_index;
        const scale = fitScale(current.fit_mode, current.rotation, index);
        if (scale !== null && Math.abs(scale - current.scale) > .0001) {
          pending.current ??= { pageIndex: index, anchor: position?.anchor }; setView(value => ({ ...value, scale })); return;
        }
      }
      schedulePosition();
    });
    observer.observe(node); return () => observer.disconnect();
  }, [fitScale, readPosition, schedulePosition]);
  useEffect(() => {
    if (view.fit_mode === 'custom' || !pdf) return;
    const index = pending.current?.pageIndex ?? pageNumber - 1, scale = fitScale(view.fit_mode, view.rotation, index);
    if (scale !== null && Math.abs(scale - view.scale) > .0001) changeView({ scale });
  }, [revision, pdf, pageNumber, view.fit_mode, view.rotation, view.scale, fitScale, changeView]);

  useEffect(() => { if (cropMode) { setAreaNote(false); setSelection(null); } }, [cropMode]);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const capture = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const selected = globalThis.getSelection();
        if (!selected || cropMode || areaNote || !onAnnotate || !root.current?.contains(selected.anchorNode) || !root.current.contains(selected.focusNode)) { setSelection(null); return; }
        try { setSelection(captureTextSelection(selected, [...registry.current.values()].filter(entry => entry.ready))); setSelectionError(''); }
        catch (cause) { setSelection(null); setSelectionError(cause instanceof Error ? cause.message : String(cause)); }
      }, 100);
    };
    globalThis.document.addEventListener('selectionchange', capture);
    return () => { clearTimeout(timer); globalThis.document.removeEventListener('selectionchange', capture); };
  }, [cropMode, areaNote, onAnnotate]);

  useEffect(() => {
    let cancelled = false;
    if (pending.current?.searchId !== undefined) pending.current = null;
    if (!pdf || !findOpen || !query.trim()) { setHits([]); setSearching(false); setSearchError(''); return; }
    setSearching(true); setSearchError(''); setHits([]);
    const timer = setTimeout(() => {
      void (async () => {
        const found: SearchHit[] = [];
        for (let index = 0; index < pdf.numPages; index++) {
          if (cancelled) return;
          let content = indexes.current.get(index);
          if (!content) {
            const page = await pdf.getPage(index + 1), text = await page.getTextContent(); if (cancelled) return;
            content = buildTextIndex(text.items); indexes.current.set(index, content);
          }
          for (const match of findTextMatches(content, query)) found.push({ ...match, pageIndex: index, id: found.length });
        }
        if (cancelled) return;
        setHits(found); hitsRef.current = found; setActiveHit(0); setSearching(false);
        if (found.length) navigate({ pageIndex: found[0].pageIndex, searchId: found[0].id });
      })().catch(cause => { if (!cancelled) { setSearchError(String(cause)); setSearching(false); } });
    }, 220);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [pdf, findOpen, query, navigate]);
  const moveHit = (offset: number) => {
    if (!hits.length) return;
    const index = (activeHit + offset + hits.length) % hits.length; setActiveHit(index); navigate({ pageIndex: hits[index].pageIndex, searchId: hits[index].id });
  };
  const openFind = useCallback(() => { setFindOpen(true); requestAnimationFrame(() => { findInput.current?.focus(); findInput.current?.select(); }); }, []);
  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if (event.isComposing || globalThis.document.querySelector('[role="dialog"][data-state="open"], dialog[open]')) return;
      const target = event.target as HTMLElement | null, editing = target?.closest('input, textarea, select, [contenteditable="true"]');
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f' && (!editing || target === findInput.current)) { event.preventDefault(); openFind(); }
      if (event.key === 'Escape' && (!editing || target === findInput.current)) {
        if (findOpen) { event.preventDefault(); setFindOpen(false); setHits([]); }
        if (cropMode) onCropMode(false);
        setSelection(null); setAreaNote(false); setZoomOpen(false);
      }
    };
    globalThis.document.addEventListener('keydown', keyboard); return () => globalThis.document.removeEventListener('keydown', keyboard);
  }, [findOpen, openFind, cropMode, onCropMode]);

  const leaveFullscreen = useCallback(async () => { if (globalThis.document.fullscreenElement === root.current) await globalThis.document.exitFullscreen(); }, []);
  const handlePageCrop = useCallback((value: Location) => {
    const { areaNote, onCrop, onAnnotate } = callbacks.current;
    if (areaNote) { setAreaNote(false); void leaveFullscreen().then(() => onAnnotate?.({ kind: 'note', quote: '', locations: [value] })); } else onCrop(value);
  }, [leaveFullscreen]);
  const handleAnnotationSelect = useCallback((annotation: Annotation) => {
    const { onAnnotationSelect } = callbacks.current;
    void leaveFullscreen().then(() => onAnnotationSelect?.(annotation));
  }, [leaveFullscreen]);
  const annotate = async (kind: 'highlight' | 'note') => {
    if (!selection) return;
    const draft = { kind, quote: selection.quote, locations: selection.locations };
    setSelection(null); globalThis.getSelection()?.removeAllRanges(); await leaveFullscreen(); onAnnotate?.(draft);
  };
  const jump = (target: number) => { if (pdf) navigate({ pageIndex: Math.min(pdf.numPages - 1, Math.max(0, (target || 1) - 1)) }); };
  const fullscreen = async () => { if (globalThis.document.fullscreenElement) await globalThis.document.exitFullscreen(); else await root.current?.requestFullscreen(); };
  const bookmarked = annotations.some(annotation => !annotation.deleted && annotation.kind === 'bookmark' && annotation.locations.some(item => item.page_index === pageNumber - 1));
  const rootBounds = root.current?.getBoundingClientRect();
  const selectionLeft = rootBounds && selection ? Math.max(8, Math.min(rootBounds.width - 180, selection.clientX - rootBounds.left)) : 8;
  const selectionTop = rootBounds && selection ? Math.max(50, selection.clientY - rootBounds.top - 44) : 50;

  return <section className={`pdf-reader pv-reader ${cropMode || areaNote ? 'is-cropping' : ''}`} ref={root} aria-label="PDF 阅读器">
    <div className="pdf-toolbar">
      <div className="reader-toolbar-group">
        <button className="icon-button" aria-label="上一页" disabled={pageNumber <= 1} onClick={() => jump(pageNumber - 1)}><ChevronLeft size={18} /></button>
        <form onSubmit={event => { event.preventDefault(); const target = Number(pageDraft); event.currentTarget.querySelector('input')?.blur(); jump(target); }}><input aria-label="PDF 页码" className="page-input" inputMode="numeric" value={pageDraft} onChange={event => setPageDraft(event.target.value)} onBlur={() => setPageDraft(String(pageNumber))} /><span className="muted"> / {pdf?.numPages || '—'}</span></form>
        <button className="icon-button" aria-label="下一页" disabled={!pdf || pageNumber >= pdf.numPages} onClick={() => jump(pageNumber + 1)}><ChevronRight size={18} /></button>
      </div><span className="toolbar-divider" />
      <div className="reader-toolbar-group reader-zoom">
        <button className="icon-button" aria-label="缩小" disabled={view.scale <= .05} onClick={() => changeView({ scale: view.scale - .15, fit_mode: 'custom' })}><Minus size={17} /></button>
        <button className="zoom-label" title="恢复 100%" onClick={() => changeView({ scale: 1, fit_mode: 'custom' })}>{Math.round(view.scale * 100)}%</button>
        <button className="icon-button reader-small-button" aria-label="设置缩放比例" aria-expanded={zoomOpen} onClick={() => { setZoomDraft(String(Math.round(view.scale * 100))); setZoomOpen(value => !value); }}><ChevronDown size={13} /></button>
        <button className="icon-button" aria-label="放大" disabled={view.scale >= 8} onClick={() => changeView({ scale: view.scale + .15, fit_mode: 'custom' })}><Plus size={17} /></button>
        {zoomOpen && <form className="reader-zoom-popover" onSubmit={event => { event.preventDefault(); const value = Number(zoomDraft); if (Number.isFinite(value) && value >= 5 && value <= 800) { changeView({ scale: value / 100, fit_mode: 'custom' }); setZoomOpen(false); } }}><label>缩放<input autoFocus aria-label="自定义缩放百分比" type="number" min={5} max={800} step="any" value={zoomDraft} onChange={event => setZoomDraft(event.target.value)} />%</label><button className="button small" type="submit">应用</button><span>5–800%</span></form>}
      </div>
      <select className="reader-fit-select" aria-label="页面适应方式" value={view.fit_mode} onChange={event => changeView({ fit_mode: event.target.value as ReaderViewState['fit_mode'] })}><option value="custom">自定义</option><option value="width">适合宽度</option><option value="page">适合整页</option></select>
      <button className="icon-button" aria-label="旋转 PDF" onClick={() => changeView({ rotation: ((view.rotation + 90) % 360) as ReaderViewState['rotation'] })}><RotateCw size={16} /></button>
      <span className="toolbar-spacer" /><div className="reader-toolbar-group">
        <button className={`icon-button ${findOpen ? 'active' : ''}`} aria-label="查找 PDF 文字" title="查找文字 (Ctrl+F)" onClick={openFind}><Search size={17} /></button>
        {onBookmark && <button className={`icon-button ${bookmarked ? 'active' : ''}`} aria-label={bookmarked ? '移除本页书签' : '添加本页书签'} aria-pressed={bookmarked} title={bookmarked ? '移除本页书签' : '添加本页书签'} onClick={() => onBookmark(pageNumber - 1)}><Bookmark size={17} fill={bookmarked ? 'currentColor' : 'none'} /></button>}
        {onAnnotate && <button className={`icon-button ${areaNote ? 'active' : ''}`} aria-label="框选区域笔记" aria-pressed={areaNote} title="框选区域，添加笔记" onClick={() => { onCropMode(false); setAreaNote(value => !value); setSelection(null); }}><MessageSquarePlus size={17} /></button>}
        <button className={`icon-button ${cropMode ? 'active' : ''}`} aria-label="框选图片区域" title="框选 PDF 区域，创建图片资源" onClick={() => { setAreaNote(false); onCropMode(!cropMode); }}><Crop size={17} /></button>
        <button className="icon-button" aria-label="全屏阅读" onClick={() => void fullscreen().catch(cause => setError(String(cause)))}><Maximize size={16} /></button>
      </div>
    </div>
    {findOpen && <div className="reader-find" role="search" aria-label="PDF 文字查找"><Search size={15} /><input ref={findInput} aria-label="查找 PDF 中的文字" placeholder="查找 PDF 中的文字" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (!event.nativeEvent.isComposing && event.key === 'Enter') { event.preventDefault(); moveHit(event.shiftKey ? -1 : 1); } }} /><span role="status">{searching ? '搜索中…' : !query.trim() ? '输入文字' : hits.length ? `${activeHit + 1} / ${hits.length}` : '无匹配'}</span><button className="icon-button" aria-label="上一个匹配" disabled={!hits.length || searching} onClick={() => moveHit(-1)}><ChevronLeft size={16} /></button><button className="icon-button" aria-label="下一个匹配" disabled={!hits.length || searching} onClick={() => moveHit(1)}><ChevronRight size={16} /></button><button className="icon-button" aria-label="关闭 PDF 查找" onClick={() => { setFindOpen(false); setHits([]); }}><X size={16} /></button>{searchError && <span className="error-text">{searchError}</span>}</div>}
    {(cropMode || areaNote) && <div className="crop-hint">{areaNote ? '拖动选择页面区域，松开后添加笔记。' : '在页面上拖动框选区域，松开后保存为图片。'}<button className="icon-button" aria-label="取消框选" onClick={() => { onCropMode(false); setAreaNote(false); }}><X size={15} /></button></div>}
    {location && !location.bbox && <div className="inline-notice">这项内容没有区域坐标，已定位到对应页。</div>}
    <ErrorMessage message={error || selectionError} />
    <div className="pdf-scroll" ref={scroll} onScroll={() => { schedulePosition(); setSelection(null); }}>
      {!pdf && !error && <Spinner label="正在打开原始 PDF…" />}
      {pdf && Array.from({ length: pdf.numPages }, (_, index) => <PdfPage key={`${paperId}-${index}`} pdf={pdf} index={index} scale={view.scale} rotation={view.rotation} register={register} onRasterReduced={rasterReduced}
        location={location?.page_index === index ? location : null} cropMode={!!cropMode || areaNote}
        onCrop={handlePageCrop} annotations={annotationsByPage.get(index) || EMPTY_PAGE_ANNOTATIONS} selectedAnnotationId={selectedAnnotationId}
        onAnnotationSelect={handleAnnotationSelect} hits={hitsByPage.get(index) || EMPTY_HITS} activeHitId={hits[activeHit]?.id} />)}
    </div>
    {!!reducedPages.size && <div className="reader-quality" role="status" title="为保持阅读流畅，当前大尺寸页面使用较低分辨率预览。文字选择和标注仍按原始 PDF 坐标定位。">大尺寸预览已降低清晰度</div>}
    {selection && <div className="reader-selection-tools" role="toolbar" aria-label="文本选区操作" style={{ left: selectionLeft, top: selectionTop }} onPointerDown={event => event.preventDefault()}><button onClick={() => void annotate('highlight')}><Highlighter size={15} />高亮</button><button onClick={() => void annotate('note')}><MessageSquarePlus size={15} />笔记</button><button aria-label="取消文本选区" onClick={() => { setSelection(null); globalThis.getSelection()?.removeAllRanges(); }}><X size={14} /></button></div>}
  </section>;
}
