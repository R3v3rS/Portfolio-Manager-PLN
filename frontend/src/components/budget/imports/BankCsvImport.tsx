import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, FileUp, RefreshCw, WandSparkles } from 'lucide-react';
import { budgetImportsApi, type BankImportRow, type BankImportSession, type BalanceMode, type BudgetImportsWorkspace, type CsvField, type CsvMapping, type CsvPreview } from '../../../api_budget_imports';
import { extractErrorMessageFromUnknown } from '../../../http/response';
import { importDay, importMoney } from './importFormat';

const mappingNames:Record<CsvField,string>={date:'Data księgowania',amount:'Kwota ze znakiem',description:'Opis operacji',merchant:'Odbiorca / sklep',currency:'Waluta',reference:'ID operacji bankowej',debit:'Obciążenie (osobna kolumna)',credit:'Uznanie (osobna kolumna)'};
export default function BankCsvImport({workspace,sessionId,onSession,onSaved,onRule}:{workspace:BudgetImportsWorkspace;sessionId:number|null;onSession:(id:number|null)=>void;onSaved:(notice:string)=>void;onRule:(pattern:string,categoryId?:number)=>void}){
  const [file,setFile]=useState<File|null>(null),[preview,setPreview]=useState<CsvPreview|null>(null),[mapping,setMapping]=useState<CsvMapping|null>(null);
  const [account,setAccount]=useState(String(workspace.accounts[0]?.id??'')),[mode,setMode]=useState<BalanceMode>('HISTORY');
  const [session,setSession]=useState<BankImportSession|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[limit,setLimit]=useState(100);
  const stageToken=useRef(crypto.randomUUID()),commitToken=useRef(crypto.randomUUID()),loadVersion=useRef(0);
  const loadSession=useCallback(async(id:number)=>{const version=++loadVersion.current;setBusy(true);setError('');try{const result=await budgetImportsApi.session(id);if(version===loadVersion.current)setSession(result);}catch(err){if(version===loadVersion.current)setError(extractErrorMessageFromUnknown(err));}finally{if(version===loadVersion.current)setBusy(false);}},[]);
  useEffect(()=>{if(sessionId){commitToken.current=crypto.randomUUID();void loadSession(sessionId);}else setSession(null);return()=>{loadVersion.current+=1;};},[sessionId,loadSession]);
  const chooseFile=async(next:File|null)=>{
    setFile(next);setPreview(null);setMapping(null);setError('');stageToken.current=crypto.randomUUID();
    if(!next)return;setBusy(true);
    try{const result=await budgetImportsApi.preview(next);setPreview(result);setMapping(result.mapping);}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const stage=async(e:React.FormEvent)=>{
    e.preventDefault();if(!file||!preview||!mapping)return;setBusy(true);setError('');
    try{const result=await budgetImportsApi.stage(file,{account_id:Number(account),balance_mode:mode,mapping,header_index:preview.header_index},stageToken.current);onSession(result.id);}
    catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}
  };
  const edit=async(row:BankImportRow,change:Parameters<typeof budgetImportsApi.updateRow>[2])=>{
    if(!session)return;setBusy(true);setError('');
    try{await budgetImportsApi.updateRow(session.id,row.id,change);const next=await budgetImportsApi.session(session.id);setSession(next);}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const refresh=async()=>{
    if(!session)return;setBusy(true);setError('');
    try{await budgetImportsApi.refresh(session.id,session.version);setSession(await budgetImportsApi.session(session.id));}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const commit=async()=>{
    if(!session)return;setBusy(true);setError('');
    try{const result=await budgetImportsApi.commit(session.id,session.version,commitToken.current);
      setSession({...session,status:'COMMITTED',result,version:session.version+1});
      onSaved(`Import zakończony. Nowe wpisy: ${result.created}, połączenia: ${result.linked}, przelewy własne: ${result.transfers}, pominięte: ${result.skipped}.`);
    }catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const selected=session?.rows.filter(r=>r.action!=='SKIP')??[];
  const invalid=selected.some(r=>r.errors.length||r.source_exists||(r.action==='MATCH'?(r.kind==='TRANSFER'?!r.transfer_id:!r.entry_id):r.kind==='TRANSFER'&&!r.target_account_id));
  return <section className="br-panel bi-csv">
    <div className="br-toolbar"><div><p className="page-eyebrow">Wyciąg z banku</p><h2>Import CSV</h2></div>{session&&<button type="button" className="budget-button-secondary" disabled={busy} onClick={()=>{onSession(null);setSession(null);setBusy(false);stageToken.current=crypto.randomUUID();}}>Wybierz kolejny plik</button>}</div>
    {error&&<div className="br-warning" role="alert">{error}{session&&<button className="budget-text-button" disabled={busy} onClick={()=>void loadSession(session.id)}>Odśwież podgląd</button>}</div>}
    {!session?<form onSubmit={stage} className="bi-upload-form"><fieldset disabled={busy}>
      <div className="budget-form-grid"><label>Konto z wyciągu<select required value={account} onChange={e=>{setAccount(e.target.value);stageToken.current=crypto.randomUUID();}}><option value="">Wybierz konto</option>{workspace.accounts.map(a=><option key={a.id} value={a.id}>{a.name} · {importMoney(a.balance)}</option>)}</select></label>
      <label>Wpływ importu na saldo<select value={mode} onChange={e=>{setMode(e.target.value as BalanceMode);stageToken.current=crypto.randomUUID();}}><option value="HISTORY">Historia — saldo już obejmuje te operacje</option><option value="APPLY">Nowe operacje — zaktualizuj saldo</option></select></label></div>
      <p className="br-form-help">{mode==='HISTORY'?'Zakupy uzupełnią historię i wydatki kategorii. Obecne saldo konta pozostanie bez zmian. Wybierz tę opcję, jeśli wpisano już aktualne saldo z banku.':'Nowe, niepowiązane wpisy zmienią saldo. Użyj tego trybu, gdy zapisane saldo nie obejmuje jeszcze operacji z wyciągu.'} Połączenia z istniejącymi wpisami nie obciążają konta drugi raz.</p>
      <label className="bi-file"><FileUp size={24}/><strong>{file?.name??'Wybierz bankowy plik CSV'}</strong><span>Do 8 MB i 3000 operacji. Odbiorca, opis, data i kwota z wyciągu.</span><input aria-label="Bankowy plik CSV" type="file" accept=".csv,text/csv" onChange={e=>void chooseFile(e.target.files?.[0]??null)}/></label>
      {preview&&mapping&&<><div className="bi-preview-meta"><b>{preview.count} operacji</b><span>{preview.encoding}</span>{preview.remembered&&<span>Zapamiętany układ kolumn</span>}</div>
      <div className="bi-mapping">{(Object.keys(mappingNames) as CsvField[]).map(key=><label key={key}>{mappingNames[key]}<select value={mapping[key]??''} onChange={e=>{setMapping({...mapping,[key]:e.target.value});stageToken.current=crypto.randomUUID();}}><option value="">Nie ma / pomiń</option>{preview.columns.map((name,i)=><option key={i} value={i}>{name}</option>)}</select></label>)}</div>
      <p className="br-form-help">Wskaż datę oraz kwotę ze znakiem albo osobne kolumny uznania i obciążenia. Używaj kwoty zaksięgowanej w PLN. Układ zapamiętamy przy przygotowaniu importu.</p>
      <details className="bi-preview"><summary>Przykładowe wiersze pliku</summary><div className="bi-table-wrap"><table><thead><tr>{preview.columns.map((c,i)=><th key={i}>{c}</th>)}</tr></thead><tbody>{preview.sample.map((row,i)=><tr key={i}>{row.map((c,j)=><td key={j}>{c}</td>)}</tr>)}</tbody></table></div></details>
      <button className="budget-button-primary" type="submit" disabled={!account||busy}>Przygotuj do sprawdzenia</button></>}
      {busy&&<p role="status" className="br-form-help">Przygotowywanie podglądu…</p>}
    </fieldset></form>:session.status==='COMMITTED'?<div className="bi-completed"><Check size={28}/><div><h3>Import zapisany</h3><p>{session.filename} · {session.account_name}</p><p>Nowe wpisy: {session.result?.created??0} · Połączenia: {session.result?.linked??0} · Przelewy: {session.result?.transfers??0} · Pominięte: {session.result?.skipped??0}</p><p>Tryb: {session.balance_mode==='HISTORY'?'historia bez zmiany salda':'aktualizacja salda'}. Kategorię nieprzypisanych zakupów uzupełnisz w zakładce „Do przypisania”.</p>{!!session.result?.bill_matches?.length&&<div className="bp-warning"><strong>Znaleziono płatności pasujące do rachunków</strong><p>Powiąż je z planem — nie zapisuj nowej płatności.</p>{session.result.bill_matches.map(match=><p key={`${match.bill_id}-${match.month}`}><Link className="budget-text-button" to={`/budget?view=bills&month=${match.month}&bill=${match.bill_id}`}>Powiąż: {match.title} · {match.month}</Link></p>)}</div>}</div></div>:<>
      <div className="bi-review-title"><strong>{session.filename}</strong><span>{session.account_name} · {session.rows.length} operacji</span><button className="budget-button-secondary" disabled={busy} onClick={()=>void refresh()}><RefreshCw size={15}/>Odśwież saldo i zastosuj reguły</button></div>
      <div className="bi-balance-preview"><div><span>Obecne saldo</span><b>{importMoney(session.opening_balance)}</b></div><div><span>Zmiana po zatwierdzeniu</span><b>{importMoney(session.cash_delta)}</b></div><div><span>Przewidywane saldo</span><b>{importMoney(session.closing_balance)}</b></div></div>
      <p className="br-form-help">{session.balance_mode==='HISTORY'?'Import historii: saldo bez zmian.':'Import nowych operacji: saldo zmienią tylko nowe wpisy i przelewy.'} Kategorie z reguł możesz poprawić. Brak kategorii pozostawia zapisany zakup do przypisania. Połączenie zachowuje podział istniejącego wpisu.</p>
      {session.balance_mode==='APPLY'&&session.expected_balance!==session.opening_balance&&<p className="br-warning">Saldo zmieniło się od przygotowania importu. Odśwież saldo i sprawdź podsumowanie przed zatwierdzeniem.</p>}
      <div className="bi-table-wrap"><table className="bi-bank-table"><thead><tr><th>Operacja</th><th>Kwota</th><th>Kategoria / przelew</th><th>Co zrobić</th></tr></thead><tbody>{session.rows.slice(0,limit).map(row=><tr key={row.id} className={row.action==='SKIP'?'is-skipped':''}>
        <td><strong>{row.merchant||row.description}</strong><small>{importDay(row.date)} · {row.description}</small>{row.errors.map(w=><small className="bi-error" key={w}>{w}</small>)}{row.warnings.map(w=><small className="bi-warning-text" key={w}>{w}</small>)}</td>
        <td className={row.bank_kind==='INCOME'?'bi-positive':''}>{row.bank_kind==='INCOME'?'+':'−'}{importMoney(row.amount)}</td>
        <td><label><span className="sr-only">Rodzaj operacji {row.row_number}</span><select value={row.kind} disabled={busy||row.source_exists} onChange={e=>void edit(row,{version:session.version,kind:e.target.value as BankImportRow['kind']})}><option value={row.bank_kind}>{row.bank_kind==='EXPENSE'?'Wydatek':'Dochód'}</option><option value="TRANSFER">Przelew własny</option></select></label>
        {row.kind==='EXPENSE'&&<label><span className="sr-only">Kategoria operacji {row.row_number}</span><select disabled={busy||row.action!=='NEW'} value={row.category_id??''} onChange={e=>void edit(row,{version:session.version,category_id:e.target.value?Number(e.target.value):null})}><option value="">Do przypisania</option>{workspace.categories.map(c=><option key={c.id} value={c.id}>{c.selection_label ?? c.name}</option>)}</select></label>}
        {row.kind==='TRANSFER'&&row.action==='NEW'&&<label><span className="sr-only">Drugie konto operacji {row.row_number}</span><select disabled={busy} value={row.target_account_id??''} onChange={e=>void edit(row,{version:session.version,target_account_id:e.target.value?Number(e.target.value):null})}><option value="">Wybierz drugie konto</option>{workspace.accounts.filter(a=>a.id!==session.account_id).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>}
        {row.kind==='TRANSFER'&&row.action==='NEW'&&<><label><span className="sr-only">Rezerwa operacji {row.row_number}</span><select disabled={busy} value={row.reserve_id??''} onChange={e=>void edit(row,{version:session.version,reserve_id:e.target.value?Number(e.target.value):null})}><option value="">Zwykły przelew — bez nowego odłożenia</option>{(workspace.reserves??[]).map(r=><option key={r.id} value={r.id}>Odłóż na: {r.name}</option>)}</select></label>{row.reserve_id&&<small>+{importMoney(row.amount)} na rezerwę na koncie docelowym · koszt {row.date.slice(0,7)}</small>}</>}
        {row.transfer_rule_name&&<small>Reguła przelewu: {row.transfer_rule_name}</small>}
        {row.rule_name&&<small>Reguła: {row.rule_name}</small>}{row.kind==='EXPENSE'&&row.category_id&&<button className="budget-text-button" disabled={busy} onClick={()=>onRule(row.merchant||row.description,row.category_id!)}><WandSparkles size={13}/>Zapamiętaj regułę</button>}</td>
        <td><label><span className="sr-only">Decyzja dla operacji {row.row_number}</span><select disabled={busy} value={row.action} onChange={e=>void edit(row,{version:session.version,action:e.target.value as BankImportRow['action']})}><option value="NEW" disabled={row.source_exists||!!row.errors.length}>Zapisz nowy wpis</option><option value="MATCH" disabled={row.source_exists||!(row.kind==='TRANSFER'?row.transfer_candidates.length:row.candidates.length)}>Połącz z istniejącym</option><option value="SKIP">Pomiń</option></select></label>
        {row.action==='MATCH'&&<label><span className="sr-only">Powiązanie operacji {row.row_number}</span><select disabled={busy} value={row.kind==='TRANSFER'?row.transfer_id??'':row.entry_id??''} onChange={e=>{if(e.target.value)void edit(row,{version:session.version,...(row.kind==='TRANSFER'?{transfer_id:Number(e.target.value)}:{entry_id:Number(e.target.value)})});}}><option value="">Wybierz zapis</option>{row.kind==='TRANSFER'?row.transfer_candidates.map(t=><option key={t.id} value={t.id}>{t.source_name} → {t.target_name} · {importDay(t.date)}</option>):row.candidates.map(c=><option key={c.id} value={c.id}>{c.description} · {importDay(c.date)} · #{c.id}</option>)}</select></label>}</td>
      </tr>)}</tbody></table></div>
      {session.rows.length>limit&&<button className="budget-button-secondary" disabled={busy} onClick={()=>setLimit(limit+100)}>Pokaż kolejne operacje ({session.rows.length-limit})</button>}
      <div className="bi-commit"><p>{selected.length} operacji do zapisu lub połączenia · {session.rows.length-selected.length} pominiętych.{selected.some(r=>r.kind==='TRANSFER'&&r.action==='NEW'&&r.reserve_id)&&<span> Odłożenia na rezerwy: {importMoney(selected.filter(r=>r.kind==='TRANSFER'&&r.action==='NEW'&&r.reserve_id).reduce((n,r)=>n+r.amount,0))}. Środki zostaną przypisane na kontach docelowych.</span>}{invalid&&<span className="bi-error"> Sprawdź błędne wiersze i brakujące powiązania.</span>}</p><button className="budget-button-primary" disabled={busy||invalid} onClick={()=>void commit()}><Check size={16}/>{busy?'Zapisywanie…':'Zatwierdź import'}</button></div>
    </>}
  </section>;
}
