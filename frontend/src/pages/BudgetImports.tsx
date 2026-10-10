import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight, Camera, Check, CirclePlus, FileUp, History, ListChecks, Pencil, RefreshCw, ShieldCheck, WandSparkles } from 'lucide-react';
import { budgetImportsApi, type BudgetImportsWorkspace, type CategoryRule } from '../api_budget_imports';
import { extractErrorMessageFromUnknown } from '../http/response';
import BankCsvImport from '../components/budget/imports/BankCsvImport';
import ReceiptImport from '../components/budget/imports/ReceiptImport';
import RuleEditor from '../components/budget/imports/RuleEditor';
import ReserveTransferRules from '../components/budget/imports/ReserveTransferRules';
import { importDay, importMoney } from '../components/budget/imports/importFormat';
import '../components/budget/budgetWorkspace.css';
import '../components/budget/budgetReserves.css';
import '../components/budget/budgetImports.css';

import BudgetRuleSuggestion, { type RuleSuggestion } from '../components/budget/BudgetRuleSuggestion';
import '../components/budget/budgetPlanning.css';

type Tab='PENDING'|'CSV'|'RECEIPT'|'RULES'|'HISTORY';
type RuleDraft={rule:CategoryRule|null;pattern?:string;categoryId?:number};
const tabs:{id:Tab;name:string;icon:typeof Camera}[]=[{id:'PENDING',name:'Do przypisania',icon:ListChecks},{id:'CSV',name:'Import CSV',icon:FileUp},{id:'RECEIPT',name:'Paragony',icon:Camera},{id:'RULES',name:'Reguły kategorii i rezerw',icon:WandSparkles},{id:'HISTORY',name:'Historia importów',icon:History}];

