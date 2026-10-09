import { useEffect, useId, useRef, useState } from 'react';
import { ArrowLeft, Download, FileText, PanelRightClose, PanelRightOpen, Plus, RefreshCw, RotateCcw, Save, Star, Trash2 } from 'lucide-react';
import { api, exportAssets, updatePaper, post } from './api';
import { createAnnotation, removeAnnotation, restoreAnnotation } from './annotation-api';
import { AnnotationEditor } from './AnnotationEditor';
import { changedFields, mergeUntouchedFields } from './edits';
import { useDraftGuard, useEditGuard } from './EditGuard';
import { useData } from './hooks';
import { PaperNotes, usePaperAnnotations } from './PaperNotes';
import { PdfViewer } from './PdfViewer';
import { readingStatusLabels, type Annotation, type AnnotationSelection, type ReadingStatus, type ReadingState } from './reading';
import { AssetImage, Empty, ErrorMessage, Field, Modal, Pager, Spinner, Status, Warnings, filename, splitTags } from './ui';
import { useReadingState } from './useReadingState';
import { handleTabKeys } from './tabs';
import type { Run } from './ResourceDetail';
import type { Folder, Location, Paged, Paper, Resource } from './types';
import './notes.css';

export function PaperDetail({ id, revision, location, cropMode, onCropMode, onCrop, onBack, onResource, onLocation, onRelated, run, onChanged, libraryKey = '', onTitleChange, selectedAnnotationId }: {
  id: string; revision: number; location?: Location | null; cropMode: boolean; onCropMode: (value: boolean) => void;
  onCrop: (location: Location) => void; onBack: () => void; onResource: (id: string) => void;
  onLocation: (location: Location) => void; onRelated: (id: string) => void; run: Run; onChanged: () => void;
  libraryKey?: string; onTitleChange?: (id: string, title: string) => void; selectedAnnotationId?: string | null;
}) {
  const { data: paper, error } = useData<Paper>(`/papers/${id}`, revision, 5000, libraryKey);
  const [tab, setTab] = useState('info');
  const tabId = useId();
  const [readerReset, setReaderReset] = useState(0);
  const [adoptedReading, setAdoptedReading] = useState<ReadingState | null>(null);
  const ignoredLocation = useRef<Location | null | undefined>(undefined);
  const [resourceOffset, setResourceOffset] = useState(0);
  const [selectedNote, setSelectedNote] = useState<string | null>(selectedAnnotationId || null);
  const [creating, setCreating] = useState<AnnotationSelection | null>(null);
  const [removing, setRemoving] = useState<Annotation | null>(null);
  const [undo, setUndo] = useState<Annotation | null>(null);
  const [sideWidth, setSideWidth] = useState(() => Math.min(620, Math.max(300, Number(localStorage.getItem('papervault-reader-width')) || 380)));
  const [sideCollapsed, setSideCollapsed] = useState(localStorage.getItem('papervault-reader-collapsed') === 'true');
  const dividerDrag = useRef<{ x: number; width: number } | null>(null);
  const split = useRef<HTMLDivElement>(null);
  const guard = useEditGuard();
  const reading = useReadingState(id, libraryKey, onChanged);
  const annotations = usePaperAnnotations(id, revision, libraryKey);
  const resourceKind = tab === 'figures' ? 'figure' : tab === 'tables' ? 'table' : null;
  const { data: resources, loading: resourceLoading, error: resourceError } = useData<Paged<Resource>>(resourceKind ? `/resources?paper_id=${id}&kind=${resourceKind}&limit=24&offset=${resourceOffset}` : null, revision, 5000, libraryKey);
  useEffect(() => { setResourceOffset(0); setTab(selectedAnnotationId ? 'notes' : 'info'); setSelectedNote(selectedAnnotationId || null); setCreating(null); setUndo(null); }, [id]);
  useEffect(() => { if (selectedAnnotationId) { setSelectedNote(selectedAnnotationId); setTab('notes'); setSideCollapsed(false); } }, [selectedAnnotationId]);
  useEffect(() => { if (paper && paper.id === id) onTitleChange?.(id, paper.title || paper.filename); }, [paper, id, onTitleChange]);
  useEffect(() => { localStorage.setItem('papervault-reader-width', String(sideWidth)); }, [sideWidth]);
  useEffect(() => { localStorage.setItem('papervault-reader-collapsed', String(sideCollapsed)); }, [sideCollapsed]);
  const clampWidth = (value: number) => Math.min(Math.max(300, Math.min(620, (split.current?.clientWidth || 1000) - 350)), Math.max(300, value));
  const adoptReading = () => {
    const saved = reading.queue?.conflict;
    if (!saved || !reading.queue?.discard()) return;
    ignoredLocation.current = location;
    setAdoptedReading(saved); setReaderReset(value => value + 1);
  };
  const selectNote = (noteId: string | null) => { void guard.attempt(() => { setSelectedNote(noteId); setTab('notes'); setSideCollapsed(false); }); };
  const locateNote = (annotation: Annotation) => { if (annotation.locations[0]) onLocation({ ...annotation.locations[0] }); setSelectedNote(annotation.id); };
  const annotate = (selection: AnnotationSelection) => {
    if (selection.kind !== 'highlight') { setCreating(selection); return; }
    void run(async () => {
      const created = await createAnnotation(id, 'highlight', { title: '', body: '', quote: selection.quote, color: 'amber', tags: [], locations: selection.locations });
      setSelectedNote(created.id); onChanged();
    }, '高亮已添加');
  };
  const bookmark = (pageIndex: number) => {
    const existing = annotations.items.find(item => item.kind === 'bookmark' && item.locations[0]?.page_index === pageIndex);
    const change = async () => {
      await run(async () => {
        if (existing) {
          const latest = await api<Annotation>(`/annotations/${existing.id}`);
          setUndo(await removeAnnotation(latest)); if (selectedNote === existing.id) setSelectedNote(null);
        } else {
          const created = await createAnnotation(id, 'bookmark', { title: `第 ${pageIndex + 1} 页`, quote: '', body: '', color: 'amber', tags: [], locations: [{ page_index: pageIndex, bbox: null }] });
          setSelectedNote(created.id);
        }
        onChanged();
      }, existing ? '书签已移除' : '书签已添加');
    };
    if (existing) void guard.attempt(change, [`annotation:${existing.id}`]); else void change();
  };
  const exportPaper = () => guard.attempt(async () => {
    await run(async () => {
      const latest = await api<Paper>(`/papers/${id}`);
      return exportAssets({ paper_ids: [id], resource_ids: [], format: 'zip', dpi: 300 }, `${filename(latest.title || latest.filename, 'paper')}.zip`);
    }, '论文资源已导出');
  });

  const remove = async () => {
    if (!removing) return;
    const ok = await run(async () => { setUndo(await removeAnnotation(removing)); }, '笔记已删除');
    if (ok) { setSelectedNote(null); setRemoving(null); onChanged(); }
  };
  const restore = async () => {
    if (!undo) return;
    const ok = await run(() => restoreAnnotation(undo), '记录已恢复');
    if (ok) { setUndo(null); onChanged(); }
  };
  const tabs = [['info', '论文信息'], ['notes', `笔记 ${annotations.items.length}`], ['figures', `图片 ${paper?.figure_count || 0}`], ['tables', `表格 ${paper?.table_count || 0}`], ['outline', '目录']];
  return <div className="paper-workspace">
    <header className="detail-topbar"><button className="icon-button" onClick={onBack} aria-label="返回论文库" title="返回工作区"><ArrowLeft size={19} /></button><div><h2>{paper?.title || paper?.filename || '正在打开论文…'}</h2></div><span className="toolbar-spacer" />
      {reading.state && <select className="reading-status-select" aria-label="阅读状态" value={reading.state.status} onChange={event => void reading.setStatus(event.target.value as ReadingStatus)}>{Object.entries(readingStatusLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select>}
      {paper && <><Status value={paper.status} /><button className={`icon-button ${paper.favorite ? 'favorited' : ''}`} aria-label="切换收藏" onClick={() => void run(() => updatePaper(id, { favorite: !paper.favorite })).then(ok => { if (ok) onChanged(); })}><Star size={18} fill={paper.favorite ? 'currentColor' : 'none'} /></button><button className="button secondary small" onClick={() => void exportPaper()}><Download size={15} />导出</button></>}
      <button className="icon-button" title={sideCollapsed ? '展开信息栏' : '收起信息栏'} aria-label={sideCollapsed ? '展开信息栏' : '收起信息栏'} aria-expanded={!sideCollapsed} onClick={() => { void guard.attempt(() => setSideCollapsed(value => !value)); }}>{sideCollapsed ? <PanelRightOpen size={18} /> : <PanelRightClose size={18} />}</button>
    </header>
    <ErrorMessage message={error} />
    {reading.error && <div className="reading-save-error" role="alert"><span>阅读位置未保存：{reading.error}</span>{reading.queue && <><button className="text-button" onClick={() => { void (reading.queue!.conflict ? reading.queue!.retryLocal() : reading.queue!.flush()); }}>{reading.queue.conflict ? '保存当前位置' : '重试'}</button>{reading.queue.conflict && <button className="text-button" onClick={adoptReading}>采用已保存记录</button>}</>}</div>}
    {undo && <div className="annotation-undo" role="status"><span>记录已删除</span><button className="text-button" onClick={() => void restore()}><RotateCcw size={13} />撤销</button><button className="icon-button" aria-label="关闭撤销提示" onClick={() => setUndo(null)}>×</button></div>}
    <div className="detail-split" ref={split}>
      {reading.initialState ? <PdfViewer key={`${libraryKey}:${id}:${readerReset}`} paperId={id} location={location === ignoredLocation.current ? null : location} cropMode={cropMode} onCropMode={onCropMode} onCrop={onCrop}
        initialState={adoptedReading || reading.initialState} onViewState={reading.onViewState} annotations={annotations.items} selectedAnnotationId={selectedNote}
        onAnnotationSelect={annotation => selectNote(annotation.id)} onAnnotate={annotate} onBookmark={bookmark} /> : !reading.error && <div className="reader-opening"><Spinner label="正在打开阅读记录…" /></div>}
      {!sideCollapsed && <>
        <div className="reader-divider" role="separator" tabIndex={0} aria-label="调整信息栏宽度" aria-orientation="vertical" aria-valuemin={300} aria-valuemax={620} aria-valuenow={Math.round(sideWidth)}
          onPointerDown={event => { event.preventDefault(); dividerDrag.current = { x: event.clientX, width: sideWidth }; event.currentTarget.setPointerCapture(event.pointerId); }}
          onPointerMove={event => { if (dividerDrag.current) setSideWidth(clampWidth(dividerDrag.current.width + dividerDrag.current.x - event.clientX)); }}
          onPointerUp={() => { dividerDrag.current = null; }} onPointerCancel={() => { dividerDrag.current = null; }} onDoubleClick={() => setSideWidth(380)}
          onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); setSideWidth(clampWidth(event.key === 'Home' ? 300 : event.key === 'End' ? 620 : sideWidth + (event.key === 'ArrowLeft' ? 20 : -20))); } }} />
        <aside className="paper-side reader-side" style={{ width: sideWidth }}><div className="detail-tabs" role="tablist" aria-label="论文面板" onKeyDown={handleTabKeys}>{tabs.map(([key, label]) => <button role="tab" id={`${tabId}-${key}`} aria-controls={`${tabId}-panel-${key}`} tabIndex={tab === key ? 0 : -1} aria-selected={tab === key} key={key} className={tab === key ? 'active' : ''} onClick={() => { void guard.attempt(() => { setTab(key); setResourceOffset(0); }); }}>{label}</button>)}</div><div className="paper-side-content" role="tabpanel" id={`${tabId}-panel-${tab}`} aria-labelledby={`${tabId}-${tab}`}>
          {!paper && !error && <Spinner />}{paper && <>{tab === 'info' && <PaperInfo key={id} paper={paper} onRelated={onRelated} run={run} onChanged={onChanged} />}
            {tab === 'notes' && <PaperNotes paperId={id} annotations={annotations.items} loading={annotations.loading} error={annotations.error} selectedId={selectedNote} onSelect={selectNote} onLocate={locateNote} onCreate={() => setCreating({ kind: 'note', quote: '', locations: [] })} onRemove={setRemoving} run={run} onChanged={onChanged} />}
            {(tab === 'figures' || tab === 'tables') && <div className="detail-resources"><ErrorMessage message={resourceError} />{resourceLoading && <Spinner />}<div className="muted">共 {resources?.total ?? 0} 项资源</div>{resources?.items.filter(resource => resource.kind === (tab === 'figures' ? 'figure' : 'table')).map(resource => <button className="detail-resource" key={resource.id} onClick={() => onResource(resource.id)}><div className="detail-resource-thumb"><AssetImage id={resource.id} thumbnail revision={revision} alt={resource.name} /></div><strong>{resource.name || resource.number || (resource.kind === 'figure' ? 'Figure' : 'Table')}</strong><p>{resource.caption || '无图注'}</p><span className="muted">{resource.locations?.[0] ? `第 ${resource.locations[0].page_index + 1} 页` : '位置未知'}</span></button>)}{!resourceLoading && !resourceError && !resources?.items.length && <Empty title="暂无资源" />}<Pager total={resources?.total || 0} offset={resourceOffset} limit={24} onChange={setResourceOffset} /></div>}
            {tab === 'outline' && <OutlinePanel key={id} paper={paper} onLocation={onLocation} run={run} onChanged={onChanged} />}
          </>}
        </div></aside>
      </>}
    </div>
    {creating && <Modal title={creating.quote ? '为摘录添加笔记' : creating.locations.length ? '区域笔记' : '新建笔记'} onClose={() => { void guard.attempt(() => setCreating(null), [`annotation:new:${id}`]); }}>
      <AnnotationEditor paperId={id} selection={creating} guardId={`annotation:new:${id}`} priority={120} run={run} onSaved={annotation => { setSelectedNote(annotation.id); setCreating(null); onChanged(); }} />
    </Modal>}
    {removing && <Modal title="删除笔记" onClose={() => setRemoving(null)}><p className="dialog-description">删除这条记录？删除后可撤销或从笔记回收列表恢复。</p><div className="modal-footer"><button className="button secondary" onClick={() => setRemoving(null)}>取消</button><button className="button danger-button" onClick={() => void remove()}>删除笔记</button></div></Modal>}
  </div>;
}
function paperDraft(p: Paper) {
  return { title: p.title || '', authors: (p.authors || []).join(', '), abstract: p.abstract || '', year: p.year?.toString() || '', venue: p.venue || '', doi: p.doi || '', arxiv_id: p.arxiv_id || '', keywords: (p.keywords || []).join(', '), tags: (p.tags || []).join(', '), notes: p.notes || '', folders: p.folders || [] };
}
function PaperInfo({ paper: p, onRelated, run, onChanged }: { paper: Paper; onRelated: (id: string) => void; run: Run; onChanged: () => void }) {
  const [draft, setDraft] = useState(() => paperDraft(p));
  const original = useRef(draft);
  useEffect(() => {
    const incoming = paperDraft(p);
    const baseline = original.current;
    // Capture the old baseline outside the updater: React StrictMode may invoke
    // an updater twice, so it must not mutate the baseline itself.
    setDraft(current => mergeUntouchedFields(baseline, current, incoming));
    original.current = incoming;
  }, [p]);
  const [saving, setSaving] = useState(false);
  const { data: folders } = useData<Paged<Folder>>('/folders');
  const set = (key: string, value: string) => setDraft(d => ({ ...d, [key]: value }));
  const normalize = (value: typeof draft) => ({ ...value, title: value.title || null, authors: splitTags(value.authors), year: value.year ? Number(value.year) : null, keywords: splitTags(value.keywords), tags: splitTags(value.tags) });
  const dirty = Object.keys(changedFields(normalize(original.current), normalize(draft))).length > 0;
  const save = async () => {
    if (saving) return false;
    setSaving(true);
    const sent = draft;
    const updates = changedFields(normalize(original.current), normalize(sent));
    const ok = await run(async () => {
      if (!Object.keys(updates).length) return;
      const saved = paperDraft(await updatePaper(p.id, updates));
      original.current = saved;
      setDraft(current => mergeUntouchedFields(sent, current, saved));
    }, '论文信息已保存');
    setSaving(false); if (ok) onChanged(); return ok;
  };
  useDraftGuard({ id: `paper:${p.id}`, label: '论文信息', dirty, onSave: save,
    onDiscard: () => setDraft({ ...original.current }), priority: 10 });

  return <div className="paper-info"><fieldset className="editor-fields" disabled={saving}><Warnings values={p.warnings} /><SimilarPapers papers={p.similar_papers} onOpen={onRelated} /><Field label="标题"><textarea rows={2} value={draft.title} onChange={e => set('title', e.target.value)} placeholder={p.filename} /></Field><Field label="作者（逗号分隔）"><input value={draft.authors} onChange={e => set('authors', e.target.value)} /></Field><div className="form-grid"><Field label="发表年份"><input type="number" min={1000} max={9999} value={draft.year} onChange={e => set('year', e.target.value)} /></Field><Field label="会议 / 期刊"><input value={draft.venue} onChange={e => set('venue', e.target.value)} /></Field></div><Field label="摘要"><textarea rows={5} value={draft.abstract} onChange={e => set('abstract', e.target.value)} /></Field><div className="form-grid"><Field label="DOI"><input value={draft.doi} onChange={e => set('doi', e.target.value)} /></Field><Field label="arXiv ID"><input value={draft.arxiv_id} onChange={e => set('arxiv_id', e.target.value)} /></Field></div><Field label="关键词"><input value={draft.keywords} onChange={e => set('keywords', e.target.value)} /></Field><Field label="自定义标签"><input value={draft.tags} onChange={e => set('tags', e.target.value)} placeholder="逗号分隔标签" /></Field>{folders?.items?.length ? <div className="field"><span>收藏夹</span><div className="folder-checks">{folders.items.map(f => <label key={f.id}><input type="checkbox" checked={draft.folders.includes(f.id)} onChange={e => setDraft(d => ({ ...d, folders: e.target.checked ? [...d.folders, f.id] : d.folders.filter(v => v !== f.id) }))} />{f.name}</label>)}</div></div> : null}<Field label="个人备注"><textarea rows={4} value={draft.notes} onChange={e => set('notes', e.target.value)} placeholder="备注" /></Field><button className="button primary" onClick={() => void save()} disabled={saving || !dirty}><Save size={16} />{saving ? '保存中…' : '保存修改'}</button><p className="draft-indicator">{dirty ? '未保存' : '已保存'}</p><div className="info-divider" /><div className="metadata-line"><span>原始文件</span><strong>{p.filename}</strong></div><div className="metadata-line"><span>导入时间</span><strong>{p.created_at ? new Date(p.created_at).toLocaleString('zh-CN') : '—'}</strong></div><button className="button secondary" onClick={() => void run(() => post(`/papers/${p.id}/reparse`), '已加入重新解析队列').then(ok => { if (ok) onChanged(); })}><RefreshCw size={15} />重新解析</button></fieldset></div>;
}

