import {useEffect,useState} from 'react';
import type {BudgetWorkspace} from '../../api_budget_workspace';
import {reservesApi,type ReservesWorkspace} from '../../api_reserves';
import type {PaymentMatch} from '../../api_planning';
import {BillPayment} from './BudgetObligations';
import {ImportDialog} from './imports/ImportUi';
import {PlanningMessages} from './PlanningUi';
import {planningMoney as money,planningDay as day,usePlanningAction} from './planningHelpers';
import {extractErrorMessageFromUnknown} from '../../http/response';

function ReserveMatch({match,reload,onClose}:{match:PaymentMatch;reload:()=>Promise<void>;onClose:()=>void}){
  const [context,setContext]=useState<ReservesWorkspace|null>(null),[error,setError]=useState('');
  const [entryId,setEntryId]=useState(match.candidates[0]?.id),[requestId]=useState(()=>crypto.randomUUID());
  const action=usePlanningAction(reload);
  useEffect(()=>{let active=true;reservesApi.get().then(r=>{if(active)setContext(r);}).catch(e=>{if(active)setError(extractErrorMessageFromUnknown(e));});return()=>{active=false;};},[]);
  const reserve=context?.items.find(r=>r.id===match.id),entry=match.candidates.find(e=>e.id===entryId),account=context?.accounts.find(a=>a.id===entry?.account_id);
  return <ImportDialog title={`Powiąż płatność: ${match.title}`} busy={action.busy} onClose={onClose}>
    {error&&<p role="alert" className="budget-feedback is-error">{error}</p>}<PlanningMessages {...action}/>
    <p>Wybierz istniejący wydatek. Rozliczymy rezerwę i zachowamy saldo konta.</p>
    <label>Transakcja do powiązania<select value={entryId} onChange={e=>setEntryId(Number(e.target.value))}>{match.candidates.map(e=><option key={e.id} value={e.id}>{e.description} · {day(e.date)} · {money(e.amount)}</option>)}</select></label>
    {reserve&&entry&&<div className="bp-balance-preview">{account?.name}: <b>{money(account?.balance??0)} → {money(account?.balance??0)}</b><small>Rezerwa: {money(reserve.saved)} → {money(reserve.monthly_amount==null&&reserve.frequency==='ONCE'?0:Math.max(0,reserve.saved-entry.amount))}</small></div>}
    <p className="bp-help">Podobny opis lub kategoria jest podpowiedzią. Sprawdź dokument i kwotę przed zatwierdzeniem.</p>
    <div className="budget-form-actions"><button className="budget-button-quiet" onClick={onClose} disabled={action.busy}>Anuluj</button><button className="budget-button-primary" disabled={!reserve||!entry||action.busy} onClick={()=>{if(reserve&&entry)void action.run(()=>reservesApi.move(reserve.id,{kind:'SPEND',amount:entry.amount,date:entry.date,notes:'Powiązano istniejącą płatność',existing_entry_id:entry.id,entry_version:entry.version,account_id:entry.account_id},reserve.version,requestId),'Płatność powiązana bez zmiany salda.',onClose);}}>Powiąż płatność</button></div>
  </ImportDialog>;
}

export default function BudgetPaymentMatches({data,reload}:{data:BudgetWorkspace;reload:()=>Promise<void>}){
  const [selected,setSelected]=useState<PaymentMatch|null>(null);
  const matches=data.planning?.payment_matches??[];
  if(!matches.length)return null;
  const bill=selected?.kind==='BILL'?data.bills.find(b=>b.id===selected.id):null;
  return <section className="budget-panel surface-card bp-panel"><details><summary><strong>Płatności do powiązania ({matches.length})</strong></summary><p className="bp-help">Rachunki i rezerwy, dla których znaleziono istniejące wydatki. Powiązanie nie tworzy nowej płatności.</p><ul className="bp-closing-list">{matches.map(m=><li key={`${m.kind}-${m.id}`}><span>{m.title} · {m.kind==='BILL'?'Rachunek':'Rezerwa'}<small>{m.candidates.length} podobnych transakcji</small></span><button className="budget-button-secondary" onClick={()=>setSelected(m)}>Sprawdź dopasowanie</button></li>)}</ul></details>{selected?.kind==='RESERVE'&&<ReserveMatch match={selected} reload={reload} onClose={()=>setSelected(null)}/>} {bill&&<BillPayment data={data} bill={bill} reload={reload} onClose={()=>setSelected(null)}/>}</section>;
}
