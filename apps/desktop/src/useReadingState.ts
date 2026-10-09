import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { patch } from './api';
import { useDraftGuard } from './EditGuard';
import { useData } from './hooks';
import type { ReaderViewState, ReadingState, ReadingStatus } from './reading';
import { ReadingStateQueue, type ReadingPatch } from './reader-state';

export function useReadingState(paperId: string, libraryKey: string, onChanged: () => void) {
  const [, refresh] = useState(0);
  const { data, loading, error } = useData<ReadingState>(`/papers/${paperId}/reading-state`, 0, 0, libraryKey);
  const onChangedRef = useRef(onChanged); onChangedRef.current = onChanged;
  const timer = useRef<number | undefined>(undefined);
  const queue = useMemo(() => data && data.paper_id === paperId ? new ReadingStateQueue(data,
    changes => patch<ReadingState>(`/papers/${paperId}/reading-state`, changes, { libraryScope: libraryKey })) : null, [data, paperId, libraryKey]);
  useEffect(() => {
    if (!queue) return;
    queue.setNotify(() => refresh(value => value + 1));
    queue.enqueue({ touch: true, ...(queue.state.status === 'unread' ? { status: 'reading' as const } : {}) });
    void queue.flush().then(ok => { if (ok) onChangedRef.current(); });
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
      queue.setNotify(() => {});
      // Navigation/desktop close normally awaits the registered flush first.
      // This also covers an external unmount or a removed paper gracefully.
      if (queue.dirty && !queue.conflict) void queue.flush();
    };
  }, [queue]);
  const schedule = useCallback((changes: ReadingPatch) => {
    if (!queue) return;
    queue.enqueue(changes);
    if (timer.current) clearTimeout(timer.current);
    timer.current = window.setTimeout(() => { void queue.flush(); }, 450);
  }, [queue]);
  const onViewState = useCallback((state: ReaderViewState) => schedule(state), [schedule]);
  const setStatus = useCallback(async (status: ReadingStatus) => {
    if (!queue) return;
    queue.enqueue({ status });
    if (await queue.flush()) onChangedRef.current();
  }, [queue]);
  useDraftGuard({ id: `reading:${libraryKey}:${paperId}`, label: '阅读位置', priority: -100,
    get autoSave() { return !queue?.conflict; },
    get dirty() { return queue?.dirty || false; },
    onSave: () => (queue?.conflict ? queue.retryLocal() : queue?.flush()) || Promise.resolve(true), onDiscard: () => { queue?.discard(); },
  });
  return { initialState: data, loading, error: error || queue?.error || '', state: queue?.current || data,
    queue, onViewState, setStatus };
}
