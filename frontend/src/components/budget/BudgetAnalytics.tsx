import React, { useEffect, useState } from 'react';
import { 
  PieChart, Pie, Cell, 
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import { budgetApi } from '../../api_budget';
import { Loader2 } from 'lucide-react';

interface AnalyticsData {
  total_expenses: number;
  by_category: { name: string; value: number; fill: string }[];
  by_envelope: { name: string; value: number }[];
}

interface Props {
  selectedAccountId: number;
}

export default function BudgetAnalytics({ selectedAccountId }: Props) {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(new Date().getFullYear());

  useEffect(() => {
    if (selectedAccountId) {
      fetchAnalytics();
    }
  }, [selectedAccountId, month, year]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const res = await budgetApi.getAnalytics<AnalyticsData>(selectedAccountId, year, month);
      setData(res);
    } catch (error) {
      console.error("Failed to fetch analytics", error);
    } finally {
      setLoading(false);
    }
  };

  const months = [
    "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
    "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"
  ];

  if (loading && !data) return <div className="flex justify-center p-8"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div>;

  return (
    <div className="space-y-8">
      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center bg-white p-4 rounded-xl shadow-sm border border-gray-100">
        <div className="flex gap-2">
            <select 
            value={month} 
            onChange={(e) => setMonth(Number(e.target.value))}
            className="p-2 border rounded-lg font-medium text-gray-700 bg-gray-50 hover:bg-white transition"
            >
            {months.map((m, i) => (
                <option key={i} value={i + 1}>{m}</option>
            ))}
            </select>
            <select 
            value={year} 
            onChange={(e) => setYear(Number(e.target.value))}
            className="p-2 border rounded-lg font-medium text-gray-700 bg-gray-50 hover:bg-white transition"
            >
            {[2024, 2025, 2026, 2027].map(y => (
                <option key={y} value={y}>{y}</option>
            ))}
            </select>
        </div>
        
        <div className="ml-auto text-right">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Suma Wydatków</p>
          <p className="text-2xl font-bold text-gray-900">{data?.total_expenses.toFixed(2)} PLN</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Category Chart */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col items-center">
          <h3 className="text-lg font-bold mb-6 text-gray-800 w-full text-left">Wydatki wg Kategorii</h3>
          {data?.by_category.length === 0 ? (
             <div className="h-64 flex items-center justify-center text-gray-400">Brak danych</div>
          ) : (
            <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                    <Pie
                    data={data?.by_category}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                    >
                    {data?.by_category.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => `${value.toFixed(2)} PLN`} />
                    <Legend />
                </PieChart>
                </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Envelope Chart */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h3 className="text-lg font-bold mb-6 text-gray-800">Wydatki wg Kopert</h3>
          {data?.by_envelope.length === 0 ? (
             <div className="h-64 flex items-center justify-center text-gray-400">Brak danych</div>
          ) : (
            <div className="h-[400px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    data={data?.by_envelope}
                    layout="vertical"
                    margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
                >
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="name" width={100} tick={{fontSize: 12}} />
                    <Tooltip formatter={(value: number) => `${value.toFixed(2)} PLN`} />
                    <Bar dataKey="value" fill="#8884d8" radius={[0, 4, 4, 0]}>
                        {data?.by_envelope.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={index % 2 === 0 ? "#8884d8" : "#82ca9d"} />
                        ))}
                    </Bar>
                </BarChart>
                </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
