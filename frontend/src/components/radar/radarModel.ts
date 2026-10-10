import type { RadarItem, RadarNotes } from '../../types';

export const emptyNotes: RadarNotes = { thesis: '', invalidation: '', review_date: null, target_price: null, target_direction: 'below' };
export const number = (value: number | null | undefined, digits = 2) =>
  value == null || !Number.isFinite(value) ? '—' : value.toLocaleString('pl-PL', { maximumFractionDigits: digits, minimumFractionDigits: digits });
export const change = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? '—' : `${value > 0 ? '+' : ''}${number(value)}%`;
export const tone = (value: number | null | undefined) => value == null || value === 0 ? '' : value > 0 ? 'rd-positive' : 'rd-negative';
export const dateText = (value: string | null | undefined) => value && Number.isFinite(new Date(value).getTime()) ? new Date(value).toLocaleDateString('pl-PL') : 'Brak daty';
export const localDate = (now = new Date()) => `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
export function dataStatus(item: RadarItem, now = Date.now()): 'missing' | 'stale' | 'recent' {
  if (item.price == null || item.price <= 0 || !Number.isFinite(item.price)) return 'missing';
  const updated = item.last_updated_at ? new Date(item.last_updated_at).getTime() : NaN;
  return !Number.isFinite(updated) || updated > now + 300_000 || now - updated > 72 * 3600_000 ? 'stale' : 'recent';
}
export function targetReached(item: RadarItem, now = Date.now()) {
  const target = item.notes?.target_price;
  if (target == null || target <= 0 || item.price == null || dataStatus(item, now) !== 'recent') return false;
  return item.notes?.target_direction === 'above' ? item.price >= target : item.price <= target;
}
export function needsAttention(item: RadarItem, now = Date.now()) {
  return dataStatus(item, now) !== 'recent' || targetReached(item, now) || Boolean(item.notes?.review_date && item.notes.review_date <= localDate(new Date(now)));
}
export function upcomingEvents(items: RadarItem[], now = new Date()) {
  const today = localDate(now);
  const staleEvents = (item: RadarItem) => {
    const updated = new Date(item.events_updated_at || '').getTime();
    return !Number.isFinite(updated) || updated > now.getTime() || now.getTime() - updated > 7 * 86400_000;
  };
  return items.flatMap(item => [
    { ticker: item.ticker, date: item.next_earnings, kind: 'Raport wynikowy', stale: staleEvents(item) },
    { ticker: item.ticker, date: item.ex_dividend_date, kind: 'Odcięcie dywidendy', stale: staleEvents(item) },
    { ticker: item.ticker, date: item.notes?.review_date, kind: 'Twój przegląd', stale: false },
  ].filter((event): event is typeof event & { date: string } => Boolean(event.date && /^\d{4}-\d{2}-\d{2}/.test(event.date) && event.date.slice(0, 10) >= today)))
    .sort((a, b) => a.date.localeCompare(b.date));
}
export type HistoryPoint = { date: string; close_price: number };
export function comparisonSeries(histories: Record<string, HistoryPoint[]>, tickers: string[], days: number, now = new Date()) {
  if (!tickers.length) return [];
  const cutoff = new Date(now); cutoff.setDate(cutoff.getDate() - days);
  const start = localDate(cutoff), end = localDate(now);
  const maps = tickers.map(ticker => new Map((histories[ticker] || [])
    .filter(point => point.date >= start && point.date <= end && Number.isFinite(point.close_price) && point.close_price > 0)
    .map(point => [point.date, point.close_price])));
  const dates = [...maps[0].keys()].filter(date => maps.every(map => map.has(date))).sort();
  if (dates.length < 2) return [];
  return dates.map(date => Object.fromEntries([['date', date], ...tickers.map((ticker, i) => [ticker, (maps[i].get(date)! / maps[i].get(dates[0])! - 1) * 100])])) as Array<{ date: string } & Record<string, string | number>>;
}
