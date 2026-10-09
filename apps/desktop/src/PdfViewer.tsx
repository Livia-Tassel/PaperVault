import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Crop, Maximize, Minus, Plus, RotateCw, X } from 'lucide-react';
import { getDocument, GlobalWorkerOptions, TextLayer, type PDFDocumentProxy, type PDFPageProxy } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import 'pdfjs-dist/web/pdf_viewer.css';
import { request } from './api';
import { ErrorMessage, Spinner } from './ui';
import { toPdfBox, toViewportBox, normalizeBox, type Box } from './geometry';
import type { Location } from './types';

GlobalWorkerOptions.workerSrc = workerUrl;
interface PdfProps { paperId: string; location?: Location | null; onCrop: (location: Location) => void; cropMode?: boolean; onCropMode: (value: boolean) => void }
export function PdfViewer({ paperId, location, onCrop, cropMode, onCropMode }: PdfProps) {
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState('');
  const [scale, setScale] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [page, setPage] = useState(1);
  const [pageDraft, setPageDraft] = useState('1');
  const root = useRef<HTMLDivElement>(null);
  const scroll = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let disposed = false; let task: ReturnType<typeof getDocument> | undefined;
    const controller = new AbortController();
    setDocument(null); setError(''); setPage(1); setPageDraft('1');
    void request(`/papers/${paperId}/pdf`, { signal: controller.signal }).then(response => response.arrayBuffer()).then(data => {
      if (disposed) return;
      task = getDocument({ data: new Uint8Array(data), enableXfa: false, useSystemFonts: true,
        cMapUrl: '/pdfjs/cmaps/', cMapPacked: true, standardFontDataUrl: '/pdfjs/standard_fonts/', wasmUrl: '/pdfjs/wasm/' });
      return task.promise;
    }).then(pdf => { if (!disposed && pdf) setDocument(pdf); }).catch(e => { if (!disposed) setError(e instanceof Error ? e.message : String(e)); });
    return () => { disposed = true; controller.abort(); void task?.destroy(); };
  }, [paperId]);
  const jump = (target: number) => {
    const clamped = Math.min(document?.numPages || 1, Math.max(1, target || 1));
    setPage(clamped); setPageDraft(String(clamped));
    scroll.current?.querySelector(`[data-page="${clamped}"]`)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  };
  useEffect(() => { if (document && location) { const timer = setTimeout(() => jump(location.page_index + 1), 80); return () => clearTimeout(timer); } }, [document, location]); // eslint-disable-line react-hooks/exhaustive-deps
  const fullscreen = async () => { if (globalThis.document.fullscreenElement) await globalThis.document.exitFullscreen(); else await root.current?.requestFullscreen(); };
  return <section className={`pdf-reader ${cropMode ? 'is-cropping' : ''}`} ref={root} aria-label="PDF 阅读器">
    <div className="pdf-toolbar">
      <button className="icon-button" aria-label="上一页" disabled={page <= 1} onClick={() => jump(page - 1)}><ChevronLeft size={18} /></button>
      <form onSubmit={e => { e.preventDefault(); jump(Number(pageDraft)); }}><input aria-label="PDF 页码" className="page-input" value={pageDraft} onChange={e => setPageDraft(e.target.value)} /><span className="muted"> / {document?.numPages || '—'}</span></form>
      <button className="icon-button" aria-label="下一页" disabled={!document || page >= document.numPages} onClick={() => jump(page + 1)}><ChevronRight size={18} /></button><span className="toolbar-divider" />
      <button className="icon-button" aria-label="缩小" disabled={scale <= 0.4} onClick={() => setScale(s => Math.max(.4, s - .15))}><Minus size={17} /></button>
      <button className="zoom-label" title="恢复 100%" onClick={() => setScale(1)}>{Math.round(scale * 100)}%</button>
      <button className="icon-button" aria-label="放大" disabled={scale >= 3} onClick={() => setScale(s => Math.min(3, s + .15))}><Plus size={17} /></button>
      <button className="icon-button" aria-label="旋转 PDF" onClick={() => setRotation(r => (r + 90) % 360)}><RotateCw size={16} /></button>
      <span className="toolbar-spacer" /><button className={`icon-button ${cropMode ? 'active' : ''}`} aria-label="框选图片区域" title="框选 PDF 区域，创建图片资源" onClick={() => onCropMode(!cropMode)}><Crop size={17} /></button>
      <button className="icon-button" aria-label="全屏阅读" onClick={() => void fullscreen()}><Maximize size={16} /></button>
    </div>
    {cropMode && <div className="crop-hint">在页面上拖动框选区域，松开后保存为图片。<button className="icon-button" aria-label="取消框选" onClick={() => onCropMode(false)}><X size={15} /></button></div>}
    {location && !location.bbox && <div className="inline-notice">这项资源没有区域坐标，已定位到对应页。</div>}
    <ErrorMessage message={error} />
    <div className="pdf-scroll" ref={scroll}>
      {!document && !error && <Spinner label="正在打开原始 PDF…" />}
      {document && Array.from({ length: document.numPages }, (_, index) => <PdfPage key={index} pdf={document} index={index} scale={scale} rotation={rotation} location={location?.page_index === index ? location : null} cropMode={!!cropMode} onCrop={onCrop} onVisible={() => { setPage(index + 1); setPageDraft(String(index + 1)); }} />)}
    </div>
  </section>;
}

