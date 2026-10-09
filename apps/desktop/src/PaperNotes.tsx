import { useEffect, useState } from 'react';
import { ArrowLeft, Bookmark, Download, Highlighter, Plus, Search, StickyNote, Trash2 } from 'lucide-react';
import { api } from './api';
import { exportAnnotations } from './annotation-api';
import { AnnotationEditor, annotationPages } from './AnnotationEditor';
import { annotationLabels, type Annotation, type AnnotationKind } from './reading';
import type { Run } from './ResourceDetail';
import type { Paged } from './types';
import { Empty, ErrorMessage, Pager, Spinner, Tags } from './ui';

export function usePaperAnnotations(paperId: string, revision: number, libraryKey: string) {
  const [snapshot, setSnapshot] = useState<{ key: string; items: Annotation[]; loading: boolean; error: string }>({ key: '', items: [], loading: true, error: '' });
  const key = JSON.stringify([paperId, libraryKey]);
  useEffect(() => {
    const controller = new AbortController();
    setSnapshot(current => ({ key, items: current.key === key ? current.items : [], loading: true, error: '' }));
    void (async () => {
      const items: Annotation[] = [];
      let offset = 0;
      while (!controller.signal.aborted) {
        const next = await api<Paged<Annotation>>(`/annotations?paper_id=${encodeURIComponent(paperId)}&limit=200&offset=${offset}`, { signal: controller.signal });
        items.push(...next.items); offset += next.items.length;
        if (!next.items.length || offset >= next.total) break;
      }
      if (!controller.signal.aborted) setSnapshot({ key, items: [...new Map(items.map(item => [item.id, item])).values()], loading: false, error: '' });
    })().catch(reason => {
      if (!controller.signal.aborted) setSnapshot(current => ({ ...current, loading: false, error: reason instanceof Error ? reason.message : String(reason) }));
    });
    return () => controller.abort();
  }, [paperId, revision, key]);
  return snapshot.key === key ? snapshot : { key, items: [], loading: true, error: '' };
}

export function PaperNotes({ paperId, annotations, loading, error, selectedId, onSelect, onLocate, onCreate, onRemove, run, onChanged }: {
  paperId: string; annotations: Annotation[]; loading: boolean; error: string; selectedId: string | null;
  onSelect: (id: string | null) => void; onLocate: (annotation: Annotation) => void;
  onCreate: () => void; onRemove: (annotation: Annotation) => void; run: Run; onChanged: () => void;
}) {
  const [input, setInput] = useState(''); const [kind, setKind] = useState<AnnotationKind | ''>('');
  const [offset, setOffset] = useState(0);
  const selected = annotations.find(annotation => annotation.id === selectedId);
  const filtered = annotations.filter(annotation => (!kind || annotation.kind === kind) &&
    (!input.trim() || [annotation.title, annotation.quote, annotation.body, ...annotation.tags].join('\n').toLocaleLowerCase().includes(input.trim().toLocaleLowerCase())));
  const icons = { bookmark: Bookmark, highlight: Highlighter, note: StickyNote };
  if (selected) return <div className="paper-notes"><div className="annotation-panel-toolbar"><button className="text-button" onClick={() => onSelect(null)}><ArrowLeft size={14} />全部笔记</button><span className="toolbar-spacer" /><button className="icon-button" aria-label="删除当前笔记" onClick={() => onRemove(selected)}><Trash2 size={15} /></button></div>
    <AnnotationEditor key={selected.id} annotation={selected} paperId={paperId} guardId={`annotation:${selected.id}`} run={run}
      onSaved={onChanged} onLocate={onLocate} />
  </div>;
  return <div className="paper-notes"><div className="annotation-panel-toolbar"><span className="muted">{annotations.length} 条记录</span><span className="toolbar-spacer" />
    <button className="icon-button" aria-label="导出本篇笔记 Markdown" title="导出本篇笔记 Markdown" onClick={() => void run(() => exportAnnotations('markdown', [], paperId), '笔记已导出')}><Download size={15} /></button>
    <button className="button secondary small" onClick={onCreate}><Plus size={14} />笔记</button></div>
    <div className="search-input"><Search size={14} /><input aria-label="搜索本篇笔记" placeholder="查找笔记" value={input} onChange={event => { setInput(event.target.value); setOffset(0); }} /></div>
    <div className="annotation-kind-filters" role="group" aria-label="本篇笔记类型">{[['', '全部'], ...Object.entries(annotationLabels)].map(([value, label]) => <button key={value} className={kind === value ? 'active' : ''} onClick={() => { setKind(value as AnnotationKind | ''); setOffset(0); }}>{label}</button>)}</div>
    <ErrorMessage message={error} />{loading && !annotations.length && <Spinner />}
    {!loading && !filtered.length && <Empty title={annotations.length ? '没有匹配的笔记' : '暂无笔记'} action={<button className="button secondary small" onClick={onCreate}>新建笔记</button>} />}
    <div className="paper-note-list">{filtered.slice(offset, offset + 30).map(annotation => { const Icon = icons[annotation.kind]; return <button key={annotation.id} className="paper-note-item" onClick={() => onSelect(annotation.id)}>
      <div className="paper-note-heading"><span className={`annotation-kind color-${annotation.color}`}><Icon size={14} /></span><strong>{annotation.title || annotationLabels[annotation.kind]}</strong><span className="muted">{annotationPages(annotation)}</span></div>
      {annotation.quote && <blockquote>{annotation.quote}</blockquote>}{annotation.body && <p>{annotation.body}</p>}<Tags values={annotation.tags} />
    </button>; })}</div>
    <Pager total={filtered.length} offset={offset} limit={30} onChange={setOffset} />
  </div>;
}
