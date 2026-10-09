import { describe, expect, it } from 'vitest';
import { emptyWorkspace, homeRoute, restoreWorkspace, storageKey, workspaceReducer, type ReaderWorkspace, type WorkspaceRoute } from './workspace-state';

const paper = (id: string): WorkspaceRoute => ({ kind: 'paper', paperId: id });
const go = (state: ReaderWorkspace, route: WorkspaceRoute) => workspaceReducer(state, { type: 'navigate', route });
describe('reader workspace navigation', () => {
  it('activates an existing paper instead of duplicating a tab', () => {
    let state = go(go(emptyWorkspace(), paper('a')), paper('b'));
    state = go(state, paper('a'));
    expect(state.tabs.map(tab => tab.id)).toEqual(['a', 'b']);
    expect(state.route).toEqual(paper('a'));
  });
  it('restores a source collection with its folder/filter and branches history', () => {
    const source = { ...homeRoute(), filter: 'favorite', folder: 'research' };
    let state = go(go(emptyWorkspace(), source), paper('a'));
    state = workspaceReducer(state, { type: 'history', delta: -1 });
    expect(state.route).toEqual(source);
    state = go(state, paper('b'));
    expect(state.history.at(-1)).toEqual(paper('b'));
    expect(state.history).not.toContainEqual(paper('a'));
    expect(state.tabs.map(tab => tab.id)).toEqual(['a', 'b']);
  });
  it('closing the active tab removes stale history and selects a neighbor coherently', () => {
    let state = go(go(go(go(emptyWorkspace(), paper('a')), paper('b')), homeRoute()), paper('b'));
    state = workspaceReducer(state, { type: 'close', id: 'b' });
    expect(state.route).toEqual(paper('a'));
    expect(state.history[state.historyIndex]).toEqual(state.route);
    expect(state.history.some(route => route.kind === 'paper' && route.paperId === 'b')).toBe(false);
    state = workspaceReducer(state, { type: 'history', delta: -1 });
    expect(state.route.kind).toBe('collection');
  });
  it('closing an inactive tab preserves the active reader and closing the last returns home', () => {
    let state = go(go(emptyWorkspace(), paper('a')), paper('b'));
    state = workspaceReducer(state, { type: 'close', id: 'a' });
    expect(state.route).toEqual(paper('b'));
    state = workspaceReducer(state, { type: 'close', id: 'b' });
    expect(state.tabs).toEqual([]);
    expect(state.route).toEqual(homeRoute());
    expect(state.history[state.historyIndex]).toEqual(state.route);
  });
  it('keeps explicit resource locations in in-session history', () => {
    const located = { ...paper('a'), location: { page_index: 5, bbox: [10, 20, 100, 120] } } as WorkspaceRoute;
    let state = go(go(emptyWorkspace(), paper('a')), located);
    state = workspaceReducer(state, { type: 'history', delta: -1 });
    expect(state.route).toEqual(paper('a'));
    state = workspaceReducer(state, { type: 'history', delta: 1 });
    expect(state.route).toEqual(located);
  });
  it('bounds history and treats unchanged title updates as no-ops', () => {
    let state = emptyWorkspace();
    for (let index = 0; index < 80; index++) state = go(state, paper(String(index)));
    expect(state.history).toHaveLength(60);
    const titled = workspaceReducer(state, { type: 'title', id: '79', title: 'My paper' });
    expect(workspaceReducer(titled, { type: 'title', id: '79', title: 'My paper' })).toBe(titled);
  });
});

describe('safe workspace restoration', () => {
  it('ignores corrupt values and unsupported versions', () => {
    for (const value of [undefined, null, 'invalid', { version: 2 }, { version: 1, tabs: [{}], route: { kind: 'paper', paperId: 'missing' } }]) expect(restoreWorkspace(value)).toEqual(emptyWorkspace());
  });
  it('restores tabs but clears transient search highlights so persisted reading position wins', () => {
    const state = go(emptyWorkspace(), { kind: 'paper', paperId: 'a', annotationId: 'annotation', location: { page_index: 7 } });
    const restored = restoreWorkspace({ ...state, tabs: [...state.tabs, ...state.tabs] });
    expect(restored.tabs).toHaveLength(1);
    expect(restored.route).toEqual(paper('a'));
  });
  it('does not restore unsafe page locations or history pointing at closed tabs', () => {
    const state = go(emptyWorkspace(), paper('a'));
    const restored = restoreWorkspace({ ...state, route: { kind: 'paper', paperId: 'a', location: { page_index: -1 } }, history: [paper('gone')] });
    expect(restored.route).toEqual(homeRoute());
    expect(restored.history).toEqual([homeRoute()]);
  });
  it('separates two library IDs and two paths even for identical paper IDs', () => {
    expect(storageKey('id1:D:/a')).not.toBe(storageKey('id2:D:/a'));
    expect(storageKey('id1:D:/a')).not.toBe(storageKey('id1:D:/b'));
    expect(storageKey('id1:D:/a', 'view:search')).not.toBe(storageKey('id1:D:/a'));
  });
});
