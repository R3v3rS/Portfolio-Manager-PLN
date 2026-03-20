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
  Filler,
  ChartOptions,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface PortfolioProfitChartProps {
  data: { date: string; label: string; value: number }[];
  title?: string;
}

const PortfolioProfitChart: React.FC<PortfolioProfitChartProps> = ({ data, title = 'Wyniki Zysku/Straty' }) => {
  const chartData = {
    labels: data.map((d) => d.label),
    datasets: [
      {
        label: 'Skumulowany Zysk (PLN)',
        data: data.map((d) => d.value),
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99, 102, 241, 0.15)',
        fill: {
          target: 'origin',
          above: 'rgba(16, 185, 129, 0.2)',
          below: 'rgba(239, 68, 68, 0.2)',
        },
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: data.map((entry) => entry.value >= 0 ? '#10b981' : '#ef4444'),
      },
    ],
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: title,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: '#e5e7eb',
        },
        ticks: {
          callback: (value) => `${value} PLN`,
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

export default PortfolioProfitChart;
