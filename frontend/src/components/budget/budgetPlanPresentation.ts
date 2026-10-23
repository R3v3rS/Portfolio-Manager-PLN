import type { BudgetCategory } from '../../api_budget_workspace';

const cents = (value: number) => Math.round(value * 100);
export function categoryAllocation(category: BudgetCategory, categories: BudgetCategory[]) {
  const children = categories.filter(child => child.parent_id === category.id);
  const assigned = children.reduce((sum, child) => sum + cents(child.planned), 0);
  const directPayments = cents(category.direct_planned_bills ?? Math.max(0, category.planned_bills - children.reduce((sum, child) => sum + child.planned_bills, 0)));
  return { assigned: assigned / 100, directPayments: directPayments / 100, unassigned: Math.max(0, cents(category.planned) - assigned - directPayments) / 100 };
}

export function categoryProgress(category: BudgetCategory) {
  const planned = Math.max(0, cents(category.planned));
  const executed = Math.max(0, cents(category.spent));
  const spent = Math.max(0, cents(category.actual_spent ?? category.spent) - cents(category.reserve_settled ?? 0));
  const funded = Math.max(0, executed - spent);
  const pending = Math.max(0, cents(category.plan_details?.payments_pending ?? 0));
  const funding = Math.max(0, cents(category.plan_details?.media_remaining ?? 0)) + funded;
  // Planned commitments occupy the remaining track; an overrun never overflows the card.
  const used = Math.min(planned, spent);
  const payments = Math.min(Math.max(0, planned - used), pending);
  const reserves = Math.min(Math.max(0, planned - used - payments), funding);
  return { spent: planned ? used / planned * 100 : 0, pending: planned ? payments / planned * 100 : 0,
    funding: planned ? reserves / planned * 100 : 0, percent: planned ? executed / planned * 100 : null,
    pendingAmount: pending / 100, fundingAmount: (funding - funded) / 100, fundedAmount: funded / 100 };
}
