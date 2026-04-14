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
  TooltipItem,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { useTheme } from '../hooks/useTheme';

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

interface PriceHistoryChartProps {
  ticker: string;
  data: { date: string; close_price: number }[];
}

const PriceHistoryChart: React.FC<PriceHistoryChartProps> = ({ ticker, data }) => {
  const { isDark } = useTheme();

  const colors = {
    gridLine: isDark ? '#334155' : '#e2e8f0',
    zeroLine: isDark ? '#475569' : '#94a3b8',
    text: isDark ? '#94a3b8' : '#64748b',
    line: isDark ? '#60a5fa' : '#3b82f6', // blue-400 : blue-500
    bg: isDark ? 'rgba(96, 165, 250, 0.15)' : 'rgba(59, 130, 246, 0.15)',
    tooltipBg: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.9)',
    tooltipText: isDark ? '#f8fafc' : '#0f172a',
    tooltipBorder: isDark ? '#334155' : '#e2e8f0',
  };

  const chartData = {
    labels: data.map(d => d.date),
    datasets: [
      {
        label: `Cena ${ticker} (PLN)`,
        data: data.map(d => d.close_price),
        borderColor: colors.line,
        backgroundColor: colors.bg,
        fill: true,
        tension: 0.3,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 6,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          color: colors.text,
          font: { family: 'Inter', size: 12 }
        }
      },
      title: {
        display: true,
        text: `Historia Wyników ${ticker}`,
        color: colors.text,
        font: { family: 'Inter', size: 14, weight: 500 }
      },
      tooltip: {
        backgroundColor: colors.tooltipBg,
        titleColor: colors.text,
        bodyColor: colors.tooltipText,
        borderColor: colors.tooltipBorder,
        borderWidth: 1,
        padding: 12,
        boxPadding: 6,
        usePointStyle: true,
        callbacks: {
          label: (context: TooltipItem<'line'>) => {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(context.parsed.y);
            }
            return label;
          }
        }
      }
    },
    scales: {
      x: {
        grid: {
          display: false,
          drawBorder: false,
        },
        ticks: {
          color: colors.text,
          font: { family: 'Inter' },
          maxTicksLimit: 10,
        }
      },
      y: {
        beginAtZero: false,
        grid: {
          color: () => colors.gridLine,
          drawBorder: false,
        },
        ticks: {
          color: colors.text,
          font: { family: 'Inter' },
          callback: (value: string | number) => `${Number(value).toLocaleString('pl-PL')} PLN`,
        },
      },
    },
    interaction: {
      intersect: false,
      mode: 'index' as const,
    },
    maintainAspectRatio: false,
  };

  return (
    <div className="h-[400px] w-full">
      <Line data={chartData} options={options} />
    </div>
  );
};

export default PriceHistoryChart;
