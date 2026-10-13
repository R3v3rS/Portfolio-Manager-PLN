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
  const next = forecast?.before_income;
  const monthLabel=new Date(data.month+'-01T12:00:00').toLocaleDateString('pl-PL',{month:'long',year:'numeric'});
  return <>
    <section className="bp-money-cards budget-month-highlights" aria-label="Dostępne pieniądze i plan">
      <article aria-label="Wydano w miesiącu"><span>Wydano w miesiącu</span><strong>{money(data.totals.period_spending?.spent??data.totals.spent)}</strong><p>Zakupy i opłacone rachunki, po zwrotach.</p>{data.totals.period_spending&&<small>{data.totals.period_spending.through?`Do ${day(data.totals.period_spending.through)} · ${data.totals.period_spending.expense_count} wydatków`:'Miesiąc jeszcze się nie rozpoczął.'}</small>}<Link to={`/budget?view=entries&month=${data.month}`}>Przejrzyj wydatki <ArrowRight size={14}/></Link></article>
      <article aria-label="Pozostałe zobowiązania"><span>Pozostałe zobowiązania</span><strong>{money(data.fixed_costs?.pending??data.bills.filter(b=>b.status!=='PAID').reduce((sum,b)=>sum+b.amount,0))}</strong><p>{data.fixed_costs?'Rachunki i raty jeszcze do opłacenia.':'Rachunki jeszcze do opłacenia.'}</p><Link to={`/budget?view=bills&month=${data.month}`}>Sprawdź rachunki <ArrowRight size={14}/></Link></article>
      {data.totals.monthly_income_to_plan!==undefined&&<article className={data.totals.monthly_income_to_plan<0?'is-negative':''} aria-label="Wolne z przychodów miesiąca"><span>Wolne z przychodów miesiąca</span><strong>{money(data.totals.monthly_income_to_plan)}</strong><p>Bez wcześniejszych sald i oszczędności.</p>{data.totals.monthly_income_to_plan<0&&<small>Plan wymaga pieniędzy z poprzednich miesięcy.</small>}</article>}
      <article className={`bp-money-now ${data.totals.to_plan<0?'is-negative':''}`} aria-label="Do zaplanowania z dostępnych pieniędzy"><span>Do zaplanowania</span><strong>{money(data.totals.to_plan)}</strong><p>Z sald kont i oczekiwanych wpływów, po uwzględnieniu planu i rezerw.</p></article>
    </section>
    <div className="budget-cash-context"><span><Wallet size={16}/>Dostępne teraz <strong>{money(data.totals.available_now??data.totals.balance)}</strong></span><span><CalendarDays size={16}/>Do następnej wypłaty <strong>{next?money(next.available):failed?'Niedostępne':'Wyliczanie…'}</strong></span><Link to={`/budget/forecast?month=${data.month}`}>Prognoza i terminy <ArrowRight size={14}/></Link></div>
    <details className="budget-calculation-help"><summary>Jak liczymy dostępne pieniądze?</summary><p>{monthLabel} · otrzymano {money(data.totals.income)}{(data.totals.expected_income??0)>0&&` + oczekiwane ${money(data.totals.expected_income??0)}`}. Wykorzystano {money(data.totals.monthly_income_cost??0)}; pozostały plan {money(data.totals.monthly_income_remaining_plan??0)}.</p><p>Wolne z przychodów miesiąca: bez wcześniejszych sald i oszczędności. Plan obejmuje wydatki oraz odłożenia.{(data.totals.monthly_invested??0)>0&&` Wpłaty do inwestycji: ${money(data.totals.monthly_invested??0)}.`}</p><p>Do zaplanowania: saldo {money(data.totals.balance)} + oczekiwane wpływy {money(data.totals.expected_income??0)} − pozostałe limity, rachunki i raty {money(data.totals.remaining_commitments??Math.max(0,data.totals.planned-data.totals.spent))} − rezerwy {money(data.totals.reserved??0)} − dodatkowe odłożenia {money(data.totals.reserve_plan_extra??data.totals.reserve_plan_remaining??0)}.</p>{next&&<p>Do następnej wypłaty: prognoza na {day(next.through)}. Płatności do tego dnia: {money(next.must_pay)}.</p>}</details>
    {next && next.minimum < 0 && <div className="bp-warning" role="status">Przed kolejną wypłatą plan przekracza dostępne środki. Najniższa prognoza: <b>{money(next.minimum)}</b>. <Link to={`/budget/forecast?month=${data.month}`}>Sprawdź koszty i konta</Link></div>}
  </>;
}

