import React from 'react';
import { cn } from '../../lib/utils.ts';

interface ProfitPoint {
  date: string;
  label: string;
  value: number;
}

interface Profit30dMatrixProps {
  data: ProfitPoint[];
  rowLabel?: string;
  summaryLabel?: string;
  mode?: 'relative_to_first' | 'day_over_day';
}

const Profit30dMatrix: React.FC<Profit30dMatrixProps> = ({
  data,
  rowLabel = '% zmiany zysku',
  summaryLabel = '30D',
  mode = 'relative_to_first',
}) => {
  if (!data || data.length < 2) {
    return <div className="p-4 text-center text-gray-500">Za mało danych do wyliczenia zmian procentowych.</div>;
  }

  const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date));
  
  let pointsWithPct;
  if (mode === 'day_over_day') {
    pointsWithPct = sorted.map((point, index) => {
      if (index === 0) {
        return { ...point, pct: null as number | null };
      }
      const prevValue = sorted[index - 1].value;
      if (Math.abs(prevValue) < 0.0001) {
        return { ...point, pct: null as number | null };
      }
      const pct = ((point.value - prevValue) / Math.abs(prevValue)) * 100;
      return { ...point, pct };
    });
  } else {
    const baseValue = sorted[0].value;
    pointsWithPct = sorted.map((point) => {
      if (Math.abs(baseValue) < 0.0001) {
        return { ...point, pct: null as number | null };
      }
      const pct = ((point.value - baseValue) / Math.abs(baseValue)) * 100;
      return { ...point, pct };
    });
  }

  const total30dPct = mode === 'day_over_day' 
    ? null 
    : (pointsWithPct[pointsWithPct.length - 1]?.pct ?? null);

  const formatPct = (value: number | null) => {
    if (value === null || Number.isNaN(value) || Math.abs(value) < 0.001) return '-';
    return `${value.toFixed(2)}%`;
  };

  const getCellClass = (value: number | null, isSummary = false) => {
    if (value === null || Number.isNaN(value) || Math.abs(value) < 0.001) return 'text-gray-400';

    if (value > 0) {
      return isSummary ? 'text-green-700 font-bold bg-green-100' : 'text-green-600 bg-green-50';
    }

    return isSummary ? 'text-red-700 font-bold bg-red-100' : 'text-red-600 bg-red-50';
  };

  const formatDateHeader = (isoDate: string) => {
    const dt = new Date(isoDate);
    if (Number.isNaN(dt.getTime())) return isoDate;
    return dt.toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit' });
  };

  return (
    <div className="overflow-x-auto bg-white rounded-lg shadow border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider sticky left-0 bg-gray-50 z-10">
              Okres
            </th>
            {pointsWithPct.map((point) => (
              <th key={point.date} className="px-2 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                {formatDateHeader(point.date)}
              </th>
            ))}
            {mode !== 'day_over_day' && (
              <th className="px-3 py-3 text-center text-xs font-bold text-gray-700 uppercase tracking-wider bg-gray-100 whitespace-nowrap">
                {summaryLabel}
              </th>
            )}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          <tr className="hover:bg-gray-50 transition-colors">
            <td className="px-3 py-3 whitespace-nowrap text-sm font-bold text-gray-900 sticky left-0 bg-white z-10 border-r border-gray-100">
              {rowLabel}
            </td>
            {pointsWithPct.map((point) => (
              <td
                key={`${point.date}-pct`}
                className={cn(
                  'px-2 py-3 whitespace-nowrap text-xs text-center border-r border-gray-50',
                  getCellClass(point.pct)
                )}
              >
                {formatPct(point.pct)}
              </td>
            ))}
            {mode !== 'day_over_day' && (
              <td
                className={cn(
                  'px-3 py-3 whitespace-nowrap text-sm text-center font-bold border-l border-gray-200',
                  getCellClass(total30dPct, true)
                )}
              >
                {formatPct(total30dPct)}
              </td>
            )}
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default Profit30dMatrix;
