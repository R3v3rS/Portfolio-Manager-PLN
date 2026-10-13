import { useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { BudgetEntry, BudgetWorkspace } from '../../api_budget_workspace';
import { planningMoney as money, planningDay as day } from './planningHelpers';

export default function BudgetTransactions({ data, children }: { data: BudgetWorkspace; children: (entry: BudgetEntry) => ReactNode }) {
  const [search, setSearch] = useState(''), [account, setAccount] = useState('');
  const [category, setCategory] = useState(''), [kind, setKind] = useState(''), [scope, setScope] = useState('');
  const [limit, setLimit] = useState(60);
  const transfers = data.bank_transfers ?? [];
  const filtered = useMemo(() => data.entries.filter(entry => {
    const matchesSearch = [entry.description, entry.merchant, entry.account_name, ...entry.lines.flatMap(line => [line.label, line.category_name])]
      .join(' ').toLocaleLowerCase('pl').includes(search.toLocaleLowerCase('pl'));
    const ids = category ? [Number(category), ...data.categories.filter(item => item.parent_id === Number(category)).map(item => item.id)] : [];
    return matchesSearch && (!account || entry.account_id === Number(account)) && (!kind || entry.kind === kind)
      && (!category || entry.lines.some(line => ids.includes(line.category_id)))
      && (!scope || (scope === 'UNASSIGNED' && entry.classification_status === 'UNASSIGNED')
        || (scope === 'BILL' && !!entry.bill_id) || (scope === 'LOAN' && !!entry.loan_id)
        || (scope === 'RECEIPT' && entry.has_receipt) || (scope === 'HISTORY' && entry.cash_effect === false));
  }), [data.entries, data.categories, search, account, category, kind, scope]);
  const filteredTransfers = transfers.filter(item => (!kind || kind === 'TRANSFER') && !category && !scope
    && (!account || [item.source_account_id, item.target_account_id].includes(Number(account)))
    && [item.description, item.source_name, item.target_name].join(' ').toLocaleLowerCase('pl').includes(search.toLocaleLowerCase('pl')));
  const days = [...new Set([...filtered.map(entry => entry.date), ...filteredTransfers.map(item => item.date)])].sort().reverse();
  const shownDays = days.filter(date => {
    const earlier = days.slice(0, days.indexOf(date));
    return earlier.reduce((count, key) => count + filtered.filter(item => item.date === key).length + filteredTransfers.filter(item => item.date === key).length, 0) < limit;
  });
  const spent = filtered.reduce((total, entry) => total + (entry.kind === 'EXPENSE' ? entry.amount : entry.kind === 'REFUND' ? -entry.amount : 0), 0);
  const count = filtered.length + filteredTransfers.length;
  const reset = () => { setSearch(''); setAccount(''); setCategory(''); setKind(''); setScope(''); setLimit(60); };
  return <>
    <div className="budget-transaction-filters">
      <label>Szukaj transakcji<input type="search" value={search} onChange={event => { setSearch(event.target.value); setLimit(60); }} placeholder="Sklep, opis lub produkt z paragonu"/></label>
      <label>Konto transakcji<select value={account} onChange={event => { setAccount(event.target.value); setLimit(60); }}><option value="">Wszystkie konta</option>{data.accounts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Kategoria transakcji<select value={category} onChange={event => { setCategory(event.target.value); setLimit(60); }}><option value="">Wszystkie kategorie</option>{data.categories.map(item => <option key={item.id} value={item.id}>{item.selection_label ?? item.name}</option>)}</select></label>
      <label>Rodzaj transakcji<select value={kind} onChange={event => { setKind(event.target.value); setLimit(60); }}><option value="">Wszystkie rodzaje</option><option value="EXPENSE">Wydatki</option><option value="INCOME">Wpływy</option><option value="REFUND">Zwroty</option><option value="TRANSFER">Przelewy</option></select></label>
    </div>
    <div className="budget-transaction-filter-status"><label>Powiązanie i stan<select value={scope} onChange={event => { setScope(event.target.value); setLimit(60); }}><option value="">Wszystkie wpisy</option><option value="UNASSIGNED">Bez kategorii</option><option value="BILL">Rozliczają rachunek</option><option value="LOAN">Rozliczają kredyt</option><option value="RECEIPT">Z paragonem</option><option value="HISTORY">Zapisane bez zmiany salda</option></select></label><button className="budget-text-button" onClick={reset}>Wyczyść filtry</button></div>
    <div className="budget-transaction-summary" aria-live="polite"><span>{count} transakcji</span><span>Wydatki po zwrotach: <b>{money(spent)}</b></span><span>Wpływy: <b>{money(filtered.filter(entry => entry.kind === 'INCOME').reduce((total, entry) => total + entry.amount, 0))}</b></span><small>Sumy dotyczą wybranych filtrów. Przelewy są poza wydatkami i wpływami.</small></div>
    {!count && <p className="budget-small-empty">Brak transakcji pasujących do filtrów.</p>}
    {shownDays.map(date => {
      const entries = filtered.filter(entry => entry.date === date);
      const daySpent = entries.reduce((total, entry) => total + (entry.kind === 'EXPENSE' ? entry.amount : entry.kind === 'REFUND' ? -entry.amount : 0), 0);
      return <section className="budget-transaction-day" key={date} aria-label={`Transakcje: ${date}`}>
        <h3>{day(date)}<span>Wydatki po zwrotach: {money(daySpent)}</span></h3>
        <div className="budget-entry-list">{entries.map(children)}
          {filteredTransfers.filter(item => item.date === date).map(item => <article className="budget-entry" key={`bank:${item.id}`}>
            <div className="budget-entry-description"><strong>{item.description || (item.move_money===0?'Przeniesienie rezerwy':'Przelew między kontami')}</strong><span>{item.source_name} → {item.target_name}</span><small>{item.reserve_name ? `Rezerwa: ${item.reserve_name}` : 'Zmiana miejsca pieniędzy'} · poza wpływami i wydatkami{item.reserve_action==='FUND'?' · odłożenie jest w planie rezerw':''}</small></div>
            <strong className="budget-entry-amount">{money(item.amount)}</strong><Link className="budget-text-button" to={`/budget/accounts?month=${data.month}`}>Konta i historia</Link>
          </article>)}
        </div>
      </section>;
    })}
    {count > limit && shownDays.length < days.length && <button className="budget-button-secondary" onClick={() => setLimit(limit + 60)}>Pokaż kolejne dni</button>}
  </>;
}
