import { useState } from 'react';
import { budgetImportsApi } from '../../api_budget_imports';
import { extractErrorMessageFromUnknown } from '../../http/response';
import { ImportDialog } from './imports/ImportUi';

export interface RuleSuggestion {pattern:string;categoryId:number;categoryName:string;accountId:number;merchant:boolean}
export default function BudgetRuleSuggestion({suggestion,onClose}:{suggestion:RuleSuggestion;onClose:()=>void}) {
  const [editing,setEditing]=useState(false),[pattern,setPattern]=useState(suggestion.pattern),[allAccounts,setAllAccounts]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[requestId]=useState(()=>crypto.randomUUID());
  return <div className="bp-warning" role="status">
    Czy kolejne płatności „{suggestion.pattern}” przypisywać do {suggestion.categoryName}?
    <button className="budget-text-button" onClick={()=>setEditing(true)}>Tak, utwórz regułę</button><button className="budget-text-button" onClick={onClose}>Pomiń</button>
    {editing&&<ImportDialog title="Zapamiętaj kategorię kolejnych płatności" busy={busy} onClose={()=>setEditing(false)}>
      {error&&<p role="alert">{error}</p>}<form className="bp-editor" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{await budgetImportsApi.saveRule({pattern:pattern.trim(),category_id:suggestion.categoryId,match_field:suggestion.merchant?'MERCHANT':'DESCRIPTION',match_type:suggestion.merchant?'EQUALS':'CONTAINS',account_id:allAccounts?null:suggestion.accountId,priority:100,active:true},requestId);onClose();}catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}}}>
        <label>{suggestion.merchant?'Dokładna nazwa odbiorcy':'Tekst w opisie'}<input required minLength={2} maxLength={150} value={pattern} onChange={e=>setPattern(e.target.value)}/></label>
        <p>Kategoria: <b>{suggestion.categoryName}</b>. Reguła dotyczy kolejnych importów i nie zmieni wcześniejszych zakupów.</p>
        <label className="bp-checkbox"><input type="checkbox" checked={allAccounts} onChange={e=>setAllAccounts(e.target.checked)}/>Stosuj na wszystkich kontach</label>
        <button className="budget-button-primary" type="submit" disabled={busy}>Zapisz regułę</button>
      </form>
    </ImportDialog>}
  </div>;
}
