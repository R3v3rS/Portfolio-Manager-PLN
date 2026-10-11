import { useEffect, useState } from 'react';
import { forecastApi, type CashForecast } from '../../api_forecast';
import type { BudgetWorkspace } from '../../api_budget_workspace';

export function useBudgetForecast(data: BudgetWorkspace | null) {
  const [forecast, setForecast] = useState<CashForecast | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    setForecast(null); setFailed(false);
    if (data?.planning) forecastApi.get({}).then(result => { if (active) setForecast(result); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [data]);
  return { forecast, failed };
}
