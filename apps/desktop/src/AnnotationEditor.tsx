import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Save } from 'lucide-react';
import { ApiError } from './api';
import { createAnnotation, updateAnnotation, type AnnotationValues } from './annotation-api';
import { changedFields } from './edits';
import { useDraftGuard } from './EditGuard';
import { annotationColors, annotationLabels, type Annotation, type AnnotationSelection } from './reading';
import { ErrorMessage, Field, splitTags } from './ui';
import type { Run } from './ResourceDetail';

type Draft = Omit<AnnotationValues, 'tags'> & { tags: string };
function draftOf(annotation: Annotation | AnnotationSelection): Draft {
  return { title: 'title' in annotation ? annotation.title : '', quote: annotation.quote || '',
    body: 'body' in annotation ? annotation.body : '', color: 'color' in annotation ? annotation.color : 'amber',
    tags: 'tags' in annotation ? annotation.tags.join(', ') : '', locations: annotation.locations };
}
const valuesOf = (draft: Draft): AnnotationValues => ({ ...draft, tags: splitTags(draft.tags) });

export function annotationPages(annotation: { locations: Annotation['locations'] }) {
  const pages = [...new Set(annotation.locations.map(location => location.page_index + 1))];
  return pages.length ? `第 ${pages.join('、')} 页` : '论文笔记';
}

export function AnnotationEditor({ paperId, annotation, selection, guardId, run, onSaved, onLocate, priority = 30 }: {
  paperId: string; annotation?: Annotation; selection?: AnnotationSelection; guardId: string; run: Run;
  onSaved: (annotation: Annotation) => void; onLocate?: (annotation: Annotation) => void;
  priority?: number;
}) {
  const initial = annotation || selection || { kind: 'note' as const, quote: '', locations: [] };
  const [draft, setDraft] = useState<Draft>(() => draftOf(initial));
  const baseline = useRef<Draft>(draft);
  const version = useRef(annotation?.version || 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState<Annotation | null>(null);
  const dirty = (!annotation && (!!draft.quote.trim() || draft.locations.length > 0)) ||
    !!Object.keys(changedFields(valuesOf(baseline.current), valuesOf(draft))).length;
  // A successful refresh updates a clean editor; an edited one retains its old
  // version so that a concurrent modification becomes an explicit 409 conflict.
  useEffect(() => {
    if (!annotation || dirty || annotation.version <= version.current) return;
    const next = draftOf(annotation); baseline.current = next; version.current = annotation.version; setDraft(next);
  }, [annotation, dirty]);
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft(current => ({ ...current, [key]: value }));
  const save = async (overrideVersion?: number) => {
    if (busy) return false;
    if (!annotation && !draft.body.trim() && !draft.title.trim() && !draft.quote.trim() && !draft.locations.length) {
      setError('请输入笔记内容、标题或选择原文位置。'); return false;
    }
    setBusy(true); setError('');
    const ok = await run(async () => {
      try {
        const values = valuesOf(draft);
        const next = annotation
          ? await updateAnnotation(annotation.id, overrideVersion ?? version.current, values)
          : await createAnnotation(paperId, initial.kind, values);
        const saved = draftOf(next); baseline.current = saved; version.current = next.version;
        setDraft(saved); setConflict(null); onSaved(next);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : String(reason));
        if (reason instanceof ApiError && reason.status === 409 && reason.current) setConflict(reason.current as Annotation);
        throw reason;
      }
    }, annotation ? '笔记已保存' : `${annotationLabels[initial.kind]}已添加`);
    setBusy(false); return ok;
  };
  const discard = () => {
    const next = draftOf(conflict || annotation || selection || initial);
    baseline.current = next; version.current = (conflict || annotation)?.version || 0;
    setDraft(next); setConflict(null); setError('');
  };
  useDraftGuard({ id: guardId, label: annotationLabels[initial.kind], dirty,
    onSave: () => save(), onDiscard: discard, priority });
  return <div className="annotation-editor">
    <div className="annotation-source"><span>{annotationLabels[initial.kind]} · {annotationPages(draft)}</span>
      {annotation && onLocate && <button className="text-button" onClick={() => onLocate(annotation)}><ExternalLink size={13} />查看原文</button>}
    </div>
    <ErrorMessage message={error} />
    {conflict && <div className="annotation-conflict" role="alert"><p>这条笔记已在其他位置更新，当前编辑内容仍保留。</p>
      <div className="inline-form"><button className="button secondary small" disabled={busy} onClick={discard}>载入最新记录</button>
        <button className="button secondary small" disabled={busy || conflict.deleted} onClick={() => void save(conflict.version)}>用当前内容更新</button></div></div>}
    <fieldset disabled={busy} className="annotation-fields">
      <Field label="笔记标题"><input value={draft.title} maxLength={500} onChange={event => set('title', event.target.value)} placeholder={initial.kind === 'bookmark' ? annotationPages(draft) : '标题（可选）'} /></Field>
      {!!(initial.quote || draft.quote) && <Field label="原文摘录"><textarea rows={3} value={draft.quote} maxLength={20000} onChange={event => set('quote', event.target.value)} /></Field>}
      <Field label="笔记内容"><textarea rows={6} value={draft.body} maxLength={100000} onChange={event => set('body', event.target.value)} placeholder="笔记" /></Field>
      <div className="annotation-color-row"><span>颜色</span><div className="annotation-colors" role="group" aria-label="标注颜色">
        {Object.entries(annotationColors).map(([color, label]) => <button type="button" key={color} aria-label={label} aria-pressed={draft.color === color}
          title={label} className={`annotation-swatch color-${color} ${draft.color === color ? 'selected' : ''}`}
          onClick={() => set('color', color as Annotation['color'])} />)}
      </div></div>
      <Field label="笔记标签"><input value={draft.tags} onChange={event => set('tags', event.target.value)} placeholder="逗号分隔" /></Field>
      <div className="annotation-save-row"><span className="muted">{dirty ? '未保存' : annotation ? '已保存' : ''}</span>
        <button className="button primary" type="button" disabled={busy || (!!annotation && !dirty)} onClick={() => void save()}><Save size={14} />{busy ? '保存中…' : '保存笔记'}</button></div>
    </fieldset>
  </div>;
}
