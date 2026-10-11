import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import PortfolioResearch from './PortfolioResearch';
import { exposure, filterPositions } from './researchModel';
import type { Holding, PortfolioValue } from '../../types';

vi.mock('recharts', () => ({
  ResponsiveContainer: () => <div data-testid="chart" />,
  AreaChart: () => null, Area: () => null, CartesianGrid: () => null,
  ReferenceLine: () => null, Tooltip: () => null, XAxis: () => null, YAxis: () => null,
}));
const holdings: Holding[] = [
  { id: 1, portfolio_id: 1, ticker: 'AAA', quantity: 1, average_buy_price: 100, total_cost: 100, current_value: 120, profit_loss: 20, profit_loss_percent: 20, change_1d_percent: 0, sector: 'Tech' },
  { id: 2, portfolio_id: 2, ticker: 'AAA', quantity: 1, average_buy_price: 100, total_cost: 100, current_value: 120, profit_loss: 20, sector: 'Tech' },
  { id: 3, portfolio_id: 1, ticker: 'BBB', quantity: 1, average_buy_price: 100, total_cost: 100, current_value: 60, profit_loss: -40, sector: 'Retail' },
  { id: 4, portfolio_id: 1, ticker: 'CCC', quantity: 1, average_buy_price: 100, total_cost: 100 },
];
const value = { portfolio_value: 400, cash_value: 100, holdings_value: 300, total_result: 0, total_result_percent: 0, open_positions_result: 0, total_dividends: 0 } as PortfolioValue;
const renderResearch = () => render(<MemoryRouter><PortfolioResearch holdings={holdings} value={value} history={[]} profitHistory={[]} dailyHistory={[]} dailyProfit={[]} onHistory={vi.fn()} onSell={vi.fn()} onClose={vi.fn()} onRisk={vi.fn()} /></MemoryRouter>);

describe('Portfolio research', () => {
  it('aggregates the same instrument across portfolios for concentration', () => {
    expect(exposure(holdings)).toEqual([{ ticker: 'AAA', value: 240, weight: 80 }, { ticker: 'BBB', value: 60, weight: 20 }]);
  });
  it('combines filters without treating missing results as losses', () => {
    expect(filterPositions(holdings, '', 'all', 'negative').map(h => h.ticker)).toEqual(['BBB']);
    expect(filterPositions(holdings, 'aaa', 'Retail', 'all')).toEqual([]);
  });
  it('filters table and totals, then resets the selection of filters', () => {
    renderResearch();
    fireEvent.change(screen.getByLabelText('Filtr wyniku'), { target: { value: 'negative' } });
    expect(within(screen.getByRole('table')).queryByText('AAA')).not.toBeInTheDocument();
    expect(within(screen.getByRole('table')).getByText('BBB')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Wyczyść filtry/ }));
    expect(within(screen.getByRole('table')).getAllByText('AAA')).toHaveLength(2);
  });
  it('keeps comparison selections independent and limits them to three', () => {
    renderResearch();
    const checks = screen.getAllByRole('checkbox');
    checks.slice(0, 3).forEach(check => fireEvent.click(check));
    expect(checks[3]).toBeDisabled();
    expect(screen.getByRole('region', { name: 'Porównanie pozycji' })).toBeInTheDocument();
    fireEvent.click(checks[0]);
    expect(checks[3]).toBeEnabled();
  });
  it('displays a real zero change and does not invent a history series', () => {
    renderResearch();
    expect(within(screen.getByRole('table')).getByText('0,00%')).toBeInTheDocument();
    expect(screen.queryByTestId('chart')).not.toBeInTheDocument();
    expect(screen.getByText(/Za mało punktów historii/)).toBeInTheDocument();
  });
});
