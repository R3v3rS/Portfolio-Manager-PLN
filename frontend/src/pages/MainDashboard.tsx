import React, { useEffect, useState } from 'react';
import {
  dashboardApi,
  EMPTY_GLOBAL_SUMMARY,
  type CurrentMonthDividends,
  type GlobalSummary,
} from '../api_dashboard';
import { portfolioApi } from '../api';
import { extractErrorMessageFromUnknown } from '../http/response';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Link } from 'react-router-dom';
import { TrendingUp, CreditCard, ArrowRight, Briefcase, Landmark, PiggyBank } from 'lucide-react';
import { cn } from '../lib/utils';
import Card from '../components/ui/Card';
import type { Holding } from '../types';

const MainDashboard: React.FC = () => {
  const [data, setData] = useState<GlobalSummary>(EMPTY_GLOBAL_SUMMARY);
  const [dividendsData, setDividendsData] = useState<CurrentMonthDividends | null>(null);
  const [allHoldings, setAllHoldings] = useState<Holding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [summary, allPortfolios, dividends] = await Promise.all([
          dashboardApi.getGlobalSummary(),
          portfolioApi.list(),
          dashboardApi.getCurrentMonthDividends().catch(() => null),
        ]);
        const holdingsPerPortfolio = await Promise.all(
          allPortfolios.portfolios
            .filter(p => ['STANDARD', 'IKE'].includes(p.account_type))
            .map(p => portfolioApi.getHoldings(p.id))
        );
        const flattenedHoldings = holdingsPerPortfolio
          .flat()
          .filter(h => h.quantity >= 0.000001 && (h.current_value ?? 0) >= 1);
        setData(summary);
        setDividendsData(dividends);
        setAllHoldings(flattenedHoldings);
        setError(null);
      } catch (err) {
        console.error(err);
        setError(extractErrorMessageFromUnknown(err));
        setData(EMPTY_GLOBAL_SUMMARY);
        setDividendsData(null);
        setAllHoldings([]);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div className="space-y-6 p-4"><div className="h-8 w-56 animate-pulse rounded bg-gray-200" /><div className="grid grid-cols-1 gap-6 md:grid-cols-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-40 animate-pulse rounded-2xl bg-gray-200" />)}</div></div>;
  if (error) return <div className="p-12 text-center text-red-600">{error}</div>;

  const chartData = [
    { name: 'Gotówka (Budżet)', value: data.assets_breakdown.budget_cash, color: '#10B981' }, // emerald-500
    { name: 'Gotówka (Inw.)', value: data.assets_breakdown.invest_cash, color: '#14B8A6' }, // teal-500
    { name: 'Konta Oszcz.', value: data.assets_breakdown.savings, color: '#6366F1' }, // indigo-500
    { name: 'Obligacje', value: data.assets_breakdown.bonds, color: '#F59E0B' }, // amber-500
    { name: 'Akcje / ETF', value: data.assets_breakdown.stocks, color: '#3B82F6' }, // blue-500
    { name: 'PPK', value: data.assets_breakdown.ppk, color: '#A855F7' }, // purple-500
  ].filter(item => item.value > 0);

  const netWorthShortTermOnly = data.total_assets - data.liabilities_breakdown.short_term;
  const netWorthAllLiabilities = data.total_assets - (data.liabilities_breakdown.short_term + data.liabilities_breakdown.long_term);
  const holdingsWithDailyChange = allHoldings.filter((h) => h.change_1d_percent !== undefined && h.change_1d_percent !== 0);
  const hasDailyChangeData = holdingsWithDailyChange.length > 0;
  const topGainers = [...holdingsWithDailyChange]
    .sort((a, b) => (b.change_1d_percent ?? 0) - (a.change_1d_percent ?? 0))
    .slice(0, 3);
  const topLosers = [...holdingsWithDailyChange]
    .sort((a, b) => (a.change_1d_percent ?? 0) - (b.change_1d_percent ?? 0))
    .slice(0, 3);
  const hasNoDividendsThisMonth = dividendsData !== null
    && dividendsData.received_this_month === 0
    && dividendsData.expected_this_month === 0;
  const totalDividendTarget = (dividendsData?.received_this_month ?? 0) + (dividendsData?.expected_this_month ?? 0);
  const dividendProgress = totalDividendTarget > 0
    ? Math.min(100, ((dividendsData?.received_this_month ?? 0) / totalDividendTarget) * 100)
    : 0;

  const renderMovers = (holdings: Holding[], colorClass: 'text-green-600' | 'text-red-600', icon: string) => {
    return holdings.map((holding) => (
      <div key={`${holding.portfolio_id}-${holding.ticker}`} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-xl border border-gray-100 bg-gray-50/70 px-3 py-2">
        <div className="text-xs">{icon}</div>
        <div className="min-w-0">
          <div className="font-mono font-bold text-gray-900 truncate">{holding.ticker}</div>
          <div className={cn('text-sm font-semibold', colorClass)}>
            {(holding.change_1d_percent ?? 0) > 0 ? '+' : ''}
            {(holding.change_1d_percent ?? 0).toFixed(2)}%
          </div>
        </div>
        <div className="text-sm text-gray-500 text-right">
          {(holding.current_value ?? 0).toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN
        </div>
      </div>
    ));
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      
      {/* Header */}
      <div className="mb-8 rounded-3xl border border-blue-100/70 bg-gradient-to-r from-white to-blue-50/70 p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-600">Portfolio Command Center</p>
        <h1 className="mt-1 text-3xl font-bold text-gray-900">Pulpit Dowódcy</h1>
        <p className="mt-1 text-sm text-gray-500">Globalny przegląd Twojego majątku</p>
      </div>

      {/* Top Row: Big Numbers */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Assets */}
        <Card variant="default" className="p-6 flex flex-col justify-between hover:shadow-md transition-shadow bg-gradient-to-b from-white to-green-50/40">
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
        </Card>

        {/* Liabilities */}
        <Card variant="default" className="p-6 flex flex-col justify-between hover:shadow-md transition-shadow bg-gradient-to-b from-white to-red-50/30">
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
        </Card>

        {/* Net Worth - The Main Card */}
        <div className={cn(
          "bg-white rounded-2xl shadow-lg border-2 p-6 flex flex-col justify-between transform hover:-translate-y-1 transition-all duration-200 relative overflow-hidden bg-gradient-to-b",
          netWorthShortTermOnly >= 0 ? "border-green-100 ring-4 ring-green-50/50" : "border-red-100 ring-4 ring-red-50/50"
        )}>
          <div className={cn("absolute top-0 right-0 w-32 h-32 rounded-full -mr-16 -mt-16 opacity-10", netWorthShortTermOnly >= 0 ? "bg-green-500" : "bg-red-500")}></div>
          
          <div className="flex items-center space-x-3 mb-2 relative z-10">
            <div className={cn("p-2 rounded-lg", netWorthShortTermOnly >= 0 ? "bg-green-100" : "bg-red-100")}>
              <Landmark className={cn("h-6 w-6", netWorthShortTermOnly >= 0 ? "text-green-700" : "text-red-700")} />
            </div>
            <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider">Majątek Netto (krótkoterminowe)</h3>
          </div>
          <div className="relative z-10">
            <p className={cn("text-4xl font-extrabold tracking-tight", netWorthShortTermOnly >= 0 ? "text-green-700" : "text-red-700")}>
              {netWorthShortTermOnly.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <span className="text-xl font-normal text-gray-500">PLN</span>
            </p>
            <p className="text-xs text-gray-400 mt-1">Aktywa - zobowiązania krótkoterminowe</p>
            <p className="text-xs text-gray-500 mt-2">
              Z krótkoterminowymi + długoterminowymi: {' '}
              <span className="font-semibold text-gray-700">
                {netWorthAllLiabilities.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* Middle Row: Visualization & Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <Card variant="default" className="lg:col-span-2 p-6">
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
        </Card>

        {/* Quick Stats Panel */}
        <Card variant="default" className="p-6 flex flex-col justify-center space-y-8">
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

           {dividendsData && (
             <div className="border-t border-gray-100 pt-6">
                <h4 className="text-sm font-medium text-gray-500 uppercase mb-2">Dywidendy — {dividendsData.month_label}</h4>
                {hasNoDividendsThisMonth ? (
                  <p className="text-sm text-gray-500">Brak dywidend w tym miesiącu</p>
                ) : (
                  <div className="space-y-3">
                    <p className="text-green-600 font-semibold">
                      Otrzymane: {dividendsData.received_this_month.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN
                    </p>
                    {dividendsData.expected_this_month > 0 && (
                      <p className="text-gray-500">
                        Oczekiwane: {dividendsData.expected_this_month.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN
                      </p>
                    )}
                    <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div className="h-full bg-green-500 transition-all" style={{ width: `${dividendProgress}%` }} />
                    </div>
                    {dividendsData.top_payers.length > 0 && (
                      <div className="space-y-1">
                        {dividendsData.top_payers.slice(0, 3).map((payer) => (
                          <div key={`${payer.ticker}-${payer.date}`} className="text-sm text-gray-700">
                            💰 {payer.ticker} {payer.amount.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} PLN{' '}
                            {payer.date ? new Date(payer.date).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }) : ''}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
             </div>
           )}
        </Card>
      </div>

      <Card variant="default" className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Dzisiejsze ruchy</h3>
        {hasDailyChangeData ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Top 3 Gainers</h4>
              <div className="space-y-1">{renderMovers(topGainers, 'text-green-600', '🟢')}</div>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Top 3 Losers</h4>
              <div className="space-y-1">{renderMovers(topLosers, 'text-red-600', '🔴')}</div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">Brak danych zmian dziennych</p>
        )}
      </Card>

      {/* Bottom Row: Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Portfolios */}
        <Link to="/portfolios" className="group p-6 hover:border-blue-200 transition-all duration-200 bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-lg hover:-translate-y-0.5">
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
        <Link to="/loans" className="group p-6 hover:border-amber-200 transition-all duration-200 bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-lg hover:-translate-y-0.5">
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
        <Link to="/budget" className="group bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-lg hover:border-indigo-200 transition-all duration-200 hover:-translate-y-0.5">
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
