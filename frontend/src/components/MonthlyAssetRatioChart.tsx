import React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { PortfolioHistoryPoint } from '../api';
import { useTheme } from '../hooks/useTheme';

interface MonthlyAssetRatioChartProps {
  data: PortfolioHistoryPoint[];
}

const formatCurrency = (value: number) => `${value.toLocaleString('pl-PL', {minimumFractionDigits: 2, maximumFractionDigits: 2})} PLN`;

const MonthlyAssetRatioChart: React.FC<MonthlyAssetRatioChartProps> = ({ data }) => {
  const { isDark } = useTheme();

  const colors = {
    stock: isDark ? '#60a5fa' : '#3b82f6', // blue-400 : blue-500 (switched to blue for better modern look instead of red)
    cash: isDark ? '#34d399' : '#10b981', // emerald-400 : emerald-500
    grid: isDark ? '#334155' : '#e2e8f0', // slate-700 : slate-200
    text: isDark ? '#94a3b8' : '#64748b', // slate-400 : slate-500
    tooltipBg: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.9)', // slate-950 : white
    tooltipBorder: isDark ? '#334155' : '#e2e8f0',
    tooltipText: isDark ? '#f8fafc' : '#0f172a',
    cursor: isDark ? 'rgba(51, 65, 85, 0.4)' : 'rgba(226, 232, 240, 0.4)',
  };

  const chartData = data
    .filter((point) => point.cash_value !== undefined || point.holdings_value !== undefined)
    .map((point) => {
      const holdingsValue = point.holdings_value ?? Math.max((point.value ?? 0) - (point.cash_value ?? 0), 0);
      const cashValue = point.cash_value ?? 0;
      const total = holdingsValue + cashValue;

      return {
        label: point.label,
        akcje: holdingsValue,
        gotowka: cashValue,
        akcjeUdzial: total > 0 ? (holdingsValue / total) * 100 : 0,
        gotowkaUdzial: total > 0 ? (cashValue / total) * 100 : 0,
      };
    });

  return (
    <div className="bg-white dark:bg-slate-900 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-slate-800">
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Akcje vs gotówka w czasie</h3>
        <p className="text-sm text-gray-500 dark:text-slate-400">
          Miesięczne porównanie wartości akcji w PLN i gotówki wraz z udziałem obu części portfela.
        </p>
      </div>

      {chartData.length > 0 ? (
        <div className="h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              margin={{ top: 10, right: 10, left: 0, bottom: 40 }}
              barCategoryGap="20%"
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={colors.grid} />
              <XAxis
                dataKey="label"
                angle={-45}
                textAnchor="end"
                height={60}
                interval={0}
                tick={{ fontSize: 11, fill: colors.text, dy: 10 }}
                axisLine={{ stroke: colors.grid }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: colors.text }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(value) => `${value.toLocaleString('pl-PL')}`}
                domain={[0, 'auto']}
                padding={{ top: 20 }}
              />
              <Tooltip
                cursor={{ fill: colors.cursor }}
                contentStyle={{
                  backgroundColor: colors.tooltipBg,
                  borderRadius: '12px',
                  border: `1px solid ${colors.tooltipBorder}`,
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                  backdropFilter: 'blur(8px)',
                  padding: '12px'
                }}
                formatter={(value: number, name: string, item) => {
                  const payload = item.payload as { akcjeUdzial: number; gotowkaUdzial: number };
                  if (name === 'Akcje') {
                    return [
                      `${formatCurrency(value)} (${payload.akcjeUdzial.toFixed(1)}%)`,
                      name,
                    ];
                  }

                  return [
                    `${formatCurrency(value)} (${payload.gotowkaUdzial.toFixed(1)}%)`,
                    name,
                  ];
                }}
                labelStyle={{ color: colors.tooltipText, fontWeight: '600', marginBottom: '8px' }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px', color: colors.text }} />
              <Bar dataKey="akcje" name="Akcje" fill={colors.stock} radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell key={`stocks-${entry.label}`} fill={colors.stock} />
                ))}
              </Bar>
              <Bar dataKey="gotowka" name="Gotówka" fill={colors.cash} radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell key={`cash-${entry.label}`} fill={colors.cash} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-gray-200 dark:border-slate-700 text-sm text-gray-500 dark:text-slate-400">
          Brak miesięcznych danych do porównania akcji i gotówki.
        </div>
      )}
    </div>
  );
};

export default MonthlyAssetRatioChart;
