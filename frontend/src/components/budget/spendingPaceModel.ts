import type { BudgetWorkspace } from '../../api_budget_workspace';
import { budgetChartData } from './budgetChartModel';

export function budgetSpendingPace(data: BudgetWorkspace, today: string) {
  const [year, month] = data.month.split('-').map(Number);
  const days = new Date(year, month, 0).getDate();
  const current = data.month === today.slice(0, 7);
  const day = current ? Number(today.slice(8, 10)) : data.month < today.slice(0, 7) ? days : 0;
  const fallback = budgetChartData(data, today).dailyPace;
  const points = data.chart?.map(p => ({
    date: p.date,
    spent: p.daily_spent === undefined ? fallback.find(f => f.date === p.date)?.spent ?? null : p.daily_spent,
    plan: p.daily_plan ?? fallback.find(f => f.date === p.date)?.plan ?? 0,
  })) ?? fallback;
  const monthlyPlan = points.find(p => p.date === `${data.month}-${days}`)?.plan ?? 0;
  const date = `${data.month}-${String(day).padStart(2, '0')}`;
  const spent = points.find(p => p.date === date)?.spent ?? null;
  const plannedToday = points.find(p => p.date === date)?.plan ?? 0;
  const equivalentDay = spent !== null && monthlyPlan > 0 ? Math.round(Math.max(0, spent) / monthlyPlan * days) : null;
  return { current, day, days, spent, monthlyPlan, plannedToday, equivalentDay,
    daysAhead: equivalentDay === null ? null : equivalentDay - day };
}
