import type { Holding } from '../../types';

export const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
export const money = (value?: number | null) => finite(value) ? `${value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN` : '—';
export const percent = (value?: number | null) => finite(value) ? `${value.toLocaleString('pl-PL', { maximumFractionDigits: 2, minimumFractionDigits: 2 })}%` : '—';
export const tone = (value?: number | null) => !finite(value) || value === 0 ? '' : value > 0 ? 'pr-positive' : 'pr-negative';
export const positionKey = (holding: Holding) => `${holding.portfolio_id}:${holding.sub_portfolio_id ?? ''}:${holding.id}:${holding.ticker}`;

// Aggregate instrument exposure across sub-portfolios before measuring concentration.
export function exposure(holdings: Holding[]) {
  const values = new Map<string, number>();
  holdings.forEach(h => {
    if (h.quantity > 0 && finite(h.current_value) && h.current_value > 0) values.set(h.ticker, (values.get(h.ticker) ?? 0) + h.current_value);
  });
  const total = [...values.values()].reduce((a, b) => a + b, 0);
  return [...values].map(([ticker, value]) => ({ ticker, value, weight: total > 0 ? value / total * 100 : 0 })).sort((a, b) => b.value - a.value);
}

export function filterPositions(holdings: Holding[], query: string, sector: string, result: string) {
  const needle = query.trim().toLocaleLowerCase('pl-PL');
  return holdings.filter(h => h.quantity > 0)
    .filter(h => !needle || [h.ticker, h.company_name, h.sector].some(v => v?.toLocaleLowerCase('pl-PL').includes(needle)))
    .filter(h => sector === 'all' || (h.sector || 'Unknown') === sector)
    .filter(h => result === 'all' || (finite(h.profit_loss) && (result === 'positive' ? h.profit_loss > 0 : h.profit_loss < 0)));
}
