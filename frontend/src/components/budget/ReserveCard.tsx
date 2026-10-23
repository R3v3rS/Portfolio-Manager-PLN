import { Link } from 'react-router-dom';
import { Archive, ArrowDownLeft, ArrowRightLeft, Check, CirclePlus, Pencil, Wallet } from 'lucide-react';
import type { Reserve, ReservesWorkspace } from '../../api_reserves';
import BudgetFundingProgress from './BudgetFundingProgress';
import { ReserveJournal } from './ReserveActivity';
import { planningMoney as money, planningDay as day } from './planningHelpers';

type Props={item:Reserve;data:ReservesWorkspace;month:string;selected:boolean;management:boolean;disabled:boolean;onAction:(kind:'PLAN'|'ADD'|'SPEND'|'RELEASE',item:Reserve)=>void;onArchive:(item:Reserve)=>void;onUndo:(id:number)=>void};
const monthText=(value:string)=>new Date(value+'-01T12:00:00').toLocaleDateString('pl-PL',{month:'long',year:'numeric'});
export default function ReserveCard({item,data,month,selected,management,disabled,onAction,onArchive,onUndo}:Props){
  const monthly=item.monthly_amount!=null,media=monthly&&!item.open_ended,active=item.status==='ACTIVE';
  const statement=item.month_statement;
  const plan=statement?.planned??item.month_planned??(item.monthly_started===false?0:item.monthly_amount??item.monthly_required);
  const funded=statement?.funded!==undefined?statement.funded+(statement.extra??0):item.month_allocated??0;
  const left=statement?.remaining??(monthly?item.remaining:Math.max(0,plan-funded));
  const planMonth=statement?.month??data.as_of.slice(0,7);
  const tag=item.status==='COMPLETED'?'Rozliczona':item.status==='ARCHIVED'?'Archiwum':item.open_ended?'Bez terminu':media?'Miesięczna pula na media':item.frequency==='YEARLY'?'Co roku':'Jednorazowo';
  return <article className={`br-card br-card-compact ${selected?'is-selected':''}`}>
    <div className="br-card-title"><div><span className="br-tag">{tag}</span><h2>{item.name}</h2><p>{item.account_name}{!monthly&&item.due_date&&` · termin ${day(item.due_date)}`}</p></div>{management&&active&&<button className="budget-icon-button" aria-label={`Edytuj rezerwę: ${item.name}`} disabled={disabled} onClick={()=>onAction('PLAN',item)}><Pencil size={16}/></button>}</div>
    {item.monthly_started===false&&item.monthly_start_month&&<p className="br-start-notice">Początek odkładania: {monthText(item.monthly_start_month)}. Wcześniej nie naliczamy planowanej wpłaty.</p>}
    <div className="br-saved"><span>{item.status==='COMPLETED'?'Zapłacono':'Odłożone środki'}</span><strong>{money(item.status==='COMPLETED'?item.movements.reduce((sum,m)=>sum+(m.expense_amount??0),0):item.saved)}</strong></div>
    {!monthly&&item.status!=='COMPLETED'&&<div className="br-compact-target"><div><span>Cel {money(item.target_amount)}</span><b>{item.progress_percent}%</b></div><div className="br-progress" role="progressbar" aria-label={`Postęp: ${item.name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={item.progress_percent}><span style={{width:`${item.progress_percent}%`}}/></div></div>}
    {active&&<><BudgetFundingProgress month={planMonth} name={item.name} planned={plan} funded={funded} zeroPlanNote={item.monthly_started===false?'Plan wpłat jeszcze się nie rozpoczął.':undefined}/><div className="br-compact-left"><span>Jeszcze do odłożenia w miesiącu</span><b className={left>0?'br-funding-needed':''}>{money(left)}</b></div>
      {management&&media&&<Link className="budget-text-button br-correct-month" to={`/budget?view=plan&month=${item.monthly_started===false?item.monthly_start_month:data.as_of.slice(0,7)}`}>{item.monthly_started===false?'Koryguj pierwszy miesiąc':'Koryguj bieżący miesiąc'}</Link>}
      <div className="br-card-actions"><button className="budget-button-primary" disabled={disabled} onClick={()=>onAction('ADD',item)}><CirclePlus size={16}/>Odłóż środki</button><button className="budget-button-secondary" disabled={disabled||!data.categories.length} onClick={()=>onAction('SPEND',item)}><Check size={16}/>Zapisz płatność</button></div></>}
    <details className="br-reserve-details" open={selected?true:undefined}><summary>Szczegóły rezerwy</summary>
      {item.notes&&<p className="br-notes">{item.notes}</p>}
      {monthly?<p>{item.open_ended?'Stały plan miesięczny':'Plan bieżącego miesiąca'}: {money(item.month_planned??item.monthly_amount??0)}. Domyślnie {money(item.monthly_amount??0)} / mies.</p>:<p>Do celu brakuje {money(item.remaining)}. {item.urgent?'Do uzupełnienia teraz.':`Na kolejne miesiące: ${money(item.monthly_required)} / mies.`}</p>}
      <p>{item.open_ended?item.monthly_amount===0?'Brak obowiązkowej wpłaty; możesz odkładać ręcznie dowolne kwoty.':'Dodatkowe wpłaty nie zmniejszają stałego planu na kolejny miesiąc.':media?'Płatności i odłożenia wykorzystują jedną pulę. Wcześniejsza rezerwa pokrywa fakturę bez drugiego obciążenia planu.':`Miesiące do odkładania: ${item.months_left}. ${item.next_contribution_date?`Następne odłożenie: ${day(item.next_contribution_date)}.`:''}`}</p>
      {!!item.locations?.length&&<div className="br-locations" aria-label={`Miejsce środków: ${item.name}`}>{item.locations.map(location=><Link key={location.account_id} to={`/budget/accounts?month=${month}`}><Wallet size={13}/>{location.account_name}<b>{money(location.amount)}</b></Link>)}</div>}
      {statement&&<div className="br-month-breakdown"><span>Wpłaty w {monthText(statement.month)} <b>{money(statement.added)}</b></span><span>Zapłacone wydatki <b>{money(statement.payments)}</b></span><small>Kwota zapłacona z wcześniejszych odłożeń nie obciąża planu drugi raz.</small></div>}
      <div className="br-actions">{active&&item.saved>0&&<button className="budget-text-button" disabled={disabled} onClick={()=>onAction('RELEASE',item)}><ArrowDownLeft size={15}/>Zwolnij</button>}{active&&item.saved>0&&data.accounts.length>1&&<Link className="budget-text-button" to={`/budget/accounts?reserve=${item.id}&month=${month}`}><ArrowRightLeft size={14}/>Przenieś na inne konto</Link>}{management&&item.saved===0&&<button className="budget-text-button" disabled={disabled} onClick={()=>onArchive(item)}><Archive size={14}/>{item.status==='ARCHIVED'?'Przywróć':'Archiwizuj'}</button>}</div>
      {(item.movements.length>0||!!item.journal?.length||!!item.transfers?.length)&&<ReserveJournal item={item} month={month} open={selected} onUndo={management?onUndo:undefined}/>}
    </details>
  </article>;
}
