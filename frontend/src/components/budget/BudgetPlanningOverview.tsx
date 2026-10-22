import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CalendarDays, Settings2, Wallet } from 'lucide-react';
import { type CashForecast } from '../../api_forecast';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { planningApi } from '../../api_planning';
import { PlanningMessages } from './PlanningUi';
import {  planningDay as day, planningMoney as money, usePlanningAction } from './planningHelpers';
import { TrendChart } from '../charts/ChartKit';

export function BudgetPlanningOverview({ data, forecast, failed }: { data: BudgetWorkspace; forecast: CashForecast | null; failed: boolean }) {
  const next=forecast?.before_income;
  const [year,month]=data.month.split('-').map(Number);
  const end=`${data.month}-${String(new Date(year,month,0).getDate()).padStart(2,'0')}`;
  const closing=forecast?.points?.find(point=>point.date===end);
  const expected=data.totals.expected_income??0;
  const monthly=data.totals.monthly_income_to_plan;
  return <>
    <section className="bp-money-cards budget-month-highlights budget-three-highlights" aria-label="Dostępne pieniądze i plan">
      <article aria-label="Wydano w miesiącu"><span>Wydano w miesiącu</span><strong>{money(data.totals.period_spending?.spent??data.totals.spent)}</strong><p>Zakupy i opłacone rachunki, po zwrotach.</p>{data.totals.period_spending&&<small>{data.totals.period_spending.through?`Do ${day(data.totals.period_spending.through)} · ${data.totals.period_spending.expense_count} wydatków`:'Miesiąc jeszcze się nie rozpoczął.'}</small>}<Link to={`/budget?view=entries&month=${data.month}`}>Przejrzyj wydatki <ArrowRight size={14}/></Link></article>
      <article className={`bp-money-now ${data.totals.to_plan<0?'is-negative':''}`} aria-label="Do rozdysponowania w planie"><span>Do rozdysponowania w planie</span><strong>{money(data.totals.to_plan)}</strong><p>Po pokryciu pozostałych limitów, płatności i rezerw.</p><small>W tym oczekiwane wpływy: {money(expected)}. To pieniądze jeszcze nieotrzymane.</small><Link to={`/budget?view=plan&month=${data.month}`}>Sprawdź plan <ArrowRight size={14}/></Link></article>
      <article className={closing&&closing.available<0?'is-negative':''} aria-label="Przewidywane saldo na koniec miesiąca"><span>Przewidywane saldo na {day(end)}</span><strong>{closing?money(closing.balance):failed?'Niedostępne':forecast?'Poza zakresem':'Wyliczanie…'}</strong><p>{closing?`Poza rezerwami: ${money(closing.available)}`:'Bieżąca prognoza obejmuje okres od dzisiaj.'}</p><small>Symulacja salda na konkretny dzień. Wolna kwota planu jest pokazana osobno.</small><Link to={`/budget/forecast?month=${data.month}`}>Prognoza i terminy <ArrowRight size={14}/></Link></article>
    </section>
    <div className="budget-cash-context"><span><Wallet size={16}/>Na kontach teraz <strong>{money(data.totals.cash_balance??data.totals.balance)}</strong>{!!data.totals.credit_card_debt&&<> · dług kart <strong>{money(data.totals.credit_card_debt)}</strong></>} · na rezerwy {money(data.totals.reserved??0)}</span><span><CalendarDays size={16}/>Do opłacenia w miesiącu <strong>{money(data.fixed_costs?.pending??data.bills.filter(b=>b.status!=='PAID').reduce((sum,b)=>sum+b.amount,0))}</strong></span></div>
    {monthly!==undefined&&<p className={monthly<0?'budget-plan-support is-needed':'budget-plan-support'} aria-label="Wolne z przychodów miesiąca">{monthly<0?<>Plan wymaga <b>{money(-monthly)}</b> pieniędzy z poprzednich miesięcy.</>:<>Z samych przychodów miesiąca pozostaje <b>{money(monthly)}</b> do zaplanowania.</>} Oczekiwane wpływy uwzględniamy w planie, a otrzymane są już w saldzie.</p>}
    <details className="budget-calculation-help"><summary>Jak rozumieć te kwoty?</summary><p>Do rozdysponowania: saldo {money(data.totals.balance)}{data.accounts.some(a=>a.account_type==='CREDIT_CARD')?' (po uwzględnieniu zadłużenia kart)':''} + oczekiwane wpływy {money(expected)} − pozostałe limity, rachunki i raty {money(data.totals.remaining_commitments??Math.max(0,data.totals.planned-data.totals.spent))} − rezerwy {money(data.totals.reserved??0)} − dodatkowe odłożenia {money(data.totals.reserve_plan_extra??data.totals.reserve_plan_remaining??0)}.</p><p>Poza rezerwami teraz: {money(data.totals.available_now??data.totals.balance)}. Ta kwota nadal musi pokryć niewykonany plan miesiąca.</p>{next&&<p>Okres rozliczeniowy kończy się {day(next.through)}; według prognozy poza rezerwami pozostanie wtedy {money(next.available)}.</p>}</details>
    {next&&next.minimum<0&&<div className="bp-warning" role="status">W okresie do {day(next.through)} może zabraknąć środków poza rezerwami. Najniższa kwota po drodze: <b>{money(next.minimum)}</b>. <Link to={`/budget/forecast?month=${data.month}`}>Sprawdź terminy i konta</Link></div>}
  </>;
}

