import { Children, cloneElement, isValidElement, type ReactNode } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { AlertCircle, Check, LoaderCircle, X } from 'lucide-react';
import { useImage } from './hooks';

export const labels: Record<string, string> = {
  queued: '排队中', running: '解析中', parsing: '解析中', importing: '导入中', completed: '已完成', ready: '已就绪',
  failed: '失败', cancelled: '已取消', cancel_requested: '正在取消', interrupted: '已中断', pending: '待解析',
  needs_review: '待校对', partial: '部分完成', downloading: '下载中', missing: '尚未安装', idle: '空闲',
  waiting_models: '等待模型', checking: '检查中', rendering: '生成图片', extracting: '提取资源', publishing: '保存中',
  error: '失败', invalid: '需要修复', planning: '准备下载', verifying: '校验中', validating_models: '校验模型',
};
export function Status({ value }: { value: string }) { return <span className={`status status-${value}`}>{labels[value] || value}</span>; }
export function Spinner({ label = '加载中…' }: { label?: string }) { return <div className="loading"><LoaderCircle size={16} className="spin" /><span>{label}</span></div>; }
export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty-state"><h3>{title}</h3>{children && <p>{children}</p>}{action}</div>;
}
export function ErrorMessage({ message }: { message?: string }) { return message ? <div className="error-message" role="alert"><AlertCircle size={17} /><span>{message}</span></div> : null; }
export function Warnings({ values }: { values?: string[] }) { return values?.length ? <details className="warnings"><summary>解析提示 · {values.length}</summary>{values.map((v, i) => <p key={i}>{v}</p>)}</details> : null; }
export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  return <Dialog.Root open onOpenChange={open => { if (!open) onClose(); }}><Dialog.Portal><Dialog.Overlay className="modal-overlay" /><Dialog.Content aria-describedby={undefined} className={`modal ${wide ? 'modal-wide' : ''}`}><div className="modal-body"><header className="modal-header"><Dialog.Title>{title}</Dialog.Title><Dialog.Close className="icon-button" aria-label="关闭对话框"><X size={20} /></Dialog.Close></header>{children}</div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
export function Tags({ values }: { values?: string[] }) { return <span className="tags">{values?.map(tag => <span className="tag" key={tag}>{tag}</span>)}</span>; }
export function AssetImage({ id, thumbnail = false, revision = 0, alt = '', className = '' }: { id: string; thumbnail?: boolean; revision?: number; alt?: string; className?: string }) {
  const { url, error } = useImage(`/resources/${id}/files/${thumbnail ? 'thumbnail' : 'png'}`, revision);
  return error ? <div className="image-fallback"><AlertCircle size={18} /><span>图片暂不可用</span></div> : url ? <img src={url} alt={alt} loading="lazy" className={className} /> : <div className="image-loading"><LoaderCircle className="spin" size={20} /></div>;
}
export function Pager({ total, offset, limit, onChange }: { total: number; offset: number; limit: number; onChange: (value: number) => void }) {
  return total > limit ? <div className="pager"><span>共 {total} 项 · 第 {Math.floor(offset / limit) + 1} / {Math.ceil(total / limit)} 页</span><button className="button secondary small" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>上一页</button><button className="button secondary small" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>下一页</button></div> : null;
}
export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) { return <button aria-label={label} role="checkbox" aria-checked={checked} className={`select-checkbox ${checked ? 'selected' : ''}`} onClick={event => { event.stopPropagation(); onChange(); }}>{checked && <Check size={13} />}</button>; }
function labelControls(children: ReactNode, label: string): ReactNode {
  return Children.map(children, child => {
    if (!isValidElement<{ children?: ReactNode; 'aria-label'?: string }>(child)) return child;
    if (typeof child.type === 'string' && ['input', 'textarea', 'select'].includes(child.type))
      return cloneElement(child, { 'aria-label': child.props['aria-label'] || label });
    return child.props.children ? cloneElement(child, {}, labelControls(child.props.children, label)) : child;
  });
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  // A controlled textarea's DOM text changes with its value. Give each control
  // a stable label instead of including that value or adjacent browse buttons.
  return <label className="field"><span>{label}</span>{labelControls(children, label)}</label>;
}
export function filename(value: string, fallback: string): string { return (value || fallback).replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[. ]+$/, '').slice(0, 100) || fallback; }
export const splitTags = (value: string): string[] => [...new Set(value.split(/[,，\n]/).map(t => t.trim()).filter(Boolean))];
