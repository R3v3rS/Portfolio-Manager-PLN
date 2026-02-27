import React from 'react';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { Pie } from 'react-chartjs-2';
import { Holding } from '../types';

ChartJS.register(ArcElement, Tooltip, Legend);

interface PortfolioChartProps {
  holdings: Holding[];
  cash: number;
}

const PortfolioChart: React.FC<PortfolioChartProps> = ({ holdings, cash }) => {
  const data = {
    labels: ['Gotówka', ...holdings.map(h => h.ticker)],
    datasets: [
      {
        data: [cash, ...holdings.map(h => (h.quantity * (h.current_price || h.average_buy_price)))],
        backgroundColor: [
          '#E5E7EB', // Cash - Gray
          '#3B82F6', // Blue
          '#10B981', // Green
          '#F59E0B', // Yellow
          '#EF4444', // Red
          '#8B5CF6', // Purple
          '#EC4899', // Pink
          '#6366F1', // Indigo
        ],
        borderColor: '#ffffff',
        borderWidth: 2,
      },
    ],
  };

  const options = {
    plugins: {
      legend: {
        position: 'right' as const,
      },
    },
    maintainAspectRatio: false,
  };

  return (
    <div className="h-64">
      <Pie data={data} options={options} />
    </div>
  );
};

export default PortfolioChart;
