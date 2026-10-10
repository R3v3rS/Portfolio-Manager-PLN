import type { JournalKind, JournalStatus, ReviewOutcome } from '../../api_journal';
export const kinds:Record<JournalKind,string> = {IDEA:'Pomysł',BUY:'Zakup',ADD:'Zwiększenie pozycji',HOLD:'Utrzymanie',REDUCE:'Zmniejszenie pozycji',SELL:'Sprzedaż',NOTE:'Obserwacja'};
export const statuses:Record<JournalStatus,string> = {WATCHING:'Do obserwacji',ACTIVE:'Aktywna teza',CLOSED:'Zamknięta teza'};
export const outcomes:Record<ReviewOutcome,string> = {NOTE:'Notatka z przeglądu',CONFIRMED:'Teza potwierdzona',CHANGED:'Teza wymaga zmiany',INVALIDATED:'Teza podważona'};
export const localToday = () => new Date().toLocaleDateString('sv-SE');
export const dateText = (day:string|null) => day ? new Date(day.slice(0,10)+'T12:00:00').toLocaleDateString('pl-PL') : 'Bez terminu';
