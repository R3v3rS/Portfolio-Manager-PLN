import { Link } from 'react-router-dom';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import type { LoanMonthPlan } from '../../api_planning';
import { planningDay as day, planningMoney as money } from './planningHelpers';

export default function BudgetLoanPayments({loans,data}:{loans:LoanMonthPlan[];data:BudgetWorkspace}) {
  return <>{loans.map(loan=><article className="budget-category-payment budget-loan-payment" key={`${loan.id}:${loan.installment_month}`}>
    <div><strong>{loan.name}</strong><small>Rata kredytu · {day(loan.date)} · {data.accounts.find(a=>a.id===loan.account_id)?.name??'Ustaw konto w kredycie'}</small><span className={`budget-payment-status ${loan.paid?'':'is-pending'}`}>{loan.paid?'Spłata zapisana':'Do rozliczenia'}</span></div>
    <b>{money(loan.paid_amount??loan.amount)}</b><Link className="budget-text-button" to={`/loans/${loan.id}?installment=${loan.installment_month}`}>{loan.paid?'Szczegóły':'Rozlicz ratę'}</Link>
  </article>)}</>;
}
