import {useEffect,useState} from 'react';
import {budgetWorkspaceApi,type SettlementPreview} from '../../api_budget_workspace';
import {extractErrorMessageFromUnknown} from '../../http/response';
import {ImportDialog} from './imports/ImportUi';
import {planningMoney as money} from './planningHelpers';

export default function BudgetSettlementUndo({entryId,reload,onClose}:{entryId:number;reload:()=>Promise<void>;onClose:()=>void}){
  const [preview,setPreview]=useState<SettlementPreview|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [requestId]=useState(()=>crypto.randomUUID());
  useEffect(()=>{let active=true;budgetWorkspaceApi.settlementPreview(entryId).then(p=>{if(active)setPreview(p);}).catch(e=>{if(active)setError(extractErrorMessageFromUnknown(e));});return()=>{active=false;};},[entryId]);
  const submit=async()=>{if(!preview)return;setBusy(true);setError('');try{await budgetWorkspaceApi.reverseSettlement(entryId,preview,requestId);onClose();await reload();}catch(e){setError(extractErrorMessageFromUnknown(e));}finally{setBusy(false);}};
  return <ImportDialog title="Cofnij rozliczenie" busy={busy} onClose={onClose}>
    {error&&<p role="alert" className="budget-feedback is-error">{error}</p>}
    {!preview&&!error&&<p role="status">Przygotowuję podgląd…</p>}
    {preview&&<><p>{preview.message}</p><div className="bp-balance-preview">{preview.account_name}: <b>{money(preview.balance_before)} → {money(preview.balance_after)}</b><small>Przywrócone do rezerwy: {money(preview.restored_reserve)}</small></div><p className="bp-help">Rachunek wróci do nierozliczonych. Cofnięcie zachowamy w historii korekt.</p></>}
    <div className="budget-form-actions"><button className="budget-button-quiet" disabled={busy} onClick={onClose}>Anuluj</button><button className="budget-button-primary" disabled={!preview||busy} onClick={()=>void submit()}>Potwierdź cofnięcie</button></div>
  </ImportDialog>;
}
