import {useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowRight,Target} from 'lucide-react';
import BudgetReserveFunding from './BudgetReserveFunding';
import BudgetMonthReview from './BudgetMonthReview';
import {planningApi,type ReserveMonthPlan,type CategoryPolicy,type ClosingDecision} from '../../api_planning';
import type {BudgetWorkspace} from '../../api_budget_workspace';
import {ImportDialog} from './imports/ImportUi';
import { PlanningMessages } from './PlanningUi';
import {planningMoney as money,planningDay as day,planningToday,usePlanningAction} from './planningHelpers';

function ReserveRow({row,data,reload,onManage}:{row:ReserveMonthPlan;data:BudgetWorkspace;reload:()=>Promise<void>;onManage:(mode:'ADD'|'TRANSFER'|'EDIT'|'SPEND')=>void}){
  const month=data.month;
  const monthly=row.monthly_amount!=null&&!row.open_ended;
  const openEnded=!!row.open_ended;
  const [amount,setAmount]=useState(String(row.planned)),[priority,setPriority]=useState(row.priority);
  const action=usePlanningAction(reload);
  return <form className="bp-saving-row" onSubmit={e=>{e.preventDefault();if(openEnded)return;void action.run(()=>planningApi.reservePlan(row.reserve_id,{month,amount:Number(amount),priority,version:row.version}),'Plan odłożenia zapisany.');}}>
    <div><Link to={`/budget/reserves?month=${data.month}&reserve=${row.reserve_id}`}><strong>{row.name}</strong></Link><small>{row.account_name} · {openEnded?'Bez terminu':monthly?'Miesięczna pula na media':`termin ${day(row.due_date)}`}</small><small>{data.categories.find(c=>c.id===row.category_id)?.selection_label??'Kategorię wybierzesz przy płatności'}</small><small>{openEnded?row.planned===0?'Odkładanie ręczne · bez obowiązkowej wpłaty':'Stałe odkładanie · bez automatycznego przeliczania':monthly?`Domyślnie ${money(row.monthly_amount!)} · ${row.automatic?'bez korekty':'korekta tego miesiąca'}`:`${row.automatic?'Plan automatyczny':'Własny plan'} · propozycja ${money(row.recommended)}`}</small></div>
    <label>{openEnded?'Stałe odłożenie miesięczne':monthly?'Pula w bieżącym miesiącu':'Odłóż w miesiącu'}<input required readOnly={openEnded} type="number" min="0" step="0.01" value={amount} onChange={e=>setAmount(e.target.value)} aria-label={`Plan odłożenia: ${row.name}`}/></label>
    <label>Ważność<select disabled={openEnded} value={priority} onChange={e=>setPriority(Number(e.target.value))}><option value={1}>Wysoka</option><option value={2}>Zwykła</option><option value={3}>Niska</option></select></label>
    <div className="bp-saving-progress"><span>{monthly?'Płatności i odłożenia':'Odłożono'} {money(row.funded)}</span><b>{monthly?'Jeszcze do odłożenia':'Pozostało'} {money(row.remaining)}</b><progress aria-label={`Odłożenia w miesiącu: ${row.name}`} max={Math.max(row.planned,1)} value={Math.min(row.funded,Math.max(row.planned,1))}/></div>
    {openEnded?<button className="budget-button-secondary" disabled={action.busy||!row.active} type="button" onClick={()=>onManage('EDIT')}>Zmień stałą kwotę</button>:<button className="budget-button-secondary" disabled={action.busy||!row.active||month<planningToday().slice(0,7)} type="submit">Zapisz plan</button>}
    <div className="bp-row-feedback"><PlanningMessages {...action}/>{monthly&&<p className="bp-help">Korekta dotyczy wybranego miesiąca. Jeśli kwota była już odłożona, dopłać różnicę lub zwolnij nadwyżkę w rezerwie. Faktura finansowana z wcześniejszych odłożeń nie zużywa puli ponownie.</p>}<div className="br-actions">{row.active&&month===planningToday().slice(0,7)&&<><button type="button" className="budget-button-secondary" disabled={action.busy||monthly&&row.remaining<=0} onClick={()=>onManage('ADD')}>Odłóż</button>{(monthly||openEnded)&&<button type="button" className="budget-button-secondary" disabled={action.busy} onClick={()=>onManage('SPEND')}>{openEnded?'Zapisz płatność':'Rozlicz fakturę'}</button>}{data.accounts.length>1&&<button type="button" className="budget-button-secondary" disabled={action.busy||monthly&&row.remaining<=0} onClick={()=>onManage('TRANSFER')}>Przelej i odłóż</button>}</>}<button type="button" className="budget-text-button" onClick={()=>onManage('EDIT')}>{openEnded?'Stała kwota i konto':monthly?'Kwota domyślna, kategoria i konto':'Termin, kategoria i konto'}</button></div></div>
  </form>;
}

