import { describe, expect, it, vi } from 'vitest';
import { DraftRegistry, type DraftGuardOptions } from './EditGuard';

const draft = (id: string, priority = 0): DraftGuardOptions => ({ id, label: id, dirty: true, priority, onSave: vi.fn(async () => true), onDiscard: vi.fn() });
describe('draft command registry', () => {
  it('reads current callbacks and dirty flags rather than registration-time snapshots', async () => {
    const registry = new DraftRegistry();
    let current = draft('paper');
    registry.register('paper', { owner: Symbol(), read: () => current });
    const previousSave = current.onSave;
    current = { ...draft('paper'), dirty: false };
    expect(registry.dirty()).toEqual([]);
    current.dirty = true;
    await registry.save();
    expect(previousSave).not.toHaveBeenCalled();
    expect(current.onSave).toHaveBeenCalledOnce();
  });
  it('saves only scoped editors and stops after a failed save', async () => {
    const registry = new DraftRegistry();
    const paper = draft('paper', 10), modal = draft('resource', 100);
    modal.onSave = vi.fn(async () => false);
    for (const value of [paper, modal]) registry.register(value.id, { owner: Symbol(), read: () => value });
    expect(await registry.save(['paper'])).toBe(true);
    expect(modal.onSave).not.toHaveBeenCalled();
    expect(await registry.save()).toBe(false);
    expect(paper.onSave).toHaveBeenCalledTimes(1);
  });
  it('a clean modal retains command priority over a dirty editor behind it', () => {
    const registry = new DraftRegistry();
    const paper = draft('paper', 10), modal = { ...draft('resource', 100), dirty: false };
    for (const value of [paper, modal]) registry.register(value.id, { owner: Symbol(), read: () => value });
    expect(registry.all()[0].id).toBe('resource');
    expect(registry.dirty()[0].id).toBe('paper');
  });
  it('stale cleanup cannot unregister a newer editor with the same ID', () => {
    const registry = new DraftRegistry();
    const old = draft('paper'), next = draft('paper');
    const cleanup = registry.register('paper', { owner: Symbol(), read: () => old });
    registry.register('paper', { owner: Symbol(), read: () => next });
    cleanup();
    registry.discard(['paper']);
    expect(old.onDiscard).not.toHaveBeenCalled();
    expect(next.onDiscard).toHaveBeenCalledOnce();
  });
  it('flushes automatic reading state without saving a manual draft', async () => {
    const registry = new DraftRegistry();
    const reading = { ...draft('reading', -100), autoSave: true }, manual = draft('paper', 10);
    for (const value of [reading, manual]) registry.register(value.id, { owner: Symbol(), read: () => value });
    expect((await registry.flushAutomatic()).flushed).toEqual(new Set(['reading']));
    expect(manual.onSave).not.toHaveBeenCalled();
  });
  it('leaves a conflicting reading update for explicit confirmation', async () => {
    const registry = new DraftRegistry();
    let conflict = false;
    const reading = { ...draft('reading'), get autoSave() { return !conflict; } };
    registry.register(reading.id, { owner: Symbol(), read: () => reading });
    conflict = true;
    expect((await registry.flushAutomatic()).flushed.size).toBe(0);
    expect(reading.onSave).not.toHaveBeenCalled();
    expect(registry.dirty()).toHaveLength(1);
  });
  it('reports automatic save failures rather than allowing navigation', async () => {
    const registry = new DraftRegistry();
    const reading = { ...draft('reading'), autoSave: true, onSave: vi.fn(async () => false) };
    registry.register(reading.id, { owner: Symbol(), read: () => reading });
    const result = await registry.flushAutomatic();
    expect(result.flushed.size).toBe(0);
    expect(result.failed.map(draft => draft.id)).toEqual(['reading']);
  });
});