export function ForecastAccounts({ data, days = 30 }: { data: CashForecast; days?: number }) {
  if (!data.account_forecasts?.length) return null;
  return <section className="budget-panel surface-card bp-account-forecast">
    <div className="budget-section-heading"><div><p className="page-eyebrow">Gdzie powinny leżeć pieniądze</p><h2>Konta za {days} dni</h2><p>Codzienne wydatki i raty przypisujemy do kont wskazanych w ustawieniach planowania. Przelewy poniżej są propozycjami.</p></div><Link className="budget-text-button" to="/budget/accounts">Konta i przelewy <ArrowRight size={15}/></Link></div>
    <div className="bp-table-wrap"><table><thead><tr><th>Konto</th><th>Saldo</th><th>Odłożone</th><th>Poza rezerwami</th><th>Najniższa wolna kwota</th></tr></thead><tbody>{data.account_forecasts.map(account => {
      const summary = account.summaries.find(item => item.days === days)!;
      return <tr key={account.id}><th scope="row">{account.name}{account.account_type==='CREDIT_CARD'&&<small>Karta kredytowa · ujemne saldo oznacza dług</small>}</th><td>{money(summary.balance ?? 0)}</td><td>{money(summary.reserved ?? 0)}</td><td className={account.account_type!=='CREDIT_CARD'&&(summary.available ?? 0) < 0 ? 'budget-negative' : ''}>{money(summary.available ?? 0)}</td><td className={account.account_type!=='CREDIT_CARD'&&(summary.minimum ?? 0) < 0 ? 'budget-negative' : ''}>{money(summary.minimum ?? 0)}{summary.first_shortfall && <small>Niedobór od {day(summary.first_shortfall)}</small>}</td></tr>;
    })}</tbody></table></div>
    {!!data.transfer_suggestions?.length && <div className="bp-transfers"><h3>Przelewy potrzebne w najbliższych 30 dniach</h3>{data.transfer_suggestions.map((item, i) => <div key={i}><span>{item.source_name} <ArrowRight size={14}/> {item.target_name}</span><b>{money(item.amount)}</b><small>Najpóźniej {day(item.by_date)}</small></div>)}<p>Propozycja wykorzystuje wolne środki, które pozostają dostępne na koncie źródłowym przez 30 dni. Zapisz wykonany przelew w historii kont.</p></div>}
  </section>;
}

