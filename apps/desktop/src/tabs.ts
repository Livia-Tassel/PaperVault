import type { KeyboardEvent } from 'react';

/** Manual activation keeps arrow navigation instant while a PDF is loading. */
export function handleTabKeys(event: KeyboardEvent<HTMLElement>) {
  if (event.nativeEvent.isComposing || event.ctrlKey || event.metaKey || event.altKey ||
      !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const source = (event.target as HTMLElement).closest<HTMLElement>('[role="tab"]');
  if (!source) return;
  const tabs = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')].filter(tab => !tab.disabled);
  const index = tabs.indexOf(source as HTMLButtonElement);
  if (index < 0 || !tabs.length) return;
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 :
    (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
  event.preventDefault(); event.stopPropagation(); tabs[next].focus();
}
