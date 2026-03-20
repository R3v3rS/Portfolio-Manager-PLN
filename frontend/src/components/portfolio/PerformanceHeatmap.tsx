import React, { useEffect, useState } from 'react';
import api from '../../api';
import { cn } from '../../lib/utils.ts';

interface PerformanceHeatmapProps {
  portfolioId: number;
}

interface MonthlyReturn {
  [month: string]: number | string; // "1", "2", ..., "12", "YTD"
}

interface PerformanceMatrix {
  [year: string]: MonthlyReturn;
}

const PerformanceHeatmap: React.FC<PerformanceHeatmapProps> = ({ portfolioId }) => {
  const [matrix, setMatrix] = useState<PerformanceMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPerformance = async () => {
      setLoading(true);
      try {
        const response = await api.get(`/${portfolioId}/performance`);
        setMatrix(response.data.matrix);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch performance matrix:', err);
        setError('Nie udało się pobrać danych o wynikach.');
      } finally {
        setLoading(false);
      }
    };

    if (portfolioId) {
      fetchPerformance();
    }
  }, [portfolioId]);

  if (loading) {
    return <div className="p-4 text-center text-gray-500">Ładowanie wyników...</div>;
  }

  if (error) {
    return <div className="p-4 text-center text-red-500">{error}</div>;
  }

  if (!matrix || Object.keys(matrix).length === 0) {
    return <div className="p-4 text-center text-gray-500">Brak danych do wyświetlenia macierzy wyników.</div>;
  }

  // Sort years descending
  const years = Object.keys(matrix).sort((a, b) => parseInt(b) - parseInt(a));
  
  const months = [
    { key: '1', label: 'Sty' },
    { key: '2', label: 'Lut' },
    { key: '3', label: 'Mar' },
    { key: '4', label: 'Kwi' },
    { key: '5', label: 'Maj' },
    { key: '6', label: 'Cze' },
    { key: '7', label: 'Lip' },
    { key: '8', label: 'Sie' },
    { key: '9', label: 'Wrz' },
    { key: '10', label: 'Paź' },
    { key: '11', label: 'Lis' },
    { key: '12', label: 'Gru' },
  ];

  const formatValue = (val: number | string | undefined) => {
    if (val === undefined || val === null) return '-';
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num)) return '-';
    if (Math.abs(num) < 0.001) return '-'; // Treat 0 as -
    return `${num.toFixed(2)}%`;
  };

  const getCellClass = (val: number | string | undefined, isYtd: boolean = false) => {
    if (val === undefined || val === null) return 'text-gray-400';
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num) || Math.abs(num) < 0.001) return 'text-gray-400';
    
    if (num > 0) {
      return isYtd 
        ? 'text-green-700 font-bold bg-green-100' 
        : 'text-green-600 bg-green-50';
    } else {
      return isYtd 
        ? 'text-red-700 font-bold bg-red-100' 
        : 'text-red-600 bg-red-50';
    }
  };

  return (
    <div className="overflow-x-auto bg-white rounded-lg shadow border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider sticky left-0 bg-gray-50 z-10">
              Rok
            </th>
            {months.map((m) => (
              <th key={m.key} className="px-2 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                {m.label}
              </th>
            ))}
            <th className="px-3 py-3 text-center text-xs font-bold text-gray-700 uppercase tracking-wider bg-gray-100">
              YTD
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {years.map((year) => {
            const yearData = matrix[year];
            return (
              <tr key={year} className="hover:bg-gray-50 transition-colors">
                <td className="px-3 py-3 whitespace-nowrap text-sm font-bold text-gray-900 sticky left-0 bg-white z-10 border-r border-gray-100">
                  {year}
                </td>
                {months.map((m) => {
                  const val = yearData[m.key];
                  return (
                    <td 
                      key={`${year}-${m.key}`} 
                      className={cn(
                        "px-2 py-3 whitespace-nowrap text-xs text-center border-r border-gray-50",
                        getCellClass(val as number)
                      )}
                    >
                      {formatValue(val as number)}
                    </td>
                  );
                })}
                <td className={cn(
                  "px-3 py-3 whitespace-nowrap text-sm text-center font-bold border-l border-gray-200",
                  getCellClass(yearData['YTD'] as number, true)
                )}>
                  {formatValue(yearData['YTD'] as number)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default PerformanceHeatmap;
