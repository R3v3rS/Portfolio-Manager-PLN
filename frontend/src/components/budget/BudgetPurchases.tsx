import {useBudgetFormGuard,useBudgetMode} from './budgetMode';
import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowRight,CalendarDays,Pencil,Plus,ShoppingBag} from 'lucide-react';
import {planningApi,type PurchaseInput,type PurchasePlan} from '../../api_planning';
import type {BudgetWorkspace} from '../../api_budget_workspace';
import {ImportDialog} from './imports/ImportUi';
import { PlanningMessages } from './PlanningUi';
import {planningMoney as money,planningDay as day,planningToday,usePlanningAction} from './planningHelpers';

function PurchaseEditor({data,purchase,reload,onClose:close}:{data:BudgetWorkspace;purchase:PurchasePlan|null;reload:()=>Promise<void>;onClose:()=>void}){
  const [input,setInput]=useState<PurchaseInput>(()=>purchase?{name:purchase.name,amount:purchase.amount,low:purchase.low,high:purchase.high,due_date:purchase.due_date,
    account_id:purchase.account_id,category_id:purchase.category_id,status:purchase.status==='COMPLETED'?'PLANNED':purchase.status,notes:purchase.notes,reserve_version:purchase.reserve_version}:
    {name:'',amount:0,low:0,high:0,due_date:planningToday(),account_id:data.accounts.find(a=>a.account_type!=='CREDIT_CARD')?.id??0,category_id:null,status:'IDEA',notes:''});
  const [requestId]=useState(()=>crypto.randomUUID()),action=usePlanningAction(reload);
  const canClose=useBudgetFormGuard(input);
  const onClose=()=>{if(canClose())close();};
  const update=<K extends keyof PurchaseInput>(key:K,value:PurchaseInput[K])=>setInput(old=>({...old,[key]:value}));
  return <ImportDialog title={purchase?'Edytuj plan zakupu':'Zakup lub wydarzenie'} busy={action.busy} onClose={onClose}>
    <PlanningMessages {...action}/><form className="bp-editor" onSubmit={e=>{e.preventDefault();void action.run(()=>purchase?planningApi.updatePurchase(purchase.id,input,purchase.version):planningApi.createPurchase(input,requestId),'Plan zakupu zapisany.',close);}}>
      <label>Nazwa<input required maxLength={120} placeholder="np. Wakacje, remont, wyprawka szkolna" value={input.name} onChange={e=>update('name',e.target.value)}/></label>
      <label>Stan planu<select value={input.status} onChange={e=>update('status',e.target.value as PurchaseInput['status'])}><option value="IDEA">Pomysł — poza prognozą</option><option value="PLANNED">Zaplanowane — odkładanie i prognoza</option><option value="CANCELLED">Anulowane</option></select></label>
      <label>Termin<input type="date" required min={input.status==='PLANNED'?planningToday():undefined} max="2100-12-31" value={input.due_date} onChange={e=>update('due_date',e.target.value)}/></label>
      <label>Przewidywany koszt w PLN<input type="number" required min="0.01" step="0.01" value={input.amount||''} onChange={e=>{const amount=Number(e.target.value);setInput(old=>({...old,amount,low:old.low||amount,high:old.high||amount}));}}/></label>
      <div className="budget-form-grid"><label>Wariant oszczędny<input type="number" required min="0.01" max={input.amount||undefined} step="0.01" value={input.low||''} onChange={e=>update('low',Number(e.target.value))}/></label><label>Wariant rozszerzony<input type="number" required min={input.amount||'0.01'} step="0.01" value={input.high||''} onChange={e=>update('high',Number(e.target.value))}/></label></div>
      <label>Konto odkładania i płatności<select required value={input.account_id} onChange={e=>update('account_id',Number(e.target.value))}>{data.accounts.filter(a=>a.account_type!=='CREDIT_CARD').map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label>Kategoria zakupu<select value={input.category_id??''} onChange={e=>update('category_id',e.target.value?Number(e.target.value):null)}><option value="">Wybiorę przy płatności</option>{data.categories.filter(c=>!c.is_unassigned).map(c=><option key={c.id} value={c.id}>{c.selection_label??c.name}</option>)}</select></label>
      <label>Notatka<textarea maxLength={2000} value={input.notes} onChange={e=>update('notes',e.target.value)}/></label>
      <p className="bp-help">Zaplanowany zakup korzysta z jednej rezerwy. Płatność zapiszesz w tej rezerwie; prognoza uwzględni koszt tylko raz. Zmiana kwoty lub terminu przeliczy odkładanie. Przed anulowaniem zwolnij odłożone środki.</p>
      <div className="budget-form-actions"><button className="budget-button-quiet" type="button" disabled={action.busy} onClick={onClose}>Anuluj</button><button className="budget-button-primary" type="submit" disabled={action.busy}>Zapisz plan zakupu</button></div>
    </form>
  </ImportDialog>;
}

function PurchaseCard({purchase,onEdit}:{purchase:PurchasePlan;onEdit:()=>void}){
  const {management}=useBudgetMode();
  const [variant,setVariant]=useState('BASE'),[date,setDate]=useState(purchase.due_date);
  const amount=variant==='LOW'?purchase.low:variant==='HIGH'?purchase.high:purchase.amount;
  const query=new URLSearchParams({purchase:String(purchase.id),purchase_amount:String(amount),purchase_date:date});
  const status={IDEA:'Pomysł',PLANNED:'Zaplanowane',CANCELLED:'Anulowane',COMPLETED:'Zrealizowane'}[purchase.status];
  return <article className="bp-purchase-card">
    <div className="bp-purchase-heading"><ShoppingBag size={21}/><span className={`bp-status is-${purchase.status.toLowerCase()}`}>{status}</span>{management&&<button className="budget-icon-button" aria-label={`Edytuj plan zakupu: ${purchase.name}`} disabled={purchase.status==='COMPLETED'} onClick={onEdit}><Pencil size={16}/></button>}</div>
    <h3>{purchase.name}</h3><strong className="bp-purchase-price">{money(purchase.amount)}</strong><p><CalendarDays size={15}/>{day(purchase.due_date)} · {purchase.account_name}</p>
    {purchase.notes&&<p className="bp-help">{purchase.notes}</p>}
    {purchase.reserve_id&&purchase.status==='PLANNED'&&<><div className="budget-progress" role="progressbar" aria-label={`Odłożone na: ${purchase.name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100,Math.round(purchase.saved/purchase.amount*100))}><span style={{width:Math.min(100,purchase.saved/purchase.amount*100)+'%'}}/></div><div className="bp-purchase-saving"><span>Odłożono {money(purchase.saved)}</span><span>Średnio {money(purchase.monthly_required)} / miesiąc</span></div><Link className="budget-button-secondary" to={`/budget/reserves?reserve=${purchase.reserve_id}`}>Odłóż lub rozlicz płatność<ArrowRight size={15}/></Link></>}
    {purchase.status==='PLANNED'&&<details className="bp-details"><summary>Sprawdź inny koszt lub termin</summary><label>Wariant<select value={variant} onChange={e=>setVariant(e.target.value)}><option value="LOW">Oszczędny — {money(purchase.low)}</option><option value="BASE">Podstawowy — {money(purchase.amount)}</option><option value="HIGH">Rozszerzony — {money(purchase.high)}</option></select></label><label>Termin wariantu<input type="date" min={planningToday()} value={date} onChange={e=>setDate(e.target.value)}/></label><Link className="budget-text-button" to={`/budget/forecast?${query}`}>Sprawdź wpływ na przyszłe saldo<ArrowRight size={15}/></Link></details>}
  </article>;
}

export default function BudgetPurchases({data,reload}:{data:BudgetWorkspace;reload:()=>Promise<void>}){
  const {management}=useBudgetMode();
  const [editing,setEditing]=useState<PurchasePlan|null|undefined>(undefined),[showAll,setShowAll]=useState(false);
  useEffect(()=>{if(!management)setEditing(undefined);},[management]);
  const rows=(data.planning?.purchases??[]).filter(p=>showAll||!['CANCELLED','COMPLETED'].includes(p.status));
  return <section className="budget-panel surface-card bp-panel"><div className="budget-section-heading"><div><p className="page-eyebrow">Większe wydatki bez zaskoczenia</p><h2>Zakupy i wydarzenia</h2><p>Porównuj warianty, zmieniaj termin i odkładaj na koszt. Pomysły pozostają poza prognozą, dopóki ich nie zaplanujesz.</p></div>{management&&<button className="budget-button-primary" onClick={()=>setEditing(null)}><Plus size={17}/>Dodaj plan</button>}</div><label className="bp-checkbox"><input type="checkbox" checked={showAll} onChange={e=>setShowAll(e.target.checked)}/>Pokaż anulowane i zrealizowane</label>
    {rows.length?<div className="bp-purchase-grid">{rows.map(p=><PurchaseCard key={`${p.id}-${p.version}-${p.amount}-${p.due_date}`} purchase={p} onEdit={()=>setEditing(p)}/>)}</div>:<div className="budget-small-empty">Zaplanuj wakacje, remont albo przyszły zakup. Koszt pojawi się w prognozie po wybraniu stanu „Zaplanowane”.</div>}
    {management&&editing!==undefined&&<PurchaseEditor data={data} purchase={editing} reload={reload} onClose={()=>setEditing(undefined)}/>}
  </section>;
}
