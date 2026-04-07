import React, { useEffect, useMemo, useState } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { analyticsApi, type AnalyticsSummaryPayload } from '../../api_analytics';

interface AnalyticsDashboardProps {
  portfolioId: number;
  subPortfolioId?: number;
}

type MetricTone = 'green' | 'yellow' | 'red';

const toneClasses: Record<MetricTone, string> = {
  green: 'border-green-200 bg-green-50 text-green-700',
  yellow: 'border-yellow-200 bg-yellow-50 text-yellow-700',
  red: 'border-red-200 bg-red-50 text-red-700',
};

const piePalette = ['#2563EB', '#16A34A', '#EAB308', '#F97316', '#7C3AED', '#14B8A6', '#EF4444', '#0EA5E9'];

const formatPercent = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  // Check if it's already a percentage (e.g. 5.0 for 5%) or a decimal (e.g. 0.05 for 5%)
  // Typically total_return_pct is 100-based, while max_drawdown and var are 1-based decimals.
  // In this project, performance metrics return 1-based decimals for drawdown/var.
  return `${(value * 100).toFixed(2)}%`;
};

const MetricCard = ({ label, value, tone }: { label: string; value: string; tone: MetricTone }) => (
  <div className={`rounded-lg border p-4 ${toneClasses[tone]}`}>
    <p className="text-xs uppercase tracking-wide opacity-80">{label}</p>
    <p className="mt-2 text-2xl font-semibold">{value}</p>
  </div>
);

const LoadingSkeleton = () => (
  <div className="space-y-6 animate-pulse">
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, idx) => (
        <div key={idx} className="h-24 rounded-lg bg-gray-200" />
      ))}
    </div>
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <div className="h-80 rounded-lg bg-gray-200" />
      <div className="h-80 rounded-lg bg-gray-200" />
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
  if (value > -10) return 'green';
  if (value >= -20) return 'yellow';
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
  if (absolute < 1) return 'green';
  if (absolute <= 2) return 'yellow';
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

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <h3 className="mb-4 text-lg font-semibold text-gray-900">Correlation Heatmap</h3>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Tooltip formatter={(value: number) => value.toFixed(2)} />
        </PieChart>
      </ResponsiveContainer>

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr>
              <th className="px-2 py-2 text-left text-xs text-gray-500">Asset</th>
              {columns.map((column) => (
                <th key={column} className="px-2 py-2 text-right text-xs text-gray-500">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={`${rowLabel(row)}-${idx}`} className="border-t border-gray-100">
                <td className="px-2 py-2 font-medium text-gray-700">{rowLabel(row)}</td>
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
      </div>
    </div>
  );
};

const DiversificationPie = ({ data }: { data: Array<{ sector: string; value: number }> }) => (
  <div className="rounded-lg border border-gray-200 p-4">
    <h3 className="mb-4 text-lg font-semibold text-gray-900">Diversification by Sector</h3>
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="sector" outerRadius={110} label={({ name, value }) => `${name}: ${value.toFixed(1)}%`}>
          {data.map((entry, index) => (
            <Cell key={entry.sector} fill={piePalette[index % piePalette.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(value: number) => `${value.toFixed(2)}%`} />
      </PieChart>
    </ResponsiveContainer>
  </div>
);

const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({ portfolioId, subPortfolioId }) => {
  const [data, setData] = useState<AnalyticsSummaryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchSummary = async () => {
      setLoading(true);
      setError(null);
      try {
        const summary = await analyticsApi.getSummary(portfolioId, subPortfolioId);
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
  }, [portfolioId, subPortfolioId]);

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

  const rawSectors = data?.diversification?.by_sector ?? [];
  const sectorMap = rawSectors.reduce<Record<string, number>>((acc, item) => {
    const sectorName = (item.sector ?? 'Unknown').trim() || 'Unknown';
    const candidate = item.value ?? item.weight ?? 0;
    const numeric = Number(candidate);
    if (Number.isFinite(numeric)) {
      acc[sectorName] = (acc[sectorName] ?? 0) + (numeric * 100);
    }
    return acc;
  }, {});

  const pieData = Object.entries(sectorMap).map(([sector, value]) => ({ sector, value }));
  const correlationData = data?.correlation?.recharts_data ?? [];

  return (
    <div className="space-y-6">
      {hasIncompleteHistory && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
          Portfolio ma zbyt mało danych historycznych, aby wyliczyć Sharpe Ratio i pełne metryki analityczne.
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Sharpe Ratio"
          value={sharpe == null ? '—' : sharpe.toFixed(2)}
          tone={getSharpeTone(sharpe)}
        />
        <MetricCard
          label="Max Drawdown"
          value={formatPercent(maxDrawdown)}
          tone={getMaxDrawdownTone(maxDrawdown)}
        />
        <MetricCard
          label="VaR 1D (% portfela)"
          value={formatPercent(var1dPercent)}
          tone={getVarTone(var1dPercent)}
        />
        <MetricCard
          label="Diversification Score"
          value={diversificationScore === null || diversificationScore === undefined ? '—' : diversificationScore.toFixed(1)}
          tone={getDiversificationTone(diversificationScore)}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <CorrelationHeatmap rows={correlationData} />
        <DiversificationPie data={pieData} />
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
