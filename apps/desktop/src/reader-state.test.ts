import { describe, expect, it } from 'vitest';
import { ReadingStateQueue, type ReadingPatch } from './reader-state';
import type { ReadingState } from './reading';

const initial: ReadingState = { paper_id: 'paper-a', version: 0, page_index: 0, anchor: null, scale: 1,
  rotation: 0, fit_mode: 'custom', status: 'unread', last_opened: null, updated_at: null };

describe('reader persistence under delayed writes and concurrent changes', () => {
  it('strips readonly response fields when a restored ReadingState reaches the view callback', async () => {
    const sent: Array<ReadingPatch & { expected_version: number }> = [];
    const queue = new ReadingStateQueue(initial, async body => { sent.push(body); return { ...initial, ...body, version: 1 }; });
    queue.enqueue({ ...initial, page_index: 2, version: 99, last_opened: 'not-client-writable' } as ReadingState);
    expect(await queue.flush()).toBe(true);
    expect(sent).toEqual([{ page_index: 2, expected_version: 0 }]);
  });
  it('persists returning to the preceding page while its outgoing write is still pending', async () => {
    let release!: () => void;
    const first = new Promise<void>(resolve => { release = resolve; });
    let server = { ...initial };
    let calls = 0;
    const queue = new ReadingStateQueue(initial, async body => {
      if (++calls === 1) await first;
      server = { ...server, ...body, version: server.version + 1 };
      return server;
    });
    queue.enqueue({ page_index: 1 });
    const saved = queue.flush();
    queue.enqueue({ page_index: 0 });
    release();
    expect(await saved).toBe(true);
    expect(calls).toBe(2);
    expect(queue.current.page_index).toBe(0);
  });
  it('does not send concurrent writes and publishes the latest scroll after the first response', async () => {
    let release!: () => void;
    const first = new Promise<void>(resolve => { release = resolve; });
    const received: Array<ReadingPatch & { expected_version: number }> = [];
    const queue = new ReadingStateQueue(initial, async body => {
      received.push(body);
      if (received.length === 1) await first;
      return { ...initial, ...body, version: received.length };
    });
    queue.enqueue({ page_index: 1, scale: 1.5 });
    const saved = queue.flush();
    queue.enqueue({ page_index: 7, anchor: [20, 80] });
    queue.enqueue({ page_index: 8, anchor: [20, 50], rotation: 90 });
    expect(received).toHaveLength(1);
    expect(queue.flush()).toBe(saved);
    release();
    expect(await saved).toBe(true);
    expect(received).toEqual([
      { page_index: 1, scale: 1.5, expected_version: 0 },
      { page_index: 8, anchor: [20, 50], rotation: 90, expected_version: 1 },
    ]);
    expect(queue.dirty).toBe(false);
    expect(queue.state.page_index).toBe(8);
  });
  it('keeps unsaved local state on a network failure and retries with the same version', async () => {
    let failing = true;
    const queue = new ReadingStateQueue(initial, async body => {
      if (failing) throw new Error('Network unavailable');
      return { ...initial, ...body, version: 1 };
    });
    queue.enqueue({ page_index: 3 });
    expect(await queue.flush()).toBe(false);
    expect(queue.current.page_index).toBe(3);
    expect(queue.dirty).toBe(true);
    failing = false;
    expect(await queue.flush()).toBe(true);
    expect(queue.state.version).toBe(1);
    expect(queue.error).toBe('');
  });
  it('requires explicit resolution rather than overwriting a newer server position', async () => {
    let writes = 0;
    const newer = { ...initial, page_index: 5, version: 4 };
    const queue = new ReadingStateQueue(initial, async body => {
      writes++;
      if (body.expected_version !== 4) throw Object.assign(new Error('Conflict'), { status: 409, current: newer });
      return { ...newer, ...body, version: 5 };
    });
    queue.enqueue({ page_index: 3 });
    expect(await queue.flush()).toBe(false);
    expect(await queue.flush()).toBe(false);
    expect(writes).toBe(1);
    expect(queue.current.page_index).toBe(3);
    expect(await queue.retryLocal()).toBe(true);
    expect(queue.state).toMatchObject({ page_index: 3, version: 5 });
  });
  it('can discard the local position after conflict without writing or losing server state', async () => {
    const newer = { ...initial, page_index: 5, version: 4 };
    const queue = new ReadingStateQueue(initial, async () => { throw Object.assign(new Error('Conflict'), { status: 409, current: newer }); });
    queue.enqueue({ page_index: 3 });
    await queue.flush();
    expect(queue.discard()).toBe(true);
    expect(queue.current).toEqual(newer);
    expect(queue.dirty).toBe(false);
  });
  it('keeps the entire visible local view when only its zoom changed before a conflict', async () => {
    const start = { ...initial, anchor: [10, 20] as [number, number] };
    const remote = { ...initial, version: 4, page_index: 5, anchor: [30, 40] as [number, number], scale: 2, rotation: 90 as const };
    const queue = new ReadingStateQueue(start, async body => {
      if (body.expected_version !== 4) throw Object.assign(new Error('Conflict'), { status: 409, current: remote });
      return { ...remote, ...body, version: 5 };
    });
    queue.enqueue({ scale: 1.5 });
    await queue.flush();
    expect(await queue.retryLocal()).toBe(true);
    expect(queue.state).toMatchObject({ page_index: 0, anchor: [10, 20], scale: 1.5, rotation: 0, fit_mode: 'custom' });
  });
});
