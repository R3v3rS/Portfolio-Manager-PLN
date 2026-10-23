import { Link } from 'react-router-dom';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { planningDay as day, planningMoney as money } from './planningHelpers';

export default function BudgetPaymentsSummary({data}:{data:BudgetWorkspace}) {
  const loans=data.planning?.loans??[];
  const paidBills=data.bills.filter(b=>b.status==='PAID'),pendingBills=data.bills.filter(b=>b.status!=='PAID');
  const paidLoans=loans.filter(l=>l.paid),pendingLoans=loans.filter(l=>!l.paid);
  const paid=(paidBills.reduce((sum,b)=>sum+Math.round(b.amount*100),0)+paidLoans.reduce((sum,l)=>sum+Math.round((l.paid_amount??l.amount)*100),0))/100;
  const pending=(pendingBills.reduce((sum,b)=>sum+Math.round(b.amount*100),0)+pendingLoans.reduce((sum,l)=>sum+Math.round(l.amount*100),0))/100;
  const next=[...pendingBills.map(b=>({key:`bill:${b.id}`,date:b.due_date,name:b.title,amount:b.amount,href:`/budget?view=bills&month=${data.month}&bill=${b.id}`})),...pendingLoans.map(l=>({key:`loan:${l.id}:${l.installment_month}`,date:l.date,name:l.name,amount:l.amount,href:`/loans/${l.id}?installment=${l.installment_month}`}))].sort((a,b)=>a.date.localeCompare(b.date)||a.key.localeCompare(b.key))[0];
  const count=data.bills.length+loans.length;
  return <div className="budget-payments-summary" aria-label="Podsumowanie rachunków i rat">
    <div><span>Opłacono</span><strong>{money(paid)}</strong><small>{paidBills.length+paidLoans.length} z {count} płatności</small></div>
    <div><span>Do opłacenia</span><strong>{money(pending)}</strong><small>Rachunki: {pendingBills.length} · raty: {pendingLoans.length}</small></div>
    <div><span>Najbliższa płatność</span>{next?<><Link className="budget-text-button" to={next.href}>{day(next.date)} · {money(next.amount)}</Link><small>{next.name}</small></>:<strong className="budget-payments-complete">{count?'Wszystkie płatności rozliczone':'Brak płatności w tym miesiącu'}</strong>}</div>
  </div>;
}
