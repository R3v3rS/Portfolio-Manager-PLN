import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { TrendChart } from '../charts/ChartKit';

import LoanPaymentChart from './LoanPaymentChart';
import LoanPaymentLink from './LoanPaymentLink';
import LoanBudgetSettingsPanel from './LoanBudgetSettingsPanel';
import { ArrowLeft, ArrowRight, CalendarDays, Check, CheckCircle2, CircleDollarSign, ClipboardCheck,
  Plus, RotateCcw, Save, SlidersHorizontal, Trash2, Wallet, X } from 'lucide-react';
import {
  addOverpayment, addRate, deleteInstallment, deleteOverpayment, getSchedule,
  recordBalanceCheck, recordInstallment, setLoanNetWorthExclusion, type LoanScheduleEntry, type LoanScheduleResponse,type LoanPaymentSelection,
} from '../../api_loans';
import { budgetWorkspaceApi, type BudgetAccount,type BudgetCategory } from '../../api_budget_workspace';
import { extractErrorMessageFromUnknown } from '../../http/response';
import './loansWorkspace.css';

const money = (value: number) => new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(value);
const localToday = () => {
  const now = new Date();
  return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
};
const dateLabel = (value: string | null) => value
  ? new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value.slice(0, 10) + 'T12:00:00'))
  : 'Brak';

