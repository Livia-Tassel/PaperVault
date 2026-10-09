import { useEffect, useState } from 'react';
import { Bookmark, Download, Highlighter, Plus, RotateCcw, Search, StickyNote, Trash2 } from 'lucide-react';
import { api, query } from './api';
import { exportAnnotations, removeAnnotation, restoreAnnotation } from './annotation-api';
import { AnnotationEditor, annotationPages } from './AnnotationEditor';
import { useEditGuard } from './EditGuard';
import { useData, useDebounce, useWorkspaceScroll } from './hooks';
import { PaperPicker } from './PaperPicker';
import { annotationLabels, type Annotation, type AnnotationKind } from './reading';
import type { Run } from './ResourceDetail';
import type { Paged } from './types';
import { Checkbox, Empty, ErrorMessage, Field, Modal, Pager, Spinner, Tags } from './ui';
import { useWorkspaceState } from './Workspace';
import './notes.css';

export const annotationIcons = { bookmark: Bookmark, highlight: Highlighter, note: StickyNote };

export function NotebookPage({ revision, onLocate, run, onChanged }: {
  revision: number; onLocate: (annotation: Annotation) => void; run: Run; onChanged: () => void;
}) {
  const [input, setInput] = useWorkspaceState('notes.query', ''); const q = useDebounce(input);
  const [kind, setKind] = useWorkspaceState<AnnotationKind | ''>('notes.kind', '');
  const [tag, setTag] = useWorkspaceState('notes.tag', ''); const tagQuery = useDebounce(tag);
  const [paper, setPaper] = useWorkspaceState<{ id: string; title: string } | null>('notes.paper', null);
  const [offset, setOffset] = useWorkspaceState('notes.offset', 0);
  const [deleted, setDeleted] = useWorkspaceState('notes.deleted', false);
  const [selected, setSelected] = useState<string[]>([]);
  const [editing, setEditing] = useState<Annotation | null>(null);
  const [creating, setCreating] = useState(false);
  const [newPaper, setNewPaper] = useState<{ id: string; title: string } | null>(null);
  const [removing, setRemoving] = useState<Annotation | null>(null);
  const [undo, setUndo] = useState<Annotation | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportScope, setExportScope] = useState('filtered');
  const [format, setFormat] = useState<'markdown' | 'json'>('markdown');
  const [exportBusy, setExportBusy] = useState(false);
  const [exportCount, setExportCount] = useState(0);
  const guard = useEditGuard();
  const filters = { q: deleted ? '' : q, paper_id: paper?.id, kind, tag: tagQuery, deleted };
  const { data, error, loading } = useData<Paged<Annotation>>(`/annotations${query({ ...filters, offset, limit: 30 })}`, revision);
  useWorkspaceScroll(`notes:${JSON.stringify(filters)}:${offset}`, !!data);
  const items = data?.items || [];
  useEffect(() => { setSelected([]); }, [q, kind, tagQuery, paper?.id, deleted, offset]);
  const changeFilters = (action: () => void) => { action(); setOffset(0); };
  const toggle = (id: string) => setSelected(values => values.includes(id) ? values.filter(value => value !== id) : [...values, id]);
  const remove = async () => {
    if (!removing) return;
    const ok = await run(async () => { setUndo(await removeAnnotation(removing)); }, '笔记已删除');
    if (ok) { if (editing?.id === removing.id) setEditing(null); setRemoving(null); setSelected([]); onChanged(); }
  };
  const restore = async (annotation: Annotation) => {
    const ok = await run(() => restoreAnnotation(annotation), '笔记已恢复');
    if (ok) { setUndo(null); onChanged(); } return ok;
  };
  const doExport = async () => {
    setExportBusy(true); setExportCount(0);
    const ok = await run(async () => {
      let ids = exportScope === 'selected' ? selected : [];
      if (exportScope === 'filtered') {
        ids = [];
        for (let nextOffset = 0; ;) {
          const page = await api<Paged<Annotation>>(`/annotations${query({ ...filters, deleted: false, offset: nextOffset, limit: 200 })}`);
          if (page.total > 10000) throw new Error('筛选结果超过 10,000 条，请缩小范围后导出。');
          ids.push(...page.items.map(item => item.id)); setExportCount(ids.length);
          nextOffset += page.items.length;
          if (!page.items.length || nextOffset >= page.total) break;
        }
        if (!ids.length) throw new Error('当前筛选没有可导出的笔记。');
      }
      return await exportAnnotations(format, ids);
    }, '笔记已导出');
    setExportBusy(false); if (ok) setExporting(false);
  };
  return <>
    <div className="collection-toolbar notebook-toolbar"><div className="search-input"><Search size={16} /><input aria-label="搜索笔记" placeholder={deleted ? '已删除的笔记' : '搜索摘录、笔记或标签'} value={deleted ? '' : input} disabled={deleted} title={deleted ? '已删除的笔记不参与全文检索' : undefined} onChange={event => changeFilters(() => setInput(event.target.value))} /></div>
      <select aria-label="笔记类型" value={kind} onChange={event => changeFilters(() => setKind(event.target.value as AnnotationKind | ''))}><option value="">全部类型</option>{Object.entries(annotationLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>
      <PaperPicker value={paper} onChange={value => changeFilters(() => setPaper(value))} />
      <input className="filter-input" aria-label="筛选笔记标签" placeholder="标签" value={tag} onChange={event => changeFilters(() => setTag(event.target.value))} />
      <button className={`icon-button ${deleted ? 'active' : ''}`} aria-label={deleted ? '返回全部笔记' : '查看已删除笔记'} title={deleted ? '返回全部笔记' : '已删除笔记'} onClick={() => changeFilters(() => setDeleted(!deleted))}><Trash2 size={16} /></button>
      {!deleted && <><button className="button secondary" onClick={() => { setExportScope(selected.length ? 'selected' : 'filtered'); setExporting(true); }}><Download size={15} />导出</button><button className="button primary" onClick={() => { setNewPaper(paper); setCreating(true); }}><Plus size={15} />新建笔记</button></>}
    </div>
    <div className="collection-subline"><span>{deleted ? '已删除' : '全部记录'} · {data?.total || 0} 条{selected.length ? ` · 已选 ${selected.length} 条` : ''}</span>
      {!!items.length && !deleted && <button className="text-button" onClick={() => setSelected(items.every(item => selected.includes(item.id)) ? [] : items.map(item => item.id))}>{items.every(item => selected.includes(item.id)) ? '取消本页选择' : '选择本页全部'}</button>}
    </div>
    {undo && <div className="annotation-undo" role="status"><span>{annotationLabels[undo.kind]}已删除</span><button className="text-button" onClick={() => void restore(undo)}><RotateCcw size={13} />撤销</button><button className="icon-button" aria-label="关闭撤销提示" onClick={() => setUndo(null)}>×</button></div>}
    <ErrorMessage message={error} />{loading && !data && <Spinner />}
    {!loading && !error && !items.length && <Empty title={deleted ? '没有已删除的笔记' : q || tag || kind || paper ? '没有匹配的笔记' : '暂无笔记'} action={!deleted ? <button className="button secondary" onClick={() => { setNewPaper(paper); setCreating(true); }}>新建笔记</button> : undefined} />}
    <div className="annotation-list">{items.map(annotation => {
      const Icon = annotationIcons[annotation.kind];
      return <article key={annotation.id} className={`annotation-row ${deleted ? 'is-deleted' : ''} ${selected.includes(annotation.id) ? 'is-selected' : ''}`}>
        {!deleted && <Checkbox label={`选择笔记 ${annotation.title || annotation.id}`} checked={selected.includes(annotation.id)} onChange={() => toggle(annotation.id)} />}
        <span className={`annotation-kind color-${annotation.color}`} title={annotationLabels[annotation.kind]}><Icon size={16} /></span>
        <button data-workspace-focus={`note:${annotation.id}`} className="annotation-open" onClick={() => setEditing(annotation)}><strong>{annotation.title || annotation.quote.slice(0, 100) || annotationLabels[annotation.kind]}</strong>
          {annotation.quote && <blockquote>{annotation.quote}</blockquote>}{annotation.body && <p>{annotation.body}</p>}
          <div className="annotation-row-meta"><span>{annotation.paper_title}</span><span>{annotationPages(annotation)}</span><time dateTime={annotation.updated_at}>{new Date(annotation.updated_at).toLocaleDateString('zh-CN')}</time></div><Tags values={annotation.tags} />
        </button>
        <div className="annotation-row-actions">{deleted ? <button className="button secondary small" onClick={() => void restore(annotation)}>恢复</button> : <><button className="text-button" onClick={() => onLocate(annotation)}>原文</button><button className="icon-button" aria-label={`删除笔记 ${annotation.title || annotation.id}`} onClick={() => setRemoving(annotation)}><Trash2 size={15} /></button></>}</div>
      </article>;
    })}</div>
    <Pager total={data?.total || 0} offset={offset} limit={30} onChange={setOffset} />
    {editing && <Modal title={editing.deleted ? '已删除的笔记' : '编辑笔记'} onClose={() => { void guard.attempt(() => setEditing(null), [`annotation:${editing.id}`]); }}>
      <button className="source-paper" onClick={() => onLocate(editing)}>{editing.paper_title}</button>
      {editing.deleted ? <><blockquote className="annotation-quote">{editing.quote}</blockquote><p className="annotation-body">{editing.body}</p><button className="button primary" onClick={() => void restore(editing).then(ok => { if (ok) setEditing(null); })}>恢复笔记</button></> :
        <AnnotationEditor key={editing.id} paperId={editing.paper_id} annotation={editing} guardId={`annotation:${editing.id}`} priority={120} run={run}
          onSaved={next => { setEditing(next); onChanged(); }} onLocate={onLocate} />}
    </Modal>}
    {creating && <Modal title="新建笔记" onClose={() => { void guard.attempt(() => setCreating(false), ['annotation:new-notebook']); }}>
      <Field label="来源论文"><PaperPicker label="选择来源论文" value={newPaper} onChange={value => { void guard.attempt(() => setNewPaper(value), ['annotation:new-notebook']); }} /></Field>
      {newPaper && <AnnotationEditor key={newPaper.id} paperId={newPaper.id} guardId="annotation:new-notebook" priority={120} run={run}
        onSaved={next => { setCreating(false); setEditing(next); onChanged(); }} />}
    </Modal>}
    {removing && <Modal title="删除笔记" onClose={() => setRemoving(null)}><p className="dialog-description">删除“{removing.title || annotationLabels[removing.kind]}”？可在已删除列表中恢复。</p><div className="modal-footer"><button className="button secondary" onClick={() => setRemoving(null)}>取消</button><button className="button danger-button" onClick={() => void remove()}>删除笔记</button></div></Modal>}
    {exporting && <Modal title="导出笔记" onClose={() => { if (!exportBusy) setExporting(false); }}><Field label="导出范围"><select value={exportScope} disabled={exportBusy} onChange={event => setExportScope(event.target.value)}>{!!selected.length && <option value="selected">所选 {selected.length} 条</option>}<option value="filtered">当前筛选 · {data?.total || 0} 条</option><option value="all">全库笔记</option></select></Field><Field label="笔记导出格式"><select value={format} disabled={exportBusy} onChange={event => setFormat(event.target.value as 'markdown' | 'json')}><option value="markdown">Markdown</option><option value="json">JSON</option></select></Field>{exportBusy && exportCount > 0 && <p className="muted">已读取 {exportCount} 条</p>}<div className="modal-footer"><button className="button primary" disabled={exportBusy} onClick={() => void doExport()}>{exportBusy ? '正在导出…' : '导出笔记'}</button></div></Modal>}
  </>;
}
