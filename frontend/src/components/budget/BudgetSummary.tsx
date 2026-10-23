import { Link } from 'react-router-dom';
import { ArrowRight, Wallet } from 'lucide-react';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import type { CashForecast } from '../../api_forecast';
import { planningDay as day, planningMoney as money, planningToday } from './planningHelpers';
import './budgetSummary.css';

const amount = (value: number | undefined) => value === undefined ? '—' : money(value);
const round = (value: number) => Math.round(value * 100) / 100;

export default function BudgetSummary({ data, forecast, failed }: {
  data: BudgetWorkspace; forecast: CashForecast | null; failed: boolean;
}) {
  const totals = data.totals;
  const today = forecast?.as_of ?? planningToday();
  const future = data.month > today.slice(0, 7);
  const [year, month] = data.month.split('-').map(Number);
  const end = `${data.month}-${String(new Date(year, month, 0).getDate()).padStart(2, '0')}`;
  const previousEnd = new Date(year, month - 1, 0);
  const previousDate = `${previousEnd.getFullYear()}-${String(previousEnd.getMonth() + 1).padStart(2, '0')}-${String(previousEnd.getDate()).padStart(2, '0')}`;
  const closing = forecast?.points.find(point => point.date === end);
  const opening = future ? forecast?.points.find(point => point.date === previousDate) : undefined;
  const monthly = totals.monthly_income_to_plan;
  const availableNow = totals.available_now ?? totals.balance - (totals.reserved ?? 0);
  const reservedNow = round(totals.balance - availableNow);
  const bridge = opening && closing && monthly !== undefined ? {
    before: round(opening.available - (forecast?.opening.available ?? availableNow)),
    assumptions: round(closing.available - opening.available - monthly),
  } : undefined;
  const estimates = forecast?.month_plans?.find(plan => plan.month === data.month)?.categories
    .filter(category => category.source === 'ESTIMATE' && category.amount > 0) ?? [];
  const next = forecast?.before_income;
  const monthLabel = new Date(year, month - 1, 1).toLocaleDateString('pl-PL', { month: 'long', year: 'numeric' });
  const pending = data.fixed_costs?.pending ?? data.bills.filter(bill => bill.status !== 'PAID').reduce((sum, bill) => sum + bill.amount, 0);

  return <section className="budget-summary" aria-label="Podsumowanie pieniędzy">
    <div className="budget-summary-heading"><div><p className="page-eyebrow">{future ? 'Plan przyszłego miesiąca' : 'Wybrany miesiąc'}</p><h2>{monthLabel}</h2></div></div>
    <div className="budget-summary-cards">
      <article className={`budget-summary-card is-primary ${monthly !== undefined && monthly < 0 ? 'is-negative' : ''}`} aria-label="Wolne z przychodów miesiąca">
        <span className="budget-summary-label">{monthly !== undefined && monthly < 0 ? 'Brakuje w dochodach miesiąca' : 'Wolne z dochodów miesiąca'}</span>
        <strong className="budget-summary-amount">{amount(monthly === undefined ? undefined : Math.abs(monthly))}</strong>
        <small>{(totals.expected_income??0)>0?`Plan uwzględnia oczekiwane wpływy: ${money(totals.expected_income??0)}`:'Na podstawie zapisanych dochodów.'}</small>
        <details className="budget-card-calculation"><summary>Jak to policzono?</summary><p>{monthly !== undefined && monthly < 0 ? 'Plan wymaga pokrycia tej kwoty z wcześniejszych środków.' : 'Tyle zostaje z dochodów tego miesiąca po jego kosztach i planie.'}</p>
        <dl className="budget-summary-breakdown"><div><dt>Dochody otrzymane i oczekiwane</dt><dd>{amount(totals.monthly_income_total)}</dd></div><div><dt>Wykonane obciążenia miesiąca</dt><dd>{amount(totals.monthly_income_cost)}</dd></div><div><dt>Pozostały plan i odłożenia</dt><dd>{amount(totals.monthly_income_remaining_plan)}</dd></div></dl>
        <small>Do otrzymania: {money(totals.expected_income ?? 0)}. To część dochodów powyżej.</small></details>
        <Link to={`/budget?view=plan&month=${data.month}`}>Sprawdź plan <ArrowRight size={14}/></Link>
      </article>
      <article className="budget-summary-card" aria-label="Wydano w miesiącu">
        <span className="budget-summary-label">Wydano w miesiącu</span><strong className="budget-summary-amount">{money(totals.period_spending?.spent ?? totals.spent)}</strong>
        <small>{future?'Miesiąc jeszcze się nie rozpoczął.':totals.period_spending?.through?`Do ${day(totals.period_spending.through)}`:'Wybrany miesiąc'}</small><details className="budget-card-calculation"><summary>Co obejmuje ta kwota?</summary><p>Zakupy i opłacone rachunki, po zwrotach. Bez przelewów własnych i nowych odłożeń.</p>
        <small>{future ? 'Bez wykonanych wydatków w przyszłym miesiącu.' : totals.period_spending?.through ? `Do ${day(totals.period_spending.through)} · ${totals.period_spending.expense_count} wydatków` : 'Zapisane wydatki wybranego miesiąca.'}</small>
        <div className="budget-summary-detail"><span>Rachunki i raty jeszcze do opłacenia</span><b>{money(pending)}</b><small>Uwzględnione w planie i finansowaniu z rezerw.</small></div></details>
        <Link to={`/budget?view=entries&month=${data.month}`}>Przejrzyj wydatki <ArrowRight size={14}/></Link>
      </article>
      <article className={`budget-summary-card ${closing && closing.available < 0 ? 'is-negative' : ''}`} aria-label="Prognoza wolnych środków na koniec miesiąca">
        <span className="budget-summary-label">Poza rezerwami na {day(end)}</span>
        <strong className="budget-summary-amount">{closing ? money(closing.available) : failed ? 'Niedostępne' : end < today ? 'Okres historyczny' : forecast ? 'Poza zakresem' : 'Wyliczanie…'}</strong>
        <details className="budget-card-calculation"><summary>Jak to policzono?</summary><p>{closing ? 'Prognoza od dzisiaj, po planowanych przepływach i odłożeniach.' : 'Prognoza obejmuje przyszłe dni od dzisiaj; nie odtwarza dawnych sald.'}</p>
        {closing && <dl className="budget-summary-breakdown"><div><dt>Saldo kont na koniec miesiąca</dt><dd>{money(closing.balance)}</dd></div><div><dt>W tym odłożone rezerwy</dt><dd>{money(closing.reserved)}</dd></div></dl>}
        <small>{future ? 'Uwzględnia też koszty przed rozpoczęciem tego miesiąca.' : 'Uwzględnia terminy płatności i założenia przyszłych wydatków.'}</small></details>
        <Link to={`/budget/forecast?month=${data.month}`}>Sprawdź prognozę i założenia <ArrowRight size={14}/></Link>
      </article>
    </div>
    <section className="budget-summary-now" aria-label="Pieniądze dzisiaj"><div><Wallet size={18}/><b>Stan dzisiaj</b><small>Niezależny od wybranego miesiąca</small></div><dl><div><dt>Na kontach</dt><dd>{money(totals.cash_balance ?? totals.balance)}</dd></div><div><dt>Odłożone rezerwy</dt><dd>{money(reservedNow)}</dd></div>{!!totals.credit_card_debt && <div><dt>Dług kart</dt><dd>{money(totals.credit_card_debt)}</dd></div>}<div><dt>Poza rezerwami{totals.credit_card_debt ? ' i długiem kart' : ''}</dt><dd>{money(availableNow)}</dd></div></dl><Link to={`/budget/accounts?month=${data.month}`}>Konta <ArrowRight size={14}/></Link><p>Kwota poza rezerwami nadal musi pokryć niewykonany plan.</p></section>
    <details className="budget-summary-explanation"><summary>Dlaczego plan i prognoza pokazują różne kwoty?</summary>
      <p>Plan dochodów obejmuje wyłącznie wybrany miesiąc. Prognoza zaczyna od dzisiejszego stanu, przechodzi przez wcześniejsze miesiące i może uzupełniać brakujące limity szacunkami.</p>
      {bridge && opening && closing && monthly !== undefined && <dl className="budget-summary-bridge" aria-label="Uzgodnienie planu z prognozą"><div><dt>Dzisiaj poza rezerwami</dt><dd>{money(forecast?.opening.available ?? availableNow)}</dd></div><div><dt>Zmiana przed rozpoczęciem miesiąca</dt><dd>{money(bridge.before)}</dd></div><div><dt>Bilans dochodów i planu miesiąca</dt><dd>{money(monthly)}</dd></div><div><dt>Różnica założeń prognozy względem planu</dt><dd>{money(bridge.assumptions)}</dd></div><div><dt>Prognoza poza rezerwami na koniec</dt><dd>{money(closing.available)}</dd></div></dl>}
      {!!estimates.length && <p>Prognoza korzysta z szacunkowych limitów: {estimates.map(category => category.name).join(', ')}. Sprawdź je w założeniach prognozy lub zapisz własne limity.</p>}
      <p>Pomocniczy bilans wybranego planu na dzisiejszych saldach: <b>{money(totals.to_plan)}</b>. {future ? 'Nie pomniejsza go plan pozostały przed tym miesiącem; nie jest prognozą wolnych pieniędzy na jego koniec.' : 'Uwzględnia wcześniejsze środki, oczekiwane wpływy oraz pozostałe limity, zobowiązania i odłożenia.'}</p>
    </details>
    {next && next.minimum < 0 && <div className="bp-warning" role="status">Do {day(next.through)} może zabraknąć środków poza rezerwami. Najniższa kwota po drodze: <b>{money(next.minimum)}</b>. <Link to={`/budget/forecast?month=${data.month}`}>Sprawdź terminy i konta</Link></div>}
  </section>;
}
