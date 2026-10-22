import BudgetNavigation from '../components/budget/BudgetNavigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRightLeft, CheckCheck, CreditCard, History, Plus, RefreshCw, ShieldCheck, Wallet, X } from 'lucide-react';
import { accountsApi, type AccountsWorkspace, type ManagedAccount, type AccountHistory } from '../api_accounts';
import { extractErrorMessageFromUnknown } from '../http/response';
import '../components/budget/budgetWorkspace.css';
import '../components/budget/budgetReserves.css';
import '../components/budget/budgetAccounts.css';

const money=(n:number)=>new Intl.NumberFormat('pl-PL',{style:'currency',currency:'PLN'}).format(n);
const dayText=(s:string)=>new Date(s+'T12:00:00').toLocaleDateString('pl-PL',{day:'numeric',month:'short',year:'numeric'});
const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
type Editor={kind:'ADD'}|{kind:'TRANSFER';source?:number;target?:number;reserve?:number}|{kind:'RECONCILE';account:ManagedAccount}|{kind:'OPENING';account:ManagedAccount}|{kind:'MARK_OPENING';account:ManagedAccount;record:AccountHistory};

export default function BudgetAccounts(){
  const [params]=useSearchParams();
  const [data,setData]=useState<AccountsWorkspace|null>(null),[loading,setLoading]=useState(true);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[filter,setFilter]=useState('');
  const [editor,setEditor]=useState<Editor|null>(null);
  const mounted=useRef(true),loadVersion=useRef(0),opened=useRef(false);
  const reload=useCallback(async()=>{
    const version=++loadVersion.current;setLoading(true);setError('');
    try{const result=await accountsApi.get();if(mounted.current&&version===loadVersion.current)setData(result);}
    catch(err){if(mounted.current&&version===loadVersion.current)setError(extractErrorMessageFromUnknown(err));}
    finally{if(mounted.current&&version===loadVersion.current)setLoading(false);}
  },[]);
  useEffect(()=>{mounted.current=true;void reload();return()=>{mounted.current=false;loadVersion.current+=1;};},[reload]);
  useEffect(()=>{
    if(!data||opened.current||!params.get('reserve'))return;
    opened.current=true;
    const reserve=data.reserves.find(r=>r.id===Number(params.get('reserve')));
    if(reserve?.locations.length&&data.accounts.length>1)setEditor({kind:'TRANSFER',reserve:reserve.id,source:reserve.locations[0].account_id});
  },[data,params]);
  const disabled=loading||!!editor;
  const hasCards=data?.accounts.some(a=>a.account_type==='CREDIT_CARD');
  const history=data?.history.filter(h=>!filter||[h.account_id,h.source_account_id,h.target_account_id].includes(Number(filter)))??[];
  return <div className="page-stack budget-page br-page ba-page">
    <header className="br-heading"><div><p className="page-eyebrow">Wiesz, gdzie są Twoje pieniądze</p><h1>Konta i przelewy</h1><p>Sprawdź salda, miejsce odkładania na cele i środki, które możesz jeszcze wykorzystać.</p></div><div className="br-actions"><button className="budget-button-secondary" onClick={()=>setEditor({kind:'ADD'})} disabled={disabled}><Plus size={16}/>Dodaj konto</button><button className="budget-button-primary" onClick={()=>setEditor({kind:'TRANSFER'})} disabled={disabled||!data||data.accounts.length<2}><ArrowRightLeft size={16}/>Zapisz przelew</button></div></header>
    <BudgetNavigation active="accounts" current/>

    {notice&&<div className="budget-feedback is-success" role="status">{notice}</div>}
    {error&&<div className="budget-feedback is-error" role="alert">{error}<button className="budget-button-secondary" disabled={loading} onClick={()=>void reload()}>Odśwież dane</button></div>}
    {!data&&loading?<p className="br-panel" role="status">Ładowanie kont…</p>:data&&<>
      <section className={`br-stats ba-stats ${hasCards?'ba-stats-with-cards':''}`} aria-label="Podsumowanie kont"><article><span>{hasCards?'Własne pieniądze na kontach':'Łącznie na kontach'}</span><strong>{money(data.totals.cash_balance??data.totals.balance)}</strong><small>{hasCards?'Konta bankowe i gotówka, bez limitu karty':'Salda kont budżetowych w PLN'}</small></article><article><span>Odłożone na rezerwy</span><strong>{money(data.totals.reserved)}</strong><small>Część sald przeznaczona na konkretne wydatki</small></article><article className="br-stat-main"><span>Poza rezerwami</span><strong className={data.totals.available<0?'br-negative':''}>{money(data.totals.available)}</strong><small>Przed uwzględnieniem miesięcznych planów i rachunków{hasCards?', po odjęciu długu kart':''}</small></article>{hasCards&&<article><span>Do spłaty na kartach</span><strong>{money(data.totals.credit_card_debt??0)}</strong><small>Już odjęte od wolnych środków. Spłata nie będzie drugim kosztem.{!!data.totals.credit_card_overpayment&&` Nadpłata na kartach: ${money(data.totals.credit_card_overpayment)}.`}</small></article>}</section>
      <div className="br-explanation"><ShieldCheck size={20}/><p>Przelew i nowe odłożenie na rezerwę obciąża budżet miesiąca i zapisuje cel na koncie docelowym. Zwykły przelew lub przeniesienie już odłożonej kwoty zmienia tylko miejsce pieniędzy. Łączna suma na Twoich kontach pozostaje taka sama.</p></div>
      {hasCards&&<div className="br-explanation ba-credit-explanation"><CreditCard size={20}/><p><b>Zakup teraz, spłata później.</b> Zakup kartą jest wydatkiem w dniu transakcji i zwiększa jej zadłużenie. Użyj „Zapisz spłatę”, kiedy przelejesz pieniądze z banku. Nie dodawaj spłaty jako kolejnego wydatku ani dochodu.</p></div>}
      {data.warnings.map(w=><p className="br-warning" role="alert" key={w}>{w}</p>)}
      <div className="br-toolbar"><h2 className="ba-section-title">Gdzie leżą środki</h2><div className="br-actions"><Link className="budget-text-button" to="/budget/reserves">Rezerwy na wydatki</Link><button className="budget-icon-button" aria-label="Odśwież konta" disabled={disabled} onClick={()=>void reload()}><RefreshCw size={17}/></button></div></div>
      {!data.accounts.length?<section className="br-panel br-empty"><Wallet size={36}/><h2>Dodaj konta, z których korzystasz</h2><p>Zacznij od aktualnego salda konta osobistego, oszczędnościowego albo gotówki. Każdą kwotę zapisuj tylko raz; odłożone środki są częścią tego salda.</p><button className="budget-button-primary" onClick={()=>setEditor({kind:'ADD'})} disabled={disabled}>Dodaj pierwsze konto</button></section>:<section className="br-grid ba-grid" aria-label="Konta budżetowe">{data.accounts.map(a=><article className={`br-card ba-card ${a.account_type==='CREDIT_CARD'?'ba-credit-card':''}`} key={a.id}>
        <div className="ba-account-title"><div className="ba-icon">{a.account_type==='CREDIT_CARD'?<CreditCard size={21}/>:<Wallet size={21}/>}</div><div><h3>{a.name}</h3><p>{a.account_type==='CREDIT_CARD'?'Karta kredytowa · PLN':'PLN'} · {a.verified_on?`Saldo sprawdzone ${dayText(a.verified_on)}`:'Saldo nie było jeszcze sprawdzane'}</p></div></div>
        <span className="ba-balance-label">{a.account_type==='CREDIT_CARD'?(a.balance>0?'Nadpłata na karcie':'Zadłużenie do spłaty'):'Saldo według zapisów'}</span><strong className="ba-balance">{money(a.account_type==='CREDIT_CARD'?Math.abs(a.balance):a.balance)}</strong>
        {a.opening_balance!=null && <div className="ba-opening"><span>Saldo początkowe</span><strong>{money(a.opening_balance)}</strong><small>{a.opening_date && dayText(a.opening_date)} · poza dochodem i historią operacji</small></div>}
        {a.account_type!=='CREDIT_CARD'&&<><div className="ba-split"><div><span>Na rezerwy</span><b>{money(a.reserved)}</b></div><div><span>Poza rezerwami</span><b className={a.available<0?'br-negative':''}>{money(a.available)}</b></div></div>
        <div className="ba-allocation-bar" aria-hidden="true"><span style={{width:`${a.balance>0?Math.min(100,a.reserved/a.balance*100):0}%`}}/></div>
        <div className="ba-locations"><h4>Odłożone na tym koncie</h4>{a.allocations.length?<ul>{a.allocations.map(r=><li key={r.reserve_id}><Link to={`/budget/reserves?reserve=${r.reserve_id}`}>{r.name}</Link><b>{money(r.amount)}</b></li>)}</ul>:<p>Brak wydzielonych rezerw. Możesz przypisać część salda do celu.</p>}</div>
        </>}
        <div className="br-card-actions"><details className="budget-account-options"><summary>Więcej opcji</summary><button className="budget-text-button" onClick={()=>setEditor({kind:'OPENING',account:a})} disabled={disabled}>{a.opening_balance==null?'Ustaw saldo początkowe':'Edytuj saldo początkowe'}</button></details><button className="budget-button-secondary" onClick={()=>setEditor({kind:'RECONCILE',account:a})} disabled={disabled}><CheckCheck size={16}/>Sprawdź saldo</button>{a.account_type==='CREDIT_CARD'?<button className="budget-button-primary" onClick={()=>setEditor({kind:'TRANSFER',target:a.id,source:data.accounts.find(b=>b.account_type!=='CREDIT_CARD')?.id})} disabled={disabled||a.balance>=0||!data.accounts.some(b=>b.account_type!=='CREDIT_CARD')}><ArrowRightLeft size={15}/>Zapisz spłatę</button>:<button className="budget-text-button" onClick={()=>setEditor({kind:'TRANSFER',source:a.id})} disabled={disabled||data.accounts.length<2}><ArrowRightLeft size={15}/>Przenieś środki</button>}</div>
      </article>)}</section>}
      <section className="br-panel ba-history"><div className="br-toolbar"><div><p className="page-eyebrow">Przesunięcia i potwierdzenia</p><h2 className="ba-section-title"><History size={19}/>Historia kont</h2></div><label>Wyświetlane konto<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="">Wszystkie konta</option>{data.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label></div>
        {history.length?<ul>{history.map(h=>{const account=data.accounts.find(a=>a.id===h.account_id);return <li key={h.id}><div className="ba-history-symbol">{h.kind==='RECONCILIATION'?<CheckCheck size={18}/>:<ArrowRightLeft size={18}/>}</div><div className="ba-history-main"><span>{h.kind==='CARD_PAYMENT'?'Spłata karty':h.kind==='TRANSFER'?'Przelew między kontami':h.kind==='LOCATION'?'Zmiana miejsca rezerwy':h.amount===0?'Potwierdzenie salda':'Korekta salda'} · {dayText(h.date)}</span><strong>{h.title}</strong><p>{h.kind==='RECONCILIATION'&&h.previous_balance!==undefined&&h.observed_balance!==undefined?`Saldo ${money(h.previous_balance)} → ${money(h.observed_balance)}`:h.detail}{h.notes&&` · ${h.notes}`}</p>{h.kind==='RECONCILIATION'&&account&&account.opening_balance==null&&<button className="budget-text-button ba-mark-opening" disabled={disabled} onClick={()=>setEditor({kind:'MARK_OPENING',account,record:h})}>To saldo początkowe</button>}</div><b className={h.kind==='RECONCILIATION'&&h.amount<0?'br-negative':''}>{h.kind==='RECONCILIATION'&&h.amount>0?'+':''}{money(h.amount)}</b></li>;})}</ul>:<p className="ba-history-empty">Nie ma jeszcze zapisanych przelewów ani potwierdzeń salda.</p>}
        <p className="br-form-help">Ostatnie 100 przelewów i sprawdzeń salda. Wpływy oraz wydatki znajdziesz w historii budżetu. Saldo początkowe jest pokazane przy koncie, poza tą historią i korektami w raporcie miesięcznym.</p>
      </section>
    </>}
    {editor&&data&&<AccountEditor editor={editor} data={data} onCancel={()=>setEditor(null)} onSaved={message=>{setEditor(null);setNotice(message);void reload();}}/>}
  </div>;
}

function AccountEditor({editor,data,onCancel,onSaved}:{editor:Editor;data:AccountsWorkspace;onCancel:()=>void;onSaved:(message:string)=>void}){
  const initialSource=editor.kind==='TRANSFER'?editor.source??data.accounts.find(a=>a.account_type!=='CREDIT_CARD')?.id:undefined;
  const [name,setName]=useState(''),[source,setSource]=useState(String(initialSource??''));
  const [target,setTarget]=useState(String((editor.kind==='TRANSFER'?editor.target:undefined)??data.accounts.find(a=>a.id!==initialSource)?.id??''));
  const [reserveId,setReserveId]=useState(editor.kind==='TRANSFER'?String(editor.reserve??''):'');
  const [accountType,setAccountType]=useState<'BANK'|'CREDIT_CARD'>('BANK');
  const [reserveAction,setReserveAction]=useState<'MOVE'|'FUND'>('MOVE');
  const [amount,setAmount]=useState(editor.kind==='RECONCILE'?String(editor.account.balance):editor.kind==='OPENING'?String(editor.account.opening_balance??editor.account.inferred_opening_balance??0):editor.kind==='MARK_OPENING'?String((editor.account.inferred_opening_balance??0)+editor.record.amount):editor.kind==='TRANSFER'&&editor.target?String(Math.max(0,-(data.accounts.find(a=>a.id===editor.target)?.balance??0))):'');
  const [day,setDay]=useState(today()),[notes,setNotes]=useState(''),[moveMoney,setMoveMoney]=useState(true);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[requestId]=useState(()=>crypto.randomUUID());
  const dialog=useRef<HTMLElement>(null);
  const sourceAccount=data.accounts.find(a=>a.id===Number(source)),targetAccount=data.accounts.find(a=>a.id===Number(target));
  const cardPayment=editor.kind==='TRANSFER'&&targetAccount?.account_type==='CREDIT_CARD';
  const signedBalance=editor.kind!=='ADD'&&'account' in editor&&editor.account.account_type==='CREDIT_CARD';
  const reserve=data.reserves.find(r=>r.id===Number(reserveId));
  const eligible=reserveAction==='FUND'?data.reserves:data.reserves.filter(r=>r.locations.some(l=>l.account_id===Number(source)&&l.amount>0));
  const available=reserve&&reserveAction==='MOVE'?reserve.locations.find(l=>l.account_id===Number(source))?.amount??0:sourceAccount?.available??0;
  const difference=editor.kind==='RECONCILE'?Number(amount)-editor.account.balance:0;
  const heading=editor.kind==='ADD'?'Dodaj konto':editor.kind==='TRANSFER'?(cardPayment?'Zapisz spłatę karty':'Zapisz przelew lub przeniesienie'):editor.kind==='OPENING'?'Saldo początkowe':editor.kind==='MARK_OPENING'?'Oznacz jako saldo początkowe':'Sprawdź saldo';
  const openingMode=editor.kind==='OPENING'||editor.kind==='MARK_OPENING';
  const resultingBalance=editor.kind==='OPENING'?editor.account.balance+Number(amount)-(editor.account.inferred_opening_balance??editor.account.opening_balance??0):editor.kind==='MARK_OPENING'?editor.account.balance:0;
  useEffect(()=>{const previous=document.activeElement as HTMLElement|null;const overflow=document.body.style.overflow;document.body.style.overflow='hidden';dialog.current?.querySelector<HTMLElement>('input,select')?.focus();return()=>{document.body.style.overflow=overflow;previous?.focus();};},[]);
  useEffect(()=>{
    const handle=(e:KeyboardEvent)=>{
      if(e.key==='Escape'&&!busy)onCancel();
      if(e.key!=='Tab'||!dialog.current)return;
      const controls=Array.from(dialog.current.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled)'));
      const first=controls[0],last=controls[controls.length-1];
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
    };document.addEventListener('keydown',handle);return()=>document.removeEventListener('keydown',handle);
  },[busy,onCancel]);
  const submit=async(e:React.FormEvent)=>{
    e.preventDefault();setBusy(true);setError('');
    try{
      if(editor.kind==='ADD'){if(accountType==='CREDIT_CARD')await accountsApi.create(name,-Number(amount),requestId,accountType);else await accountsApi.create(name,Number(amount),requestId);onSaved(accountType==='CREDIT_CARD'?'Karta dodana. Początkowe zadłużenie nie jest wydatkiem tego miesiąca.':'Konto dodane z podanym saldem początkowym.');}
      else if(editor.kind==='OPENING'||editor.kind==='MARK_OPENING'){await accountsApi.openingBalance(editor.account.id,{...(editor.kind==='MARK_OPENING'?{from_reconciliation_id:Number(editor.record.id.slice(1))}:{balance:Number(amount)}),expected_balance:editor.account.balance,expected_opening_id:editor.account.opening_record_id??null,notes},requestId);onSaved(editor.kind==='MARK_OPENING'?`Ustawiono saldo początkowe ${money(Number(amount))}. Obecne saldo konta pozostaje ${money(editor.account.balance)}. Wpis zniknął z historii korekt.`:'Saldo początkowe zapisane osobno, poza dochodem i historią korekt.');}
      else if(editor.kind==='RECONCILE'){await accountsApi.reconcile(editor.account.id,Number(amount),editor.account.balance,notes,requestId);onSaved('Saldo sprawdzone. Różnica została zapisana jako korekta salda.');}
      else{
        if(!sourceAccount||!targetAccount)throw new Error('Wybierz dwa konta.');
        await accountsApi.transfer({source_account_id:sourceAccount.id,target_account_id:targetAccount.id,source_balance:sourceAccount.balance,
          target_balance:targetAccount.balance,reserve_id:cardPayment?null:reserve?.id??null,...(reserve&&!cardPayment?{version:reserve.version}:{}),
          amount:Number(amount),date:day,notes,move_money:cardPayment?true:reserve?moveMoney:true,reserve_action:cardPayment?'MOVE':reserveAction},requestId);
        onSaved(cardPayment?'Spłata karty zapisana. Wydatek pozostał w miesiącu zakupu; spłata nie jest drugim kosztem.':reserveAction==='FUND'?`Odłożono ${money(Number(amount))} na ${reserve?.name}. Przelew obciąża budżet ${day.slice(0,7)}; rezerwa jest na koncie ${targetAccount.name}.`:moveMoney||!reserve?'Przelew zapisany. Salda i miejsca odłożenia środków zostały zaktualizowane.':'Miejsce rezerwy zmienione. Salda kont pozostały bez zmian.');
      }
    }catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}
  };
  return <div className="budget-modal-backdrop"><section ref={dialog} className="budget-modal br-modal" role="dialog" aria-modal="true" aria-labelledby="account-editor-title"><div className="budget-modal-header"><div><p className="page-eyebrow">{editor.kind==='RECONCILE'||editor.kind==='OPENING'||editor.kind==='MARK_OPENING'?editor.account.name:'Konta budżetowe w PLN'}</p><h2 id="account-editor-title">{heading}</h2></div><button className="budget-icon-button" aria-label="Zamknij formularz konta" disabled={busy} onClick={onCancel}><X size={18}/></button></div>
    {error&&<p className="br-warning" role="alert">{error}</p>}
    <form onSubmit={submit}><fieldset disabled={busy}>
      {editor.kind==='ADD'&&<><label>Rodzaj konta<select value={accountType} onChange={e=>{setAccountType(e.target.value as 'BANK'|'CREDIT_CARD');setAmount('');}}><option value="BANK">Konto bankowe / gotówka</option><option value="CREDIT_CARD">Karta kredytowa</option></select></label><label>Nazwa konta<input required maxLength={150} placeholder={accountType==='CREDIT_CARD'?'np. Karta kredytowa PKO':'np. Konto oszczędnościowe'} value={name} onChange={e=>setName(e.target.value)}/></label></>}
      {editor.kind==='TRANSFER'&&<>
        <div className="budget-form-grid"><label>Z konta<select required value={source} onChange={e=>{setSource(e.target.value);setReserveId('');setMoveMoney(true);if(e.target.value===target)setTarget(String(data.accounts.find(a=>String(a.id)!==e.target.value)?.id??''));}}>{data.accounts.filter(a=>a.account_type!=='CREDIT_CARD').map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label><label>Na konto<select required value={target} onChange={e=>{setTarget(e.target.value);setReserveId('');setReserveAction('MOVE');setMoveMoney(true);}}>{data.accounts.filter(a=>a.id!==Number(source)).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label></div>
        {!cardPayment&&<><label>Cel przelewu<select value={reserveAction} onChange={e=>{setReserveAction(e.target.value as 'MOVE'|'FUND');setReserveId('');setMoveMoney(true);}}><option value="MOVE">Zwykły przelew / przeniesienie już odłożonych środków</option><option value="FUND">Przelew i nowe odłożenie na rezerwę — koszt tego miesiąca</option></select></label>
        <label>{reserveAction==='FUND'?'Rezerwa do zasilenia':'Jakie środki przenosisz'}<select required={reserveAction==='FUND'} value={reserveId} onChange={e=>{setReserveId(e.target.value);setMoveMoney(true);}}><option value="">{reserveAction==='FUND'?'Wybierz rezerwę':'Pieniądze poza rezerwami'}</option>{eligible.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
        {reserve&&reserveAction==='MOVE'&&<label>Sposób przeniesienia<select value={moveMoney?'BANK':'LOCATION'} onChange={e=>setMoveMoney(e.target.value==='BANK')}><option value="BANK">Wykonano przelew — zmień oba salda i miejsce rezerwy</option><option value="LOCATION">Środki już są na drugim koncie — zmień tylko przypisanie</option></select></label>}</>}
      </>}
      <div className={editor.kind==='TRANSFER'?'budget-form-grid':''}><label>{editor.kind==='ADD'&&accountType==='CREDIT_CARD'?'Obecne zadłużenie w PLN':signedBalance?'Saldo karty w PLN (minus oznacza dług)':editor.kind==='RECONCILE'?'Aktualne saldo w banku w PLN':editor.kind==='ADD'||openingMode?'Saldo początkowe w PLN':'Kwota w PLN'}<input type="number" required min={signedBalance?'-999999999.99':editor.kind==='TRANSFER'?'0.01':'0'} max="999999999.99" step="0.01" readOnly={editor.kind==='MARK_OPENING'} value={amount} onChange={e=>setAmount(e.target.value)}/></label>{editor.kind==='TRANSFER'&&<label>Data operacji<input type="date" required min="2000-01-01" max={today()} value={day} onChange={e=>setDay(e.target.value)}/></label>}</div>
      {editor.kind!=='ADD'&&editor.kind!=='MARK_OPENING'&&<label>{editor.kind==='RECONCILE'?'Powód różnicy / notatka':'Notatka (opcjonalnie)'}<textarea required={editor.kind==='RECONCILE'&&Math.abs(difference)>=.005} rows={2} maxLength={500} value={notes} onChange={e=>setNotes(e.target.value)}/></label>}
      {cardPayment&&sourceAccount&&targetAccount&&<div className="ba-payment-preview" role="status"><p>{sourceAccount.name}: <b>{money(sourceAccount.balance)} → {money(sourceAccount.balance-Number(amount))}</b></p><p>{targetAccount.name} — dług: <b>{money(Math.max(0,-targetAccount.balance))} → {money(Math.max(0,-targetAccount.balance-Number(amount)))}</b></p><small>Spłata zmienia tylko salda. Zakupy są już w wydatkach i wolnych środkach.</small>{Number(amount)>available&&<p className="br-negative">Brakuje środków poza rezerwami na koncie spłaty. Zmień konto lub kwotę.</p>}</div>}
      <p className="br-form-help">{editor.kind==='ADD'&&accountType==='CREDIT_CARD'?'Wpisz wykorzystany dług jako dodatnią kwotę, np. 300. Jeśli karta jest spłacona, wpisz 0. Nie wpisuj limitu kredytowego. Początkowe zadłużenie pomniejszy wolne środki, bez tworzenia wydatku ani dochodu.':openingMode?`Saldo początkowe to środki posiadane przed zapisanymi operacjami. Wydatki i przelewy zostają zachowane. Saldo konta po zapisie: ${Number.isFinite(resultingBalance)?money(resultingBalance):'—'}. Ten zapis nie jest dochodem ani korektą w historii.`:editor.kind==='ADD'?'Podaj saldo dzisiejsze. Kwoty odłożone na rezerwy są jego częścią. Nie dodawaj drugi raz pieniędzy już zapisanych jako konto oszczędnościowe w inwestycjach.':editor.kind==='RECONCILE'?`W aplikacji: ${money(editor.account.balance)}. Różnica: ${Number.isFinite(difference)?money(difference):'—'}. Potwierdzenie zapisuje dzisiejsze saldo. Korekta nie jest przychodem ani wydatkiem; znane brakujące operacje warto najpierw uzupełnić w budżecie.`:`Na koncie źródłowym do przeniesienia: ${money(available)}. ${reserveAction==='FUND'?'Kwota powiększy rezerwę na koncie docelowym i obciąży budżet miesiąca. Średnia kolejnych wpłat przeliczy się automatycznie. Zapisz późniejszą płatność w rezerwie, aby nie obciążyć budżetu ponownie.':reserve&&!moveMoney?'Salda nie zmienią się. Konto docelowe musi mieć wolne środki na tę rezerwę.':'Zapis zmniejszy saldo źródłowe i zwiększy docelowe o tę samą kwotę. Przeniesienie już odłożonych pieniędzy nie jest nową wpłatą na cel.'}`}</p>
      {editor.kind==='OPENING'&&editor.account.opening_balance==null&&data.history.some(h=>h.account_id===editor.account.id&&h.kind==='RECONCILIATION')&&<p className="br-warning">Jeśli kwota początkowa jest już zapisana jako korekta, anuluj ten formularz i użyj przy niej w historii przycisku „To saldo początkowe”. To zachowa obecne saldo i zapobiegnie ponownemu doliczeniu kwoty.</p>}
      {!signedBalance&&openingMode&&(editor.kind==='OPENING'||editor.kind==='MARK_OPENING')&&resultingBalance<editor.account.reserved&&<p className="br-warning">Wynikowe saldo jest niższe od odłożonych rezerw. Sprawdź kwotę początkową i miejsca odłożenia.</p>}
      {!signedBalance&&editor.kind==='RECONCILE'&&Number(amount)<editor.account.reserved&&<p className="br-warning">Saldo będzie niższe niż zapisane rezerwy. Po potwierdzeniu sprawdź, gdzie faktycznie leżą odłożone środki.</p>}
      <div className="budget-form-actions"><button className="budget-button-quiet" type="button" disabled={busy} onClick={onCancel}>Anuluj</button><button className="budget-button-primary" type="submit" disabled={busy||(cardPayment&&(Number(amount)>available||Number(amount)>Math.max(0,-(targetAccount?.balance??0))))}>{busy?'Zapisywanie…':editor.kind==='ADD'?'Dodaj konto':editor.kind==='MARK_OPENING'?'Oznacz jako saldo początkowe':editor.kind==='OPENING'?'Zapisz saldo początkowe':editor.kind==='RECONCILE'?'Potwierdź saldo':cardPayment?'Zapisz spłatę':reserve&&!moveMoney?'Przenieś przypisanie':'Zapisz przelew'}</button></div>
    </fieldset></form>
  </section></div>;
}
