import React, { useEffect, useState } from 'react';
import {
  dashboardApi,
  EMPTY_GLOBAL_SUMMARY,
  type CurrentMonthDividends,
  type GlobalSummary,
} from '../api_dashboard';
import { portfolioApi } from '../api';
import { extractErrorMessageFromUnknown } from '../http/response';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid } from 'recharts';
import { TrendingUp, CreditCard, Landmark } from 'lucide-react';
import { cn } from '../lib/utils';
import { Card, SectionHeader, Sidebar } from '../components/dashboard/DashboardPrimitives';
import { StatCard } from '../components/dashboard/StatCard';
import { ChartCard } from '../components/dashboard/ChartCard';
import { DataTable } from '../components/dashboard/DataTable';
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

  if (loading) return <div className="p-12 text-center text-gray-500">Ładowanie kokpitu...</div>;
  if (error) return <div className="p-12 text-center text-red-600">{error}</div>;

  const chartData = [
    { name: 'Gotówka (Budżet)', value: data.assets_breakdown.budget_cash, color: '#10B981' }, // emerald-500
    { name: 'Gotówka (Inw.)', value: data.assets_breakdown.invest_cash, color: '#14B8A6' }, // teal-500
    { name: 'Konta Oszcz.', value: data.assets_breakdown.savings, color: '#6366F1' }, // indigo-500
    { name: 'Obligacje', value: data.assets_breakdown.bonds, color: '#F59E0B' }, // amber-500
    { name: 'Akcje / ETF', value: data.assets_breakdown.stocks, color: '#3B82F6' }, // blue-500
    { name: 'PPK', value: data.assets_breakdown.ppk, color: '#A855F7' }, // purple-500
  ].filter(item => item.value > 0);
  const timelineData = [
    { name: 'Sty', portfolio: 320, deposits: 300 },
    { name: 'Lut', portfolio: 360, deposits: 320 },
    { name: 'Mar', portfolio: 410, deposits: 350 },
    { name: 'Kwi', portfolio: 470, deposits: 390 },
    { name: 'Maj', portfolio: 520, deposits: 430 },
    { name: 'Cze', portfolio: 560, deposits: 460 },
  ];

  const DarkTooltip = ({ active, payload, label }: { active?: boolean; payload?: { value: number; name: string }[]; label?: string }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="rounded-xl border border-white/10 bg-[#0b1220]/95 px-3 py-2 text-xs shadow-xl">
        <p className="mb-1 text-slate-300">{label}</p>
        {payload.map((item) => <p key={item.name} className="text-slate-100">{item.name}: {item.value.toFixed(2)} PLN</p>)}
      </div>
    );
  };

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
      <div key={`${holding.portfolio_id}-${holding.ticker}`} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 py-2">
        <div>{icon}</div>
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
    <div className="min-h-screen bg-[#0B0F14] text-slate-100">
      <div className="mx-auto flex max-w-[1700px]">
        <Sidebar items={['Pulpit', 'Inwestycje', 'Analiza', 'Analytics', 'Historia', 'AI']} />
        <main className="w-full p-4 md:p-6 lg:p-8">
          <div className="mb-6 flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
            <div>
              <h1 className="text-2xl font-semibold">IKE</h1>
              <p className="text-xs text-slate-400">Nowoczesny panel inwestycyjny</p>
            </div>
            <div className="flex gap-2">
              {['Transfer', 'Nowa Operacja', 'Odśwież ceny'].map((label, i) => <button key={label} className={`h-10 rounded-xl px-4 text-sm font-medium transition-all duration-200 ease-in-out active:scale-95 ${i===0?'bg-gradient-to-r from-emerald-500/25 to-emerald-400/15 text-emerald-200 hover:shadow-[0_0_18px_rgba(34,197,94,0.25)]':'bg-gradient-to-r from-indigo-500/25 to-violet-500/20 text-indigo-100 hover:shadow-[0_0_18px_rgba(99,102,241,0.25)]'} ring-1 ring-white/10 hover:-translate-y-0.5`}>{label}</button>)}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Wartość całkowita" value={`${data.total_assets.toFixed(2)} PLN`} />
            <StatCard label="Gotówka" value={`${(data.assets_breakdown.budget_cash + data.assets_breakdown.invest_cash).toFixed(2)} PLN`} />
            <StatCard label="Zysk / Strata" value={`${netWorthShortTermOnly.toFixed(2)} PLN`} tone={netWorthShortTermOnly >= 0 ? 'profit' : 'loss'} />
            <StatCard label="Dywidendy" value={`${(dividendsData?.received_this_month ?? 0).toFixed(2)} PLN`} tone="profit" />
            <StatCard label="Otwarte pozycje" value={`${allHoldings.length}`} />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
            <ChartCard title="Wartość portfela">
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={timelineData}>
                    <defs>
                      <linearGradient id="gradientGreen" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#22c55e" stopOpacity="0.35" />
                        <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
                      </linearGradient>
                      <linearGradient id="gradientBlue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.30" />
                        <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(148,163,184,0.14)" vertical={false} />
                    <XAxis dataKey="name" stroke="#64748b" tickLine={false} axisLine={false} />
                    <YAxis stroke="#64748b" tickLine={false} axisLine={false} />
                    <Tooltip content={<DarkTooltip />} />
                    <Area type="monotone" dataKey="portfolio" stroke="#22c55e" fill="url(#gradientGreen)" strokeWidth={2.6} dot={{ r: 0 }} activeDot={{ r: 4, stroke: '#86efac', strokeWidth: 2 }} />
                    <Area type="monotone" dataKey="deposits" stroke="#3b82f6" fill="url(#gradientBlue)" strokeWidth={2.2} dot={{ r: 0 }} activeDot={{ r: 4, stroke: '#93c5fd', strokeWidth: 2 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </ChartCard>
            <ChartCard title="Zysk / Strata">
              <Card className="border-none bg-transparent p-0 shadow-none">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-slate-400">Bieżący zysk</p><p className="mt-2 text-2xl font-semibold text-emerald-400">{netWorthShortTermOnly.toFixed(2)} PLN</p></div>
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><p className="text-slate-400">Dywidendy</p><p className="mt-2 text-2xl font-semibold text-indigo-300">{(dividendsData?.received_this_month ?? 0).toFixed(2)} PLN</p></div>
                </div>
              </Card>
            </ChartCard>
          </div>

          <div className="mt-6">
            <SectionHeader title="Aktywne pozycje" subtitle="Dark rows, badges, kolorowane PnL" />
            <DataTable holdings={allHoldings} />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card><SectionHeader title="Ekspozycja sektorowa" subtitle="Top sektory" /><div className="h-52"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={chartData.slice(0,4)} innerRadius={48} outerRadius={80} dataKey="value">{chartData.slice(0,4).map((e,i)=><Cell key={i} fill={e.color} />)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div></Card>
            <Card><SectionHeader title="Ekspozycja krajowa" subtitle="Top kraje" /><div className="space-y-3 text-sm text-slate-300"><div className="flex justify-between"><span>USA</span><span>60%</span></div><div className="flex justify-between"><span>Polska</span><span>25%</span></div><div className="flex justify-between"><span>UE</span><span>15%</span></div></div></Card>
            <Card><SectionHeader title="Nadchodzące dywidendy" /><div className="space-y-2 text-sm">{(dividendsData?.top_payers ?? []).slice(0,4).map((payer)=><div key={`${payer.ticker}-${payer.date}`} className="flex items-center justify-between rounded-lg bg-slate-900/70 px-3 py-2"><span>{payer.ticker}</span><span className="text-emerald-300">{payer.amount.toFixed(2)} PLN</span></div>)}</div></Card>
          </div>
        </main>
      </div>
    </div>
  );};

export default MainDashboard;
