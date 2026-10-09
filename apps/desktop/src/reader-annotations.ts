import type { Annotation } from './reading';
import type { Location } from './types';

export interface PageAnnotation { annotation: Annotation; locations: Location[] }

/** Build once per annotation snapshot. A cross-page record has one entry per page. */
export function indexAnnotationsByPage(annotations: readonly Annotation[]): Map<number, PageAnnotation[]> {
  const pages = new Map<number, PageAnnotation[]>();
  for (const annotation of annotations) {
    if (annotation.deleted) continue;
    const locationsByPage = new Map<number, Location[]>();
    for (const location of annotation.locations) {
      const locations = locationsByPage.get(location.page_index);
      if (locations) locations.push(location); else locationsByPage.set(location.page_index, [location]);
    }
    for (const [index, locations] of locationsByPage) {
      const entry = { annotation, locations }, entries = pages.get(index);
      if (entries) entries.push(entry); else pages.set(index, [entry]);
    }
  }
  return pages;
}
