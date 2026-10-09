import React, { useEffect, useRef, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { PdfViewer } from '../src/PdfViewer';
import type { Annotation, AnnotationSelection, ReaderViewState } from '../src/reading';
import type { Location } from '../src/types';
import '../src/styles.css';

let mounted: Root | undefined;
export function mountReader(options: { initialState?: ReaderViewState; location?: Location; annotations?: Annotation[] } = {}) {
  mounted?.unmount();
  document.getElementById('reader-test-root')?.remove();
  const host = document.createElement('div'); host.id = 'reader-test-root';
  host.style.cssText = 'position:fixed;inset:0;z-index:999;display:flex;background:white'; document.body.append(host);
  function Harness() {
    const [annotations, setAnnotations] = useState<Annotation[]>(options.annotations || []);
    const [location, setLocation] = useState(options.location);
    const [cropMode, setCropMode] = useState(false);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const state = useRef<{ latest: ReaderViewState | null; views: ReaderViewState[]; selections: AnnotationSelection[]; crops: Location[] }>({ latest: null, views: [], selections: [], crops: [] });
    useEffect(() => {
      Object.assign(window, { readerHarness: {
        snapshot: () => ({ ...state.current, annotations }),
        location: (value: Location) => setLocation({ ...value }),
        annotations: (value: Annotation[]) => setAnnotations(value),
      } });
    }, [annotations]);
    const add = (selection: AnnotationSelection) => {
      state.current.selections.push(selection);
      const annotation: Annotation = { id: `test-${state.current.selections.length}`, paper_id: 'reader-fixture', paper_title: 'Reader fixture', ...selection,
        title: '', body: '', color: 'amber', tags: [], version: 1, deleted: false, created_at: '', updated_at: '' };
      setAnnotations(values => [...values, annotation]); setSelectedId(annotation.id);
    };
    return <PdfViewer paperId="reader-fixture" initialState={options.initialState} location={location} cropMode={cropMode} onCropMode={setCropMode}
      onCrop={value => state.current.crops.push(value)} annotations={annotations} selectedAnnotationId={selectedId} onAnnotationSelect={annotation => setSelectedId(annotation.id)}
      onAnnotate={add} onViewState={value => { state.current.latest = value; state.current.views.push(value); }}
      onBookmark={pageIndex => {
        const old = annotations.find(annotation => annotation.kind === 'bookmark' && annotation.locations[0]?.page_index === pageIndex);
        if (old) setAnnotations(values => values.filter(annotation => annotation.id !== old.id)); else add({ kind: 'bookmark', quote: '', locations: [{ page_index: pageIndex, bbox: null }] });
      }} />;
  }
  mounted = createRoot(host); mounted.render(<Harness />);
}
