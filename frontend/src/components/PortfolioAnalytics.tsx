import React, { useMemo } from 'react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { PortfolioHistoryPoint } from '../api';
import { Holding } from '../types';
import MonthlyAssetRatioChart from './MonthlyAssetRatioChart';

interface PortfolioAnalyticsProps {
  holdings: Holding[];
  cashBalance: number;
  historyData: PortfolioHistoryPoint[];
}

const COLORS = [
  '#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658', '#8dd1e1', '#a4de6c', '#d0ed57', '#ff6b6b'
];

const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  if (percent < 0.05) return null;

  return (
    <text x={x} y={y} fill="white" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" fontSize={12} fontWeight="bold">
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

const PortfolioAnalytics: React.FC<PortfolioAnalyticsProps> = ({ holdings, cashBalance, historyData }) => {
  
  const assetData = useMemo(() => {
    const data = holdings.map(h => ({
      name: h.ticker,
      value: h.current_value || (h.quantity * h.average_buy_price)
    }));
    
    if (cashBalance > 0.01) {
        data.push({ name: 'Gotówka', value: cashBalance });
    }
    return data.sort((a, b) => b.value - a.value);
  }, [holdings, cashBalance]);

  const sectorData = useMemo(() => {
    const sectors: Record<string, number> = {};
    holdings.forEach(h => {
      const sector = h.sector && h.sector !== 'Unknown' ? h.sector : 'Inne';
      const val = h.current_value || (h.quantity * h.average_buy_price);
      sectors[sector] = (sectors[sector] || 0) + val;
    });

    if (cashBalance > 0.01) {
        sectors['Gotówka'] = cashBalance;
    }

    return Object.entries(sectors)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [holdings, cashBalance]);

  const industryData = useMemo(() => {
    const industries: Record<string, number> = {};
    holdings.forEach(h => {
      const industry = h.industry && h.industry !== 'Unknown' ? h.industry : 'Inne';
      const val = h.current_value || (h.quantity * h.average_buy_price);
      industries[industry] = (industries[industry] || 0) + val;
    });

     if (cashBalance > 0.01) {
        industries['Gotówka'] = cashBalance;
    }

    return Object.entries(industries)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [holdings, cashBalance]);

  const formatTooltip = (value: number) => `${value.toFixed(2)} PLN`;

  const ChartSection = ({ title, data }: { title: string, data: any[] }) => (
    <div className="bg-white p-6 rounded-lg shadow border border-gray-200 flex flex-col items-center">
      <h3 className="text-lg font-medium text-gray-900 mb-4 text-center">{title}</h3>
      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={80}
              fill="#8884d8"
              paddingAngle={2}
              dataKey="value"
              label={renderCustomLabel}
              labelLine={false}
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={formatTooltip} />
            <Legend verticalAlign="bottom" height={36}/>
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ChartSection title="Struktura Aktywów" data={assetData} />
        <ChartSection title="Ekspozycja na Sektory" data={sectorData} />
        <ChartSection title="Ekspozycja na Branże" data={industryData} />
      </div>

      <MonthlyAssetRatioChart data={historyData} />
    </div>
  );
};

export default PortfolioAnalytics;
