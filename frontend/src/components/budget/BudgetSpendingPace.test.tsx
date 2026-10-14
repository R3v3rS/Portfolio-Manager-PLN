import { describe, it, expect } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { budgetSpendingPace } from './spendingPaceModel';
import BudgetSpendingPace from './BudgetSpendingPace';

const workspace = (spent = 160, plan = 310): BudgetWorkspace => ({
  month: '2026-10', accounts: [], entries: [], categories: [], bills: [],
  totals: { balance: 1000, income: 0, planned: plan, spent, remaining_in_plan: plan - spent, to_plan: 1000 },
  chart: Array.from({ length: 31 }, (_, i) => ({ date: `2026-10-${String(i + 1).padStart(2, '0')}`,
    daily_plan: plan * (i + 1) / 31, daily_spent: i < 11 ? spent : null,
    cash_spent: i < 11 ? spent + 2000 : null, budget_spent: i < 11 ? spent + 2300 : null,
    cash_plan: 2000 + plan * (i + 1) / 31, budget_plan: 2300 + plan * (i + 1) / 31 })),
});

describe('daily spending pace', () => {
  it('shows five days ahead, excluding fixed payments and allocations', () => {
    const data = workspace();
    expect(budgetSpendingPace(data, '2026-10-11')).toMatchObject({ equivalentDay: 16, daysAhead: 5, spent: 160, plannedToday: 110 });
    render(<BudgetSpendingPace data={data} today="2026-10-11"/>);
    expect(screen.getByText('Około 5 dni przed planem')).toBeInTheDocument();
    expect(screen.getByText(/16. dniowi planu/)).toBeInTheDocument();
    cleanup();
  });
  it('shows a reserve of days when refunds reduce shopping costs', () => {
    expect(budgetSpendingPace(workspace(60), '2026-10-11')).toMatchObject({ equivalentDay: 6, daysAhead: -5 });
  });
  it('does not turn currency rounding into a day of overspending', () => {
    expect(budgetSpendingPace(workspace(110.01), '2026-10-11').daysAhead).toBe(0);
  });
  it('handles missing plans without dividing by zero', () => {
    expect(budgetSpendingPace(workspace(100, 0), '2026-10-11').equivalentDay).toBeNull();
  });
  it('does not describe overspending as an impossible calendar day', () => {
    render(<BudgetSpendingPace data={workspace(400)} today="2026-10-11"/>);
    expect(screen.getByText('Przekroczony plan codziennych wydatków')).toBeInTheDocument();
    expect(screen.queryByText(/40. dniowi/)).not.toBeInTheDocument();
    cleanup();
  });
  it('handles future and closed months and net negative spending', () => {
    expect(budgetSpendingPace(workspace(), '2026-09-11')).toMatchObject({ day: 0, spent: null });
    const closed = workspace(); closed.chart!.forEach(p => { p.daily_spent = 160; });
    expect(budgetSpendingPace(closed, '2026-11-11')).toMatchObject({ current: false, day: 31, spent: 160 });
    expect(budgetSpendingPace(workspace(-20), '2026-10-11').equivalentDay).toBe(0);
  });
  it('uses the existing daily model for older responses without chart points', () => {
    const data = workspace(0); delete data.chart;
    expect(budgetSpendingPace(data, '2026-10-11')).toMatchObject({ monthlyPlan: 310, spent: 0 });
  });
});
