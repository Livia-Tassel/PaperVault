import { useEffect, useState } from 'react';
import { api, request } from './api';

export function useData<T>(path: string | null, revision = 0, interval = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!path) { setData(null); return; }
    let mounted = true;
    let inFlight = false;
    const controller = new AbortController();
    const load = async () => {
      if (inFlight) return;
      inFlight = true;
      try { const next = await api<T>(path, { signal: controller.signal }); if (mounted) { setData(next); setError(''); } }
      catch (e) { if (mounted && !(e instanceof DOMException && e.name === 'AbortError')) setError(e instanceof Error ? e.message : String(e)); }
      finally { inFlight = false; if (mounted) setLoading(false); }
    };
    setLoading(true); void load();
    const timer = interval ? window.setInterval(() => { if (!document.hidden) void load(); }, interval) : undefined;
    return () => { mounted = false; controller.abort(); if (timer) clearInterval(timer); };
  }, [path, revision, interval]);
  return { data, error, loading, setData };
}
export function useDebounce<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => { const timer = setTimeout(() => setDebounced(value), delay); return () => clearTimeout(timer); }, [value, delay]);
  return debounced;
}
export function useImage(path: string | null, revision = 0) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    if (!path) { setUrl(''); return; }
    let object = ''; let disposed = false;
    const controller = new AbortController();
    setUrl(''); setError('');
    void request(path, { signal: controller.signal }).then(r => r.blob()).then(blob => {
      if (!disposed) { object = URL.createObjectURL(blob); setUrl(object); }
    }).catch(e => { if (!disposed) setError(e instanceof Error ? e.message : String(e)); });
    return () => { disposed = true; controller.abort(); if (object) URL.revokeObjectURL(object); };
  }, [path, revision]);
  return { url, error };
}
