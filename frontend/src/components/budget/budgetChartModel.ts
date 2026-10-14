import type { BudgetWorkspace } from '../../api_budget_workspace';
const cents = (value: number) => Math.round(value * 100);
export function budgetChartData(data: BudgetWorkspace, today: string, extraIncome = 0) {
  const [year, month] = data.month.split('-').map(Number);
  const days = new Date(year, month, 0).getDate();
  const dayDate = (day: number) => `${data.month}-${String(day).padStart(2, '0')}`;
  const current = today.startsWith(data.month);
  const lastActual = current ? Number(today.slice(8, 10)) : data.month < today.slice(0, 7) ? days : 0;
  const allBills = data.bills.reduce((sum, bill) => sum + cents(bill.amount), 0);
  const loans=data.planning?.loans??[];
  const allLoans=loans.reduce((sum,l)=>sum+cents(l.amount),0);
  const variablePlan = Math.max(cents(data.totals.planned) - allBills-allLoans, 0);
  const reserveRows=data.planning?.reserve_plans??[];
  const mediaIds=new Set(reserveRows.filter(r=>r.monthly_amount!=null&&!r.open_ended).map(r=>r.category_id));
  const fixedDate=(bill:BudgetWorkspace['bills'][number])=>{
    const paid=bill.paid_on??data.entries.find(e=>e.id===bill.entry_id)?.date;
    return paid&&paid<bill.due_date?paid:bill.due_date;
  };
  const fixedAmount=(bill:BudgetWorkspace['bills'][number])=>cents(bill.planned_amount??bill.base_amount??bill.amount);
  const nominalFixed=Object.fromEntries(data.categories.map(c=>[c.id,0]));
  for(const bill of data.bills)if(!reserveRows.some(r=>r.reserve_id===bill.reserve_id&&r.monthly_amount!=null&&!r.open_ended))nominalFixed[bill.category_id]=(nominalFixed[bill.category_id]??0)+fixedAmount(bill);
  for(const loan of loans)if(loan.category_id!=null)nominalFixed[loan.category_id]=(nominalFixed[loan.category_id]??0)+cents(loan.amount);
  for(const reserve of reserveRows)if(reserve.monthly_amount!=null&&!reserve.open_ended&&reserve.category_id!=null)nominalFixed[reserve.category_id]=(nominalFixed[reserve.category_id]??0)+cents(reserve.planned);
  const own=Object.fromEntries(data.categories.map(c=>[c.id,Math.max(mediaIds.has(c.id)?0:cents(c.manual_plan),nominalFixed[c.id]??0)]));
  const excludedIds=new Set(data.categories.filter(c=>c.daily_pace_included===false||c.daily_pace_effective===false||data.categories.some(parent=>parent.id===c.parent_id&&parent.daily_pace_included===false)).map(c=>c.id));
  const limit=(filtered:boolean)=>data.categories.length?data.categories.filter(c=>!c.parent_id).reduce((sum,root)=>{
    if(filtered&&excludedIds.has(root.id))return sum;
    const children=data.categories.filter(c=>c.parent_id===root.id);
    const total=Math.max(cents(root.manual_plan), (nominalFixed[root.id]??0)+children.reduce((s,c)=>s+own[c.id],0))+cents(root.carryover??0);
    const excluded=filtered?children.filter(c=>excludedIds.has(c.id)).reduce((s,c)=>s+Math.max(0,own[c.id]-(nominalFixed[c.id]??0)),0):0;
    return sum+Math.max(0,total-(nominalFixed[root.id]??0)-children.reduce((s,c)=>s+(nominalFixed[c.id]??0),0)-excluded);
  },0):variablePlan;
  const dailyLimit=limit(true),fullDailyLimit=limit(false);
  let spent = 0,dailySpent=0;
  const dailyPace:{date:string;spent:number|null;plan:number}[]=[];
  const pace = Array.from({ length: days }, (_, index) => {
    const date = dayDate(index + 1);
    spent += data.entries.filter(entry => (entry.kind === 'EXPENSE'||entry.kind==='REFUND') && entry.date === date).reduce((sum, entry) => sum + (entry.kind==='REFUND'?-1:1)*cents(entry.amount), 0);
    for(const entry of data.entries.filter(e=>e.date===date&&(e.kind==='EXPENSE'||e.kind==='REFUND'))){
      const original=entry.refund_of?data.entries.find(e=>e.id===entry.refund_of):entry;
      if(original?.bill_id||original?.loan_id||original?.reserve_id)continue;
      const media=entry.lines.filter(l=>mediaIds.has(l.category_id)||excludedIds.has(l.category_id)).reduce((sum,l)=>sum+cents(l.amount),0);
      dailySpent+=(entry.kind==='REFUND'?-1:1)*(cents(entry.amount)-media);
    }
    dailyPace.push({date,spent:index<lastActual?dailySpent/100:null,plan:Math.round(dailyLimit*(index+1)/days)/100});
    const due = data.bills.filter(bill => fixedDate(bill) <= date).reduce((sum, bill) => sum + fixedAmount(bill), 0);
    return { date, spent: index < lastActual ? spent / 100 : null, plan: (fullDailyLimit * (index + 1) / days + due+loans.filter(l=>(l.paid_on&&l.paid_on<l.date?l.paid_on:l.date)<=date).reduce((sum,l)=>sum+cents(l.amount),0)) / 100 };
  });
  const unpaid = data.bills.filter(bill => bill.status !== 'PAID');
  const remainingVariable = data.categories.filter(category => !category.parent_id).reduce((sum, category) => {
    const outstanding = unpaid.filter(bill => (bill.category_id === category.id || data.categories.some(child => child.id === bill.category_id && child.parent_id === category.id))).reduce((total, bill) => total + cents(bill.amount), 0);
    return sum + Math.max(cents(category.planned - category.spent) - outstanding, 0);
  }, 0);
  const unpaidTotal = unpaid.reduce((sum, bill) => sum + cents(bill.amount), 0);
  const income = Number.isFinite(extraIncome) ? Math.max(cents(extraIncome), 0) : 0;
  const forecast = [{ date: today, balance: data.totals.balance }];
  const start = current ? Number(today.slice(8, 10)) : days;
  const daysLeft = days - start;
  let balance = cents(data.totals.balance);
  for (let day = start + 1; day <= days; day++) {
    const date = dayDate(day);
    const bills = unpaid.filter(bill => bill.due_date === date || (day === start + 1 && bill.due_date <= today)).reduce((sum, bill) => sum + cents(bill.amount), 0);
    const variable = Math.round(remainingVariable * (day - start) / daysLeft) - Math.round(remainingVariable * (day - start - 1) / daysLeft);
    balance -= bills + variable;
    if (day === days) balance += income;
    forecast.push({ date, balance: balance / 100 });
  }
  // On the last day show the remaining obligations as a same-day scenario, separately from today's balance.
  const closing = (cents(data.totals.balance) - unpaidTotal - remainingVariable + income) / 100;
  return { pace,dailyPace, forecast: current ? forecast : [], closing, remainingVariable: remainingVariable / 100, unpaidTotal: unpaidTotal / 100, current, daysLeft };
}
