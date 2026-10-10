import React, { useMemo, useState } from 'react';
import { AlertTriangle, Check, X } from 'lucide-react';
import { assignAll, assignRow, bookSession, getSession, refreshSymbols, rejectRow } from '../../api_import_staging';
import type { BookResult, StagingConflictType, StagingRow, StagingSession } from '../../types/importStaging';
import { HttpError } from '../../http';
import { symbolMapApi, type MappingCurrency } from '../../api_symbol_map';

interface ImportStagingModalProps {
  session: StagingSession;
  subPortfolios: { id: number; name: string }[];
  onBook: (result: BookResult) => void;
  onCancel: () => void;
  onCloseAfterBooking?: () => void;
}
const conflictLabel: Record<Exclude<StagingConflictType, null>, string> = {
  missing_holding: 'Brak pozycji', insufficient_qty: 'Niewystarczająca liczba akcji',
  database_duplicate: 'Duplikat w bazie', file_internal_duplicate: 'Duplikat w pliku', missing_symbol: 'Brak mapowania symbolu',
  source_mismatch: 'Identyfikator operacji ma inne dane — sprawdź źródło',
};
const statusLabel = { pending: 'Oczekuje', assigned: 'Przypisano', booked: 'Zaksięgowano', rejected: 'Odrzucono' };
const typeLabel = { BUY: 'Zakup', SELL: 'Sprzedaż', DEPOSIT: 'Wpłata', WITHDRAW: 'Wypłata', DIVIDEND: 'Dywidenda', INTEREST: 'Odsetki' };
const isActive = (row: StagingRow) => row.status === 'pending' || row.status === 'assigned';
const isDuplicate = (row: StagingRow) => row.conflict_type === 'database_duplicate' || row.conflict_type === 'file_internal_duplicate';
const money = (value: number) => value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const ImportStagingModal: React.FC<ImportStagingModalProps> = ({session: initialSession, subPortfolios, onBook, onCancel, onCloseAfterBooking}) => {
  const [session, setSession] = useState(initialSession);
  const [globalSubPortfolio, setGlobalSubPortfolio] = useState('');
  const [confirmedConflicts, setConfirmedConflicts] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [bookResult, setBookResult] = useState<BookResult | null>(null);
  const [showSummary, setShowSummary] = useState(false);
  const [mappingDrafts, setMappingDrafts] = useState<Record<string, {ticker: string; currency: MappingCurrency | ''}>>({});
  const rows = session.rows;
  const summary = useMemo(() => {
    const ready = rows.filter(row => isActive(row) && row.conflict_type === null);
    const conflicts = rows.filter(row => isActive(row) && row.conflict_type !== null);
    return {ready: ready.length, conflicts: conflicts.length,
      rejected: rows.filter(row => row.status === 'rejected').length,
      bookable: ready.length + conflicts.filter(row => row.conflict_type !== 'source_mismatch' && confirmedConflicts.has(row.id)).length};
  }, [rows, confirmedConflicts]);

  const synchronize = async () => {
    const updated = await getSession(session.session_id);
    setSession(updated);
    setConfirmedConflicts(new Set());
    return updated;
  };
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await action(); }
    catch (err) {
      const details = err instanceof HttpError
        ? (err.data as {error?: {details?: {row_errors?: unknown}}} | undefined)?.error?.details?.row_errors
        : undefined;
      const rowErrors = Array.isArray(details) ? details.filter((item): item is string => typeof item === 'string') : [];
      setError(rowErrors.length ? `Księgowanie wycofane. ${rowErrors.join(' ')}` : err instanceof Error ? err.message : 'Nie udało się wykonać operacji.');
    }
    finally { setBusy(false); }
  };
  const handleBook = () => run(async () => {
    const result = await bookSession(session.session_id, Array.from(confirmedConflicts));
    // The response includes authoritative row states, including newly detected conflicts.
    // Do not fabricate "booked" states or retry a successful write after a read error.
    setBookResult(result);
    setConfirmedConflicts(new Set());
    if (result.session) {
      setSession(result.session);
    } else {
      try { await synchronize(); }
      catch { setError('Księgowanie zapisane. Nie udało się odświeżyć podglądu; zamknij okno i wznów tę sesję.'); }
    }
    setShowSummary(true);
    onBook(result);
  });
  const handleAssign = (rowId: number, subId: number | null) => run(async () => {
    await assignRow(session.session_id, rowId, subId);
    await synchronize();
  });
  const handleAssignAll = () => run(async () => {
    if (globalSubPortfolio === '') return;
    const subId = globalSubPortfolio === 'main' ? null : Number(globalSubPortfolio);
    const response = await assignAll(session.session_id, subId);
    if ('session' in response && response.session) setSession(response.session);
    else await synchronize();
    setConfirmedConflicts(new Set());
  });
  const handleReject = (rowId: number) => run(async () => {
    await rejectRow(session.session_id, rowId);
    await synchronize();
  });
  const toggle = (id: number) => setConfirmedConflicts(prev => {
    const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next;
  });
  const saveMappings = () => run(async () => {
    for (const symbol of session.summary.missing_symbols) {
      const draft = mappingDrafts[symbol];
      if (!draft?.ticker.trim()) throw new Error(`Podaj ticker dla ${symbol}.`);
      if (!draft.currency) throw new Error(`Wybierz walutę instrumentu ${symbol}.`);
    }
    for (const symbol of session.summary.missing_symbols) {
      const draft = mappingDrafts[symbol];
      await symbolMapApi.create({symbol_input:symbol, ticker:draft.ticker.trim().toUpperCase(), currency:draft.currency as MappingCurrency});
    }
    setSession(await refreshSymbols(session.session_id));
    setConfirmedConflicts(new Set());
  });
  const close = onCloseAfterBooking ?? onCancel;
  const hasRemaining = rows.some(isActive);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-3 sm:p-5">
      <section role="dialog" aria-modal="true" aria-labelledby="import-staging-title" className="flex max-h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-slate-700 p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-teal-400">Import transakcji</p>
            <h2 id="import-staging-title" className="mt-1 text-xl font-semibold text-slate-100">Poczekalnia importu</h2>
            <p className="mt-1 text-sm text-slate-400">{session.source_file ?? 'Zapisana sesja'} · {session.summary.input_rows ?? rows.length} wierszy w pliku</p>
          </div>
          <button type="button" aria-label="Zamknij podgląd" disabled={busy} onClick={close} className="rounded-lg p-2 text-slate-300 hover:bg-slate-800"><X className="h-5 w-5" /></button>
        </header>
        <div className="overflow-auto p-5">
          {error && <p role="alert" className="mb-4 rounded-xl border border-red-800 bg-red-950/50 p-3 text-sm text-red-200">{error}</p>}
          {showSummary && bookResult && (
            <div role="status" className="mb-4 rounded-xl border border-teal-800 bg-teal-950/40 p-4">
              <h3 className="font-semibold text-slate-100">Podsumowanie księgowania</h3>
              <p className="mt-1 text-sm text-slate-300">Zaksięgowano: {bookResult.booked} · Tylko historia: {bookResult.booked_tx_only} · Pominięte duplikaty: {bookResult.duplicate_skipped ?? 0} · Nierozstrzygnięte konflikty: {bookResult.skipped_conflicts}</p>
              {hasRemaining && <button type="button" onClick={() => setShowSummary(false)} className="mt-3 text-sm font-semibold text-teal-300">Rozwiąż pozostałe wiersze</button>}
              {!hasRemaining && <button type="button" onClick={close} className="mt-3 rounded-lg bg-teal-700 px-4 py-2 text-sm text-white">Zamknij</button>}
            </div>
          )}
          <div className="mb-4 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-teal-950 px-3 py-1.5 text-teal-200">{summary.ready} gotowych</span>
            <span className="rounded-full bg-amber-950 px-3 py-1.5 text-amber-200">{summary.conflicts} konfliktów</span>
            <span className="rounded-full bg-slate-800 px-3 py-1.5 text-slate-300">{summary.rejected} odrzuconych</span>
            <span className="rounded-full bg-slate-800 px-3 py-1.5 text-slate-300">{session.summary.booked ?? rows.filter(row => row.status === 'booked').length} zaksięgowanych</span>
          </div>
          {session.warnings?.map(warning => <p key={warning} className="mb-3 text-sm leading-relaxed text-amber-200">{warning}</p>)}
          {rows.some(row => row.conflict_type === 'missing_holding' || row.conflict_type === 'insufficient_qty') && <p className="mb-3 text-sm leading-relaxed text-amber-200">Sprzedaż wymaga wcześniejszego zakupu. Sprawdź przypisanie do strategii albo uzupełnij wcześniejszą historię. „Zatwierdź historycznie” zapisuje tylko historię i nie zmienia salda ani liczby akcji.</p>}
          {!!session.unsupported_rows?.length && (
            <details className="mb-4 rounded-xl border border-amber-900 bg-amber-950/30 p-3">
              <summary className="cursor-pointer text-sm font-medium text-amber-200">Nieobsługiwane wiersze: {session.unsupported_rows.length} — nie zostaną zaksięgowane</summary>
              <ul className="mt-2 space-y-1 text-sm text-slate-300">{session.unsupported_rows.map(row => <li key={row.row_number}>Wiersz {row.row_number}: {row.type} · {row.reason}</li>)}</ul>
            </details>
          )}
          {!!session.summary.missing_symbols.length && (
            <div className="mb-4 rounded-xl border border-amber-900 p-3 text-sm text-amber-200">
              <p>Przypisz nowe instrumenty. Zapisane powiązania zostaną użyte przy kolejnych importach.</p>
              <div className="my-3 grid gap-3">{session.summary.missing_symbols.map(symbol => {
                const draft = mappingDrafts[symbol] ?? {ticker:'', currency:symbol.endsWith('.PL') ? 'PLN' as const : '' as const};
                return <div key={symbol} className="flex flex-wrap items-center gap-3"><strong>{symbol}</strong>
                  <input aria-label={`Ticker notowań dla ${symbol}`} placeholder="np. DNP.WA" disabled={busy} value={draft.ticker} onChange={event => setMappingDrafts(previous => ({...previous,[symbol]:{...draft,ticker:event.target.value}}))} className="rounded-lg border border-slate-600 p-2 text-slate-100" />
                  <select aria-label={`Waluta instrumentu ${symbol}`} disabled={busy} value={draft.currency} onChange={event => setMappingDrafts(previous => ({...previous,[symbol]:{...draft,currency:event.target.value as MappingCurrency | ''}}))}><option value="">Wybierz walutę</option>{(['PLN','USD','EUR','GBP'] as const).map(currency => <option key={currency} value={currency}>{currency}</option>)}</select>
                </div>;
              })}</div>
              <button type="button" disabled={busy} onClick={() => void saveMappings()} className="rounded-lg bg-teal-700 px-3 py-2 text-sm font-semibold text-white">Zapisz powiązania i odśwież</button>
              <button type="button" disabled={busy} onClick={() => void run(async () => { setSession(await refreshSymbols(session.session_id)); setConfirmedConflicts(new Set()); })} className="ml-2 font-semibold text-teal-300">Odśwież mapowania</button>
            </div>
          )}
          {!showSummary && <div className="mb-4 flex flex-wrap items-center gap-2">
            <label htmlFor="import-global-scope" className="text-sm text-slate-300">Przypisz wszystkie do:</label>
            <select id="import-global-scope" value={globalSubPortfolio} onChange={event => setGlobalSubPortfolio(event.target.value)} disabled={busy} className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-100">
              <option value="">Wybierz portfel</option><option value="main">Portfel główny</option>
              {subPortfolios.map(sub => <option key={sub.id} value={sub.id}>{sub.name}</option>)}
            </select>
            <button type="button" onClick={() => void handleAssignAll()} disabled={globalSubPortfolio === '' || busy} className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-100 disabled:opacity-40">Przypisz wszystkie</button>
          </div>}
          {rows.length > 0 ? <div className="overflow-x-auto rounded-xl border border-slate-700">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-800 text-left text-xs text-slate-400"><tr>{['Operacja', 'Instrument', 'Liczba', 'Przepływ PLN', 'Prowizja PLN', 'Data', 'Portfel docelowy', 'Status / decyzja'].map(label => <th key={label} className="whitespace-nowrap px-3 py-3 font-medium">{label}</th>)}</tr></thead>
              <tbody>{rows.map(row => {
                const active = isActive(row);
                const actionable = active && row.conflict_type !== null && row.conflict_type !== 'missing_symbol' && row.conflict_type !== 'source_mismatch';
                return <tr key={row.id} className="border-t border-slate-800 align-top text-slate-300">
                  <td className="px-3 py-3">{typeLabel[row.type]}</td><td className="px-3 py-3 font-semibold text-slate-100">{row.ticker}{row.instrument_name && <p className="mt-1 text-xs font-normal text-slate-400">{row.instrument_name}</p>}{row.source_operation_id && <p className="mt-1 text-xs font-normal text-slate-400">ID: {row.source_operation_id}</p>}</td>
                  <td className="px-3 py-3 tabular-nums">{row.quantity ?? '—'}</td><td className="px-3 py-3 tabular-nums">{money(row.total_value)}</td>
                  <td className="px-3 py-3 tabular-nums">{row.commission == null ? '—' : money(row.commission)}</td><td className="whitespace-nowrap px-3 py-3">{row.date}</td>
                  <td className="px-3 py-3"><select aria-label={`Portfel docelowy ${row.id}`} value={row.target_sub_portfolio_id ?? 'main'} disabled={busy || !active} onChange={event => void handleAssign(row.id, event.target.value === 'main' ? null : Number(event.target.value))} className="min-w-36 rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-slate-100 disabled:opacity-50">
                    <option value="main">Portfel główny</option>{subPortfolios.map(sub => <option key={sub.id} value={sub.id}>{sub.name}</option>)}
                  </select></td>
                  <td className="min-w-60 px-3 py-3">
                    <p>{row.booking_mode === 'duplicate_skipped' ? 'Duplikat pominięty' : row.booking_mode === 'history_only' ? 'Zapisano tylko historię' : statusLabel[row.status]}</p>
                    {row.conflict_type && row.status !== 'booked' && <p className="mt-1 inline-flex items-center gap-1 text-xs text-amber-300"><AlertTriangle className="h-3.5 w-3.5" />{conflictLabel[row.conflict_type]}</p>}
                    {actionable && <button type="button" aria-pressed={confirmedConflicts.has(row.id)} disabled={busy} onClick={() => toggle(row.id)} title={isDuplicate(row) ? 'Pominięcie nie dodaje transakcji i nie zmienia sald.' : 'Zapis tylko do historii, bez zmiany gotówki i liczby akcji.'} className="mt-2 flex items-center gap-1 rounded-lg border border-amber-800 px-2 py-1 text-xs text-amber-200 disabled:opacity-40"><Check className="h-3.5 w-3.5" />{isDuplicate(row) ? 'Pomiń duplikat' : 'Zatwierdź historycznie'}{confirmedConflicts.has(row.id) ? ' ✓' : ''}</button>}
                    {active && <button type="button" disabled={busy} onClick={() => void handleReject(row.id)} className="mt-2 text-xs text-red-300">Odrzuć wiersz</button>}
                  </td>
                </tr>;
              })}</tbody>
            </table>
          </div> : <p className="py-4 text-sm text-slate-400">Plik nie zawiera obsługiwanych operacji. Sprawdź listę pominiętych wierszy.</p>}
        </div>
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-700 p-4">
          <p className="text-sm text-slate-400">{summary.bookable} wierszy wybranych. Podgląd nie zmienia sald.</p>
          <div className="flex gap-2">
            <button type="button" disabled={busy} onClick={() => { if (confirm('Anulować oczekujące wiersze? Zaksięgowane operacje pozostaną bez zmian.')) onCancel(); }} className="rounded-lg border border-red-900 px-3 py-2 text-sm text-red-300 disabled:opacity-40">Anuluj import</button>
            <button type="button" disabled={busy || summary.bookable === 0 || showSummary} onClick={() => void handleBook()} className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{busy ? 'Przetwarzanie…' : 'Zaksięguj zatwierdzone'}</button>
            <button type="button" disabled={busy} onClick={close} className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200">{showSummary ? 'Zamknij podgląd' : 'Zapisz na później'}</button>
          </div>
        </footer>
      </section>
    </div>
  );
};
export default ImportStagingModal;
