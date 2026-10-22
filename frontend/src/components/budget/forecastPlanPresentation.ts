import type { CashForecast, ForecastKind } from '../../api_forecast';

/** Use the actual forecast dates, including bills postponed beyond their scheduled date. */
export function forecastPlansThrough(data: CashForecast, through: string) {
  return (data.month_plans ?? []).filter(row => row.month <= through.slice(0, 7)).map(row => {
    const events = data.events.filter(event => !event.recorded && event.date <= through
      && event.scheduled_date.slice(0, 7) === row.month);
    const sum = (kind: ForecastKind) => events.filter(event => event.kind === kind)
      .reduce((total, event) => total + Math.round(event.amount * 100), 0) / 100;
    return { ...row, ordinary_remaining: sum('DAILY'), income: sum('INCOME'), bills: sum('BILL'),
      loans: sum('LOAN'), reserves: sum('RESERVE_ADD'), reserve_payments: sum('RESERVE_COST'), investments: sum('GOAL') };
  });
}
