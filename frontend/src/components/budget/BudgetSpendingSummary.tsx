import { ArrowRight, ReceiptText } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { planningDay as day, planningMoney as money, planningToday } from './planningHelpers';

export default function BudgetSpendingSummary({ data, compact = false }: { data: BudgetWorkspace; compact?: boolean }) {
  const summary = data.totals.period_spending;
  if (!summary) return null;
  const currentMonth = data.month === planningToday().slice(0, 7);
  return <section className={`budget-spending-summary ${compact?'is-compact':''}`} aria-label="Wydatki miesiąca">
    {!compact&&<div className="budget-spending-main">
      <p className="page-eyebrow"><ReceiptText size={16}/> {currentMonth ? 'Wydano w tym miesiącu do dziś' : 'Wydano w wybranym miesiącu'}</p>
      <strong>{money(summary.spent)}</strong>
      <p>{summary.through ? <>{day(summary.first)} — {day(summary.through)} · Liczba wydatków: {summary.expense_count}</> : 'Ten miesiąc jeszcze się nie rozpoczął.'}</p>
      {(summary.refunds??0)>0&&<small>Kwota po zwrotach: zakupy {money(summary.spent+(summary.refunds??0))} − zwroty {money(summary.refunds??0)}.</small>}
      <Link to={`/budget?view=entries&month=${data.month}`}>Przejrzyj wydatki <ArrowRight size={15}/></Link>
    </div>}
    <div className="budget-spending-detail">
      <span>Odłożono na rezerwy</span><b>{money(summary.reserve_contributions)}</b>
      <p>Pieniądze na przyszłe koszty, np. roczne ubezpieczenie.</p>
    </div>
    <div className="budget-spending-detail">
      <span>Łączne obciążenie budżetu</span><b>{money(summary.budget_spent)}</b>
      <p>Wydatki i odłożone rezerwy{summary.reserve_settled || summary.reserve_released ? ', pomniejszone o rozliczone lub uwolnione rezerwy.' : '.'}</p>
      {summary.reserve_settled > 0 && <small>Opłacono z rezerw: {money(summary.reserve_settled)}</small>}
      {summary.reserve_released > 0 && <small>Uwolniono z rezerw: {money(summary.reserve_released)}</small>}
    </div>
    <details className="budget-calculation-help budget-spending-note"><summary>Jak liczymy wydatki i odłożenia?</summary><p>Zakupy i opłacone rachunki liczymy raz, także wpisy bez zmiany salda. Planowane płatności i przelewy między własnymi kontami nie zwiększają wydanej kwoty.</p></details>
  </section>;
}
