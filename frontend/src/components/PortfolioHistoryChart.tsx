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

interface PortfolioHistoryChartProps {
  data: { date: string; label: string; value: number }[];
  title?: string;
}

const PortfolioHistoryChart: React.FC<PortfolioHistoryChartProps> = ({ data, title = 'Wartość Portfela w Czasie' }) => {
  const chartData = {
    labels: data.map(d => d.label),
    datasets: [
      {
        label: `Całkowita Wartość (PLN)`,
        data: data.map(d => d.value),
        borderColor: '#10b981', // Emerald for savings
        backgroundColor: 'rgba(16, 185, 129, 0.5)',
        tension: 0.3, // Smoother curve
        pointRadius: 4,
        pointBackgroundColor: '#059669',
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
        text: title,
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        ticks: {
          callback: (value: any) => `${value} PLN`,
        },
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

export default PortfolioHistoryChart;