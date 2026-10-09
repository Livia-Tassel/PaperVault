import { api, download, patch, post } from './api';
import type { Annotation, AnnotationColor, AnnotationKind } from './reading';
import type { Location } from './types';

export interface AnnotationValues {
  title: string; quote: string; body: string; color: AnnotationColor; tags: string[]; locations: Location[];
}
export const createAnnotation = (paperId: string, kind: AnnotationKind, values: AnnotationValues) =>
  post<Annotation>(`/papers/${paperId}/annotations`, { kind, ...values });
export const updateAnnotation = (id: string, version: number, values: Partial<AnnotationValues>) =>
  patch<Annotation>(`/annotations/${id}`, { ...values, expected_version: version });
export const removeAnnotation = (annotation: Annotation) =>
  api<Annotation>(`/annotations/${annotation.id}?expected_version=${annotation.version}`, { method: 'DELETE' });
export const restoreAnnotation = (annotation: Annotation) =>
  post<Annotation>(`/annotations/${annotation.id}/restore`, { expected_version: annotation.version });
export const exportAnnotations = (format: 'markdown' | 'json', ids: string[] = [], paperId?: string) =>
  download('/annotations/export', `PaperVault-notes.${format === 'markdown' ? 'md' : 'json'}`, { ids, paper_id: paperId, format });