function PdfPage({ pdf, index, scale, rotation, location, cropMode, onCrop, onVisible }: { pdf: PDFDocumentProxy; index: number; scale: number; rotation: number; location?: Location | null; cropMode: boolean; onCrop: (location: Location) => void; onVisible: () => void }) {
  const [page, setPage] = useState<PDFPageProxy | null>(null);
  const [near, setNear] = useState(index === 0);
  const [error, setError] = useState('');
  const [selection, setSelection] = useState<Box | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const text = useRef<HTMLDivElement>(null);
  const highlight = useRef<HTMLDivElement>(null);
  const drag = useRef<[number, number] | null>(null);
  const visibleCallback = useRef(onVisible); visibleCallback.current = onVisible;
  useEffect(() => { let disposed = false; void pdf.getPage(index + 1).then(value => { if (!disposed) setPage(value); }).catch(e => { if (!disposed) setError(String(e)); }); return () => { disposed = true; }; }, [pdf, index]);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => { setNear(entries[0].isIntersecting); }, { rootMargin: '800px 0px' });
    const active = new IntersectionObserver(entries => { if (entries[0].isIntersecting) visibleCallback.current(); }, { threshold: .25 });
    if (box.current) { observer.observe(box.current); active.observe(box.current); }
    return () => { observer.disconnect(); active.disconnect(); };
  }, []);
  const viewport = page?.getViewport({ scale, rotation: ((page.rotate || 0) + rotation) % 360 });
  useEffect(() => {
    if (!page || !near || !canvas.current || !text.current) return;
    const vp = page.getViewport({ scale, rotation: ((page.rotate || 0) + rotation) % 360 });
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    const node = canvas.current; node.width = Math.ceil(vp.width * pixelRatio); node.height = Math.ceil(vp.height * pixelRatio);
    const context = node.getContext('2d'); if (!context) return;
    const render = page.render({ canvas: node, canvasContext: context, viewport: vp, transform: [pixelRatio, 0, 0, pixelRatio, 0, 0] });
    const textNode = text.current; textNode.replaceChildren();
    textNode.style.setProperty('--scale-factor', String(scale));
    const layer = new TextLayer({ textContentSource: page.streamTextContent(), container: textNode, viewport: vp });
    let cancelled = false;
    void Promise.all([render.promise, layer.render()]).catch(e => { if (!cancelled && e?.name !== 'RenderingCancelledException' && e?.name !== 'AbortException') setError(String(e)); });
    return () => { cancelled = true; render.cancel(); layer.cancel(); textNode.replaceChildren(); node.width = 0; node.height = 0; };
  }, [page, near, scale, rotation]);
  useEffect(() => { if (location?.bbox && near) { const timer = setTimeout(() => highlight.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 200); return () => clearTimeout(timer); } }, [location, near]);
  const rect = location?.bbox && viewport ? toViewportBox(location.bbox, viewport) : null;
  const point = (event: React.PointerEvent) => { const bounds = box.current!.getBoundingClientRect(); return [Math.max(0, Math.min(bounds.width, event.clientX - bounds.left)), Math.max(0, Math.min(bounds.height, event.clientY - bounds.top))] as [number, number]; };
  const styleBox = (b: Box) => ({ left: b[0], top: b[1], width: b[2] - b[0], height: b[3] - b[1] });
  return <div className="pdf-page-wrap"><div data-page={index + 1} className="pdf-page" ref={box} style={{ width: viewport?.width || 612 * scale, height: viewport?.height || 792 * scale }}
    onPointerDown={event => { if (!cropMode || !viewport) return; event.preventDefault(); box.current?.setPointerCapture(event.pointerId); const p = point(event); drag.current = p; setSelection([p[0], p[1], p[0], p[1]]); }}
    onPointerMove={event => { if (!drag.current) return; const p = point(event); setSelection(normalizeBox([...drag.current, ...p] as Box)); }}
    onPointerCancel={() => { drag.current = null; setSelection(null); }}
    onPointerUp={event => { if (!drag.current || !viewport) return; const p = point(event); const selected = normalizeBox([...drag.current, ...p] as Box); drag.current = null; setSelection(null); if (selected[2] - selected[0] >= 5 && selected[3] - selected[1] >= 5) onCrop({ page_index: index, bbox: toPdfBox(selected, viewport) }); }}>
    {error ? <ErrorMessage message={error} /> : <><canvas ref={canvas} style={{ width: viewport?.width, height: viewport?.height }} /><div ref={text} className="textLayer" />{rect && <div ref={highlight} className="pdf-highlight" style={styleBox(rect)} aria-label="资源所在区域" />}{selection && <div className="pdf-selection" style={styleBox(selection)} />}</>}
  </div><span className="page-number">{index + 1}</span></div>;
}
