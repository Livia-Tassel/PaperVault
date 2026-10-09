import { useState } from 'react';
import { Copy, Crop, Download, ExternalLink, Image, Plus, Save, Trash2 } from 'lucide-react';
import { copyImage, copyText, download, updateResource } from './api';
import { useData } from './hooks';
import { changedFields } from './edits';
import { AssetImage, ErrorMessage, Field, Modal, Spinner, Warnings, filename, splitTags } from './ui';
import type { Resource, TableData } from './types';

export type Run = (operation: () => Promise<unknown>, success?: string) => Promise<boolean>;
export function ResourceDetail({ id, revision, onClose, onLocate, onCrop, run, onChanged }: { id: string; revision: number; onClose: () => void; onLocate: (resource: Resource) => void; onCrop: (resource: Resource) => void; run: Run; onChanged: () => void }) {
  const { data, error } = useData<Resource>(`/resources/${id}`, revision);
  return <Modal title={data ? (data.name || `${data.kind === 'figure' ? 'Figure' : 'Table'} ${data.number || ''}`) : '资源详情'} onClose={onClose} wide>
    <ErrorMessage message={error} />{!data && !error && <Spinner />}{data && <ResourceContent key={`${id}-${revision}`} resource={data} revision={revision} onLocate={onLocate} onCrop={onCrop} run={run} onChanged={onChanged} />}
  </Modal>;
}
function ResourceContent({ resource: r, revision, onLocate, onCrop, run, onChanged }: { resource: Resource; revision: number; onLocate: (resource: Resource) => void; onCrop: (resource: Resource) => void; run: Run; onChanged: () => void }) {
  const [name, setName] = useState(r.name || ''); const [caption, setCaption] = useState(r.caption || '');
  const [notes, setNotes] = useState(r.notes || ''); const [tags, setTags] = useState((r.tags || []).join(', '));
  const [table, setTable] = useState<TableData | null>(r.table); const [editing, setEditing] = useState(false);
  const [tableDirty, setTableDirty] = useState(false);
  const [dpi, setDpi] = useState(300); const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<'table' | 'image'>(r.kind === 'table' && r.table?.rows?.length ? 'table' : 'image');
  const save = async () => { setSaving(true); const values = { name, caption, notes, tags: splitTags(tags) }; const previous = { name: r.name || '', caption: r.caption || '', notes: r.notes || '', tags: r.tags || [] }; const updates = changedFields(previous, values); const ok = await run(() => updateResource(r.id, { ...updates, ...(tableDirty && table ? { table } : {}) }), '人工修改已保存'); setSaving(false); if (ok) { setEditing(false); onChanged(); } };
  const exportFile = async (format: string) => { await run(() => download(`/resources/${r.id}/files/${format}${format === 'png' ? `?dpi=${dpi}` : ''}`, `${filename(name || r.number, r.kind)}.${format}`), '资源已导出'); };
  return <div className="resource-detail">
    <div className="resource-main"><div className="resource-actions"><div className="segmented">{r.kind === 'table' && <button className={preview === 'table' ? 'selected' : ''} onClick={() => setPreview('table')}>表格内容</button>}<button className={preview === 'image' ? 'selected' : ''} onClick={() => setPreview('image')}><Image size={14} />原始截图</button></div><button className="button secondary small" onClick={() => onLocate(r)}><ExternalLink size={15} />查看原文</button></div>
      <div className={`resource-preview ${preview === 'table' ? 'table-preview' : ''}`}>{preview === 'table' ? table ? <TableEditor table={table} editable={editing} onChange={value => { setTable(value); setTableDirty(true); }} /> : <p className="muted">未识别到结构化单元格，请查看原始截图。</p> : <AssetImage id={r.id} revision={revision} alt={r.caption || r.name} />}</div>
      {r.kind === 'table' && <div className="table-edit-bar"><button className="button secondary small" disabled={!table} onClick={() => { setPreview('table'); setEditing(!editing); }}>{editing ? '结束编辑' : '编辑单元格 / 行列'}</button><span className="muted">CSV 不保留合并单元格。</span></div>}
      <Warnings values={[...(r.needs_review ? ['请对照原文校对。'] : []), ...(r.warnings || [])]} />
      <div className="export-bar"><select aria-label="图片导出分辨率" value={dpi} onChange={e => setDpi(Number(e.target.value))}><option value="150">150 DPI</option><option value="300">300 DPI</option><option value="600">600 DPI</option></select><button className="button secondary small" onClick={() => void exportFile('png')}><Download size={15} />PNG</button>{r.kind === 'table' && <><button className="button secondary small" onClick={() => void exportFile('csv')}><Download size={15} />CSV</button><button className="button secondary small" onClick={() => void exportFile('html')}><Download size={15} />HTML</button></>}<button className="button secondary small" onClick={() => void run(() => preview === 'table' && table ? copyText(table.rows.map(row => row.join('\t')).join('\n')) : copyImage(`/resources/${r.id}/files/png`), '已复制到剪贴板')}><Copy size={15} />复制{preview === 'table' ? '表格' : '图片'}</button><button className="button secondary small" onClick={() => onCrop(r)}><Crop size={15} />调整裁剪</button></div>
    </div>
    <aside className="resource-meta"><div className="muted">来源论文</div><button className="source-paper" onClick={() => onLocate(r)}>{r.paper_title || '查看原始论文'}<ExternalLink size={14} /></button><div className="source-location">{r.locations?.length ? r.locations.map(l => `第 ${l.page_index + 1} 页`).join('、') : '位置未知'}</div>
      <Field label="资源名称"><input value={name} onChange={e => setName(e.target.value)} /></Field><Field label="Caption"><textarea rows={4} value={caption} onChange={e => setCaption(e.target.value)} /></Field><Field label="标签（逗号分隔）"><input value={tags} onChange={e => setTags(e.target.value)} placeholder="架构图, 实验结果" /></Field><Field label="个人备注"><textarea rows={3} value={notes} onChange={e => setNotes(e.target.value)} placeholder="备注" /></Field><button className="button primary" disabled={saving} onClick={() => void save()}><Save size={16} />{saving ? '保存中…' : '保存人工修改'}</button>
    </aside>
  </div>;
}
export function TableEditor({ table, editable = false, onChange }: { table: TableData; editable?: boolean; onChange?: (table: TableData) => void }) {
  const rows = table.rows || [];
  const [selected, setSelected] = useState<[number, number]>([0, 0]);
  const columns = Math.max(1, ...rows.map(row => row.length));
  const cellMap = new Map((table.cells || []).filter(c => c.row !== undefined && c.col !== undefined).map(c => [`${c.row}:${c.col}`, c]));
  const occupied = new Set<string>();
  const update = (next: string[][], headers = table.header_rows || 0) => onChange?.({ ...table, rows: next, cells: [], num_rows: next.length, num_cols: Math.max(0, ...next.map(row => row.length)), header_rows: Math.min(headers, next.length) });
  return <div className="table-editor">{editable && <div className="table-editor-toolbar"><button className="button secondary small" onClick={() => update([...rows, Array(columns).fill('')])}><Plus size={13} />行</button><button className="button secondary small" onClick={() => update(rows.length ? rows.map(row => [...row, '']) : [['']])}><Plus size={13} />列</button><button className="button secondary small" disabled={rows.length <= 1} onClick={() => update(rows.filter((_, i) => i !== selected[0]))}><Trash2 size={13} />所选行</button><button className="button secondary small" disabled={columns <= 1} onClick={() => update(rows.map(row => row.filter((_, i) => i !== selected[1])))}><Trash2 size={13} />所选列</button><label>表头行数 <input aria-label="表头行数" type="number" min={0} max={rows.length} value={table.header_rows || 0} onChange={e => update(rows, Number(e.target.value))} /></label></div>}
    {editable && (table.cells || []).some(cell => (cell.row_span || 1) > 1 || (cell.col_span || 1) > 1) && <div className="inline-notice">修改后会展开合并单元格；原始 PDF 不变。</div>}
    <div className="table-scroll"><table><tbody>{rows.map((row, ri) => <tr key={ri}>{Array.from({ length: columns }, (_, ci) => { if (!editable && occupied.has(`${ri}:${ci}`)) return null; const cell = !editable ? cellMap.get(`${ri}:${ci}`) : undefined; const rowSpan = Math.max(1, Math.min(cell?.row_span || 1, rows.length - ri)); const colSpan = Math.max(1, Math.min(cell?.col_span || 1, columns - ci)); if (!editable) for (let rr = ri; rr < ri + rowSpan; rr++) for (let cc = ci; cc < ci + colSpan; cc++) occupied.add(`${rr}:${cc}`); const Tag = ri < (table.header_rows || 0) || cell?.is_header ? 'th' : 'td'; return <Tag key={ci} rowSpan={rowSpan} colSpan={colSpan} className={editable && selected[0] === ri && selected[1] === ci ? 'cell-selected' : ''}>{editable ? <input aria-label={`第 ${ri + 1} 行第 ${ci + 1} 列`} value={String(row[ci] ?? '')} onFocus={() => setSelected([ri, ci])} onChange={e => update(rows.map((r, i) => i === ri ? Array.from({ length: columns }, (_, j) => j === ci ? e.target.value : String(r[j] ?? '')) : [...r]))} /> : String(row[ci] ?? '')}</Tag>; })}</tr>)}</tbody></table>{!rows.length && <p className="muted">没有可显示的单元格。</p>}</div>
  </div>;
}
