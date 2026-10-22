import { expect, it } from 'vitest';
import type { CashForecast } from '../../api_forecast';
import { forecastPlansThrough } from './forecastPlanPresentation';

it('cuts a partial last month and includes a delayed bill only when it is forecast to be paid', () => {
  const data = { month_plans: [{ month: '2030-01', income: 1000, bills: 300 }, { month: '2030-02' }],
    events: [
      { kind: 'INCOME', amount: 1000, date: '2030-01-20', scheduled_date: '2030-01-20', recorded: false },
      { kind: 'BILL', amount: 100, date: '2030-01-15', scheduled_date: '2030-01-05', recorded: false },
      { kind: 'BILL', amount: 200, date: '2030-01-05', scheduled_date: '2030-01-05', recorded: true },
      { kind: 'DAILY', amount: 10.01, date: '2030-01-10', scheduled_date: '2030-01-10', recorded: false },
    ] } as unknown as CashForecast;
  const short = forecastPlansThrough(data, '2030-01-12');
  expect(short).toHaveLength(1); expect(short[0]).toMatchObject({ income: 0, bills: 0, ordinary_remaining: 10.01 });
  expect(forecastPlansThrough(data, '2030-01-31')[0]).toMatchObject({ income: 1000, bills: 100 });
  expect(data.month_plans?.[0].income).toBe(1000);
});
