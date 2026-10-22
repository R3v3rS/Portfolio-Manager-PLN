import {useState} from 'react';
import {Link} from 'react-router-dom';
import type {Reserve,ReserveAccountChange,ReserveJournalEvent,ReserveSummary} from '../../api_reserves';
import {planningMoney as money,planningDay as day} from './planningHelpers';

const reserveTransactionHref=(id:number,date:string)=>`/budget?view=entries&month=${date.slice(0,7)}&entry_id=${id}`;

export function ReserveAccountEffects({accounts}:{accounts:ReserveAccountChange[]}){
  return <div className="br-effect-accounts">{accounts.map(a=><div key={a.account_id}><strong>{a.account_name}</strong><span>Saldo konta <b>{money(a.balance_before)} → {money(a.balance_after)}</b></span><span>Poza rezerwami <b>{money(a.available_before)} → {money(a.available_after)}</b></span></div>)}</div>;
}

export function ReserveOperationSummary({value,compact=false}:{value:ReserveSummary;compact?:boolean}){
  return <div className="br-operation-summary" aria-label="Podsumowanie operacji rezerwy">
    {!compact&&<strong>{value.reserve_name} · {day(value.date)}</strong>}
    <dl className="br-receipt-grid">
      {value.reserve_before!=null&&<div><dt>Rezerwa przed operacją</dt><dd>{money(value.reserve_before)}</dd></div>}
      <div><dt>{value.kind==='SPEND'?'Zapłacono':value.kind==='ADD'?'Odłożono':'Zwolniono'}</dt><dd>{money(value.amount)}</dd></div>
      {value.reserve_after!=null&&<div><dt>Pozostało w rezerwie</dt><dd>{money(value.reserve_after)}</dd></div>}
    </dl>
    {value.kind==='SPEND'&&<>
      <p>Z rezerwy pokryto <b>{money(value.covered)}</b>{value.amount>value.covered&&<>; z bieżących środków <b>{money(value.amount-value.covered)}</b></>}.</p>
      {value.surplus>0&&<p className="br-surplus-result">{value.surplus_mode==='FREE'?<>Do wolnych środków wróciło <strong>{money(value.surplus)}</strong>.</>:value.surplus_mode==='RESERVE'?<>Przeniesiono <strong>{money(value.surplus)}</strong> do rezerwy „{value.surplus_reserve_name}”.</>:<>Nadwyżka <strong>{money(value.surplus)}</strong> zostaje na kolejne płatności.</>}</p>}
      {value.existing_expense&&<p>Powiązanie istniejącego wydatku — saldo konta pozostaje bez zmian.</p>}
    </>}
    {value.available_change!=null&&!compact&&<p>Zmiana środków poza rezerwami: <b>{value.available_change>0?'+':''}{money(value.available_change)}</b>. To środki przed pozostałymi rachunkami i limitami miesiąca.</p>}
    {!compact&&<ReserveAccountEffects accounts={value.accounts}/>}
    {value.budget_entry_id!=null&&<Link className="budget-text-button" to={reserveTransactionHref(value.budget_entry_id,value.date)}>Pokaż transakcję</Link>}
  </div>;
}

