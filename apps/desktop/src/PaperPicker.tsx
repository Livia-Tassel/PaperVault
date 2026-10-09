import { useId, useState } from 'react';
import { Search, X } from 'lucide-react';
import { query } from './api';
import { useData, useDebounce } from './hooks';
import { ErrorMessage } from './ui';
import type { Paged, Paper } from './types';

/** Search-backed selection also reaches papers beyond the first library page. */
export function PaperPicker({ value, onChange, label = '筛选论文', disabled = false }: {
  value: { id: string; title: string } | null;
  onChange: (paper: { id: string; title: string } | null) => void;
  label?: string; disabled?: boolean;
}) {
  const [input, setInput] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const q = useDebounce(input);
  const listId = useId();
  const { data, error, loading } = useData<Paged<Paper>>(open ? `/papers${query({ q, limit: 20 })}` : null);
  const items = data?.items || [];
  const select = (paper: Paper) => { onChange({ id: paper.id, title: paper.title || paper.filename }); setOpen(false); setInput(''); };
  return <div className="paper-picker" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <div className="search-input"><Search size={15} /><input role="combobox" aria-label={label}
      aria-expanded={open} aria-controls={listId} aria-autocomplete="list"
      aria-activedescendant={open && items[active] ? `${listId}-${active}` : undefined}
      value={open ? input : value?.title || ''} placeholder={label} disabled={disabled}
      onFocus={() => { setInput(''); setOpen(true); setActive(0); }}
      onChange={event => { setInput(event.target.value); setOpen(true); setActive(0); }}
      onKeyDown={event => {
        if (event.nativeEvent.isComposing) return;
        if (event.key === 'Escape' && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); }
        else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true); setActive(index => Math.max(0, Math.min(items.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))); }
        else if (event.key === 'Enter' && open && items[active]) { event.preventDefault(); if (input === q && !loading) select(items[active]); }
      }} />
      {value && <button type="button" className="icon-button" aria-label={`清除${label}`} disabled={disabled} onClick={() => { onChange(null); setInput(''); }}><X size={14} /></button>}
    </div>
    {open && <div className="paper-picker-menu"><ErrorMessage message={error} /><div id={listId} role="listbox" aria-label="论文匹配结果">
      {items.map((paper, index) => <button key={paper.id} type="button" id={`${listId}-${index}`} role="option"
        aria-selected={index === active} disabled={input !== q || loading} onMouseDown={event => event.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => select(paper)}>
        <span>{paper.title || paper.filename}</span><small>{paper.authors?.join(' · ') || paper.filename}</small>
      </button>)}
      {!items.length && <p className="muted">{loading ? '正在查找…' : '没有匹配的论文'}</p>}
      {!!data && data.total > items.length && <p className="muted">共 {data.total} 篇，输入标题或作者缩小范围。</p>}
    </div></div>}
  </div>;
}
