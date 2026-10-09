import { invoke, isTauri } from '@tauri-apps/api/core';
import type { CropRequest, ExportRequest, Library, LibraryOpenRequest, Paper, PaperPatch, Resource, ResourcePatch } from './types';

export const native = isTauri();
interface Connection { baseUrl: string; token: string }
let current: Promise<Connection> | undefined;
let activeLibraryScope = '';
export const setLibraryScope = (scope: string) => { activeLibraryScope = scope; };
export const getLibraryScope = () => activeLibraryScope;
export type ApiRequestOptions = RequestInit & { libraryScope?: string };

export function connection(): Promise<Connection> {
  if (!current) current = native
    ? invoke<Connection>('backend_connection').catch(error => { current = undefined; throw error; })
    : Promise.resolve({ baseUrl: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8765/api/v1', token: import.meta.env.VITE_API_TOKEN || 'dev-token' });
  return current;
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public current?: unknown) { super(message); }
}
export async function request(path: string, options: ApiRequestOptions = {}): Promise<Response> {
  // Capture before the asynchronous IPC handshake. Deferred reader writes pass
  // their original scope explicitly, so a restored copy cannot receive them.
  const scope = options.libraryScope ?? activeLibraryScope;
  const { baseUrl, token } = await connection();
  const headers = new Headers(options.headers);
  headers.set('Authorization', `Bearer ${token}`);
  if (scope && ['POST', 'PATCH', 'DELETE'].includes(options.method || '') && path !== '/library/open' && !path.startsWith('/models/'))
    headers.set('X-PaperVault-Library', encodeURIComponent(scope));
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  let response: Response;
  try { response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, { ...options, headers }); }
  catch (error) { if (error instanceof DOMException && error.name === 'AbortError') throw error; throw new ApiError('无法连接本地服务。请确认 PaperVault 后端已启动，然后重试。', 0); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail || body.error || `请求失败 (${response.status})`;
    throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), response.status, body.current);
  }
  return response;
}
export async function api<T>(path: string, options?: ApiRequestOptions): Promise<T> {
  const response = await request(path, options);
  return response.status === 204 ? undefined as T : await response.json() as T;
}
export const post = <T,>(path: string, data?: unknown, options?: ApiRequestOptions) => api<T>(path, { ...options, method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) });
export const patch = <T,>(path: string, data: unknown, options?: ApiRequestOptions) => api<T>(path, { ...options, method: 'PATCH', body: JSON.stringify(data) });
export const openLibrary = (data: LibraryOpenRequest) => post<Library>('/library/open', data);
export const updatePaper = (id: string, data: PaperPatch) => patch<Paper>(`/papers/${id}`, data);
export const updateResource = (id: string, data: ResourcePatch) => patch<Resource>(`/resources/${id}`, data);
export const cropResource = (id: string, data: CropRequest) => post<Resource>(`/resources/${id}/crop`, data);
export const addResource = (paperId: string, data: CropRequest) => post<Resource>(`/papers/${paperId}/resources`, data);
export const exportAssets = (data: ExportRequest, filename: string) => download('/exports', filename, data);
export function query(values: Record<string, string | number | boolean | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== '') params.set(key, String(value)); });
  return params.toString() ? `?${params}` : '';
}
export async function saveBlob(blob: Blob, filename: string): Promise<boolean> {
  if (native) {
    const { save } = await import('@tauri-apps/plugin-dialog');
    const path = await save({ defaultPath: filename });
    if (!path) return false;
    const { writeFile } = await import('@tauri-apps/plugin-fs');
    await writeFile(path, new Uint8Array(await blob.arrayBuffer()));
    return true;
  }
  const href = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = href; a.download = filename; a.click();
  window.setTimeout(() => URL.revokeObjectURL(href), 30000);
  return true;
}
export async function download(path: string, filename: string, data?: unknown): Promise<boolean> {
  const response = await request(path, data === undefined ? undefined : { method: 'POST', body: JSON.stringify(data) });
  return saveBlob(await response.blob(), filename);
}
export async function copyText(text: string): Promise<void> {
  if (native) { const { writeText } = await import('@tauri-apps/plugin-clipboard-manager'); await writeText(text); }
  else await navigator.clipboard.writeText(text);
}
export async function copyImage(path: string): Promise<void> {
  const blob = await (await request(path)).blob();
  if (native) {
    const { writeImage } = await import('@tauri-apps/plugin-clipboard-manager');
    const { Image } = await import('@tauri-apps/api/image');
    const image = await Image.fromBytes(new Uint8Array(await blob.arrayBuffer()));
    try { await writeImage(image); } finally { await image.close(); }
  } else await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
}
export async function chooseDirectory(title: string): Promise<string | null> {
  if (!native) return null;
  const { open } = await import('@tauri-apps/plugin-dialog');
  return await open({ directory: true, multiple: false, title }) as string | null;
}
