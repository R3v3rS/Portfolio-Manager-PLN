import { Link } from 'react-router-dom';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { planningMoney as money, planningDay as day } from './planningHelpers';

export default function BudgetMonthPlan({data}:{data:BudgetWorkspace}) {
  const loans=data.planning?.loans??[],reserves=data.planning?.reserve_plans??[];
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
    <div className="bp-table-wrap"><table><thead><tr><th>Część budżetu</th><th>Zaplanowano</th><th>Wykonano</th><th>Pozostało</th><th>Obciążenie miesiąca</th></tr></thead><tbody>{display.map(r=><tr key={r.name}><th><Link to={r.href}>{r.name}</Link></th><td>{money(r.planned)}</td><td>{money(r.done)}</td><td>{money(r.left)}</td><td>{"month_cost" in r&&typeof r.month_cost==='number'?money(r.month_cost):'—'}</td></tr>)}</tbody></table></div>
    <details className="budget-calculation-help"><summary>Jak czytać plan miesiąca?</summary><p className="bp-help">„Pozostało” liczymy osobno dla limitów kategorii i nierozliczonych płatności. Przekroczenie jednej kategorii nie zwiększa limitu pozostałych. Wykonanie pokazuje płatności oraz odłożenia. Kolumna „Obciążenie miesiąca” rozlicza wcześniejsze rezerwy, dzięki czemu kwota nie jest liczona dwa razy.</p></details>
    {!!loans.length&&<details className="bp-details"><summary>Raty ujęte w planie ({loans.length})</summary>{loans.map(l=><p key={`${l.id}-${l.installment_month}`}><Link to={`/loans/${l.id}`}>{l.name}</Link> · {day(l.date)} · {money(l.amount)} · {l.paid?'Zapisano spłatę':'Do rozliczenia'}</p>)}</details>}
    {data.totals.loan_warnings?.map(w=><p key={w} className="bp-warning">{w}</p>)}
  </section>;
}
