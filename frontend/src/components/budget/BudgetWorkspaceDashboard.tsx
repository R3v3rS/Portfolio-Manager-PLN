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
import BudgetTransactionRow from './BudgetTransactionRow';
import BudgetCategoryPlanTable from './BudgetCategoryPlanTable';
import BudgetYearPlan from './BudgetYearPlan';
import BudgetPlanTransfer from './BudgetPlanTransfer';
import BudgetReviewQueue from './BudgetReviewQueue';
import BudgetNextActions from './BudgetNextActions';
import BudgetDefaultPlans from './BudgetDefaultPlans';
import BudgetPlanCopy from './BudgetPlanCopy';
import BudgetCategorySettings from './BudgetCategorySettings';
import { BudgetPlanningOverview, BudgetPayCycle, ForecastAccounts } from './BudgetPlanningOverview';
import { BudgetReservePlans, BudgetCarryoverPolicies } from './BudgetReservePlans';
import BudgetObligations from './BudgetObligations';
import BudgetPurchases from './BudgetPurchases';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import {
  ArrowRight, Camera,
  ClipboardList, CreditCard,
  Pencil, Plus, Wallet, X,
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

export default function BudgetWorkspaceDashboard() {
  const [refundPurchase,setRefundPurchase]=useState<BudgetEntry|null>(null);
  const [ruleSuggestion,setRuleSuggestion]=useState<RuleSuggestion|null>(null);
  const [planEditing,setPlanEditing]=useState(false);
  const [showYear,setShowYear]=useState(false);
  const [showClosing,setShowClosing]=useState(false);
  const [copyPlan,setCopyPlan]=useState(false);
  const [categorySearch,setCategorySearch]=useState('');
  const [showUnusedCategories,setShowUnusedCategories]=useState(false);
  const [transferPlan,setTransferPlan]=useState(false);
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const settingsTab=params.get('settings')??(location.hash==='#default-plans'?'defaults':'categories');
  const openedEntryId = useRef<number | null>(null);
  const month = budgetMonth(params.get('month'));
  const view: View = ['overview', 'plan', 'entries', 'bills', 'cycle', 'purchases', 'settings'].includes(params.get('view') || '') ? params.get('view') as View : 'overview';
  const setMonth = (value: string) => { const next = new URLSearchParams(params); next.set('month', value); setParams(next); };
  const setView = useCallback((value: View) => { const next = new URLSearchParams(params); next.set('view', value); next.set('month', month); next.delete('bill'); next.delete('edit_entry'); setParams(next); },[params,month,setParams]);
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
  const [categoryDescription, setCategoryDescription] = useState('');
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
    setEntryAccountId(String(entry?.account_id ?? data?.accounts.find(a=>mode!=='INCOME'||a.account_type!=='CREDIT_CARD')?.id ?? ''));
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
  }, [data, params, openEntry, setView]);

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
      if (editingCategory) await budgetWorkspaceApi.updateCategory(editingCategory.id, categoryName, categoryParent ? Number(categoryParent) : null, editingCategory.version ?? 1, categoryDailyPace, categoryDescription);
      else await budgetWorkspaceApi.createCategory(categoryName, categoryParent ? Number(categoryParent) : null, categoryDailyPace, categoryDescription);
      setCategoryName('');
      setShowCategoryForm(false);
    }, editingCategory ? 'Kategoria zmieniona. Dotychczasowe wpisy zachowały przypisanie.' : 'Kategoria dodana.');
  };

  const openCategory = (parent: number | null = null, category: BudgetCategory | null = null) => {
    setEditingCategory(category); setCategoryName(category?.name ?? '');
    setCategoryDescription(category?.description ?? '');
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
          <h1>{view==='plan'?'Plan miesiąca':view==='entries'?'Transakcje':view==='bills'?'Rachunki i raty':view==='settings'?'Ustawienia budżetu':view==='cycle'?'Okres rozliczeniowy':view==='purchases'?'Większe zakupy':'Budżet pod kontrolą'}</h1>
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
          <details className="budget-topline budget-topline-compact"><summary>Salda kont teraz</summary>
            <div className="budget-account-list">
              <span className="budget-muted-label">Salda teraz</span>
              {data.accounts.map(account => <span className="budget-account-pill" key={account.id}><CreditCard size={14} />{account.name}<strong>{money(account.balance)}</strong></span>)}
              <button type="button" className="budget-text-button" onClick={() => setShowAccountForm(!showAccountForm)}><Plus size={15} /> Dodaj konto</button>
            </div>

          </details>
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
              <article className="budget-stat"><span>Do rozdysponowania w planie</span><strong className={data.totals.to_plan < 0 ? 'budget-negative' : ''}>{money(data.totals.to_plan)}</strong><small>Saldo + oczekiwane wpływy − pozostałe limity i zobowiązania − odłożenia − rezerwy ({money(data.totals.reserved ?? 0)})</small><Link className="budget-stat-income" to={`/budget/forecast?month=${month}`}>Wpływy do otrzymania: {money(data.totals.expected_income ?? 0)} <ArrowRight size={13} /></Link><small>Plan dla wybranego miesiąca. Otrzymane wpływy są już w saldzie.</small></article>
            </section>}
            {!data.planning&&<BudgetSpendingSummary data={data}/>}
            <BudgetNextActions data={data} forecast={forecast}/><BudgetReviewQueue data={data} forecast={forecast}/>
            <BudgetCharts key={month} data={data} />
            <details className="budget-plan-settings"><summary>Kategorie i szczegóły wykonania</summary>
              <div className="budget-category-list">{data.categories.filter(c=>!c.parent_id&&(c.planned>0||c.spent!==0)).map(c=><div key={c.id} className="budget-category-payment"><div><strong>{c.name}</strong><small>Wykorzystano {money(c.spent)} z {money(c.planned)}</small></div><b className={c.remaining<0?'budget-negative':''}>{c.remaining<0?'Przekroczono':'Pozostało'} {money(Math.abs(c.remaining))}</b><Link className="budget-text-button" to={`/budget?view=plan&month=${month}#category-${c.id}`}>Sprawdź limit</Link></div>)}</div>
            </details>
          </>}

          {view === 'plan' && <>
            <div className="budget-view-toolbar"><div className="br-tabs" aria-label="Zakres planu"><button aria-pressed={!showYear} className={!showYear?'is-active':''} onClick={()=>setShowYear(false)}>Miesiąc</button><button aria-pressed={showYear} className={showYear?'is-active':''} onClick={()=>setShowYear(true)}>12 miesięcy</button></div><div className="br-actions"><button className="budget-button-secondary" onClick={()=>setTransferPlan(true)}>Przenieś limit</button><button className="budget-button-secondary" onClick={()=>setShowClosing(true)}>Rozlicz miesiąc</button></div></div>
            {showYear?<BudgetYearPlan month={month}/>:<>
              <div className="budget-plan-summary"><span>Do rozdysponowania <b className={data.totals.to_plan<0?'budget-negative':''}>{money(data.totals.to_plan)}</b></span><span>Plan kategorii <b>{money(data.totals.planned)}</b></span><span>Wybrany miesiąc <b>{monthLabel(month)}</b></span></div>
              <details className="budget-plan-settings"><summary>Podział planu: wpływy, płatności i odłożenia</summary><BudgetMonthPlan data={data} reload={reload}/></details>
              <div className="budget-view-toolbar"><div className="br-actions"><button className="budget-button-secondary" disabled={busy} onClick={()=>void action(()=>budgetWorkspaceApi.copyPlans(previousMonth,month).then(()=>undefined),'Skopiowano brakujące limity.')}>Kopiuj poprzedni miesiąc</button><button className="budget-button-secondary" onClick={()=>setCopyPlan(true)}><ClipboardList size={16}/>Kopiuj na 3, 6 lub 12 miesięcy</button></div><button className="budget-button-primary" disabled={busy} aria-pressed={planEditing} onClick={()=>setPlanEditing(!planEditing)}><Pencil size={15}/>{planEditing?'Zamknij edycję limitów':'Edytuj limity'}</button></div>
              <BudgetCategoryPlanTable data={data} editing={planEditing} busy={busy} drafts={planDrafts} setDraft={(id,value)=>setPlanDrafts(old=>({...old,[id]:value}))} onSave={category=>void action(()=>budgetWorkspaceApi.setPlan(category.id,month,inputAmount(planDrafts[category.id]??'0')).then(()=>undefined),'Limit zapisany.')} onReset={category=>void action(()=>budgetWorkspaceApi.resetPlan(category.id,month).then(()=>undefined),'Przywrócono domyślny limit.')} onEdit={category=>openCategory(null,category)} onAdd={parent=>openCategory(parent)} reload={reload}/>
              {data.planning&&<BudgetReservePlans data={data} reload={reload} editing={planEditing}/>}
              <details className="budget-plan-settings"><summary>Tempo wybranych kategorii</summary><BudgetSpendingPace data={data}/></details>
            </>}
          </>}

          {view === 'entries' && <section className="budget-panel surface-card">
            <div className="budget-section-heading"><div><p className="page-eyebrow">{monthLabel(month)}</p><h2>Transakcje miesiąca</h2><p>Zakupy bez kategorii liczą się do wydatków. Paragon możesz dołączyć później i rozdzielić produkty.</p></div><Link className="budget-button-primary" to={`/budget/imports?tab=receipt&month=${month}`}><Camera size={17} /> Dodaj paragon</Link></div>
            {data.entries.length === 0 && !(data.bank_transfers?.length) ? <div className="budget-small-empty">Nie ma jeszcze wpisów w tym miesiącu. <button type="button" onClick={() => openEntry('EXPENSE')}>Dodaj pierwszy wydatek</button></div> :
              <BudgetTransactions data={data}>{entry=><BudgetTransactionRow key={entry.id} entry={entry} busy={busy} edit={value=>openEntry(value.kind as 'INCOME'|'EXPENSE',value)} apply={value=>void applyEntryBalance(value)} refund={setRefundPurchase} remove={value=>void deleteEntry(value)}/>}</BudgetTransactions>}
          </section>}

          {view === 'bills' && <><BudgetObligations data={data} reload={reload}/><section className="budget-panel surface-card"><h2>Raty kredytów w miesiącu</h2>{data.planning?.loans?.map(loan=><div className="budget-category-payment" key={`${loan.id}-${loan.installment_month}`}><div><strong>{loan.name}</strong><small>{dateLabel(loan.date)} · {data.accounts.find(a=>a.id===loan.account_id)?.name??'Ustaw konto w kredycie'} · {data.categories.find(c=>c.id===loan.category_id)?.selection_label}</small><span className="budget-payment-status">{loan.paid?'Spłata zapisana':'Do rozliczenia'}</span></div><b>{money(loan.paid_amount??loan.amount)}</b><Link className="budget-text-button" to={`/loans/${loan.id}?installment=${loan.installment_month}`}>{loan.paid?'Szczegóły':'Rozlicz'}</Link></div>)}{!data.planning?.loans?.length&&<p className="bp-help">Brak rat w tym miesiącu.</p>}</section></>}
          {view === 'cycle' && data.planning && <BudgetPayCycle key={month + ':' + data.planning.settings.version} data={data} forecast={forecast} reload={reload}/>}
          {view === 'purchases' && data.planning && <BudgetPurchases data={data} reload={reload}/>}
          {view === 'settings' && <>
            <div className="br-tabs budget-settings-tabs" aria-label="Sekcje ustawień">{[['categories','Kategorie'],['defaults','Plan domyślny'],['rules','Reguły'],['planning','Konta i okres'],['closing','Koniec miesiąca']].map(([id,name])=><button key={id} aria-pressed={settingsTab===id} className={settingsTab===id?'is-active':''} onClick={()=>{const next=new URLSearchParams(params);next.set('settings',id);setParams(next);}}>{name}</button>)}</div>
            {settingsTab==='defaults'&&<BudgetDefaultPlans key={month} data={data} reload={reload}/>}
            {settingsTab==='categories'&&<>
            <section className="budget-panel surface-card"><div className="budget-section-heading"><div><p className="page-eyebrow">Twoja struktura budżetu</p><h2>Kategorie i podkategorie</h2><p>Tu zmienisz nazwy, podział i kategorie uwzględniane w tempie. Limity ustawisz w planie miesiąca.</p></div><button className="budget-button-secondary" onClick={()=>openCategory()}><Plus size={16}/>Dodaj kategorię</button></div>
              <label>Szukaj kategorii<input type="search" value={categorySearch} onChange={event=>setCategorySearch(event.target.value)}/></label>
              <label className="budget-checkbox"><input type="checkbox" checked={showUnusedCategories} onChange={event=>setShowUnusedCategories(event.target.checked)}/>Pokaż nieużywane kategorie</label><BudgetCategorySettings categories={data.categories} search={categorySearch} showUnused={showUnusedCategories} edit={category=>openCategory(null,category)} add={parent=>openCategory(parent)}/>
            </section>
            </>}{settingsTab==='rules'&&<section className="budget-panel surface-card"><h2>Automatyczne przypisywanie</h2><p className="bp-help">Kategorie sklepów i odbiorców oraz przelewy na rezerwy.</p><Link className="budget-button-secondary" to={`/budget/imports?tab=rules&month=${month}`}>Reguły kategorii i rezerw <ArrowRight size={15}/></Link></section>}
            {data.planning&&settingsTab==='planning'&&<BudgetPayCycle key={`settings:${month}:${data.planning.settings.version}`} data={data} forecast={forecast} reload={reload} settingsOnly/>}{data.planning&&settingsTab==='closing'&&<BudgetCarryoverPolicies data={data} reload={reload} mode="settings"/>}
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
              <label>Konto<select required value={entryAccountId} onChange={event => setEntryAccountId(event.target.value)}>{data.accounts.filter(a=>entryMode!=='INCOME'||a.account_type!=='CREDIT_CARD').map(account => <option key={account.id} value={account.id}>{account.name}{account.account_type==='CREDIT_CARD'?' · karta kredytowa':''}</option>)}</select></label>
              <label>Data<input type="date" required max={localToday()} value={entryDate} onChange={event => setEntryDate(event.target.value)} /></label>
            </div>
            {entryMode === 'RECEIPT' && <label>Sklep lub usługodawca<input value={entryMerchant} onChange={event => setEntryMerchant(event.target.value)} placeholder="np. Sklep osiedlowy" /></label>}
            <label>Opis<input required={entryMode !== 'RECEIPT'} maxLength={150} value={entryDescription} onChange={event => setEntryDescription(event.target.value)} placeholder={entryMode === 'INCOME' ? 'np. Wynagrodzenie' : 'np. Zakupy spożywcze'} /></label>
            {entryMode !== 'INCOME' && <div className="budget-line-section">
              <div className="budget-section-heading"><div><h3>Podział wydatku</h3><p>Jedna lub więcej pozycji przypisanych do kategorii.</p></div></div>
              {entryLines.map((line, index) => <div className="budget-line-row" key={index}>
                <label>Pozycja<input value={line.label} onChange={event => updateLine(index, 'label', event.target.value)} placeholder="Opcjonalny opis" /></label>
                <label>Kategoria<select required value={line.category_id} onChange={event => updateLine(index, 'category_id', event.target.value)}>{data.categories.map(category => <option key={category.id} value={category.id} title={category.description}>{category.selection_label ?? category.name}</option>)}</select>{data.categories.find(category=>category.id===Number(line.category_id))?.description&&<small className="budget-category-description">{data.categories.find(category=>category.id===Number(line.category_id))?.description}</small>}</label>
                {entryLines.length > 1 && <label>Kwota<input type="number" min="0.01" step="0.01" required value={line.amount} onChange={event => updateLine(index, 'amount', event.target.value)} /></label>}
                {entryLines.length > 1 && <button type="button" className="budget-icon-button" aria-label={'Usuń pozycję ' + (index + 1)} onClick={() => setEntryLines(lines => lines.filter((_, lineIndex) => lineIndex !== index))}><X size={16} /></button>}
              </div>)}
              <button type="button" className="budget-text-button" onClick={() => setEntryLines(lines => [...lines, { category_id: String(data.categories[0]?.id ?? ''), label: '', amount: '' }])}><Plus size={16} /> Dodaj pozycję</button>
            </div>}
            <label>Łączna kwota w PLN<input type="number" min="0.01" step="0.01" required value={entryLines.length > 1 && entryMode !== 'INCOME' ? String(effectiveEntryAmount) : entryAmount} readOnly={entryLines.length > 1 && entryMode !== 'INCOME'} onChange={event => setEntryAmount(event.target.value)} /></label>
            {data.accounts.filter(a=>a.id===Number(entryAccountId)).map(a=>{const restored=editingEntry?.cash_effect!==false&&editingEntry?.account_id===a.id?(editingEntry?.kind==='INCOME'?-1:1)*(editingEntry?.amount??0):0;const delta=(entryMode==='INCOME'?1:-1)*effectiveEntryAmount*(editingEntry?.cash_effect===false?0:1);const after=a.balance+restored+delta;return <div className="bp-balance-preview" key={a.id}>{a.name}: <b>{money(a.balance)} → {money(after)}</b><small>{editingEntry?.cash_effect===false?'Ten wpis jest już uwzględniony w saldzie.':'Saldo po zapisaniu wpisu.'}</small>{a.account_type==='CREDIT_CARD'?<strong>Zadłużenie po zakupie: {money(Math.max(0,-after))}. Zakup obciąży kategorię w dniu transakcji; spłata będzie przelewem.</strong>:after<0&&<strong className="budget-negative">Na tym koncie zabraknie {money(-after)}.</strong>}</div>;})}
            {entryMode !== 'INCOME' && <label className="budget-upload-label"><Camera size={18} /><span>{receiptFile ? receiptFile.name : editingEntry?.has_receipt ? 'Zamień zdjęcie paragonu (opcjonalnie)' : 'Dołącz zdjęcie lub PDF paragonu (opcjonalnie)'}</span><input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={event => setReceiptFile(event.target.files?.[0] ?? null)} /></label>}
            <div className="budget-form-actions"><button type="button" className="budget-button-quiet" onClick={() => setEntryMode(null)}>Anuluj</button><button type="submit" disabled={busy} className="budget-button-primary">{busy ? 'Zapisywanie...' : editingEntry ? 'Zapisz zmiany' : 'Dodaj wpis'}</button></div>
          </form>
        </section>
      </div>}
      {showCategoryForm && data && <ImportDialog title={editingCategory ? 'Edytuj kategorię' : categoryParent ? 'Dodaj podkategorię' : 'Dodaj kategorię'} busy={busy} onClose={() => setShowCategoryForm(false)}>
        <form onSubmit={saveCategory} className="budget-category-form">
          {error && <p role="alert" className="budget-negative">{error}</p>}
          <label>Nazwa kategorii<input required maxLength={100} value={categoryName} onChange={event => setCategoryName(event.target.value)} placeholder={categoryParent ? 'np. Paliwo, bilety, utrzymanie auta' : 'np. Transport'} /></label>
          <label>Opis i przykłady<textarea maxLength={500} rows={3} value={categoryDescription} onChange={event=>setCategoryDescription(event.target.value)} placeholder="Co zaliczasz do tej kategorii, a co przypisujesz gdzie indziej?"/></label>
          <label>Kategoria główna<select value={categoryParent} onChange={event => setCategoryParent(event.target.value)} disabled={!!editingCategory && data.categories.some(c => c.parent_id === editingCategory.id)}><option value="">Samodzielna kategoria główna</option>{data.categories.filter(c => !c.parent_id && !c.is_unassigned && c.id !== editingCategory?.id).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
          <label className="budget-checkbox"><input type="checkbox" checked={categoryDailyPace} onChange={event=>setCategoryDailyPace(event.target.checked)}/>Uwzględniaj w tempie codziennych wydatków</label>
          <p className="budget-plan-explanation">Wyłącz np. paliwo kupowane raz na kilka tygodni. Z tempa usuniemy wydatki i limit tej kategorii; pełny budżet, prognoza oraz saldo nadal ją uwzględniają. Wyłączenie kategorii głównej obejmuje jej podkategorie. Dla wyłączanej podkategorii ustaw osobny limit, aby odjąć go od wspólnego planu.</p>
          {categoryParent&&data.categories.find(c=>c.id===Number(categoryParent))?.daily_pace_included===false&&<p className="bp-warning">Kategoria główna jest wyłączona z tempa, więc ta podkategoria również nie będzie liczona.</p>}
          <p className="budget-plan-explanation">Wydatki podkategorii są uwzględnione w sumie kategorii głównej. Zmiana nazwy lub przeniesienie kategorii zachowuje jej wpisy, rachunki i reguły importu oraz przelicza także wcześniejsze miesiące.</p>
          <div className="budget-form-actions"><button type="button" className="budget-button-quiet" disabled={busy} onClick={() => setShowCategoryForm(false)}>Anuluj</button><button type="submit" className="budget-button-primary" disabled={busy}>{busy ? 'Zapisywanie…' : editingCategory ? 'Zapisz zmiany' : 'Dodaj'}</button></div>
        </form>
      </ImportDialog>}
      {showClosing&&data?.planning&&<ImportDialog title={`Rozliczenie miesiąca · ${monthLabel(month)}`} busy={busy} onClose={()=>setShowClosing(false)}><BudgetCarryoverPolicies data={data} reload={reload} mode="closing"/></ImportDialog>}
      {transferPlan&&data&&<BudgetPlanTransfer data={data} reload={reload} onClose={()=>setTransferPlan(false)}/>}
      {copyPlan&&data&&<BudgetPlanCopy data={data} reload={reload} onClose={()=>setCopyPlan(false)}/>}
    </div>
  );
}
