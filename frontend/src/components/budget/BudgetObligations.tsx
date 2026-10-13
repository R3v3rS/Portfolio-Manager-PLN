import BudgetSettlementUndo from './BudgetSettlementUndo';
import {Fragment,useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {CalendarDays,Check,CircleAlert,Pause,Pencil,Play,Plus} from 'lucide-react';
import {budgetWorkspaceApi,type BudgetBill,type BillInput,type BudgetWorkspace} from '../../api_budget_workspace';
import {ImportDialog} from './imports/ImportUi';
import { PlanningMessages } from './PlanningUi';
import {planningMoney as money,planningDay as day,planningToday,usePlanningAction} from './planningHelpers';

const frequencyNames={MONTHLY:'Co miesiąc',QUARTERLY:'Co kwartał',YEARLY:'Co roku',ONCE:'Jednorazowo'};
function billInput(bill:BudgetBill,month:string):BillInput{
  return {title:bill.title,amount:bill.base_amount??bill.amount,account_id:bill.account_id,category_id:bill.category_id,
    due_day:bill.due_day??Number(bill.due_date.slice(-2)),frequency:bill.frequency,start_month:bill.start_month??month,due_month:bill.due_month??month,
    end_month:bill.end_month,promotion_end:bill.promotion_end,notice_date:bill.notice_date,regular_amount:bill.regular_amount,
    variable_amount:bill.variable_amount??false,notes:bill.notes??'',reserve_id:bill.reserve_id??null,version:bill.version};
}

export function BillEditor({data,bill,reload,onClose,categoryId}:{data:BudgetWorkspace;bill:BudgetBill|null;reload:()=>Promise<void>;onClose:()=>void;categoryId?:number}){
  const [input,setInput]=useState<BillInput>(()=>bill?billInput(bill,data.month):{title:'',amount:0,due_day:data.month===planningToday().slice(0,7)?Number(planningToday().slice(-2)):1,frequency:'ONCE',start_month:data.month,due_month:data.month,account_id:data.accounts[0]?.id??0,category_id:categoryId??data.categories.find(c=>c.name==='Rachunki')?.id??data.categories.find(c=>!c.is_unassigned)?.id??0,variable_amount:false,notes:'',reserve_id:null});
  const [requestId]=useState(()=>crypto.randomUUID()),action=usePlanningAction(reload);
  const update=<K extends keyof BillInput>(key:K,value:BillInput[K])=>setInput(old=>({...old,[key]:value}));
  const oneOff=input.frequency==='ONCE';
  const paymentMonth=input.due_month??data.month;
  const [year,month]=paymentMonth.split('-').map(Number);
  const paymentDate=`${paymentMonth}-${String(Math.max(1,Math.min(input.due_day,new Date(year,month,0).getDate()))).padStart(2,'0')}`;
  return <ImportDialog title={bill?'Edytuj zobowiązanie':'Nowe zobowiązanie'} busy={action.busy} onClose={onClose}>
    <PlanningMessages {...action}/><form className="bp-editor" onSubmit={e=>{e.preventDefault();void action.run(()=>bill?budgetWorkspaceApi.updateBill(bill.id,input):budgetWorkspaceApi.createBill({...input,request_id:requestId}),'Zobowiązanie zapisane.',onClose);}}>
      <label>Nazwa<input required maxLength={150} value={input.title} onChange={e=>update('title',e.target.value)} placeholder="np. Internet, OC auta"/></label>
      <fieldset className="bp-bill-type"><legend>Rodzaj rachunku</legend><label><input type="radio" name="bill-type" checked={oneOff} onChange={()=>setInput(old=>({...old,frequency:'ONCE',end_month:null,promotion_end:null,regular_amount:null,notice_date:null}))}/><span><strong>Jednorazowy</strong><small>Jedna płatność, np. zakup lub prezent.</small></span></label><label><input type="radio" name="bill-type" checked={!oneOff} onChange={()=>update('frequency','MONTHLY')}/><span><strong>Powtarzalny</strong><small>Regularna opłata, np. czynsz lub telefon.</small></span></label></fieldset>
      <div className="budget-form-grid"><label>Kwota w PLN<input type="number" required min="0.01" step="0.01" value={input.amount||''} onChange={e=>update('amount',Number(e.target.value))}/></label>{oneOff?<label>Termin płatności<input required type="date" value={paymentDate} onChange={e=>{const value=e.target.value;if(value)setInput(old=>({...old,due_month:value.slice(0,7),due_day:Number(value.slice(-2))}));}}/></label>:<label>Dzień płatności<input type="number" required min="1" max="31" value={input.due_day} onChange={e=>update('due_day',Number(e.target.value))}/></label>}</div>
      {!oneOff&&<><label>Powtarzalność<select value={input.frequency} onChange={e=>update('frequency',e.target.value as BillInput['frequency'])}>{Object.entries(frequencyNames).filter(([value])=>value!=='ONCE').map(([value,name])=><option key={value} value={value}>{name}</option>)}</select></label><div className="budget-form-grid"><label>Pierwszy miesiąc<input type="month" required value={input.start_month} onChange={e=>update('start_month',e.target.value)}/></label><label>Ostatni miesiąc — opcjonalnie<input type="month" min={input.start_month} value={input.end_month??''} onChange={e=>update('end_month',e.target.value||null)}/></label></div></>}
      <label>Konto płatności<select required value={input.account_id} onChange={e=>update('account_id',Number(e.target.value))}>{data.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label>Kategoria<select required value={input.category_id} onChange={e=>update('category_id',Number(e.target.value))}>{data.categories.filter(c=>!c.is_unassigned).map(c=><option key={c.id} value={c.id}>{c.selection_label??c.name}</option>)}</select></label>
      <p className="bp-help">Rachunek pojawi się w planie tej kategorii i jej kategorii głównej. Jego kwota mieści się w limicie kategorii; podwyższy plan tylko wtedy, gdy przypisane płatności lub podkategorie przekroczą wspólny limit.</p>
      <label className="bp-checkbox"><input type="checkbox" checked={input.variable_amount??false} onChange={e=>update('variable_amount',e.target.checked)}/>Kwota jest szacunkowa — przy płatności podam rzeczywistą</label>
      {!oneOff&&<details className="bp-details" open={!!input.promotion_end||!!input.notice_date}><summary>Promocja i termin wypowiedzenia</summary><div className="budget-form-grid"><label>Koniec promocji<input type="date" value={input.promotion_end??''} onChange={e=>update('promotion_end',e.target.value||null)}/></label><label>Kwota po promocji<input type="number" min="0.01" step="0.01" required={!!input.promotion_end} value={input.regular_amount??''} onChange={e=>update('regular_amount',e.target.value?Number(e.target.value):null)}/></label></div><label>Termin wypowiedzenia<input type="date" value={input.notice_date??''} onChange={e=>update('notice_date',e.target.value||null)}/></label></details>}
      <label>Finansowanie z rezerwy — opcjonalnie<select value={input.reserve_id??''} onChange={e=>update('reserve_id',e.target.value?Number(e.target.value):null)}><option value="">Z bieżącego budżetu</option>{data.planning?.reserve_plans.filter(r=>r.active).map(r=><option key={r.reserve_id} value={r.reserve_id}>{r.name}</option>)}</select></label>
      {input.reserve_id&&<p className="bp-help">{data.planning?.reserve_plans.find(r=>r.reserve_id===input.reserve_id)?.open_ended?'Płatność korzysta z rezerwy bez terminu. Nie zmieni stałej kwoty odkładania.':data.planning?.reserve_plans.find(r=>r.reserve_id===input.reserve_id)?.monthly_amount!=null?'Dla miesięcznej puli wybierz tę samą kategorię. Faktura może mieć inną kwotę i dowolną częstotliwość, np. kwartalną.':'Kwota, pierwszy termin i powtarzalność muszą odpowiadać rezerwie.'} Płatność zapisze jeden wydatek i rozliczy odłożone środki.</p>}
      <label>Notatka<textarea maxLength={2000} value={input.notes??''} onChange={e=>update('notes',e.target.value)}/></label>
      <div className="budget-form-actions"><button className="budget-button-quiet" type="button" disabled={action.busy} onClick={onClose}>Anuluj</button><button type="submit" className="budget-button-primary" disabled={action.busy}>Zapisz zobowiązanie</button></div>
    </form>
  </ImportDialog>;
}

export function BillPayment({data,bill,reload,onClose}:{data:BudgetWorkspace;bill:BudgetBill;reload:()=>Promise<void>;onClose:()=>void}){
  const suggestions=bill.payment_candidates??[];
  const candidates=[...suggestions,...data.entries.filter(e=>e.kind==='EXPENSE'&&e.account_id===bill.account_id&&!e.bill_id&&!e.loan_id&&!e.reserve_id&&(bill.variable_amount||Math.round(e.amount*100)===Math.round(bill.amount*100))&&!suggestions.some(c=>c.id===e.id)).map(e=>({id:e.id,date:e.date,description:e.description,amount:e.amount,version:e.version??1}))];
  const [existing,setExisting]=useState(String(suggestions[0]?.id??'')),[separate,setSeparate]=useState(false);
  const [amount,setAmount]=useState(String(suggestions[0]?.amount??bill.amount)),[date,setDate]=useState(suggestions[0]?.date??(data.month===planningToday().slice(0,7)?planningToday():data.month+'-01'));
  const [requestId]=useState(()=>crypto.randomUUID()),action=usePlanningAction(reload);
  const selected=candidates.find(c=>String(c.id)===existing),account=data.accounts.find(a=>a.id===bill.account_id);
  const selectedEntry=data.entries.find(e=>e.id===selected?.id);
  const unassigned=selectedEntry?.classification_status==='UNASSIGNED';
  const categoryMismatch=!!selectedEntry&&!unassigned&&(!selectedEntry.lines.length||selectedEntry.lines.some(line=>line.category_id!==bill.category_id));
  const categoryLabel=data.categories.find(c=>c.id===bill.category_id)?.selection_label??bill.category_name;
  return <ImportDialog title={`Zapisz opłacenie: ${bill.title}`} busy={action.busy} onClose={onClose}>
    <p className="bp-help">Finansowanie: {bill.funding_source??'Wolne środki'} · pokrycie z rezerwy {money(Math.min(Number(amount)||0,bill.reserve_covered??0))} · poza rezerwą {money(Math.max(0,(Number(amount)||0)-(bill.reserve_covered??0)))}. {Number(amount)>(bill.base_amount??bill.amount)&&`Kwota wyższa od planu o ${money(Number(amount)-(bill.base_amount??bill.amount))}; uwzględnimy rzeczywistą płatność.`}</p><p>Rozlicz płatność z konta {bill.account_name}. {bill.reserve_id&&'Rozliczymy także powiązaną rezerwę.'}</p><PlanningMessages {...action}/>
    <p className="bp-payment-purpose"><strong>Rozliczasz istniejący plan: {bill.title}.</strong> {selected?'Dołączysz zakup już zapisany w historii.':'Zapiszesz rzeczywistą płatność do tego rachunku.'} Nie dodajesz nowego zobowiązania w planie.</p>
    <form className="bp-editor" onSubmit={e=>{e.preventDefault();void action.run(()=>budgetWorkspaceApi.payBill(bill.id,data.month,date,{amount:Number(amount),version:bill.version,reserve_version:bill.reserve_version??undefined,request_id:requestId,existing_entry_id:selected?.id,entry_version:selected?.version,confirm_separate:separate,expected_balance:account?.balance}),selected?'Powiązano istniejącą płatność. Saldo bez zmian.':'Płatność zapisana.',onClose);}}>
      <label>Powiązanie z istniejącą transakcją<select value={existing} onChange={e=>{setExisting(e.target.value);setSeparate(false);const candidate=candidates.find(c=>String(c.id)===e.target.value);if(candidate){setAmount(String(candidate.amount));setDate(candidate.date);}}}><option value="">Nowa płatność — pomniejsz saldo</option>{candidates.map(c=><option key={c.id} value={c.id}>{c.description} · {day(c.date)} · {money(c.amount)}</option>)}</select></label>
      {selected&&<p className="bp-help">Istniejący wydatek #{selected.id} zostanie przypisany do rachunku. Nie tworzymy kolejnego wydatku ani obciążenia konta.</p>}
      {unassigned&&<p className="bp-help">Nieprzypisany wydatek otrzyma kategorię rachunku: <strong>{categoryLabel}</strong>. Cofnięcie rozliczenia przywróci poprzednią kategorię.</p>}
      {categoryMismatch&&<p role="alert" className="budget-negative">Ten wydatek ma inną kategorię. Przed powiązaniem przypisz cały wydatek do „{categoryLabel}”, aby plan nie liczył kosztu ponownie. <Link to={`/budget?view=entries&month=${data.month}`}>Popraw kategorię wydatku</Link></p>}
      {!selected&&candidates.length>0&&<label className="bp-checkbox"><input required type="checkbox" checked={separate} onChange={e=>setSeparate(e.target.checked)}/>To osobna płatność, mimo znalezionego podobnego wydatku</label>}
      <label>Zapłacona kwota w PLN<input disabled={!!selected} required type="number" min="0.01" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)}/></label><label>Data płatności<input disabled={!!selected} required type="date" min={data.month+'-01'} max={planningToday()} value={date} onChange={e=>setDate(e.target.value)}/></label>
      {account&&<div className="bp-balance-preview">{account.name}: <b>{money(account.balance)} → {money(account.balance-(selected?0:Number(amount)||0))}</b><small>{selected?'Powiązanie zachowuje saldo.':'Nowa płatność zmniejszy saldo.'}</small>{!selected&&account.balance<Number(amount)&&<strong className="budget-negative">Na tym koncie brakuje {money(Number(amount)-account.balance)}.</strong>}</div>}
      <div className="budget-form-actions"><button className="budget-button-quiet" type="button" onClick={onClose} disabled={action.busy}>Anuluj</button><button className="budget-button-primary" type="submit" disabled={action.busy||categoryMismatch||(!selected&&candidates.length>0&&!separate)}>{selected?'Powiąż płatność':'Zapisz opłacenie'}</button></div>
    </form>
  </ImportDialog>;
}

export default function BudgetObligations({data,reload}:{data:BudgetWorkspace;reload:()=>Promise<void>}){
  const [params,setParams]=useSearchParams();
  const requestedBill=params.get('bill');
  const [scope,setScope]=useState<'MONTH'|'ALL'>('MONTH'),[inactive,setInactive]=useState(false),[editing,setEditing]=useState<BudgetBill|null|undefined>(undefined),[paying,setPaying]=useState<BudgetBill|null>(null);
  const [kind,setKind]=useState<'ALL'|'ONCE'|'RECURRING'>('ALL');
  const [undo,setUndo]=useState<number|null>(null);
  useEffect(()=>{
    if(!requestedBill)return;
    const bill=data.bills.find(item=>String(item.id)===requestedBill);
    if(!bill)return;
    if(bill.status!=='PAID'&&data.month<=planningToday().slice(0,7))setPaying(bill);
    setParams(current=>{const next=new URLSearchParams(current);next.delete('bill');return next;},{replace:true});
  },[requestedBill,data.bills,data.month,setParams]);
  const action=usePlanningAction(reload);
  const catalog=data.planning?.bill_catalog??data.bills;
  const rows=(scope==='MONTH'?data.bills:catalog).filter(b=>(inactive||b.active!==false)&&(kind==='ALL'||(kind==='ONCE')===(b.frequency==='ONCE'))).sort((a,b)=>Number(b.frequency==='ONCE')-Number(a.frequency==='ONCE'));
  const paidRows=scope==='MONTH'?rows.filter(b=>b.status==='PAID'):[];
  const pendingRows=scope==='MONTH'?rows.filter(b=>b.status!=='PAID'):rows;
  const renderRows=(items:typeof rows)=>items.map((bill,index)=>{
      const occurrence=data.bills.find(b=>b.id===bill.id),date=occurrence?.due_date??bill.next_due_date;
      return <Fragment key={bill.id}>{(index===0||(items[index-1].frequency==='ONCE')!==(bill.frequency==='ONCE'))&&<h3 className="bp-bill-group">{bill.frequency==='ONCE'?'Rachunki jednorazowe':'Rachunki powtarzalne'}</h3>}<article className={`bp-obligation ${occurrence?.status==='OVERDUE'?'is-overdue':occurrence?.status==='PAID'?'is-paid':''}`}>
        <div className="bp-obligation-date"><CalendarDays size={18}/><span>{date?day(date):'Brak kolejnego terminu'}</span></div>
        <div className="bp-obligation-main"><h3>{bill.title}</h3><span className="bp-bill-kind">{bill.frequency==='ONCE'?'Jednorazowy':'Powtarzalny'}</span><p>{frequencyNames[bill.frequency]} · {bill.account_name}</p><span className={`budget-bill-status ${bill.active===false?'is-paused':occurrence?.status==='PAID'?'is-paid':occurrence?.status==='OVERDUE'?'is-overdue':'is-pending'}`}>{bill.active===false?<Pause size={14}/>:occurrence?.status==='PAID'?<Check size={14}/>:occurrence?.status==='OVERDUE'?<CircleAlert size={14}/>:<CalendarDays size={14}/>} {bill.active===false?'Wstrzymany':occurrence?.status==='PAID'?'Opłacony':occurrence?.status==='OVERDUE'?'Po terminie':'Do zapłaty'}</span>{bill.variable_amount&&<small>Kwota szacunkowa</small>}{bill.reserve_id&&<Link to={`/budget/reserves?reserve=${bill.reserve_id}`}>Finansuje rezerwa: {bill.reserve_name}</Link>}{bill.promotion_end&&<small>Promocja do {day(bill.promotion_end)} · potem {money(bill.regular_amount??bill.amount)}</small>}{bill.notice_date&&<small className="bp-deadline">Wypowiedzenie do {day(bill.notice_date)}</small>}</div>
        <div className="bp-obligation-money"><small>{bill.funding_source}</small>{bill.reserve_id&&<small>Z rezerwy {money(bill.reserve_covered??0)} · z wolnych środków {money(bill.unfunded??bill.amount)}</small>}<b>{money(occurrence?.amount??bill.amount)}</b><small>{bill.frequency==='ONCE'?'Jedna płatność — bez powtarzania':`Plan na 12 miesięcy ${money(bill.annual_cost??bill.amount)}`}</small></div>
        <div className="bp-obligation-actions">{occurrence?.status==='PAID'&&occurrence.entry_id&&<button className="budget-button-secondary" onClick={()=>setUndo(occurrence.entry_id)}>Cofnij rozliczenie</button>}{!!occurrence?.payment_candidates?.length&&<button className="budget-button-primary" onClick={()=>setPaying(occurrence)}>Znaleziono płatność — powiąż</button>}{occurrence&&occurrence.status!=='PAID'&&data.month<=planningToday().slice(0,7)&&<button className="budget-button-secondary" disabled={action.busy} onClick={()=>setPaying(occurrence)}><Check size={15}/>Zapisz opłacenie</button>}<button className="budget-icon-button" aria-label={`Edytuj zobowiązanie: ${bill.title}`} disabled={action.busy} onClick={()=>setEditing(bill)}><Pencil size={16}/></button><button className="budget-icon-button" aria-label={`${bill.active===false?'Przywróć':'Wstrzymaj'} zobowiązanie: ${bill.title}`} disabled={action.busy} onClick={()=>void action.run(()=>budgetWorkspaceApi.updateBill(bill.id,{...billInput(bill,data.month),active:bill.active===false}),bill.active===false?'Zobowiązanie przywrócone.':'Zobowiązanie wstrzymane.')}>{bill.active===false?<Play size={16}/>:<Pause size={16}/>}</button></div>
      </article></Fragment>;
    });
  return <section className="budget-panel surface-card bp-panel">
    <div className="budget-section-heading"><div><p className="page-eyebrow">Rachunki i subskrypcje</p><h2>Zobowiązania pod kontrolą</h2><p>Terminy, koszt kolejnych 12 miesięcy, promocje i finansowanie z rezerw w jednym miejscu.</p></div><button className="budget-button-primary" disabled={action.busy} onClick={()=>setEditing(null)}><Plus size={17}/>Dodaj zobowiązanie</button></div>
    <div className="bp-toolbar"><div className="bp-switch"><button aria-pressed={scope==='MONTH'} onClick={()=>setScope('MONTH')}>Wybrany miesiąc</button><button aria-pressed={scope==='ALL'} onClick={()=>setScope('ALL')}>Wszystkie zobowiązania</button></div><label>Rodzaj rachunków<select value={kind} onChange={e=>setKind(e.target.value as typeof kind)}><option value="ALL">Wszystkie rodzaje</option><option value="ONCE">Jednorazowe</option><option value="RECURRING">Powtarzalne</option></select></label><label className="bp-checkbox"><input type="checkbox" checked={inactive} onChange={e=>setInactive(e.target.checked)}/>Pokaż wstrzymane</label></div><PlanningMessages {...action}/><div className="bp-help">{data.bills.filter(b=>b.status!=='PAID'&&b.payment_candidates?.length).length>0&&<p><strong>Do powiązania: {data.bills.filter(b=>b.status!=='PAID'&&b.payment_candidates?.length).length} rachunków.</strong> Wybierz „Znaleziono płatność — powiąż”, aby rozliczyć import bez kolejnego obciążenia.</p>}</div>
    {!rows.length?<p className="budget-small-empty">Brak zobowiązań w tym widoku.</p>:<>
      <div className="bp-obligations">{renderRows(pendingRows)}</div>
      {scope==='MONTH'&&pendingRows.length===0&&<p className="budget-small-empty">Wszystkie rachunki w tym widoku są opłacone.</p>}
      {paidRows.length>0&&<details className="budget-paid-bills"><summary><Check size={16}/>Opłacone rachunki ({paidRows.length}) · {money(paidRows.reduce((sum,b)=>sum+b.amount,0))}</summary><div className="bp-obligations">{renderRows(paidRows)}</div></details>}
    </>}

    {undo&&<BudgetSettlementUndo entryId={undo} reload={reload} onClose={()=>setUndo(null)}/>}
    {editing!==undefined&&<BillEditor key={editing?.id??'new'} data={data} bill={editing} reload={reload} onClose={()=>setEditing(undefined)}/>}{paying&&<BillPayment data={data} bill={paying} reload={reload} onClose={()=>setPaying(null)}/>}
  </section>;
}
