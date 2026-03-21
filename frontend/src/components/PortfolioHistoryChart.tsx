import React from 'react';
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

interface PortfolioHistoryChartProps {
  data: {
    date: string;
    label: string;
    value: number;
    net_contributions?: number;
    benchmark_value?: number;
  }[];
  title?: string;
}

const PortfolioHistoryChart: React.FC<PortfolioHistoryChartProps> = ({ data, title = 'Wartość Portfela w Czasie' }) => {
  const hasContributionsLine = data.some((point) => point.net_contributions !== undefined);
  const hasBenchmarkLine = data.some((point) => point.benchmark_value !== undefined);

  return (
    <div className="h-80 w-full">
      {/* Title is handled by parent or chart configuration, but Recharts doesn't have a built-in Title component like Chart.js 
          We can render it as a standard HTML element if needed, or rely on parent. 
          The previous implementation had a title prop. */}
      {/* <h3 className="text-center mb-4 font-bold text-gray-700">{title}</h3> */}
      
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
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
          <XAxis 
            dataKey="label" 
            tick={{ fontSize: 12, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={false}
          />
          <YAxis 
            tick={{ fontSize: 12, fill: '#6b7280' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => `${value}`}
          />
          <Tooltip 
            contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e7eb', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
            formatter={(value: number, name: string) => [
              `${value.toFixed(2)} PLN`, 
              name === 'benchmark_value'
                ? 'Benchmark'
                : name === 'net_contributions'
                  ? 'Wpłaty netto'
                  : name
            ]}
            labelStyle={{ color: '#374151', fontWeight: 'bold', marginBottom: '4px' }}
          />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Line
            type="monotone"
            dataKey="value"
            name="Wartość Portfela"
            stroke="#10b981"
            strokeWidth={3}
            dot={{ r: 4, fill: '#10b981', strokeWidth: 2, stroke: '#fff' }}
            activeDot={{ r: 6, strokeWidth: 0 }}
          />
          {hasContributionsLine && (
            <Line
              type="monotone"
              dataKey="net_contributions"
              name="Wpłaty netto"
              stroke="#4338ca"
              strokeWidth={2}
              dot={{ r: 3, fill: '#4338ca', strokeWidth: 2, stroke: '#fff' }}
              activeDot={{ r: 6, strokeWidth: 0 }}
            />
          )}
          {hasBenchmarkLine && (
            <Line
              type="monotone"
              dataKey="benchmark_value"
              name="Benchmark"
              stroke="#9ca3af"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
              activeDot={{ r: 6, strokeWidth: 0 }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PortfolioHistoryChart;
