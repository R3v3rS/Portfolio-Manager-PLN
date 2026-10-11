import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import BudgetSpendingSummary from './BudgetSpendingSummary';

afterEach(() => vi.useRealTimers());

it('shows actual spending separately from savings and links to the selected month', () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-10-03T12:00:00'));
  const data: BudgetWorkspace = {
    month: '2026-10', accounts: [], categories: [], entries: [], bills: [],
    totals: { balance: 1131.1, income: 0, planned: 4513, spent: 500,
      remaining_in_plan: 4013, to_plan: 2654.01,
      period_spending: { first: '2026-10-01', through: '2026-10-03', spent: 370.91,
        expense_count: 9, reserve_contributions: 435, reserve_released: 0,
        reserve_settled: 0, reserve_adjustment: 435, budget_spent: 805.91 } },
  };
  render(<MemoryRouter><BudgetSpendingSummary data={data}/></MemoryRouter>);
  const summary = within(screen.getByRole('region', { name: 'Wydatki miesiąca' }));
  expect(summary.getByText('Wydano w tym miesiącu do dziś')).toBeInTheDocument();
  expect(summary.getByText(/370,91/)).toBeInTheDocument();
  expect(summary.getByText(/435,00/)).toBeInTheDocument();
  expect(summary.getByText(/805,91/)).toBeInTheDocument();
  expect(summary.getByText(/Liczba wydatków: 9/)).toBeInTheDocument();
  expect(summary.getByRole('link', { name: /Przejrzyj wydatki/ })).toHaveAttribute('href', '/budget?view=entries&month=2026-10');
  expect(summary.queryByText(/500,00/)).not.toBeInTheDocument();
});
