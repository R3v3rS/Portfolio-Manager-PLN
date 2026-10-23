import {useBudgetMode} from '../budgetMode';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Camera, Check, Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import { budgetImportsApi, type BalanceMode, type BudgetImportsWorkspace, type ExpenseCandidate, type ReceiptCommit, type ReceiptDraft, type ReceiptLine } from '../../../api_budget_imports';
import { extractErrorMessageFromUnknown } from '../../../http/response';
import { importDay, importMoney, importToday } from './importFormat';

type LineDraft={label:string;amount:string;category_id:string};
export default function ReceiptImport({workspace,draftId,onDraft,onSaved,onDeleted}:{workspace:BudgetImportsWorkspace;draftId:number|null;onDraft:(id:number|null)=>void;onSaved:(message:string)=>void;onDeleted:(id:number)=>void}){
  const {management}=useBudgetMode();
  const [draft,setDraft]=useState<ReceiptDraft|null>(null),[account,setAccount]=useState(String(workspace.selected_entry?.account_id??workspace.accounts[0]?.id??''));
  const [amount,setAmount]=useState(''),[day,setDay]=useState(importToday()),[merchant,setMerchant]=useState(''),[text,setText]=useState('');
  const [mode,setMode]=useState<ReceiptCommit['classification_mode']>('KEEP'),[balanceMode,setBalanceMode]=useState<BalanceMode|''>('');
  const [category,setCategory]=useState(''),[lines,setLines]=useState<LineDraft[]>([]),[candidates,setCandidates]=useState<ExpenseCandidate[]>([]),[target,setTarget]=useState('');
  const [separate,setSeparate]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const uploadToken=useRef(crypto.randomUUID()),commitToken=useRef(crypto.randomUUID()),loadVersion=useRef(0);
  const uploadFileKey=useRef('');
  const initialize=useCallback((next:ReceiptDraft)=>{
    const known=workspace.selected_entry;
    setDraft(next);setAmount(String(next.data.amount??known?.amount??''));setDay(next.data.date||known?.date||'');
    setMerchant(next.data.merchant||known?.merchant||known?.description||'');setText(next.raw_text);
    setAccount(String(known?.account_id??next.account_id??workspace.accounts[0]?.id??''));
    const found=known?[known,...next.candidates.filter(c=>c.id!==known.id)]:next.candidates;
    setCandidates(found);
    const strong=next.candidates.filter(c=>c.merchant_match);
    const preferred=known??(strong.length===1?strong[0]:null);
    setTarget(preferred?String(preferred.id):'');
    const proposed=next.data.category_id??(preferred?.lines.length===1?preferred.lines[0].category_id:null);
    const common=workspace.categories.some(c=>c.id===proposed)?proposed:null;
    setCategory(common?String(common):'');
    setLines(next.data.lines.map(l=>({label:l.label,amount:String(l.amount),category_id:String(workspace.categories.some(c=>c.id===l.category_id)?l.category_id:common??'')})));
    const complete=next.data.amount!==null&&next.data.lines.length>0&&next.data.lines.reduce((sum,line)=>sum+Math.round(line.amount*100),0)===Math.round(next.data.amount*100);
    setMode(complete?'SPLIT':'KEEP');setBalanceMode('');setSeparate(false);commitToken.current=crypto.randomUUID();
  },[workspace.selected_entry,workspace.accounts,workspace.categories]);
  const initializeRef=useRef(initialize);useEffect(()=>{initializeRef.current=initialize;},[initialize]);
  const load=useCallback(async(id:number)=>{const version=++loadVersion.current;setBusy(true);setError('');try{const result=await budgetImportsApi.receipt(id);if(version===loadVersion.current)initializeRef.current(result);}catch(err){if(version===loadVersion.current)setError(extractErrorMessageFromUnknown(err));}finally{if(version===loadVersion.current)setBusy(false);}},[]);
  useEffect(()=>{if(draftId)void load(draftId);else setDraft(null);return()=>{loadVersion.current+=1;};},[draftId,load]);
  const upload=async(file:File|null)=>{
    if(!file)return;setBusy(true);setError('');
    const key=`${file.name}:${file.size}:${file.lastModified}`;
    if(uploadFileKey.current!==key){uploadFileKey.current=key;uploadToken.current=crypto.randomUUID();}
    try{const result=await budgetImportsApi.uploadReceipt(file,account?Number(account):null,uploadToken.current);onDraft(result.id);}
    catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}
  };
  const find=async()=>{
    setBusy(true);setError('');
    try{const result=await budgetImportsApi.matches({account_id:account?Number(account):undefined,date:day,amount:Number(amount),merchant});setCandidates(result);setTarget('');const strong=result.filter(c=>c.merchant_match);if(strong.length===1){setTarget(String(strong[0].id));setAccount(String(strong[0].account_id));}}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const reparse=async()=>{
    if(!draft)return;setBusy(true);setError('');
    try{await budgetImportsApi.parseReceipt(draft.id,text,draft.version);initialize(await budgetImportsApi.receipt(draft.id));}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const remove=async()=>{
    if(!draft||busy)return;
    if(!window.confirm(`Usunąć paragon „${draft.filename}”? Zdjęcie i odczyt zostaną usunięte. Zapisany wydatek, jego kategorie i saldo konta pozostaną bez zmian.`))return;
    setBusy(true);setError('');
    try{
      await budgetImportsApi.deleteReceipt(draft.id,draft.version);
      onDeleted(draft.id);onDraft(null);setDraft(null);setText('');setLines([]);
      uploadFileKey.current='';uploadToken.current=crypto.randomUUID();
      onSaved('Paragon usunięty. Zapisane wydatki, kategorie i salda kont pozostają bez zmian.');
    }catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const recognizeAgain=async()=>{
    if(!draft||busy)return;
    if(!window.confirm('Odczytać zdjęcie ponownie? Nowy odczyt zastąpi dane w tym formularzu, w tym ręczne poprawki. Zapisane wydatki i salda pozostaną bez zmian.'))return;
    setBusy(true);setError('');
    try{await budgetImportsApi.recognizeReceipt(draft.id,draft.version);initialize(await budgetImportsApi.receipt(draft.id));}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const selected=candidates.find(c=>String(c.id)===target);
  const chooseTarget=(value:string)=>{
    setTarget(value);const entry=candidates.find(c=>String(c.id)===value);
    if(entry){setAccount(String(entry.account_id));if(entry.lines.length===1){const id=entry.lines[0].category_id;setCategory(workspace.categories.some(c=>c.id===id)?String(id):'');}}
  };
  const sum=lines.reduce((n,l)=>n+Math.round(Number(l.amount)*100),0)/100;
  const splitInvalid=mode==='SPLIT'&&(!lines.length||lines.some(l=>!l.category_id||!l.label.trim()||!Number.isFinite(Number(l.amount))||Number(l.amount)<=0)||Math.round(sum*100)!==Math.round(Number(amount)*100));
  const save=async(e:React.FormEvent)=>{
    e.preventDefault();if(!draft)return;if(!selected&&!balanceMode){setError('Wybierz, czy saldo konta już uwzględnia ten zakup.');return;}setBusy(true);setError('');
    const parsed:ReceiptLine[]=lines.map(l=>({label:l.label,amount:Number(l.amount),category_id:Number(l.category_id)}));
    const input:ReceiptCommit={action:selected?'MATCH':'NEW',account_id:Number(account),amount:Number(amount),date:day,merchant,
      ...(selected?{entry_id:selected.id,entry_version:selected.version}:{}),classification_mode:mode,
      ...(mode==='GENERAL'?{category_id:Number(category)}:{}),...(mode==='SPLIT'?{lines:parsed}:{}),balance_mode:balanceMode||'HISTORY',
      expected_balance:workspace.accounts.find(a=>a.id===Number(account))?.balance??0,confirm_separate:separate};
    try{const result=await budgetImportsApi.commitReceipt(draft.id,input,draft.version,commitToken.current);
      setDraft({...draft,status:'COMMITTED',entry_id:result.entry_id,version:draft.version+1});
      onSaved(result.linked?'Paragon połączony z istniejącym zakupem. Saldo konta pozostaje bez zmian.':`Wydatek z paragonem zapisany. ${balanceMode==='HISTORY'?'Saldo pozostaje bez zmian.':'Saldo konta zostało zaktualizowane.'}`);
    }catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  return <section className="br-panel bi-receipts"><div className="br-toolbar"><div><p className="page-eyebrow">Zdjęcie lub PDF</p><h2>Paragony i podział zakupów</h2></div>{draft&&<div className="br-actions">{draft.status==='PENDING'&&<button type="button" className="budget-button-secondary" disabled={busy||!workspace.ocr.available} onClick={()=>void recognizeAgain()}><RefreshCw size={16}/>{busy?'Przetwarzanie…':'Odczytaj ponownie'}</button>}{(management||draft.status==='PENDING')&&<button type="button" className="budget-button-secondary bi-delete-receipt" disabled={busy} onClick={()=>void remove()}><Trash2 size={16}/>Usuń paragon</button>}<button type="button" className="budget-button-secondary" disabled={busy} onClick={()=>{onDraft(null);setDraft(null);setBusy(false);uploadToken.current=crypto.randomUUID();}}>Dodaj kolejny paragon</button></div>}</div>
    {error&&<div className="br-warning" role="alert">{error}{draftId&&<button className="budget-text-button" disabled={busy} onClick={()=>void load(draftId)}>Odśwież paragon</button>}</div>}
    {!draft?<><p className="br-form-help">Rozpoznane dane najpierw sprawdzasz. Jeśli zakup już jest w budżecie, zdjęcie i podział uzupełnią istniejący wpis na jego koncie. Odczyt działa lokalnie na Windows; zdjęcia nie są wysyłane do zewnętrznej usługi.</p>
      {workspace.selected_entry&&<p className="br-warning">Dodajesz paragon do: {workspace.selected_entry.description} · {importMoney(workspace.selected_entry.amount)} · {workspace.selected_entry.account_name}.</p>}
      <label>Konto zakupu<select disabled={busy} value={account} onChange={e=>{setAccount(e.target.value);uploadToken.current=crypto.randomUUID();}}><option value="">Wyszukaj we wszystkich kontach</option>{workspace.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label className="bi-file"><Camera size={27}/><strong>Wybierz zdjęcie paragonu lub zrób zdjęcie</strong><span>JPG, PNG, WebP lub PDF do 8 MB. PDF do 3 stron.</span><input aria-label="Zdjęcie lub PDF paragonu" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" disabled={busy} onChange={e=>void upload(e.target.files?.[0]??null)}/></label>
      {busy&&<p role="status" className="br-form-help">Odczytywanie tekstu na tym komputerze…</p>}
      {!workspace.ocr.available&&<p className="br-warning">Odczyt OCR jest niedostępny na tym systemie. Zdjęcie można zachować, a dane wpisać ręcznie.</p>}
    </>:draft.status==='COMMITTED'?<div className="bi-completed"><Check size={28}/><div><h3>Paragon zapisany</h3><p>{draft.filename}</p><Link className="budget-text-button" to={`/budget?view=entries&month=${day.slice(0,7)}`}>Otwórz zakup w budżecie</Link></div></div>:<div className="bi-receipt-review">
      <aside className="bi-receipt-image">{draft.is_pdf?<a href={budgetImportsApi.receiptFile(draft.id)} target="_blank" rel="noreferrer">Otwórz oryginalny PDF</a>:<img src={budgetImportsApi.receiptFile(draft.id)} alt="Oryginał paragonu do porównania z odczytanymi danymi"/>}<p>{draft.filename}</p><details><summary>Popraw tekst odczytu</summary><textarea aria-label="Tekst odczytany z paragonu" value={text} disabled={busy} onChange={e=>setText(e.target.value)} maxLength={60000}/><button className="budget-button-secondary" disabled={busy} onClick={()=>void reparse()}>Rozpoznaj dane z tekstu</button></details></aside>
      <form onSubmit={save}><fieldset disabled={busy}>
        {draft.warnings.length>0&&<div className="br-warning"><ul>{draft.warnings.map(w=><li key={w}>{w}</li>)}</ul></div>}
        <div className="budget-form-grid"><label>Sklep / odbiorca<input maxLength={150} value={merchant} onChange={e=>setMerchant(e.target.value)} placeholder="np. LIDL"/></label><label>Data zakupu<input required type="date" min="2000-01-01" max={importToday()} value={day} onChange={e=>setDay(e.target.value)}/></label></div>
        <div className="budget-form-grid"><label>Kwota zakupu (PLN)<input required type="number" min="0.01" max="999999999.99" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)}/></label><label>Konto zakupu<select required value={account} onChange={e=>{setAccount(e.target.value);setTarget('');}}><option value="">Wybierz konto</option>{workspace.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label></div>
        <div className="bi-match"><div className="br-toolbar"><h3>Powiązanie z transakcją</h3><button type="button" className="budget-button-secondary" disabled={!amount||!day||busy} onClick={()=>void find()}><Search size={15}/>Znajdź zakup</button></div>
        <label>Do którego wpisu dołączyć paragon<select value={target} onChange={e=>chooseTarget(e.target.value)}><option value="">Nowy, odrębny wydatek</option>{candidates.map(c=><option key={c.id} value={c.id}>{c.description} · {importMoney(c.amount)} · {importDay(c.date)} · {c.account_name}</option>)}</select></label>
        {selected?<p className="br-form-help">Uzupełniasz istniejący zakup #{selected.id}. Konto, kwota i saldo pozostaną bez zmian. {selected.has_receipt&&'Zapis zastąpi aktualny załącznik.'}{Number(amount)!==selected.amount&&<strong className="bi-error"> Kwota musi odpowiadać zakupowi: {importMoney(selected.amount)}.</strong>}</p>:<>
          {candidates.length>0&&<label className="bi-check bi-warning-text"><input type="checkbox" checked={separate} onChange={e=>setSeparate(e.target.checked)}/>Potwierdzam, że to odrębny zakup mimo podobnych wpisów</label>}
          <label>Czy saldo konta już uwzględnia ten zakup?<select value={balanceMode} onChange={e=>setBalanceMode(e.target.value as BalanceMode)}><option value="">Wybierz sposób rozliczenia salda</option><option value="HISTORY">Tak — uzupełnij historię, saldo bez zmian</option><option value="APPLY">Nie — pomniejsz saldo konta</option></select></label></>}
        </div>
        {workspace.accounts.filter(a=>a.id===Number(account)).map(a=><div className="bp-balance-preview" key={a.id}>{a.name}: <b>{importMoney(a.balance)} → {importMoney(a.balance-(!selected&&balanceMode==='APPLY'?(Number(amount)||0):0))}</b><small>{selected?'Paragon uzupełnia istniejący zakup.':!balanceMode?'Wybierz powyżej, czy ten zakup ma pomniejszyć saldo.':balanceMode==='HISTORY'?'Zakup już zawiera się w saldzie — bez obciążenia.':'Nowy zakup pomniejszy saldo konta.'}</small>{a.account_type==='CREDIT_CARD'&&<small>Karta kredytowa: ujemne saldo oznacza zadłużenie. Wydatek dotyczy daty zakupu; spłata będzie osobnym przelewem.</small>}{!selected&&balanceMode==='APPLY'&&a.account_type!=='CREDIT_CARD'&&a.balance<Number(amount)&&<strong className="budget-negative">Na tym koncie brakuje {importMoney(Number(amount)-a.balance)}.</strong>}</div>)}
        <label>Jak przypisać wydatek<select value={mode} onChange={e=>setMode(e.target.value as ReceiptCommit['classification_mode'])}><option value="KEEP">{selected?'Zachowaj obecne kategorie':'Pozostaw do przypisania'}</option><option value="GENERAL">Cały zakup do jednej kategorii</option><option value="SPLIT">Podziel według pozycji</option></select></label>
        {mode!=='KEEP'&&<label>{mode==='GENERAL'?'Kategoria całego zakupu':'Wspólna kategoria pozycji'}<select required={mode==='GENERAL'} value={category} onChange={e=>setCategory(e.target.value)}><option value="">Wybierz kategorię</option>{workspace.categories.map(c=><option key={c.id} value={c.id}>{c.selection_label ?? c.name}</option>)}</select></label>}
        {mode==='SPLIT'&&<><button type="button" className="budget-text-button" disabled={!category||busy} onClick={()=>setLines(lines.map(l=>({...l,category_id:category})))}>Przypisz tę kategorię wszystkim pozycjom</button>
        <div className="bi-products">{lines.map((line,index)=><div key={index} className="bi-product"><label>Pozycja {index+1}<input required maxLength={120} value={line.label} onChange={e=>setLines(lines.map((l,i)=>i===index?{...l,label:e.target.value}:l))}/></label><label>Kategoria pozycji {index+1}<select required value={line.category_id} onChange={e=>setLines(lines.map((l,i)=>i===index?{...l,category_id:e.target.value}:l))}><option value="">Wybierz kategorię</option>{workspace.categories.map(c=><option key={c.id} value={c.id}>{c.selection_label ?? c.name}</option>)}</select></label><label>Kwota pozycji {index+1}<input required type="number" min="0.01" step="0.01" value={line.amount} onChange={e=>setLines(lines.map((l,i)=>i===index?{...l,amount:e.target.value}:l))}/></label><button type="button" className="budget-icon-button" aria-label={`Usuń pozycję ${index+1}`} onClick={()=>setLines(lines.filter((_,i)=>i!==index))}><Trash2 size={15}/></button></div>)}</div>
        <button type="button" className="budget-text-button" disabled={lines.length>=100} onClick={()=>setLines([...lines,{label:'',amount:'',category_id:category}])}><Plus size={15}/>Dodaj pozycję</button><p className={splitInvalid?'br-warning':'br-form-help'}>Suma pozycji: {importMoney(Number.isFinite(sum)?sum:0)} · Paragon: {importMoney(Number(amount)||0)}. Podział musi odpowiadać dokładnej kwocie zakupu.</p></>}
        <p className="br-form-help">Sprawdź nazwy, kwoty i rabaty przed zapisem. Możesz zachować paragon bez podziału lub przypisać cały zakup do Jedzenia. Dołączenie zdjęcia nie tworzy kolejnej płatności.</p>
        <button className="budget-button-primary" type="submit" disabled={busy||(!selected&&!balanceMode)||splitInvalid||(mode==='GENERAL'&&!category)||(!selected&&candidates.length>0&&!separate)||(!!selected&&Number(amount)!==selected.amount)}><Check size={16}/>{busy?'Zapisywanie…':selected?'Połącz paragon i zapisz podział':'Zapisz wydatek z paragonem'}</button>
      </fieldset></form>
    </div>}
  </section>;
}
