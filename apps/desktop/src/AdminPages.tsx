import { useState } from 'react';
import { ArrowUpRight, Download, FolderOpen, RefreshCw, Search, Upload, X } from 'lucide-react';
import { chooseDirectory, native, post } from './api';
import { useData, useDebounce } from './hooks';
import { Empty, ErrorMessage, Field, Spinner, Status } from './ui';
import type { Run } from './ResourceDetail';
import type { Job, Library, ModelState, Paged, SearchHit, SearchResults } from './types';

export function SearchPage({ initialQuery = '', onResult }: { initialQuery?: string; onResult: (hit: SearchHit, kind: string) => void }) {
  const [input, setInput] = useState(initialQuery); const q = useDebounce(input, 300);
  const { data, loading, error } = useData<SearchResults>(q.trim() ? `/search?q=${encodeURIComponent(q)}` : null);
  const [group, setGroup] = useState('all');
  const groups = [['papers', '论文'], ['figures', '图片'], ['tables', '表格'], ['content', '正文']] as const;
  const total = data ? groups.reduce((sum, [key]) => sum + (data[key]?.length || 0), 0) : 0;
  return <><div className="global-search-box"><Search size={18} /><input id="global-search" autoFocus aria-label="全局全文搜索" value={input} onChange={e => setInput(e.target.value)} placeholder="搜索论文、图片、表格或正文" /><kbd>Ctrl K</kbd></div><div className="search-tabs"><button className={group === 'all' ? 'active' : ''} onClick={() => setGroup('all')}>全部 {data ? total : ''}</button>{groups.map(([key, label]) => <button className={group === key ? 'active' : ''} key={key} onClick={() => setGroup(key)}>{label} {data?.[key]?.length ?? ''}</button>)}</div><ErrorMessage message={error} />{loading && <Spinner label="搜索中…" />}{!q.trim() && <Empty title="输入关键词进行搜索" />}{q.trim() && data && total === 0 && !loading && <Empty title="未找到结果" />}{data && groups.filter(([key]) => group === 'all' || group === key).map(([key, label]) => !!data[key]?.length && <section className="search-group" key={key}><h3>{label}<span>{data[key].length}</span></h3>{data[key].map((hit, index) => <button className="search-result" key={`${hit.id}-${index}`} onClick={() => onResult(hit, key)}><div className="result-heading"><strong>{hit.title || hit.caption || hit.paper_title || (key === 'content' ? '正文片段' : '搜索结果')}</strong><ArrowUpRight size={16} /></div><p>{Array.isArray(hit.snippet) ? hit.snippet.map((part, i) => part.matched ? <mark key={i}>{part.text}</mark> : <span key={i}>{part.text}</span>) : hit.snippet || hit.text || hit.caption}</p><span className="muted">{hit.paper_title}{hit.location || hit.page_index !== undefined ? ` · 第 ${(hit.location?.page_index ?? hit.page_index ?? 0) + 1} 页` : ''}</span></button>)}</section>)}</>;
}

