import {useBudgetFormGuard} from '../budgetMode';
import { useState } from 'react';
import { budgetImportsApi, type BudgetImportsWorkspace, type CategoryRule, type CategoryRuleInput } from '../../../api_budget_imports';
import { extractErrorMessageFromUnknown } from '../../../http/response';
import { ImportDialog } from './ImportUi';

export default function RuleEditor({workspace,rule,pattern='',categoryId,onClose:close,onSaved}:{workspace:BudgetImportsWorkspace;rule:CategoryRule|null;pattern?:string;categoryId?:number;onClose:()=>void;onSaved:()=>void}){
  const [name,setName]=useState(rule?.name??''),[text,setText]=useState(rule?.pattern??pattern);
  const [field,setField]=useState<CategoryRuleInput['match_field']>(rule?.match_field??'ANY');
  const [match,setMatch]=useState<CategoryRuleInput['match_type']>(rule?.match_type??'CONTAINS');
  const [category,setCategory]=useState(String(rule?.category_id??categoryId??workspace.categories[0]?.id??'NEW'));
  const [newCategory,setNewCategory]=useState(''),[account,setAccount]=useState(String(rule?.account_id??''));
  const [priority,setPriority]=useState(String(rule?.priority??100)),[active,setActive]=useState(rule?Boolean(rule.active):true);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[requestId]=useState(()=>crypto.randomUUID());
  const canClose=useBudgetFormGuard([name,text,field,match,category,newCategory,account,priority,active]);
  const onClose=()=>{if(canClose())close();};
  const save=async(e:React.FormEvent)=>{
    e.preventDefault();setBusy(true);setError('');
    const data:CategoryRuleInput={name:name.trim()||text.trim(),pattern:text.trim(),match_field:field,match_type:match,
      category_id:category==='NEW'?null:Number(category),...(category==='NEW'?{new_category:newCategory.trim()}:{}),
      account_id:account?Number(account):null,priority:Number(priority),active};
    try{if(rule)await budgetImportsApi.updateRule(rule.id,data,rule.version);else await budgetImportsApi.saveRule(data,requestId);onSaved();}
    catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}
  };
  return <ImportDialog title={rule?'Edytuj regułę kategorii':'Dodaj stałą regułę kategorii'} busy={busy} onClose={onClose}>
    <p className="br-form-help">Reguła przypisuje kategorię podczas kolejnych importów. Przykład: opis lub odbiorca zawiera ENEA → Prąd / media. Zapisane i ręcznie przypisane zakupy zachowują swoje kategorie.</p>
    {error&&<p className="br-warning" role="alert">{error}</p>}
    <form onSubmit={save}><fieldset disabled={busy}>
      <label>Nazwa reguły<input maxLength={150} placeholder="np. Rachunki za prąd" value={name} onChange={e=>setName(e.target.value)}/></label>
      <label>Tekst do dopasowania<input required minLength={2} maxLength={150} placeholder="np. ENEA, LIDL, ORLEN" value={text} onChange={e=>setText(e.target.value)}/></label>
      <div className="budget-form-grid"><label>Gdzie szukać<select value={field} onChange={e=>setField(e.target.value as CategoryRuleInput['match_field'])}><option value="ANY">Odbiorca lub opis</option><option value="MERCHANT">Odbiorca / sklep</option><option value="DESCRIPTION">Opis operacji</option></select></label>
      <label>Dopasowanie<select value={match} onChange={e=>setMatch(e.target.value as CategoryRuleInput['match_type'])}><option value="CONTAINS">Zawiera tekst</option><option value="EQUALS">Dokładnie taki tekst</option><option value="STARTS_WITH">Zaczyna się od tekstu</option></select></label></div>
      <label>Kategoria docelowa<select value={category} onChange={e=>setCategory(e.target.value)}>{workspace.categories.map(c=><option key={c.id} value={c.id}>{c.selection_label ?? c.name}</option>)}<option value="NEW">+ Utwórz kategorię główną</option></select></label>
      {category==='NEW'&&<label>Nazwa nowej kategorii<input required maxLength={100} placeholder="np. Prąd / media" value={newCategory} onChange={e=>setNewCategory(e.target.value)}/></label>}
      <div className="budget-form-grid"><label>Obowiązuje dla konta<select value={account} onChange={e=>setAccount(e.target.value)}><option value="">Wszystkie konta</option>{workspace.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label><label>Priorytet<input type="number" min="0" max="10000" step="1" required value={priority} onChange={e=>setPriority(e.target.value)}/></label></div>
      <p className="br-form-help">Wyższy priorytet wygrywa. Przy równym priorytecie wybieramy bardziej szczegółowy tekst. Sprzeczne reguły zostawiają zakup do sprawdzenia. Wielkość liter i polskie znaki nie wpływają na dopasowanie.</p>
      <label className="bi-check"><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>Reguła aktywna</label>
      <div className="budget-form-actions"><button type="button" className="budget-button-quiet" onClick={onClose}>Anuluj</button><button className="budget-button-primary" type="submit">{busy?'Zapisywanie…':'Zapisz regułę'}</button></div>
    </fieldset></form>
  </ImportDialog>;
}
