import { useEffect, useState } from 'react';
import { getLoanPaymentCandidates, type LoanPaymentCandidate, type LoanPaymentSelection } from '../../api_loans';

interface Props {
  loanId: number;
  accountId: number;
  date: string;
  amount: number;
  onChange: (selection: LoanPaymentSelection) => void;
  paymentKind?: 'raty' | 'nadpłaty';
}

export default function LoanPaymentLink({ loanId, accountId, date, amount, onChange, paymentKind = 'raty' }: Props) {
  const [items, setItems] = useState<LoanPaymentCandidate[]>([]);
  const [selected, setSelected] = useState('NEW');
  const [confirmed, setConfirmed] = useState(false);
  const [checkedKey, setCheckedKey] = useState('');
  const [error, setError] = useState('');
  const queryKey = `${loanId}:${accountId}:${date}:${amount}`;
  const loading = checkedKey !== queryKey;

  useEffect(() => {
    let active = true;
    setItems([]); setSelected('NEW'); setConfirmed(false); setError(''); setCheckedKey('');
    if (!accountId || !date || !Number.isFinite(amount) || amount <= 0) return;
    const timer = window.setTimeout(() => {
      getLoanPaymentCandidates(loanId, accountId, date, amount)
        .then(result => { if (active) setItems(result.items); })
        .catch(() => {
          if (active) setError('Nie udało się sprawdzić istniejących płatności. Spróbuj ponownie otworzyć formularz.');
        })
        .finally(() => { if (active) setCheckedKey(queryKey); });
    }, 150);
    return () => { active = false; window.clearTimeout(timer); };
  }, [loanId, accountId, date, amount, queryKey]);

  useEffect(() => {
    const entry = !loading && !error ? items.find(item => String(item.id) === selected) : undefined;
    onChange({
      ...(entry ? { existing_entry_id: entry.id, entry_version: entry.version }
        : !loading && confirmed ? { confirm_new_expense: true } : {}),
      ready: !accountId || (!loading && !error && (items.length === 0 || !!entry || confirmed)),
    });
  }, [items, selected, confirmed, loading, error, accountId, onChange]);

  if (!accountId) return null;
  return <div className="loan-payment-link">
    {loading && <p>Sprawdzanie istniejących płatności…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && <>
      <label>Sposób rozliczenia
        <select aria-label={`Powiązanie ${paymentKind} z wydatkiem`} value={selected} onChange={event => {
          setSelected(event.target.value); setConfirmed(false);
        }}>
          <option value="NEW">Nowy wydatek — pomniejsz saldo konta</option>
          {items.map(item => <option key={item.id} value={item.id}>
            Powiąż: {item.date} · {item.description} · {item.amount.toFixed(2)} zł
          </option>)}
        </select>
      </label>
      {items.length > 0 && selected === 'NEW' && <>
        <p className="loan-form-note">Znaleziono {items.length} możliwych płatności. Wybierz istniejący wydatek, aby nie odjąć {paymentKind} drugi raz.</p>
        <label className="loan-payment-confirmation">
          <input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />
          Potwierdzam: to osobna płatność, dodaj nowy wydatek
        </label>
      </>}
      {selected !== 'NEW' && <p className="loan-form-note">
        Powiążemy istniejący wydatek bez zmiany salda. Przypiszemy mu kategorię rat tego kredytu.
        Cofnięcie spłaty zachowa ten wydatek w budżecie.
      </p>}
    </>}
  </div>;
}
