import React, { useEffect, useMemo, useState } from 'react';
import api from '../../api';
import { cn } from '../../lib/utils';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface PerformanceHeatmapProps {
  portfolioId: number;
}

interface MonthlyReturn {
  [month: string]: number | string; // "1", "2", ..., "12", "YTD"
}

interface PerformanceMatrix {
  [year: string]: MonthlyReturn;
}

const MONTHS = [
  { key: '1', label: 'Sty' },
  { key: '2', label: 'Lut' },
  { key: '3', label: 'Mar' },
  { key: '4', label: 'Kwi' },
  { key: '5', label: 'Maj' },
  { key: '6', label: 'Cze' },
  { key: '7', label: 'Lip' },
  { key: '8', label: 'Sie' },
  { key: '9', label: 'Wrz' },
  { key: '10', label: 'Paź' },
  { key: '11', label: 'Lis' },
  { key: '12', label: 'Gru' },
] as const;

const PerformanceHeatmap: React.FC<PerformanceHeatmapProps> = ({ portfolioId }) => {
  const [matrix, setMatrix] = useState<PerformanceMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPerformance = async () => {
      setLoading(true);
      try {
        const response = await api.get<{ matrix: PerformanceMatrix }>(`/${portfolioId}/performance`);
        setMatrix(response.matrix);
        setError(null);
      } catch (err: unknown) {
        console.error('Failed to fetch performance matrix:', err);
        setError('Nie udało się pobrać danych o wynikach.');
      } finally {
        setLoading(false);
      }
    };

    if (portfolioId) {
      fetchPerformance();
    }
  }, [portfolioId]);

  // Sort years descending
  const years = matrix ? Object.keys(matrix).sort((a, b) => parseInt(b) - parseInt(a)) : [];

  const chartData = useMemo(() => {
    if (!matrix) return [];

    return Object.keys(matrix)
      .sort((a, b) => parseInt(a) - parseInt(b))
      .flatMap((year) =>
        MONTHS.flatMap((month) => {
          const rawValue = matrix[year]?.[month.key];
          const value = typeof rawValue === 'string' ? parseFloat(rawValue) : rawValue;

          if (typeof value !== 'number' || Number.isNaN(value)) {
            return [];
          }

          return [{
            id: `${year}-${month.key}`,
            label: `${month.label} ${year}`,
            shortLabel: `${month.label} '${year.slice(-2)}`,
            value,
            fill: value >= 0 ? '#22c55e' : '#dc2626',
          }];
        })
      );
  }, [matrix]);

  if (loading) {
    return <div className="p-4 text-center text-gray-500">Ładowanie wyników...</div>;
  }

  if (error) {
    return <div className="p-4 text-center text-red-500">{error}</div>;
  }

  if (!matrix || Object.keys(matrix).length === 0) {
    return <div className="p-4 text-center text-gray-500">Brak danych do wyświetlenia macierzy wyników.</div>;
  }

  const formatValue = (val: number | string | undefined) => {
    if (val === undefined || val === null) return '-';
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num)) return '-';
    if (Math.abs(num) < 0.001) return '-'; // Treat 0 as -
    return `${num.toFixed(2)}%`;
  };

  const getCellClass = (val: number | string | undefined, isYtd: boolean = false) => {
    if (val === undefined || val === null) return 'text-gray-400';
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num) || Math.abs(num) < 0.001) return 'text-gray-400';
    
    if (num > 0) {
      return isYtd 
        ? 'text-green-700 font-bold bg-green-100' 
        : 'text-green-600 bg-green-50';
    } else {
      return isYtd 
        ? 'text-red-700 font-bold bg-red-100' 
        : 'text-red-600 bg-red-50';
    }
  };

  return (
    <div className="space-y-4">
      {chartData.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow">
          <div className="mb-3">
            <h4 className="text-base font-medium text-gray-900">Stopa zwrotu w ujęciu miesięcznym</h4>
            <p className="text-sm text-gray-500">Kolumnowy widok miesięcznych zmian procentowych z danych MoM.</p>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 12, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="shortLabel"
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                  interval="preserveStartEnd"
                  minTickGap={20}
                />
                <YAxis
                  tickFormatter={(value: number) => `${value.toFixed(0)}%`}
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                  width={48}
                />
                <Tooltip
                  formatter={(value: number) => [`${value.toFixed(2)}%`, 'Stopa zwrotu']}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.label ?? ''}
                  contentStyle={{
                    borderRadius: '0.5rem',
                    borderColor: '#e5e7eb',
                  }}
                />
                <ReferenceLine y={0} stroke="#6b7280" strokeWidth={1.5} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell key={entry.id} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <div className="overflow-x-auto bg-white rounded-lg shadow border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider sticky left-0 bg-gray-50 z-10">
                Rok
              </th>
              {MONTHS.map((m) => (
                <th key={m.key} className="px-2 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {m.label}
                </th>
              ))}
              <th className="px-3 py-3 text-center text-xs font-bold text-gray-700 uppercase tracking-wider bg-gray-100">
                YTD
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {years.map((year) => {
              const yearData = matrix[year];
              return (
                <tr key={year} className="hover:bg-gray-50 transition-colors">
                  <td className="px-3 py-3 whitespace-nowrap text-sm font-bold text-gray-900 sticky left-0 bg-white z-10 border-r border-gray-100">
                    {year}
                  </td>
                  {MONTHS.map((m) => {
                    const val = yearData[m.key];
                    return (
                      <td
                        key={`${year}-${m.key}`}
                        className={cn(
                          "px-2 py-3 whitespace-nowrap text-xs text-center border-r border-gray-50",
                          getCellClass(val as number)
                        )}
                      >
                        {formatValue(val as number)}
                      </td>
                    );
                  })}
                  <td className={cn(
                    "px-3 py-3 whitespace-nowrap text-sm text-center font-bold border-l border-gray-200",
                    getCellClass(yearData['YTD'] as number, true)
                  )}>
                    {formatValue(yearData['YTD'] as number)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PerformanceHeatmap;
