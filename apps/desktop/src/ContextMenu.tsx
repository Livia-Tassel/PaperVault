import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

export interface ContextAction { label: string; action: () => void; danger?: boolean }
export function ContextMenu({ x, y, actions, onClose }: { x: number; y: number; actions: ContextAction[]; onClose: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    root.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const close = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) onClose(); };
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const buttons = Array.from(root.current?.querySelectorAll<HTMLButtonElement>('button') || []);
        const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
        buttons[(current + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length]?.focus();
      }
    };
    window.addEventListener('pointerdown', close); window.addEventListener('keydown', key);
    return () => { window.removeEventListener('pointerdown', close); window.removeEventListener('keydown', key); };
  }, [onClose]);
  return createPortal(<div ref={root} role="menu" className="context-menu" style={{ left: Math.min(x, window.innerWidth - 200), top: Math.min(y, window.innerHeight - actions.length * 38 - 16) }}>{actions.map(item => <button role="menuitem" key={item.label} className={item.danger ? 'danger' : ''} onClick={() => { onClose(); item.action(); }}>{item.label}</button>)}</div>, document.body);
}
