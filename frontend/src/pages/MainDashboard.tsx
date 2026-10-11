import WealthHistory from '../components/charts/WealthHistory';
import GoalsSummary from '../components/goals/GoalsSummary';
import DashboardActions from '../components/dashboard/DashboardActions';
import React, { useEffect, useMemo, useState } from 'react';
import {
  dashboardApi,
  EMPTY_GLOBAL_SUMMARY,
  type CurrentMonthDividends,
  type GlobalSummary,
} from '../api_dashboard';
import { portfolioApi } from '../api';
import { extractErrorMessageFromUnknown } from '../http/response';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Link } from 'react-router-dom';
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BriefcaseBusiness,
  CalendarDays,
  ChevronRight,
  CircleDollarSign,
  Landmark,
  Layers3,
  PiggyBank,
  Sparkles,
  WalletCards,
} from 'lucide-react';
import { cn } from '../lib/utils';
import Card from '../components/ui/Card';
import type { Holding } from '../types';

const moneyFormatter = new Intl.NumberFormat('pl-PL', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const formatMoney = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? '—' : `${moneyFormatter.format(value)} PLN`;
const headlineMoney = (value: number | null | undefined) => formatMoney(value).replace(' PLN', ' zł');
const formatPercent = (value: number) => `${value.toLocaleString('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;

const FinancialOverview: React.FC = () => {
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
          portfolioApi.list().catch(() => ({ portfolios: [] })),
          dashboardApi.getCurrentMonthDividends().catch(() => null),
        ]);
        const holdingsPerPortfolio = await Promise.all(
          allPortfolios.portfolios
            .filter((portfolio) => ['STANDARD', 'IKE'].includes(portfolio.account_type))
            .map((portfolio) => portfolioApi.getHoldings(portfolio.id).catch(() => [])),
        );
        setData(summary);
        setDividendsData(dividends);
        setAllHoldings(
          holdingsPerPortfolio
            .flat()
            .filter((holding) => holding.quantity >= 0.000001 && (holding.current_value ?? 0) >= 1),
        );
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

  const allocation = useMemo(() => [
    { name: 'Akcje i ETF-y', shortName: 'Akcje / ETF', value: data.assets_breakdown.stocks, color: '#3B82F6' },
    { name: 'PPK', shortName: 'PPK', value: data.assets_breakdown.ppk, color: '#A855F7' },
    { name: 'Konta oszczędnościowe', shortName: 'Oszczędności', value: data.assets_breakdown.savings, color: '#6366F1' },
    { name: 'Obligacje', shortName: 'Obligacje', value: data.assets_breakdown.bonds, color: '#F59E0B' },
    { name: 'Gotówka inwestycyjna', shortName: 'Gotówka inwest.', value: data.assets_breakdown.invest_cash, color: '#14B8A6' },
    { name: 'Gotówka budżetowa', shortName: 'Gotówka budżet.', value: data.assets_breakdown.budget_cash, color: '#10B981' },
  ].filter((item) => item.value > 0), [data.assets_breakdown]);

  if (loading) {
    return (
      <div className="page-stack">
        <div className="h-10 w-72 animate-pulse rounded-xl bg-gray-200 dark:bg-gray-800" />
        <div className="h-72 animate-pulse rounded-[2rem] bg-gray-200 dark:bg-gray-800" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-36 animate-pulse rounded-2xl bg-gray-200 dark:bg-gray-800" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="mx-auto max-w-xl p-10 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-300">
          <Activity className="h-6 w-6" />
        </div>
        <h1 className="text-xl font-bold text-gray-950 dark:text-white">Nie udało się załadować pulpitu</h1>
        <p className="mt-2 text-sm text-red-600 dark:text-red-300">{error}</p>
      </Card>
    );
  }

  const totalLiabilities = data.liabilities_breakdown.short_term + data.liabilities_breakdown.long_term;
  const netWorth = data.total_assets == null ? null : data.total_assets - totalLiabilities;
  const liquidAssets = data.assets_breakdown.budget_cash + data.assets_breakdown.invest_cash + data.assets_breakdown.savings;
  const allShortTermLiabilities = data.all_short_term_liabilities ?? data.liabilities_breakdown.short_term;
  const shortTermCoverage = allShortTermLiabilities > 0
    ? liquidAssets / allShortTermLiabilities
    : null;
  const largestAllocation = allocation.reduce<(typeof allocation)[number] | null>(
    (largest, item) => (!largest || item.value > largest.value ? item : largest),
    null,
  );

  const holdingsWithDailyChange = allHoldings.filter(
    (holding) => holding.change_1d_percent !== undefined && holding.change_1d_percent !== 0,
  );
  const hasDailyChangeData = holdingsWithDailyChange.length > 0;
  const trackedDailyValue = holdingsWithDailyChange.reduce((sum, holding) => sum + (holding.current_value ?? 0), 0);
  const estimatedDailyPnl = holdingsWithDailyChange.reduce(
    (sum, holding) => sum + ((holding.current_value ?? 0) * (holding.change_1d_percent ?? 0)) / 100,
    0,
  );
  const estimatedDailyPercent = trackedDailyValue > 0 ? (estimatedDailyPnl / trackedDailyValue) * 100 : 0;
  const topGainers = [...holdingsWithDailyChange]
    .filter((holding) => (holding.change_1d_percent ?? 0) > 0)
    .sort((a, b) => (b.change_1d_percent ?? 0) - (a.change_1d_percent ?? 0))
    .slice(0, 3);
  const topLosers = [...holdingsWithDailyChange]
    .filter((holding) => (holding.change_1d_percent ?? 0) < 0)
    .sort((a, b) => (a.change_1d_percent ?? 0) - (b.change_1d_percent ?? 0))
    .slice(0, 3);
  const hasNoDividendsThisMonth = dividendsData !== null
    && dividendsData.received_this_month === 0
    && dividendsData.expected_this_month === 0;
  const totalDividendTarget = (dividendsData?.received_this_month ?? 0) + (dividendsData?.expected_this_month ?? 0);
  const dividendProgress = totalDividendTarget > 0
    ? Math.min(100, ((dividendsData?.received_this_month ?? 0) / totalDividendTarget) * 100)
    : 0;

  const renderMovers = (holdings: Holding[], direction: 'up' | 'down') => {
    if (holdings.length === 0) {
      return <p className="rounded-xl border border-dashed border-gray-200 px-4 py-5 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">Brak pozycji w tej grupie</p>;
    }
    return holdings.map((holding) => {
      const change = holding.change_1d_percent ?? 0;
      const isUp = direction === 'up';
      return (
        <div key={`${holding.portfolio_id}-${holding.ticker}`} className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/70">
          <div className="flex min-w-0 items-center gap-3">
            <div className={cn(
              'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl',
              isUp ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300' : 'bg-rose-50 text-rose-600 dark:bg-rose-950/40 dark:text-rose-300',
            )}>
              {isUp ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
            </div>
            <div className="min-w-0">
              <p className="truncate font-mono text-sm font-bold text-gray-950 dark:text-white">{holding.ticker}</p>
              <p className="truncate text-xs text-gray-500 dark:text-gray-400">{formatMoney(holding.current_value)}</p>
            </div>
          </div>
          <span className={cn('rounded-lg px-2 py-1 text-sm font-bold tabular-nums', isUp ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300' : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300')}>
            {change > 0 ? '+' : ''}{change.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%
          </span>
        </div>
      );
    });
  };

  const navigationCards = [
    { to: '/portfolios', title: 'Zarządzaj Portfelami', description: 'Akcje, ETF-y, obligacje i IKE', icon: BriefcaseBusiness, accent: 'blue' },
    { to: '/budget', title: 'Budżet i oszczędności', description: 'Konta, koperty i wolne środki', icon: PiggyBank, accent: 'violet' },
    { to: '/loans', title: 'Kredyty i zobowiązania', description: 'Raty, nadpłaty i harmonogramy', icon: Landmark, accent: 'amber' },
  ] as const;

  return (
    <div className="page-stack">
      <section className="app-hero rounded-2xl p-5 md:p-6" aria-label="Najważniejsze kwoty">
        <div className="grid gap-6 lg:grid-cols-[1fr_1.5fr] lg:items-center">
          <div><p className="text-sm font-semibold text-teal-200">Majątek netto</p>{data.valuation_status && data.valuation_status !== 'ok' && <p className="mt-2 text-xs text-amber-200">{data.valuation_status === 'incomplete' ? 'Niepełna wycena — brakuje notowań' : 'Wycena orientacyjna — część cen jest nieaktualna'}</p>}<p className={cn('mt-2 text-3xl font-bold tracking-tight tabular-nums',netWorth>=0 ? 'text-white' : 'text-rose-300')}>{headlineMoney(netWorth)}</p><p className="mt-3 text-xs leading-5 text-slate-300">Aktywa: {headlineMoney(data.total_assets)}<br/>Zobowiązania uwzględnione: {headlineMoney(totalLiabilities)}</p>{!!data.excluded_liabilities?.length && <p className="mt-2 text-xs text-amber-200">Pominięto kredyty: {data.excluded_liabilities.map(loan => loan.name).join(', ')} · {headlineMoney(data.excluded_liabilities.reduce((sum, loan) => sum + loan.estimated_balance, 0))}</p>}</div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-white/10 bg-white/5 p-4"><p className="text-xs text-slate-300">Do zaplanowania</p><p className="mt-2 text-lg font-bold tabular-nums text-white">{headlineMoney(data.quick_stats.free_pool)}</p><p className="mt-2 text-xs leading-5 text-slate-400">W tym oczekiwane wpływy: {headlineMoney(data.quick_stats.expected_income ?? 0)}</p></div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4"><p className="text-xs text-slate-300">Płynne środki</p><p className="mt-2 text-lg font-bold tabular-nums text-white">{headlineMoney(liquidAssets)}</p><p className="mt-2 text-xs leading-5 text-slate-400">Gotówka i oszczędności. Część może być już przypisana do planu.</p></div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4"><p className="text-xs text-slate-300">Najbliższa rata</p><p className="mt-2 text-lg font-bold tabular-nums text-white">{data.quick_stats.next_loan_installment>0 ? headlineMoney(data.quick_stats.next_loan_installment) : 'Brak rat'}</p><p className="mt-2 text-xs leading-5 text-slate-400">{data.quick_stats.next_loan_date ? new Date(data.quick_stats.next_loan_date+'T12:00:00').toLocaleDateString('pl-PL') : 'Brak nadchodzącego terminu'}</p></div>
          </div>
        </div>
      </section>

      <DashboardActions />
      {data.valuation_notes?.length ? <details className="dc-analysis"><summary>Założenia i aktualność wyceny ({data.valuation_notes.length})</summary><ul className="space-y-2 p-4 text-sm text-slate-300">{data.valuation_notes.map(note => <li key={note}>{note}</li>)}</ul></details> : null}

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[1.55fr_0.85fr]">
        <Card className="overflow-hidden p-0">
          <div className="flex flex-col gap-2 border-b border-gray-100 px-6 py-5 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between">
            <div><p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-600 dark:text-blue-300">Rozkład majątku</p><h2 className="mt-1 text-xl font-bold text-gray-950 dark:text-white">Struktura Aktywów</h2></div>
            {largestAllocation && <p className="text-sm text-gray-500 dark:text-gray-400">Największa część: <span className="font-semibold text-gray-900 dark:text-gray-200">{largestAllocation.shortName}</span></p>}
          </div>
          <div className="grid gap-4 p-5 md:grid-cols-[minmax(260px,0.9fr)_1.1fr] md:p-6">
            <div className="relative h-[280px] min-h-[280px] w-full min-w-0">
              {allocation.length > 0 ? <><ResponsiveContainer width="100%" height={280} minWidth={240}><PieChart><Pie data={allocation} cx="50%" cy="50%" innerRadius={82} outerRadius={112} paddingAngle={3} dataKey="value" stroke="none">{allocation.map((entry) => <Cell key={entry.name} fill={entry.color} />)}</Pie><Tooltip formatter={(value: number) => formatMoney(value)} contentStyle={{ borderRadius: '14px', border: '1px solid rgba(148, 163, 184, .25)', boxShadow: '0 12px 30px -12px rgba(15, 23, 42, .35)' }} /></PieChart></ResponsiveContainer><div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center"><span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Łącznie</span><span className="mt-1 max-w-32 text-xl font-extrabold text-gray-950 dark:text-white">{formatMoney(data.total_assets)}</span></div></> : <div className="flex h-full items-center justify-center text-sm text-gray-500">Brak aktywów do pokazania</div>}
            </div>
            <div className="flex flex-col justify-center space-y-4">
              {allocation.map((item) => {
                const share = data.total_assets > 0 ? (item.value / data.total_assets) * 100 : 0;
                return <div key={item.name}><div className="mb-1.5 flex items-center justify-between gap-4 text-sm"><div className="flex min-w-0 items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: item.color }} /><span className="truncate font-medium text-gray-700 dark:text-gray-200">{item.name}</span></div><div className="shrink-0 text-right"><span className="font-bold text-gray-950 dark:text-white">{formatPercent(share)}</span><span className="ml-2 hidden text-gray-500 dark:text-gray-400 sm:inline">{formatMoney(item.value)}</span></div></div><div className="h-1.5 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800"><div className="h-full rounded-full" style={{ width: `${Math.max(share, 1)}%`, backgroundColor: item.color }} /></div></div>;
              })}
            </div>
          </div>
        </Card>

        <Card className="overflow-hidden p-0">
          <div className="border-b border-gray-100 px-6 py-5 dark:border-gray-800"><p className="text-xs font-bold uppercase tracking-[0.16em] text-violet-600 dark:text-violet-300">Najbliższe sprawy</p><h2 className="mt-1 text-xl font-bold text-gray-950 dark:text-white">Na radarze</h2></div>
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            <div className="p-5"><div className="flex items-start gap-3"><div className="rounded-xl bg-blue-50 p-2.5 text-blue-600 dark:bg-blue-950/40 dark:text-blue-300"><WalletCards className="h-5 w-5" /></div><div className="min-w-0 flex-1"><p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Do zaplanowania (budżet)</p><p className="mt-1 text-xl font-bold text-gray-950 dark:text-white">{formatMoney(data.quick_stats.free_pool)}</p><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">W tym oczekiwane wpływy: {formatMoney(data.quick_stats.expected_income ?? 0)}</p></div></div></div>
            <div className="p-5"><div className="flex items-start gap-3"><div className="rounded-xl bg-amber-50 p-2.5 text-amber-600 dark:bg-amber-950/40 dark:text-amber-300"><CalendarDays className="h-5 w-5" /></div><div className="min-w-0 flex-1"><p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Najbliższa rata (kredyt)</p>{data.quick_stats.next_loan_installment > 0 ? <><p className="mt-1 text-xl font-bold text-gray-950 dark:text-white">{formatMoney(data.quick_stats.next_loan_installment)}</p><p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Termin: {data.quick_stats.next_loan_date ? new Date(data.quick_stats.next_loan_date).toLocaleDateString('pl-PL') : 'Nieznany'}</p></> : <p className="mt-2 text-sm font-semibold text-emerald-600 dark:text-emerald-300">Brak nadchodzących rat</p>}</div></div></div>
            {dividendsData && <div className="p-5"><div className="flex items-start gap-3"><div className="rounded-xl bg-emerald-50 p-2.5 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300"><CircleDollarSign className="h-5 w-5" /></div><div className="min-w-0 flex-1"><p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Dywidendy — {dividendsData.month_label}</p>{hasNoDividendsThisMonth ? <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">Brak dywidend w tym miesiącu</p> : <div className="mt-2 space-y-2"><p className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">Otrzymane: {formatMoney(dividendsData.received_this_month)}</p>{dividendsData.expected_this_month > 0 && <p className="text-xs text-gray-500 dark:text-gray-400">Oczekiwane: {formatMoney(dividendsData.expected_this_month)}</p>}<div className="h-1.5 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${dividendProgress}%` }} /></div>{dividendsData.top_payers.slice(0, 2).map((payer) => <p key={`${payer.ticker}-${payer.date}`} className="text-xs text-gray-600 dark:text-gray-300">💰 {payer.ticker} {formatMoney(payer.amount)} {payer.date ? `· ${new Date(payer.date).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })}` : ''}</p>)}</div>}</div></div></div>}
            <div className="p-5"><div className="flex items-start gap-3"><div className="rounded-xl bg-violet-50 p-2.5 text-violet-600 dark:bg-violet-950/40 dark:text-violet-300"><Sparkles className="h-5 w-5" /></div><div><p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Sygnał finansowy</p><p className="mt-1 text-sm leading-5 text-gray-700 dark:text-gray-200">{shortTermCoverage === null ? 'Brak zobowiązań krótkoterminowych — płynność wygląda bezpiecznie.' : shortTermCoverage >= 2 ? `Płynne środki pokrywają krótkoterminowe zobowiązania ${shortTermCoverage.toLocaleString('pl-PL', { maximumFractionDigits: 1 })}×.` : 'Płynne środki są niskie względem zobowiązań krótkoterminowych.'}</p></div></div></div>
          </div>
        </Card>
      </section>

      <Card className="overflow-hidden p-0">
        <div className="flex flex-col gap-2 border-b border-gray-100 px-6 py-5 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-emerald-600 dark:text-emerald-300">Zmiany na rynku</p><h2 className="mt-1 text-xl font-bold text-gray-950 dark:text-white">Dzisiejsze ruchy</h2></div>{hasDailyChangeData && <p className="text-sm text-gray-500 dark:text-gray-400">{holdingsWithDailyChange.length} pozycji · Szacunkowo {formatMoney(estimatedDailyPnl)} ({formatPercent(estimatedDailyPercent)})</p>}</div>
        {hasDailyChangeData ? <div className="grid gap-6 p-5 md:grid-cols-2 md:p-6"><div><div className="mb-2 flex items-center gap-2 px-3"><ArrowUpRight className="h-4 w-4 text-emerald-600" /><h3 className="text-sm font-bold text-gray-700 dark:text-gray-200">Najmocniejsze pozycje</h3></div><div className="space-y-1">{renderMovers(topGainers, 'up')}</div></div><div><div className="mb-2 flex items-center gap-2 px-3"><ArrowDownRight className="h-4 w-4 text-rose-600" /><h3 className="text-sm font-bold text-gray-700 dark:text-gray-200">Najsłabsze pozycje</h3></div><div className="space-y-1">{renderMovers(topLosers, 'down')}</div></div></div> : <p className="p-8 text-center text-sm text-gray-500 dark:text-gray-400">Brak danych zmian dziennych</p>}
      </Card>

      <section>
        <div className="mb-4 flex items-center gap-2"><Layers3 className="h-5 w-5 text-blue-600 dark:text-blue-300" /><h2 className="text-lg font-bold text-gray-950 dark:text-white">Przejdź do szczegółów</h2></div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {navigationCards.map((item) => {
            const Icon = item.icon;
            const colorClasses = { blue: 'bg-blue-50 text-blue-600 group-hover:bg-blue-600 group-hover:text-white dark:bg-blue-950/40 dark:text-blue-300', violet: 'bg-violet-50 text-violet-600 group-hover:bg-violet-600 group-hover:text-white dark:bg-violet-950/40 dark:text-violet-300', amber: 'bg-amber-50 text-amber-600 group-hover:bg-amber-600 group-hover:text-white dark:bg-amber-950/40 dark:text-amber-300' }[item.accent];
            return <Link key={item.to} to={item.to} className="group flex items-center gap-4 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-lg dark:border-gray-800 dark:bg-gray-900 dark:hover:border-blue-800"><div className={cn('flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl transition-colors', colorClasses)}><Icon className="h-6 w-6" /></div><div className="min-w-0 flex-1"><h3 className="font-bold text-gray-950 dark:text-white">{item.title}</h3><p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{item.description}</p></div><ChevronRight className="h-5 w-5 shrink-0 text-gray-300 transition-transform group-hover:translate-x-1 group-hover:text-blue-500" /></Link>;
          })}
        </div>
      </section>
      <GoalsSummary />
      <WealthHistory />
    </div>
  );
};

const MainDashboard: React.FC = () => {
  return <div className="page-stack">
    <header className="page-heading flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
      <p className="page-eyebrow">Twoje finanse</p>
      <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-950 dark:text-white">Centrum finansów</h1>
      <p className="dc-help">Wiesz, co wymaga uwagi. Wybierz sprawę i wykonaj następny krok.</p>
      </div>
      <Link className="dc-button" to="/reports/monthly"><CalendarDays size={16}/>Raport miesięczny</Link>
    </header>
    <FinancialOverview />
  </div>;
};

export default MainDashboard;
