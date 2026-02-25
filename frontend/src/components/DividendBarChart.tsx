import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface DividendBarChartProps {
  data: { label: string; amount: number }[];
}

const DividendBarChart: React.FC<DividendBarChartProps> = ({ data }) => {
  const chartData = {
    labels: data.map(d => d.label),
    datasets: [
      {
        label: 'Monthly Dividend Income (PLN)',
        data: data.map(d => d.amount),
        backgroundColor: '#10b981', // Emerald-500
        borderColor: '#059669', // Emerald-600
        borderWidth: 1,
        borderRadius: 4,
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
        display: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: {
          color: '#f3f4f6',
        },
      },
      x: {
        grid: {
          display: false,
        },
      },
    },
    maintainAspectRatio: false,
  };

  return (
    <div className="h-64 w-full">
      <Bar data={chartData} options={options} />
    </div>
  );
};

export default DividendBarChart;
