import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Download, FileText, Plus, RefreshCw, Save, Star, Trash2 } from 'lucide-react';
import { exportAssets, updatePaper, post } from './api';
import { changedFields, mergeUntouchedFields } from './edits';
import { useData } from './hooks';
import { PdfViewer } from './PdfViewer';
import { AssetImage, Empty, ErrorMessage, Field, Pager, Spinner, Status, Warnings, filename, splitTags } from './ui';
import type { Run } from './ResourceDetail';
import type { Folder, Location, Paged, Paper, Resource } from './types';

export function PaperDetail({ id, revision, location, cropMode, onCropMode, onCrop, onBack, onResource, onLocation, onRelated, run, onChanged }: { id: string; revision: number; location?: Location | null; cropMode: boolean; onCropMode: (v: boolean) => void; onCrop: (l: Location) => void; onBack: () => void; onResource: (id: string) => void; onLocation: (l: Location) => void; onRelated: (id: string) => void; run: Run; onChanged: () => void }) {
  const { data: paper, error } = useData<Paper>(`/papers/${id}`, revision, 5000);
  const [tab, setTab] = useState('info');
  const [resourceOffset, setResourceOffset] = useState(0);
  const resourceKind = tab === 'figures' ? 'figure' : tab === 'tables' ? 'table' : null;
  const { data: resources, loading: resourceLoading, error: resourceError } = useData<Paged<Resource>>(resourceKind ? `/resources?paper_id=${id}&kind=${resourceKind}&limit=24&offset=${resourceOffset}` : null, revision, 5000);
  useEffect(() => { setResourceOffset(0); setTab('info'); }, [id]);
  return <div className="paper-workspace"><header className="detail-topbar"><button className="icon-button" onClick={onBack} aria-label="返回论文库"><ArrowLeft size={19} /></button><div><h2>{paper?.title || paper?.filename || '正在打开论文…'}</h2></div><span className="toolbar-spacer" />{paper && <><Status value={paper.status} /><button className={`icon-button ${paper.favorite ? 'favorited' : ''}`} aria-label="切换收藏" onClick={() => void run(() => updatePaper(id, { favorite: !paper.favorite })).then(ok => { if (ok) onChanged(); })}><Star size={18} fill={paper.favorite ? 'currentColor' : 'none'} /></button><button className="button secondary small" onClick={() => void run(() => exportAssets({ paper_ids: [id], resource_ids: [], format: 'zip', dpi: 300 }, `${filename(paper.title || paper.filename, 'paper')}.zip`), '论文资源已导出')}><Download size={15} />导出</button></>}</header>
    <ErrorMessage message={error} /><div className="detail-split"><PdfViewer paperId={id} location={location} cropMode={cropMode} onCropMode={onCropMode} onCrop={onCrop} /><aside className="paper-side"><div className="detail-tabs">{[['info', '论文信息'], ['figures', `图片 ${paper?.figure_count || 0}`], ['tables', `表格 ${paper?.table_count || 0}`], ['outline', '目录']].map(([key, label]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => { setTab(key); setResourceOffset(0); }}>{label}</button>)}</div><div className="paper-side-content">
      {!paper && !error && <Spinner />}{paper && <>{tab === 'info' && <PaperInfo key={id} paper={paper} onRelated={onRelated} run={run} onChanged={onChanged} />}{(tab === 'figures' || tab === 'tables') && <div className="detail-resources"><ErrorMessage message={resourceError} />{resourceLoading && <Spinner />}<div className="muted">共 {resources?.total ?? 0} 项资源，每页 24 项</div>{resources?.items.filter(r => r.kind === (tab === 'figures' ? 'figure' : 'table')).map(r => <button className="detail-resource" key={r.id} onClick={() => onResource(r.id)}><div className="detail-resource-thumb"><AssetImage id={r.id} thumbnail revision={revision} alt={r.name} /></div><strong>{r.name || r.number || (r.kind === 'figure' ? 'Figure' : 'Table')}</strong><p>{r.caption || '无图注'}</p><span className="muted">{r.locations?.[0] ? `第 ${r.locations[0].page_index + 1} 页` : '位置未知'}</span></button>)}{!resourceLoading && !resourceError && !resources?.items.some(r => r.kind === (tab === 'figures' ? 'figure' : 'table')) && <Empty title="暂无资源" />}<Pager total={resources?.total || 0} offset={resourceOffset} limit={24} onChange={setResourceOffset} /></div>}{tab === 'outline' && <OutlinePanel key={`${id}-${revision}`} paper={paper} onLocation={onLocation} run={run} onChanged={onChanged} />}</>}
    </div></aside></div>
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
  const save = async () => { setSaving(true); const normalize = (value: typeof draft) => ({ ...value, title: value.title || null, authors: splitTags(value.authors), year: value.year ? Number(value.year) : null, keywords: splitTags(value.keywords), tags: splitTags(value.tags) }); const next = normalize(draft), previous = normalize(original.current); const updates = changedFields(previous, next); const ok = await run(() => updatePaper(p.id, updates), '论文信息已保存'); setSaving(false); if (ok) onChanged(); };
  return <div className="paper-info"><Warnings values={p.warnings} /><SimilarPapers papers={p.similar_papers} onOpen={onRelated} /><Field label="标题"><textarea rows={2} value={draft.title} onChange={e => set('title', e.target.value)} placeholder={p.filename} /></Field><Field label="作者（逗号分隔）"><input value={draft.authors} onChange={e => set('authors', e.target.value)} /></Field><div className="form-grid"><Field label="发表年份"><input type="number" min={1000} max={9999} value={draft.year} onChange={e => set('year', e.target.value)} /></Field><Field label="会议 / 期刊"><input value={draft.venue} onChange={e => set('venue', e.target.value)} /></Field></div><Field label="摘要"><textarea rows={5} value={draft.abstract} onChange={e => set('abstract', e.target.value)} /></Field><div className="form-grid"><Field label="DOI"><input value={draft.doi} onChange={e => set('doi', e.target.value)} /></Field><Field label="arXiv ID"><input value={draft.arxiv_id} onChange={e => set('arxiv_id', e.target.value)} /></Field></div><Field label="关键词"><input value={draft.keywords} onChange={e => set('keywords', e.target.value)} /></Field><Field label="自定义标签"><input value={draft.tags} onChange={e => set('tags', e.target.value)} placeholder="逗号分隔标签" /></Field>{folders?.items?.length ? <div className="field"><span>收藏夹</span><div className="folder-checks">{folders.items.map(f => <label key={f.id}><input type="checkbox" checked={draft.folders.includes(f.id)} onChange={e => setDraft(d => ({ ...d, folders: e.target.checked ? [...d.folders, f.id] : d.folders.filter(v => v !== f.id) }))} />{f.name}</label>)}</div></div> : null}<Field label="个人备注"><textarea rows={4} value={draft.notes} onChange={e => set('notes', e.target.value)} placeholder="备注" /></Field><button className="button primary" onClick={() => void save()} disabled={saving}><Save size={16} />{saving ? '保存中…' : '保存修改'}</button><div className="info-divider" /><div className="metadata-line"><span>原始文件</span><strong>{p.filename}</strong></div><div className="metadata-line"><span>导入时间</span><strong>{p.created_at ? new Date(p.created_at).toLocaleString('zh-CN') : '—'}</strong></div><button className="button secondary" onClick={() => void run(() => post(`/papers/${p.id}/reparse`), '已加入重新解析队列').then(ok => { if (ok) onChanged(); })}><RefreshCw size={15} />重新解析</button></div>;
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
    if (!Object.keys(updates).length) { setEditing(false); return; }
    setSaving(true);
    const ok = await run(() => updatePaper(paper.id, updates), '章节与参考文献已保存');
    setSaving(false);
    if (ok) { setEditing(false); onChanged(); }
  };
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
    <div className="inline-form"><button className="button secondary" disabled={saving} onClick={() => setEditing(false)}>取消编辑</button><button className="button primary" disabled={saving} onClick={() => void save()}><Save size={14} />{saving ? '保存中…' : '保存目录与参考文献'}</button></div>
  </div>;
  return <div><button className="button secondary small" onClick={begin}>编辑目录与参考文献</button><div className="outline" style={{ marginTop: 14, outline: 'none' }}>
    <h3>章节结构</h3>{paper.sections?.map((section, index) => <button key={index} style={{ paddingLeft: 12 + Math.min(section.level || 0, 4) * 10 }} onClick={() => onLocation(section.location || { page_index: section.page_index || 0 })}><FileText size={14} /><span>{section.title || section.text || `章节 ${index + 1}`}</span></button>)}
    {!paper.sections?.length && <p className="muted">暂无章节。</p>}
    <h3>参考文献</h3>{paper.references?.map((reference, index) => <p className="reference" key={index}><span>{index + 1}.</span>{typeof reference === 'string' ? reference : reference.text}</p>)}
    {!paper.references?.length && <p className="muted">暂无参考文献。</p>}
  </div></div>;
}