export default function LoanWorkspaceDetail() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const loanId = Number(id);
  const [data, setData] = useState<LoanScheduleResponse | null>(null);
  const [accounts, setAccounts] = useState<BudgetAccount[]>([]);
  const [categories,setCategories]=useState<BudgetCategory[]>([]);
  const [paymentLink,setPaymentLink]=useState<LoanPaymentSelection>({ready:false});
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<'overview' | 'schedule' | 'scenario' | 'history'>(() => params.has('installment') ? 'schedule' : 'overview');
  const [scenarioAmount, setScenarioAmount] = useState('0');
  const [debouncedAmount, setDebouncedAmount] = useState(0);
  const [scenarioAction, setScenarioAction] = useState<'REDUCE_TERM' | 'REDUCE_INSTALLMENT'>('REDUCE_TERM');
  const [paymentTarget, setPaymentTarget] = useState<LoanScheduleEntry | null>(null);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(localToday);
  const [paymentAccount, setPaymentAccount] = useState('');
  const [paymentToBudget,setPaymentToBudget]=useState<LoanScheduleResponse['payments_list'][number]|null>(null);
  const [overpaymentAmount, setOverpaymentAmount] = useState('');
  const [overpaymentDate, setOverpaymentDate] = useState(localToday);
  const [overpaymentAction, setOverpaymentAction] = useState<'REDUCE_TERM' | 'REDUCE_INSTALLMENT'>('REDUCE_TERM');
  const [overpaymentAccount, setOverpaymentAccount] = useState('');
  const [rate, setRate] = useState('');
  const [rateDate, setRateDate] = useState(localToday);
  const [balance, setBalance] = useState('');
  const [balanceDate, setBalanceDate] = useState(localToday);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedAmount(Math.max(0, Number(scenarioAmount) || 0)), 350);
    return () => window.clearTimeout(timer);
  }, [scenarioAmount]);
  const refresh = useCallback(async () => {
    if (!Number.isInteger(loanId) || loanId <= 0) return;
    const result = await getSchedule(loanId, debouncedAmount > 0
      ? { monthly_overpayment: debouncedAmount, simulated_action: scenarioAction } : undefined);
    setData(result);
  }, [loanId, debouncedAmount, scenarioAction]);
  const refreshAccounts = useCallback(async () => {
    try { const budget=await budgetWorkspaceApi.get(localToday().slice(0, 7));setAccounts(budget.accounts);setCategories(budget.categories??[]); }
    catch { setAccounts([]); }
  }, []);
  useEffect(() => {
    void refresh().catch(cause => setError(extractErrorMessageFromUnknown(cause) || 'Nie udało się pobrać harmonogramu.'));
  }, [refresh]);
  useEffect(() => { void refreshAccounts(); }, [refreshAccounts]);

  const action = async (work: () => Promise<unknown>, message: string) => {
    setBusy(true); setError(''); setSuccess('');
    try { await work(); }
    catch (cause) {
      setError(extractErrorMessageFromUnknown(cause) || 'Nie udało się zapisać zmiany.');
      setBusy(false);
      return false;
    }
    setSuccess(message);
    try { await refresh(); await refreshAccounts(); }
    catch (cause) { setError('Zmiana została zapisana, ale nie udało się odświeżyć widoku: ' + (extractErrorMessageFromUnknown(cause) || 'spróbuj ponownie otworzyć stronę.')); }
    finally { setBusy(false); }
    return true;
  };
  const startPayment = (row: LoanScheduleEntry) => {
    setPaymentTarget(row); setPaymentAmount(row.installment.toFixed(2));
    setPaymentDate(row.date <= localToday() ? row.date : localToday()); setPaymentAccount(String(data?.budget_settings?.resolved_account_id??''));setPaymentLink({ready:false});
  };
  const changeNetWorthExclusion = async (excluded: boolean) => {
    setBusy(true); setError(''); setSuccess('');
    try {
      const result = await setLoanNetWorthExclusion(loanId, excluded);
      setData(current => current ? { ...current, loan: { ...current.loan, exclude_from_net_worth: result.exclude_from_net_worth } } : current);
      setSuccess(result.exclude_from_net_worth ? 'Kredyt pominięty w majątku netto. Raty pozostają w planie płatności.' : 'Kredyt ponownie uwzględniany w majątku netto.');
    } catch (cause) { setError(extractErrorMessageFromUnknown(cause) || 'Nie udało się zapisać ustawienia majątku netto.'); }
    finally { setBusy(false); }
  };
  const savePayment = async (event: FormEvent) => {
    event.preventDefault();
    if (!paymentTarget) return;
    const target = paymentTarget;
    const saved = await action(() => recordInstallment(loanId, {
      installment_month: target.month, paid_on: paymentDate, amount: Number(paymentAmount),
      ...(paymentAccount ? { account_id: Number(paymentAccount) } : {}),
      ...(paymentLink.existing_entry_id?{existing_entry_id:paymentLink.existing_entry_id,entry_version:paymentLink.entry_version}:paymentLink.confirm_new_expense?{confirm_new_expense:true}:{}),
    }), paymentLink.existing_entry_id?'Spłata powiązana z istniejącym wydatkiem. Saldo nie zmieniło się.':paymentAccount ? 'Rata zapisana. Saldo wybranego konta zostało pomniejszone.' : 'Spłata zapisana bez wydatku — saldo kont nie zostało pomniejszone.');
    if (saved) setPaymentTarget(null);
  };
  const saveOverpayment = async (event: FormEvent) => {
    event.preventDefault();
    const saved = await action(() => addOverpayment(loanId, {
      amount: Number(overpaymentAmount), date: overpaymentDate, type: overpaymentAction,
      ...(overpaymentAccount ? { account_id: Number(overpaymentAccount) } : {}),
    }), 'Nadpłata została zapisana.');
    if (saved) setOverpaymentAmount('');
  };
  const saveRate = async (event: FormEvent) => {
    event.preventDefault();
    const saved = await action(() => addRate(loanId, { interest_rate: Number(rate), valid_from_date: rateDate }), 'Oprocentowanie zostało zapisane.');
    if (saved) setRate('');
  };
  const saveBalance = async (event: FormEvent) => {
    event.preventDefault();
    const saved = await action(() => recordBalanceCheck(loanId, { balance: Number(balance), checked_on: balanceDate }), 'Saldo bankowe zostało zapisane.');
    if (saved) setBalance('');
  };
  const undoPayment = (paymentId: number) => {
    const payment=data?.payments_list.find(p=>p.id===paymentId);
    if (!window.confirm(payment?.budget_entry_created===false?'Cofnąć powiązanie spłaty? Istniejący wydatek pozostanie w budżecie i saldzie.':'Cofnąć zapis raty? Utworzony przy niej wydatek w budżecie też zostanie cofnięty.')) return;
    void action(() => deleteInstallment(loanId, paymentId), 'Zapis raty cofnięty.');
  };
  const undoOverpayment = (overpaymentId: number) => {
    if (!window.confirm('Cofnąć nadpłatę? Powiązany wydatek w budżecie też zostanie cofnięty.')) return;
    void action(() => deleteOverpayment(loanId, overpaymentId), 'Nadpłata cofnięta.');
  };

  const schedule = useMemo(() => data?.actual.schedule.filter(row => row.installment > 0 && row.month > 0) ?? [], [data]);
  const paidMonths = useMemo(() => new Set(data?.payments_list.map(row => row.installment_month) ?? []), [data]);
  const requestedInstallment = schedule.find(row => row.month === Number(params.get('installment')));
  const chart = useMemo(() => {
    if (!data) return null;
    const comparison = view === 'scenario' ? data.simulation.schedule : data.actual.schedule;
    const dates = Array.from(new Set([
      ...data.baseline.schedule.map(row => row.date), ...comparison.map(row => row.date),
    ])).sort();
    let base = data.baseline.schedule[0]?.remaining_balance ?? 0;
    let variant = comparison[0]?.remaining_balance ?? 0;
    const basePoints: number[] = [];
    const variantPoints: number[] = [];
    dates.forEach(day => {
      const baseRow = data.baseline.schedule.find(row => row.date === day);
      const variantRow = comparison.find(row => row.date === day);
      if (baseRow) base = baseRow.remaining_balance;
      if (variantRow) variant = variantRow.remaining_balance;
      basePoints.push(base); variantPoints.push(variant);
    });
    const identical = basePoints.every((value, index) => Math.abs(value - variantPoints[index]) < .005);
    return { identical, points: dates.map((date, index) => ({ date, baseline: basePoints[index], variant: variantPoints[index] })) };
  }, [data, view]);
  const balanceSeries = chart?.identical ? [{ key: 'baseline', name: 'Harmonogram bez zmian' }] : [
    { key: 'baseline', name: 'Bez nadpłat', color: '#8fa9b3', dashed: true },
    { key: 'variant', name: view === 'scenario' ? 'Wariant symulowany' : 'Zapisane nadpłaty' },
  ];

  if (!data) return <div className="loan-page"><Link className="loan-back" to="/loans"><ArrowLeft size={17} /> Kredyty</Link>
    <div className="loan-empty surface-card" role={error ? 'alert' : undefined}>{error || 'Ładowanie kredytu…'}</div></div>;
  const { loan, status, actual_metrics, simulated_metrics } = data;
  const nextRow = schedule.find(row => row.date === status.next_due_date);
  const nextRate = nextRow?.interest_rate ?? data.rates_list[data.rates_list.length - 1]?.interest_rate ?? 0;
  const upcoming = schedule.filter(row => row.date >= localToday() && !paidMonths.has(row.month)).slice(0, 4);
  const paymentSuggestion = requestedInstallment && !paidMonths.has(requestedInstallment.month)
    ? requestedInstallment : nextRow;

  return <div className="loan-page">
    <Link className="loan-back" to="/loans"><ArrowLeft size={17} /> Wszystkie kredyty</Link>
    <header className="loan-heading loan-detail-heading"><div><p className="page-eyebrow">Analiza zobowiązania</p><h1>{loan.name}</h1>
      <p>{loan.category === 'RATY_0' ? 'Raty 0%' : loan.category === 'HIPOTECZNY' ? 'Kredyt hipoteczny' : 'Kredyt gotówkowy'} · {loan.installment_type === 'DECREASING' ? 'raty malejące' : 'raty równe'} · od {dateLabel(loan.start_date)}</p></div>
      {paymentSuggestion && <button type="button" className="loan-button-primary" onClick={() => { startPayment(paymentSuggestion); setView('schedule'); }}><Check size={17} /> Zapisz spłatę</button>}</header>
    {error && <div role="alert" className="loan-alert">{error}<button type="button" aria-label="Zamknij komunikat" onClick={() => setError('')}><X size={16} /></button></div>}
    {success && <div role="status" className="loan-alert is-success">{success}<button type="button" aria-label="Zamknij komunikat" onClick={() => setSuccess('')}><X size={16} /></button></div>}
    <section className="loan-summary-grid" aria-label="Stan kredytu">
      <article className="loan-summary-card loan-summary-primary"><span>Szacunkowo pozostało</span><strong>{money(status.estimated_balance)}</strong><small>Harmonogram zakłada terminowe spłaty.</small></article>
      <article className="loan-summary-card"><span>Najbliższa rata</span><strong>{status.next_due_date ? money(status.next_installment) : 'Spłacony'}</strong><small>{status.next_due_date ? dateLabel(status.next_due_date) : 'Brak kolejnych rat'}</small></article>
      <article className="loan-summary-card"><span>Oprocentowanie następnej raty</span><strong>{nextRate.toFixed(2).replace('.', ',')}%</strong><small>Według zapisanych zmian oprocentowania</small></article>
    </section>
    <section className="loan-net-worth surface-card" aria-label="Ustawienie majątku netto">
      <label className="loan-checkbox"><input type="checkbox" checked={loan.exclude_from_net_worth ?? false} disabled={busy}
        onChange={event => void changeNetWorthExclusion(event.target.checked)} aria-describedby="loan-net-worth-help" />
        <span>Nie uwzględniaj w majątku netto</span></label>
      <p id="loan-net-worth-help">{loan.exclude_from_net_worth ? 'Kapitał tego kredytu nie pomniejsza majątku netto.' : 'Kapitał tego kredytu pomniejsza majątek netto.'} Raty, budżet, prognoza i przypomnienia pozostają aktywne. Ustawienie zapisuje się automatycznie.</p>
    </section>
    <div className="loan-confirmation surface-card"><span className="loan-confirmation-icon"><ClipboardCheck size={19} /></span>
      <div><strong>{status.confirmed_balance === null ? 'Saldo bankowe nie zostało potwierdzone' : 'Ostatnie saldo bankowe: ' + money(status.confirmed_balance)}</strong>
        <p>{status.confirmed_on ? 'Potwierdzone na ' + dateLabel(status.confirmed_on) + '. Szacunek i saldo bankowe są pokazywane osobno.' : 'Podaj kwotę z banku, aby odróżniać rzeczywisty stan od prognozy.'}</p></div>
      <button type="button" className="loan-text-button" onClick={() => setView('history')}>Uzgodnij saldo <ArrowRight size={16} /></button></div>
    <nav className="loan-tabs" aria-label="Widoki kredytu">
      {([['overview', 'Przegląd'], ['schedule', 'Harmonogram'], ['scenario', 'Symulacja'], ['history', 'Historia i dane']] as const).map(([key, title]) =>
        <button key={key} type="button" className={view === key ? 'is-active' : ''} aria-current={view === key ? 'page' : undefined} onClick={() => setView(key)}>{title}</button>)}
    </nav>
    {view === 'overview' && <div className="loan-overview-grid">
      <section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Przebieg spłaty</p><h2>Kapitał w czasie</h2></div><button type="button" className="loan-text-button" onClick={() => setView('scenario')}>Sprawdź nadpłatę <ArrowRight size={16} /></button></div>
        <div>{chart && <TrendChart data={chart.points} series={balanceSeries} />}{chart?.identical && <p className="chart-note">Warianty mają identyczny przebieg, dlatego pokazano jedną linię.</p>}</div>
        <p className="loan-muted">Wykres jest orientacyjny. Bank może stosować inną metodę naliczania odsetek i opłat.</p></section>
      <div className="loan-side-stack"><section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Najbliższe miesiące</p><h2>Nadchodzące raty</h2></div><CalendarDays size={20} /></div>
        {upcoming.length ? upcoming.map(row => <div className="loan-upcoming" key={row.month}><span>{dateLabel(row.date)}</span><strong>{money(row.installment)}</strong></div>) : <p className="loan-muted">Brak kolejnych rat.</p>}
        <button type="button" className="loan-text-button" onClick={() => setView('schedule')}>Pełny harmonogram <ArrowRight size={16} /></button></section>
        <section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Zapisane nadpłaty</p><h2>Efekt według modelu</h2></div><CircleDollarSign size={20} /></div>
          <div className="loan-insight"><span>Mniej odsetek</span><strong>{money(actual_metrics.interest_saved)}</strong></div>
          <div className="loan-insight"><span>Okres krótszy o</span><strong>{actual_metrics.months_saved} mies.</strong></div>
          <p className="loan-muted">To porównanie symulacji z harmonogramem bez nadpłat, nie potwierdzenie rozliczenia bankowego.</p></section></div>
    </div>}
    {view === 'overview' && <LoanPaymentChart schedule={schedule} />}
    {view === 'schedule' && <section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Rata po racie</p><h2>Harmonogram</h2><p>Kwoty są szacunkowe. Zapisana spłata potwierdza płatność, nie zmienia obliczeń banku.</p></div></div>
      {requestedInstallment && <div className="loan-upcoming"><span>Sprawa z pulpitu: rata {requestedInstallment.month} · {dateLabel(requestedInstallment.date)}</span><strong>{money(requestedInstallment.installment)}</strong>{paidMonths.has(requestedInstallment.month) ? <span>Spłata już zapisana</span> : <button className="loan-text-button" disabled={busy} onClick={() => startPayment(requestedInstallment)}>Zapisz tę spłatę</button>}</div>}
      <div className="loan-table-wrap"><table className="loan-table"><thead><tr><th>Nr</th><th>Termin</th><th>Rata</th><th>Kapitał</th><th>Odsetki</th><th>Saldo po</th><th>Status</th><th></th></tr></thead>
        <tbody>{schedule.map(row => <tr key={row.month}><td>{row.month}</td><td>{dateLabel(row.date)}</td><td className="loan-strong">{money(row.installment)}</td>
          <td>{money(row.principal_part)}</td><td>{money(row.interest_part)}</td><td>{money(row.remaining_balance)}</td>
          <td><span className={paidMonths.has(row.month) ? 'loan-status is-paid' : 'loan-status'}>{paidMonths.has(row.month) ? 'Zapisana' : row.date < localToday() ? 'Bez potwierdzenia' : 'Planowana'}</span></td>
          <td>{!paidMonths.has(row.month) && <button type="button" className="loan-text-button" onClick={() => startPayment(row)}>Zapisz spłatę</button>}</td></tr>)}</tbody></table></div></section>}
    {view === 'scenario' && <div className="loan-overview-grid"><section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Co się zmieni</p><h2>Symulacja nadpłaty</h2><p>Wariant wpływa wyłącznie na podgląd. Nie zapisuje wydatku.</p></div></div>
      <div className="loan-form-grid"><label>Co miesiąc dodatkowo (PLN)<input type="number" min="0" step="0.01" value={scenarioAmount} onChange={event => setScenarioAmount(event.target.value)} /></label>
        <label>Cel<select value={scenarioAction} onChange={event => setScenarioAction(event.target.value as 'REDUCE_TERM' | 'REDUCE_INSTALLMENT')}><option value="REDUCE_TERM">Skrócenie okresu</option><option value="REDUCE_INSTALLMENT">Zmniejszenie raty</option></select></label></div>
      <div>{chart && <TrendChart data={chart.points} series={balanceSeries} />}{chart?.identical && <p className="chart-note">Warianty mają identyczny przebieg, dlatego pokazano jedną linię.</p>}</div></section>
      <div className="loan-side-stack"><section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Wynik scenariusza</p><h2>Porównanie</h2></div><SlidersHorizontal size={20} /></div>
        <div className="loan-insight"><span>Oszczędność odsetek</span><strong>{money(simulated_metrics.interest_saved)}</strong></div>
        <div className="loan-insight"><span>Skrócenie okresu</span><strong>{simulated_metrics.months_saved} mies.</strong></div>
        <div className="loan-insight"><span>Odsetki w scenariuszu</span><strong>{money(simulated_metrics.total_interest ?? 0)}</strong></div>
        <p className="loan-muted">Porównanie obejmuje także wcześniej zapisane nadpłaty. Wcześniejsza spłata może zależeć od warunków Twojej umowy.</p></section>
        <section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Rzeczywisty przelew</p><h2>Dodaj nadpłatę</h2></div><Plus size={20} /></div>
          <form className="loan-form" onSubmit={saveOverpayment}><label>Kwota (PLN)<input required type="number" min="0.01" step="0.01" value={overpaymentAmount} onChange={event => setOverpaymentAmount(event.target.value)} /></label>
            <label>Data<input required type="date" max={localToday()} value={overpaymentDate} onChange={event => setOverpaymentDate(event.target.value)} /></label>
            <label>Cel<select value={overpaymentAction} onChange={event => setOverpaymentAction(event.target.value as 'REDUCE_TERM' | 'REDUCE_INSTALLMENT')}><option value="REDUCE_TERM">Skrócenie okresu</option><option value="REDUCE_INSTALLMENT">Zmniejszenie raty</option></select></label>
            <label>Wydatek w budżecie<select value={overpaymentAccount} onChange={event => setOverpaymentAccount(event.target.value)}><option value="">Tylko zapisz nadpłatę</option>{accounts.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>
            {accounts.length === 0 && <p className="loan-form-note">Aby połączyć nadpłatę z wydatkiem, najpierw <Link to="/budget">dodaj konto w budżecie</Link>.</p>}
            <button type="submit" className="loan-button-primary" disabled={busy}>Zapisz nadpłatę</button></form></section></div></div>}
    {view === 'history' && <div className="loan-history-grid">
      <div className="loan-side-stack"><section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Potwierdzone operacje</p><h2>Zapisane spłaty</h2></div><CheckCircle2 size={20} /></div>
        {data.payments_list.length ? data.payments_list.map(payment => <div className="loan-history-row" key={payment.id}><span><strong>Rata {payment.installment_month}</strong><small>{dateLabel(payment.paid_on)}{payment.budget_linked ? ' · rozliczona w budżecie' : ' · bez wydatku w budżecie'}</small></span><b>{money(payment.amount)}</b>
          {!payment.budget_linked&&<button type="button" className="loan-button-secondary" disabled={busy} onClick={()=>{setPaymentAccount(String(data?.budget_settings?.resolved_account_id??''));setPaymentLink({ready:false});setPaymentToBudget(payment);}}>Rozlicz w budżecie</button>}
          <button type="button" className="loan-icon-button" disabled={busy} title="Cofnij spłatę" aria-label={'Cofnij ratę ' + payment.installment_month} onClick={() => undoPayment(payment.id)}><RotateCcw size={16} /></button></div>) : <p className="loan-muted">Nie zapisano jeszcze żadnej spłaty.</p>}</section>
        <section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Przedterminowe spłaty</p><h2>Nadpłaty</h2></div></div>
          {data.overpayments_list.length ? data.overpayments_list.map(op => <div className="loan-history-row" key={op.id}><span><strong>{dateLabel(op.date)}</strong><small>{op.type === 'REDUCE_INSTALLMENT' ? 'Zmniejszenie raty' : 'Skrócenie okresu'}{op.budget_linked ? ' · budżet' : ''}</small></span><b>{money(op.amount)}</b>
            <button type="button" className="loan-icon-button" disabled={busy} title="Cofnij nadpłatę" aria-label={'Cofnij nadpłatę z ' + dateLabel(op.date)} onClick={() => undoOverpayment(op.id)}><Trash2 size={16} /></button></div>) : <p className="loan-muted">Nie ma zapisanych nadpłat.</p>}</section></div>
      <div className="loan-side-stack"><section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Dane z banku</p><h2>Uzgodnij saldo</h2></div><Wallet size={20} /></div>
        <p className="loan-muted">Wpisz kapitał pozostały do spłaty z banku. Zachowamy go osobno od szacunku z harmonogramu.</p>
        <form className="loan-form" onSubmit={saveBalance}><label>Kapitał pozostały (PLN)<input required type="number" min="0" step="0.01" value={balance} onChange={event => setBalance(event.target.value)} /></label>
          <label>Stan na dzień<input required type="date" max={localToday()} value={balanceDate} onChange={event => setBalanceDate(event.target.value)} /></label>
          <button type="submit" className="loan-button-secondary" disabled={busy}><Save size={16} /> Zapisz saldo bankowe</button></form>
        {data.balance_checks_list.map(check => <div className="loan-history-row" key={check.id}><span><strong>{money(check.balance)}</strong><small>{dateLabel(check.checked_on)}</small></span></div>)}</section>
        <section className="loan-panel surface-card"><div className="loan-section-title"><div><p className="page-eyebrow">Historia stóp</p><h2>Oprocentowanie</h2></div></div>
          {data.rates_list.map(item => <div className="loan-history-row" key={item.id}><span><strong>{Number(item.interest_rate).toFixed(2).replace('.', ',')}%</strong><small>od {dateLabel(item.valid_from_date)}</small></span></div>)}
          <form className="loan-form loan-form-separated" onSubmit={saveRate}><label>Nowe oprocentowanie (%)<input required type="number" min="0" max="100" step="0.01" value={rate} onChange={event => setRate(event.target.value)} /></label>
            <label>Obowiązuje od<input required type="date" value={rateDate} onChange={event => setRateDate(event.target.value)} /></label>
            <button type="submit" className="loan-button-secondary" disabled={busy}>Dodaj zmianę</button></form></section></div></div>}
    {paymentTarget && <div className="loan-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !busy) setPaymentTarget(null); }}>
      <section className="loan-modal surface-card" role="dialog" aria-modal="true" aria-label="Zapisz spłatę raty">
        <div className="loan-modal-heading"><div><p className="page-eyebrow">Rata {paymentTarget.month}</p><h2>Zapisz spłatę</h2></div><button type="button" className="loan-icon-button" onClick={() => setPaymentTarget(null)} aria-label="Zamknij formularz"><X size={20} /></button></div>
        <p className="loan-muted">Planowany termin: {dateLabel(paymentTarget.date)}. Zapis jest potwierdzeniem płatności w aplikacji.</p>
        <form className="loan-form" onSubmit={savePayment}><label>Zapłacona kwota (PLN)<input required type="number" min="0.01" step="0.01" value={paymentAmount} onChange={event => setPaymentAmount(event.target.value)} /></label>
          <label>Data płatności<input required type="date" max={localToday()} value={paymentDate} onChange={event => setPaymentDate(event.target.value)} /></label>
          <label>Konto budżetowe<select value={paymentAccount} onChange={event => setPaymentAccount(event.target.value)}><option value="">Bez wydatku — nie pomniejszaj salda kont</option>{accounts.filter(account=>account.currency==='PLN').map(account => <option key={account.id} value={account.id}>{account.name} · {money(account.balance)}</option>)}</select></label>
          <LoanPaymentLink loanId={loanId} accountId={Number(paymentAccount)} date={paymentDate} amount={Number(paymentAmount)} onChange={setPaymentLink}/>
          <p className="loan-form-note">{paymentAccount?`${accounts.find(a=>a.id===Number(paymentAccount))?.name}: ${money(accounts.find(a=>a.id===Number(paymentAccount))?.balance??0)} → ${money((accounts.find(a=>a.id===Number(paymentAccount))?.balance??0)-(paymentLink.existing_entry_id?0:Number(paymentAmount||0)))}`:'Uwaga: zapiszesz wyłącznie potwierdzenie spłaty. Saldo budżetu pozostanie bez zmian. Wybierz konto, jeśli rata ma zostać odjęta od jego salda.'}</p>
          <p className="loan-form-note">{paymentLink.existing_entry_id?'Płatność jest już w budżecie. Powiążemy ją ze spłatą bez ponownego obciążenia konta.':'Nowy wydatek pomniejszy saldo wybranego konta. Jeśli rata jest już w budżecie, wybierz jej istniejącą płatność powyżej.'}</p>
          {accounts.length === 0 && <p className="loan-form-note">Aby zapisać także wydatek, najpierw <Link to="/budget">dodaj konto w budżecie</Link>.</p>}
          <div className="loan-form-actions"><button type="button" className="loan-button-quiet" onClick={() => setPaymentTarget(null)}>Anuluj</button>
            <button type="submit" className="loan-button-primary" disabled={busy||!paymentLink.ready}><Check size={17} /> Potwierdź spłatę</button></div></form></section></div>}
    {paymentToBudget&&<div className="loan-modal-backdrop"><section className="loan-modal surface-card" role="dialog" aria-modal="true" aria-label="Rozlicz istniejącą spłatę w budżecie"><h2>Rozlicz istniejącą spłatę w budżecie</h2><p>Rata {paymentToBudget.installment_month} · {dateLabel(paymentToBudget.paid_on)} · {money(paymentToBudget.amount)}. Zachowamy tę spłatę i jej datę.</p><form className="loan-form" onSubmit={async event=>{event.preventDefault();const saved=await action(()=>recordInstallment(loanId,{installment_month:paymentToBudget.installment_month,paid_on:paymentToBudget.paid_on,amount:paymentToBudget.amount,account_id:Number(paymentAccount),apply_to_budget:true,payment_id:paymentToBudget.id,...(paymentLink.existing_entry_id?{existing_entry_id:paymentLink.existing_entry_id,entry_version:paymentLink.entry_version}:paymentLink.confirm_new_expense?{confirm_new_expense:true}:{})}),paymentLink.existing_entry_id?'Spłata powiązana z istniejącym wydatkiem. Saldo nie zmieniło się.':'Spłata rozliczona w budżecie. Saldo konta zostało pomniejszone.');if(saved)setPaymentToBudget(null);}}><label>Konto płatności<select required value={paymentAccount} onChange={e=>setPaymentAccount(e.target.value)}><option value="">Wybierz konto</option>{accounts.filter(a=>a.currency==='PLN').map(a=><option key={a.id} value={a.id}>{a.name} · {money(a.balance)}</option>)}</select></label><LoanPaymentLink loanId={loanId} accountId={Number(paymentAccount)} date={paymentToBudget.paid_on} amount={paymentToBudget.amount} onChange={setPaymentLink}/>{error&&<p role="alert">{error}</p>}<p className="loan-form-note">{paymentAccount?`${money(accounts.find(a=>a.id===Number(paymentAccount))?.balance??0)} → ${money((accounts.find(a=>a.id===Number(paymentAccount))?.balance??0)-(paymentLink.existing_entry_id?0:paymentToBudget.amount))}`:'Wybierz konto płatności.'} {paymentLink.existing_entry_id?'Płatność jest już w budżecie — zachowamy saldo.':'Nowy wydatek wybierz tylko wtedy, gdy saldo nie uwzględnia jeszcze tej raty.'}</p><div className="loan-form-actions"><button type="button" className="loan-button-quiet" disabled={busy} onClick={()=>setPaymentToBudget(null)}>Anuluj</button><button type="submit" className="loan-button-primary" disabled={busy||!paymentAccount||!paymentLink.ready}>{paymentLink.existing_entry_id?'Powiąż bez zmiany salda':'Pomniejsz saldo i rozlicz'}</button></div></form></section></div>}
    {data.budget_settings&&<LoanBudgetSettingsPanel key={`${loanId}-${data.budget_settings.version}`} settings={data.budget_settings} accounts={accounts} categories={categories} onSaved={refresh}/>}
    <div className="loan-footer"><span>Harmonogram jest szacunkiem; uzgadniaj saldo i naliczone odsetki z bankiem.</span><button type="button" className="loan-text-button" onClick={() => setView('schedule')}>Zobacz raty <ArrowRight size={15} /></button></div>
  </div>;
}
