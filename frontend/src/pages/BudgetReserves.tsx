import BudgetSettlementUndo from '../components/budget/BudgetSettlementUndo';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Archive, ArrowDownLeft, ArrowLeft, ArrowRightLeft, CalendarDays, Check, CirclePlus, History, Pencil, PiggyBank, Plus, RefreshCw, ShieldCheck, Wallet, X } from 'lucide-react';
import { reservesApi, type Reserve, type ReserveMovementInput, type ReserveMovementKind, type ReservePlan, type ReservesWorkspace } from '../api_reserves';
import { budgetImportsApi, type ExpenseCandidate } from '../api_budget_imports';
import { extractErrorMessageFromUnknown } from '../http/response';
import '../components/budget/budgetWorkspace.css';
import '../components/budget/budgetReserves.css';
import '../components/budget/budgetAccounts.css';

const money = (value: number) => new Intl.NumberFormat('pl-PL',{style:'currency',currency:'PLN'}).format(value);
const dayText = (day: string) => new Date(day+'T12:00:00').toLocaleDateString('pl-PL',{day:'numeric',month:'short',year:'numeric'});
const today = () => { const d=new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
const labels = {ADD:'Odłożenie',RELEASE:'Zwolnienie środków',SPEND:'Rozliczenie wydatku'};
type Editor = {kind:'PLAN';item:Reserve|null} | {kind:ReserveMovementKind;item:Reserve};

export default function BudgetReserves() {
  const [params] = useSearchParams();
  const [data,setData] = useState<ReservesWorkspace|null>(null);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [archive,setArchive] = useState(false);
  const [group,setGroup]=useState('ALL');
  const [undo,setUndo]=useState<number|null>(null);
  const [editor,setEditor] = useState<Editor|null>(null);
  const [busy,setBusy] = useState(false);
  const mounted = useRef(true);
  const loadVersion = useRef(0);
  const reload = useCallback(async () => {
    const version = ++loadVersion.current;
    setLoading(true); setError('');
    try { const result=await reservesApi.get(); if(mounted.current && version===loadVersion.current) setData(result); }
    catch(err) { if(mounted.current && version===loadVersion.current) setError(extractErrorMessageFromUnknown(err)); }
    finally { if(mounted.current && version===loadVersion.current) setLoading(false); }
  },[]);
  useEffect(() => { mounted.current=true; void reload(); return () => {mounted.current=false;loadVersion.current+=1;}; },[reload]);
  const saved = (message: string) => {setEditor(null);setNotice(message);void reload();};
  const setArchived = async (item:Reserve) => {
    setBusy(true);setError('');setNotice('');
    try {await reservesApi.archive(item.id,item.status!=='ARCHIVED',item.version);setNotice(item.status==='ARCHIVED'?'Rezerwa przywrócona.':'Rezerwa przeniesiona do archiwum.');await reload();}
    catch(err) {setError(extractErrorMessageFromUnknown(err));}
    finally {setBusy(false);}
  };
  const visible = data?.items.filter(item => archive ? item.status!=='ACTIVE' : item.status==='ACTIVE').filter(item=>group==='ALL'||(group==='OPEN'?item.open_ended:group==='MEDIA'?item.monthly_amount!=null&&!item.open_ended:item.monthly_amount==null)) ?? [];
  return <div className="page-stack budget-page br-page">
    <header className="br-heading"><div><p className="page-eyebrow">Przygotuj pieniądze przed terminem</p><h1>Rezerwy na wydatki</h1><p>Ubezpieczenie, remont czy zakup sprzętu — odkładaj we własnym tempie, a plan dopasuje się do wpłat.</p></div><div className="br-actions"><Link className="budget-button-secondary" to="/budget"><ArrowLeft size={16}/>Budżet</Link><button className="budget-button-primary" onClick={() => {setNotice('');setEditor({kind:'PLAN',item:null});}} disabled={!data || !data.accounts.length || loading || busy || !!editor}><Plus size={17}/>Nowa rezerwa</button></div></header>
    {notice && <div role="status" className="budget-feedback is-success">{notice}</div>}
    {error && <div role="alert" className="budget-feedback is-error">{error}<button className="budget-button-secondary" onClick={() => void reload()} disabled={loading}>Spróbuj ponownie</button></div>}
    {!data && loading ? <p className="br-panel" role="status">Ładowanie rezerw…</p> : data && <>
      <section aria-label="Podsumowanie rezerw" className="br-stats">
        <article><span>Odłożone środki</span><strong>{money(data.totals.saved)}</strong><small>Część sald kont wydzielona na aktywne rezerwy</small></article>
        <article><span>Pozostało do odłożenia</span><strong>{money(data.totals.remaining)}</strong><small>Cele z terminem oraz niewykonany plan bieżącego miesiąca</small></article>
        <article className="br-stat-main"><span>Jeszcze do odłożenia w miesiącu</span><strong>{money(data.totals.monthly_remaining??data.totals.monthly_required)}</strong><small>{data.totals.urgent_amount>0 ? `W tym pilne: ${money(data.totals.urgent_amount)}` : 'Ten sam plan co w budżecie i prognozie'}</small></article>
        <article><span>Aktywne rezerwy</span><strong>{data.totals.active}</strong><small>Z terminem i bez terminu</small></article>
      </section>
      <div className="br-explanation"><ShieldCheck size={20}/><p>Nowe odłożenie obciąża budżet miesiąca, a pieniądze pozostają częścią salda konta. Przy późniejszej płatności budżet obciąży tylko kwota niepokryta wcześniejszymi odłożeniami. Przelew i odłożenie na innym koncie zapiszesz w „Kontach i przelewach”.</p></div>
      {data.warnings.map(warning => <p className="br-warning" role="alert" key={warning}>{warning}</p>)}
      {data.accounts.length ? <section className="br-accounts" aria-label="Środki na kontach">{data.accounts.map(account => <article key={account.id}><Wallet size={17}/><div><strong>{account.name}</strong><span>Saldo: {money(account.balance)} · Rezerwy: {money(account.reserved)}</span></div><b className={account.available<0?'br-negative':''}>{money(account.available)}<small>poza rezerwami</small></b></article>)}</section> : <section className="br-panel br-empty"><PiggyBank size={36}/><h2>Zacznij od konta budżetowego</h2><p>Dodaj konto z aktualnym saldem. Potem wydzielisz z niego środki na ubezpieczenie auta, mieszkania albo inny większy koszt.</p><Link className="budget-button-primary" to="/budget">Dodaj konto w budżecie</Link></section>}
      <Link className="budget-text-button" to="/budget/accounts"><ArrowRightLeft size={16}/>Salda, przelewy i miejsca odłożenia</Link><div className="br-toolbar"><label>Rodzaj rezerwy<select value={group} onChange={e=>setGroup(e.target.value)}><option value="ALL">Wszystkie</option><option value="TARGET">Cele z terminem</option><option value="MEDIA">Prąd i woda</option><option value="OPEN">Bez terminu</option></select></label><div className="br-tabs" aria-label="Stan rezerw"><button className={!archive?'is-active':''} aria-pressed={!archive} onClick={() => setArchive(false)}>Aktywne</button><button className={archive?'is-active':''} aria-pressed={archive} onClick={() => setArchive(true)}><History size={15}/>Rozliczone i archiwum</button></div><button className="budget-icon-button" aria-label="Odśwież rezerwy" disabled={loading || busy || !!editor} onClick={() => void reload()}><RefreshCw size={17}/></button></div>
      {data.accounts.length>0 && visible.length===0 && <section className="br-panel br-empty"><PiggyBank size={36}/><h2>{archive?'Nie ma jeszcze rozliczonych rezerw':'Przygotuj się na większy wydatek'}</h2><p>{archive?'Po zapisaniu płatności jednorazowa rezerwa pojawi się tutaj.':'Podaj przewidywany koszt i termin. Każde odłożenie obniży brakującą kwotę i przeliczy kolejne miesiące.'}</p>{!archive && <button className="budget-button-primary" onClick={() => setEditor({kind:'PLAN',item:null})} disabled={loading || !!editor}><Plus size={17}/>Dodaj pierwszą rezerwę</button>}</section>}
      <div className="br-group-summary"><strong>{group==='MEDIA'?'Miesięczne pule mediów':group==='OPEN'?'Stałe odkładanie bez terminu':group==='TARGET'?'Koszty z terminem':'Wszystkie rezerwy'}</strong><p>{group==='MEDIA'?'Plan obejmuje płatności i nowe odłożenia. Wcześniejsza rezerwa finansuje fakturę bez kolejnego kosztu.':group==='OPEN'?'Stałą wpłatę planujemy niezależnie od płatności; 0 zł oznacza odkładanie ręczne.':group==='TARGET'?'Brakująca kwota rozkłada się na miesiące do terminu. Wyższa wpłata zmniejsza następne odłożenia.':'Wybierz rodzaj, aby porównać rezerwy działające według tej samej zasady.'}</p><small>{visible.length} rezerw · odłożone {money(visible.reduce((sum,r)=>sum+r.saved,0))}</small></div><section className="br-grid" aria-label="Lista rezerw">{visible.map(item => <article key={item.id} className={`br-card ${params.get('reserve')===String(item.id)?'is-selected':''}`}>
        <div className="br-card-title"><div><span className="br-tag">{item.status==='COMPLETED'?'Rozliczona':item.status==='ARCHIVED'?'Archiwum':item.open_ended?'Bez terminu':item.monthly_amount!=null?'Miesięczna pula na media':item.frequency==='YEARLY'?'Co roku':'Jednorazowo'}{item.monthly_amount==null&&` · Cykl ${item.cycle}`}</span><h2>{item.name}</h2><p><CalendarDays size={14}/>{item.monthly_amount!=null?`Domyślnie ${money(item.monthly_amount)} / mies.`:dayText(item.due_date)} · {item.account_name}</p></div>{item.status==='ACTIVE' && <button className="budget-icon-button" aria-label={`Edytuj rezerwę: ${item.name}`} onClick={() => setEditor({kind:'PLAN',item})} disabled={loading || busy || !!editor}><Pencil size={16}/></button>}</div>
        {item.notes && <p className="br-notes">{item.notes}</p>}
        {!!item.locations?.length && <div className="br-locations" aria-label={`Miejsce środków: ${item.name}`}>{item.locations.map(l=><Link key={l.account_id} to="/budget/accounts"><Wallet size={13}/>{l.account_name}<b>{money(l.amount)}</b></Link>)}</div>}
        <div className="br-saved"><span>{item.status==='COMPLETED'?'Zapłacono':'Odłożone środki'}</span><strong>{money(item.status==='COMPLETED'?item.movements.reduce((sum,m)=>sum+(m.expense_amount??0),0):item.saved)}</strong>{item.status!=='COMPLETED'&&<small>Aktualna kwota dostępna w tej rezerwie</small>}</div>
        {item.monthly_amount!=null&&!item.open_ended?<div className="br-progress-label"><Link to={`/budget?view=plan&month=${data.as_of.slice(0,7)}`}>Koryguj bieżący miesiąc</Link></div>:item.monthly_amount==null&&item.status!=='COMPLETED'&&<><div className="br-progress-label"><span>Cel: <b>{money(item.target_amount)}</b></span><span>{item.progress_percent}% celu</span></div><div className="br-progress" role="progressbar" aria-label={`Postęp: ${item.name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={item.progress_percent}><span style={{width:`${item.progress_percent}%`}}/></div></>}
        {item.status==='ACTIVE' && <><div className="br-plan"><div><span>{item.open_ended?'Stały plan miesięczny':item.monthly_amount!=null?'Plan bieżącego miesiąca':item.urgent?'Do uzupełnienia teraz':'Na kolejne miesiące'}</span><strong>{money(item.monthly_amount!=null?item.month_planned??item.monthly_amount:item.monthly_required)}{item.monthly_amount==null&&!item.urgent && item.remaining>0 && <small> / mies.</small>}</strong></div><div><span>{item.monthly_amount!=null?'Jeszcze do odłożenia':'Pozostało'}</span><b>{money(item.remaining)}</b><small>{item.monthly_amount!=null?`${item.open_ended?'Odłożono w miesiącu':'Płatności i odłożenia'}: ${money(item.month_allocated??0)}`:item.remaining===0?'Kwota celu odłożona':item.urgent?item.overdue?'Termin minął':'Przed końcem terminu':`Miesiące do odkładania: ${item.months_left}`}</small></div></div>
          <p className="br-plan-note">{item.open_ended?`Stały plan: ${money(item.monthly_amount??0)} miesięcznie. Zmienisz go w edycji rezerwy. ${item.monthly_amount===0?'Brak obowiązkowej wpłaty; możesz odkładać ręcznie dowolne kwoty.':'Dodatkowe wpłaty nie zmniejszają planu na kolejny miesiąc.'}`:item.monthly_amount!=null?'Kwota domyślna trafia do kolejnych miesięcy. Korektę kwoty z licznika lub rozliczenia zapisujesz w planie wybranego miesiąca. Faktury zużywają rezerwę; reszta środków zostaje na przyszłość.':item.remaining===0 ? item.surplus>0?`Nadwyżka: ${money(item.surplus)}. Możesz ją zwolnić lub pozostawić do rozliczenia.`:'Możesz zapisać płatność po jej wykonaniu.' : item.urgent?'Dopłać brakującą kwotę lub zmień termin planowanego kosztu.' : `Następne odłożenie: ${dayText(item.next_contribution_date!)}. ${item.funded_this_month?'W tym miesiącu zapisano już odłożenie; plan obejmuje kolejne miesiące.':'Bieżący miesiąc jest uwzględniony w planie.'}`}</p>
          <div className="br-card-actions"><button className="budget-button-primary" onClick={() => setEditor({kind:'ADD',item})} disabled={loading || busy || !!editor}><CirclePlus size={16}/>Odłóż środki</button><button className="budget-button-secondary" onClick={() => setEditor({kind:'SPEND',item})} disabled={!data.categories.length || loading || busy || !!editor}><Check size={16}/>Zapisz płatność</button>{item.saved>0 && <button className="budget-text-button" onClick={() => setEditor({kind:'RELEASE',item})} disabled={loading || busy || !!editor}><ArrowDownLeft size={15}/>Zwolnij</button>}</div></>}
        {item.movements.length>0 && <details className="br-history" open={params.get('reserve')===String(item.id)}><summary><History size={15}/>Historia odłożeń i płatności ({item.movements.length})</summary><ul>{item.movements.map(m => <li key={m.id}><div><strong>{m.kind==='SPEND' && m.budget_entry_id===null?'Zwolnienie przy płatności':labels[m.kind]}</strong><small>{dayText(m.date)}{m.account_name && ` · ${m.account_name}`} · Cykl {m.cycle}{m.notes && ` · ${m.notes}`}</small>{m.kind==='SPEND' && <small>Zwolniono z rezerwy: {money(m.amount)}</small>}</div><div>{m.budget_entry_id&&m.kind==='SPEND'&&<button className="budget-text-button" onClick={()=>setUndo(m.budget_entry_id)}>Cofnij rozliczenie</button>}<b>{m.kind==='ADD'?'+':m.kind==='RELEASE'?'−':''}{money(m.expense_amount ?? m.amount)}</b></div></li>)}</ul></details>}
        {!!item.transfers?.length && <details className="br-history"><summary><ArrowRightLeft size={15}/>Przeniesienia między kontami ({item.transfers.length})</summary><ul>{item.transfers.map(t=><li key={t.id}><div><strong>{t.source_account_name} → {t.target_account_name}</strong><small>{dayText(t.date)} · {t.reserve_action==='FUND'?'Przelew i nowe odłożenie — koszt miesiąca':t.move_money?'Przelew i zmiana miejsca':'Zmiana przypisania bez zmiany sald'}{t.notes&&` · ${t.notes}`}</small></div><b>{money(t.amount)}</b></li>)}</ul></details>}
        <div className="br-card-footer">{item.saved>0 && item.status==='ACTIVE' && data.accounts.length>1 && <Link className="budget-text-button" to={`/budget/accounts?reserve=${item.id}`}><ArrowRightLeft size={14}/>Przenieś na inne konto</Link>}{item.saved===0 && <button className="budget-text-button" onClick={() => void setArchived(item)} disabled={loading || busy || !!editor}><Archive size={14}/>{item.status==='ARCHIVED'?'Przywróć':'Archiwizuj'}</button>}</div>
      </article>)}</section>
      <section className="br-panel br-method"><h2>Jak przeliczamy plan?</h2><p>Rezerwa bez terminu ma stałą kwotę miesięczną, również 0 zł. Zmienisz ją tylko w ustawieniach rezerwy. Brak celu i terminu oznacza brak automatycznego przeliczania po wpłatach.</p><p>Miesięczna pula na media korzysta ze stałej kwoty domyślnej. Korekta w planie dotyczy tylko wybranego miesiąca. Płatności i odłożenia liczymy w bieżącym miesiącu, a faktury rozliczone z rezerwy nie obciążają budżetu ponownie. Odłożone środki zostają na kolejne faktury.</p><p>Brakującą kwotę dzielimy przez pozostałe miesięczne odłożenia przed terminem kosztu. Dzień odkładania wynika z daty rozpoczęcia cyklu. Bieżący miesiąc liczy się do czasu zapisania odłożenia. Po nim plan obejmuje kolejne miesiące. Każda większa lub mniejsza kwota zmienia średnią; bez wpłaty liczba miesięcy maleje i średnia rośnie. Możesz dopłacać kilka razy w miesiącu.</p><p>Przy koszcie corocznym zapis płatności otwiera kolejny cykl z terminem w następnym roku. Niewykorzystane środki pozostają w rezerwie. Dla kosztu jednorazowego rozliczenie zwalnia także nadwyżkę.</p></section>
    </>}
    {undo&&<BudgetSettlementUndo entryId={undo} reload={reload} onClose={()=>setUndo(null)}/>}
    {editor && data && <ReserveEditor key={`${editor.kind}-${editor.item?.id ?? 'new'}`} editor={editor} data={data} onCancel={() => setEditor(null)} onSaved={saved}/>}
  </div>;
}

export function ReserveEditor({editor,data,onCancel,onSaved}:{editor:Editor;data:ReservesWorkspace;onCancel:()=>void;onSaved:(message:string)=>void}) {
  const item=editor.item, isPlan=editor.kind==='PLAN';
  const [name,setName]=useState(item?.name ?? '');
  const [notes,setNotes]=useState(isPlan?item?.notes ?? '':'');
  const initialAccount=editor.kind==='RELEASE'?item?.locations?.[0]?.account_id ?? item?.account_id:item?.account_id;
  const [accountId,setAccountId]=useState(String(initialAccount ?? data.accounts[0]?.id ?? ''));
  const [monthly,setMonthly]=useState(item?.monthly_amount!=null);
  const [openEnded,setOpenEnded]=useState(item?.open_ended??false);
  const [amount,setAmount]=useState(String(isPlan?item?.monthly_amount??item?.target_amount ?? '':editor.kind==='RELEASE'?item!.locations?.find(l=>l.account_id===initialAccount)?.amount ?? item!.saved:editor.kind==='SPEND'?item!.monthly_amount??item!.target_amount:item!.monthly_required || item!.remaining || ''));
  const chosenAccount=data.accounts.find(a=>a.id===Number(accountId));
  const locationAmount=item?.locations?.find(l=>l.account_id===Number(accountId))?.amount ?? (item?.locations?0:item?.saved ?? 0);
  const [day,setDay]=useState(isPlan?item?.due_date ?? '':today());
  const [frequency,setFrequency]=useState<'ONCE'|'YEARLY'>(item?.frequency ?? 'YEARLY');
  const [categoryId,setCategoryId]=useState(String(item?.category_id??(isPlan?'':data.categories[0]?.id??'')));
  const [paymentMode,setPaymentMode]=useState<'NEW'|'EXISTING'>('NEW');
  const [payments,setPayments]=useState<ExpenseCandidate[]>([]),[paymentId,setPaymentId]=useState(''),[searched,setSearched]=useState(false);
  const clearPayments=()=>{setPayments([]);setPaymentId('');setSearched(false);};
  const [busy,setBusy]=useState(false), [error,setError]=useState('');
  const [requestId]=useState(() => crypto.randomUUID());
  const firstField=useRef<HTMLInputElement>(null), dialog=useRef<HTMLElement>(null);
  const heading=isPlan ? item?'Edytuj rezerwę':'Nowa rezerwa' : editor.kind==='ADD'?'Odłóż środki':editor.kind==='RELEASE'?'Zwolnij środki':'Zapisz płatność';
  useEffect(() => {
    const previous=document.activeElement as HTMLElement|null; firstField.current?.focus();
    const overflow=document.body.style.overflow;document.body.style.overflow='hidden';
    return () => {document.body.style.overflow=overflow;previous?.focus();};
  },[]);
  useEffect(() => {
    const onKey=(event:KeyboardEvent) => {
      if(event.key==='Escape' && !busy) onCancel();
      if(event.key!=='Tab' || !dialog.current) return;
      const controls=Array.from(dialog.current.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled)'));
      const first=controls[0],last=controls[controls.length-1];
      if(event.shiftKey && document.activeElement===first){event.preventDefault();last?.focus();}
      else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus();}
    };
    document.addEventListener('keydown',onKey); return () => {document.removeEventListener('keydown',onKey);};
  },[busy,onCancel]);
  const submit = async (event:React.FormEvent) => {
    event.preventDefault();setBusy(true);setError('');
    try {
      if(isPlan) {
        const plan:ReservePlan={name,notes,category_id:categoryId?Number(categoryId):null,account_id:Number(accountId),target_amount:Number(amount),due_date:day,frequency,monthly_amount:monthly?Number(amount):null,open_ended:openEnded};
        if(item) await reservesApi.update(item.id,plan,item.version); else await reservesApi.create(plan,requestId);
        onSaved(item?'Plan rezerwy zaktualizowany.':'Rezerwa utworzona. Możesz odłożyć na nią środki.');
      } else {
        const payment=payments.find(p=>p.id===Number(paymentId));
        if(editor.kind==='SPEND'&&paymentMode==='EXISTING'&&!payment)throw new Error('Znajdź i wybierz istniejącą płatność.');
        const input:ReserveMovementInput={kind:editor.kind,account_id:Number(accountId),amount:Number(amount),date:day,notes,
          ...(editor.kind==='SPEND'?payment?{existing_entry_id:payment.id,entry_version:payment.version}:{category_id:Number(categoryId)}:{})};
        await reservesApi.move(item!.id,input,item!.version,requestId);
        onSaved(editor.kind==='ADD'?'Środki odłożone. Plan kolejnych miesięcy został przeliczony.':editor.kind==='RELEASE'?'Środki zwolnione. Plan został przeliczony.':payment?'Rezerwa rozliczona z istniejącą płatnością. Wydatek i saldo nie zostały zapisane ponownie.':'Płatność zapisana w budżecie i rezerwa rozliczona.');
      }
    } catch(err) {setError(extractErrorMessageFromUnknown(err));setBusy(false);}
  };
  const findPayments=async()=>{
    setBusy(true);setError('');clearPayments();
    try{setPayments(await budgetImportsApi.matches({account_id:Number(accountId),amount:Number(amount),date:day,merchant:''}));setSearched(true);}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  return <div className="budget-modal-backdrop"><section ref={dialog} className="budget-modal br-modal" role="dialog" aria-modal="true" aria-labelledby="reserve-editor-title"><div className="budget-modal-header"><div><p className="page-eyebrow">{isPlan?'Plan większego wydatku':item?.name}</p><h2 id="reserve-editor-title">{heading}</h2></div><button className="budget-icon-button" aria-label="Zamknij formularz rezerwy" onClick={onCancel} disabled={busy}><X size={18}/></button></div>
    {error && <p role="alert" className="br-warning">{error}</p>}
    <form onSubmit={submit}><fieldset disabled={busy}>
      {isPlan && <label>Nazwa rezerwy<input ref={firstField} required maxLength={120} placeholder="np. Ubezpieczenie auta" value={name} onChange={e => setName(e.target.value)}/></label>}
      {isPlan&&<label>Sposób planowania<select value={openEnded?'OPEN':monthly?'MONTHLY':'TARGET'} onChange={e=>{const mode=e.target.value;setMonthly(mode!=='TARGET');setOpenEnded(mode==='OPEN');if(mode==='OPEN')setAmount(String(item?.open_ended?item.monthly_amount??0:0));else if(mode==='MONTHLY'&&item?.monthly_amount==null)setAmount('');}} disabled={item?.monthly_amount!=null&&!!item.movements.length}><option value="TARGET">Odkładanie na koszt z terminem</option><option value="MONTHLY">Miesięczna pula na media — prąd, woda</option><option value="OPEN">Bez terminu — stałe odkładanie</option></select></label>}
      {isPlan&&monthly&&item?.monthly_amount==null&&!!item?.movements.length&&<p className="br-form-help">Od bieżącego miesiąca. Zachowamy odłożone środki i historię; stare wpłaty nie zostaną zapisane ponownie.</p>}
      {isPlan&&monthly&&<p className="br-form-help">{openEnded?'Bez daty i kwoty docelowej. Stały plan może wynosić 0 zł. Wpłaty i płatności nie przeliczają tej kwoty; możesz odkładać dodatkowo, kiedy chcesz. Plan nie wykonuje wpłaty.':'Kwota powtarza się w planie kolejnych miesięcy. Możesz skorygować wybrany miesiąc według licznika lub rozliczenia. Odłożenie pieniędzy zapisujesz osobno.'}</p>}
      <label>{isPlan?'Domyślne konto nowych odłożeń':editor.kind==='SPEND'?'Konto płatności':'Konto ze środkami'}<select required value={accountId} onChange={e => {setAccountId(e.target.value);clearPayments();if(editor.kind==='RELEASE')setAmount(String(item?.locations?.find(l=>l.account_id===Number(e.target.value))?.amount ?? 0));}}>{data.accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      {isPlan && item && <p className="br-form-help">Zmiana konta dotyczy nowych odłożeń. Już odłożone pieniądze zostają na swoich kontach.</p>}
      <div className="budget-form-grid"><label>{isPlan?monthly?'Domyślna kwota miesięczna w PLN':'Przewidywany koszt w PLN':editor.kind==='SPEND'?'Zapłacona kwota w PLN':'Kwota w PLN'}<input ref={isPlan?undefined:firstField} type="number" min={isPlan&&monthly?'0':'0.01'} step="0.01" max="999999999.99" required value={amount} onChange={e => {setAmount(e.target.value);clearPayments();}}/></label>{(!isPlan||!monthly)&&<label>{isPlan?'Termin wydatku':'Data operacji'}<input type="date" min={isPlan?item?.start_date ?? today():item?.start_date} max={isPlan?'2100-12-31':today()} required value={day} onChange={e => {setDay(e.target.value);clearPayments();}}/></label>}</div>
      {isPlan&&<label>Kategoria przyszłej płatności<select required={monthly&&!openEnded} value={categoryId} onChange={e=>setCategoryId(e.target.value)}><option value="">{monthly&&!openEnded?'Wybierz osobną kategorię, np. Prąd':'Wybiorę przy płatności'}</option>{data.categories.map(c=><option key={c.id} value={c.id}>{c.selection_label??c.name}</option>)}</select></label>}
      {isPlan && !monthly&&<label>Powtarzalność<select value={frequency} onChange={e => setFrequency(e.target.value as 'ONCE'|'YEARLY')}><option value="YEARLY">Co roku — np. ubezpieczenie</option><option value="ONCE">Jednorazowo — np. remont lub zakup</option></select></label>}
      {!isPlan && editor.kind==='SPEND' && <>
        <label>Płatność w budżecie<select value={paymentMode} onChange={e=>{setPaymentMode(e.target.value as 'NEW'|'EXISTING');clearPayments();}}><option value="NEW">Nie ma jeszcze wpisu — zapisz nowy wydatek</option><option value="EXISTING">Jest już wydatek, np. z wyciągu bankowego — powiąż go</option></select></label>
        {paymentMode==='NEW'?<label>Kategoria wydatku<select required value={categoryId} onChange={e => setCategoryId(e.target.value)}>{data.categories.map(c => <option key={c.id} value={c.id}>{c.selection_label ?? c.name}</option>)}</select></label>:<>
          <button className="budget-button-secondary" type="button" onClick={()=>void findPayments()} disabled={busy||!Number(amount)||!day}>Znajdź zapisany wydatek</button>
          <p className="br-form-help">Szukamy tej samej kwoty na wybranym koncie w odstępie do 3 dni. Wybór płatności ustawi jej datę księgowania. Zachowamy jej kategorie i paragon; saldo nie zmieni się ponownie.</p>
          {payments.length>0&&<label>Zapisany wydatek<select required value={paymentId} onChange={e=>{setPaymentId(e.target.value);const p=payments.find(p=>p.id===Number(e.target.value));if(p)setDay(p.date);}}><option value="">Wybierz właściwą płatność</option>{payments.map(p=><option key={p.id} value={p.id}>{p.merchant||p.description} · {dayText(p.date)} · {money(p.amount)}</option>)}</select></label>}
          {searched&&!payments.length&&<p className="br-form-help">Nie znaleziono wydatku. Sprawdź kwotę, datę i konto albo zapisz nową płatność.</p>}
        </>}
      </>}
      <label>Notatka (opcjonalnie)<textarea rows={2} maxLength={isPlan?2000:500} value={notes} onChange={e => setNotes(e.target.value)}/></label>
      {!isPlan && <p className="br-form-help">{editor.kind==='ADD'?`Wolne środki na ${chosenAccount?.name}: ${money(chosenAccount?.available ?? 0)}. Zapis obciąży budżet miesiąca i zwiększy rezerwę bez zmiany salda konta.`:editor.kind==='RELEASE'?`Odłożono na wybranym koncie: ${money(locationAmount)}. Zwolniona kwota ponownie będzie dostępna do planowania.`:paymentMode==='EXISTING'?`Rezerwa zostanie rozliczona z wybraną płatnością. Nie powstanie nowy wydatek i saldo nie zmieni się ponownie. Budżet pomniejszymy o wcześniej odłożone środki.`:`Zapisz tę operację po wykonaniu płatności. Powstanie jeden wydatek na koncie ${chosenAccount?.name}. Kwoty tej rezerwy zostaną zwolnione najpierw na koncie płatności, a w razie potrzeby także na pozostałych kontach. Nie tworzy to przelewów między kontami. ${item!.open_ended?'Rezerwa pozostanie aktywna. Zachowamy niewykorzystane środki i stały plan miesięczny.':item!.monthly_amount!=null?'Miesięczna pula pozostanie aktywna. Niewykorzystane środki zostają na kolejne faktury.':item!.frequency==='YEARLY'?'Rozpocznie się kolejny roczny cykl.':'Rezerwa zostanie rozliczona, a nadwyżka zwolniona.'}`}</p>}
      <div className="budget-form-actions"><button type="button" className="budget-button-quiet" onClick={onCancel} disabled={busy}>Anuluj</button><button className="budget-button-primary" type="submit" disabled={busy}>{busy?'Zapisywanie…':isPlan?item?'Zapisz zmiany':'Utwórz rezerwę':heading}</button></div>
    </fieldset></form></section></div>;
}
