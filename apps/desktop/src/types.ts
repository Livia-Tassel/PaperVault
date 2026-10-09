export interface Location { [key: string]: unknown; page_index: number; bbox?: [number, number, number, number] | null; coordinate_system?: string; page_width?: number; page_height?: number }
export interface Paper extends WirePaper {
  id: string; title: string | null; filename: string; authors: string[]; abstract: string;
  year: number | null; venue: string; doi: string; arxiv_id: string; keywords: string[];
  tags: string[]; folders: string[]; favorite: boolean; notes: string; status: string;
  figure_count: number; table_count: number; sections: Array<{ title?: string; text?: string; level?: number; page_index?: number; location?: Location }>;
  references: Array<string | { text: string }>; warnings: string[]; created_at: string;
  similar_papers?: Array<{ id: string; title: string; reason: string }>;
}
export interface TableCell { [key: string]: unknown; text: string; row?: number; col?: number; row_span?: number; col_span?: number; row_start?: number; col_start?: number; column_header?: boolean; is_header?: boolean }
export interface TableData { [key: string]: unknown; rows: string[][]; cells?: TableCell[]; header_rows: number; num_rows?: number; num_cols?: number }
export interface Resource extends WireResource {
  id: string; paper_id: string; paper_title: string; kind: 'figure' | 'table'; number: string; name: string; caption: string;
  locations: Location[]; tags: string[]; notes: string; table: TableData | null;
  files: Record<string, string>; warnings: string[]; needs_review: boolean;
}
export interface Job { id: string; paper_id: string; paper_title: string; status: string; phase: string; pages_done?: number; pages_total?: number; resources_count?: number; error?: string; created_at?: string }
export interface Library { path: string | null; paper_count: number; figure_count: number; table_count: number }
export interface Folder { id: string; name: string; paper_count?: number }
export interface Paged<T> { items: T[]; total: number }
export interface SnippetPart { text: string; matched: boolean }
export interface SearchHit { id: string; paper_id?: string; resource_id?: string; title?: string; paper_title?: string; caption?: string; text?: string; snippet?: SnippetPart[] | string; location?: Location; locations?: Location[]; page_index?: number; kind?: string }
export interface SearchResults { papers: SearchHit[]; figures: SearchHit[]; tables: SearchHit[]; content: SearchHit[] }
export interface ModelState { phase?: string; bytes_done?: number; bytes_total?: number; downloaded_files?: number; total_files?: number; current_file?: string; status?: string; ready?: boolean; path?: string; error?: string; progress?: number | null; downloaded_bytes?: number; total_bytes?: number; message?: string; files?: Array<{ name: string; status: string }> }
export interface ImportResult { items: unknown[]; duplicates: unknown[]; errors: Array<string | { path?: string; filename?: string; error: string }> }
import type { components } from './api.generated';
export type LibraryOpenRequest = components['schemas']['LibraryOpen'];
export type PaperPatch = components['schemas']['PaperPatch'];
export type ResourcePatch = components['schemas']['ResourcePatch'];
export type CropRequest = components['schemas']['CropRequest'];
export type ExportRequest = components['schemas']['ExportRequest'];
type WirePaper = components['schemas']['Paper'];
type WireResource = Omit<components['schemas']['Resource'], 'table' | 'locations'>;
