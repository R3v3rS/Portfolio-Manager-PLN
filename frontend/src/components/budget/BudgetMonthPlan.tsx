import { Link } from 'react-router-dom';
import {useState} from 'react';
import {BillPayment} from './BudgetObligations';
import type {BudgetBill} from '../../api_budget_workspace';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { planningMoney as money, planningDay as day } from './planningHelpers';

export default function BudgetMonthPlan({data,reload}:{data:BudgetWorkspace;reload?:()=>Promise<void>}) {
  const [expanded,setExpanded]=useState<string|null>(null),[paying,setPaying]=useState<BudgetBill|null>(null);
  const loans=data.planning?.loans??[],reserves=data.planning?.reserve_plans??[];
  const ordinaryBills=data.bills.filter(b=>{const reserve=reserves.find(r=>r.reserve_id===b.reserve_id);return !(reserve?.monthly_amount!=null&&!reserve.open_ended);});
  const paidBills=data.bills.filter(b=>b.status==='PAID').reduce((sum,b)=>sum+b.amount,0);
  const paidLoans=data.entries.filter(e=>e.kind==='EXPENSE'&&e.loan_id).reduce((sum,e)=>sum+e.amount,0);
  const categoryPlan=data.categories.filter(c=>!c.parent_id).reduce((sum,c)=>sum+Math.max(0,c.planned-c.planned_bills),0);
  const dailySpent=data.totals.spent-paidBills-paidLoans;
  const rows=[
    {name:'Wpływy',planned:data.totals.income+(data.totals.expected_income??0),done:data.totals.income,left:data.totals.expected_income??0,href:'/budget/forecast'},
    {name:'Codzienne wydatki',planned:categoryPlan,done:dailySpent,left:Math.max(0,categoryPlan-dailySpent),href:`/budget?view=entries&month=${data.month}`},
    {name:'Rachunki',planned:data.bills.reduce((s,b)=>s+b.amount,0),done:paidBills,left:data.bills.filter(b=>b.status!=='PAID').reduce((s,b)=>s+b.amount,0),href:`/budget?view=bills&month=${data.month}`},
    {name:'Raty kredytów',planned:loans.reduce((s,l)=>s+l.amount,0),done:paidLoans,left:loans.filter(l=>!l.paid).reduce((s,l)=>s+l.amount,0),href:'/loans'},
    {name:'Odłożenia na rezerwy',planned:reserves.reduce((s,r)=>s+r.planned,0),done:reserves.reduce((s,r)=>s+r.funded,0),left:reserves.reduce((s,r)=>s+r.remaining,0),href:'/budget/reserves'},
  ];
  const links:Record<string,string>={INCOME:'/budget/forecast',DAILY:`/budget?view=entries&month=${data.month}`,BILLS:`/budget?view=bills&month=${data.month}`,LOANS:'/loans',RESERVES:'/budget/reserves',RESERVE_COST:'/budget/reserves',MEDIA:`/budget?view=plan&month=${data.month}`};
  const display=data.planning?.month_plan?.map(r=>({...r,left:r.remaining,href:links[r.kind]}))??rows;
  return <section className="budget-panel surface-card bp-panel" aria-label="Wspólny plan miesiąca">
    <div className="budget-section-heading"><div><p className="page-eyebrow">Cały miesiąc w jednym miejscu</p><h2>Wpływy, płatności i odłożenia</h2><p>Raty są pobierane z kredytów. Odłożenia wydzielają pieniądze na przyszłość; finansowane nimi rachunki nie obciążają wolnej kwoty drugi raz.</p></div><strong>{money(data.totals.to_plan)}<small className="bp-help"> do zaplanowania</small></strong></div>
    <div className="bp-table-wrap"><table><thead><tr><th>Część budżetu</th><th>Zaplanowano</th><th>Wykonano</th><th>Pozostało</th><th>Obciążenie miesiąca</th><th>Szczegóły</th></tr></thead><tbody>{display.map((r,i)=>{const kind='kind' in r?String(r.kind):['INCOME','DAILY','BILLS','LOANS','RESERVES'][i];return <tr key={r.name}><th><Link to={r.href}>{r.name}</Link></th><td>{money(r.planned)}</td><td>{money(r.done)}</td><td>{money(r.left)}</td><td>{"month_cost" in r&&typeof r.month_cost==='number'?money(r.month_cost):'—'}</td><td><button type="button" className="budget-text-button" aria-expanded={expanded===kind} onClick={()=>setExpanded(expanded===kind?null:kind)}>{expanded===kind?'Ukryj':'Pokaż plan'}</button></td></tr>;})}</tbody></table></div>
    {expanded&&<div className="bp-details"><h3>Pozycje planu miesiąca</h3>
      {expanded==='BILLS'&&<>{ordinaryBills.length?ordinaryBills.map(b=><div className="bp-plan-item" key={b.id}><div><strong>{b.title}</strong><small>{day(b.due_date)} · {b.account_name} · {b.status==='PAID'?'Rozliczony':'Do zapłaty'}</small><p>{b.reserve_id?`Finansowanie z rezerwy: ${money(b.reserve_covered??0)}; nie dodajemy tej części kosztu drugi raz.`:'Z wolnych środków miesiąca.'}</p></div><b>{money(b.amount)}</b>{b.status!=='PAID'&&reload?<button className="budget-button-secondary" onClick={()=>setPaying(b)}>Rozlicz zaplanowany rachunek</button>:<Link to={`/budget?view=entries&month=${data.month}`}>Zobacz historię</Link>}</div>):<p>Brak rachunków w tym miesiącu.</p>}<Link to={`/budget?view=bills&month=${data.month}`}>Dodaj lub zmień rachunek w planie</Link></>}
      {expanded==='LOANS'&&loans.map(l=><div className="bp-plan-item" key={`${l.id}-${l.installment_month}`}><span>{l.name}<small>{day(l.date)} · {l.paid?'Rozliczona':'Do zapłaty'}</small></span><b>{money(l.amount)}</b><Link to={`/loans/${l.id}`}>Przejdź do raty</Link></div>)}
      {['RESERVES','MEDIA'].includes(expanded)&&<>{reserves.filter(r=>expanded==='MEDIA'?(r.monthly_amount!=null&&!r.open_ended):(r.monthly_amount==null||r.open_ended)).map(r=><div className="bp-plan-item" key={r.reserve_id}><span>{r.name}<small>{r.account_name} · {r.remaining>0?'Brakuje odłożenia':'Plan wykonany'}</small></span><b>{money(r.funded)} / {money(r.planned)}</b><Link to={`/budget?view=plan&month=${data.month}#reserve-month-plans`}>Odłóż lub rozlicz</Link></div>)}<p>Wpłata do rezerwy wydziela środki. Późniejsza faktura finansowana z tych pieniędzy nie jest drugim obciążeniem miesiąca.</p></>}
      {expanded==='RESERVE_COST'&&<>{data.entries.filter(e=>e.reserve_id&&!e.bill_id&&!e.loan_id&&e.kind==='EXPENSE').map(e=><div className="bp-plan-item" key={e.id}><span>{e.description}<small>{day(e.date)} · {e.account_name}</small></span><b>{money(e.amount)}</b><Link to={`/budget?view=entries&month=${data.month}`}>Zobacz płatność</Link></div>)}<p>Obciążenie miesiąca uwzględnia środki użyte z wcześniejszych rezerw; nie dodajemy ich drugi raz.</p></>}{expanded==='DAILY'&&<>{data.categories.filter(c=>!c.parent_id&&(c.planned>0||c.spent>0)).map(c=><div className="bp-plan-item" key={c.id}><span>{c.name}</span><b>{money(c.spent)} / {money(c.planned)}</b><span className={c.remaining<0?'budget-negative':''}>Pozostało {money(c.remaining)}</span></div>)}<p>Powyżej widzisz limity całych kategorii, również z przypisanymi do nich rachunkami. To podgląd tych samych pieniędzy, a nie kolejne pozycje do sumowania. Zbiorczy wiersz codziennych wydatków oddziela już zobowiązania.</p></>}
      {expanded==='INCOME'&&<><p>Otrzymane: {money(data.totals.income)}. Oczekiwane: {money(data.totals.expected_income??0)}.</p><Link to="/budget/forecast">Sprawdź terminy planowanych wpływów</Link></>}
    </div>}
    {paying&&reload&&<BillPayment data={data} bill={paying} reload={reload} onClose={()=>setPaying(null)}/>}
    <details className="budget-calculation-help"><summary>Jak czytać plan miesiąca?</summary><p className="bp-help">„Pozostało” liczymy osobno dla limitów kategorii i nierozliczonych płatności. Nadwyżka w jednej kategorii lub rezerwie nie pokrywa automatycznie braków w innej. Wykonanie pokazuje rzeczywiste płatności oraz odłożenia, także ponad plan. Kolumna „Obciążenie miesiąca” rozlicza wcześniejsze rezerwy, dzięki czemu kwota nie jest liczona dwa razy.</p></details>
    {!!loans.length&&<details className="bp-details"><summary>Raty ujęte w planie ({loans.length})</summary>{loans.map(l=><p key={`${l.id}-${l.installment_month}`}><Link to={`/loans/${l.id}`}>{l.name}</Link> · {day(l.date)} · {money(l.amount)} · {l.paid?'Zapisano spłatę':'Do rozliczenia'}</p>)}</details>}
    {data.totals.loan_warnings?.map(w=><p key={w} className="bp-warning">{w}</p>)}
  </section>;
}
