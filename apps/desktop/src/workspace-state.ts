import type { Location } from './types';

export type WorkspacePage = 'papers' | 'figures' | 'tables' | 'search' | 'jobs' | 'settings' | 'notes';
export interface CollectionRoute { kind: 'collection'; page: WorkspacePage; filter: string; folder: string }
export interface PaperRoute { kind: 'paper'; paperId: string; location?: Location | null; annotationId?: string | null }
export type WorkspaceRoute = CollectionRoute | PaperRoute;
export interface ReaderTab { id: string; title: string }
export interface ReaderWorkspace {
  version: 1;
  tabs: ReaderTab[];
  collection: CollectionRoute;
  route: WorkspaceRoute;
  history: WorkspaceRoute[];
  historyIndex: number;
}
export const homeRoute = (): CollectionRoute => ({ kind: 'collection', page: 'papers', filter: 'all', folder: '' });
export function emptyWorkspace(): ReaderWorkspace {
  const route = homeRoute();
  return { version: 1, tabs: [], collection: route, route, history: [route], historyIndex: 0 };
}
const pages = new Set(['papers', 'figures', 'tables', 'search', 'jobs', 'settings', 'notes']);
function validRoute(value: unknown): value is WorkspaceRoute {
  if (!value || typeof value !== 'object') return false;
  const route = value as Record<string, unknown>;
  if (route.kind === 'collection') return typeof route.page === 'string' && pages.has(route.page) && typeof route.filter === 'string' && typeof route.folder === 'string';
  if (route.kind !== 'paper' || typeof route.paperId !== 'string' || !route.paperId) return false;
  if (route.annotationId != null && typeof route.annotationId !== 'string') return false;
  if (route.location != null) {
    const location = route.location as Location;
    if (!Number.isInteger(location.page_index) || location.page_index < 0) return false;
    if (location.bbox != null && (!Array.isArray(location.bbox) || location.bbox.length !== 4 || !location.bbox.every(Number.isFinite))) return false;
  }
  return true;
}
export function restoreWorkspace(value: unknown): ReaderWorkspace {
  if (!value || typeof value !== 'object' || (value as ReaderWorkspace).version !== 1) return emptyWorkspace();
  const stored = value as ReaderWorkspace;
  const tabs = Array.isArray(stored.tabs) ? stored.tabs.filter(tab => tab && typeof tab.id === 'string' && tab.id && typeof tab.title === 'string')
    .filter((tab, index, all) => all.findIndex(other => other.id === tab.id) === index).slice(0, 100).map(tab => ({ id: tab.id, title: tab.title.slice(0, 300) })) : [];
  const collection = validRoute(stored.collection) && stored.collection.kind === 'collection' ? stored.collection : homeRoute();
  const usable = (route: unknown): route is WorkspaceRoute => validRoute(route) && (route.kind === 'collection' || tabs.some(tab => tab.id === route.paperId));
  const route = usable(stored.route) ? stored.route : collection;
  // Reopen a reader at its last reading position, not at yesterday's search highlight.
  const resumed = (entry: WorkspaceRoute): WorkspaceRoute => entry.kind === 'paper' ? { kind: 'paper', paperId: entry.paperId } : entry;
  const history = Array.isArray(stored.history) ? stored.history.filter(usable).slice(-60).map(resumed) : [];
  const savedIndex = Number.isInteger(stored.historyIndex) ? stored.historyIndex : history.length - 1;
  const historyIndex = Math.max(0, Math.min(savedIndex, history.length - 1));
  if (!history.length || JSON.stringify(history[historyIndex]) !== JSON.stringify(resumed(route))) return { version: 1, tabs, collection, route: resumed(route), history: [resumed(route)], historyIndex: 0 };
  return { version: 1, tabs, collection, route: resumed(route), history, historyIndex };
}
export type WorkspaceAction =
  | { type: 'navigate'; route: WorkspaceRoute; title?: string }
  | { type: 'history'; delta: -1 | 1 }
  | { type: 'close'; id: string }
  | { type: 'title'; id: string; title: string }
  | { type: 'remove'; ids: string[] };
export function workspaceReducer(state: ReaderWorkspace, action: WorkspaceAction): ReaderWorkspace {
  if (action.type === 'title') {
    if (!action.title || state.tabs.find(tab => tab.id === action.id)?.title === action.title) return state;
    return { ...state, tabs: state.tabs.map(tab => tab.id === action.id ? { ...tab, title: action.title } : tab) };
  }
  if (action.type === 'remove') return action.ids.reduce((next, id) => workspaceReducer(next, { type: 'close', id }), state);
  if (action.type === 'close') {
    const oldIndex = state.tabs.findIndex(tab => tab.id === action.id);
    const tabs = state.tabs.filter(tab => tab.id !== action.id);
    const nextTab = tabs[Math.max(0, Math.min(oldIndex, tabs.length - 1))];
    const route = state.route.kind === 'paper' && state.route.paperId === action.id ? nextTab ? { kind: 'paper' as const, paperId: nextTab.id } : state.collection : state.route;
    const history = state.history.filter(entry => entry.kind !== 'paper' || entry.paperId !== action.id);
    const before = state.history.slice(0, state.historyIndex + 1).filter(entry => entry.kind !== 'paper' || entry.paperId !== action.id).length;
    const historyIndex = Math.max(0, before - 1);
    const base = { ...state, tabs, route, history: history.length ? history : [state.collection], historyIndex };
    if (JSON.stringify(base.history[historyIndex]) === JSON.stringify(route)) return base;
    const nextHistory = [...base.history.slice(0, historyIndex + 1), route].slice(-60);
    return { ...base, history: nextHistory, historyIndex: nextHistory.length - 1 };
  }
  if (action.type === 'history') {
    const historyIndex = Math.max(0, Math.min(state.history.length - 1, state.historyIndex + action.delta));
    const route = state.history[historyIndex];
    return { ...state, historyIndex, route, collection: route.kind === 'collection' ? route : state.collection };
  }
  const route = action.route;
  const tabs = route.kind === 'paper' && !state.tabs.some(tab => tab.id === route.paperId) ? [...state.tabs, { id: route.paperId, title: action.title || '正在打开论文…' }] : state.tabs;
  const collection = route.kind === 'collection' ? route : state.collection;
  const same = JSON.stringify(state.route) === JSON.stringify(route);
  if (same) return { ...state, tabs, collection, route };
  const history = [...state.history.slice(0, state.historyIndex + 1), route].slice(-60);
  return { ...state, tabs, route, collection, history, historyIndex: history.length - 1 };
}

export function storageKey(libraryKey: string, suffix = 'session') { return `papervault:workspace:v1:${encodeURIComponent(libraryKey)}:${suffix}`; }
export function readStorage(key: string): unknown {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : undefined; } catch { return undefined; }
}
export function writeStorage(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Reading remains available if storage is full or denied. */ }
}
