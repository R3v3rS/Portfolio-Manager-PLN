import {useBudgetDraftGuard,useBudgetMode} from './budgetMode';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Settings2 } from 'lucide-react';
import { type CashForecast } from '../../api_forecast';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { planningApi } from '../../api_planning';
import { PlanningMessages } from './PlanningUi';
import {  planningDay as day, planningMoney as money, usePlanningAction } from './planningHelpers';
import { TrendChart } from '../charts/ChartKit';

export { default as BudgetPlanningOverview } from './BudgetSummary';

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
  const {management}=useBudgetMode();
  const context = data.planning!;
  const config = context.settings;
  const [payDay, setPayDay] = useState(String(config.resolved_pay_day));
  const [income, setIncome] = useState(String(config.resolved_income_id ?? ''));
  const [spendingAccount, setSpendingAccount] = useState(String(config.resolved_spending_account_id ?? ''));
  const [loanAccount, setLoanAccount] = useState(String(config.resolved_loan_account_id ?? ''));
  useBudgetDraftGuard(settingsOnly&&(Number(payDay)!==config.resolved_pay_day||income!==String(config.resolved_income_id??'')||spendingAccount!==String(config.resolved_spending_account_id??'')||loanAccount!==String(config.resolved_loan_account_id??'')));
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
    {management&&settingsOnly&&<section className="budget-panel surface-card"><div className="budget-section-heading"><div><p className="page-eyebrow">Dopasuj do swoich finansów</p><h2><Settings2 size={18}/> Ustawienia planowania</h2><p>Wybrany dzień określa granice okresu. Termin faktycznego wpływu zmienisz w planie dochodu.</p></div><Link className="budget-text-button" to="/budget/forecast">Edytuj dochody <ArrowRight size={15}/></Link></div>
      <form className="bp-settings-form" onSubmit={save}><fieldset disabled={action.busy}>
        <label>Dzień początku okresu<input required type="number" min="1" max="31" step="1" value={payDay} onChange={e => setPayDay(e.target.value)}/></label>
        <label>Główna wypłata<select value={income} onChange={e => setIncome(e.target.value)}><option value="">Wybierz automatycznie</option>{forecast?.incomes.filter(item => item.active && item.frequency === 'MONTHLY').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Konto codziennych wydatków<select value={spendingAccount} onChange={e => setSpendingAccount(e.target.value)}><option value="">Konto głównej wypłaty</option>{data.accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Konto rat kredytów<select value={loanAccount} onChange={e => setLoanAccount(e.target.value)}><option value="">Konto codziennych wydatków</option>{data.accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <button className="budget-button-primary" type="submit">Zapisz ustawienia</button>
      </fieldset></form><p className="bp-help">Dzień 29–31 w krótszym miesiącu oznacza jego ostatni dzień. Konto rat jest domyślne dla kredytów bez własnego przypisania. Osobne konto i kategorię ustawisz w <Link to="/loans">szczegółach każdego kredytu</Link>. Ustawienia służą planowaniu i nie wykonują przelewów.</p>
    </section>}
    {management&&!settingsOnly&&<Link className="budget-text-button" to={`/budget?view=settings&settings=planning&month=${data.month}`}>Zmień dzień okresu i konta planowania</Link>}
  </div>;
}