export function JobsPage({ revision, run, onChanged, onPaper }: { revision: number; run: Run; onChanged: () => void; onPaper: (id: string) => void }) {
  const { data, error, loading } = useData<Paged<Job>>('/jobs', revision, 1500);
  const [filter, setFilter] = useState('all');
  const items = data?.items || [];
  const active = items.filter(job => ['queued', 'running', 'parsing', 'cancel_requested', 'publishing', 'waiting_models'].includes(job.status));
  const failed = items.filter(job => ['failed', 'interrupted'].includes(job.status));
  const completed = items.filter(job => job.status === 'completed');
  const filtered = filter === 'all' ? items : filter === 'active' ? active : filter === 'failed' ? failed : completed;
  const filters = [{ key: 'all', title: '全部任务', count: items.length }, { key: 'active', title: '进行中', count: active.length }, { key: 'failed', title: '失败 / 中断', count: failed.length }, { key: 'completed', title: '已完成', count: completed.length }];
  return <>
    <div className="search-tabs">{filters.map(({ key, title, count }) => <button key={key} className={filter === key ? 'active' : ''} onClick={() => setFilter(key)}>{title} {count}</button>)}</div>
    <ErrorMessage message={error} />
    {loading && !data && <Spinner />}
    {!filtered.length && !loading && !error && <Empty title={filter === 'all' ? '暂无解析任务' : '此列表暂无任务'} />}
    <div className="job-list">{filtered.map(job => <article className="job-card" key={job.id}>
      <div className="job-content">
        <button className="job-title" onClick={() => onPaper(job.paper_id)}>{job.paper_title || '论文解析任务'}</button>
        <div className="job-info"><Status value={job.status} />{active.includes(job) && job.phase && <span>{job.phase}</span>}
          {job.pages_total ? <span>{typeof job.pages_done === 'number' ? `${job.pages_done} / ${job.pages_total} 页` : `共 ${job.pages_total} 页`}</span> : typeof job.pages_done === 'number' ? <span>已处理 {job.pages_done} 页</span> : null}
          {typeof job.resources_count === 'number' && <span>{job.resources_count} 个资源</span>}
          {job.created_at && <time dateTime={job.created_at}>{new Date(job.created_at).toLocaleString('zh-CN')}</time>}
        </div>
        {job.pages_total && typeof job.pages_done === 'number' && job.status === 'running' ? <progress aria-label="已处理页数" value={job.pages_done} max={job.pages_total} /> : null}
        {job.error && <ErrorMessage message={job.error} />}
      </div>
      <div className="job-actions">{['failed', 'cancelled', 'interrupted'].includes(job.status) ? <button className="button secondary small" onClick={() => void run(() => post(`/jobs/${job.id}/retry`), '任务已重新排队').then(ok => { if (ok) onChanged(); })}><RefreshCw size={14} />重试</button> : active.includes(job) && <button className="button secondary small" disabled={job.status === 'cancel_requested'} onClick={() => void run(() => post(`/jobs/${job.id}/cancel`), '已请求取消任务').then(ok => { if (ok) onChanged(); })}><X size={14} />取消</button>}</div>
    </article>)}</div>
  </>;
}

