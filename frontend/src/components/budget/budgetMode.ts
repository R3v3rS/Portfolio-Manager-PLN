import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';

// Deliberately kept in memory: route changes retain the mode; reopening the app starts safely in browsing.
let management = false;
const listeners = new Set<() => void>();
const drafts = new Set<() => boolean>();
const checkedClicks = new WeakSet<MouseEvent>();
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
export function confirmBudgetNavigation() {
  return ![...drafts].some(dirty => dirty()) || window.confirm('Masz niezapisane zmiany. Opuścić edycję i je odrzucić?');
}
export function setBudgetManagement(value: boolean) {
  if (value === management) return true;
  if (!value && !confirmBudgetNavigation()) return false;
  management = value;
  listeners.forEach(listener => listener());
  return true;
}
export function useBudgetMode() {
  return { management: useSyncExternalStore(subscribe, () => management, () => false), setManagement: setBudgetManagement };
}
export function useBudgetDraftGuard(dirty: boolean) {
  const current = useRef(dirty);
  current.current = dirty;
  useEffect(() => {
    const check = () => current.current;
    drafts.add(check);
    const unload = (event: BeforeUnloadEvent) => { if (current.current) { event.preventDefault(); event.returnValue = ''; } };
    const click = (event: MouseEvent) => {
      if (!current.current || event.defaultPrevented || checkedClicks.has(event) || !(event.target instanceof Element)) return;
      const link = event.target.closest('a[href]');
      if (link) { checkedClicks.add(event); if (!confirmBudgetNavigation()) { event.preventDefault(); event.stopPropagation(); } }
    };
    window.addEventListener('beforeunload', unload);
    document.addEventListener('click', click, true);
    return () => { drafts.delete(check); window.removeEventListener('beforeunload', unload); document.removeEventListener('click', click, true); };
  }, []);
}

/** Compare values, not keystrokes: reverting a form to its initial values clears its warning. */
export function useBudgetFormGuard(value: unknown) {
  const snapshot = JSON.stringify(value);
  const initial = useRef(snapshot);
  const dirty = initial.current !== snapshot;
  useBudgetDraftGuard(dirty);
  return useCallback(() => !dirty || window.confirm('Odrzucić niezapisane zmiany formularza?'), [dirty]);
}