export function BudgetReservePlans({data,reload,editing=true}:{data:BudgetWorkspace;reload:()=>Promise<void>;editing?:boolean}){
  const rows=data.planning?.reserve_plans??[];
  const [manage,setManage]=useState<{row:ReserveMonthPlan;mode:'ADD'|'TRANSFER'|'EDIT'|'SPEND'}|null>(null);
  return <section id="reserve-month-plans" className="budget-panel surface-card bp-panel">
    <div className="budget-section-heading"><div><p className="page-eyebrow">Odkładanie jest częścią planu</p><h2><Target size={20}/>Odłożenia i miesięczne pule</h2><p>Plan pomniejsza „Do zaplanowania”. Prąd i wodę możesz planować stałą kwotą z ręczną korektą miesiąca. Pula obejmuje płatności i odłożenia, bez podwójnego limitu kategorii.</p></div><Link className="budget-text-button" to={`/budget/reserves?month=${data.month}`}>Dodaj lub edytuj rezerwę<ArrowRight size={15}/></Link></div>
    <div className="bp-saving-total"><span>Zaplanowano <b>{money(rows.reduce((s,r)=>s+r.planned,0))}</b></span><span>Odłożono <b>{money(rows.reduce((s,r)=>s+(r.contributed??r.funded),0))}</b></span><span>Obciążenie puli mediów <b>{money(rows.filter(r=>r.monthly_amount!=null&&!r.open_ended).reduce((s,r)=>s+r.funded,0))}</b></span><span>Jeszcze do odłożenia <b>{money(rows.reduce((s,r)=>s+r.remaining,0))}</b></span></div>
    {rows.length?[...rows].sort((a,b)=>Number(a.monthly_amount!=null)-Number(b.monthly_amount!=null)||Number(!!a.open_ended)-Number(!!b.open_ended)).map(row=>editing?<ReserveRow key={`${row.reserve_id}-${row.version}-${row.funded}-${row.planned}`} row={row} data={data} reload={reload} onManage={mode=>setManage({row,mode})}/>:<div className="budget-reserve-read-row" key={row.reserve_id}><div><Link to={`/budget/reserves?month=${data.month}&reserve=${row.reserve_id}`}><strong>{row.name}</strong></Link><small>{row.account_name} · {row.open_ended?'Bez terminu':row.monthly_amount!=null?'Miesięczna pula':day(row.due_date)}</small></div><div><span>Plan miesiąca</span><b>{money(row.planned)}</b></div><div><span>{row.monthly_amount!=null&&!row.open_ended?'Płatności i odłożenia':'Odłożono w miesiącu'}</span><b>{money(row.monthly_amount!=null&&!row.open_ended?row.funded:row.contributed??row.funded)}</b></div><div><span>Jeszcze do odłożenia</span><b>{money(row.remaining)}</b></div>{row.active&&data.month===planningToday().slice(0,7)&&<button className="budget-button-secondary" disabled={row.monthly_amount!=null&&!row.open_ended&&row.remaining<=0} onClick={()=>setManage({row,mode:'ADD'})}>Odłóż</button>}</div>):<p className="budget-small-empty">Dodaj rezerwę na przyszły koszt albo zaplanuj większy zakup.</p>}
    <details className="budget-calculation-help"><summary>Jak liczymy plan odłożeń?</summary><p className="bp-help">Plan automatyczny wynika z brakującej kwoty i terminu. Uwzględniamy go zarówno w „Do zaplanowania”, jak i prognozie. Możesz zapisać własną kwotę, również 0 zł. Sam plan nie wykonuje wpłaty.</p></details>
    {manage&&<BudgetReserveFunding {...manage} reload={reload} onClose={()=>setManage(null)}/>}
  </section>;
}

