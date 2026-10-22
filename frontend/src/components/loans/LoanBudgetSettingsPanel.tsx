import { useState, type FormEvent } from 'react';
import { saveLoanBudgetSettings, type LoanBudgetSettings } from '../../api_loans';
import type { BudgetAccount, BudgetCategory } from '../../api_budget_workspace';
import { extractErrorMessageFromUnknown } from '../../http/response';

interface Props {
  settings: LoanBudgetSettings;
  accounts: BudgetAccount[];
  categories: BudgetCategory[];
  onSaved: () => Promise<void>;
}

export default function LoanBudgetSettingsPanel({ settings, accounts, categories, onSaved }: Props) {
  const [account, setAccount] = useState(String(settings.account_id ?? ''));
  const [category, setCategory] = useState(String(settings.category_id ?? ''));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const savedAccount = accounts.find(item => item.id === settings.resolved_account_id);

  const save = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      await saveLoanBudgetSettings(settings.loan_id, {
        account_id: account ? Number(account) : null, category_id: Number(category), version: settings.version,
      });
      setNotice('Ustawienia zapisane.');
      await onSaved();
    } catch (cause) {
      setError(extractErrorMessageFromUnknown(cause));
    } finally {
      setBusy(false);
    }
  };

  return <details className="loan-panel loan-budget-settings surface-card">
    <summary><span>Budżet tego kredytu · konto i kategoria rat</span>
      <small>{savedAccount?.name ?? 'Wybierz konto'}</small>
    </summary>
    <p className="loan-muted">To konto podpowiemy przy spłacie i wykorzystamy w prognozie.
      Zmiana nazwy kategorii zachowa jej przypisanie. Ustawienia nie zmieniają sald ani istniejących wydatków.</p>
    <form className="loan-form" onSubmit={save}>
      <div className="loan-form-grid">
        <label>Konto płatności rat
          <select aria-label="Domyślne konto rat kredytu" value={account} onChange={event => setAccount(event.target.value)}>
            <option value="">Konto z ogólnych ustawień prognozy</option>
            {accounts.filter(item => item.currency === 'PLN').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        <label>Kategoria rat
          <select required aria-label="Kategoria rat kredytu" value={category} onChange={event => setCategory(event.target.value)}>
            <option value="">Wybierz kategorię</option>
            {categories.filter(item => !item.is_unassigned).map(item => <option key={item.id} value={item.id}>
              {item.selection_label ?? item.path ?? item.name}
            </option>)}
          </select>
        </label>
      </div>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <button type="submit" className="loan-button-secondary" disabled={busy || !category}>Zapisz konto i kategorię rat</button>
    </form>
  </details>;
}
