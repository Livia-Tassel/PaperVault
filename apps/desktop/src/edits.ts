/** Only changed fields become manual overrides; untouched extraction stays automatic. */
export function changedFields<T extends object>(previous: T, next: T): Partial<T> {
  return Object.fromEntries(Object.entries(next).filter(([key, value]) =>
    JSON.stringify(value) !== JSON.stringify(previous[key as keyof T]))) as Partial<T>;
}