function SimilarPapers({ papers, onOpen }: { papers: Paper["similar_papers"]; onOpen: (id: string) => void }) { return papers?.length ? <div className="similar-papers"><strong>可能是同一论文的其他版本</strong>{papers.map(paper => <button key={paper.id} onClick={() => onOpen(paper.id)}>{paper.title || "未命名论文"}<small>{paper.reason}</small></button>)}</div> : null; }

type Section = Paper['sections'][number];
export function changeSectionPage(section: Section, pageIndex: number): Section {
  if ((section.location?.page_index ?? section.page_index ?? 0) === pageIndex) return section;
  // A box belongs to its original page. Moving a heading must not highlight an
  // unrelated region on the newly selected page.
  return { ...section, page_index: pageIndex, location: { ...section.location, page_index: pageIndex, bbox: null } };
}
export function outlineChanges(previousSections: Section[], nextSections: Section[], previousReferences: string[], referenceText: string) {
  const references = referenceText === previousReferences.join('\n')
    ? previousReferences
    : referenceText.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  return changedFields({ sections: previousSections, references: previousReferences }, { sections: nextSections, references });
}
function OutlinePanel({ paper, onLocation, run, onChanged }: { paper: Paper; onLocation: (location: Location) => void; run: Run; onChanged: () => void }) {
  const guard = useEditGuard();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sections, setSections] = useState<Section[]>([]);
  const [references, setReferences] = useState('');
  const baseline = useRef<{ sections: Section[]; references: string[] }>({ sections: [], references: [] });
  const pages = typeof paper.pages_count === 'number' ? paper.pages_count : undefined;
  const begin = () => {
    const currentSections = structuredClone(paper.sections || []);
    const currentReferences = (paper.references || []).map(reference => typeof reference === 'string' ? reference : reference.text);
    baseline.current = { sections: currentSections, references: currentReferences };
    setSections(currentSections); setReferences(currentReferences.join('\n')); setEditing(true);
  };
  const modify = (index: number, update: (section: Section) => Section) => setSections(values => values.map((section, i) => i === index ? update(section) : section));
  const save = async () => {
    const updates = outlineChanges(baseline.current.sections, sections, baseline.current.references, references);
    if (!Object.keys(updates).length) { setEditing(false); return true; }
    setSaving(true);
    const ok = await run(() => updatePaper(paper.id, updates), '章节与参考文献已保存');
    setSaving(false);
    if (ok) { baseline.current = { sections: structuredClone(sections), references: references.split(/\r?\n/).map(line => line.trim()).filter(Boolean) }; setEditing(false); onChanged(); }
    return ok;
  };
  const dirty = editing && Object.keys(outlineChanges(baseline.current.sections, sections, baseline.current.references, references)).length > 0;
  useDraftGuard({ id: `outline:${paper.id}`, label: '目录与参考文献', dirty, onSave: save, onDiscard: () => setEditing(false), priority: 20 });
  if (editing) return <div className="paper-info">
    <h3 style={{ fontSize: 14 }}>编辑目录与参考文献</h3>
    <p className="help-text">更改页码会清除原定位框。</p>
    {sections.map((section, index) => <fieldset key={index} style={{ border: 0, borderBottom: '1px solid var(--line)', padding: '8px 0', marginBottom: 8 }}>
      <legend style={{ fontSize: 11, color: 'var(--muted)', padding: '0 4px' }}>章节 {index + 1}</legend>
      <Field label={`章节 ${index + 1} 标题`}><input value={section.title ?? section.text ?? ''} onChange={event => modify(index, value => ({ ...value, title: event.target.value }))} /></Field>
      <div className="form-grid"><Field label={`章节 ${index + 1} 层级`}><input type="number" min={1} max={6} value={section.level || 1} onChange={event => modify(index, value => ({ ...value, level: Math.max(1, Math.min(6, Number(event.target.value) || 1)) }))} /></Field><Field label={`章节 ${index + 1} 页码`}><input type="number" min={1} max={pages} value={(section.location?.page_index ?? section.page_index ?? 0) + 1} onChange={event => modify(index, value => changeSectionPage(value, Math.max(1, Math.min(pages || Infinity, Number(event.target.value) || 1)) - 1))} /></Field></div>
      <button className="button secondary small danger" aria-label={`删除章节 ${index + 1}`} onClick={() => setSections(values => values.filter((_, i) => i !== index))}><Trash2 size={13} />删除此章节</button>
    </fieldset>)}
    <button className="button secondary small" onClick={() => setSections(values => [...values, { title: '', level: 1, page_index: 0, location: { page_index: 0, bbox: null } }])}><Plus size={14} />添加章节</button>
    <div className="info-divider" />
    <Field label="参考文献（每行一条）"><textarea rows={10} value={references} onChange={event => setReferences(event.target.value)} placeholder="每行一条" /></Field>
    <div className="inline-form"><button className="button secondary" disabled={saving} onClick={() => { void guard.attempt(() => setEditing(false), [`outline:${paper.id}`]); }}>取消编辑</button><button className="button primary" disabled={saving} onClick={() => void save()}><Save size={14} />{saving ? '保存中…' : '保存目录与参考文献'}</button></div>
  </div>;
  return <div><button className="button secondary small" onClick={begin}>编辑目录与参考文献</button><div className="outline" style={{ marginTop: 14, outline: 'none' }}>
    <h3>章节结构</h3>{paper.sections?.map((section, index) => <button key={index} style={{ paddingLeft: 12 + Math.min(section.level || 0, 4) * 10 }} onClick={() => onLocation(section.location || { page_index: section.page_index || 0 })}><FileText size={14} /><span>{section.title || section.text || `章节 ${index + 1}`}</span></button>)}
    {!paper.sections?.length && <p className="muted">暂无章节。</p>}
    <h3>参考文献</h3>{paper.references?.map((reference, index) => <p className="reference" key={index}><span>{index + 1}.</span>{typeof reference === 'string' ? reference : reference.text}</p>)}
    {!paper.references?.length && <p className="muted">暂无参考文献。</p>}
  </div></div>;
}
