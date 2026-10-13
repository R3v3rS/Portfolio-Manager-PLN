import BudgetPaymentMatches from './BudgetPaymentMatches';
import { ImportDialog } from './imports/ImportUi';
import BudgetCharts from './BudgetCharts';
import BudgetSpendingPace from './BudgetSpendingPace';
import BudgetSpendingSummary from './BudgetSpendingSummary';
import BudgetRefundDialog from './BudgetRefundDialog';
import BudgetRuleSuggestion, { type RuleSuggestion } from './BudgetRuleSuggestion';
import BudgetMonthPlan from './BudgetMonthPlan';
import BudgetNavigation, { budgetMonth } from './BudgetNavigation';
import BudgetTransactions from './BudgetTransactions';
import BudgetCategoryPayments from './BudgetCategoryPayments';
import BudgetNextActions from './BudgetNextActions';
import BudgetDefaultPlans, {planSourceLabel} from './BudgetDefaultPlans';
import BudgetPlanCopy from './BudgetPlanCopy';
import { BudgetPlanningOverview, BudgetPayCycle, ForecastAccounts } from './BudgetPlanningOverview';
import { BudgetReservePlans, BudgetCarryoverPolicies } from './BudgetReservePlans';
import BudgetObligations from './BudgetObligations';
import BudgetPurchases from './BudgetPurchases';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import {
  ArrowDownLeft, ArrowRight, ArrowUpRight, Camera,
  CirclePlus, ClipboardList, CreditCard,
  FileText, Pencil, Plus, Trash2, Wallet, X,
} from 'lucide-react';
import {
  budgetWorkspaceApi, type BudgetEntry,
  type BudgetWorkspace, type BudgetCategory, type EntryInput,
} from '../../api_budget_workspace';
import { extractErrorMessageFromUnknown } from '../../http/response';
import './budgetWorkspace.css';
import './budgetPlanning.css';
import './budgetVisual.css';
import { useBudgetForecast } from './useBudgetForecast';

type View = 'overview' | 'plan' | 'entries' | 'bills' | 'cycle' | 'purchases' | 'settings';
type EntryMode = 'INCOME' | 'EXPENSE' | 'RECEIPT';
type LineDraft = { category_id: string; label: string; amount: string };

const money = (value: number) => new Intl.NumberFormat('pl-PL', {
  style: 'currency', currency: 'PLN', maximumFractionDigits: 2,
}).format(value);
const localToday = () => {
  const today = new Date();
  return today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' +
    String(today.getDate()).padStart(2, '0');
};
const shiftMonth = (month: string, difference: number) => {
  const [year, currentMonth] = month.split('-').map(Number);
  const next = new Date(year, currentMonth - 1 + difference, 1);
  return next.getFullYear() + '-' + String(next.getMonth() + 1).padStart(2, '0');
};
const monthLabel = (month: string) => {
  const [year, currentMonth] = month.split('-').map(Number);
  return new Intl.DateTimeFormat('pl-PL', { month: 'long', year: 'numeric' }).format(new Date(year, currentMonth - 1, 1));
};
const dateLabel = (value: string) => new Intl.DateTimeFormat('pl-PL', {
  day: '2-digit', month: 'short',
}).format(new Date(value + 'T12:00:00'));
const inputAmount = (value: string) => Number(value.replace(',', '.'));

const categoryIcon = (icon: string) => {
  switch (icon) {
    case 'UtensilsCrossed': return '🍽';
    case 'House': return '⌂';
    case 'ReceiptText': return '▤';
    case 'Car': return '↗';
    case 'HeartPulse': return '♡';
    case 'Sparkles': return '✦';
    default: return '◈';
  }
};