export default function BudgetImports(){
  const [suggestion,setSuggestion]=useState<RuleSuggestion|null>(null);
  const [params]=useSearchParams();const requestedId=Number(params.get('entry_id'))||undefined;
  const [data,setData]=useState<BudgetImportsWorkspace|null>(null),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
  const [tab,setTab]=useState<Tab>(params.get('tab')==='receipt'||requestedId?'RECEIPT':'PENDING');
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[ruleEditor,setRuleEditor]=useState<RuleDraft|null>(null);
  const [sessionId,setSessionId]=useState<number|null>(null),[draftId,setDraftId]=useState<number|null>(null),[limit,setLimit]=useState(200);
  const [selected,setSelected]=useState<Set<number>>(new Set()),[category,setCategory]=useState(''),[rowCategories,setRowCategories]=useState<Record<number,string>>({});
  const mounted=useRef(true),version=useRef(0);
  const reload=useCallback(async()=>{const current=++version.current;setLoading(true);setError('');try{const next=await budgetImportsApi.get(requestedId,limit);if(mounted.current&&current===version.current)setData(next);}catch(err){if(mounted.current&&current===version.current)setError(extractErrorMessageFromUnknown(err));}finally{if(mounted.current&&current===version.current)setLoading(false);}},[requestedId,limit]);
  useEffect(()=>{mounted.current=true;void reload();return()=>{mounted.current=false;version.current+=1;};},[reload]);
  const saved=(message:string)=>{setNotice(message);void reload();};
  const receiptDeleted=(id:number)=>setData(before=>before?{...before,receipts:before.receipts.filter(r=>r.id!==id)}:before);
  const versionsFor=(ids:number[])=>Object.fromEntries(ids.map(id=>[String(id),data?.pending.find(e=>e.id===id)?.version??0]));
  const assign=async(ids:number[],categoryId:number)=>{
    setBusy(true);setError('');
    try{const entry=ids.length===1?data?.pending.find(e=>e.id===ids[0]):null;const target=data?.categories.find(c=>c.id===categoryId);await budgetImportsApi.categorize(ids,versionsFor(ids),categoryId);if(entry&&target)setSuggestion({pattern:entry.merchant||entry.description,categoryId,categoryName:target.selection_label??target.name,accountId:entry.account_id,merchant:!!entry.merchant});setSelected(new Set());setNotice(`Kategoria przypisana do ${ids.length} wydatków. Salda kont pozostają bez zmian.`);await reload();}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const applyRules=async()=>{
    if(!data?.pending.length)return;setBusy(true);setError('');
    const ids=(selected.size?[...selected]:data.pending.map(e=>e.id)).slice(0,500);
    try{const result=await budgetImportsApi.applyRules(ids,versionsFor(ids));setSelected(new Set());setNotice(`Reguły przypisały ${result.updated} wydatków. Do ręcznego sprawdzenia: ${result.unmatched}. Salda bez zmian.`);await reload();}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const blocked=busy||loading;
  return <div className="page-stack budget-page br-page bi-page">
    <header className="br-heading"><div><p className="page-eyebrow">Mniej przepisywania, pełniejszy budżet</p><h1>Importy i paragony</h1><p>Wczytaj wyciąg, przypisz sklepy do kategorii i uzupełniaj zakupy paragonami. Jeden zakup pozostaje jednym wydatkiem.</p></div><div className="br-actions"><Link className="budget-button-secondary" to="/budget"><ArrowLeft size={16}/>Budżet</Link><button className="budget-button-secondary" disabled={blocked} aria-label="Odśwież importy i wydatki" onClick={()=>void reload()}><RefreshCw size={16}/></button><button className="budget-button-primary" disabled={!data||blocked} onClick={()=>setRuleEditor({rule:null})}><CirclePlus size={16}/>Dodaj regułę</button></div></header>
    {notice&&<div className="budget-feedback is-success" role="status">{notice}</div>}
    {suggestion&&<BudgetRuleSuggestion suggestion={suggestion} onClose={()=>{setSuggestion(null);void reload();}}/>}
    {error&&<div className="budget-feedback is-error" role="alert">{error}{data&&<span> Pokazujemy ostatnio odczytane dane.</span>}<button className="budget-text-button" disabled={loading} onClick={()=>void reload()}>Odśwież dane</button></div>}
    {!data&&loading?<p className="br-panel" role="status">Ładowanie importów…</p>:data&&<>
      <section className="br-stats bi-stats" aria-label="Stan uzupełniania budżetu">
        <article className="br-stat-main"><span>Zakupy do przypisania</span><strong>{data.pending_count}</strong><small>Już zapisane wydatki; oczekują na kategorię</small></article>
        <article><span>Stałe reguły</span><strong>{data.rules.filter(r=>r.active).length+(data.transfer_rules??[]).filter(r=>r.active&&r.reserve_active).length}</strong><small>Sklepy i płatności przypisywane przy imporcie</small></article>
        <article><span>Importy do sprawdzenia</span><strong>{data.sessions.filter(s=>s.status==='PENDING').length}</strong><small>Ostatnie 30 importów; wpisy przed zatwierdzeniem</small></article>
        <article><span>Paragony do sprawdzenia</span><strong>{data.receipts.filter(r=>r.status==='PENDING').length}</strong><small>Ostatnie 30 dokumentów; odczyt i powiązania</small></article>
      </section>
      <div className="br-explanation"><ShieldCheck size={21}/><p>Import najpierw trafia do sprawdzenia. Zakupy bez kategorii można zapisać jako „Nieprzypisane”, a potem przypisać ręcznie lub regułą. Paragon jest opcjonalny; jego dołączenie do zakupów z banku nie zmienia salda.</p></div>
      {!data.accounts.length&&<div className="br-warning">Dodaj konto z aktualnym saldem, aby importować operacje. <Link to="/budget/accounts" className="budget-text-button">Konta i przelewy<ArrowUpRight size={14}/></Link></div>}
      <div className="br-tabs bi-tabs" role="tablist" aria-label="Uzupełnianie budżetu">{tabs.map(item=><button key={item.id} role="tab" aria-selected={tab===item.id} aria-controls={`import-panel-${item.id}`} id={`import-tab-${item.id}`} className={tab===item.id?'is-active':''} onClick={()=>setTab(item.id)}><item.icon size={16}/>{item.name}</button>)}</div>
      <div role="tabpanel" id={`import-panel-${tab}`} aria-labelledby={`import-tab-${tab}`}>
      {tab==='PENDING'&&<section className="br-panel bi-pending"><div className="br-toolbar"><div><p className="page-eyebrow">Kategoria bez obowiązku dodawania zdjęcia</p><h2>Zakupy do przypisania</h2></div><div className="br-actions"><button className="budget-button-secondary" disabled={blocked||!data.pending.length||!data.rules.some(r=>r.active)} onClick={()=>void applyRules()}><WandSparkles size={15}/>Zastosuj reguły</button><button className="budget-button-primary" onClick={()=>setTab('CSV')}><FileUp size={15}/>Importuj wyciąg</button></div></div>
        {!data.pending.length?<div className="bi-empty"><ListChecks size={30}/><h3>Wszystkie zapisane zakupy mają kategorię</h3><p>Po imporcie pojawią się tutaj zakupy bez dopasowanej reguły. Możesz przypisać całe zakupy do Jedzenia albo dodać paragon i rozdzielić produkty.</p></div>:<>
          <div className="bi-bulk"><label className="bi-check"><input type="checkbox" checked={selected.size===Math.min(data.pending.length,500)&&selected.size>0} disabled={blocked} onChange={e=>setSelected(e.target.checked?new Set(data.pending.slice(0,500).map(p=>p.id)):new Set())}/>Wybierz widoczne (do 500)</label><label>Kategoria zaznaczonych<select value={category} disabled={blocked} onChange={e=>setCategory(e.target.value)}><option value="">Wybierz kategorię</option>{data.categories.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label><button className="budget-button-primary" disabled={blocked||!selected.size||!category} onClick={()=>void assign([...selected],Number(category))}>Przypisz zaznaczone ({selected.size})</button></div>
          <div className="bi-pending-list">{data.pending.map(entry=><article key={entry.id}><label className="bi-check"><input type="checkbox" aria-label={`Wybierz wydatek: ${entry.description}`} checked={selected.has(entry.id)} disabled={blocked} onChange={e=>setSelected(before=>{const next=new Set(before);if(e.target.checked&&next.size<500)next.add(entry.id);else next.delete(entry.id);return next;})}/></label><div className="bi-pending-text"><strong>{entry.merchant||entry.description}</strong><p>{importDay(entry.date)} · {entry.account_name} · {entry.description}</p><small>{entry.has_receipt?'Paragon dołączony':'Paragon opcjonalny'} · Do przypisania</small></div><b>{importMoney(entry.amount)}</b><div className="bi-pending-actions"><label><span className="sr-only">Kategoria wydatku: {entry.description}</span><select value={rowCategories[entry.id]??''} disabled={blocked} onChange={e=>setRowCategories({...rowCategories,[entry.id]:e.target.value})}><option value="">Wybierz kategorię</option>{data.categories.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label><button className="budget-icon-button" disabled={blocked||!rowCategories[entry.id]} aria-label={`Przypisz kategorię: ${entry.description}`} onClick={()=>void assign([entry.id],Number(rowCategories[entry.id]))}><Check size={17}/></button><button className="budget-icon-button" disabled={blocked||!rowCategories[entry.id]} aria-label={`Zapamiętaj regułę: ${entry.description}`} onClick={()=>setRuleEditor({rule:null,pattern:entry.merchant||entry.description,categoryId:Number(rowCategories[entry.id])})}><WandSparkles size={17}/></button><Link className="budget-icon-button" to={`/budget?view=entries&month=${entry.date.slice(0,7)}&edit_entry=${entry.id}`} aria-label={`Podziel ręcznie: ${entry.description}`}><Pencil size={17}/></Link><Link className="budget-icon-button" to={`/budget/imports?tab=receipt&entry_id=${entry.id}`} aria-label={`Dodaj paragon: ${entry.description}`} onClick={()=>{setTab('RECEIPT');setDraftId(null);}}><Camera size={17}/></Link></div></article>)}</div>
          {data.pending_count>data.pending.length&&<button className="budget-button-secondary" disabled={blocked||limit>=5000} onClick={()=>setLimit(Math.min(5000,limit+200))}>Pokaż więcej ({data.pending_count-data.pending.length})</button>}
        </>}
      </section>}
      {tab==='CSV'&&<BankCsvImport workspace={data} sessionId={sessionId} onSession={setSessionId} onSaved={saved} onRule={(pattern,categoryId)=>setRuleEditor({rule:null,pattern,categoryId})}/>}
      {tab==='RECEIPT'&&<><ReceiptImport workspace={data} draftId={draftId} onDraft={setDraftId} onSaved={saved} onDeleted={receiptDeleted}/>{data.receipts.length>0&&!draftId&&<section className="br-panel bi-document-list"><h2>Ostatnie paragony</h2>{data.receipts.map(r=><button key={r.id} disabled={blocked} onClick={()=>setDraftId(r.id)}><Camera size={17}/><span>{r.filename}<small>{r.status==='PENDING'?'Do sprawdzenia':'Zapisany i powiązany z zakupem'}</small></span><ArrowUpRight size={16}/></button>)}</section>}</>}
      {tab==='RULES'&&<><section className="br-panel bi-rules"><div className="br-toolbar"><div><p className="page-eyebrow">Ustaw raz, wykorzystuj przy kolejnych wyciągach</p><h2>Stałe reguły kategorii</h2></div><button className="budget-button-primary" disabled={blocked} onClick={()=>setRuleEditor({rule:null})}><CirclePlus size={16}/>Nowa reguła</button></div><p className="br-form-help">Przykłady: ENEA → Prąd / media, LIDL → Jedzenie, ORLEN → Transport. Każda reguła może obowiązywać na wszystkich kontach lub jednym wybranym.</p>{data.rules.length?<div className="bi-rule-list">{data.rules.map(rule=><article key={rule.id} className={!rule.active?'is-paused':''}><WandSparkles size={20}/><div><strong>{rule.name}</strong><p>{rule.match_type==='CONTAINS'?'Zawiera':rule.match_type==='EQUALS'?'Równa się':'Zaczyna się od'} „{rule.pattern}” → <b>{rule.category_name}</b></p><small>{rule.account_name??'Wszystkie konta'} · Priorytet {rule.priority} · {rule.active?'Aktywna':'Wstrzymana'}</small></div><button className="budget-button-secondary" disabled={blocked} onClick={()=>setRuleEditor({rule})}><Pencil size={15}/>Edytuj</button></article>)}</div>:<div className="bi-empty"><WandSparkles size={30}/><h3>Dodaj pierwszą regułę</h3><p>Stałe płatności i zakupy w znanych sklepach będą od razu przypisane do wybranej kategorii. Podział z paragonu możesz zatwierdzić później.</p></div>}</section><ReserveTransferRules workspace={data} onSaved={saved}/></>}
      {tab==='HISTORY'&&<section className="br-panel bi-document-list"><h2>Ostatnie importy z banku</h2><p className="br-form-help">Wróć do przygotowanego importu lub sprawdź wynik zatwierdzonego pliku.</p>{data.sessions.length?data.sessions.map(s=><button key={s.id} disabled={blocked} onClick={()=>{setSessionId(s.id);setTab('CSV');}}><FileUp size={19}/><span>{s.filename}<small>{s.account_name} · {s.row_count} operacji · {s.status==='PENDING'?'Do sprawdzenia':'Zatwierdzony'} · {s.balance_mode==='HISTORY'?'Historia bez zmiany salda':'Nowe operacje'}</small></span><ArrowUpRight size={17}/></button>):<p className="bi-empty">Nie ma jeszcze importów. Przygotuj pierwszy plik w zakładce „Import CSV”.</p>}</section>}
      </div>
    </>}
    {data&&ruleEditor&&<RuleEditor workspace={data} {...ruleEditor} onClose={()=>setRuleEditor(null)} onSaved={()=>{setRuleEditor(null);saved('Reguła zapisana. Kolejne importy wykorzystają wskazaną kategorię. W przygotowanym imporcie użyj „Odśwież saldo i zastosuj reguły”.');}}/>}
  </div>;
}
