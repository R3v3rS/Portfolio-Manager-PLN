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
  ScriptableScaleContext,
  ScriptableContext,
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
    labels: data.map(d => d.label),
    datasets: [
      {
        label: 'Skumulowany Zysk (PLN)',
        data: data.map(d => d.value),
        borderColor: () => {
          return '#6366f1'; // Indigo default
        },
        segment: {
          borderColor: (ctx: { p0: { parsed: { y: number } } }) => ctx.p0.parsed.y >= 0 ? '#10b981' : '#ef4444',
          backgroundColor: (ctx: { p0: { parsed: { y: number } } }) => ctx.p0.parsed.y >= 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
        },
        fill: {
            target: 'origin',
            above: 'rgba(16, 185, 129, 0.2)',
            below: 'rgba(239, 68, 68, 0.2)'
        },
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: (context: ScriptableContext<'line'>) => {
            const val = context.raw as number;
            return val >= 0 ? '#10b981' : '#ef4444';
        }
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
        beginAtZero: true,
        grid: {
            color: (context: ScriptableScaleContext) => {
                if (context.tick.value === 0) return '#374151';
                return '#e5e7eb';
            },
            lineWidth: (context: ScriptableScaleContext) => {
                if (context.tick.value === 0) return 2;
                return 1;
            }
        },
        ticks: {
          callback: (value: string | number) => `${value} PLN`,
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
