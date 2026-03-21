import React, { useState, useMemo } from 'react';
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
    benchmark_inflation?: number;
  }[];
  title?: string;
  benchmarkName?: string;
}

const PortfolioHistoryChart: React.FC<PortfolioHistoryChartProps> = ({ 
  data, 
  title = 'Wartość Portfela w Czasie',
  benchmarkName = 'Benchmark'
}) => {
  const [showInflation, setShowInflation] = useState(false);
  
  const hasContributionsLine = data.some((point) => point.net_contributions !== undefined);
  const hasBenchmarkLine = data.some((point) => point.benchmark_value !== undefined);
  const hasInflationData = data.some((point) => point.benchmark_inflation !== undefined);

  return (
    <div className="flex flex-col h-80 w-full">
      <div className="flex justify-end items-center mb-2 px-4 space-x-4">
        {hasInflationData && (
          <label className="flex items-center space-x-2 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={showInflation}
              onChange={(e) => setShowInflation(e.target.checked)}
              className="rounded border-gray-300 text-orange-500 focus:ring-orange-500"
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
              formatter={(value: number, name: string) => {
                if (name === 'benchmark_inflation') {
                  const point = data.find(p => p.benchmark_inflation === value);
                  const netContr = point?.net_contributions || 0;
                  const diff = netContr > 0 ? ((value - netContr) / netContr * 100).toFixed(2) : '0.00';
                  return [`${value.toFixed(2)} PLN (+${diff}%)`, 'Inflacja (PL)'];
                }
                return [
                  `${value.toFixed(2)} PLN`, 
                  name === 'benchmark_value'
                    ? benchmarkName
                    : name === 'net_contributions'
                      ? 'Wpłaty netto'
                      : name === 'value'
                        ? 'Wartość Portfela'
                        : name
                ];
              }}
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
                name={benchmarkName}
                stroke="#9ca3af"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                activeDot={{ r: 6, strokeWidth: 0 }}
              />
            )}
            {showInflation && hasInflationData && (
              <Line
                type="monotone"
                dataKey="benchmark_inflation"
                name="Inflacja (PL)"
                stroke="#f97316"
                strokeWidth={2}
                strokeDasharray="3 3"
                dot={false}
                activeDot={{ r: 6, strokeWidth: 0 }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default PortfolioHistoryChart;
