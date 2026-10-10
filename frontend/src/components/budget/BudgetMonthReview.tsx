import { Link } from 'react-router-dom';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { planningMoney as money, planningDay as day } from './planningHelpers';

export default function BudgetMonthReview({data}:{data:BudgetWorkspace}) {
  const review=data.planning?.month_review;
  if(!review)return null;
  return <details className="bp-month-review" open><summary>Kontrola przed zamknięciem miesiąca</summary>
    <>{review.closing_snapshot&&<p className={review.closing_snapshot.changed?"bp-warning":"bp-help"}>{review.closing_snapshot.changed?`Dane zmieniły się po zamknięciu. Zmiana wpływów: ${money(review.closing_snapshot.differences.income)}, wydatków: ${money(review.closing_snapshot.differences.spent)}. Sprawdź też plany i odłożenia. Zachowaliśmy pierwotne zamknięcie i przeniesione limity.`:'Dane są zgodne z zapisanym zamknięciem miesiąca.'}</p>}</><p className="bp-help">Zamknięcie nie oznacza automatycznego opłacenia rachunków. Porównaj bieżące salda z bankiem; aplikacja nie pobiera ich samodzielnie.</p>
    <div className="bp-table-wrap"><table><thead><tr><th>Konto</th><th>Saldo w aplikacji</th><th>Rezerwy</th><th>Sprawdzone z bankiem</th></tr></thead><tbody>{review.accounts.map(a=><tr key={a.id}><th>{a.name}</th><td>{money(a.balance)}</td><td>{money(a.reserved)}</td><td>{a.verified_on?day(a.verified_on):'Nie sprawdzono'}</td></tr>)}</tbody></table></div>
    <Link className="budget-text-button" to="/budget/accounts">Porównaj i potwierdź salda</Link>
    <ul className="bp-closing-list">
      {review.corrections.map(c=><li key={`correction-${c.id}`}><span>Różnica salda · {c.name} · {day(c.date)} · {c.notes}</span><b>{money(c.amount)}</b></li>)}
      {review.unpaid_bills.map(b=><li key={`bill-${b.id}`}><Link to={`/budget?view=bills&month=${data.month}`}>Brak rozliczenia: {b.title}</Link><b>{money(b.amount)}</b></li>)}
      {review.unpaid_loans.map(l=><li key={`loan-${l.id}-${l.installment_month}`}><Link to={`/loans/${l.id}`}>Brak zapisu raty: {l.name}</Link><b>{money(l.amount)}</b></li>)}
      {review.missing_reserves.map(r=><li key={`reserve-${r.reserve_id}`}><Link to={`/budget/reserves?reserve=${r.reserve_id}`}>Brakuje odłożenia: {r.name}</Link><b>{money(r.remaining)}</b></li>)}
    </ul>
    {!!review.unassigned&&<Link className="budget-text-button" to="/budget/imports">Wydatki bez kategorii: {review.unassigned}</Link>}
    {review.warnings.map(w=><p className="bp-warning" key={w}>{w}</p>)}
    {!review.unpaid_bills.length&&!review.unpaid_loans.length&&!review.missing_reserves.length&&!review.unassigned&&<p className="bp-help">Wszystkie zapisane zobowiązania i plany odłożeń są rozliczone.</p>}
  </details>;
}
