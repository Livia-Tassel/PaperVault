/** Only changed fields become manual overrides; untouched extraction stays automatic. */
export function changedFields<T extends object>(previous: T, next: T): Partial<T> {
  return Object.fromEntries(Object.entries(next).filter(([key, value]) =>
    JSON.stringify(value) !== JSON.stringify(previous[key as keyof T]))) as Partial<T>;
}

/** Advance server values while preserving fields edited since the last baseline. */
export function mergeUntouchedFields<T extends object>(baseline: T, draft: T, incoming: T): T {
  const merged = { ...draft };
  for (const key of Object.keys(incoming) as Array<keyof T>) {
    if (JSON.stringify(draft[key]) === JSON.stringify(baseline[key])) merged[key] = incoming[key];
  }
  return merged;
}
