import React, { useEffect, useMemo, useState } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
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

const piePalette = ['#2563EB', '#16A34A', '#EAB308', '#F97316', '#7C3AED', '#14B8A6', '#EF4444', '#0EA5E9'];

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

const CorrelationHeatmap = ({ rows }: { rows: Array<Record<string, string | number | null>> }) => {
  const columns = useMemo(() => {
    const colSet = new Set<string>();
    rows.forEach((row) => {
      Object.keys(row).forEach((key) => {
        if (key !== 'name' && key !== 'asset' && key !== 'label' && key !== 'symbol') {
          colSet.add(key);
        }
      });
    });
    return Array.from(colSet);
  }, [rows]);

  const rowLabel = (row: Record<string, string | number | null>) =>
    (row.symbol ?? row.asset ?? row.name ?? row.label ?? '').toString() || '—';

  const cellColor = (value: number | null): string => {
    if (value === null || Number.isNaN(value)) return 'bg-gray-100';
    if (value > 0.8) return 'bg-red-200';
    if (value >= 0.5) return 'bg-yellow-100';
    return 'bg-green-100';
  };

  const hasMatrix = rows.length > 0 && columns.length > 0;

  return (
  <div className="min-w-0 rounded-xl border border-gray-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
      <h3 className="mb-1 text-lg font-semibold text-gray-900 dark:text-slate-100">Korelacja aktywów</h3>
      <p className="mb-4 text-sm text-gray-500 dark:text-slate-400">Wyższa wartość oznacza, że instrumenty częściej poruszają się w tym samym kierunku.</p>
      {!hasMatrix && (
        <div className="rounded-md border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
          Brak macierzy korelacji. Dodaj co najmniej dwa aktywa z dostępną historią cen, aby zobaczyć zależności.
        </div>
      )}

      {hasMatrix && <div className="min-w-0 overflow-x-auto">
        <table className="min-w-max text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-white px-2 py-2 text-left text-xs text-gray-500 dark:bg-slate-950 dark:text-slate-400">Aktywo</th>
              {columns.map((column) => (
                  <th key={column} className="px-2 py-2 text-right text-xs text-gray-500 dark:text-slate-400">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${rowLabel(row)}-${idx}`} className="border-t border-gray-100 dark:border-slate-800">
                <td className="sticky left-0 z-10 bg-white px-2 py-2 font-medium text-gray-700 dark:bg-slate-950 dark:text-slate-200">{rowLabel(row)}</td>
                {columns.map((column) => {
                  const raw = row[column];
                  const numeric = typeof raw === 'number' ? raw : raw === null || raw === undefined ? null : Number(raw);
                  return (
                    <td key={`${column}-${idx}`} className={`px-2 py-2 text-right ${cellColor(numeric)}`}>
                      {numeric === null || Number.isNaN(numeric) ? '—' : numeric.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
    </div>
  );
};

const DiversificationPie = ({ data }: { data: Array<{ sector: string; value: number }> }) => (
  <div className="min-w-0 rounded-xl border border-gray-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
    <h3 className="mb-1 text-lg font-semibold text-gray-900 dark:text-slate-100">Dywersyfikacja sektorowa</h3>
    <p className="mb-4 text-sm text-gray-500 dark:text-slate-400">Udział poszczególnych sektorów w części akcyjnej portfela.</p>
    {data.length === 0 ? (
      <div className="rounded-md border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
        Brak danych sektorowych. Uzupełnij sektory pozycji albo odśwież metadane instrumentów.
      </div>
    ) : (
      <div className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-[minmax(220px,1fr)_minmax(180px,220px)]">
        <div className="min-w-0">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
              <Pie data={data} dataKey="value" nameKey="sector" outerRadius={96}>
                {data.map((entry, index) => (
                  <Cell key={entry.sector} fill={piePalette[index % piePalette.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="min-w-0 space-y-2 self-center text-sm text-gray-700 dark:text-slate-300">
          {data.map((entry, index) => (
            <li key={entry.sector} className="flex min-w-0 items-center gap-2">
              <span
                className="h-3 w-3 shrink-0 rounded-sm"
                style={{ backgroundColor: piePalette[index % piePalette.length] }}
              />
              <span className="min-w-0 flex-1 truncate" title={entry.sector}>
                {entry.sector}
              </span>
              <span className="shrink-0 font-medium text-gray-900 dark:text-slate-100">{entry.value.toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      </div>
    )}
  </div>
);

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

  const hasIncompleteHistory = sharpe == null;

  const rawMaxDrawdown = data?.performance?.max_drawdown;
  const maxDrawdown = typeof rawMaxDrawdown === 'number' ? rawMaxDrawdown : rawMaxDrawdown?.value;
  const var1dPercent = data?.risk?.var_1d_percent;
  const diversificationScore = data?.diversification?.score;
  const drawdownDetail = typeof rawMaxDrawdown === 'object' && rawMaxDrawdown
    ? `${formatDate(rawMaxDrawdown.start_date)}–${formatDate(rawMaxDrawdown.end_date)}${rawMaxDrawdown.duration_days ? ` · ${rawMaxDrawdown.duration_days} dni` : ''}`
    : 'Największy spadek od lokalnego szczytu.';
  const varDetail = `${formatCurrency(data?.risk?.var_1d_pln)} · 95% ufności · ${data?.risk?.data_points ?? 0} sesji`;
  const performance = data?.performance;

  const rawSectors = data?.diversification?.by_sector ?? [];
  const sectorMap = rawSectors.reduce<Record<string, number>>((acc, item) => {
    const sectorName = (item.sector ?? 'Unknown').trim() || 'Unknown';
    const candidate = item.value ?? item.weight ?? 0;
    const numeric = Number(candidate);
    if (Number.isFinite(numeric)) {
      const percentage = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
      acc[sectorName] = (acc[sectorName] ?? 0) + percentage;
    }
    return acc;
  }, {});

  const pieData = Object.entries(sectorMap).map(([sector, value]) => ({ sector, value }));
  const correlationData = data?.correlation?.recharts_data ?? [];

  return (
    <div className="space-y-6">
      {hasIncompleteHistory && (
        <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800 dark:border-yellow-900/70 dark:bg-yellow-950/30 dark:text-yellow-200">
          Portfel ma zbyt mało danych historycznych, aby wyliczyć wskaźnik Sharpe’a i pełne metryki ryzyka.
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
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Wskaźnik Sharpe’a"
          value={sharpe == null ? '—' : sharpe.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          tone={getSharpeTone(sharpe)}
          detail="Nadwyżka zwrotu względem ryzyka; powyżej 1,00 jest zwykle dobrym wynikiem."
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

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <CorrelationHeatmap rows={correlationData} />
        <DiversificationPie data={pieData} />
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
