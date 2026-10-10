import type { Holding } from '../../types';
export type AllocationGroup = 'instrument' | 'sector' | 'industry' | 'currency';
export function allocationRows(holdings: Holding[], cash: number, group: AllocationGroup, includeCash: boolean) {
  const buckets = new Map<string, number>();
  const missing: string[] = [];
  for (const holding of holdings) {
    if (holding.quantity <= 0) continue;
    if (holding.current_value == null || !Number.isFinite(holding.current_value) || holding.current_value < 0) { missing.push(holding.ticker); continue; }
    const raw = group === 'instrument' ? holding.ticker : group === 'sector' ? holding.sector : group === 'industry' ? holding.industry : holding.currency;
    const name = raw && raw !== 'Unknown' ? raw : 'Nieprzypisane';
    buckets.set(name, (buckets.get(name) ?? 0) + holding.current_value);
  }
  if (includeCash && Number.isFinite(cash) && cash > 0) buckets.set('Gotówka', cash);
  const total = Array.from(buckets.values()).reduce((sum, value) => sum + value, 0);
  return { missing, total, rows: Array.from(buckets, ([name, value]) => ({ name, value, share: total > 0 ? value / total * 100 : 0 })).sort((a, b) => b.value - a.value || a.name.localeCompare(b.name)) };
}
