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

interface MonthlyAssetRatioChartProps {
  data: PortfolioHistoryPoint[];
}

const STOCK_COLOR = '#dc2626';
const CASH_COLOR = '#16a34a';

const formatCurrency = (value: number) => `${value.toFixed(2)} PLN`;

const MonthlyAssetRatioChart: React.FC<MonthlyAssetRatioChartProps> = ({ data }) => {
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
    <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
      <div className="mb-4">
        <h3 className="text-lg font-medium text-gray-900">Akcje vs gotówka w czasie</h3>
        <p className="text-sm text-gray-500">
          Miesięczne porównanie wartości akcji w PLN i gotówki wraz z udziałem obu części portfela.
        </p>
      </div>

      {chartData.length > 0 ? (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              margin={{ top: 10, right: 24, left: 8, bottom: 48 }}
              barCategoryGap="18%"
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis
                dataKey="label"
                angle={-35}
                textAnchor="end"
                height={70}
                interval={0}
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
                cursor={{ fill: 'rgba(229, 231, 235, 0.35)' }}
                contentStyle={{
                  backgroundColor: '#fff',
                  borderRadius: '8px',
                  border: '1px solid #e5e7eb',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
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
                labelStyle={{ color: '#374151', fontWeight: 'bold', marginBottom: '4px' }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Bar dataKey="akcje" name="Akcje" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell key={`stocks-${entry.label}`} fill={STOCK_COLOR} />
                ))}
              </Bar>
              <Bar dataKey="gotowka" name="Gotówka" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell key={`cash-${entry.label}`} fill={CASH_COLOR} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-gray-200 text-sm text-gray-500">
          Brak miesięcznych danych do porównania akcji i gotówki.
        </div>
      )}
    </div>
  );
};

export default MonthlyAssetRatioChart;
