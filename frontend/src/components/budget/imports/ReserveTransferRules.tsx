import {useBudgetFormGuard} from '../budgetMode';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRightLeft, CirclePlus, Pencil } from 'lucide-react';
import { budgetImportsApi, type BudgetImportsWorkspace, type ReserveTransferRule } from '../../../api_budget_imports';
import { extractErrorMessageFromUnknown } from '../../../http/response';
import { ImportDialog } from './ImportUi';

export default function ReserveTransferRules({workspace,onSaved}:{workspace:BudgetImportsWorkspace;onSaved:(message:string)=>void}){
  const [editor,setEditor]=useState<{rule:ReserveTransferRule|null}|null>(null);
  const rules=workspace.transfer_rules??[];
  const ready=workspace.accounts.length>1&&!!workspace.reserves?.length;
  return <section className="br-panel bi-rules">
    <div className="br-toolbar"><div><p className="page-eyebrow">Przelewy między własnymi kontami</p><h2>Stałe odłożenia na rezerwy</h2></div><button className="budget-button-primary" disabled={!ready} onClick={()=>setEditor({rule:null})}><CirclePlus size={16}/>Reguła przelewu na rezerwę</button></div>
    <p className="br-form-help">Przykład: opis zawiera „OC auta”, przelew PKO BP → Alior → rezerwa na ubezpieczenie. Kwota z wyciągu obciąży budżet miesiąca i zwiększy odłożone środki na Aliorze. Reguła rozpoznaje również wpływ na drugim koncie i proponuje powiązanie z tym samym przelewem.</p>
    {!ready&&<p className="br-form-help">Dodaj dwa własne <Link to="/budget/accounts">konta</Link> i <Link to="/budget/reserves">rezerwę</Link>, aby utworzyć regułę.</p>}
    <div className="bi-rule-list">{rules.map(rule=><article key={rule.id} className={!rule.active||!rule.reserve_active?'is-paused':''}><ArrowRightLeft size={20}/><div><strong>„{rule.pattern}” → {rule.reserve_name}</strong><p>{rule.source_name} → {rule.target_name}</p><small>{!rule.reserve_active?'Rezerwa rozliczona lub w archiwum':rule.active?'Aktywna':'Wstrzymana'} · Nowe odłożenie na koncie docelowym</small></div><button className="budget-button-secondary" onClick={()=>setEditor({rule})}><Pencil size={15}/>Edytuj przelew</button></article>)}</div>
    {editor&&<TransferRuleEditor key={editor.rule?.id??'new'} workspace={workspace} rule={editor.rule} onClose={()=>setEditor(null)} onSaved={()=>{setEditor(null);onSaved('Reguła przelewu zapisana. W przygotowanym imporcie odśwież reguły; każdy przelew sprawdzisz przed zatwierdzeniem.');}}/>}
  </section>;
}

function TransferRuleEditor({workspace,rule,onClose:close,onSaved}:{workspace:BudgetImportsWorkspace;rule:ReserveTransferRule|null;onClose:()=>void;onSaved:()=>void}){
  const [pattern,setPattern]=useState(rule?.pattern??'');
  const [source,setSource]=useState(String(rule?.source_account_id??workspace.accounts[0]?.id??''));
  const [target,setTarget]=useState(String(rule?.target_account_id??workspace.accounts.find(a=>a.id!==Number(source))?.id??''));
  const [reserve,setReserve]=useState(String(rule?.reserve_id??workspace.reserves?.[0]?.id??''));
  const [active,setActive]=useState(rule?.active??true),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [token]=useState(()=>crypto.randomUUID());
  const canClose=useBudgetFormGuard([pattern,source,target,reserve,active]);
  const onClose=()=>{if(canClose())close();};
  const save=async(e:React.FormEvent)=>{
    e.preventDefault();setBusy(true);setError('');
    try{
      const input={pattern:pattern.trim(),source_account_id:Number(source),target_account_id:Number(target),reserve_id:Number(reserve),active};
      if(rule)await budgetImportsApi.updateTransferRule(rule.id,input,rule.version);else await budgetImportsApi.saveTransferRule(input,token);
      onSaved();
    }catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}
  };
  return <ImportDialog title={rule?'Edytuj regułę przelewu':'Przelew i odłożenie na rezerwę'} busy={busy} onClose={onClose}>
    {error&&<p className="br-warning" role="alert">{error}</p>}
    <form onSubmit={save}><fieldset disabled={busy}>
      <label>Cel w opisie przelewu<input required maxLength={120} placeholder="np. OC auta" value={pattern} onChange={e=>setPattern(e.target.value)}/></label>
      <p className="br-form-help">Używaj osobnego, jednoznacznego opisu dla każdego celu, np. „rezerwa OC auta”. Sam BLIK nie określa celu. Reguła szuka całej frazy w opisie, bez rozróżniania wielkości liter i polskich znaków.</p>
      <div className="budget-form-grid"><label>Własne konto źródłowe<select required value={source} onChange={e=>{setSource(e.target.value);if(e.target.value===target)setTarget(String(workspace.accounts.find(a=>String(a.id)!==e.target.value)?.id??''));}}>{workspace.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label><label>Własne konto docelowe<select required value={target} onChange={e=>setTarget(e.target.value)}>{workspace.accounts.filter(a=>String(a.id)!==source).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label></div>
      <label>Rezerwa do zasilenia<select required value={reserve} onChange={e=>setReserve(e.target.value)}>{rule&&!workspace.reserves?.some(r=>r.id===rule.reserve_id)&&<option value={rule.reserve_id}>{rule.reserve_name} (nieaktywna)</option>}{(workspace.reserves??[]).map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
      <label className="bi-check"><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>Reguła przelewu aktywna</label>
      <div className="budget-form-actions"><button className="budget-button-quiet" type="button" onClick={onClose}>Anuluj</button><button className="budget-button-primary" type="submit">{busy?'Zapisywanie…':'Zapisz regułę przelewu'}</button></div>
    </fieldset></form>
  </ImportDialog>;
}