function PolicyRow({row,data,reload}:{row:CategoryPolicy;data:BudgetWorkspace;reload:()=>Promise<void>}){
  const [mode,setMode]=useState(row.mode),[reserve,setReserve]=useState(String(row.reserve_id??''));
  const action=usePlanningAction(reload);
  const carry=data.categories.find(c=>c.id===row.category_id)?.carryover??0;
  return <form className="bp-policy-row" onSubmit={e=>{e.preventDefault();void action.run(()=>planningApi.policy(row.category_id,{mode,reserve_id:mode==='RESERVE'?Number(reserve):null,start_month:row.version?row.start_month:data.month,version:row.version}),'Zasada kategorii zapisana.');}}>
    <div><strong>{row.name}</strong>{carry>0&&<small>Przeniesiono {money(carry)}</small>}</div>
    <label>Niewykorzystany limit<select aria-label={`Zasada kategorii: ${row.name}`} value={mode} onChange={e=>setMode(e.target.value as CategoryPolicy['mode'])}><option value="RESET">Zaczynam kolejny miesiąc od nowa</option><option value="ROLLOVER">Przenoszę do limitu następnego miesiąca</option><option value="DECIDE">Zdecyduję przy zamknięciu miesiąca</option><option value="RESERVE">Zawsze odkładam na wybraną rezerwę</option></select></label>
    {mode==='RESERVE'&&<label>Rezerwa<select required value={reserve} onChange={e=>setReserve(e.target.value)}><option value="">Wybierz rezerwę</option>{data.planning?.reserve_plans.filter(r=>r.active).map(r=><option key={r.reserve_id} value={r.reserve_id}>{r.name}</option>)}</select></label>}
    <button className="budget-button-secondary" type="submit" disabled={action.busy}>Zapisz zasadę</button><div className="bp-row-feedback">{mode==='DECIDE'&&<p className="bp-help">Przy zamknięciu wybierzesz: kolejny miesiąc, oszczędności, inwestycje albo rezerwa. Do tego czasu nadwyżka nie przenosi się automatycznie.</p>}<PlanningMessages {...action}/></div>
  </form>;
}