export default function BudgetWorkspaceDashboard() {
  const [refundPurchase,setRefundPurchase]=useState<BudgetEntry|null>(null);
  const [ruleSuggestion,setRuleSuggestion]=useState<RuleSuggestion|null>(null);
  const [planEditing,setPlanEditing]=useState(false);
  const [copyPlan,setCopyPlan]=useState(false);
  const [categorySearch,setCategorySearch]=useState('');
  const [categoryScope,setCategoryScope]=useState<'ALL'|'SPENT'|'OVER'>('ALL');
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const openedEntryId = useRef<number | null>(null);
  const month = budgetMonth(params.get('month'));
  const view: View = ['overview', 'plan', 'entries', 'bills', 'cycle', 'purchases', 'settings'].includes(params.get('view') || '') ? params.get('view') as View : 'overview';
  const setMonth = (value: string) => { const next = new URLSearchParams(params); next.set('month', value); setParams(next); };
  const setView = (value: View) => { const next = new URLSearchParams(params); next.set('view', value); next.set('month', month); next.delete('bill'); next.delete('edit_entry'); setParams(next); };
  const [data, setData] = useState<BudgetWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showAccountForm, setShowAccountForm] = useState(false);
  const [accountName, setAccountName] = useState('');
  const [openingBalance, setOpeningBalance] = useState('0');
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [categoryName, setCategoryName] = useState('');
  const [categoryParent, setCategoryParent] = useState('');
  const [categoryDailyPace, setCategoryDailyPace] = useState(true);
  const [editingCategory, setEditingCategory] = useState<BudgetCategory | null>(null);
  const [planDrafts, setPlanDrafts] = useState<Record<number, string>>({});
  const [entryMode, setEntryMode] = useState<EntryMode | null>(null);
  const [editingEntry, setEditingEntry] = useState<BudgetEntry | null>(null);
  const [entryAccountId, setEntryAccountId] = useState('');
  const [entryAmount, setEntryAmount] = useState('');
  const [entryDate, setEntryDate] = useState(localToday);
  const entryRequestId=useRef(crypto.randomUUID());
  const [entryDescription, setEntryDescription] = useState('');
  const [entryMerchant, setEntryMerchant] = useState('');
  const [entryLines, setEntryLines] = useState<LineDraft[]>([]);
  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const { forecast, failed: forecastFailed } = useBudgetForecast(data);

  const reload = useCallback(async () => {
    const next = await budgetWorkspaceApi.get(month);
    setData(next);
    setPlanDrafts(Object.fromEntries(next.categories.map(category => [category.id, String(category.manual_plan)])));
  }, [month]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setPlanEditing(false);
    setData(null);
    setError('');
    budgetWorkspaceApi.get(month).then(next => {
      if (!active) return;
      setData(next);
      setPlanDrafts(Object.fromEntries(next.categories.map(category => [category.id, String(category.manual_plan)])));
    }).catch(err => {
      if (active) setError(extractErrorMessageFromUnknown(err));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [month]);

  useEffect(()=>{
    if (!data || loading || !/^#(category-\d+|reserve-month-plans|default-plans)$/.test(location.hash)) return;
    document.getElementById(location.hash.slice(1))?.scrollIntoView?.({block:'start'});
  },[data,loading,location.hash,view]);

  useEffect(() => {
    if (!entryMode) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) setEntryMode(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [entryMode, busy]);

  const action = async (work: () => Promise<void>, success: string) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await work();
      await reload();
      setNotice(success);
    } catch (err) {
      setError(extractErrorMessageFromUnknown(err));
    } finally {
      setBusy(false);
    }
  };

  const openEntry = useCallback((mode: EntryMode, entry?: BudgetEntry) => {
    entryRequestId.current=crypto.randomUUID();
    setEditingEntry(entry ?? null);
    setEntryMode(mode);
    setEntryAccountId(String(entry?.account_id ?? data?.accounts[0]?.id ?? ''));
    setEntryAmount(entry ? String(entry.amount) : '');
    setEntryDate(entry?.date ?? (month >= localToday().slice(0, 7) ? localToday() : month + '-01'));
    setEntryDescription(entry?.description ?? '');
    setEntryMerchant(entry?.merchant ?? '');
    setEntryLines(entry?.lines.map(line => ({
      category_id: String(line.category_id), label: line.label, amount: String(line.amount),
    })) ?? [{ category_id: String(data?.categories[0]?.id ?? ''), label: '', amount: '' }]);
    setReceiptFile(null);
    setError('');
  }, [data, month]);

  useEffect(() => {
    const id = Number(params.get('edit_entry'));
    if (!data || !id || openedEntryId.current === id) return;
    const entry = data.entries.find(item => item.id === id && item.kind === 'EXPENSE');
    if (entry) { openedEntryId.current = id; setView('entries'); openEntry('EXPENSE', entry); }
  }, [data, params, openEntry]);

  useEffect(() => {
    const add = params.get('add');
    if (!data || !['expense','income'].includes(add ?? '')) return;
    openEntry(add === 'income' ? 'INCOME' : 'EXPENSE');
    const next = new URLSearchParams(params); next.delete('add'); setParams(next, {replace:true});
  }, [data, params, openEntry, setParams]);

  const updateLine = (index: number, field: keyof LineDraft, value: string) =>
    setEntryLines(lines => lines.map((line, lineIndex) =>
      lineIndex === index ? { ...line, [field]: value } : line
    ));

  const effectiveEntryAmount = entryLines.length > 1
    ? Math.round(entryLines.reduce((sum, line) => sum + (inputAmount(line.amount) || 0), 0) * 100) / 100
    : inputAmount(entryAmount);

  const saveEntry = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!entryMode) return;
    const kind = entryMode === 'INCOME' ? 'INCOME' : 'EXPENSE';
    const lines = kind === 'EXPENSE' ? entryLines.map(line => ({
      category_id: Number(line.category_id),
      amount: entryLines.length > 1 ? inputAmount(line.amount) : effectiveEntryAmount,
      label: line.label.trim(),
    })) : undefined;
    const payload: EntryInput = {
      ...(!editingEntry?{request_id:entryRequestId.current}:{}),
      ...(editingEntry?.version !== undefined ? { version: editingEntry.version } : {}),
      account_id: Number(entryAccountId), kind, amount: effectiveEntryAmount,
      date: entryDate, description: entryDescription.trim() || entryMerchant.trim() || 'Wydatek',
      merchant: entryMerchant.trim() || undefined, lines,
    };
    setBusy(true);
    setError('');
    try {
      const result = editingEntry
        ? await budgetWorkspaceApi.updateEntry(editingEntry.id, payload)
        : await budgetWorkspaceApi.createEntry(payload);
      const entryId = editingEntry?.id ?? (result as { id: number }).id;
      if (receiptFile) {
        try {
          await budgetWorkspaceApi.uploadReceipt(entryId, receiptFile);
        } catch (uploadError) {
          setError('Wydatek zapisano, ale nie udało się dołączyć paragonu: ' + extractErrorMessageFromUnknown(uploadError));
          setEntryMode(null);
          try { await reload(); } catch { /* Keep the saved-entry message; the form must stay closed. */ }
          return;
        }
      }
      setEntryMode(null);
      setNotice(editingEntry ? 'Wpis zaktualizowany.' : 'Wpis dodany do budżetu.');
      if(kind==='EXPENSE'&&lines?.length===1&&(!editingEntry||lines[0].category_id!==editingEntry.lines[0]?.category_id)) {
        const category=data?.categories.find(c=>c.id===lines[0].category_id);
        if(category&&!category.is_unassigned)setRuleSuggestion({pattern:payload.merchant||payload.description,categoryId:category.id,categoryName:category.selection_label??category.name,accountId:payload.account_id,merchant:!!payload.merchant});
      }
      try {
        await reload();
      } catch {
        setError('Wpis został zapisany. Nie udało się odświeżyć widoku — odśwież stronę, aby go zobaczyć.');
      }
    } catch (err) {
      setError(extractErrorMessageFromUnknown(err));
    } finally {
      setBusy(false);
    }
  };

  const saveAccount = async (event: React.FormEvent) => {
    event.preventDefault();
    await action(async () => {
      await budgetWorkspaceApi.createAccount(accountName, inputAmount(openingBalance));
      setShowAccountForm(false);
      setAccountName('');
      setOpeningBalance('0');
    }, 'Konto dodane. Możesz zaplanować miesiąc.');
  };

  const saveCategory = async (event: React.FormEvent) => {
    event.preventDefault();
    await action(async () => {
      if (editingCategory) await budgetWorkspaceApi.updateCategory(editingCategory.id, categoryName, categoryParent ? Number(categoryParent) : null, editingCategory.version ?? 1, categoryDailyPace);
      else await budgetWorkspaceApi.createCategory(categoryName, categoryParent ? Number(categoryParent) : null, categoryDailyPace);
      setCategoryName('');
      setShowCategoryForm(false);
    }, editingCategory ? 'Kategoria zmieniona. Dotychczasowe wpisy zachowały przypisanie.' : 'Kategoria dodana.');
  };

  const openCategory = (parent: number | null = null, category: BudgetCategory | null = null) => {
    setEditingCategory(category); setCategoryName(category?.name ?? '');
    setCategoryParent(String(category?.parent_id ?? parent ?? ''));
    setCategoryDailyPace(category?.daily_pace_included !== false);
    setError(''); setShowCategoryForm(true);
  };

  const deleteEntry = (entry: BudgetEntry) => {
    if (!window.confirm('Usunąć wpis „' + entry.description + '”? Saldo konta zostanie skorygowane.')) return;
    void action(() => budgetWorkspaceApi.deleteEntry(entry.id).then(() => undefined), 'Wpis usunięty.');
  };

  const applyEntryBalance = async (entry: BudgetEntry) => {
    const account = data?.accounts.find(item => item.id === entry.account_id);
    if (!account || busy) return;
    if (!window.confirm(`Pomniejszyć saldo konta „${account.name}” o ${money(entry.amount)} za „${entry.description}”? Użyj tej opcji, jeśli saldo w aplikacji jeszcze nie uwzględnia tego zakupu. Wydatek i jego podział pozostaną tym samym wpisem.`)) return;
    setBusy(true);setError('');setNotice('');
    try {
      const result = await budgetWorkspaceApi.applyEntryBalance(entry.id, entry.version ?? 0, account.balance);
      // Reflect the completed operation even if the following refresh fails.
      setData(before => before ? {
        ...before,
        entries: before.entries.map(item => item.id === entry.id ? {...item,cash_effect:true,version:result.version} : item),
        accounts: before.accounts.map(item => item.id === account.id ? {...item,balance:result.balance} : item),
        totals: {...before.totals,balance:before.totals.balance+result.balance-account.balance,to_plan:before.totals.to_plan+result.balance-account.balance},
      } : before);
      setNotice(result.applied ? `Saldo ${account.name} pomniejszono o ${money(entry.amount)}. Zakup nie został dodany ponownie.` : 'Ten zakup jest już uwzględniony w saldzie.');
      try { await reload(); } catch { setError('Zmiana salda została zapisana. Odśwież stronę, aby wczytać pełne podsumowanie.'); }
    } catch (err) { setError(extractErrorMessageFromUnknown(err)); }
    finally { setBusy(false); }
  };

  const previousMonth = shiftMonth(month, -1);

  return (
    <div className="budget-page page-stack">
      <header className="budget-heading">
        <div>
          <p className="page-eyebrow">Codzienne finanse</p>
          <h1>Budżet pod kontrolą</h1>
          <p className="budget-subtitle">Zaplanuj miesiąc, zapisuj wydatki i pilnuj terminów płatności.</p>
        </div>
      </header>
      <BudgetNavigation active={view==='cycle'?'forecast':view==='purchases'?'reserves':view} month={month} onMonth={setMonth} onView={target=>setView(target as View)} onExpense={()=>openEntry('EXPENSE')} onIncome={()=>openEntry('INCOME')}/>

      {error && <div role="alert" className="budget-feedback is-error">{error}<button type="button" aria-label="Zamknij komunikat" onClick={() => setError('')}><X size={16} /></button></div>}
      {notice && <div role="status" className="budget-feedback is-success">{notice}<button type="button" aria-label="Zamknij komunikat" onClick={() => setNotice('')}><X size={16} /></button></div>}
      {loading && !data ? <div className="budget-empty">Ładowanie budżetu...</div> :
        !data ? <div className="budget-empty">Nie udało się wczytać budżetu. Odśwież stronę i spróbuj ponownie.</div> :
        data.accounts.length === 0 ? (
          <section className="budget-onboarding surface-card">
            <div className="budget-onboarding-icon"><Wallet size={27} /></div>
            <p className="page-eyebrow">Nowy początek</p>
            <h2>Zacznij od konta, z którego płacisz</h2>
            <p>Podaj jego aktualne saldo. Utworzymy podstawowe kategorie, a potem ustawisz własny plan miesiąca.</p>
            <form onSubmit={saveAccount} className="budget-onboarding-form">
              <label>Nazwa konta<input required maxLength={100} value={accountName} onChange={event => setAccountName(event.target.value)} placeholder="np. Konto osobiste" /></label>
              <label>Aktualne saldo w PLN<input type="number" min="0" step="0.01" required value={openingBalance} onChange={event => setOpeningBalance(event.target.value)} /></label>
              <button className="budget-button-primary" disabled={busy} type="submit">Utwórz budżet <ArrowRight size={17} /></button>
            </form>
          </section>
        ) : <>
          <div className="budget-topline">
            <div className="budget-account-list">
              <span className="budget-muted-label">Salda teraz</span>
              {data.accounts.map(account => <span className="budget-account-pill" key={account.id}><CreditCard size={14} />{account.name}<strong>{money(account.balance)}</strong></span>)}
              <button type="button" className="budget-text-button" onClick={() => setShowAccountForm(!showAccountForm)}><Plus size={15} /> Dodaj konto</button>
            </div>
            <div className="budget-quick-actions">
              <button type="button" className="budget-button-secondary" onClick={() => openEntry('INCOME')}><ArrowDownLeft size={17} /> Przychód</button>
              <Link className="budget-button-secondary" to={`/budget/imports?tab=receipt&month=${month}`}><Camera size={17} /> Paragon</Link>
              <button type="button" className="budget-button-primary" onClick={() => openEntry('EXPENSE')}><Plus size={17} /> Wydatek</button>
            </div>
          </div>
          {showAccountForm && <form onSubmit={saveAccount} className="budget-inline-form surface-card">
            <label>Nazwa konta<input required maxLength={100} value={accountName} onChange={event => setAccountName(event.target.value)} /></label>
            <label>Aktualne saldo w PLN<input type="number" min="0" step="0.01" required value={openingBalance} onChange={event => setOpeningBalance(event.target.value)} /></label>
            <button type="submit" disabled={busy} className="budget-button-primary">Zapisz konto</button>
            <button type="button" onClick={() => setShowAccountForm(false)} className="budget-button-quiet">Anuluj</button>
          </form>}

          {(view==='bills'||view==='entries')&&<BudgetPaymentMatches data={data} reload={reload}/>}
          {view === 'overview' && <>
            {data.planning ? <BudgetPlanningOverview data={data} forecast={forecast} failed={forecastFailed}/> : <section aria-label="Podsumowanie miesiąca" className="budget-stats">
              <article className="budget-stat budget-stat-main"><span>Saldo kont</span><strong>{money(data.totals.balance)}</strong><small>Rzeczywiste środki na Twoich kontach</small><Wallet size={54} aria-hidden="true" /></article>
              <article className="budget-stat"><span>Plan miesiąca</span><strong>{money(data.totals.planned)}</strong><small>Limity kategorii wraz z rachunkami</small></article>
              <article className="budget-stat"><span>Obciążenie miesiąca</span><strong>{money(data.totals.budget_spent??data.totals.spent)}</strong><small>Wydatki {money(data.totals.spent)} · odłożono {money(data.totals.reserve_contributions??0)}{(data.totals.reserve_settled??0)>0&&` · rozliczono z rezerw ${money(data.totals.reserve_settled??0)}`}{(data.totals.reserve_released??0)>0&&` · zwolniono ${money(data.totals.reserve_released??0)}`}</small></article>
              <article className="budget-stat"><span>Do zaplanowania</span><strong className={data.totals.to_plan < 0 ? 'budget-negative' : ''}>{money(data.totals.to_plan)}</strong><small>Saldo + oczekiwane wpływy − pozostałe limity i zobowiązania − odłożenia − rezerwy ({money(data.totals.reserved ?? 0)})</small><Link className="budget-stat-income" to={`/budget/forecast?month=${month}`}>Wpływy do otrzymania: {money(data.totals.expected_income ?? 0)} <ArrowRight size={13} /></Link><small>Plan dla wybranego miesiąca. Otrzymane wpływy są już w saldzie.</small></article>
            </section>}
            {!data.planning&&<BudgetSpendingSummary data={data}/>}
            <BudgetNextActions data={data} forecast={forecast}/>
            <BudgetCharts key={month} data={data} />
            <details className="budget-plan-settings"><summary>Kategorie i szczegóły wykonania</summary>
              <div className="budget-category-list">{data.categories.filter(c=>!c.parent_id&&(c.planned>0||c.spent!==0)).map(c=><div key={c.id} className="budget-category-payment"><div><strong>{c.name}</strong><small>Wykorzystano {money(c.spent)} z {money(c.planned)}</small></div><b className={c.remaining<0?'budget-negative':''}>{c.remaining<0?'Przekroczono':'Pozostało'} {money(Math.abs(c.remaining))}</b><Link className="budget-text-button" to={`/budget?view=plan&month=${month}#category-${c.id}`}>Sprawdź limit</Link></div>)}</div>
            </details>
          </>}

          {view === 'plan' && <><BudgetMonthPlan data={data} reload={reload}/><section className="budget-panel surface-card">
            <div className="budget-section-heading"><div><p className="page-eyebrow">{monthLabel(month)}</p><h2>Plan miesiąca</h2><p>Limit głównej kategorii jest wspólny dla jej podkategorii. Możesz też rozdzielić go na osobne limity. Rachunki i podkategorie liczymy tylko raz.</p></div><button type="button" className="budget-button-secondary" disabled={busy} onClick={() => void action(
              () => budgetWorkspaceApi.copyPlans(previousMonth, month).then(() => undefined),
              'Skopiowano brakujące limity z poprzedniego miesiąca.',
            )}><ClipboardList size={16} /> Kopiuj poprzedni miesiąc</button></div>
            <div className="budget-plan-toolbar"><Link className="budget-text-button" to={`/budget?view=settings&month=${month}#default-plans`}>Ustaw domyślny plan miesięczny</Link><button className="budget-button-secondary" disabled={busy} onClick={()=>setCopyPlan(true)}><ClipboardList size={16}/>Kopiuj na 3, 6 lub 12 miesięcy</button></div>
            <div className="budget-plan-mode"><p>{planEditing?'Zapisz wyjątek na ten miesiąc; pozostałe miesiące zachowają swój plan.':'Domyślny limit obowiązuje do kolejnej zmiany; limit miesięczny ma pierwszeństwo.'}</p><button className="budget-button-secondary" disabled={busy} aria-pressed={planEditing} onClick={()=>setPlanEditing(!planEditing)}><Pencil size={15}/>{planEditing?'Zamknij edycję limitów':'Edytuj limity'}</button></div>
            <div className="bp-plan-filters"><label>Szukaj kategorii<input type="search" value={categorySearch} onChange={e=>setCategorySearch(e.target.value)} placeholder="Nazwa kategorii lub podkategorii"/></label><label>Pokaż kategorie<select value={categoryScope} onChange={e=>setCategoryScope(e.target.value as typeof categoryScope)}><option value="ALL">Wszystkie</option><option value="SPENT">Z wydatkami</option><option value="OVER">Z przekroczeniem limitu</option></select></label></div>
            <div className="budget-plan-list">{data.categories.filter(category => !category.parent_id&&(categoryScope==='ALL'||categoryScope==='SPENT'&&category.spent>0||categoryScope==='OVER'&&category.remaining<0)&&(category.name.toLocaleLowerCase('pl').includes(categorySearch.toLocaleLowerCase('pl'))||data.categories.some(c=>c.parent_id===category.id&&c.name.toLocaleLowerCase('pl').includes(categorySearch.toLocaleLowerCase('pl'))))).map(root => {
              const children = data.categories.filter(child => child.parent_id === root.id);
              return <section className="budget-plan-group" id={`category-${root.id}`} key={root.id} aria-label={'Plan kategorii ' + root.name}>
                <div className="budget-plan-provenance"><span>{planSourceLabel(root.plan_source)}{root.plan_source==='DEFAULT'&&` · od ${root.plan_source_month}`}</span>{planEditing&&root.plan_source==='MONTH'&&root.default_plan!=null&&<button className="budget-text-button" disabled={busy} onClick={()=>void action(()=>budgetWorkspaceApi.resetPlan(root.id,month).then(()=>undefined),'Przywrócono domyślny limit kategorii.')}>Wróć do domyślnego: {money(root.default_plan)}</button>}</div>
                {!planEditing&&<><div className="budget-plan-read-row"><span className="budget-category-icon" aria-hidden="true">{categoryIcon(root.icon)}</span><strong>{root.name}</strong><div><span>Całkowity limit</span><b>{money(root.planned)}</b></div><div><span>Wykorzystano</span><b>{money(root.spent)}</b></div><div><span>{root.planned===0?'Bez limitu':root.remaining<0?'Przekroczono':'Pozostało'}</span><b className={root.planned>0&&root.remaining<0?'budget-negative':''}>{root.planned===0?'—':money(Math.abs(root.remaining))}</b></div></div>{children.length>0&&<details className="budget-subcategory-details"><summary>Podkategorie ({children.length})</summary><div className="budget-subcategory-list">{(root.direct_spent??0)!==0&&<div><span>Ogólnie · bez podkategorii</span><b>{money(root.direct_spent??0)}</b></div>}{children.map(child=><div key={child.id}><span>{child.name}<small>Limit {money(child.planned)} · w tym płatności {money(child.planned_bills)}</small><small>{planSourceLabel(child.plan_source)}</small></span><b>{money(child.spent)}<small>wykorzystano</small></b></div>)}</div></details>}</>}
                {planEditing&&<>{[root].map(category => <div className={'budget-plan-row' + (category.parent_id ? ' is-child' : '')} key={category.id}>
                  <span className="budget-category-icon" aria-hidden="true">{categoryIcon(category.icon)}</span>
                  <div className="budget-plan-name"><strong>{category.name}</strong>{category.monthly_reserve_managed&&<small>Pula mediów — kwotę zmienisz poniżej w odłożeniach.</small>}<small>{category.parent_id ? root.name + ' · ' : ''}Plan stały: {money(category.planned_bills)} · {category.monthly_reserve_plan?'płatności i odłożenia':'wydano'}: {money(category.spent)}{(category.carryover ?? 0) > 0 && ' · przeniesiono: ' + money(category.carryover ?? 0)}</small>
                    {!category.is_unassigned && <div className="budget-category-actions"><button type="button" className="budget-text-button" onClick={() => openCategory(null, category)} aria-label={'Edytuj kategorię: ' + (category.path ?? category.name)}><Pencil size={13}/>Edytuj</button>
                      {!category.parent_id && <button type="button" className="budget-text-button" onClick={() => openCategory(category.id)} aria-label={'Dodaj podkategorię do: ' + category.name}><Plus size={14}/>Podkategoria</button>}</div>}
                  </div>
                  {(category.reserve_covered??0)>0&&<small className="bp-help">Już finansowane rezerwą: {money(category.reserve_covered??0)}. Tę część odejmujemy od limitu wymagającego wolnych pieniędzy.</small>}<label>{category.id === root.id && children.length ? 'Wspólny limit miesięczny' : 'Limit miesięczny'}<span className="budget-amount-input"><input aria-label={'Limit: ' + (category.path ?? category.name)} type="number" min="0" step="0.01" disabled={category.monthly_reserve_managed} value={category.monthly_reserve_managed?String(category.planned):planDrafts[category.id] ?? ''} onChange={event => setPlanDrafts(drafts => ({ ...drafts, [category.id]: event.target.value }))} /> PLN</span></label>
                  <button type="button" className="budget-button-secondary" disabled={busy || category.monthly_reserve_managed || ((category.plan_source===undefined||category.plan_source==='MONTH')&&inputAmount(planDrafts[category.id] ?? '0') === category.manual_plan)} onClick={() => void action(
                    () => budgetWorkspaceApi.setPlan(category.id, month, inputAmount(planDrafts[category.id] ?? '0')).then(() => undefined),
                    'Zapisano limit kategorii ' + category.name + '.',
                  )}>Zapisz</button>
                </div>)}
                {children.length>0&&<details className="bp-plan-children" open={!!categorySearch}><summary>Podkategorie ({children.length}) · rozwiń limity</summary>{children.filter(c=>!categorySearch||root.name.toLocaleLowerCase('pl').includes(categorySearch.toLocaleLowerCase('pl'))||c.name.toLocaleLowerCase('pl').includes(categorySearch.toLocaleLowerCase('pl'))).map(category=><div key={category.id} className="budget-plan-row is-child"><div className="budget-plan-name"><strong>{category.name}</strong><small>{planSourceLabel(category.plan_source)}</small>{category.plan_source==='MONTH'&&category.default_plan!=null&&<button className="budget-text-button" disabled={busy} onClick={()=>void action(()=>budgetWorkspaceApi.resetPlan(category.id,month).then(()=>undefined),'Przywrócono domyślny limit.')}>Wróć do domyślnego: {money(category.default_plan)}</button>}<small>{category.monthly_reserve_managed?'Płatności i odłożenia':'Wydano'} {money(category.spent)} · plan {money(category.planned)}</small>{category.monthly_reserve_managed&&<small>Pula mediów — kwotę zmienisz w sekcji „Odłożenia i miesięczne pule”.</small>}<button className="budget-text-button" aria-label={'Edytuj kategorię: '+(category.path??category.name)} onClick={()=>openCategory(null,category)}><Pencil size={13}/>Edytuj</button></div><label>Limit miesięczny<span className="budget-amount-input"><input aria-label={'Limit: '+(category.path??category.name)} type="number" min="0" step="0.01" disabled={category.monthly_reserve_managed} value={category.monthly_reserve_managed?String(category.planned):planDrafts[category.id]??''} onChange={e=>setPlanDrafts(old=>({...old,[category.id]:e.target.value}))}/> PLN</span></label><button className="budget-button-secondary" disabled={busy||category.monthly_reserve_managed||((category.plan_source===undefined||category.plan_source==='MONTH')&&inputAmount(planDrafts[category.id]??'0')===category.manual_plan)} onClick={()=>void action(()=>budgetWorkspaceApi.setPlan(category.id,month,inputAmount(planDrafts[category.id]??'0')).then(()=>undefined),'Limit zapisany.')}>Zapisz</button></div>)}</details>}
                {children.length > 0 && <p className="budget-plan-explanation">Łączny plan {root.name}: <strong>{money(root.planned)}</strong> · limity podkategorii: {money(root.children_plan ?? 0)}{(root.direct_planned_bills ?? 0)>0 && <> · rachunki ogólne: {money(root.direct_planned_bills ?? 0)}</>}. Kwoty podkategorii mieszczą się we wspólnym limicie. Jeśli ich suma z rachunkami ogólnymi jest wyższa, łączny plan rośnie do tej sumy.</p>}
                </>}
                <BudgetCategoryPayments category={root} data={data} reload={reload}/>
              </section>;
            })}</div>
            <button type="button" className="budget-text-button budget-add-category" onClick={() => openCategory()}><CirclePlus size={18} /> Dodaj kategorię</button>
          </section>{data.planning && <><BudgetReservePlans data={data} reload={reload} editing={planEditing}/><details className="budget-plan-settings"><summary>Sprawdzenie i zamknięcie miesiąca</summary><BudgetCarryoverPolicies data={data} reload={reload} mode="closing"/></details></>}<details className="budget-plan-settings"><summary>Tempo wybranych kategorii</summary><BudgetSpendingPace data={data}/></details></>}

          {view === 'entries' && <section className="budget-panel surface-card">
            <div className="budget-section-heading"><div><p className="page-eyebrow">{monthLabel(month)}</p><h2>Transakcje miesiąca</h2><p>Zakupy bez kategorii liczą się do wydatków. Paragon możesz dołączyć później i rozdzielić produkty.</p></div><Link className="budget-button-primary" to={`/budget/imports?tab=receipt&month=${month}`}><Camera size={17} /> Dodaj paragon</Link></div>
            {data.entries.length === 0 && !(data.bank_transfers?.length) ? <div className="budget-small-empty">Nie ma jeszcze wpisów w tym miesiącu. <button type="button" onClick={() => openEntry('EXPENSE')}>Dodaj pierwszy wydatek</button></div> :
              <BudgetTransactions data={data}>{entry => <article className="budget-entry" key={entry.id}>
                <span className={entry.kind === 'INCOME' ? 'budget-entry-icon is-income' : 'budget-entry-icon'}>{entry.kind === 'TRANSFER' ? <ArrowRight size={19} /> : entry.kind === 'INCOME' ? <ArrowDownLeft size={19} /> : <ArrowUpRight size={19} />}</span>
                <div className="budget-entry-description"><strong>{entry.description}</strong><span>{dateLabel(entry.date)} · {entry.account_name}{entry.lines.length > 0 ? ' · ' + entry.lines.map(line => line.category_name).filter((name, index, all) => all.indexOf(name) === index).join(', ') : ''}</span>
                  {entry.lines.length > 1 && <small>{entry.lines.map(line => (line.label || line.category_name) + ' ' + money(line.amount)).join(' · ')}</small>}
                  {entry.kind === 'EXPENSE' && <small className={entry.classification_status === 'UNASSIGNED' ? 'budget-classification is-pending' : 'budget-classification'}>{entry.classification_status === 'UNASSIGNED' ? <Link to="/budget/imports">Do przypisania</Link> : entry.classification_status === 'SPLIT' ? 'Podział na pozycje' : 'Kategoria ogólna'}{entry.cash_effect === false ? ' · Saldo nie pomniejszone' : ''}</small>}
                  {entry.kind === 'EXPENSE' && entry.cash_effect === false && !entry.bill_id && !entry.loan_id && <button type="button" className="budget-text-button budget-apply-balance" disabled={busy} aria-label={'Uwzględnij w saldzie: '+entry.description} onClick={()=>void applyEntryBalance(entry)}><Wallet size={14}/>Uwzględnij w saldzie</button>}
                  {entry.kind==='REFUND'&&<small>Zwrot zakupu #{entry.refund_of} · zmniejsza wydatki, poza dochodem</small>}{!!entry.refunded&&<small>Zwrócono {money(entry.refunded)}</small>}{entry.kind === 'TRANSFER' && <small>Transfer {entry.direction === 'IN' ? 'z' : 'do'}: {entry.portfolio_name} · poza przychodami i wydatkami</small>}
                </div>
                <strong className={entry.kind === 'INCOME'||entry.kind==='REFUND' ? 'budget-entry-amount is-income' : 'budget-entry-amount'}>{entry.kind === 'INCOME'||entry.kind==='REFUND' || (entry.kind === 'TRANSFER' && entry.direction === 'IN') ? '+' : '−'}{money(entry.amount)}</strong>
                <div className="budget-entry-actions">
                  {entry.kind==='EXPENSE'&&(entry.refunded??0)<entry.amount&&<button type="button" title="Zapisz zwrot zakupu" aria-label={'Zapisz zwrot: '+entry.description} disabled={busy} onClick={()=>setRefundPurchase(entry)}><ArrowDownLeft size={17}/></button>}
                  {entry.kind === 'EXPENSE' && <Link to={`/budget/imports?tab=receipt&entry_id=${entry.id}`} title="Dołącz lub rozlicz paragon" aria-label={'Dołącz paragon: ' + entry.description}><Camera size={17}/></Link>}
                  {entry.has_receipt && <a href={budgetWorkspaceApi.receiptUrl(entry.id)} title="Pobierz paragon" aria-label={'Pobierz paragon: ' + entry.description}><FileText size={17} /></a>}
                  {entry.kind !== 'TRANSFER' && entry.kind !== 'REFUND' && !(entry.refunded??0) && !entry.bill_id && !entry.loan_id && <button type="button" title="Edytuj wpis" aria-label={'Edytuj: ' + entry.description} onClick={() => openEntry(entry.kind as 'INCOME' | 'EXPENSE', entry)}><Pencil size={16} /></button>}
                  {entry.kind === 'TRANSFER' ? <Link to={'/portfolio/' + entry.portfolio_id} title="Otwórz powiązany portfel" aria-label={'Otwórz portfel powiązany z: ' + entry.description}><ArrowRight size={16} /></Link> : entry.loan_id ? <Link to={'/loans/' + entry.loan_id} title="Otwórz kredyt" aria-label={'Otwórz kredyt powiązany z: ' + entry.description}><ArrowRight size={16} /></Link> :
                    <button type="button" title="Usuń wpis" aria-label={'Usuń: ' + entry.description} onClick={() => deleteEntry(entry)}><Trash2 size={16} /></button>}
                </div>
              </article>}</BudgetTransactions>}
          </section>}

          {view === 'bills' && <><BudgetObligations data={data} reload={reload}/><section className="budget-panel surface-card"><h2>Raty kredytów w miesiącu</h2>{data.planning?.loans?.map(loan=><div className="budget-category-payment" key={`${loan.id}-${loan.installment_month}`}><div><strong>{loan.name}</strong><small>{dateLabel(loan.date)} · {data.accounts.find(a=>a.id===loan.account_id)?.name??'Ustaw konto w kredycie'} · {data.categories.find(c=>c.id===loan.category_id)?.selection_label}</small><span className="budget-payment-status">{loan.paid?'Spłata zapisana':'Do rozliczenia'}</span></div><b>{money(loan.paid_amount??loan.amount)}</b><Link className="budget-text-button" to={`/loans/${loan.id}?installment=${loan.installment_month}`}>{loan.paid?'Szczegóły':'Rozlicz'}</Link></div>)}{!data.planning?.loans?.length&&<p className="bp-help">Brak rat w tym miesiącu.</p>}</section></>}
          {view === 'cycle' && data.planning && <BudgetPayCycle key={month + ':' + data.planning.settings.version} data={data} forecast={forecast} reload={reload}/>}
          {view === 'purchases' && data.planning && <BudgetPurchases data={data} reload={reload}/>}
          {view === 'settings' && <>
            <BudgetDefaultPlans key={month} data={data} reload={reload}/>
            <section className="budget-panel surface-card"><div className="budget-section-heading"><div><p className="page-eyebrow">Twoja struktura budżetu</p><h2>Kategorie i podkategorie</h2><p>Tu zmienisz nazwy, podział i kategorie uwzględniane w tempie. Limity ustawisz w planie miesiąca.</p></div><button className="budget-button-secondary" onClick={()=>openCategory()}><Plus size={16}/>Dodaj kategorię</button></div>
              <label>Szukaj kategorii<input type="search" value={categorySearch} onChange={event=>setCategorySearch(event.target.value)}/></label>
              <div className="budget-settings-categories">{data.categories.filter(c=>!c.is_unassigned&&(c.selection_label??c.name).toLocaleLowerCase('pl').includes(categorySearch.toLocaleLowerCase('pl'))).map(category=><div key={category.id} className="budget-settings-category"><div><strong>{category.selection_label??category.name}</strong><small>{category.daily_pace_effective===false?'Poza wskaźnikiem tempa':'Uwzględniana w tempie'}</small></div><div className="br-actions"><button className="budget-text-button" aria-label={`Edytuj kategorię: ${category.path??category.name}`} onClick={()=>openCategory(null,category)}><Pencil size={14}/>Edytuj</button>{!category.parent_id&&<button className="budget-text-button" aria-label={`Dodaj podkategorię do: ${category.name}`} onClick={()=>openCategory(category.id)}><Plus size={14}/>Podkategoria</button>}</div></div>)}</div>
            </section>
            <section className="budget-panel surface-card"><h2>Automatyczne przypisywanie</h2><p className="bp-help">Kategorie sklepów i odbiorców oraz przelewy na rezerwy.</p><Link className="budget-button-secondary" to={`/budget/imports?tab=rules&month=${month}`}>Reguły kategorii i rezerw <ArrowRight size={15}/></Link></section>
            {data.planning&&<><BudgetPayCycle key={`settings:${month}:${data.planning.settings.version}`} data={data} forecast={forecast} reload={reload} settingsOnly/><BudgetCarryoverPolicies data={data} reload={reload} mode="settings"/></>}
          </>}
          {view === 'overview' && forecast && <details className="budget-plan-settings"><summary>Salda kont i potrzebne przelewy w kolejnych 30 dniach</summary><ForecastAccounts data={forecast}/></details>}
        </>}

      {data&&refundPurchase&&<BudgetRefundDialog purchase={refundPurchase} data={data} reload={reload} onClose={()=>setRefundPurchase(null)}/>}
      {ruleSuggestion&&<BudgetRuleSuggestion suggestion={ruleSuggestion} onClose={()=>setRuleSuggestion(null)}/>}
      {entryMode && data && <div className="budget-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !busy) setEntryMode(null); }}>
        <section role="dialog" aria-modal="true" aria-label={editingEntry ? 'Edytuj wpis' : entryMode === 'RECEIPT' ? 'Dodaj paragon' : entryMode === 'INCOME' ? 'Dodaj przychód' : 'Dodaj wydatek'} className="budget-modal">
          <div className="budget-modal-header"><div><p className="page-eyebrow">{editingEntry ? 'Korekta' : 'Nowy wpis'}</p><h2>{editingEntry ? 'Edytuj wpis' : entryMode === 'RECEIPT' ? 'Dodaj paragon' : entryMode === 'INCOME' ? 'Dodaj przychód' : 'Dodaj wydatek'}</h2></div><button type="button" className="budget-icon-button" aria-label="Zamknij formularz" onClick={() => setEntryMode(null)}><X size={20} /></button></div>
          <form onSubmit={saveEntry} className="budget-entry-form">
            <div className="budget-form-grid">
              <label>Konto<select required value={entryAccountId} onChange={event => setEntryAccountId(event.target.value)}>{data.accounts.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>
              <label>Data<input type="date" required max={localToday()} value={entryDate} onChange={event => setEntryDate(event.target.value)} /></label>
            </div>
            {entryMode === 'RECEIPT' && <label>Sklep lub usługodawca<input value={entryMerchant} onChange={event => setEntryMerchant(event.target.value)} placeholder="np. Sklep osiedlowy" /></label>}
            <label>Opis<input required={entryMode !== 'RECEIPT'} maxLength={150} value={entryDescription} onChange={event => setEntryDescription(event.target.value)} placeholder={entryMode === 'INCOME' ? 'np. Wynagrodzenie' : 'np. Zakupy spożywcze'} /></label>
            {entryMode !== 'INCOME' && <div className="budget-line-section">
              <div className="budget-section-heading"><div><h3>Podział wydatku</h3><p>Jedna lub więcej pozycji przypisanych do kategorii.</p></div></div>
              {entryLines.map((line, index) => <div className="budget-line-row" key={index}>
                <label>Pozycja<input value={line.label} onChange={event => updateLine(index, 'label', event.target.value)} placeholder="Opcjonalny opis" /></label>
                <label>Kategoria<select required value={line.category_id} onChange={event => updateLine(index, 'category_id', event.target.value)}>{data.categories.map(category => <option key={category.id} value={category.id}>{category.selection_label ?? category.name}</option>)}</select></label>
                {entryLines.length > 1 && <label>Kwota<input type="number" min="0.01" step="0.01" required value={line.amount} onChange={event => updateLine(index, 'amount', event.target.value)} /></label>}
                {entryLines.length > 1 && <button type="button" className="budget-icon-button" aria-label={'Usuń pozycję ' + (index + 1)} onClick={() => setEntryLines(lines => lines.filter((_, lineIndex) => lineIndex !== index))}><X size={16} /></button>}
              </div>)}
              <button type="button" className="budget-text-button" onClick={() => setEntryLines(lines => [...lines, { category_id: String(data.categories[0]?.id ?? ''), label: '', amount: '' }])}><Plus size={16} /> Dodaj pozycję</button>
            </div>}
            <label>Łączna kwota w PLN<input type="number" min="0.01" step="0.01" required value={entryLines.length > 1 && entryMode !== 'INCOME' ? String(effectiveEntryAmount) : entryAmount} readOnly={entryLines.length > 1 && entryMode !== 'INCOME'} onChange={event => setEntryAmount(event.target.value)} /></label>
            {data.accounts.filter(a=>a.id===Number(entryAccountId)).map(a=>{const restored=editingEntry?.cash_effect!==false&&editingEntry?.account_id===a.id?(editingEntry?.kind==='INCOME'?-1:1)*(editingEntry?.amount??0):0;const delta=(entryMode==='INCOME'?1:-1)*effectiveEntryAmount*(editingEntry?.cash_effect===false?0:1);const after=a.balance+restored+delta;return <div className="bp-balance-preview" key={a.id}>{a.name}: <b>{money(a.balance)} → {money(after)}</b><small>{editingEntry?.cash_effect===false?'Ten wpis jest już uwzględniony w saldzie.':'Saldo po zapisaniu wpisu.'}</small>{after<0&&<strong className="budget-negative">Na tym koncie zabraknie {money(-after)}.</strong>}</div>;})}
            {entryMode !== 'INCOME' && <label className="budget-upload-label"><Camera size={18} /><span>{receiptFile ? receiptFile.name : editingEntry?.has_receipt ? 'Zamień zdjęcie paragonu (opcjonalnie)' : 'Dołącz zdjęcie lub PDF paragonu (opcjonalnie)'}</span><input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={event => setReceiptFile(event.target.files?.[0] ?? null)} /></label>}
            <div className="budget-form-actions"><button type="button" className="budget-button-quiet" onClick={() => setEntryMode(null)}>Anuluj</button><button type="submit" disabled={busy} className="budget-button-primary">{busy ? 'Zapisywanie...' : editingEntry ? 'Zapisz zmiany' : 'Dodaj wpis'}</button></div>
          </form>
        </section>
      </div>}
      {showCategoryForm && data && <ImportDialog title={editingCategory ? 'Edytuj kategorię' : categoryParent ? 'Dodaj podkategorię' : 'Dodaj kategorię'} busy={busy} onClose={() => setShowCategoryForm(false)}>
        <form onSubmit={saveCategory} className="budget-category-form">
          {error && <p role="alert" className="budget-negative">{error}</p>}
          <label>Nazwa kategorii<input required maxLength={100} value={categoryName} onChange={event => setCategoryName(event.target.value)} placeholder={categoryParent ? 'np. Paliwo, bilety, utrzymanie auta' : 'np. Transport'} /></label>
          <label>Kategoria główna<select value={categoryParent} onChange={event => setCategoryParent(event.target.value)} disabled={!!editingCategory && data.categories.some(c => c.parent_id === editingCategory.id)}><option value="">Samodzielna kategoria główna</option>{data.categories.filter(c => !c.parent_id && !c.is_unassigned && c.id !== editingCategory?.id).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
          <label className="budget-checkbox"><input type="checkbox" checked={categoryDailyPace} onChange={event=>setCategoryDailyPace(event.target.checked)}/>Uwzględniaj w tempie codziennych wydatków</label>
          <p className="budget-plan-explanation">Wyłącz np. paliwo kupowane raz na kilka tygodni. Z tempa usuniemy wydatki i limit tej kategorii; pełny budżet, prognoza oraz saldo nadal ją uwzględniają. Wyłączenie kategorii głównej obejmuje jej podkategorie. Dla wyłączanej podkategorii ustaw osobny limit, aby odjąć go od wspólnego planu.</p>
          {categoryParent&&data.categories.find(c=>c.id===Number(categoryParent))?.daily_pace_included===false&&<p className="bp-warning">Kategoria główna jest wyłączona z tempa, więc ta podkategoria również nie będzie liczona.</p>}
          <p className="budget-plan-explanation">Wydatki podkategorii są uwzględnione w sumie kategorii głównej. Zmiana nazwy lub przeniesienie kategorii zachowuje jej wpisy, rachunki i reguły importu oraz przelicza także wcześniejsze miesiące.</p>
          <div className="budget-form-actions"><button type="button" className="budget-button-quiet" disabled={busy} onClick={() => setShowCategoryForm(false)}>Anuluj</button><button type="submit" className="budget-button-primary" disabled={busy}>{busy ? 'Zapisywanie…' : editingCategory ? 'Zapisz zmiany' : 'Dodaj'}</button></div>
        </form>
      </ImportDialog>}
      {copyPlan&&data&&<BudgetPlanCopy data={data} reload={reload} onClose={()=>setCopyPlan(false)}/>}
    </div>
  );
}
