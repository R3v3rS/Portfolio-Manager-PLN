import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface PriceHistoryChartProps {
  ticker: string;
  data: { date: string; close_price: number }[];
}

const PriceHistoryChart: React.FC<PriceHistoryChartProps> = ({ ticker, data }) => {
  const chartData = {
    labels: data.map(d => d.date),
    datasets: [
      {
        label: `${ticker} Price (PLN)`,
        data: data.map(d => d.close_price),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.5)',
        tension: 0.1,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: `${ticker} Historical Performance`,
      },
    },
    scales: {
      y: {
        beginAtZero: false,
      },
    },
    maintainAspectRatio: false,
  };

  return (
    <div className="h-64 w-full">
      <Line data={chartData} options={options} />
    </div>
  );
};

export default PriceHistoryChart;
