import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Pencil, Plus } from 'lucide-react';
import type { BudgetBill, BudgetCategory, BudgetWorkspace } from '../../api_budget_workspace';
import { BillEditor, BillPayment } from './BudgetObligations';
import { planningDay as day, planningMoney as money, planningToday } from './planningHelpers';

export default function BudgetCategoryPayments({ category, data, reload }: { category: BudgetCategory; data: BudgetWorkspace; reload: () => Promise<void> }) {
  const children = data.categories.filter(item => item.parent_id === category.id);
  const ids = [category.id, ...children.map(item => item.id)];
  const bills = data.bills.filter(bill => ids.includes(bill.category_id));
  const loans = data.planning?.loans?.filter(loan => loan.category_id !== null && ids.includes(loan.category_id)) ?? [];
  const media = data.planning?.reserve_plans.filter(reserve => reserve.monthly_amount != null && !reserve.open_ended && reserve.category_id != null && ids.includes(reserve.category_id)) ?? [];
  const [editing, setEditing] = useState<BudgetBill | null | undefined>(), [paying, setPaying] = useState<BudgetBill | null>(null);
  const [showPaid, setShowPaid] = useState(false);
  const pending = bills.some(bill=>bill.status!=='PAID') || loans.some(loan=>!loan.paid);
  const paidCount = bills.filter(bill=>bill.status==='PAID').length + loans.filter(loan=>loan.paid).length;
  const hasPayments = bills.length+loans.length+media.length>0 || category.planned_bills>0;
  const plan = category.plan_details;
  const ordinaryPlan = plan?.ordinary_planned ?? Math.max(0, category.planned - category.planned_bills);
  return <>
    {hasPayments&&<div className="budget-category-allocation" aria-label={`Podział limitu: ${category.name}`}>
      <div className="budget-allocation-values">
        <div><span>Płatności i pule w limicie</span><b>{money(category.planned_bills)}</b><small>Rachunki, raty i miesięczne media</small></div>
        <div><span>Limit zwykłych wydatków</span><b>{money(ordinaryPlan)}</b><small>Po wydzieleniu płatności i mediów</small></div>
        <div><span>Zwykłe wydatki — jeszcze do wykorzystania</span><b>{money(plan?.ordinary_remaining ?? Math.max(0, category.remaining))}</b><small>{plan ? `Wydano ${money(plan.ordinary_spent)}` : 'W ramach wspólnego planu'}</small></div>
      </div>
      {(category.reserve_covered ?? 0) > 0 && <p>Poza tym limitem: {money(category.reserve_covered ?? 0)} finansowane odłożoną rezerwą.</p>}
      {plan&&plan.payments_pending>0&&<p>Płatności jeszcze do rozliczenia: {money(plan.payments_pending)}. Ta kwota jest już zarezerwowana w planie.</p>}
      {(category.carryover ?? 0) > 0 && <p>W limicie jest {money(category.carryover ?? 0)} przeniesione z poprzedniego miesiąca.</p>}
      {category.manual_plan>0&&category.planned>category.manual_plan+(category.carryover??0)+.005&&<p>Wpisano wspólny limit {money(category.manual_plan)}. Plan wzrósł do {money(category.planned)}, aby pomieścić przypisane płatności i limity podkategorii.</p>}
      {!!plan?.ordinary_over && <p className="budget-negative">Przekroczenie zwykłych wydatków: {money(plan.ordinary_over)}. Pozostałe kategorie zachowują swoje limity.</p>}
      <p>To podział kwoty pokazanej u góry. Rachunków nie dopisuj drugi raz do limitu.</p>
    </div>}
    {!hasPayments&&<div className="budget-plan-toolbar"><p>{category.is_unassigned?'Zakupy bez przypisania są uwzględnione w wydatkach. Przypisz je do właściwych kategorii.':'Cały limit dotyczy zwykłych wydatków. Nie ma w nim rachunków ani rat.'}{(category.carryover??0)>0&&` W tym przeniesiono ${money(category.carryover??0)}.`}</p>{category.is_unassigned?<Link className="budget-text-button" to={`/budget/imports?tab=pending&month=${data.month}`}>Przypisz kategorie</Link>:<button className="budget-text-button" onClick={()=>setEditing(null)}><Plus size={15}/>Dodaj rachunek do: {category.name}</button>}</div>}
    {hasPayments&&<details className="budget-category-payments" open={pending}>
      <summary>Rachunki i raty w tej kategorii ({bills.length + loans.length})</summary>
      {pending&&paidCount>0&&<label className="budget-transaction-filter-status"><input type="checkbox" checked={showPaid} onChange={event=>setShowPaid(event.target.checked)}/>Pokaż opłacone płatności ({paidCount})</label>}
      {media.map(reserve => <div className="budget-category-payment" key={`media:${reserve.reserve_id}`}>
        <div><strong>{reserve.name} · miesięczna pula</strong><small>Plan {money(reserve.planned)} · wykonano {money(reserve.funded)} · brakuje {money(reserve.remaining)}</small><small>Płatności i odłożenia wykorzystują tę samą pulę.</small></div>
        <b>{money(reserve.planned)}</b><Link className="budget-text-button" to={`/budget?view=plan&month=${data.month}#reserve-month-plans`}>Zmień pulę / odłóż</Link>
      </div>)}
      {[category, ...children].map(group => {
        const groupedBills = bills.filter(bill => bill.category_id === group.id && (!pending||showPaid||bill.status!=='PAID'));
        const groupedLoans = loans.filter(loan => loan.category_id === group.id && (!pending||showPaid||!loan.paid));
        if (!groupedBills.length && !groupedLoans.length) return null;
        return <div key={group.id}>
          <h4>{group.id === category.id && children.length ? 'Ogólnie w kategorii' : group.name}</h4>
          {groupedBills.map(bill => {
            const reserve = media.find(item => item.reserve_id === bill.reserve_id);
            return <div className="budget-category-payment" key={bill.id}>
              <div><strong>{bill.title}</strong><small>Termin {day(bill.due_date)} · {bill.account_name}</small>
                <small>{reserve ? `W puli ${reserve.name} — bez dodatkowego limitu` : bill.reserve_id ? `Z rezerwy ${money(bill.reserve_covered ?? 0)} · z budżetu ${money(bill.unfunded ?? Math.max(0, bill.amount - (bill.reserve_covered ?? 0)))}` : 'Wliczony w płatności tej kategorii'}</small>
                <span className={`budget-payment-status ${bill.status === 'PAID' ? '' : 'is-pending'}`}>{bill.status === 'PAID' ? `Opłacony${bill.paid_on ? ` · ${day(bill.paid_on)}` : ''}` : bill.status === 'OVERDUE' ? 'Termin minął — sprawdź płatność' : 'Do opłacenia'}</span>
              </div><b>{money(bill.amount)}</b>
              <div className="budget-category-payment-actions">
                {bill.status !== 'PAID' && data.month <= planningToday().slice(0, 7) && <button className="budget-button-secondary" onClick={() => setPaying(bill)}><Check size={14}/>{bill.payment_candidates?.length ? 'Powiąż płatność' : 'Rozlicz'}</button>}
                <button className="budget-icon-button" aria-label={`Zmień kategorię lub plan rachunku: ${bill.title}`} title="Kategoria, kwota i termin rachunku" onClick={() => setEditing(bill)}><Pencil size={15}/></button>
              </div>
            </div>;
          })}
          {groupedLoans.map(loan => <div className="budget-category-payment" key={`loan:${loan.id}:${loan.installment_month}`}>
            <div><strong>{loan.name} · rata</strong><small>{day(loan.date)} · {data.accounts.find(account => account.id === loan.account_id)?.name ?? 'Konto w ustawieniach kredytu'}</small><span className={`budget-payment-status ${loan.paid ? '' : 'is-pending'}`}>{loan.paid ? 'Spłata zapisana' : 'Do rozliczenia'}</span></div>
            <b>{money(loan.paid_amount ?? loan.amount)}</b><Link className="budget-text-button" to={`/loans/${loan.id}?installment=${loan.installment_month}`}>Rozlicz / szczegóły</Link>
          </div>)}
        </div>;
      })}
      {!bills.length && !loans.length && <p className="bp-help">Nie ma przypisanych rachunków ani rat w tym miesiącu.</p>}
      {!category.is_unassigned && <button className="budget-text-button" onClick={() => setEditing(null)}><Plus size={15}/>Dodaj rachunek do: {category.name}</button>}
    </details>}
    {editing !== undefined && <BillEditor data={data} bill={editing} categoryId={category.id} reload={reload} onClose={() => setEditing(undefined)}/>}
    {paying && <BillPayment data={data} bill={paying} reload={reload} onClose={() => setPaying(null)}/>}
  </>;
}
