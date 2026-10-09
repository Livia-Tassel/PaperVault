import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react';
import { handleTabKeys } from './tabs';
import { ArrowLeft, ArrowRight, BookOpen, X } from 'lucide-react';
import { emptyWorkspace, readStorage, restoreWorkspace, storageKey, workspaceReducer, writeStorage, type ReaderWorkspace, type WorkspaceAction } from './workspace-state';

const Context = createContext('');
export function WorkspaceProvider({ libraryKey, children }: { libraryKey: string; children: ReactNode }) { return <Context.Provider value={libraryKey}>{children}</Context.Provider>; }
export function useWorkspaceKey() { return useContext(Context); }

/** Cache view controls under the active library, without persisting drafts or credentials. */
export function useWorkspaceState<T>(key: string, initial: T | (() => T)): [T, Dispatch<SetStateAction<T>>] {
  const libraryKey = useContext(Context);
  const scopedKey = storageKey(libraryKey, `view:${key}`);
  const initialValue = useMemo(() => {
    const fallback = typeof initial === 'function' ? (initial as () => T)() : initial;
    const saved = libraryKey ? readStorage(scopedKey) : undefined;
    return saved !== undefined && typeof saved === typeof fallback && Array.isArray(saved) === Array.isArray(fallback) ? saved as T : fallback;
  }, [scopedKey]); // A newly mounted view supplies the fallback; it is not a reset signal.
  const [cached, setCached] = useState({ key: scopedKey, value: initialValue });
  const value = cached.key === scopedKey ? cached.value : initialValue;
  const setValue = useCallback<Dispatch<SetStateAction<T>>>(next => setCached(previous => {
    const current = previous.key === scopedKey ? previous.value : initialValue;
    const value = typeof next === 'function' ? (next as (previous: T) => T)(current) : next;
    if (libraryKey) writeStorage(scopedKey, value);
    return { key: scopedKey, value };
  }), [scopedKey, libraryKey, initialValue]);
  return [value, setValue];
}

export function useReaderWorkspace(libraryKey: string) {
  const key = storageKey(libraryKey);
  const restored = useMemo(() => libraryKey ? restoreWorkspace(readStorage(key)) : emptyWorkspace(), [key, libraryKey]);
  const [cached, setCached] = useState({ key, state: restored });
  const state = cached.key === key ? cached.state : restored;
  const dispatch = useCallback((action: WorkspaceAction) => setCached(previous => ({ key, state: workspaceReducer(previous.key === key ? previous.state : restored, action) })), [key, restored]);
  useEffect(() => { if (libraryKey) writeStorage(key, state); }, [key, libraryKey, state]);
  return [state, dispatch] as const;
}

export function WorkspaceBar({ state, onHistory, onActivate, onClose, onHome }: {
  state: ReaderWorkspace; onHistory: (delta: -1 | 1) => void;
  onActivate: (id: string) => void; onClose: (id: string) => void; onHome: () => void;
}) {
  const tabList = useRef<HTMLDivElement>(null);
  useEffect(() => { tabList.current?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' }); }, [state.route]);
  return <div className="workspace-bar" aria-label="阅读工作区">
    <div className="workspace-history">
      <button className="icon-button" aria-label="后退" title="后退 (Alt+←)" disabled={state.historyIndex <= 0} onClick={() => onHistory(-1)}><ArrowLeft size={16} /></button>
      <button className="icon-button" aria-label="前进" title="前进 (Alt+→)" disabled={state.historyIndex >= state.history.length - 1} onClick={() => onHistory(1)}><ArrowRight size={16} /></button>
    </div>
    <div ref={tabList} className="workspace-tabs" onKeyDown={handleTabKeys} role="tablist" aria-label="打开的论文">
      <button className={`workspace-home ${state.route.kind === 'collection' ? 'active' : ''}`} role="tab" tabIndex={state.route.kind === 'collection' ? 0 : -1} aria-selected={state.route.kind === 'collection'} aria-label="返回工作区" onClick={onHome}><BookOpen size={15} /><span>工作区</span></button>
      {state.tabs.map(tab => <div className={`workspace-tab ${state.route.kind === 'paper' && state.route.paperId === tab.id ? 'active' : ''}`} key={tab.id}>
        <button role="tab" tabIndex={state.route.kind === 'paper' && state.route.paperId === tab.id ? 0 : -1} aria-selected={state.route.kind === 'paper' && state.route.paperId === tab.id} title={tab.title} onClick={() => onActivate(tab.id)}><span>{tab.title}</span></button>
        <button className="tab-close" aria-label={`关闭论文 ${tab.title}`} title="关闭论文 (Ctrl+W)" onClick={() => onClose(tab.id)}><X size={13} /></button>
      </div>)}
    </div>
  </div>;
}
