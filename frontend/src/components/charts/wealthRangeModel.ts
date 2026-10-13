import type { WealthPoint } from '../../api_charts';
export type WealthRange = '1M' | '3M' | '6M' | '1Y' | 'ALL';
export const wealthRanges: { key: WealthRange; label: string; months: number }[] = [
  { key: '1M', label: '1 mies.', months: 1 }, { key: '3M', label: '3 mies.', months: 3 },
  { key: '6M', label: '6 mies.', months: 6 }, { key: '1Y', label: '1 rok', months: 12 },
  { key: 'ALL', label: 'Cała historia', months: 0 },
];
export function wealthRange(points: WealthPoint[], range: WealthRange, today: string) {
  const months = wealthRanges.find(r => r.key === range)!.months;
  const [year, month, day] = today.split('-').map(Number);
  const startMonth = new Date(year, month - 1 - months, 1);
  const lastDay = new Date(startMonth.getFullYear(), startMonth.getMonth() + 1, 0).getDate();
  const from = months ? `${startMonth.getFullYear()}-${String(startMonth.getMonth() + 1).padStart(2, '0')}-${String(Math.min(day, lastDay)).padStart(2, '0')}` : null;
  const available = points.filter(p => p.date <= today).sort((a, b) => a.date.localeCompare(b.date));
  return { from, to: today, firstAvailable: available[0]?.date,
    points: available.filter(p => !from || p.date >= from) };
}
