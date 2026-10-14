import type { BudgetCategory } from '../../api_budget_workspace';
import { planningMoney as money } from './planningHelpers';

export function showCategory(category: BudgetCategory, includeUnused: boolean, search: string) {
  return includeUnused || search.trim() !== '' || category.has_activity !== false;
}

export function categoryPlanDescription(category: BudgetCategory, parent?: BudgetCategory) {
  if (category.monthly_reserve_managed) return `Miesięczna pula: ${money(category.planned)}. Płatności i odłożenia wykorzystują tę samą kwotę.`;
  if (category.planned_bills > 0 && category.manual_plan === 0) return `Plan z rachunków i rat: ${money(category.planned_bills)}.`;
  if (parent && category.manual_plan === 0 && category.planned_bills === 0) {
    const ordinary=parent.plan_details?.ordinary_planned??Math.max(0,parent.planned-parent.planned_bills);
    if (ordinary > 0) return `Korzysta ze wspólnego limitu zwykłych wydatków „${parent.name}”: ${money(ordinary)}. Bez dodatkowej kwoty.`;
    if (parent.planned_bills > 0) return `Brak osobnego limitu. Plan „${parent.name}” pokrywa przypisane płatności; nowy zakup będzie dodatkowym kosztem.`;
    return 'Brak własnego i wspólnego limitu. Zapisane wydatki nadal obciążają budżet.';
  }
  if (category.planned === 0) return category.plan_source === 'MONTH' || category.plan_source === 'DEFAULT'
    ? 'Własny limit: 0 zł. Wydatki nadal obciążają budżet.' : 'Brak planu. Ustaw limit albo przypisz rachunek.';
  return parent ? `Własny limit ${money(category.manual_plan)} mieści się we wspólnym planie „${parent.name}”.`
    : 'Wspólny limit kategorii — podkategorie i płatności liczymy tylko raz.';
}
