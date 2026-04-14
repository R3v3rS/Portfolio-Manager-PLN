import React, { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { useTheme } from '../hooks/useTheme';

interface PortfolioHistoryChartProps {
  data: {
    date: string;
    label: string;
    value: number;
    net_value?: number;
    net_contributions?: number;
    benchmark_value?: number;
    benchmark_inflation?: number;
  }[];
  title?: string;
  benchmarkName?: string;
}

const PortfolioHistoryChart: React.FC<PortfolioHistoryChartProps> = ({ 
  data, 
  benchmarkName = 'Benchmark'
}) => {
  const [showInflation, setShowInflation] = useState(false);
  const { isDark } = useTheme();
  
  const hasContributionsLine = data.some((point) => point.net_contributions !== undefined);
  const hasNetValueLine = data.some((point) => point.net_value !== undefined);
  const hasBenchmarkLine = data.some((point) => point.benchmark_value !== undefined);
  const hasInflationData = data.some((point) => point.benchmark_inflation !== undefined);

  // Modern colors
  const colors = {
    value: isDark ? '#34d399' : '#10b981', // emerald-400 : emerald-500
    netValue: isDark ? '#a78bfa' : '#8b5cf6', // violet-400 : violet-500
    contributions: isDark ? '#60a5fa' : '#3b82f6', // blue-400 : blue-500
    benchmark: isDark ? '#94a3b8' : '#9ca3af', // slate-400 : gray-400
    inflation: isDark ? '#fb923c' : '#f97316', // orange-400 : orange-500
    grid: isDark ? '#334155' : '#e2e8f0', // slate-700 : slate-200
    text: isDark ? '#94a3b8' : '#64748b', // slate-400 : slate-500
    tooltipBg: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.9)', // slate-950 : white
    tooltipBorder: isDark ? '#334155' : '#e2e8f0',
    tooltipText: isDark ? '#f8fafc' : '#0f172a',
  };

  return (
    <div className="flex flex-col h-[400px] w-full">
      <div className="flex justify-end items-center mb-4 px-4 space-x-4">
        {hasInflationData && (
          <label className="flex items-center space-x-2 text-sm text-slate-600 dark:text-slate-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showInflation}
              onChange={(e) => setShowInflation(e.target.checked)}
              className="rounded border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-orange-500 focus:ring-orange-500"
            />
            <span>Inflacja (PL)</span>
          </label>
        )}
      </div>
      
      <div className="flex-1 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{
              top: 10,
              right: 30,
              left: 20,
              bottom: 5,
            }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={colors.grid} />
            <XAxis 
              dataKey="label" 
              tick={{ fontSize: 12, fill: colors.text }}
              axisLine={{ stroke: colors.grid }}
              tickLine={false}
              dy={10}
            />
            <YAxis 
              tick={{ fontSize: 12, fill: colors.text }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(value) => `${value.toLocaleString('pl-PL')}`}
              dx={-10}
            />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: colors.tooltipBg, 
                borderRadius: '12px', 
                border: `1px solid ${colors.tooltipBorder}`, 
                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
                backdropFilter: 'blur(8px)'
              }}
              formatter={(value: number, name: string) => {
                if (name === 'benchmark_inflation') {
                  const point = data.find(p => p.benchmark_inflation === value);
                  const netContr = point?.net_contributions || 0;
                  const diff = netContr > 0 ? ((value - netContr) / netContr * 100).toFixed(2) : '0.00';
                  return [`${value.toLocaleString('pl-PL', {minimumFractionDigits: 2, maximumFractionDigits: 2})} PLN (+${diff}%)`, 'Inflacja (PL)'];
                }
                return [
                  `${value.toLocaleString('pl-PL', {minimumFractionDigits: 2, maximumFractionDigits: 2})} PLN`, 
                  name === 'benchmark_value'
                    ? benchmarkName
                    : name === 'net_contributions'
                      ? 'Wpłaty netto'
                      : name === 'net_value'
                        ? 'Wartość netto (po podatku)'
                        : name === 'value'
                          ? 'Wartość Portfela'
                          : name
                ];
              }}
              labelStyle={{ color: colors.tooltipText, fontWeight: '600', marginBottom: '8px' }}
            />
            <Legend wrapperStyle={{ paddingTop: '20px', color: colors.text }} />
            <Line
              type="monotone"
              dataKey="value"
              name="Wartość Portfela"
              stroke={colors.value}
              strokeWidth={3}
              dot={false}
              activeDot={{ r: 6, fill: colors.value, strokeWidth: 0 }}
            />
            {hasNetValueLine && (
              <Line
                type="monotone"
                dataKey="net_value"
                name="Wartość netto (po podatku)"
                stroke={colors.netValue}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6, fill: colors.netValue, strokeWidth: 0 }}
              />
            )}
            {hasContributionsLine && (
              <Line
                type="monotone"
                dataKey="net_contributions"
                name="Wpłaty netto"
                stroke={colors.contributions}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6, fill: colors.contributions, strokeWidth: 0 }}
              />
            )}
            {hasBenchmarkLine && (
              <Line
                type="monotone"
                dataKey="benchmark_value"
                name={benchmarkName}
                stroke={colors.benchmark}
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                activeDot={{ r: 6, fill: colors.benchmark, strokeWidth: 0 }}
              />
            )}
            {showInflation && hasInflationData && (
              <Line
                type="monotone"
                dataKey="benchmark_inflation"
                name="Inflacja (PL)"
                stroke={colors.inflation}
                strokeWidth={2}
                strokeDasharray="3 3"
                dot={false}
                activeDot={{ r: 6, fill: colors.inflation, strokeWidth: 0 }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default PortfolioHistoryChart;