export function SettingsPage({ library, revision, theme, onTheme, run, onChanged, onOpenLibrary }: { library: Library | null; revision: number; theme: string; onTheme: (value: string) => void; run: Run; onChanged: () => void; onOpenLibrary: () => void }) {
  const { data: models, error } = useData<ModelState>('/models', revision, 2500);
  const [modelPath, setModelPath] = useState(''); const [backupPath, setBackupPath] = useState(''); const [backupResult, setBackupResult] = useState('');
  const [restorePath, setRestorePath] = useState(''); const [restoreDestination, setRestoreDestination] = useState(''); const [restoring, setRestoring] = useState(false);
  const browseModel = async () => { const path = await chooseDirectory('选择离线模型目录'); if (path) setModelPath(path); };
  const chooseBackup = async () => { if (native) { const { save } = await import('@tauri-apps/plugin-dialog'); const path = await save({ defaultPath: 'PaperVault-backup.zip', filters: [{ name: 'PaperVault 备份', extensions: ['zip'] }] }); if (path) setBackupPath(path); } };
  const browseRestore = async () => { if (native) { const { open } = await import('@tauri-apps/plugin-dialog'); const path = await open({ multiple: false, filters: [{ name: 'PaperVault 备份', extensions: ['zip'] }] }); if (typeof path === 'string') setRestorePath(path); } };
  const backup = async () => { await run(async () => { const result = await post<{ path: string }>('/backups', backupPath ? { destination: backupPath } : {}); setBackupResult(result.path); }, '论文库备份已完成'); };
  const restore = async () => { setRestoring(true); await run(() => post('/backups/restore', { path: restorePath, destination: restoreDestination }), '恢复完成，原论文库仍然保留').then(ok => { if (ok) onChanged(); }); setRestoring(false); };
  return <div className="settings-stack"><section className="settings-card"><div className="settings-heading"><div><h3>论文库</h3></div></div><div className="path-display">{library?.path || '尚未选择论文库'}</div><div className="settings-row"><span className="muted">{library?.paper_count || 0} 篇论文 · {library?.figure_count || 0} 个图片 · {library?.table_count || 0} 个表格</span><button className="button secondary small" onClick={onOpenLibrary}><FolderOpen size={15} />切换论文库</button>{native && library?.path && <button className="button secondary small" onClick={() => void run(async () => { const { openPath } = await import('@tauri-apps/plugin-opener'); await openPath(library.path!); })}>打开文件夹</button>}</div></section>
    <section className="settings-card"><div className="settings-heading"><div><h3>解析模型</h3></div>{models && <Status value={models.phase || models.status || (models.ready ? 'ready' : 'missing')} />}</div><ErrorMessage message={error || models?.error} />{models?.message && <p className="muted">{models.message}</p>}{models?.path && <div className="path-display">{models.path}</div>}{['downloading', 'planning', 'verifying', 'importing'].includes(models?.phase || '') && <>{models?.bytes_total ? <div className="download-progress"><progress value={models.bytes_done || 0} max={models.bytes_total} /><span>{Math.round((models.bytes_done || 0) / 1048576)} / {Math.round(models.bytes_total / 1048576)} MB</span></div> : ['downloading', 'planning', 'verifying', 'importing'].includes(models?.phase || '') && <Spinner label="正在下载并校验模型文件…" />}</>}<div className="settings-row"><button className="button primary" disabled={['downloading', 'planning', 'verifying', 'importing'].includes(models?.phase || '')} onClick={() => void run(() => post('/models/download'), '模型下载已开始').then(ok => { if (ok) onChanged(); })}><Download size={16} />{['error', 'invalid'].includes(models?.phase || '') ? '重试下载模型' : models?.ready || models?.phase === 'ready' ? '检查 / 补全模型' : '下载解析模型'}</button>{!models?.ready && <span className="help-text">仅下载模型文件，不上传论文。</span>}</div><div className="inline-form"><input aria-label="离线模型目录" value={modelPath} onChange={e => setModelPath(e.target.value)} placeholder="离线模型目录" />{native && <button className="button secondary" onClick={() => void browseModel()}>浏览</button>}<button className="button secondary" disabled={!modelPath.trim()} onClick={() => void run(() => post('/models/import', { path: modelPath }), '离线模型已导入').then(ok => { if (ok) onChanged(); })}><Upload size={15} />导入</button></div></section>
    <section className="settings-card"><div className="settings-heading"><div><h3>备份与恢复</h3></div></div><Field label="备份文件路径"><div className="inline-form"><input value={backupPath} onChange={e => setBackupPath(e.target.value)} placeholder="留空保存至论文库 backups 目录" />{native && <button className="button secondary" onClick={() => void chooseBackup()}>浏览</button>}<button className="button primary" onClick={() => void backup()}>创建备份</button></div></Field>{backupResult && <div className="success-message">备份已保存：{backupResult}</div>}<div className="info-divider" /><Field label="备份文件"><div className="inline-form"><input value={restorePath} onChange={e => setRestorePath(e.target.value)} placeholder="选择备份 ZIP 文件" />{native && <button className="button secondary" onClick={() => void browseRestore()}>浏览</button>}</div></Field><Field label="恢复到新的空目录"><div className="inline-form"><input value={restoreDestination} onChange={e => setRestoreDestination(e.target.value)} placeholder="恢复目录" />{native && <button className="button secondary" onClick={() => void chooseDirectory('选择新的空目录').then(path => { if (path) setRestoreDestination(path); })}>浏览</button>}</div></Field><p className="help-text">恢复到空目录，现有论文库不会被覆盖。</p><button className="button secondary" disabled={!restorePath.trim() || !restoreDestination.trim() || restoring} onClick={() => void restore()}><RefreshCw size={15} />{restoring ? '正在校验并恢复…' : '校验备份并恢复'}</button></section>
    <section className="settings-card"><div className="settings-heading"><div><h3>偏好设置</h3></div></div><div className="settings-row"><span>外观</span><div className="segmented">{[['light', '浅色'], ['dark', '深色'], ['system', '跟随系统']].map(([value, label]) => <button className={theme === value ? 'selected' : ''} key={value} onClick={() => onTheme(value)}>{label}</button>)}</div></div><div className="settings-row"><span>界面语言</span><span className="muted">简体中文</span></div><div className="settings-row"><span>快捷键</span><span className="shortcut-help"><kbd>Ctrl K</kbd> 全局搜索 <kbd>Ctrl O</kbd> 导入论文 <kbd>Esc</kbd> 关闭详情</span></div></section>
  </div>;
}