export function ReserveJournal({item,month,open,onUndo}:{item:Reserve;month:string;open:boolean;onUndo:(id:number)=>void}){
  const [kind,setKind]=useState('ALL'),[period,setPeriod]=useState('ALL');
  const events:ReserveJournalEvent[]=item.journal??item.movements.map(m=>({id:String(m.id),kind:m.kind,title:m.kind==='ADD'?'Odłożenie':m.kind==='RELEASE'?'Zwolnienie środków':'Rozliczenie płatności',date:m.date,amount:m.expense_amount??m.amount,reserve_change:m.kind==='ADD'?m.amount:-m.amount,bank_change:m.expense_amount?-m.expense_amount:0,account_name:m.account_name??item.account_name,notes:m.notes,transfer:null,budget_entry_id:m.budget_entry_id,summary:null}));
  const filtered=events.filter(e=>(kind==='ALL'||e.kind===kind)&&(period==='ALL'||e.date.startsWith(month)));
  return <details className="br-history" open={open}><summary>Historia rezerwy ({events.length})</summary>
    <div className="br-journal-filters"><label>Operacje<select value={kind} onChange={e=>setKind(e.target.value)}><option value="ALL">Wszystkie operacje</option><option value="ADD">Odłożenia</option><option value="FUND">Przelewy i odłożenia</option><option value="SPEND">Płatności</option><option value="RELEASE">Zwolnienia</option><option value="TRANSFER">Przeniesienia między kontami</option><option value="REALLOCATE">Nadwyżki z innych rezerw</option><option value="REVERSAL">Cofnięcia rozliczeń</option></select></label><label>Okres historii<select value={period} onChange={e=>setPeriod(e.target.value)}><option value="ALL">Cała historia</option><option value="MONTH">Wybrany miesiąc: {month}</option></select></label></div>
    {!filtered.length&&<p className="br-form-help">Brak operacji dla wybranych filtrów.</p>}
    <ol className="br-journal">{filtered.map(e=><li key={e.id}><div className="br-journal-heading"><div><strong>{e.title}</strong><small>{day(e.date)} · {e.account_name}</small></div><b>{money(e.amount)}</b></div>
      {e.transfer&&<small>{e.transfer.source} → {e.transfer.target}{e.kind==='FUND'?' · przelew i odłożenie liczone razem':' · łączna kwota rezerwy bez zmian'}</small>}
      {e.notes&&<p>{e.notes}</p>}
      {e.summary?<ReserveOperationSummary value={e.summary} compact/>:<small>{e.kind==='REVERSAL'?'Cofnięta operacja nie jest ponownie wliczana do zestawienia.':e.transfer?<>{e.transfer.changes_cash!==false?<>Salda: {e.transfer.source} {money(-e.amount)} · {e.transfer.target} +{money(e.amount)}.</>:'Zapis nie zmienia sald kont.'} Rezerwa: {e.reserve_change>0?'+':''}{money(e.reserve_change)}.</>:<>Rezerwa: {e.reserve_change>0?'+':''}{money(e.reserve_change)} · {e.bank_change?`zmiana salda konta ${money(e.bank_change)}`:'saldo konta bez zmian'}</>}</small>}
      {e.kind==='SPEND'&&e.budget_entry_id!=null&&<button className="budget-text-button" onClick={()=>onUndo(e.budget_entry_id!)}>Cofnij rozliczenie</button>}
    </li>)}</ol>
  </details>;
}

export function ReserveMonthlyStatement({items,month,onMonth}:{items:Reserve[];month:string;onMonth:(month:string)=>void}){
  const rows=items.filter(i=>i.month_statement&&(i.status==='ACTIVE'||i.month_statement.opening!==0||i.month_statement.added!==0||i.month_statement.used!==0||i.month_statement.released!==0));
  const total=(key:'opening'|'added'|'used'|'released'|'ending')=>rows.reduce((s,r)=>s+(r.month_statement?.[key]??0),0);
  return <details className="br-panel br-month-statement"><summary>Zestawienie miesięczne rezerw</summary><div className="br-statement-heading"><p>Stan początkowy + odłożenia − środki wykorzystane − zwolnienia = stan końcowy.</p><label>Miesiąc zestawienia<input type="month" min="2000-01" max="2100-12" value={month} onChange={e=>e.target.value&&onMonth(e.target.value)}/></label></div>
    <div className="br-table-scroll"><table><caption className="sr-only">Zestawienie rezerw: {month}</caption><thead><tr><th>Rezerwa</th><th>Na początek</th><th>Odłożono / otrzymano</th><th>Pokryto z rezerwy</th><th>Zwolniono / przekazano</th><th>Na koniec</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><th scope="row"><Link to={`/budget/reserves?month=${month}&reserve=${r.id}`}>{r.name}</Link><small>Zapłacone wydatki: {money(r.month_statement!.payments)}</small><small>Plan: {money(r.month_statement!.planned??0)} · wykonano: {money(r.month_statement!.funded??0)} · pozostało: {money(r.month_statement!.remaining??0)}</small>{!!r.month_statement!.extra&&<small>Dodatkowe odłożenia: {money(r.month_statement!.extra)}</small>}</th>{(['opening','added','used','released','ending'] as const).map(k=><td key={k}>{money(r.month_statement![k])}</td>)}</tr>)}</tbody><tfoot><tr><th>Razem</th>{(['opening','added','used','released','ending'] as const).map(k=><td key={k}>{money(total(k))}</td>)}</tr></tfoot></table></div>
    <p className="br-form-help">„Pokryto z rezerwy” obejmuje odłożoną część płatności. Wydatki ponad rezerwę finansują bieżące środki. Przeniesienie nadwyżki pojawia się jako przekazanie w jednej rezerwie i otrzymanie w drugiej; nie tworzy nowego kosztu ani przelewu bankowego.</p>
  </details>;
}
