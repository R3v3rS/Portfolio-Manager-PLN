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
  ScriptableContext
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

const PortfolioProfitChart: React.FC<PortfolioProfitChartProps> = ({ data, title = 'Profit/Loss Performance' }) => {
  const chartData = {
    labels: data.map(d => d.label),
    datasets: [
      {
        label: 'Cumulative Profit (PLN)',
        data: data.map(d => d.value),
        borderColor: (context: ScriptableContext<'line'>) => {
          const ctx = context.chart.ctx;
          const gradient = ctx.createLinearGradient(0, 0, 0, context.chart.height);
          // Simple check: if the latest value is positive, use green, else red?
          // Or we can just use a fixed color, but user asked for green/red areas.
          // Let's use a solid color for the line based on the last value for now, 
          // or we can use segment styling if we want the line to change color at 0.
          return '#6366f1'; // Indigo default
        },
        segment: {
          borderColor: (ctx: any) => ctx.p0.parsed.y >= 0 ? '#10b981' : '#ef4444', // Green if start >= 0, Red if < 0 (approx)
          backgroundColor: (ctx: any) => ctx.p0.parsed.y >= 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
        },
        fill: {
            target: 'origin',
            above: 'rgba(16, 185, 129, 0.2)',   // Area will be green above the origin
            below: 'rgba(239, 68, 68, 0.2)'    // And red below the origin
        },
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: (context: any) => {
            const val = context.raw;
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
        beginAtZero: true, // Important for the 0 line
        grid: {
            color: (context: any) => {
                if (context.tick.value === 0) return '#374151'; // Darker line at 0
                return '#e5e7eb';
            },
            lineWidth: (context: any) => {
                if (context.tick.value === 0) return 2;
                return 1;
            }
        },
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

export default PortfolioProfitChart;
