import {useEffect,useState} from 'react';
import {reservesApi,type ReservesWorkspace,type ReserveFundingPlan,type ReserveBatchRow,type ReserveBatchPreview} from '../../api_reserves';
import {extractErrorMessageFromUnknown} from '../../http/response';
import {ImportDialog} from './imports/ImportUi';
import {planningMoney as money} from './planningHelpers';
import {ReserveAccountEffects} from './ReserveActivity';

export default function ReserveBatchFunding({data,onClose,onSaved}:{data:ReservesWorkspace;onClose:()=>void;onSaved:(message:string)=>void}){
  const [plan,setPlan]=useState<ReserveFundingPlan|null>(null),[rows,setRows]=useState<ReserveBatchRow[]>([]);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[preview,setPreview]=useState<ReserveBatchPreview|null>(null);
  const [requestId]=useState(()=>crypto.randomUUID());
  useEffect(()=>{let active=true;void reservesApi.fundingPlan().then(p=>{if(active){setPlan(p);setRows(p.rows.map(r=>({reserve_id:r.reserve_id,account_id:r.account_id,version:r.version,amount:r.proposed})));}}).catch(e=>{if(active)setError(extractErrorMessageFromUnknown(e));});return()=>{active=false;};},[]);
  const update=(id:number,change:Partial<ReserveBatchRow>)=>{setRows(old=>old.map(r=>r.reserve_id===id?{...r,...change}:r));setPreview(null);};
  const chosen=rows.filter(r=>r.amount>0),total=chosen.reduce((s,r)=>s+r.amount,0);
  const submit=async(e:React.FormEvent)=>{e.preventDefault();if(!plan)return;setBusy(true);setError('');try{
    const input={date:plan.date,rows:chosen};
    if(!preview){setPreview(await reservesApi.fundingPreview(input));setBusy(false);return;}
    const result=await reservesApi.fundBatch({...input,expected_state:preview.expected_state},requestId);
    onSaved(`Odłożono łącznie ${money(result.total)} na ${chosen.length} rezerw. Salda kont nie zmieniły się.`);
  }catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}};
  return <ImportDialog title="Odłóż na kilka rezerw" busy={busy} onClose={onClose}>
    <p className="br-form-help">Propozycja pokrywa brakujący plan tego miesiąca według ważności, osobno dla każdego konta. Nie wykonuje przelewów bankowych. Najpierw sprawdź, ile możesz wydzielić także po pozostałych rachunkach i limitach.</p>
    {error&&<p className="br-warning" role="alert">{error}</p>}{!plan&&!error&&<p role="status">Przygotowuję propozycję…</p>}
    {plan&&<form onSubmit={e=>void submit(e)}><fieldset disabled={busy} className="br-batch-fields">
      {!rows.length&&<p>Nie ma brakujących odłożeń w tym miesiącu.</p>}
      {rows.map(r=>{const p=plan.rows.find(p=>p.reserve_id===r.reserve_id)!;return <div className="br-batch-row" key={r.reserve_id}><div><strong>{p.name}</strong><small>Brakuje {money(p.remaining)} · ważność {p.priority===1?'wysoka':p.priority===3?'niska':'zwykła'}</small></div><label>Konto: {p.name}<select value={r.account_id} onChange={e=>update(r.reserve_id,{account_id:Number(e.target.value)})}>{data.accounts.map(a=><option key={a.id} value={a.id}>{a.name} · poza rezerwami {money(a.available)}</option>)}</select></label><label>Odłożenie: {p.name}<input type="number" required min="0" max="999999999.99" step="0.01" value={r.amount} onChange={e=>update(r.reserve_id,{amount:Number(e.target.value)})}/></label>{r.amount<p.remaining&&<small className="br-batch-shortfall">Plan niepokryty w całości: {money(p.remaining-r.amount)}</small>}</div>;})}
      <p>Wybrane odłożenia: <strong>{money(total)}</strong> · data {plan.date}</p>
      {preview&&<section className="br-preview" aria-label="Podgląd zbiorczego odkładania"><h3>Sprawdź przed zatwierdzeniem</h3><ReserveAccountEffects accounts={preview.accounts}/><p>Powstanie {chosen.length} odłożeń. Nie powstaną wydatki ani przelewy; pieniądze zostaną wydzielone na kontach.</p><button type="button" className="budget-text-button" onClick={()=>setPreview(null)}>Odśwież podgląd</button></section>}
      <div className="budget-form-actions"><button type="button" className="budget-button-quiet" onClick={onClose}>Anuluj</button><button type="submit" className="budget-button-primary" disabled={busy||!chosen.length}>{busy?'Zapisywanie…':preview?'Zatwierdź odłożenia':'Sprawdź podgląd'}</button></div>
    </fieldset></form>}
  </ImportDialog>;
}
