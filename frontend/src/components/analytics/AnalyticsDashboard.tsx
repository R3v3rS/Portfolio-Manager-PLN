import React, { useEffect, useState } from 'react';
import { TrendChart } from '../charts/ChartKit';

import CorrelationHeatmap from './CorrelationHeatmap';
import { analyticsApi, type AnalyticsSummaryPayload } from '../../api_analytics';

interface AnalyticsDashboardProps {
  portfolioId: number;
  subPortfolioId?: number;
}

type MetricTone = 'green' | 'yellow' | 'red';

const toneClasses: Record<MetricTone, string> = {
  green: 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/70 dark:bg-emerald-950/30 dark:text-emerald-300',
  yellow: 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-300',
  red: 'border-red-200 bg-red-50 text-red-800 dark:border-red-900/70 dark:bg-red-950/30 dark:text-red-300',
};

const formatPercent = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${(value * 100).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
};

const formatPercentagePoints = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
};

const formatCurrency = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${Math.abs(value).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN`;
};

const formatDate = (value?: string | null) => {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString('pl-PL');
};

const MetricCard = ({ label, value, tone, detail }: { label: string; value: string; tone: MetricTone; detail: string }) => (
  <div className={`rounded-xl border p-4 ${toneClasses[tone]}`}>
    <p className="text-xs font-semibold uppercase tracking-[0.14em] opacity-75">{label}</p>
    <p className="mt-2 text-2xl font-semibold">{value}</p>
    <p className="mt-2 text-xs leading-relaxed opacity-80">{detail}</p>
  </div>
);

const LoadingSkeleton = () => (
  <div className="space-y-6 animate-pulse">
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, idx) => (
        <div key={idx} className="h-32 rounded-xl bg-gray-200 dark:bg-slate-800" />
      ))}
    </div>
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <div className="h-80 rounded-xl bg-gray-200 dark:bg-slate-800" />
      <div className="h-80 rounded-xl bg-gray-200 dark:bg-slate-800" />
    </div>
  </div>
);

const getSharpeTone = (value?: number | null): MetricTone => {
  if (value === null || value === undefined) return 'yellow';
  if (value < 1) return 'red';
  if (value <= 2) return 'yellow';
  return 'green';
};

const getMaxDrawdownTone = (value?: number | null): MetricTone => {
  if (value === null || value === undefined) return 'yellow';
  if (value > -0.1) return 'green';
  if (value >= -0.2) return 'yellow';
  return 'red';
};

const getDiversificationTone = (value?: number | null): MetricTone => {
  if (value === null || value === undefined) return 'yellow';
  if (value < 40) return 'red';
  if (value <= 65) return 'yellow';
  return 'green';
};

const getVarTone = (value?: number | null): MetricTone => {
  if (value === null || value === undefined) return 'yellow';
  const absolute = Math.abs(value);
  if (absolute < 0.01) return 'green';
  if (absolute <= 0.02) return 'yellow';
  return 'red';
};

const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({ portfolioId, subPortfolioId }) => {
  const [data, setData] = useState<AnalyticsSummaryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState('1y');

  useEffect(() => {
    let mounted = true;
    const fetchSummary = async () => {
      setLoading(true);
      setError(null);
      try {
        const summary = await analyticsApi.getSummary(portfolioId, subPortfolioId, period);
        if (mounted) setData(summary);
      } catch (err) {
        if (mounted) {
          const message = err instanceof Error ? err.message : 'Nie udało się pobrać analityki.';
          setError(message);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void fetchSummary();
    return () => {
      mounted = false;
    };
  }, [period, portfolioId, subPortfolioId]);

  const sharpe = data?.performance?.sharpe_ratio;

  if (loading) return <LoadingSkeleton />;

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  }

  const dataStatus = data?.performance?.data_status;
  const hasIncompleteHistory = dataStatus ? dataStatus !== 'ok' : sharpe == null;
  const missingMessage = dataStatus === 'no_holdings' ? 'Brak otwartych pozycji w wybranym portfelu.' :
    dataStatus === 'missing_prices' ? 'Brakuje ceny lub kursu waluty. Uzupełnij notowania, aby policzyć ryzyko.' :
      `Za mało wspólnych sesji z pełnymi notowaniami: ${data?.performance?.data_points ?? 0}. Do obliczeń potrzeba co najmniej 30 sesji. Brak danych nie oznacza zerowego ryzyka.`;

  const rawMaxDrawdown = data?.performance?.max_drawdown;
  const maxDrawdown = typeof rawMaxDrawdown === 'number' ? rawMaxDrawdown : rawMaxDrawdown?.value;
  const var1dPercent = data?.risk?.var_1d_percent;
  const diversificationScore = data?.diversification?.score;
  const drawdownDetail = typeof rawMaxDrawdown === 'object' && rawMaxDrawdown
    ? `${formatDate(rawMaxDrawdown.start_date)}–${formatDate(rawMaxDrawdown.end_date)}${rawMaxDrawdown.duration_days ? ` · ${rawMaxDrawdown.duration_days} dni` : ''}`
    : 'Największy spadek od lokalnego szczytu.';
  const varDetail = `${formatCurrency(data?.risk?.var_1d_pln)} · 95% ufności · ${data?.risk?.data_points ?? 0} sesji`;
  const performance = data?.performance;

  const correlationData = data?.correlation?.recharts_data ?? [];

  return (
    <div className="space-y-6">
      {hasIncompleteHistory && (
        <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800 dark:border-yellow-900/70 dark:bg-yellow-950/30 dark:text-yellow-200">
          {missingMessage}
        </div>
      )}
      <div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600 dark:text-blue-400">Ryzyko i jakość wyniku</p>
            <h3 className="mt-1 text-xl font-semibold text-slate-900 dark:text-slate-100">Najważniejsze wskaźniki</h3>
          </div>
          <label className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
            Okres
            <select
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200"
            >
              <option value="3mo">3 miesiące</option>
              <option value="6mo">6 miesięcy</option>
              <option value="1y">1 rok</option>
              <option value="2y">2 lata</option>
            </select>
          </label>
        </div>
      </div>
      <p className="rounded-xl border border-slate-700 p-4 text-sm text-slate-300">Faktyczny okres obliczeń: <strong>{formatDate(performance?.observed_from)} – {formatDate(performance?.observed_to)}</strong> · {performance?.data_points ?? 0} wspólnych sesji. Wybrany okres jest maksymalnym zakresem; krótsza historia instrumentu lub waluty skraca próbę. Wskaźniki dotyczą obecnego koszyka akcji i ETF-ów, bez gotówki i historii zmian składu.</p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Wskaźnik Sharpe’a"
          value={sharpe == null ? '—' : sharpe.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          tone={getSharpeTone(sharpe)}
          detail={`Roczna miara dla obecnego koszyka. Stopa odniesienia: ${formatPercent(data?.performance?.risk_free_rate ?? 0.05)} rocznie.`}
        />
        <MetricCard
          label="Maksymalne obsunięcie"
          value={formatPercent(maxDrawdown)}
          tone={getMaxDrawdownTone(maxDrawdown)}
          detail={drawdownDetail}
        />
        <MetricCard
          label="VaR 1D części akcyjnej"
          value={var1dPercent == null ? '—' : formatPercent(Math.abs(var1dPercent))}
          tone={getVarTone(var1dPercent)}
          detail={varDetail}
        />
        <MetricCard
          label="Dywersyfikacja"
          value={diversificationScore === null || diversificationScore === undefined ? '—' : `${diversificationScore.toLocaleString('pl-PL', { maximumFractionDigits: 0 })}/100`}
          tone={getDiversificationTone(diversificationScore)}
          detail={data?.diversification?.recommendation ?? 'Ocena koncentracji aktywów i sektorów.'}
        />
      </div>
      <p className="text-xs leading-relaxed text-slate-400">Analiza części akcyjnej w PLN według obecnych udziałów, bez gotówki. Opisuje model obecnego koszyka; historyczne wpłaty i zmiany składu nie są tu odtworzone. Wykorzystywane są wyłącznie wspólne sesje z pełnymi danymi.</p>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {[
          ['Zwrot za okres', formatPercentagePoints(performance?.total_return_pct)],
          ['Zmienność roczna', formatPercent(performance?.volatility_annualized)],
          ['Najlepsza sesja', formatPercent(performance?.best_day?.return)],
          ['Najgorsza sesja', formatPercent(performance?.worst_day?.return)],
          ['CVaR 1D', data?.risk?.cvar_1d_pct == null ? '—' : `${formatPercent(Math.abs(data.risk.cvar_1d_pct))} · ${formatCurrency(data.risk.cvar_1d_pln)}`],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-950">
            <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">{value}</p>
          </div>
        ))}
      </div>

      <section className="chart-panel"><div className="chart-heading"><div><h2>Obsunięcia obecnego koszyka</h2><p>Spadek od poprzedniego szczytu · PLN · obecne udziały, bez gotówki</p></div></div>
        <TrendChart data={performance?.drawdown_series ?? []} series={[{ key: 'value', name: 'Obsunięcie', color: '#f28d9c', area: true }]} unit="%" zero />
        <p className="chart-note">To historia modelu obecnego koszyka, spójna ze wskaźnikiem maksymalnego obsunięcia. Nie odtwarza zmian składu portfela. {typeof rawMaxDrawdown === 'object' && rawMaxDrawdown ? `Szczyt: ${formatDate(rawMaxDrawdown.start_date)} · dołek: ${formatDate(rawMaxDrawdown.end_date)} · odrobienie: ${rawMaxDrawdown.recovery_date ? formatDate(rawMaxDrawdown.recovery_date) : 'jeszcze nie odrobiono'}` : ''}</p>
      </section>
      <CorrelationHeatmap rows={correlationData} period={period} />
    </div>
  );
};

export default AnalyticsDashboard;
