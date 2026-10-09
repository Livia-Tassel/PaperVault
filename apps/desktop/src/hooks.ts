import { useEffect, useState } from 'react';
import { api, request } from './api';
import { useWorkspaceKey } from './Workspace';
import { readStorage, storageKey, writeStorage } from './workspace-state';

export function useData<T>(path: string | null, revision = 0, interval = 0, identity = '') {
  const workspaceKey = useWorkspaceKey();
  const key = path ? JSON.stringify([identity || workspaceKey, path]) : null;
  const [snapshot, setSnapshot] = useState<{ key: string | null; data: T | null; error: string; loading: boolean }>({ key: null, data: null, error: '', loading: false });
  useEffect(() => {
    if (!path) { setSnapshot({ key: null, data: null, error: '', loading: false }); return; }
    let mounted = true;
    let inFlight = false;
    const controller = new AbortController();
    const load = async () => {
      if (inFlight) return;
      inFlight = true;
      try { const next = await api<T>(path, { signal: controller.signal }); if (mounted) setSnapshot({ key, data: next, error: '', loading: false }); }
      catch (e) { if (mounted && !(e instanceof DOMException && e.name === 'AbortError')) setSnapshot(previous => ({ key, data: previous.key === key ? previous.data : null, error: e instanceof Error ? e.message : String(e), loading: false })); }
      finally { inFlight = false; }
    };
    setSnapshot(previous => ({ key, data: previous.key === key ? previous.data : null, error: previous.key === key ? previous.error : '', loading: true })); void load();
    const timer = interval ? window.setInterval(() => { if (!document.hidden) void load(); }, interval) : undefined;
    return () => { mounted = false; controller.abort(); if (timer) clearInterval(timer); };
  }, [path, key, revision, interval]);
  // A path change must not expose the preceding entity for even one render.
  // In particular, an editor for paper B must never initialize from paper A.
  return snapshot.key === key ? { data: snapshot.data, error: snapshot.error, loading: snapshot.loading }
    : { data: null, error: '', loading: !!path };
}
export function useDebounce<T>(value: T, delay = 250, identity = ''): T {
  const workspaceKey = useWorkspaceKey();
  const key = `${workspaceKey}:${identity}`;
  const [debounced, setDebounced] = useState({ key, value });
  useEffect(() => {
    if (debounced.key !== key) { setDebounced({ key, value }); return; }
    const timer = setTimeout(() => setDebounced({ key, value }), delay);
    return () => clearTimeout(timer);
  }, [value, delay, key, debounced.key]);
  return debounced.key === key ? debounced.value : value;
}
export function useImage(path: string | null, revision = 0) {
  const workspaceKey = useWorkspaceKey();
  const key = JSON.stringify([workspaceKey, path]);
  const [url, setUrl] = useState('');
  const [sourceKey, setSourceKey] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    if (!path) { setUrl(''); return; }
    let object = ''; let disposed = false;
    const controller = new AbortController();
    setUrl(''); setError('');
    void request(path, { signal: controller.signal }).then(r => r.blob()).then(blob => {
      if (!disposed) { object = URL.createObjectURL(blob); setSourceKey(key); setUrl(object); }
    }).catch(e => { if (!disposed) setError(e instanceof Error ? e.message : String(e)); });
    return () => { disposed = true; controller.abort(); if (object) URL.revokeObjectURL(object); };
  }, [path, revision, workspaceKey, key]);
  return { url: sourceKey === key ? url : '', error };
}

/** Restore a collection after reading, without storing live DOM or credentials. */
export function useWorkspaceScroll(name: string, ready: boolean) {
  const libraryKey = useWorkspaceKey();
  const key = storageKey(libraryKey, `scroll:${name}`);
  useEffect(() => {
    if (!ready || !libraryKey) return;
    const container = document.querySelector<HTMLElement>('.page-content');
    if (!container) return;
    const stored = readStorage(key) as { top?: unknown; focus?: unknown } | undefined;
    let top = typeof stored?.top === 'number' && Number.isFinite(stored.top) ? Math.max(0, stored.top) : 0;
    let focus = typeof stored?.focus === 'string' ? stored.focus : '';
    const previousFocus = document.activeElement;
    const mayRestoreFocus = !previousFocus || previousFocus === document.body || previousFocus === document.documentElement ||
      previousFocus === container || !!previousFocus.closest('.sidebar, .workspace-home');
    const frame = requestAnimationFrame(() => {
      const target = [...container.querySelectorAll<HTMLElement>('[data-workspace-focus]')].find(element => element.dataset.workspaceFocus === focus);
      // A late response must not pull focus back after the user has already
      // moved to a workspace tab, search field, or another control.
      if (mayRestoreFocus && document.activeElement === previousFocus) target?.focus({ preventScroll: true });
      container.scrollTop = top;
    });
    const scroll = () => { top = container.scrollTop; };
    const focused = (event: FocusEvent) => {
      const target = (event.target as HTMLElement | null)?.closest<HTMLElement>('[data-workspace-focus]');
      if (target?.dataset.workspaceFocus) focus = target.dataset.workspaceFocus;
    };
    const persist = () => writeStorage(key, { top, focus });
    container.addEventListener('scroll', scroll, { passive: true });
    container.addEventListener('focusin', focused);
    window.addEventListener('pagehide', persist);
    return () => {
      cancelAnimationFrame(frame); container.removeEventListener('scroll', scroll);
      container.removeEventListener('focusin', focused); window.removeEventListener('pagehide', persist); persist();
    };
  }, [key, libraryKey, ready]);
}
