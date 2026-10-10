import type { AssetAllocation, AssetClass, GoalPortfolio } from '../../api_goals';

export const assetClasses: { key: AssetClass; name: string; color: string }[] = [
  { key: 'stocks', name: 'Akcje i ETF-y', color: '#67ded2' },
  { key: 'bonds', name: 'Obligacje', color: '#e5bc70' },
  { key: 'ppk', name: 'PPK', color: '#b1a1f5' },
  { key: 'savings', name: 'Oszczędności', color: '#80b8ef' },
  { key: 'cash', name: 'Gotówka inwestycyjna', color: '#8fa9b3' },
];
export const emptyAllocation = (): AssetAllocation => ({ stocks: 0, bonds: 0, ppk: 0, savings: 0, cash: 0 });
export const goalMoney = (value: number | null) => value === null || !Number.isFinite(value) ? 'Brak pełnej wyceny' : `${value.toLocaleString('pl-PL', { maximumFractionDigits: 2, minimumFractionDigits: 2 })} PLN`;
export const goalPercent = (value: number) => `${value.toLocaleString('pl-PL', { maximumFractionDigits: 1 })}%`;
export const localToday = () => new Date().toLocaleDateString('sv-SE');
const parseDate = (value: string) => new Date(value + 'T00:00:00Z');
const isoDate = (value: Date) => value.toISOString().slice(0, 10);
const daysBetween = (a: string, b: string) => (parseDate(b).getTime() - parseDate(a).getTime()) / 86400000;

/** Contributions on monthly anniversaries, at the end of each growth interval. */
export function projectGoal(initial: number, monthly: number, annualPercent: number, end: string, start = localToday()) {
  if (![initial, monthly, annualPercent].every(Number.isFinite) || monthly < 0 || annualPercent <= -100 || !/^\d{4}-\d{2}-\d{2}$/.test(end) || !/^\d{4}-\d{2}-\d{2}$/.test(start)) throw new Error('Nieprawidłowe założenia symulacji.');
  const beginning = parseDate(start);
  if (!Number.isFinite(beginning.getTime()) || !Number.isFinite(parseDate(end).getTime())) throw new Error('Nieprawidłowe daty symulacji.');
  const dates: string[] = [];
  for (let month = 1; month <= 732; month++) {
    const first = new Date(Date.UTC(beginning.getUTCFullYear(), beginning.getUTCMonth() + month, 1));
    const lastDay = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
    const payment = isoDate(new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), Math.min(beginning.getUTCDate(), lastDay))));
    if (payment > end) break;
    dates.push(payment);
  }
  const growth = (from: string, to: string) => (1 + annualPercent / 100) ** (daysBetween(from, to) / 365.2425);
  const points = [{ date: start, value: initial }];
  let value = initial, last = start;
  for (const payment of dates) {
    value = value * growth(last, payment) + monthly;
    points.push({ date: payment, value });
    last = payment;
  }
  if (end > last) { value *= growth(last, end); points.push({ date: end, value }); }
  const horizon = end > start ? end : start;
  return { points, final: value, contributionCount: dates.length, paidIn: monthly * dates.length,
    initialAtEnd: initial * growth(start, horizon), contributionFactor: dates.reduce((sum, payment) => sum + growth(payment, horizon), 0) };
}

export function requiredMonthly(initial: number, target: number, annual: number, end: string, start = localToday()) {
  const model = projectGoal(initial, 0, annual, end, start);
  const gap = target - model.initialAtEnd;
  return gap <= 0 ? 0 : model.contributionFactor > 0 ? Math.ceil(gap / model.contributionFactor * 100) / 100 : null;
}

/** Cent-preserving split according to deficits against the user's own target. */
export function allocateDeposit(current: AssetAllocation, targets: AssetAllocation, amount: number) {
  const total = Object.values(current).reduce((sum, value) => sum + value, 0);
  if (!Number.isFinite(amount) || amount < 0 || Object.values(current).some(value => !Number.isFinite(value) || value < 0) || Object.values(targets).some(value => !Number.isFinite(value) || value < 0) || Math.abs(Object.values(targets).reduce((sum, value) => sum + value, 0) - 100) > .001) throw new Error('Nieprawidłowa struktura lub kwota wpłaty.');
  const cents = Math.round(amount * 100);
  const newTotal = total + cents / 100;
  const weights = assetClasses.map(({ key }) => Math.max(newTotal * targets[key] / 100 - current[key], 0));
  const sum = weights.reduce((a, b) => a + b, 0);
  const raw = weights.map(weight => sum > 0 ? cents * weight / sum : 0);
  const shares = raw.map(Math.floor);
  let remaining = cents - shares.reduce((a, b) => a + b, 0);
  const order = raw.map((value, index) => ({ index, remainder: value - shares[index] })).sort((a, b) => b.remainder - a.remainder || a.index - b.index);
  for (const row of order) { if (!remaining) break; shares[row.index]++; remaining--; }
  return assetClasses.map(({ key, name, color }, index) => ({ key, name, color, current: current[key], target: targets[key],
    beforeShare: total > 0 ? current[key] / total * 100 : 0, amount: shares[index] / 100,
    after: current[key] + shares[index] / 100,
    afterShare: newTotal > 0 ? (current[key] + shares[index] / 100) / newTotal * 100 : 0 }));
}

export function isDescendant(id: number, ancestor: number, portfolios: GoalPortfolio[]) {
  const seen = new Set<number>();
  let current = portfolios.find(p => p.id === id);
  while (current?.parent_portfolio_id && !seen.has(current.id)) {
    seen.add(current.id);
    if (current.parent_portfolio_id === ancestor) return true;
    current = portfolios.find(p => p.id === current?.parent_portfolio_id);
  }
  return false;
}
