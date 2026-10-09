import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { native } from './api';
import { Modal } from './ui';

export interface DraftGuardOptions {
  id: string;
  label: string;
  dirty: boolean;
  onSave: () => Promise<boolean>;
  onDiscard: () => void;
  priority?: number;
  autoSave?: boolean;
}
type Action = () => void | Promise<void>;
type DraftRegistration = { owner: symbol; read: () => DraftGuardOptions };

/** A fresh read at command time prevents saving an obsolete render's draft. */
export class DraftRegistry {
  private drafts = new Map<string, DraftRegistration>();
  register(id: string, registration: DraftRegistration) {
    this.drafts.set(id, registration);
    return () => { if (this.drafts.get(id)?.owner === registration.owner) this.drafts.delete(id); };
  }
  all(ids?: string[]) {
    return [...this.drafts.values()].map(value => value.read())
      .filter(draft => !ids || ids.includes(draft.id))
      .sort((a, b) => (b.priority || 0) - (a.priority || 0));
  }
  dirty(ids?: string[]) { return this.all(ids).filter(draft => draft.dirty); }
  async flushAutomatic(ids?: string[]) {
    const flushed = new Set<string>();
    const failed: DraftGuardOptions[] = [];
    for (const id of this.dirty(ids).map(draft => draft.id)) {
      const draft = this.all([id])[0];
      if (!draft?.dirty || !draft.autoSave) continue;
      try { if (await draft.onSave()) flushed.add(id); else failed.push(draft); }
      catch { failed.push(draft); }
    }
    return { flushed, failed };
  }
  async save(ids?: string[]) {
    for (const draft of this.dirty(ids)) if (!await draft.onSave()) return false;
    return true;
  }
  discard(ids?: string[]) { for (const draft of this.dirty(ids)) draft.onDiscard(); }
}

interface EditGuard {
  attempt: (action: Action, ids?: string[]) => Promise<boolean>;
  saveCurrent: () => Promise<boolean>;
  registry: DraftRegistry;
}
const Context = createContext<EditGuard | null>(null);
type Pending = { action: Action; ids?: string[]; labels: string[]; resolve: (allowed: boolean) => void };

export function EditGuardProvider({ children }: { children: ReactNode }) {
  const registry = useRef(new DraftRegistry()).current;
  const pending = useRef<Pending | null>(null);
  const [prompt, setPrompt] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const allowNativeUnload = useRef(false);
  const [error, setError] = useState('');
  const [operationError, setOperationError] = useState('');
  const perform = useCallback(async (action: Action) => {
    try { await action(); return true; }
    catch (reason) { setOperationError(reason instanceof Error ? reason.message : String(reason)); return false; }
  }, []);
  const attempt = useCallback(async (action: Action, ids?: string[]) => {
    if (pending.current || busyRef.current) return false;
    busyRef.current = true;
    let automatic: Awaited<ReturnType<DraftRegistry['flushAutomatic']>>;
    try { automatic = await registry.flushAutomatic(ids); }
    finally { busyRef.current = false; }
    const { flushed, failed } = automatic;
    const dirty = registry.dirty(ids).filter(draft => !flushed.has(draft.id));
    for (const draft of failed) if (!dirty.some(item => item.id === draft.id)) dirty.push(draft);
    if (!dirty.length) {
      busyRef.current = true;
      try { return await perform(action); }
      finally { busyRef.current = false; }
    }
    return new Promise<boolean>(resolve => {
      const next = { action, ids, labels: dirty.map(draft => draft.label), resolve };
      pending.current = next; setError(failed.length ? '阅读进度尚未保存。请重试保存，或继续编辑。' : ''); setPrompt(next);
    });
  }, [registry, perform]);
  const finish = useCallback((allowed: boolean) => {
    const current = pending.current;
    pending.current = null; setPrompt(null); setError(''); current?.resolve(allowed);
  }, []);
  const choose = async (choice: 'save' | 'discard' | 'cancel') => {
    if (busyRef.current || !pending.current) return;
    if (choice === 'cancel') { finish(false); return; }
    const current = pending.current;
    busyRef.current = true; setBusy(true); setError('');
    try {
      if (choice === 'save' && !await registry.save(current.ids)) { setError('保存未完成，修改仍保留。请重试或继续编辑。'); return; }
      if (choice === 'discard') registry.discard(current.ids);
      // Close the confirmation before a native window destroy or another modal opens.
      pending.current = null; setPrompt(null);
      current.resolve(await perform(current.action));
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { busyRef.current = false; setBusy(false); }
  };
  const saveCurrent = useCallback(async () => {
    if (pending.current || busyRef.current) return false;
    // The top editor owns Ctrl+S even when clean; do not save a draft behind a modal.
    const current = registry.all()[0];
    if (!current?.dirty) return true;
    busyRef.current = true;
    try { return await current.onSave(); }
    catch (reason) { setOperationError(reason instanceof Error ? reason.message : String(reason)); return false; }
    finally { busyRef.current = false; }
  }, [registry]);
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!allowNativeUnload.current && registry.dirty().length) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [registry]);
  useEffect(() => {
    if (!native) return;
    let disposed = false; let unlisten: (() => void) | undefined; let closing = false;
    void import('@tauri-apps/api/window').then(async ({ getCurrentWindow }) => {
      const window = getCurrentWindow();
      const stop = await window.onCloseRequested(event => {
        event.preventDefault();
        if (closing) return;
        closing = true;
        void attempt(async () => {
          allowNativeUnload.current = true;
          try { await window.destroy(); } catch (reason) { allowNativeUnload.current = false; throw reason; }
        }).finally(() => { closing = false; });
      });
      if (disposed) stop(); else unlisten = stop;
    }).catch(reason => setOperationError(`无法启用关闭保护：${String(reason)}`));
    return () => { disposed = true; unlisten?.(); };
  }, [attempt]);
  useEffect(() => () => { pending.current?.resolve(false); }, []);
  return <Context.Provider value={{ registry, attempt, saveCurrent }}>{children}
    {operationError && <div className="guard-operation-error" role="alert"><span>{operationError}</span><button onClick={() => setOperationError('')} aria-label="关闭操作错误">×</button></div>}
    {prompt && <Modal title="有未保存的修改" onClose={() => { if (!busyRef.current) finish(false); }}>
      <p className="dialog-description">{prompt.labels.join('、')}的修改尚未保存。</p>
      {error && <p role="alert" className="error-message">{error}</p>}
      <div className="modal-footer guard-actions">
        <button className="button secondary" disabled={busy} onClick={() => void choose('cancel')}>继续编辑</button>
        <button className="button secondary" disabled={busy} onClick={() => void choose('discard')}>放弃修改</button>
        <button className="button primary" disabled={busy} onClick={() => void choose('save')}>{busy ? '保存中…' : '保存并继续'}</button>
      </div>
    </Modal>}
  </Context.Provider>;
}

export function useEditGuard() {
  const context = useContext(Context);
  if (!context) throw new Error('useEditGuard requires EditGuardProvider');
  return context;
}

/** Use a stable ID (including entity ID); higher priority editors own Ctrl+S. */
export function useDraftGuard(options: DraftGuardOptions) {
  const { registry } = useEditGuard();
  const latest = useRef(options); latest.current = options;
  useEffect(() => registry.register(options.id, { owner: Symbol(options.id), read: () => latest.current }), [registry, options.id]);
}