export function ForecastAccounts({ data, days = 30 }: { data: CashForecast; days?: number }) {
  if (!data.account_forecasts?.length) return null;
  return <section className="budget-panel surface-card bp-account-forecast">
    <div className="budget-section-heading"><div><p className="page-eyebrow">Gdzie powinny leżeć pieniądze</p><h2>Konta za {days} dni</h2><p>Codzienne wydatki i raty przypisujemy do kont wskazanych w ustawieniach planowania. Przelewy poniżej są propozycjami.</p></div><Link className="budget-text-button" to="/budget/accounts">Konta i przelewy <ArrowRight size={15}/></Link></div>
    <div className="bp-table-wrap"><table><thead><tr><th>Konto</th><th>Saldo</th><th>Odłożone</th><th>Poza rezerwami</th><th>Najniższa wolna kwota</th></tr></thead><tbody>{data.account_forecasts.map(account => {
      const summary = account.summaries.find(item => item.days === days)!;
      return <tr key={account.id}><th scope="row">{account.name}</th><td>{money(summary.balance ?? 0)}</td><td>{money(summary.reserved ?? 0)}</td><td className={(summary.available ?? 0) < 0 ? 'budget-negative' : ''}>{money(summary.available ?? 0)}</td><td className={(summary.minimum ?? 0) < 0 ? 'budget-negative' : ''}>{money(summary.minimum ?? 0)}{summary.first_shortfall && <small>Niedobór od {day(summary.first_shortfall)}</small>}</td></tr>;
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
      <div className="budget-section-heading"><div><p className="page-eyebrow">Od wypłaty do wypłaty</p><h2>{day(cycle.start)} — {day(cycle.end)}</h2><p>Miesiąc wybrany u góry wskazuje początek okresu. Limity kategorii i historia nadal dotyczą miesięcy kalendarzowych.</p></div></div>
      <div className="bp-cycle-stats"><div><span>Otrzymane w okresie</span><b>{money(cycle.income)}</b></div><div><span>Jeszcze oczekiwane</span><b>{money(cycle.expected_income)}</b></div><div><span>Zapisane wydatki</span><b>{money(cycle.spent)}</b></div><div><span>Pozostałe koszty w prognozie</span><b>{forecast ? money(plannedOut) : '—'}</b></div></div>
      {points.length > 1 ? <TrendChart data={points} series={[{key:'balance', name:'Saldo kont', area:true}, {key:'available', name:'Poza rezerwami', dashed:true}]} height={260} zero note="Prognoza zaczyna się dzisiaj; zapisane wydatki są już w saldzie. Plan nie zmienia historii."/> : <p className="budget-small-empty">Wykres pojawia się dla części okresu objętej prognozą od dzisiaj. Historyczne wpływy i wydatki widzisz powyżej.</p>}
    </section>}
    <section className="budget-panel surface-card"><div className="budget-section-heading"><div><p className="page-eyebrow">Dopasuj do swoich finansów</p><h2><Settings2 size={18}/> Ustawienia planowania</h2><p>Wybrany dzień określa granice okresu. Termin faktycznego wpływu zmienisz w planie dochodu.</p></div><Link className="budget-text-button" to="/budget/forecast">Edytuj dochody <ArrowRight size={15}/></Link></div>
      <form className="bp-settings-form" onSubmit={save}><fieldset disabled={action.busy}>
        <label>Dzień początku okresu<input required type="number" min="1" max="31" step="1" value={payDay} onChange={e => setPayDay(e.target.value)}/></label>
        <label>Główna wypłata<select value={income} onChange={e => setIncome(e.target.value)}><option value="">Wybierz automatycznie</option>{forecast?.incomes.filter(item => item.active && item.frequency === 'MONTHLY').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Konto codziennych wydatków<select value={spendingAccount} onChange={e => setSpendingAccount(e.target.value)}><option value="">Konto głównej wypłaty</option>{data.accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Konto rat kredytów<select value={loanAccount} onChange={e => setLoanAccount(e.target.value)}><option value="">Konto codziennych wydatków</option>{data.accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <button className="budget-button-primary" type="submit">Zapisz ustawienia</button>
      </fieldset></form><p className="bp-help">Dzień 29–31 w krótszym miesiącu oznacza jego ostatni dzień. Konto rat jest domyślne dla kredytów bez własnego przypisania. Osobne konto i kategorię ustawisz w <Link to="/loans">szczegółach każdego kredytu</Link>. Ustawienia służą planowaniu i nie wykonują przelewów.</p>
    </section>
    {!settingsOnly&&forecast && <ForecastAccounts data={forecast}/>}
  </div>;
}
