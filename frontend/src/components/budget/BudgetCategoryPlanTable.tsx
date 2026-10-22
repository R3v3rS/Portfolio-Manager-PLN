import {Fragment,useState} from 'react';
import {Car,ChevronDown,ChevronRight,HeartPulse,House,Pencil,Plus,ReceiptText,Shapes,Sparkles,UtensilsCrossed,type LucideIcon} from 'lucide-react';
import type {BudgetCategory,BudgetWorkspace} from '../../api_budget_workspace';
import BudgetCategoryPayments from './BudgetCategoryPayments';
import {showCategory,categoryPlanDescription} from './categoryPresentation';
import {planSourceLabel} from './BudgetDefaultPlans';
import {planningMoney as money} from './planningHelpers';

const icons:Record<string,LucideIcon>={Car,HeartPulse,House,ReceiptText,Shapes,Sparkles,UtensilsCrossed};
type Props={data:BudgetWorkspace;editing:boolean;busy:boolean;drafts:Record<number,string>;setDraft:(id:number,value:string)=>void;onSave:(category:BudgetCategory)=>void;onReset:(category:BudgetCategory)=>void;onEdit:(category:BudgetCategory)=>void;onAdd:(parent?:number)=>void;reload:()=>Promise<void>};
export default function BudgetCategoryPlanTable({data,editing,busy,drafts,setDraft,onSave,onReset,onEdit,onAdd,reload}:Props){
  const [search,setSearch]=useState(''),[scope,setScope]=useState('ALL'),[unused,setUnused]=useState(false),[expanded,setExpanded]=useState<Set<number>>(new Set());
  const matches=(c:BudgetCategory)=>(c.path??c.name).toLocaleLowerCase('pl').includes(search.toLocaleLowerCase('pl'));
  const roots=data.categories.filter(c=>!c.parent_id&&!c.is_unassigned&&showCategory(c,unused,search)
    &&(matches(c)||data.categories.some(child=>child.parent_id===c.id&&matches(child)))
    &&(scope==='ALL'||scope==='SPENT'&&c.spent!==0||scope==='OVER'&&(c.remaining<0||(c.plan_details?.ordinary_over??0)>0)));
  const editor=(c:BudgetCategory)=><div className="budget-limit-editor"><label><span className="sr-only">Limit: {c.path??c.name}</span><input aria-label={`Limit: ${c.path??c.name}`} type="number" min="0" step="0.01" disabled={busy||c.monthly_reserve_managed} value={c.monthly_reserve_managed?String(c.planned):drafts[c.id]??''} onChange={e=>setDraft(c.id,e.target.value)}/></label><button className="budget-button-secondary" disabled={busy||c.monthly_reserve_managed||((c.plan_source===undefined||c.plan_source==='MONTH')&&Number(drafts[c.id]??0)===c.manual_plan)} onClick={()=>onSave(c)}>Zapisz</button></div>;
  return <section className="budget-panel budget-category-table-panel" aria-label="Limity kategorii">
    <div className="budget-plan-filters"><label>Szukaj kategorii<input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Kategoria lub podkategoria"/></label><label>Pokaż kategorie<select value={scope} onChange={e=>setScope(e.target.value)}><option value="ALL">Wszystkie</option><option value="SPENT">Z wydatkami</option><option value="OVER">Z przekroczeniem limitu</option></select></label><label className="budget-checkbox"><input type="checkbox" checked={unused} onChange={e=>setUnused(e.target.checked)}/>Pokaż nieużywane kategorie</label></div>
    <div className="budget-table-scroll"><table className="budget-compact-table budget-category-table"><thead><tr><th>Kategoria</th><th>Cały plan</th><th>Wydano w planie</th><th>Do opłacenia</th><th>Na zwykłe wydatki</th></tr></thead><tbody>{roots.map(root=>{
      const children=data.categories.filter(c=>c.parent_id===root.id&&showCategory(c,unused,search));
      const open=editing||expanded.has(root.id)||!!search,Icon=icons[root.icon]??Shapes;
      const left=root.plan_details?.ordinary_remaining??Math.max(0,root.remaining);
      return <Fragment key={root.id}><tr id={`category-${root.id}`} className={root.remaining<0?'is-over':''}><th><button className="budget-category-toggle" aria-expanded={open} aria-label={`Szczegóły kategorii: ${root.name}`} onClick={()=>setExpanded(old=>{const next=new Set(old);if(next.has(root.id))next.delete(root.id);else next.add(root.id);return next;})}>{open?<ChevronDown size={16}/>:<ChevronRight size={16}/>}<Icon size={18}/><span><strong>{root.name}</strong><small>{planSourceLabel(root.plan_source)}{children.length>0&&` · Podkategorie (${children.length})`}</small></span></button></th><td>{editing?editor(root):money(root.planned)}</td><td>{money(root.spent)}{root.remaining<0&&<small className="budget-negative">Ponad plan {money(-root.remaining)}</small>}</td><td>{money(root.plan_details?.payments_pending??Math.max(0,root.planned_bills-root.spent))}</td><td><b>{money(left)}</b>{(root.plan_details?.ordinary_over??0)>0&&<small className="budget-negative">Przekroczenie {money(root.plan_details!.ordinary_over)}</small>}</td></tr>
        {open&&<tr className="budget-category-detail-row"><td colSpan={5}><div className="budget-category-detail">
          <div className="budget-section-heading"><div>{root.description&&<p>{root.description}</p>}<p className="bp-help">{categoryPlanDescription(root)}</p>{root.carryover? <small>Przeniesiono {money(root.carryover)} z poprzedniego miesiąca.</small>:null}</div><div className="br-actions"><button className="budget-text-button" aria-label={`Edytuj kategorię: ${root.path??root.name}`} onClick={()=>onEdit(root)}><Pencil size={14}/>Edytuj kategorię</button><button className="budget-text-button" aria-label={`Dodaj podkategorię do: ${root.name}`} onClick={()=>onAdd(root.id)}><Plus size={14}/>Podkategoria</button></div></div>
          {root.plan_source==='MONTH'&&root.default_plan!=null&&<button className="budget-text-button" disabled={busy} onClick={()=>onReset(root)}>Wróć do domyślnego: {money(root.default_plan)}</button>}
          {children.length>0&&<div className="budget-child-limits">{children.filter(c=>matches(c)||matches(root)).map(c=><div key={c.id}><div><strong>{c.name}</strong><small>{planSourceLabel(c.plan_source)} · {categoryPlanDescription(c,root)}</small></div><span>Plan {money(c.planned)} · wydano {money(c.spent)}</span>{editing&&editor(c)}<button className="budget-text-button" aria-label={`Edytuj kategorię: ${c.path??c.name}`} onClick={()=>onEdit(c)}><Pencil size={14}/>Edytuj</button>{c.plan_source==='MONTH'&&c.default_plan!=null&&<button className="budget-text-button" disabled={busy} onClick={()=>onReset(c)}>Wróć do domyślnego: {money(c.default_plan)}</button>}</div>)}</div>}
          <BudgetCategoryPayments category={root} data={data} reload={reload}/>
        </div></td></tr>}
      </Fragment>;
    })}</tbody></table></div>{!roots.length&&<p className="budget-small-empty">Brak kategorii pasujących do filtrów.</p>}
    <p className="bp-help">Cały plan zawiera podkategorie i przypisane płatności. „Na zwykłe wydatki” jest już po wydzieleniu rachunków; nie sumuj ponownie wierszy nadrzędnych i podrzędnych. Podczas edycji wpisujesz własny całkowity limit, a nie dodatkową kwotę poza rachunkami.</p>
    <button className="budget-text-button" onClick={()=>onAdd()}><Plus size={16}/>Dodaj kategorię</button>
  </section>;
}
