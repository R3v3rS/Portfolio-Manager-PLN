import type { BudgetCategory } from '../../api_budget_workspace';
import { planningMoney as money } from './planningHelpers';
import { categoryAllocation } from './budgetPlanPresentation';

export function showCategory(category: Pick<BudgetCategory,'has_activity'>, includeUnused: boolean, search: string) {
  return includeUnused || search.trim() !== '' || category.has_activity !== false;
}

export function categoryPlanDescription(category: BudgetCategory, parent?: BudgetCategory, categories?: BudgetCategory[]) {
  if (category.monthly_reserve_managed) return `Miesięczna pula: ${money(category.planned)}. Płatności i odłożenia wykorzystują tę samą kwotę.`;
  if (category.planned_bills > 0 && category.manual_plan === 0) return `Plan z rachunków i rat: ${money(category.planned_bills)}.`;
  if (parent && category.manual_plan === 0 && category.planned_bills === 0) {
    const ordinary=categories ? categoryAllocation(parent,categories).unassigned : null;
    if (ordinary !== null) return `Bez własnej kwoty. W planie „${parent.name}” nieprzypisane do podkategorii i płatności: ${money(ordinary)}. To część wspólnej puli, nie dodatkowy limit.`;
    if (parent.planned > parent.planned_bills) return `Korzysta ze wspólnego limitu „${parent.name}”. Nie ma dodatkowej kwoty; sprawdź podział planu kategorii.`;
    if (parent.planned_bills > 0) return `Brak osobnego limitu. Plan „${parent.name}” pokrywa przypisane płatności; nowy zakup będzie dodatkowym kosztem.`;
    return 'Brak własnego i wspólnego limitu. Zapisane wydatki nadal obciążają budżet.';
  }
  if (category.planned === 0) return category.plan_source === 'MONTH' || category.plan_source === 'DEFAULT'
    ? 'Własny limit: 0 zł. Wydatki nadal obciążają budżet.' : 'Brak planu. Ustaw limit albo przypisz rachunek.';
  return parent ? `Własny limit ${money(category.manual_plan)} mieści się we wspólnym planie „${parent.name}”.`
    : 'Wspólny limit kategorii — podkategorie i płatności liczymy tylko raz.';
}
