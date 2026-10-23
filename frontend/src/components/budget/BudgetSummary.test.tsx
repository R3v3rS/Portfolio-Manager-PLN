import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import type { CashForecast } from '../../api_forecast';
import BudgetSummary from './BudgetSummary';

const data = (): BudgetWorkspace => ({
  month: '2030-02', accounts: [], categories: [], bills: [], entries: [],
  totals: { balance: 1000, cash_balance: 1000, available_now: 800, reserved: 200,
    income: 0, expected_income: 2000, spent: 0, planned: 1300, remaining_in_plan: 1300,
    to_plan: 1500, monthly_income_total: 2000, monthly_income_cost: 0,
    monthly_income_remaining_plan: 1300, monthly_income_to_plan: 700 },
});
const forecast = (): CashForecast => ({
  as_of: '2030-01-15', opening: { balance: 1000, reserved: 200, available: 800 },
  points: [{date:'2030-01-31',balance:800,reserved:300,available:500},
    {date:'2030-02-28',balance:1000,reserved:600,available:400}],
  month_plans: [{month:'2030-02',categories:[{name:'Transport',source:'ESTIMATE',amount:100}]}],
} as CashForecast);
const show = (workspace = data(), result: CashForecast | null = forecast(), failed = false) =>
  render(<MemoryRouter><BudgetSummary data={workspace} forecast={result} failed={failed}/></MemoryRouter>);

describe('BudgetSummary', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date('2030-01-15T12:00:00')); });
  afterEach(() => { vi.useRealTimers(); });
  it('separates monthly income surplus from current cash and projected free funds', () => {
    show();
    const plan = within(screen.getByLabelText('Wolne z przychodów miesiąca'));
    expect(plan.getByText(/700,00/,{selector:'strong'})).toBeInTheDocument();
    expect(plan.queryByText(/1\s?500,00/)).not.toBeInTheDocument();
    const future = within(screen.getByLabelText('Prognoza wolnych środków na koniec miesiąca'));
    expect(future.getByText(/400,00/,{selector:'strong'})).toBeInTheDocument();
    expect(future.getByText(/1\s?000,00/,{selector:'dd'})).toBeInTheDocument();
    expect(screen.getByText('Miesiąc jeszcze się nie rozpoczął.')).toBeInTheDocument();
  });
  it('reconciles prior-month costs and differing forecast assumptions without adding parent limits', () => {
    show();
    const bridge = within(screen.getByLabelText('Uzgodnienie planu z prognozą'));
    expect(bridge.getByText(/-300,00/)).toBeInTheDocument();
    expect(bridge.getByText(/-800,00/)).toBeInTheDocument();
    expect(bridge.getByText(/400,00/)).toBeInTheDocument();
    expect(screen.getByText(/szacunkowych limitów: Transport/)).toBeInTheDocument();
    expect(screen.getByText(/Nie pomniejsza go plan pozostały przed tym miesiącem/)).toBeInTheDocument();
  });
  it('shows forecast failure without substituting a zero or the plan surplus', () => {
    show(data(), null, true);
    const future = within(screen.getByLabelText('Prognoza wolnych środków na koniec miesiąca'));
    expect(future.getByText('Niedostępne')).toBeInTheDocument();
    expect(future.queryByText(/0,00/,{selector:'strong'})).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Uzgodnienie planu z prognozą')).not.toBeInTheDocument();
  });
  it('does not present a future forecast as a historical closing balance', () => {
    const workspace=data(); workspace.month='2029-12'; show(workspace);
    expect(screen.getByText('Okres historyczny')).toBeInTheDocument();
    expect(screen.queryByLabelText('Uzgodnienie planu z prognozą')).not.toBeInTheDocument();
  });
  it('shows today earmarks independently of the selected month and card debt only once', () => {
    const workspace=data();Object.assign(workspace.totals,{cash_balance:1300,credit_card_debt:300,reserved:999});
    show(workspace);
    const now=within(screen.getByLabelText('Pieniądze dzisiaj'));
    expect(now.getByText(/200,00/,{selector:'dd'})).toBeInTheDocument();
    expect(now.getByText(/800,00/,{selector:'dd'})).toBeInTheDocument();
    expect(now.queryByText(/999,00/)).not.toBeInTheDocument();
    expect(now.getByText('Poza rezerwami i długiem kart')).toBeInTheDocument();
  });
  it('makes a monthly deficit explicit rather than describing it as available money', () => {
    const workspace=data();workspace.totals.monthly_income_to_plan=-100;show(workspace);
    const plan=within(screen.getByLabelText('Wolne z przychodów miesiąca'));
    expect(plan.getByText('Brakuje w dochodach miesiąca')).toBeInTheDocument();
    expect(plan.getByText(/pokrycia tej kwoty z wcześniejszych środków/)).toBeInTheDocument();
  });
});
