import { Pencil, Plus } from 'lucide-react';
import type { BudgetCategory } from '../../api_budget_workspace';
import { categoryPlanDescription, showCategory } from './categoryPresentation';

type Props = { categories: BudgetCategory[]; search: string; showUnused: boolean;
  edit: (category: BudgetCategory) => void; add: (parent: number) => void };
export default function BudgetCategorySettings({ categories, search, showUnused, edit, add }: Props) {
  const matches = (category: BudgetCategory) => (category.path ?? category.name).toLocaleLowerCase('pl').includes(search.toLocaleLowerCase('pl'));
  const visible = (category: BudgetCategory) => !category.is_unassigned && showCategory(category, showUnused, search);
  const description = (category: BudgetCategory) => <>
    {category.description && <p className="budget-category-description">{category.description}</p>}
    <small>{category.has_activity === false ? 'Nieużywana · zachowana do późniejszego użycia'
      : categoryPlanDescription(category, categories.find(parent => parent.id === category.parent_id))}</small>
    <small>Reguły importu: {category.rule_count ?? 0} · {category.daily_pace_effective === false ? 'Poza wskaźnikiem tempa' : 'Uwzględniana w tempie'}</small>
  </>;
  const editButton = (category: BudgetCategory) => <button className="budget-text-button" aria-label={`Edytuj kategorię: ${category.path ?? category.name}`} onClick={() => edit(category)}><Pencil size={14}/>Edytuj</button>;
  return <div className="budget-settings-categories">{categories.filter(root => !root.parent_id && visible(root)
    && (matches(root) || categories.some(child => child.parent_id === root.id && matches(child)))).map(root => {
      const children = categories.filter(child => child.parent_id === root.id && visible(child) && (matches(root) || matches(child)));
      return <section className="budget-category-setting-group" key={root.id}>
        <div className="budget-settings-category"><strong>{root.name}</strong><div className="br-actions">{editButton(root)}
          <button className="budget-text-button" aria-label={`Dodaj podkategorię do: ${root.name}`} onClick={() => add(root.id)}><Plus size={14}/>Podkategoria</button></div></div>
        <details open={search ? true : undefined}><summary>Opis i podkategorie: {root.name} ({children.length})</summary>
          <div className="budget-category-root-description">{description(root)}</div>
          {children.map(child => <div key={child.id} className="budget-settings-category budget-settings-child"><div><strong>{child.name}</strong>{description(child)}</div>{editButton(child)}</div>)}
        </details>
      </section>;
    })}</div>;
}
