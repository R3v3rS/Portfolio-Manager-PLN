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

interface PortfolioProfitChartProps {
  data: { date: string; label: string; value: number }[];
  title?: string;
}

const PortfolioProfitChart: React.FC<PortfolioProfitChartProps> = ({ data, title = 'Wyniki Zysku/Straty' }) => {
  const { isDark } = useTheme();
  
  const colors = {
    gridLine: isDark ? '#334155' : '#e2e8f0', // slate-700 : slate-200
    zeroLine: isDark ? '#475569' : '#94a3b8', // slate-600 : slate-400
    text: isDark ? '#94a3b8' : '#64748b', // slate-400 : slate-500
    positiveLine: isDark ? '#34d399' : '#10b981', // emerald-400 : emerald-500
    negativeLine: isDark ? '#f87171' : '#ef4444', // red-400 : red-500
    positiveBg: isDark ? 'rgba(52, 211, 153, 0.15)' : 'rgba(16, 185, 129, 0.2)',
    negativeBg: isDark ? 'rgba(248, 113, 113, 0.15)' : 'rgba(239, 68, 68, 0.2)',
    tooltipBg: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.9)', // slate-950 : white
    tooltipText: isDark ? '#f8fafc' : '#0f172a',
    tooltipBorder: isDark ? '#334155' : '#e2e8f0',
  };

  const chartData = {
    labels: data.map(d => d.label),
    datasets: [
      {
        label: 'Skumulowany Zysk (PLN)',
        data: data.map(d => d.value),
        borderColor: () => {
          return colors.positiveLine; // Default
        },
        segment: {
          borderColor: (ctx: { p0: { parsed: { y: number } } }) => ctx.p0.parsed.y >= 0 ? colors.positiveLine : colors.negativeLine,
          backgroundColor: (ctx: { p0: { parsed: { y: number } } }) => ctx.p0.parsed.y >= 0 ? colors.positiveBg : colors.negativeBg,
        },
        fill: {
            target: 'origin',
            above: colors.positiveBg,
            below: colors.negativeBg
        },
        tension: 0.4, // Smoother curve
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 6,
        pointBackgroundColor: (context: ScriptableContext<'line'>) => {
            const val = context.raw as number;
            return val >= 0 ? colors.positiveLine : colors.negativeLine;
        }
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
        display: !!title,
        text: title,
        color: colors.text,
        font: { family: 'Inter', size: 14, weight: '500' as const }
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
          label: (context: any) => {
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
        beginAtZero: true,
        grid: {
            color: (context: ScriptableScaleContext) => {
                if (context.tick.value === 0) return colors.zeroLine;
                return colors.gridLine;
            },
            lineWidth: (context: ScriptableScaleContext) => {
                if (context.tick.value === 0) return 2;
                return 1;
            },
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

export default PortfolioProfitChart;
