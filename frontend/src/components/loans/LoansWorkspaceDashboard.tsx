import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CalendarDays, CheckCircle2, CreditCard, Landmark, Plus, Trash2, X } from 'lucide-react';
import { createLoan, deleteLoan, getLoans, type LoanSummary } from '../../api_loans';
import { extractErrorMessageFromUnknown } from '../../http/response';
import './loansWorkspace.css';

const money = (value: number) => new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(value);
const dateLabel = (value: string | null) => value
  ? new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(value.slice(0, 10) + 'T12:00:00'))
  : 'Harmonogram zakończony';
const localToday = () => {
  const now = new Date();
  return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
};
const categoryName = (category?: string) => category === 'HIPOTECZNY' ? 'Hipoteczny'
  : category === 'RATY_0' ? 'Raty 0%' : 'Gotówkowy';
const blankForm = () => ({
  name: '', original_amount: '', duration_months: '', start_date: localToday(),
  installment_type: 'EQUAL' as 'EQUAL' | 'DECREASING', initial_rate: '', category: 'GOTOWKOWY', exclude_from_net_worth: false,
});

export default function LoansWorkspaceDashboard() {
  const [loans, setLoans] = useState<LoanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(blankForm);
  const load = useCallback(async () => {
    try { setError(''); setLoans(await getLoans()); }
    catch (cause) { setError(extractErrorMessageFromUnknown(cause) || 'Nie udało się pobrać kredytów.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      await createLoan({
        name: form.name.trim(), original_amount: Number(form.original_amount),
        duration_months: Number(form.duration_months), start_date: form.start_date,
        installment_type: form.installment_type, initial_rate: Number(form.initial_rate || 0), category: form.category,
        exclude_from_net_worth: form.exclude_from_net_worth,
      });
      setShowForm(false); setForm(blankForm()); await load();
    } catch (cause) { setError(extractErrorMessageFromUnknown(cause) || 'Nie udało się dodać kredytu.'); }
    finally { setBusy(false); }
  };
  const remove = async (loan: LoanSummary) => {
    if (!window.confirm('Usunąć kredyt „' + loan.name + '” wraz z historią spłat? Wydatki zapisane w budżecie pozostaną.')) return;
    setBusy(true);
    try { await deleteLoan(loan.id); await load(); }
    catch (cause) { setError(extractErrorMessageFromUnknown(cause) || 'Nie udało się usunąć kredytu.'); }
    finally { setBusy(false); }
  };
  const totalEstimated = loans.reduce((sum, loan) => sum + loan.estimated_balance, 0);
  const totalInstallments = loans.reduce((sum, loan) => sum + loan.next_installment, 0);
  const withConfirmation = loans.filter(loan => loan.confirmed_balance !== null).length;

  return <div className="loan-page">
    <header className="loan-heading"><div><p className="page-eyebrow">Zobowiązania</p><h1>Kredyty pod kontrolą</h1>
      <p>Harmonogram, potwierdzone spłaty i warianty nadpłat w jednym miejscu.</p></div>
      <button type="button" className="loan-button-primary" onClick={() => setShowForm(true)}><Plus size={18} /> Dodaj kredyt</button></header>
    {error && <div role="alert" className="loan-alert">{error}<button type="button" onClick={() => setError('')} aria-label="Zamknij komunikat"><X size={16} /></button></div>}
    <section className="loan-summary-grid" aria-label="Podsumowanie kredytów">
      <article className="loan-summary-card loan-summary-primary"><span>Szacunkowy kapitał do spłaty</span><strong>{money(totalEstimated)}</strong>
        <small>Harmonogram zakłada terminowe opłacanie zwykłych rat.</small></article>
      <article className="loan-summary-card"><span>Suma najbliższych rat</span><strong>{money(totalInstallments)}</strong>
        <small>Planowana kwota kolejnej raty każdego kredytu</small></article>
      <article className="loan-summary-card"><span>Uzgodnione z bankiem</span><strong>{withConfirmation} / {loans.length}</strong>
        <small>Kredyty z ręcznie potwierdzonym saldem</small></article>
    </section>
    <div className="loan-list-header"><div><p className="page-eyebrow">Twoje zobowiązania</p><h2>Kredyty</h2></div><span>{loans.length} {loans.length === 1 ? 'pozycja' : 'pozycji'}</span></div>
    {loading ? <div className="loan-empty surface-card">Ładowanie kredytów…</div> : loans.length === 0
      ? <div className="loan-empty surface-card"><Landmark size={28} /><h2>Nie masz jeszcze kredytów</h2><p>Dodaj pierwszy kredyt, aby zobaczyć jego harmonogram.</p></div>
      : <div className="loan-list">{loans.map(loan => {
        const share = loan.original_amount > 0 ? Math.max(0, Math.min(100, (1 - loan.estimated_balance / loan.original_amount) * 100)) : 0;
        return <article className="loan-item surface-card" key={loan.id}>
          <div className="loan-item-top"><div className="loan-item-title"><span className="loan-item-icon"><Landmark size={19} /></span>
            <div><span className="loan-pill">{categoryName(loan.category)}</span><h3>{loan.name}</h3>{loan.exclude_from_net_worth && <small className="loan-muted">Nie uwzględniany w majątku netto</small>}</div></div>
            <button type="button" className="loan-icon-button" disabled={busy} title="Usuń kredyt" aria-label={'Usuń kredyt: ' + loan.name} onClick={() => void remove(loan)}><Trash2 size={17} /></button></div>
          <div className="loan-item-values"><div><span>Szacunkowo pozostało</span><strong>{money(loan.estimated_balance)}</strong></div>
            <div><span>Najbliższa rata</span><strong>{loan.next_due_date ? money(loan.next_installment) : 'Spłacony'}</strong></div>
            <div><span>Termin</span><strong>{dateLabel(loan.next_due_date)}</strong></div></div>
          <div className="loan-progress" role="progressbar" aria-label={'Postęp spłaty: ' + loan.name} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(share)}><span style={{ width: share + '%' }} /></div>
          <div className="loan-item-bottom"><span><CreditCard size={15} /> Początkowo {money(loan.original_amount)}</span>
            <span><CheckCircle2 size={15} /> Zapisane raty: {loan.recorded_payments}</span>
            {loan.confirmed_on && <span><CalendarDays size={15} /> Saldo bankowe z {dateLabel(loan.confirmed_on)}</span>}
            <Link to={'/loans/' + loan.id}>Analizuj kredyt <ArrowRight size={16} /></Link></div>
        </article>;
      })}</div>}
    {showForm && <div className="loan-modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !busy) setShowForm(false); }}>
      <section className="loan-modal surface-card" role="dialog" aria-modal="true" aria-label="Dodaj kredyt">
        <div className="loan-modal-heading"><div><p className="page-eyebrow">Nowe zobowiązanie</p><h2>Dodaj kredyt</h2></div>
          <button type="button" className="loan-icon-button" onClick={() => setShowForm(false)} aria-label="Zamknij formularz"><X size={20} /></button></div>
        <form onSubmit={create} className="loan-form">
          <label>Nazwa<input required maxLength={100} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} placeholder="np. Kredyt mieszkaniowy" /></label>
          <div className="loan-form-grid"><label>Rodzaj<select value={form.category} onChange={event => setForm({ ...form, category: event.target.value, initial_rate: event.target.value === 'RATY_0' ? '0' : form.initial_rate })}><option value="GOTOWKOWY">Gotówkowy</option><option value="HIPOTECZNY">Hipoteczny</option><option value="RATY_0">Raty 0%</option></select></label>
            <label>Typ rat<select value={form.installment_type} onChange={event => setForm({ ...form, installment_type: event.target.value as 'EQUAL' | 'DECREASING' })}><option value="EQUAL">Równe</option><option value="DECREASING">Malejące</option></select></label></div>
          <div className="loan-form-grid"><label>Kwota początkowa (PLN)<input required type="number" min="0.01" step="0.01" value={form.original_amount} onChange={event => setForm({ ...form, original_amount: event.target.value })} /></label>
            <label>Okres w miesiącach<input required type="number" min="1" step="1" value={form.duration_months} onChange={event => setForm({ ...form, duration_months: event.target.value })} /></label></div>
          <div className="loan-form-grid"><label>Data rozpoczęcia<input required type="date" value={form.start_date} onChange={event => setForm({ ...form, start_date: event.target.value })} /></label>
            <label>Oprocentowanie początkowe (%)<input required type="number" min="0" max="100" step="0.01" disabled={form.category === 'RATY_0'} value={form.initial_rate} onChange={event => setForm({ ...form, initial_rate: event.target.value })} /></label></div>
          <p className="loan-form-note">Wyniki harmonogramu są orientacyjne. Saldo bankowe możesz dodać w szczegółach kredytu.</p>
          <label className="loan-checkbox"><input type="checkbox" checked={form.exclude_from_net_worth} onChange={event => setForm({ ...form, exclude_from_net_worth: event.target.checked })}/><span>Nie uwzględniaj w majątku netto</span></label>
          <p className="loan-form-note">Raty pozostaną w budżecie, prognozie i przypomnieniach. To ustawienie możesz później zmienić w szczegółach kredytu.</p>
          <div className="loan-form-actions"><button type="button" className="loan-button-quiet" onClick={() => setShowForm(false)}>Anuluj</button>
            <button type="submit" className="loan-button-primary" disabled={busy}>{busy ? 'Zapisywanie…' : 'Dodaj kredyt'}</button></div>
        </form>
      </section></div>}
  </div>;
}