export function BudgetPayCycle({ data, forecast, reload, settingsOnly=false }: { data: BudgetWorkspace; forecast: CashForecast | null; reload: () => Promise<void>;settingsOnly?:boolean }) {
  const context = data.planning!;
  const config = context.settings;
  const [payDay, setPayDay] = useState(String(config.resolved_pay_day));
  const [income, setIncome] = useState(String(config.resolved_income_id ?? ''));
  const [spendingAccount, setSpendingAccount] = useState(String(config.resolved_spending_account_id ?? ''));
  const [loanAccount, setLoanAccount] = useState(String(config.resolved_loan_account_id ?? ''));
  const action = usePlanningAction(reload);
  const cycle = context.cycle;
  const points = forecast?.points.filter(point => point.date >= cycle.start && point.date <= cycle.end) ?? [];
  const events = forecast?.events.filter(event => event.date >= cycle.start && event.date <= cycle.end) ?? [];
  const plannedOut = -events.filter(event => event.cash_delta < 0).reduce((sum, event) => sum + event.cash_delta, 0);
  const save = (event: React.FormEvent) => {
    event.preventDefault();
    void action.run(() => planningApi.settings({ pay_day: Number(payDay), income_id: income ? Number(income) : null,
      spending_account_id: spendingAccount ? Number(spendingAccount) : null, loan_account_id: loanAccount ? Number(loanAccount) : null, version: config.version }), 'Ustawienia okresu i kont zapisane.');
  };
  return <div className="bp-section-stack">
    <PlanningMessages {...action}/>
    {!settingsOnly&&<section className="budget-panel surface-card">
      <div className="budget-section-heading"><div><p className="page-eyebrow">Okres rozliczeniowy</p><h2>{day(cycle.start)} — {day(cycle.end)}</h2><p>Miesiąc wybrany u góry wskazuje początek okresu. Limity kategorii i historia nadal dotyczą miesięcy kalendarzowych.</p></div></div>
      <div className="bp-cycle-stats"><div><span>Otrzymane w okresie</span><b>{money(cycle.income)}</b></div><div><span>Jeszcze oczekiwane</span><b>{money(cycle.expected_income)}</b></div><div><span>Zapisane wydatki</span><b>{money(cycle.spent)}</b></div><div><span>Pozostałe koszty w prognozie</span><b>{forecast ? money(plannedOut) : '—'}</b></div></div>
      {points.length > 1 ? <TrendChart data={points} series={[{key:'balance', name:'Saldo kont', area:true}, {key:'available', name:'Poza rezerwami', dashed:true}]} height={260} zero note="Prognoza zaczyna się dzisiaj; zapisane wydatki są już w saldzie. Plan nie zmienia historii."/> : <p className="budget-small-empty">Wykres pojawia się dla części okresu objętej prognozą od dzisiaj. Historyczne wpływy i wydatki widzisz powyżej.</p>}
    </section>}
    {settingsOnly&&<section className="budget-panel surface-card"><div className="budget-section-heading"><div><p className="page-eyebrow">Dopasuj do swoich finansów</p><h2><Settings2 size={18}/> Ustawienia planowania</h2><p>Wybrany dzień określa granice okresu. Termin faktycznego wpływu zmienisz w planie dochodu.</p></div><Link className="budget-text-button" to="/budget/forecast">Edytuj dochody <ArrowRight size={15}/></Link></div>
      <form className="bp-settings-form" onSubmit={save}><fieldset disabled={action.busy}>
        <label>Dzień początku okresu<input required type="number" min="1" max="31" step="1" value={payDay} onChange={e => setPayDay(e.target.value)}/></label>
        <label>Główna wypłata<select value={income} onChange={e => setIncome(e.target.value)}><option value="">Wybierz automatycznie</option>{forecast?.incomes.filter(item => item.active && item.frequency === 'MONTHLY').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Konto codziennych wydatków<select value={spendingAccount} onChange={e => setSpendingAccount(e.target.value)}><option value="">Konto głównej wypłaty</option>{data.accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Konto rat kredytów<select value={loanAccount} onChange={e => setLoanAccount(e.target.value)}><option value="">Konto codziennych wydatków</option>{data.accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <button className="budget-button-primary" type="submit">Zapisz ustawienia</button>
      </fieldset></form><p className="bp-help">Dzień 29–31 w krótszym miesiącu oznacza jego ostatni dzień. Konto rat jest domyślne dla kredytów bez własnego przypisania. Osobne konto i kategorię ustawisz w <Link to="/loans">szczegółach każdego kredytu</Link>. Ustawienia służą planowaniu i nie wykonują przelewów.</p>
    </section>}
    {!settingsOnly&&<Link className="budget-text-button" to={`/budget?view=settings&settings=planning&month=${data.month}`}>Zmień dzień okresu i konta planowania</Link>}
  </div>;
}
