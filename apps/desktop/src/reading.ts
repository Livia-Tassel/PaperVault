import type { Location } from './types';
import type { components } from './api.generated';

type WireAnnotation = components['schemas']['Annotation'];
type WireReadingState = components['schemas']['ReadingState'];
export type AnnotationKind = WireAnnotation['kind'];
export type AnnotationColor = NonNullable<WireAnnotation['color']>;
export type ReadingStatus = WireReadingState['status'];

export interface ReaderViewState {
  page_index: number;
  anchor: [number, number] | null;
  scale: number;
  rotation: 0 | 90 | 180 | 270;
  fit_mode: 'custom' | 'width' | 'page';
}

export interface ReadingState extends WireReadingState {
  paper_id: string;
  status: ReadingStatus;
  last_opened: string | null;
  version: number;
  rotation: ReaderViewState['rotation'];
}

export interface Annotation extends WireAnnotation {
  id: string;
  paper_id: string;
  paper_title: string;
  kind: AnnotationKind;
  title: string;
  quote: string;
  body: string;
  color: AnnotationColor;
  tags: string[];
  locations: Location[];
  version: number;
  deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface AnnotationSelection {
  kind: AnnotationKind;
  quote: string;
  locations: Location[];
}

export const annotationLabels: Record<AnnotationKind, string> = {
  bookmark: '书签', highlight: '高亮', note: '笔记',
};
export const annotationColors: Record<AnnotationColor, string> = {
  amber: '黄色', green: '绿色', blue: '蓝色', pink: '粉色', purple: '紫色',
};
export const readingStatusLabels: Record<ReadingStatus, string> = {
  unread: '未读', reading: '在读', read: '已读',
};
