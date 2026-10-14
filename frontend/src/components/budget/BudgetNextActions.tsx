import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle2 } from 'lucide-react';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import type { CashForecast } from '../../api_forecast';
import { planningDay as day, planningMoney as money } from './planningHelpers';

export default function BudgetNextActions({ data, forecast }: { data: BudgetWorkspace; forecast: CashForecast | null }) {
  const items: {key:string;title:string;detail:string;href:string;action:string}[] = [];
  for (const account of forecast?.account_forecasts ?? []) {
    if (account.summaries[0]?.first_shortfall) items.push({key:`account:${account.id}`,title:`Sprawdź środki na ${account.name}`,detail:`Prognozowany brak od ${day(account.summaries[0].first_shortfall)}.`,href:`/budget/forecast?month=${data.month}`,action:'Sprawdź konto'});
  }
  for (const bill of data.bills.filter(item => item.status !== 'PAID').sort((a,b)=>a.due_date.localeCompare(b.due_date))) {
    items.push({key:`bill:${bill.id}`,title:bill.title,detail:`${money(bill.amount)} · termin ${day(bill.due_date)} · ${bill.account_name}`,href:`/budget?view=bills&month=${data.month}&bill=${bill.id}`,action:bill.payment_candidates?.length?'Powiąż płatność':'Rozlicz rachunek'});
  }
  for (const loan of data.planning?.loans?.filter(item => !item.paid) ?? []) {
    items.push({key:`loan:${loan.id}`,title:`Rata: ${loan.name}`,detail:`${money(loan.amount)} · ${day(loan.date)}`,href:`/loans/${loan.id}?installment=${loan.installment_month}`,action:'Sprawdź spłatę'});
  }
  const missing = data.planning?.reserve_plans.filter(item => item.remaining > 0) ?? [];
  if (missing.length) items.push({key:'reserves',title:'Uzupełnij planowane odłożenia',detail:`${missing.length} rezerw · brakuje ${money(missing.reduce((sum,item)=>sum+item.remaining,0))}`,href:`/budget?view=plan&month=${data.month}#reserve-month-plans`,action:'Odłóż środki'});
  const unassigned = data.entries.filter(entry => entry.classification_status === 'UNASSIGNED').length;
  if (unassigned) items.push({key:'entries',title:'Przypisz kategorie zakupom',detail:`${unassigned} wydatków już zapisanych w budżecie.`,href:`/budget/imports?tab=pending&month=${data.month}`,action:'Przypisz kategorie'});
  return <section className="budget-panel surface-card budget-priority-panel">
    <div className="budget-section-heading"><div><p className="page-eyebrow">Następny krok</p><h2>Do załatwienia w miesiącu</h2></div><Link className="budget-text-button" to={`/budget?view=bills&month=${data.month}`}>Wszystkie płatności <ArrowRight size={15}/></Link></div>
    {!items.length ? <p className="budget-small-empty"><CheckCircle2 size={18}/> Płatności i odłożenia z planu są rozliczone.</p> : <div className="budget-bill-list">{items.slice(0,5).map(item => <div className="budget-category-payment" key={item.key}><div><strong>{item.title}</strong><small>{item.detail}</small></div><Link className="budget-text-button" to={item.href}>{item.action} <ArrowRight size={14}/></Link></div>)}</div>}
    {items.length > 5 && <p className="bp-help">Pokazujemy 5 najbliższych spraw. Pozostałe znajdziesz w płatnościach i planie miesiąca.</p>}
  </section>;
}
