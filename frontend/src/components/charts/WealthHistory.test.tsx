import { describe, it, expect, vi, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { chartsApi, type WealthPoint } from '../../api_charts';
import WealthHistory from './WealthHistory';
import { wealthRange } from './wealthRangeModel';
vi.mock('../../api_charts', () => ({ chartsApi: { wealth: vi.fn() } }));
vi.mock('./ChartKit', () => ({ TrendChart: ({ data }: { data: WealthPoint[] }) => <div data-testid="wealth-points">{data.map(p => p.date).join(',')}</div> }));
const point = (date: string): WealthPoint => ({ date, net_worth: 100, total_assets: 120, total_liabilities: 20 });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.resetAllMocks(); });
describe('wealth history ranges', () => {
  it('filters calendar months and clamps the last day, including leap years', () => {
    expect(wealthRange([], '1M', '2026-03-31').from).toBe('2026-02-28');
    expect(wealthRange([], '1Y', '2024-02-29').from).toBe('2023-02-28');
    expect(wealthRange([], '3M', '2026-10-12').from).toBe('2026-07-12');
    expect(wealthRange([], '6M', '2026-10-12').from).toBe('2026-04-12');
  });
  it('keeps boundary observations without fabricating older points or modifying the response', () => {
    const points = ['2026-07-11', '2026-07-12', '2026-10-12', '2026-10-13'].map(point);
    expect(wealthRange(points, '3M', '2026-10-12').points.map(p => p.date)).toEqual(['2026-07-12', '2026-10-12']);
    expect(wealthRange(points, 'ALL', '2026-10-12').points).toHaveLength(3);
    expect(points).toHaveLength(4);
  });
  it('changes the displayed range without requesting another snapshot', async () => {
    vi.spyOn(Date.prototype, 'toLocaleDateString').mockReturnValue('2026-10-12');
    vi.mocked(chartsApi.wealth).mockResolvedValue({ history: ['2026-01-01', '2026-08-01', '2026-10-01', '2026-10-12'].map(point) });
    render(<WealthHistory/>);
    await waitFor(() => expect(screen.getByTestId('wealth-points')).toHaveTextContent('2026-01-01'));
    fireEvent.click(screen.getByRole('button', { name: '3 mies.' }));
    expect(screen.getByTestId('wealth-points')).not.toHaveTextContent('2026-01-01');
    expect(screen.getByTestId('wealth-points')).toHaveTextContent('2026-08-01');
    fireEvent.click(screen.getByRole('button', { name: '1 mies.' }));
    expect(screen.getByTestId('wealth-points')).not.toHaveTextContent('2026-08-01');
    fireEvent.click(screen.getByRole('button', { name: 'Cała historia' }));
    expect(screen.getByTestId('wealth-points')).toHaveTextContent('2026-01-01');
    expect(chartsApi.wealth).toHaveBeenCalledTimes(1);
  });
  it('explains why a year still shows only a short saved history', async () => {
    vi.spyOn(Date.prototype, 'toLocaleDateString').mockReturnValue('2026-10-12');
    vi.mocked(chartsApi.wealth).mockResolvedValue({ history: [point('2026-10-01'), point('2026-10-12')] });
    render(<WealthHistory/>);
    await screen.findByTestId('wealth-points');
    fireEvent.click(screen.getByRole('button', { name: '1 rok' }));
    expect(screen.getByText(/Dla wcześniejszych dat nie ma zapisanych/)).toHaveTextContent('1 października 2026');
    expect(screen.getByTestId('wealth-points')).toHaveTextContent('2026-10-01,2026-10-12');
  });
});