export function BudgetCarryoverPolicies({data,reload,mode='all'}:{data:BudgetWorkspace;reload:()=>Promise<void>;mode?:'all'|'settings'|'closing'}){
  const [closing,setClosing]=useState(false),[requestId]=useState(()=>crypto.randomUUID());
  const [decisions,setDecisions]=useState<Record<string,ClosingDecision>>({});
  const action=usePlanningAction(reload),policies=data.planning?.policies??[];
  const routes=policies.filter(p=>(p.mode==='RESERVE'||p.mode==='DECIDE')&&p.start_month<=data.month).map(p=>({...p,amount:Math.max(0,data.categories.find(c=>c.id===p.category_id)?.remaining??0)}));
  const pending=routes.filter(r=>r.mode==='DECIDE'&&r.amount>0);
  const incomplete=pending.some(r=>{const d=decisions[r.category_id];return !d||(d.destination==='RESERVE'&&!d.reserve_id)||(['SAVINGS','INVESTMENTS'].includes(d.destination)&&!d.account_id);});
  const setDecision=(id:number,change:ClosingDecision)=>setDecisions(old=>({...old,[id]:change}));
  return <section className="budget-panel surface-card bp-panel">
    <div className="budget-section-heading"><div><p className="page-eyebrow">Niewykorzystane limity</p><h2>{mode==='closing'?'Sprawdź i zamknij miesiąc':'Co przechodzi na kolejny miesiąc?'}</h2><p>Zasada obejmuje kategorię główną razem z jej podkategoriami. Przekroczenie limitu nie tworzy dodatniej kwoty do przeniesienia.</p></div></div>
    {mode!=='closing'&&<>{policies.map(row=><PolicyRow key={`${row.category_id}-${row.version}-${data.month}`} row={row} data={data} reload={reload}/>)}
    <p className="bp-help">Przeniesiony limit nie jest dochodem i nie zmienia salda. Do zamknięcia miesiąca kwota przeniesienia przelicza się po korektach. Po zamknięciu zachowujemy zatwierdzony limit i pokazujemy późniejsze różnice. Odłożenie na rezerwę korzysta z faktycznie wolnych pieniędzy w dniu zamknięcia.</p>
    </>}
    {mode!=='settings'&&<>
    <BudgetMonthReview data={data}/>
    {data.planning?.closing.id?<><p className="budget-feedback is-success">Miesiąc zamknięty. Odłożenia nie będą zapisane ponownie.</p><ul className="bp-closing-list">{data.planning.closing_items?.map(r=><li key={r.category_id}><span>{r.name} → {r.destination==='ROLLOVER'?'limit kolejnego miesiąca':r.destination==='RESET'?'bez przeniesienia':r.reserve_name??r.destination}</span><b>{money(r.amount)}</b></li>)}</ul></>:data.month<planningToday().slice(0,7)&&<button className="budget-button-primary" onClick={()=>setClosing(true)}>Zamknij miesiąc i rozlicz limity</button>}
    <PlanningMessages {...action}/>
    {closing&&<ImportDialog title={`Zamknij miesiąc ${data.month}`} busy={action.busy} onClose={()=>setClosing(false)}>
      <BudgetMonthReview data={data}/>
      {pending.map(r=>{const choice=decisions[r.category_id];return <div className="bp-closing-decision" key={r.category_id}><h3>{r.name} · {money(r.amount)} do rozdysponowania</h3><label>Przeznaczenie<select aria-label={`Przeznaczenie limitu: ${r.name}`} value={choice?.destination??''} onChange={e=>setDecision(r.category_id,{destination:e.target.value as ClosingDecision['destination']})}><option value="">Wybierz przy zamknięciu</option><option value="ROLLOVER">Limit kolejnego miesiąca</option><option value="SAVINGS">Oszczędności</option><option value="INVESTMENTS">Środki na inwestycje</option><option value="RESERVE">Wybrana rezerwa</option><option value="RESET">Bez przeniesienia — pozostaw wolne</option></select></label>{choice?.destination==='RESERVE'&&<label>Rezerwa<select aria-label={`Rezerwa dla limitu: ${r.name}`} value={choice.reserve_id??''} onChange={e=>setDecision(r.category_id,{...choice,reserve_id:Number(e.target.value)})}><option value="">Wybierz rezerwę</option>{data.planning?.reserve_plans.filter(p=>p.active).map(p=><option key={p.reserve_id} value={p.reserve_id}>{p.name} · {p.account_name}</option>)}</select></label>}{choice&&['SAVINGS','INVESTMENTS'].includes(choice.destination)&&<label>Konto z pieniędzmi<select aria-label={`Konto dla limitu: ${r.name}`} value={choice.account_id??''} onChange={e=>setDecision(r.category_id,{...choice,account_id:Number(e.target.value)})}><option value="">Wybierz konto</option>{data.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>}</div>;})}
      <p className="bp-help">Oszczędności i inwestycje wydzielimy jako rezerwy bez terminu, ze stałą wpłatą 0 zł. Nie zmieniamy salda konta i nie kupujemy instrumentów. Przelew zapiszesz osobno. Jeśli brakuje wolnych pieniędzy na wybranym koncie, zamknięcie nie zostanie zapisane.</p>
      <p>Zapisz poniższe odłożenia z wolnych środków kont przypisanych do rezerw. Datą odłożenia będzie dzisiejszy dzień.</p>
      <ul className="bp-closing-list">{routes.filter(r=>r.mode==='RESERVE').map(r=><li key={r.category_id}><span>{r.name} → {data.planning?.reserve_plans.find(p=>p.reserve_id===r.reserve_id)?.name}</span><b>{money(r.amount)}</b></li>)}</ul>
      {!routes.length&&<p>Brak kategorii kierujących środki do rezerwy. Zapiszemy wyłącznie zamknięcie miesiąca.</p>}
      <PlanningMessages {...action}/><div className="budget-form-actions"><button className="budget-button-quiet" disabled={action.busy} onClick={()=>setClosing(false)}>Anuluj</button><button className="budget-button-primary" disabled={action.busy||incomplete} onClick={()=>void action.run(()=>planningApi.closeMonth(data.month,Object.fromEntries(routes.map(r=>[String(r.category_id),r.version])),requestId,Object.fromEntries(routes.map(r=>[String(r.category_id),r.amount])),data.planning?.month_review?.token,decisions),'Miesiąc zamknięty.',()=>setClosing(false))}>Potwierdź zamknięcie</button></div>
    </ImportDialog>}
    </>}
  </section>;
}
