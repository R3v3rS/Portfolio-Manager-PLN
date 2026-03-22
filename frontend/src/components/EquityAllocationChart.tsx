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

interface EquityAllocationChartProps {
  data: EquityAllocation[];
}

const COLORS = [
  '#2563eb', // Blue
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
  const chartData = useMemo(() => {
    return [...data].sort((a, b) => b.percentage - a.percentage);
  }, [data]);

  const chartHeight = Math.max(400, chartData.length * 40);

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-gray-200 text-sm text-gray-500">
        Brak danych o alokacji akcji.
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const item = payload[0].payload as EquityAllocation;
      return (
        <div className="bg-white p-3 border border-gray-200 shadow-lg rounded-md">
          <p className="font-bold text-gray-900">{item.name} ({item.ticker})</p>
          <p className="text-sm text-blue-600">Alokacja: {item.percentage.toFixed(2)}%</p>
          <p className="text-sm text-gray-600">Wartość: {item.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN</p>
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
          <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#f3f4f6" />
          <XAxis type="number" hide domain={[0, 'auto']} />
          <YAxis
            type="category"
            dataKey="ticker"
            width={80}
            tick={{ fontSize: 12, fontWeight: 500, fill: '#374151' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f8fafc' }} />
          <Bar
            dataKey="percentage"
            radius={[0, 4, 4, 0]}
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
              style={{ fontSize: 11, fontWeight: 600, fill: '#4b5563' }}
              offset={10}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EquityAllocationChart;
