import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Link } from 'react-router-dom';
import { Wallet, TrendingUp, CreditCard, ArrowRight, Briefcase, Landmark, PiggyBank } from 'lucide-react';
import { cn } from '../lib/utils';

interface GlobalSummary {
  net_worth: number;
  total_assets: number;
  total_liabilities: number;
  liabilities_breakdown: {
    short_term: number;
    long_term: number;
  };
  assets_breakdown: {
    budget_cash: number;
    invest_cash: number;
    savings: number;
    bonds: number;
    stocks: number;
    ppk: number;
  };
  quick_stats: {
    free_pool: number;
    next_loan_installment: number;
    next_loan_date: string | null;
  };
}

const MainDashboard: React.FC = () => {
  const [data, setData] = useState<GlobalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await axios.get('/api/dashboard/global-summary');
        setData(res.data);
      } catch (err) {
        console.error(err);
        setError('Nie udało się pobrać danych kokpitu.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div className="p-12 text-center text-gray-500">Ładowanie kokpitu...</div>;
  if (error) return <div className="p-12 text-center text-red-600">{error}</div>;
  if (!data) return null;

  const chartData = [
    { name: 'Gotówka (Budżet)', value: data.assets_breakdown.budget_cash, color: '#10B981' }, // emerald-500
    { name: 'Gotówka (Inw.)', value: data.assets_breakdown.invest_cash, color: '#14B8A6' }, // teal-500
    { name: 'Konta Oszcz.', value: data.assets_breakdown.savings, color: '#6366F1' }, // indigo-500
    { name: 'Obligacje', value: data.assets_breakdown.bonds, color: '#F59E0B' }, // amber-500
    { name: 'Akcje / ETF', value: data.assets_breakdown.stocks, color: '#3B82F6' }, // blue-500
    { name: 'PPK', value: data.assets_breakdown.ppk, color: '#A855F7' }, // purple-500
  ].filter(item => item.value > 0);

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Pulpit Dowódcy</h1>
        <p className="mt-1 text-sm text-gray-500">Globalny przegląd Twojego majątku</p>
      </div>

      {/* Top Row: Big Numbers */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Assets */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center space-x-3 mb-2">
            <div className="p-2 bg-green-100 rounded-lg">
              <TrendingUp className="h-6 w-6 text-green-600" />
            </div>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Aktywa</h3>
          </div>
          <div>
            <p className="text-3xl font-bold text-gray-900">{data.total_assets.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN</p>
            <p className="text-xs text-gray-400 mt-1">Gotówka + Inwestycje</p>
          </div>
        </div>

        {/* Liabilities */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col justify-between hover:shadow-md transition-shadow">
          <div className="flex items-center space-x-3 mb-2">
            <div className="p-2 bg-red-100 rounded-lg">
              <CreditCard className="h-6 w-6 text-red-600" />
            </div>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Zobowiązania</h3>
          </div>
          <div>
            <p className="text-3xl font-bold text-gray-900">{data.total_liabilities.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN</p>
            <div className="mt-2 space-y-1">
              <p className="text-xs text-gray-500">
                Krótkoterminowe (pożyczka gotówkowa, raty 0%):{' '}
                <span className="font-semibold text-gray-700">
                  {data.liabilities_breakdown.short_term.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN
                </span>
              </p>
              <p className="text-xs text-gray-500">
                Długoterminowe (kredyt hipoteczny):{' '}
                <span className="font-semibold text-gray-700">
                  {data.liabilities_breakdown.long_term.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN
                </span>
              </p>
            </div>
          </div>
        </div>

        {/* Net Worth - The Main Card */}
        <div className={cn(
          "bg-white rounded-2xl shadow-lg border-2 p-6 flex flex-col justify-between transform hover:-translate-y-1 transition-all duration-200 relative overflow-hidden",
          data.net_worth >= 0 ? "border-green-100 ring-4 ring-green-50/50" : "border-red-100 ring-4 ring-red-50/50"
        )}>
          <div className={cn("absolute top-0 right-0 w-32 h-32 rounded-full -mr-16 -mt-16 opacity-10", data.net_worth >= 0 ? "bg-green-500" : "bg-red-500")}></div>
          
          <div className="flex items-center space-x-3 mb-2 relative z-10">
            <div className={cn("p-2 rounded-lg", data.net_worth >= 0 ? "bg-green-100" : "bg-red-100")}>
              <Landmark className={cn("h-6 w-6", data.net_worth >= 0 ? "text-green-700" : "text-red-700")} />
            </div>
            <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider">Majątek Netto</h3>
          </div>
          <div className="relative z-10">
            <p className={cn("text-4xl font-extrabold tracking-tight", data.net_worth >= 0 ? "text-green-700" : "text-red-700")}>
              {data.net_worth.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <span className="text-xl font-normal text-gray-500">PLN</span>
            </p>
            <p className="text-xs text-gray-400 mt-1">Aktywa - Zobowiązania</p>
          </div>
        </div>
      </div>

      {/* Middle Row: Visualization & Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-6">Struktura Aktywów</h3>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={80}
                  outerRadius={110}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(value: number) => `${value.toLocaleString('pl-PL', { minimumFractionDigits: 2 })} PLN`}
                  contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                />
                <Legend verticalAlign="bottom" height={36} iconType="circle"/>
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Quick Stats Panel */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col justify-center space-y-8">
           <div>
              <h4 className="text-sm font-medium text-gray-500 uppercase mb-2">Dostępne Środki (Budżet)</h4>
              <div className="flex items-baseline space-x-2">
                <span className="text-2xl font-bold text-gray-900">{data.quick_stats.free_pool.toLocaleString('pl-PL', { minimumFractionDigits: 2 })}</span>
                <span className="text-sm text-gray-500">PLN</span>
              </div>
           </div>

           <div className="border-t border-gray-100 pt-6">
              <h4 className="text-sm font-medium text-gray-500 uppercase mb-2">Najbliższa Rata (Kredyt)</h4>
              {data.quick_stats.next_loan_installment > 0 ? (
                <div>
                   <div className="flex items-baseline space-x-2">
                    <span className="text-2xl font-bold text-red-600">{data.quick_stats.next_loan_installment.toLocaleString('pl-PL', { minimumFractionDigits: 2 })}</span>
                    <span className="text-sm text-gray-500">PLN</span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    Termin: {data.quick_stats.next_loan_date ? new Date(data.quick_stats.next_loan_date).toLocaleDateString('pl-PL') : 'Nieznany'}
                  </p>
                </div>
              ) : (
                <p className="text-green-600 font-medium">Brak nadchodzących rat</p>
              )}
           </div>
        </div>
      </div>

      {/* Bottom Row: Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Portfolios */}
        <Link to="/portfolios" className="group bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-lg hover:border-blue-100 transition-all duration-200">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-blue-50 text-blue-600 rounded-xl group-hover:bg-blue-100 transition-colors">
              <Briefcase className="h-8 w-8" />
            </div>
            <ArrowRight className="h-5 w-5 text-gray-300 group-hover:text-blue-500 transform group-hover:translate-x-1 transition-all" />
          </div>
          <h3 className="text-xl font-bold text-gray-900 group-hover:text-blue-600 transition-colors">Zarządzaj Portfelami</h3>
          <p className="mt-2 text-sm text-gray-500">Akcje, Obligacje, IKE/IKZE</p>
        </Link>

        {/* Loans */}
        <Link to="/loans" className="group bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-lg hover:border-amber-100 transition-all duration-200">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-amber-50 text-amber-600 rounded-xl group-hover:bg-amber-100 transition-colors">
              <Landmark className="h-8 w-8" />
            </div>
            <ArrowRight className="h-5 w-5 text-gray-300 group-hover:text-amber-500 transform group-hover:translate-x-1 transition-all" />
          </div>
          <h3 className="text-xl font-bold text-gray-900 group-hover:text-amber-600 transition-colors">Zarządzaj Kredytami</h3>
          <p className="mt-2 text-sm text-gray-500">Hipoteki, Gotówkowe, Nadpłaty</p>
        </Link>

        {/* Budget */}
        <Link to="/budget" className="group bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-lg hover:border-indigo-100 transition-all duration-200">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl group-hover:bg-indigo-100 transition-colors">
              <PiggyBank className="h-8 w-8" />
            </div>
            <ArrowRight className="h-5 w-5 text-gray-300 group-hover:text-indigo-500 transform group-hover:translate-x-1 transition-all" />
          </div>
          <h3 className="text-xl font-bold text-gray-900 group-hover:text-indigo-600 transition-colors">Zarządzaj Budżetem</h3>
          <p className="mt-2 text-sm text-gray-500">Konta, Koperty, Wydatki</p>
        </Link>

      </div>
    </div>
  );
};

export default MainDashboard;
