import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from 'recharts';
import { EquityAllocation } from '../types';
import { useTheme } from '../hooks/useTheme';

interface EquityAllocationChartProps {
  data: EquityAllocation[];
}

const COLORS = [
  '#3b82f6', // Blue
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#ef4444', // Red
  '#8b5cf6', // Violet
  '#06b6d4', // Cyan
  '#ec4899', // Pink
  '#f97316', // Orange
  '#6366f1', // Indigo
  '#84cc16', // Lime
];

const EquityAllocationChart: React.FC<EquityAllocationChartProps> = ({ data }) => {
  const { isDark } = useTheme();

  const themeColors = {
    grid: isDark ? '#334155' : '#f3f4f6', // slate-700 : gray-100
    text: isDark ? '#94a3b8' : '#374151', // slate-400 : gray-700
    cursor: isDark ? 'rgba(51, 65, 85, 0.4)' : '#f8fafc',
    labelFill: isDark ? '#cbd5e1' : '#4b5563', // slate-300 : gray-600
  };

  const chartData = useMemo(() => {
    return [...data].sort((a, b) => b.percentage - a.percentage);
  }, [data]);

  const chartHeight = Math.max(400, chartData.length * 40);

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-gray-200 dark:border-slate-700 text-sm text-gray-500 dark:text-slate-400">
        Brak danych o alokacji akcji.
      </div>
    );
  }

  type TooltipEntry = { payload: EquityAllocation };

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: TooltipEntry[] }) => {
    if (active && payload && payload.length) {
      const item = payload[0].payload as EquityAllocation;
      return (
        <div className="bg-white dark:bg-slate-900 p-4 border border-gray-200 dark:border-slate-700 shadow-xl rounded-xl backdrop-blur-md bg-opacity-90 dark:bg-opacity-90">
          <p className="font-bold text-gray-900 dark:text-slate-100">{item.name} ({item.ticker})</p>
          <p className="text-sm font-semibold text-blue-600 dark:text-blue-400 mt-1">Alokacja: {item.percentage.toFixed(2)}%</p>
          <p className="text-sm text-gray-600 dark:text-slate-400">Wartość: {item.value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full" style={{ height: chartHeight > 600 ? '600px' : `${chartHeight}px`, overflowY: chartHeight > 600 ? 'auto' : 'hidden' }}>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 80, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke={themeColors.grid} />
          <XAxis type="number" hide domain={[0, 'auto']} />
          <YAxis
            type="category"
            dataKey="ticker"
            width={80}
            tick={{ fontSize: 12, fontWeight: 500, fill: themeColors.text }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: themeColors.cursor }} />
          <Bar
            dataKey="percentage"
            radius={[0, 6, 6, 0]}
            barSize={24}
          >
            {chartData.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={COLORS[index % COLORS.length]} 
              />
            ))}
            <LabelList
              dataKey="percentage"
              position="right"
              formatter={(val: number) => `${val.toFixed(2)}%`}
              style={{ fontSize: 11, fontWeight: 600, fill: themeColors.labelFill }}
              offset={10}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EquityAllocationChart;
