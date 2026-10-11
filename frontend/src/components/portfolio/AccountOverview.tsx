import type { Portfolio, PortfolioValue } from '../../types';
import type { PPKSummary, PPKTransaction } from '../../services/ppkCalculator';
import { RefreshCw } from 'lucide-react';

const money = (value: number | undefined | null) => value == null ? '—' : new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(value);
const number = (value: number, digits = 2) => value.toLocaleString('pl-PL', { minimumFractionDigits: digits, maximumFractionDigits: digits });
function Metric({ label, value, help }: { label: string; value: string; help: string }) {
  return <article className="rounded-2xl border border-slate-700 bg-slate-900 p-5"><p className="text-sm text-slate-400">{label}</p><p className="mt-2 text-2xl font-bold tabular-nums text-slate-100">{value}</p><p className="mt-2 text-xs leading-5 text-slate-400">{help}</p></article>;
}
export default function AccountOverview({ portfolio, value, summary, transactions, price, onRefresh, refreshing, refreshWarning }: {
  portfolio: Portfolio; value: PortfolioValue & { live_interest?: number }; summary: PPKSummary | null;
  transactions: PPKTransaction[]; price: { price: number; date: string; source?: string } | null;
  onRefresh?: () => void; refreshing?: boolean; refreshWarning?: string | null;
}) {
  if (portfolio.account_type === 'SAVINGS') return <section className="space-y-4" aria-label="Podsumowanie oszczędności">
    <div className="app-hero rounded-2xl p-6"><p className="page-eyebrow">Pieniądze na koncie</p><h2 className="mt-2 text-4xl font-bold tabular-nums text-white">{money(value.cash_value - (value.live_interest ?? 0))}</h2><p className="mt-3 text-sm text-slate-300">Saldo zapisane w aplikacji. Niezaksięgowane odsetki pokazujemy osobno.</p></div>
    <div className="grid gap-4 sm:grid-cols-3">
      <Metric label="Zapisane odsetki" value={money(value.total_interest ?? 0)} help="Suma odsetek z historii tego konta."/>
      <Metric label="Odsetki od ostatniego rozliczenia" value={money(value.live_interest ?? 0)} help="Szacunek według obecnego salda i stopy. Nie jest potwierdzeniem naliczenia przez bank."/>
      <Metric label="Oprocentowanie roczne" value={`${number(portfolio.savings_rate ?? 0)}%`} help={`Wycena z szacowanymi odsetkami: ${money(value.portfolio_value)}.`}/>
    </div>
  </section>;
  const employee = transactions.reduce((sum,t) => sum+t.employee_units*t.price_per_unit,0);
  const employer = transactions.reduce((sum,t) => sum+t.employer_units*t.price_per_unit,0);
  const stale = price && Date.now()-new Date(price.date+'T12:00:00').getTime()>7*86400000;
  const gain = summary?.totalProfit;
  const percent = summary && summary.totalPurchaseValue>0 ? summary.totalProfit/summary.totalPurchaseValue*100 : null;
  return <section className="space-y-4" aria-label="Podsumowanie PPK">
    <div className="app-hero rounded-2xl p-6"><div className="flex flex-wrap items-center justify-between gap-3"><p className="page-eyebrow">Wartość jednostek funduszu</p>{onRefresh && <button className="pr-button" onClick={onRefresh} disabled={refreshing}><RefreshCw size={15} className={refreshing ? 'animate-spin' : ''}/>{refreshing ? 'Sprawdzanie wyceny…' : 'Odśwież wycenę PPK'}</button>}</div><h2 className="mt-2 text-4xl font-bold tabular-nums text-white">{price ? money(summary?.totalCurrentValue) : 'Brak wyceny'}</h2><p className="mt-3 text-sm text-slate-300">Brutto, przed potrąceniami przy zwrocie. Cena jednostki: {money(price?.price)} · {price ? new Date(price.date+'T12:00:00').toLocaleDateString('pl-PL') : 'brak zapisanej ceny'}.</p><p className="mt-2 text-xs text-slate-400">{price?.source ? `Źródło: ${price.source}. ` : ''}Cena dotyczy ostatniej opublikowanej wyceny, a nie kursu na żywo. Sprawdzamy ją automatycznie co 12 godzin po otwarciu inwestycji.</p></div>
    {refreshWarning && <p role="status" className="rounded-xl border border-amber-700 bg-amber-950/30 p-4 text-sm text-amber-200">{refreshWarning}</p>}
    {(!price || stale) && <p className="rounded-xl border border-amber-700 bg-amber-950/30 p-4 text-sm text-amber-200" role="status">{price ? 'Cena jest starsza niż 7 dni. Wartości i wynik poniżej są orientacyjne.' : 'Bez ceny jednostki nie można obliczyć aktualnego wyniku funduszu.'}</p>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Metric label="Twoje wpłaty" value={money(employee)} help="Kapitał pracownika według zapisanych wpłat."/>
      <Metric label="Wpłaty pracodawcy" value={money(employer)} help="Dodatkowy kapitał; nie jest wynikiem funduszu. Dopłaty państwa nie są osobno ewidencjonowane."/>
      <Metric label="Wynik funduszu brutto" value={price ? money(gain) : '—'} help={price && percent!=null ? `${number(percent)}% względem wszystkich wpłat. Wzrost wartości jednostek, bez wpłat.` : 'Wymaga wpłat i aktualnej ceny jednostki.'}/>
      <Metric label="Szacunkowa kwota zwrotu" value={price ? money(summary?.totalNetValue) : '—'} help="Zwrot przed 60. rokiem życia: 30% obecnej wartości części pracodawcy do ZUS oraz podatek od wypłacanego zysku. Dopłaty państwa nie są ewidencjonowane."/>
    </div>
    {price && <p className="text-sm text-slate-400">Do ZUS: {money(summary?.employerToZUS)} · Podatek przy zwrocie: {money(summary?.withdrawalTax)}. Wynik funduszu pokazujemy przed tymi potrąceniami.</p>}
    <p className="text-sm text-slate-400">Jednostki: {number(summary?.totalUnits ?? 0,4)} · Średnia cena nabycia: {money(summary?.averagePrice)} · Wszystkie wpłaty: {money(summary?.totalPurchaseValue)}.</p>
  </section>;
}
