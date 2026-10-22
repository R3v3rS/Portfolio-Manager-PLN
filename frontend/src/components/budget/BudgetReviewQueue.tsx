import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {budgetImportsApi,type BudgetImportsWorkspace} from '../../api_budget_imports';
import type {BudgetWorkspace} from '../../api_budget_workspace';
import type {CashForecast} from '../../api_forecast';
import {planningMoney as money} from './planningHelpers';

export default function BudgetReviewQueue({data,forecast}:{data:BudgetWorkspace;forecast:CashForecast|null}){
  const [imports,setImports]=useState<BudgetImportsWorkspace|null>(null),[failed,setFailed]=useState(false),[filter,setFilter]=useState('ALL');
  useEffect(()=>{let active=true;setFailed(false);budgetImportsApi.get().then(next=>{if(active)setImports(next);}).catch(()=>{if(active)setFailed(true);});return()=>{active=false;};},[data.month,data.entries]);
  const month=data.month;
  const rows:{key:string;kind:string;name:string;detail:string;href:string}[]=[];
  const unassigned=imports?.pending_count??data.entries.filter(e=>e.classification_status==='UNASSIGNED').length;
  if(unassigned)rows.push({key:'categories',kind:'DATA',name:`${unassigned} zakupów bez kategorii`,detail:'Już zapisane wydatki — przypisanie kategorii nie zmienia salda.',href:`/budget/imports?tab=pending&month=${month}`});
  for(const session of imports?.sessions.filter(s=>s.status==='PENDING')??[])rows.push({key:`import:${session.id}`,kind:'DATA',name:`Import: ${session.filename}`,detail:'Operacje czekają na sprawdzenie przed zatwierdzeniem.',href:`/budget/imports?tab=csv&session_id=${session.id}&month=${month}`});
  for(const receipt of imports?.receipts.filter(r=>r.status==='PENDING')??[])rows.push({key:`receipt:${receipt.id}`,kind:'DATA',name:`Paragon: ${receipt.filename}`,detail:'Sprawdź odczyt, kwotę i powiązanie z zakupem.',href:`/budget/imports?tab=receipt&receipt_id=${receipt.id}&month=${month}`});
  for(const match of data.planning?.payment_matches??[])if(match.candidates.length)rows.push({key:`match:${match.kind}:${match.id}`,kind:'PAYMENT',name:`Sprawdź powiązanie: ${match.title}`,detail:'Propozycja wymaga potwierdzenia; nie dodawaj drugiej płatności.',href:match.kind==='BILL'?`/budget?view=bills&month=${month}`:`/budget/reserves?reserve=${match.id}&month=${month}`});
  for(const account of data.planning?.month_review?.accounts.filter(a=>!a.verified_on)??[])rows.push({key:`account:${account.id}`,kind:'ACCOUNT',name:`Potwierdź saldo: ${account.name}`,detail:'Porównaj stan zapisów z bankiem lub gotówką.',href:`/budget/accounts?month=${month}`});
  for(const reserve of data.planning?.reserve_plans.filter(r=>r.remaining>0)??[])rows.push({key:`reserve:${reserve.reserve_id}`,kind:'PAYMENT',name:`Uzupełnij odłożenie: ${reserve.name}`,detail:`W planie ${month} brakuje ${money(reserve.remaining)}.`,href:`/budget/reserves?reserve=${reserve.reserve_id}&month=${month}`});
  if(forecast?.month_plans?.some(r=>r.categories.some(c=>c.source==='ESTIMATE')))rows.push({key:'forecast',kind:'PLAN',name:'Uzupełnij założenia prognozy',detail:'Przyszłe miesiące zawierają szacunkowe limity.',href:`/budget/forecast?month=${month}&section=basis`});
  const shown=rows.filter(row=>filter==='ALL'||row.kind===filter);
  return <details className="budget-panel budget-review-queue"><summary>Do sprawdzenia <span className="budget-count">{rows.length}</span></summary><p className="bp-help">Dokumenty, powiązania i założenia planu w jednym miejscu. Oczekujący import i już zapisany zakup to różne etapy.</p>{failed&&<p role="status">Nie udało się odczytać stanu importów. <Link to={`/budget/imports?month=${month}`}>Sprawdź importy</Link></p>}<label>Rodzaj spraw<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="ALL">Wszystkie sprawy</option><option value="DATA">Importy i kategorie</option><option value="PAYMENT">Płatności i odłożenia</option><option value="ACCOUNT">Salda kont</option><option value="PLAN">Założenia planu</option></select></label>{shown.length?<ul className="budget-task-list">{shown.map(row=><li key={row.key}><div><strong>{row.name}</strong><small>{row.detail}</small></div><Link className="budget-text-button" to={row.href}>Sprawdź</Link></li>)}</ul>:<p>Brak spraw tego rodzaju.</p>}</details>;
}
