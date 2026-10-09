import type { ReaderViewState, ReadingState, ReadingStatus } from './reading';

export type ReadingPatch = Partial<ReaderViewState> & { status?: ReadingStatus; touch?: boolean };
type Persist = (patch: ReadingPatch & { expected_version: number }) => Promise<ReadingState>;
const editable = new Set(['page_index', 'anchor', 'scale', 'rotation', 'fit_mode', 'status', 'touch']);

/** Coalesce scroll events, serialize writes, and keep the last local view on failure. */
export class ReadingStateQueue {
  private pending: ReadingPatch = {};
  private sending: ReadingPatch = {};
  private running: Promise<boolean> | null = null;
  private notify: () => void;
  state: ReadingState;
  error = '';
  conflict: ReadingState | null = null;

  constructor(initial: ReadingState, private persist: Persist, notify: () => void = () => {}) {
    this.state = initial;
    this.notify = notify;
  }
  get dirty() { return !!this.running || Object.keys(this.pending).length > 0; }
  get current(): ReadingState { return { ...this.state, ...this.sending, ...this.pending }; }
  setNotify(notify: () => void) { this.notify = notify; }

  enqueue(patch: ReadingPatch) {
    const current = this.current;
    const updates: ReadingPatch = {};
    for (const [key, value] of Object.entries(patch)) {
      if (editable.has(key) && value !== undefined && (key === 'touch' || JSON.stringify(current[key as keyof ReadingState]) !== JSON.stringify(value)))
        Object.assign(updates, { [key]: value });
    }
    if (!Object.keys(updates).length) return;
    this.pending = { ...this.pending, ...updates };
    this.notify();
  }

  flush(): Promise<boolean> {
    if (this.running) return this.running;
    if (this.conflict) return Promise.resolve(false);
    this.running = this.drain().finally(() => { this.running = null; this.notify(); });
    this.notify();
    return this.running;
  }

  private async drain(): Promise<boolean> {
    while (Object.keys(this.pending).length) {
      const sending = this.pending;
      this.sending = sending;
      this.pending = {};
      this.error = '';
      try {
        const next = await this.persist({ ...sending, expected_version: this.state.version });
        if (next.paper_id !== this.state.paper_id || next.version < this.state.version)
          throw new Error('阅读记录响应与当前论文不一致');
        this.state = next;
        this.sending = {};
        this.notify();
      } catch (reason) {
        this.pending = { ...sending, ...this.pending };
        this.sending = {};
        this.error = reason instanceof Error ? reason.message : String(reason);
        const failure = reason as { status?: number; current?: ReadingState };
        if (failure?.status === 409 && failure.current?.paper_id === this.state.paper_id && Number.isInteger(failure.current.version))
          this.conflict = failure.current;
        this.notify();
        return false;
      }
    }
    return true;
  }

  /** Explicitly keep this reader's position after the UI presents a conflict. */
  retryLocal() {
    if (this.conflict) {
      // The user's choice is to keep the visible position, not merely replay
      // a scale delta on top of another window's page and anchor.
      const local = this.current;
      this.pending = { page_index: local.page_index, anchor: local.anchor, scale: local.scale,
        rotation: local.rotation, fit_mode: local.fit_mode, ...this.pending };
      this.state = this.conflict; this.conflict = null;
    }
    this.error = '';
    return this.flush();
  }

  /** Discard only unsent view state, never a user annotation or paper edit. */
  discard() {
    if (this.running) return false;
    if (this.conflict) this.state = this.conflict;
    this.pending = {}; this.conflict = null; this.error = ''; this.notify();
    return true;
  }
}
