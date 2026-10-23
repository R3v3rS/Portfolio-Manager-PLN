import type { BudgetCategory } from '../../api_budget_workspace';
import { categoryProgress } from './budgetPlanPresentation';
import { planningMoney as money } from './planningHelpers';

export default function BudgetPlanProgress({ category }: { category: BudgetCategory }) {
  const progress = categoryProgress(category);
  return <div className="budget-plan-progress">
    <div className={`budget-segment-track ${category.remaining < 0 ? 'is-over' : ''}`} aria-hidden="true">
      <span className="is-spent" style={{ width: `${progress.spent}%` }}/><span className="is-pending" style={{ width: `${progress.pending}%` }}/><span className="is-funding" style={{ width: `${progress.funding}%` }}/>
    </div>
    <small>{progress.percent === null ? 'Bez zaplanowanej kwoty' : `Wykonanie planu ${Math.round(progress.percent)}%`}{progress.pendingAmount > 0 && ` · do opłacenia ${money(progress.pendingAmount)}`}{progress.fundedAmount > 0 && ` · odłożono na media ${money(progress.fundedAmount)}`}{progress.fundingAmount > 0 && ` · do odłożenia na media ${money(progress.fundingAmount)}`}{(category.reserve_settled ?? 0) > 0 && ` · opłacono z wcześniejszej rezerwy ${money(category.reserve_settled ?? 0)}`}</small>
  </div>;
}
