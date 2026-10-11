import { useState } from 'react';
import { budgetWorkspaceApi, type BudgetEntry, type BudgetWorkspace } from '../../api_budget_workspace';
import { ImportDialog } from './imports/ImportUi';
import { PlanningMessages } from './PlanningUi';
import { planningMoney as money, planningToday, usePlanningAction } from './planningHelpers';

export default function BudgetRefundDialog({purchase,data,reload,onClose}:{purchase:BudgetEntry;data:BudgetWorkspace;reload:()=>Promise<void>;onClose:()=>void}) {
  const [amount,setAmount]=useState(String(Math.max(0,purchase.amount-(purchase.refunded??0))));
  const [date,setDate]=useState(planningToday()),[account,setAccount]=useState(String(purchase.account_id));
  const [category,setCategory]=useState(String(purchase.lines[0]?.category_id??''));
  const [mode,setMode]=useState<'APPLY'|'HISTORY'|'MATCH'>('APPLY'),[incoming,setIncoming]=useState<BudgetEntry[]>([]),[selected,setSelected]=useState('');
  const [requestId]=useState(()=>crypto.randomUUID()),action=usePlanningAction(reload);
  const bankEntry=incoming.find(e=>e.id===Number(selected)),bankAccount=data.accounts.find(a=>a.id===Number(account));
  return <ImportDialog title="Zapisz zwrot zakupu" busy={action.busy} onClose={onClose}>
    <p>{purchase.description} · Zakup {money(purchase.amount)} · Dotychczas zwrócono {money(purchase.refunded??0)}.</p>
    <PlanningMessages {...action}/>
    <form className="bp-editor" onSubmit={e=>{e.preventDefault();void action.run(()=>budgetWorkspaceApi.refund(purchase.id,{version:purchase.version??1,amount:Number(amount),date,account_id:Number(account),category_id:Number(category),balance_mode:mode==='APPLY'?'APPLY':'HISTORY',expected_balance:bankAccount?.balance??0,...(mode==='MATCH'&&bankEntry?{existing_entry_id:bankEntry.id,entry_version:bankEntry.version}: {})},requestId),'Zwrot zapisany. Wydatki pomniejszono, dochód pozostaje bez zmian.',onClose);}}>
      <label>Kwota zwrotu (PLN)<input required type="number" min="0.01" max={purchase.amount-(purchase.refunded??0)} step="0.01" value={amount} onChange={e=>{setAmount(e.target.value);setSelected('');}}/></label>
      <label>Data otrzymania zwrotu<input required type="date" min={purchase.date} max={planningToday()} value={date} onChange={e=>{setDate(e.target.value);setSelected('');}}/></label>
      <label>Konto zwrotu<select value={account} onChange={e=>{setAccount(e.target.value);setSelected('');}}>{data.accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label>Kategoria zwracanego wydatku<select required value={category} onChange={e=>setCategory(e.target.value)}><option value="">Wybierz kategorię</option>{data.categories.map(c=><option key={c.id} value={c.id}>{c.selection_label??c.name}</option>)}</select></label>
      <label>Jak uwzględnić zwrot<select value={mode} onChange={e=>{setMode(e.target.value as typeof mode);setSelected('');}}><option value="APPLY">Nowy zwrot — zwiększ saldo konta</option><option value="HISTORY">Saldo banku już obejmuje zwrot — tylko historia</option><option value="MATCH">Powiąż z wpływem zaimportowanym z banku</option></select></label>
      {mode==='MATCH'&&<><button type="button" className="budget-button-secondary" onClick={()=>void action.run(async()=>{const result=await budgetWorkspaceApi.get(date.slice(0,7));setIncoming(result.entries.filter(e=>e.kind==='INCOME'&&e.account_id===Number(account)&&e.date===date&&Math.round(e.amount*100)===Math.round(Number(amount)*100)));},'Wybierz wpływ odpowiadający zwrotowi.')}>Znajdź wpływ z banku</button><label>Wpływ odpowiadający zwrotowi<select required value={selected} onChange={e=>setSelected(e.target.value)}><option value="">Wybierz wpływ</option>{incoming.map(e=><option key={e.id} value={e.id}>{e.description} · {money(e.amount)}</option>)}</select></label></>}
      <p className="bp-help">Saldo {bankAccount?.name}: {money(bankAccount?.balance??0)} → {money((bankAccount?.balance??0)+(mode==='APPLY'?Number(amount)||0:0))}. Zwrot zmniejsza wydatki w miesiącu otrzymania. Nie jest dochodem.</p>
      <button className="budget-button-primary" disabled={action.busy||(mode==='MATCH'&&!bankEntry)} type="submit">Zapisz zwrot</button>
    </form>
  </ImportDialog>;
}
