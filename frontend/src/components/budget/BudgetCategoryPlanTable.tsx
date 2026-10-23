import { Fragment, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronRight, Pencil, Plus } from 'lucide-react';
import type { BudgetCategory, BudgetWorkspace } from '../../api_budget_workspace';
import BudgetCategoryPayments from './BudgetCategoryPayments';
import BudgetPlanProgress from './BudgetPlanProgress';
import { categoryAllocation } from './budgetPlanPresentation';
import { confirmBudgetNavigation, useBudgetDraftGuard } from './budgetMode';
import { showCategory, categoryPlanDescription } from './categoryPresentation';
import { planSourceLabel } from './BudgetDefaultPlans';
import { planningMoney as money } from './planningHelpers';

type Props = { data: BudgetWorkspace; editing: boolean; busy: boolean; drafts: Record<number, string>; setDraft: (id: number, value: string) => void; onSave: (category: BudgetCategory) => void; onReset: (category: BudgetCategory) => void; onEdit: (category: BudgetCategory) => void; onAdd: (parent?: number) => void; reload: () => Promise<void>; revealId?:number|null };
export default function BudgetCategoryPlanTable({ data, editing, busy, drafts, setDraft, onSave, onReset, onEdit, onAdd, reload, revealId }: Props) {
  const [search, setSearch] = useState(''), [scope, setScope] = useState('ALL'), [unused, setUnused] = useState(false), [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [filtersOpen,setFiltersOpen]=useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  useEffect(()=>{const added=data.categories.find(c=>c.id===revealId);if(!added)return;setSearch(added.name);setScope('ALL');setUnused(true);setSelected(added.id);setFiltersOpen(true);},[revealId,data.categories]);
  const current = data.categories.find(c => c.id === selected);
  useBudgetDraftGuard(editing && !!current && Number(drafts[current.id] ?? current.manual_plan) !== current.manual_plan);
  const choose = (category: BudgetCategory | null) => {
    if (!confirmBudgetNavigation()) return;
    if (current) setDraft(current.id, String(current.manual_plan));
    setSelected(category?.id ?? null);
  };
  const matches = (c: BudgetCategory) => (c.path ?? c.name).toLocaleLowerCase('pl').includes(search.toLocaleLowerCase('pl'));
  const roots = data.categories.filter(c => !c.parent_id && showCategory(c, unused || editing, search)
    && (matches(c) || data.categories.some(child => child.parent_id === c.id && matches(child)))
    && (scope === 'ALL' || scope === 'SPENT' && c.spent !== 0 || scope === 'OVER' && c.remaining < 0));
  const editor = (c: BudgetCategory) => editing && selected === c.id ? <div className="budget-limit-editor">
    <label><span>Cały limit: {c.name}</span><input aria-label={`Limit: ${c.path ?? c.name}`} type="number" min="0" step="0.01" disabled={busy} value={drafts[c.id] ?? ''} onChange={e => setDraft(c.id, e.target.value)}/></label>
    <button className="budget-button-primary" disabled={busy || !Number.isFinite(Number(drafts[c.id])) || Number(drafts[c.id]) < 0 || ((c.plan_source === undefined || c.plan_source === 'MONTH') && Number(drafts[c.id] ?? 0) === c.manual_plan)} onClick={() => onSave(c)}>Zapisz</button>
    <button className="budget-text-button" disabled={busy} onClick={() => choose(null)}>Zamknij edycję</button>
    <small>Wpisz całkowitą kwotę. Podkategorie i rachunki mieszczą się w tym samym planie.</small>
  </div> : editing && !c.is_unassigned && !c.monthly_reserve_managed ? <button className="budget-text-button" aria-label={`Zmień limit: ${c.path ?? c.name}`} onClick={() => choose(c)}><Pencil size={14}/>Zmień limit</button> : null;
  return <section className="budget-panel budget-category-table-panel" aria-label="Limity kategorii">
    <button type="button" className="budget-button-secondary budget-filter-toggle" aria-expanded={filtersOpen} onClick={()=>setFiltersOpen(!filtersOpen)}>Filtry kategorii{(search||scope!=='ALL')?' · aktywne':''}</button>
    <div className={`budget-plan-filters ${filtersOpen?'is-mobile-open':''}`}><label>Szukaj kategorii<input type="search" value={search} onChange={e => { if (confirmBudgetNavigation()) setSearch(e.target.value); }} placeholder="Kategoria lub podkategoria"/></label><label>Pokaż kategorie<select value={scope} onChange={e => { if (confirmBudgetNavigation()) setScope(e.target.value); }}><option value="ALL">Wszystkie</option><option value="SPENT">Z wydatkami</option><option value="OVER">Z przekroczeniem limitu</option></select></label><label className="budget-checkbox"><input type="checkbox" checked={unused || editing} disabled={editing} onChange={e => setUnused(e.target.checked)}/>Pokaż nieużywane kategorie</label></div>
    {editing && <p className="bp-help" role="status">Zarządzanie pokazuje także nieużywane kategorie. Wybierz „Zmień limit” przy konkretnej pozycji.</p>}
    <div className="budget-plan-legend"><span className="is-spent">Wydano</span><span className="is-pending">Do opłacenia</span><span className="is-funding">Pula mediów</span><span>Reszta planu</span></div>
    <div className="budget-table-scroll"><table className="budget-compact-table budget-category-table"><thead><tr><th>Kategoria</th><th>Plan</th><th>Wydano</th><th>Pozostało</th></tr></thead><tbody>{roots.map(root => {
      const allChildren = data.categories.filter(c => c.parent_id === root.id);
      const children = allChildren.filter(c => showCategory(c, unused || editing, search));
      const open = expanded.has(root.id) || !!search;
      const allocation = categoryAllocation(root, data.categories);
      return <Fragment key={root.id}><tr id={`category-${root.id}`} className={root.remaining < 0 ? 'is-over' : ''}>
        <th><button className="budget-category-toggle" aria-expanded={open} aria-label={`Szczegóły kategorii: ${root.name}`} onClick={() => setExpanded(old => { const next = new Set(old); if (next.has(root.id)) next.delete(root.id); else next.add(root.id); return next; })}>{open ? <ChevronDown size={16}/> : <ChevronRight size={16}/>}<span><strong>{root.name}</strong><small>{planSourceLabel(root.plan_source)}{children.length > 0 && ` · Podkategorie (${children.length})`}</small></span></button><BudgetPlanProgress category={root}/></th>
        <td data-label="Plan"><b>{money(root.planned)}</b>{editor(root)}</td><td data-label="Wydano">{money(root.actual_spent??root.spent)}{root.actual_spent!==undefined&&Math.abs(root.actual_spent-root.spent)>.005&&<small>Wykonanie planu {money(root.spent)}</small>}</td><td data-label="Pozostało"><b className={root.remaining < 0 ? 'budget-negative' : ''}>{money(root.remaining)}</b>{root.remaining < 0 && <small className="budget-negative">Przekroczenie {money(-root.remaining)}</small>}</td>
      </tr>{open && <tr className="budget-category-detail-row"><td colSpan={4}><div className="budget-category-detail">
        <div className="budget-section-heading"><div>{root.description && <p>{root.description}</p>}<p className="bp-help">{categoryPlanDescription(root)}</p>{root.carryover ? <small>Przeniesiono {money(root.carryover)} z poprzedniego miesiąca.</small> : null}</div>{editing && !root.is_unassigned && <div className="br-actions"><button className="budget-text-button" aria-label={`Edytuj kategorię: ${root.path ?? root.name}`} onClick={() => onEdit(root)}><Pencil size={14}/>Edytuj kategorię</button><button className="budget-text-button" aria-label={`Dodaj podkategorię do: ${root.name}`} onClick={() => onAdd(root.id)}><Plus size={14}/>Podkategoria</button></div>}</div>
        {allChildren.length > 0 && <div className="budget-hierarchy-summary" aria-label={`Podział planu: ${root.name}`}><span>W podkategoriach <b>{money(allocation.assigned)}</b></span><span>Płatności bezpośrednio w kategorii <b>{money(allocation.directPayments)}</b></span><span>Nieprzypisana część planu <b>{money(allocation.unassigned)}</b></span><small>Te części składają się na plan kategorii. Nie sumuj go ponownie z podkategoriami. Nieprzypisana część nie oznacza wolnych pieniędzy na koncie.</small></div>}
        {editing && root.plan_source === 'MONTH' && root.default_plan != null && <button className="budget-text-button" disabled={busy} onClick={() => onReset(root)}>Wróć do domyślnego: {money(root.default_plan)}</button>}
        {children.length > 0 && <div className="budget-child-limits">{children.filter(c => matches(c) || matches(root)).map(c => <div key={c.id}><div><strong>{c.name}</strong><small>{categoryPlanDescription(c, root, data.categories)}</small><BudgetPlanProgress category={c}/></div><span>Plan {money(c.planned)} · wydano {money(c.actual_spent??c.spent)} · pozostało {money(c.remaining)}</span>{editor(c)}{editing && <button className="budget-text-button" aria-label={`Edytuj kategorię: ${c.path ?? c.name}`} onClick={() => onEdit(c)}><Pencil size={14}/>Edytuj</button>}{editing && c.plan_source === 'MONTH' && c.default_plan != null && <button className="budget-text-button" disabled={busy} onClick={() => onReset(c)}>Wróć do domyślnego: {money(c.default_plan)}</button>}</div>)}</div>}
        <BudgetCategoryPayments category={root} data={data} reload={reload}/>
        <Link className="budget-text-button" to={`/budget?view=entries&month=${data.month}&category=${root.id}`}>Przejrzyj wydatki: {root.name}</Link>
      </div></td></tr>}</Fragment>;
    })}</tbody></table></div>{!roots.length && <p className="budget-small-empty">Brak kategorii pasujących do filtrów.</p>}
    <p className="bp-help">Pozostało = plan pomniejszony o wykonanie (płatności z wcześniejszych rezerw nie zużywają go ponownie). W tej kwocie nadal mieszczą się nieopłacone rachunki i odłożenia na media. To limit kategorii, nie wolne saldo konta.</p>
    {editing && <button className="budget-text-button" onClick={() => onAdd()}><Plus size={16}/>Dodaj kategorię</button>}
  </section>;
}
