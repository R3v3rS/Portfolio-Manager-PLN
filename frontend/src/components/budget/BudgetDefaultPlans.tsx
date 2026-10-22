import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {budgetWorkspaceApi,type BudgetWorkspace,type DefaultPlans} from '../../api_budget_workspace';
import {extractErrorMessageFromUnknown} from '../../http/response';
import {planningToday,planningMoney as money,usePlanningAction} from './planningHelpers';
import {showCategory} from './categoryPresentation';
import {PlanningMessages} from './PlanningUi';

export const planSourceLabel=(source:BudgetWorkspace['categories'][number]['plan_source'])=>
  source==='DEFAULT'?'Plan domyślny':source==='MONTH'?'Limit na ten miesiąc':source==='MEDIA'?'Miesięczna pula':'Plan z podkategorii lub płatności';

export default function BudgetDefaultPlans({data,reload}:{data:BudgetWorkspace;reload:()=>Promise<void>}){
  const earliest=planningToday().slice(0,7);
  const [start,setStart]=useState(data.month<earliest?earliest:data.month);
  const [record,setRecord]=useState<DefaultPlans|null>(null),[drafts,setDrafts]=useState<Record<number,string>>({});
  const [error,setError]=useState(''),[loading,setLoading]=useState(true),[search,setSearch]=useState(''),[showUnused,setShowUnused]=useState(false);
  const refresh=async()=>{const next=await budgetWorkspaceApi.defaultPlans(start);setRecord(next);setDrafts(Object.fromEntries(next.items.map(row=>[row.category_id,row.amount===null?'':String(row.amount)])));};
  const action=usePlanningAction(async()=>{await refresh();await reload();});
  useEffect(()=>{
    let active=true;setLoading(true);setError('');setRecord(null);
    budgetWorkspaceApi.defaultPlans(start).then(next=>{if(active){setRecord(next);setDrafts(Object.fromEntries(next.items.map(row=>[row.category_id,row.amount===null?'':String(row.amount)])));}})
      .catch(err=>{if(active)setError(extractErrorMessageFromUnknown(err));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[start]);
  const selected=record?.items.filter(row=>!row.managed&&(drafts[row.category_id]??'').trim()!=='')??[];
  return <section className="budget-panel surface-card budget-default-plans" id="default-plans">
    <div className="budget-section-heading"><div><p className="page-eyebrow">Podstawa kolejnych miesięcy</p><h2>Domyślny plan miesięczny</h2><p>Limity obowiązują do kolejnej zmiany. Limit zapisany w konkretnym miesiącu ma pierwszeństwo, także gdy wynosi 0 zł.</p></div><Link className="budget-text-button" to={`/budget?view=plan&month=${start}`}>Sprawdź plan miesiąca</Link></div>
    <div className="budget-plan-toolbar"><label>Obowiązuje od miesiąca<input type="month" min={earliest} max="2100-12" required value={start} disabled={action.busy} onChange={e=>{if(e.target.value)setStart(e.target.value);}}/></label><button className="budget-button-secondary" disabled={loading||action.busy||!record} onClick={()=>setDrafts(old=>({...old,...Object.fromEntries(data.categories.filter(c=>!c.monthly_reserve_managed&&!c.is_unassigned&&c.plan_source!=='NONE').map(c=>[c.id,String(c.manual_plan)]))}))}>Użyj limitów z {data.month}</button></div>
    <p className="bp-help">Wspólny limit kategorii zawiera jej podkategorie, rachunki i raty. Nie kopiujemy płatności ani jednorazowych rachunków. Kwoty mediów ustawiasz w miesięcznych pulach, a pozostałych rezerw — w ich planach odłożeń.</p>
    {error&&<p role="alert" className="budget-negative">{error}</p>}<PlanningMessages {...action}/>
    {loading?<p className="bp-help">Ładowanie limitów…</p>:record&&<form onSubmit={e=>{e.preventDefault();void action.run(()=>budgetWorkspaceApi.saveDefaults(start,selected.map(row=>({category_id:row.category_id,amount:Number(drafts[row.category_id]),revision:row.revision}))),'Plan domyślny zapisany. Miesięczne wyjątki pozostają bez zmian.');}}>
      <fieldset disabled={action.busy}><label className="budget-checkbox"><input type="checkbox" checked={showUnused} onChange={e=>setShowUnused(e.target.checked)}/>Pokaż nieużywane kategorie</label><label>Szukaj kategorii domyślnego planu<input type="search" value={search} onChange={e=>setSearch(e.target.value)}/></label>
        <div className="budget-default-list">{record.items.filter(row=>showCategory(data.categories.find(c=>c.id===row.category_id)??{has_activity:true},showUnused,search)&&row.name.toLocaleLowerCase('pl').includes(search.toLocaleLowerCase('pl'))).map(row=><div key={row.category_id} className={'budget-default-row'+(row.parent_id?' is-child':'')}><div><strong>{row.name}</strong><small>{row.managed?'Zarządzana przez miesięczną pulę':row.amount===null?'Brak planu domyślnego':`${money(row.amount)} od ${row.start_month}`}</small>{row.history.some(r=>r.start_month>start)&&<small>Zaplanowana późniejsza zmiana: {row.history.filter(r=>r.start_month>start).map(r=>`${r.start_month}: ${money(r.amount)}`).join(' · ')}</small>}</div>{!row.managed&&<label>Limit w PLN<input aria-label={`Domyślny limit: ${row.name}`} type="number" min="0" max="999999999.99" step="0.01" placeholder="Nie ustawiono" value={drafts[row.category_id]??''} onChange={e=>setDrafts(old=>({...old,[row.category_id]:e.target.value}))}/></label>}</div>)}</div>
        <p className="bp-help">Puste pole pozostawia dotychczasową zasadę. 0 zł zeruje własny limit; rachunki, raty i limity podkategorii nadal obowiązują. Zmiana nie usuwa wcześniejszych planów ani miesięcznych wyjątków.</p>
        <button type="submit" className="budget-button-primary" disabled={!selected.length}>Zapisz plan domyślny ({selected.length})</button>
      </fieldset>
    </form>}
  </section>;
}
