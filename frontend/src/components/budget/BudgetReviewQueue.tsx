import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {budgetImportsApi,type BudgetImportsWorkspace} from '../../api_budget_imports';
import type {BudgetWorkspace} from '../../api_budget_workspace';
import type {CashForecast} from '../../api_forecast';
import {planningMoney as money,planningDay as day,planningToday} from './planningHelpers';

type Task={key:string;kind:'PAYMENT'|'DATA'|'ACCOUNT'|'PLAN';name:string;detail:string;href:string;action:string;priority:number;date?:string};
export default function BudgetReviewQueue({data,forecast}:{data:BudgetWorkspace;forecast:CashForecast|null}){
  const [imports,setImports]=useState<BudgetImportsWorkspace|null>(null),[failed,setFailed]=useState(false),[loading,setLoading]=useState(true);
  const [filter,setFilter]=useState('ALL'),[expanded,setExpanded]=useState(false);
  useEffect(()=>{let active=true;setFailed(false);setLoading(true);setImports(null);budgetImportsApi.get().then(next=>{if(active)setImports(next);}).catch(()=>{if(active)setFailed(true);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[data.month,data.entries]);
  useEffect(()=>{setExpanded(false);setFilter('ALL');},[data.month]);
  const month=data.month,today=planningToday();
  const tasks=new Map<string,Task>();
  const add=(task:Task)=>tasks.set(task.key,task);
  for(const account of forecast?.account_forecasts??[]){
    const date=account.summaries[0]?.first_shortfall;
    if(account.account_type!=='CREDIT_CARD'&&date?.slice(0,7)===month)add({key:`shortfall:${account.id}`,kind:'ACCOUNT',name:`Sprawdź środki na ${account.name}`,detail:`Prognozowany niedobór od ${day(date)}.`,href:`/budget/forecast?month=${month}`,action:'Sprawdź konto',priority:0,date});
  }
  for(const bill of data.bills??[]){
    if(bill.status==='PAID')continue;
    const matched=!!bill.payment_candidates?.length||data.planning?.payment_matches?.some(m=>m.kind==='BILL'&&m.id===bill.id&&m.candidates.length);
    add({key:`bill:${bill.id}`,kind:'PAYMENT',name:bill.title,detail:`${money(bill.amount)} · ${day(bill.due_date)} · ${bill.account_name}${matched?' · znaleziono istniejącą płatność':''}`,href:`/budget?view=bills&month=${month}&bill=${bill.id}`,action:matched?'Powiąż płatność':'Rozlicz rachunek',priority:bill.due_date<today?1:matched?2:3,date:bill.due_date});
  }
  for(const loan of data.planning?.loans??[]){
    if(!loan.paid)add({key:`loan:${loan.id}:${loan.installment_month}`,kind:'PAYMENT',name:`Rata: ${loan.name}`,detail:`${money(loan.amount)} · ${day(loan.date)} · ${data.accounts?.find(a=>a.id===loan.account_id)?.name??'Sprawdź konto spłaty'}`,href:`/loans/${loan.id}?installment=${loan.installment_month}`,action:'Sprawdź spłatę',priority:loan.date<today?1:3,date:loan.date});
  }
  for(const reserve of data.planning?.reserve_plans??[]){
    if(reserve.active!==false&&reserve.remaining>0)add({key:`reserve:${reserve.reserve_id}`,kind:'PAYMENT',name:`Odłóż: ${reserve.name}`,detail:`Do wykonania w ${month}: ${money(reserve.remaining)}.`,href:`/budget/reserves?reserve=${reserve.reserve_id}&month=${month}`,action:'Odłóż środki',priority:4});
  }
  for(const match of data.planning?.payment_matches??[]){
    if(!match.candidates.length)continue;
    const key=match.kind==='BILL'?`bill:${match.id}`:`reserve:${match.id}`;
    if(match.kind==='BILL'&&tasks.has(key))continue;
    // Replace an ordinary funding reminder for this reserve with its matching task.
    add({key,kind:'PAYMENT',name:`Sprawdź powiązanie: ${match.title}`,detail:'Znaleziono istniejący wydatek. Potwierdź powiązanie, aby nie zapisywać drugiej płatności.',href:match.kind==='BILL'?`/budget?view=bills&month=${month}&bill=${match.id}`:`/budget/reserves?reserve=${match.id}&month=${month}`,action:'Sprawdź powiązanie',priority:2});
  }
  const unassigned=imports?.pending_count??data.entries.filter(e=>e.classification_status==='UNASSIGNED').length;
  if(unassigned)add({key:'categories',kind:'DATA',name:`${unassigned} zakupów bez kategorii`,detail:`Już zapisane wydatki${imports?' · wszystkie miesiące':''}. Przypisanie nie zmienia salda.`,href:`/budget/imports?tab=pending&month=${month}`,action:'Przypisz kategorie',priority:3});
  for(const session of imports?.sessions??[])if(session.status==='PENDING')add({key:`import:${session.id}`,kind:'DATA',name:`Import: ${session.filename}`,detail:'Operacje czekają na sprawdzenie przed zatwierdzeniem.',href:`/budget/imports?tab=csv&session_id=${session.id}&month=${month}`,action:'Sprawdź import',priority:3});
  for(const receipt of imports?.receipts??[])if(receipt.status==='PENDING')add({key:`receipt:${receipt.id}`,kind:'DATA',name:`Paragon: ${receipt.filename}`,detail:'Sprawdź odczyt, kwotę i powiązanie z zakupem.',href:`/budget/imports?tab=receipt&receipt_id=${receipt.id}&month=${month}`,action:'Sprawdź paragon',priority:3});
  for(const account of data.planning?.month_review?.accounts??[])if(!account.verified_on)add({key:`account:${account.id}`,kind:'ACCOUNT',name:`Potwierdź saldo: ${account.name}`,detail:'Porównaj stan zapisów z bankiem lub gotówką.',href:`/budget/accounts?month=${month}`,action:'Sprawdź saldo',priority:4});
  if(forecast?.month_plans?.some(r=>r.categories.some(c=>c.source==='ESTIMATE')))add({key:'forecast',kind:'PLAN',name:'Uzupełnij założenia prognozy',detail:'Przyszłe miesiące zawierają szacunkowe limity.',href:`/budget/forecast?month=${month}&section=basis`,action:'Sprawdź założenia',priority:5});
  const rows=[...tasks.values()].sort((a,b)=>a.priority-b.priority||(a.date??'9999').localeCompare(b.date??'9999')||a.name.localeCompare(b.name,'pl'));
  const filtered=rows.filter(row=>filter==='ALL'||row.kind===filter),shown=expanded?filtered:filtered.slice(0,3);
  return <section className="budget-panel surface-card budget-review-queue budget-unified-tasks" aria-label="Do zrobienia">
    <div className="budget-section-heading"><div><h2>Do zrobienia <span className="budget-count">{rows.length}</span></h2></div><label>Rodzaj spraw<select aria-label="Rodzaj spraw" value={filter} onChange={e=>{setFilter(e.target.value);setExpanded(false);}}><option value="ALL">Wszystkie sprawy</option><option value="PAYMENT">Płatności i odłożenia</option><option value="DATA">Importy i kategorie</option><option value="ACCOUNT">Salda kont</option><option value="PLAN">Założenia planu</option></select></label></div>
    {failed&&<p role="status">Nie udało się odczytać stanu importów. <Link to={`/budget/imports?month=${month}`}>Sprawdź importy</Link></p>}
    {shown.length?<ul className="budget-task-list">{shown.map(row=><li key={row.key}><div><strong>{row.name}</strong><small>{row.detail}</small></div><Link className="budget-text-button" to={row.href}>{row.action}</Link></li>)}</ul>:<p className="budget-small-empty">{loading?'Sprawdzanie importów…':failed?'W załadowanych danych nie ma spraw tego rodzaju. Stan importów nie został potwierdzony.':'Brak spraw tego rodzaju.'}</p>}
    {filtered.length>3&&<div className="budget-ranking-footer"><small>Pokazano {shown.length} z {filtered.length} spraw.</small><button type="button" className="budget-text-button" onClick={()=>setExpanded(!expanded)}>{expanded?'Zwiń do 3 spraw':`Pokaż wszystkie (${filtered.length})`}</button></div>}
    <details className="budget-task-context"><summary>Zakres listy</summary><p>Płatności i odłożenia dotyczą wybranego miesiąca. Importy, paragony i zakupy do przypisania obejmują wszystkie miesiące.</p></details>
  </section>;
}
