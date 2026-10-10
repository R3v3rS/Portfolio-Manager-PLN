import {useEffect,useState} from 'react';
import {reservesApi,type ReservesWorkspace} from '../../api_reserves';
import {accountsApi} from '../../api_accounts';
import type {ReserveMonthPlan} from '../../api_planning';
import {ReserveEditor} from '../../pages/BudgetReserves';
import {ImportDialog} from './imports/ImportUi';
import {PlanningMessages} from './PlanningUi';
import {planningMoney as money,planningToday,usePlanningAction} from './planningHelpers';
import {extractErrorMessageFromUnknown} from '../../http/response';

export default function BudgetReserveFunding({row,mode,reload,onClose}:{row:ReserveMonthPlan;mode:'ADD'|'TRANSFER'|'EDIT'|'SPEND';reload:()=>Promise<void>;onClose:()=>void}){
  const [context,setContext]=useState<ReservesWorkspace|null>(null),[error,setError]=useState('');
  const [amount,setAmount]=useState(String(row.remaining)),[source,setSource]=useState(''),[target,setTarget]=useState(String(row.account_id)),[date,setDate]=useState(planningToday());
  const [requestId]=useState(()=>crypto.randomUUID()),action=usePlanningAction(reload);
  useEffect(()=>{let active=true;void reservesApi.get().then(next=>{if(active){setContext(next);setSource(String(next.accounts.find(a=>a.id!==row.account_id)?.id??''));}}).catch(err=>{if(active)setError(extractErrorMessageFromUnknown(err));});return()=>{active=false;};},[row.account_id]);
  const item=context?.items.find(r=>r.id===row.reserve_id),from=context?.accounts.find(a=>String(a.id)===source),to=context?.accounts.find(a=>String(a.id)===target),value=Number(amount)||0;
  if((mode==='EDIT'||mode==='SPEND')&&context&&item)return <ReserveEditor editor={{kind:mode==='EDIT'?'PLAN':'SPEND',item}} data={context} onCancel={onClose} onSaved={()=>{void reload();onClose();}}/>;
  return <ImportDialog title={`${mode==='TRANSFER'?'Przelej i odłóż':mode==='EDIT'?'Edytuj rezerwę':'Odłóż'}: ${row.name}`} busy={action.busy} onClose={onClose}>
    {error&&<p className="budget-feedback is-error" role="alert">{error}</p>}{!context&&!error&&<p>Wczytywanie aktualnych sald…</p>}
    <PlanningMessages {...action}/>
    {context&&item&&mode!=='EDIT'&&<form className="bp-editor" onSubmit={e=>{e.preventDefault();void action.run(async()=>{
      if(mode==='TRANSFER')return accountsApi.transfer({source_account_id:Number(source),target_account_id:Number(target),amount:value,date,notes:`Odłożenie: ${row.name}`,move_money:true,reserve_id:item.id,version:item.version,source_balance:from?.balance??0,target_balance:to?.balance??0,reserve_action:'FUND'},requestId);
      return reservesApi.move(item.id,{kind:'ADD',amount:value,date,notes:`Plan miesięczny: ${row.name}`,account_id:Number(target)},item.version,requestId);
    },'Pieniądze odłożone na rezerwę.',onClose);}}>
      <p className="bp-help">{mode==='TRANSFER'?'Zapisujesz wykonany przelew między własnymi kontami i przypisujesz kwotę do rezerwy.':'Wydzielasz pieniądze, które już są na wybranym koncie.'} Odłożenie jest kosztem planu miesiąca, a zakup z tej rezerwy nie obciąży go ponownie.</p>
      {mode==='TRANSFER'&&<label>Przelew z konta<select required value={source} onChange={e=>setSource(e.target.value)}><option value="">Wybierz konto</option>{context.accounts.filter(a=>String(a.id)!==target).map(a=><option key={a.id} value={a.id}>{a.name} · wolne {money(a.available)}</option>)}</select></label>}
      <label>Konto rezerwy<select required value={target} onChange={e=>setTarget(e.target.value)}>{context.accounts.filter(a=>mode!=='TRANSFER'||String(a.id)!==source).map(a=><option key={a.id} value={a.id}>{a.name} · wolne {money(a.available)}</option>)}</select></label>
      <label>Kwota odłożenia<input required type="number" min="0.01" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)}/></label><label>Data odłożenia<input required type="date" max={planningToday()} value={date} onChange={e=>setDate(e.target.value)}/></label>
      <div className="bp-balance-preview">{mode==='TRANSFER'&&from&&<p>{from.name}: <b>{money(from.balance)} → {money(from.balance-value)}</b></p>}{to&&<><p>{to.name}: <b>{money(to.balance)} → {money(to.balance+(mode==='TRANSFER'?value:0))}</b></p><small>Rezerwa: {money(item.saved)} → {money(item.saved+value)}</small></>}{(mode==='TRANSFER'?from:to)&&value>((mode==='TRANSFER'?from:to)?.available??0)&&<strong className="budget-negative">Na wybranym koncie brakuje wolnych środków na to odłożenie.</strong>}</div>
      <button className="budget-button-primary" disabled={action.busy||(mode==='TRANSFER'&&(!source||source===target))} type="submit">{mode==='TRANSFER'?'Zapisz przelew i odłożenie':'Zapisz odłożenie'}</button>
    </form>}
  </ImportDialog>;
}
