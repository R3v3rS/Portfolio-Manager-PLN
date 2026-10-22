import {useState} from 'react';
import {budgetWorkspaceApi,type BudgetWorkspace,type PlanCopyInput,type PlanCopyPreview} from '../../api_budget_workspace';
import {ImportDialog} from './imports/ImportUi';
import {planningToday,planningMoney as money} from './planningHelpers';
import {extractErrorMessageFromUnknown} from '../../http/response';

function nextMonth(month:string){const [y,m]=month.split('-').map(Number);return `${m===12?y+1:y}-${String(m===12?1:m+1).padStart(2,'0')}`;}
const actionLabels={ADD:'Dodaj limit',REPLACE:'Zastąp limit',KEEP:'Zachowaj wyjątek',MANAGED:'Miesięczna pula — pomiń',NO_SOURCE:'Brak limitu źródłowego — pomiń'};
export default function BudgetPlanCopy({data,reload,onClose}:{data:BudgetWorkspace;reload:()=>Promise<void>;onClose:()=>void}){
  const earliest=planningToday().slice(0,7);
  const [input,setInput]=useState<PlanCopyInput>({source:data.month,start:nextMonth(data.month)<earliest?earliest:nextMonth(data.month),months:12,replace:false,category_ids:data.categories.filter(c=>!c.is_unassigned&&!c.monthly_reserve_managed).map(c=>c.id)});
  const [preview,setPreview]=useState<PlanCopyPreview|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [requestId,setRequestId]=useState(()=>crypto.randomUUID());
  const update=(next:Partial<PlanCopyInput>)=>{setInput(old=>({...old,...next}));setPreview(null);setError('');setRequestId(crypto.randomUUID());};
  const check=async()=>{setBusy(true);setError('');try{setPreview(await budgetWorkspaceApi.previewCopy(input));setRequestId(crypto.randomUUID());}catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}};
  const save=async()=>{if(!preview)return;setBusy(true);setError('');try{await budgetWorkspaceApi.copyRange(input,preview.token,requestId);onClose();await reload();}catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}};
  return <ImportDialog title="Zastosuj limity na kolejne miesiące" busy={busy} onClose={onClose}>
    <p className="bp-help">Kopiujemy zapisane lub domyślne limity kategorii. Podgląd pokazuje własne limity; końcowy wspólny plan uwzględni także podkategorie i przypisane płatności. Rachunki, raty i odłożenia wynikają z własnych harmonogramów. Nie kopiujemy historii ani przeniesionych kwot z zamknięcia miesiąca.</p>
    {error&&<p role="alert" className="budget-negative">{error}</p>}
    <form className="bp-editor" onSubmit={e=>{e.preventDefault();void check();}}><fieldset disabled={busy}>
      <div className="budget-form-grid"><label>Miesiąc źródłowy<input required type="month" max="2100-12" value={input.source} onChange={e=>update({source:e.target.value})}/></label><label>Pierwszy miesiąc docelowy<input required type="month" min={earliest} max="2100-12" value={input.start} onChange={e=>update({start:e.target.value})}/></label></div>
      <label>Liczba miesięcy<select value={input.months} onChange={e=>update({months:Number(e.target.value)})}>{[3,6,12].map(n=><option key={n} value={n}>{n} {n===3?'miesiące':'miesięcy'}</option>)}</select></label>
      <label>Istniejące limity miesięczne<select value={input.replace?'REPLACE':'KEEP'} onChange={e=>update({replace:e.target.value==='REPLACE'})}><option value="KEEP">Zachowaj — uzupełnij tylko brakujące</option><option value="REPLACE">Zastąp w wybranych kategoriach</option></select></label>
      <details className="bp-details"><summary>Kategorie do skopiowania ({input.category_ids.length})</summary><div className="budget-copy-selection">{data.categories.filter(c=>!c.is_unassigned&&!c.monthly_reserve_managed).map(category=><label key={category.id} className="bp-checkbox"><input type="checkbox" checked={input.category_ids.includes(category.id)} onChange={e=>update({category_ids:e.target.checked?[...input.category_ids,category.id]:input.category_ids.filter(id=>id!==category.id)})}/>{category.path??category.name}</label>)}</div></details>
      <button className="budget-button-secondary" type="submit" disabled={!input.category_ids.length}>Pokaż podgląd</button>
    </fieldset></form>
    {preview&&<section className="budget-copy-preview" aria-label="Podgląd kopiowania"><p><strong>{preview.copied} limitów do zapisania</strong> · {preview.skipped} bez zmiany. Zakres: {preview.rows[0]?.month} – {preview.rows.at(-1)?.month}.</p><div className="cf-table-wrap"><table><thead><tr><th>Miesiąc / kategoria</th><th>Własny limit przed</th><th>Własny limit po</th><th>Decyzja</th></tr></thead><tbody>{preview.rows.map(row=><tr key={`${row.month}:${row.category_id}`}><td>{row.month}<small>{row.name}</small></td><td>{money(row.previous)}</td><td>{money(['ADD','REPLACE'].includes(row.action)?row.amount:row.previous)}</td><td>{actionLabels[row.action]}</td></tr>)}</tbody></table></div><div className="budget-form-actions"><button type="button" className="budget-button-quiet" onClick={onClose} disabled={busy}>Anuluj</button><button type="button" className="budget-button-primary" disabled={busy||!preview.copied} onClick={()=>void save()}>Zapisz pokazane limity</button></div></section>}
  </ImportDialog>;
}
