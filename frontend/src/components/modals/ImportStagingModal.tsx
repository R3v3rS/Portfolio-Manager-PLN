import React, { useMemo, useState } from 'react';
import { AlertTriangle, Check, CircleDollarSign, Landmark, ShieldAlert, X } from 'lucide-react';

import { assignAll, assignRow, bookSession, rejectRow } from '../../api_import_staging';
import type { BookResult, StagingConflictType, StagingRow, StagingSession } from '../../types/importStaging';
import { cn } from '../../lib/utils';

interface ImportStagingModalProps {
  session: StagingSession;
  subPortfolios: { id: number; name: string }[];
  onBook: (result: BookResult) => void;
  onCancel: () => void;
}

const conflictLabel: Record<Exclude<StagingConflictType, null>, string> = {
  missing_holding: 'Brak holdingu',
  insufficient_qty: 'Niewystarczająca ilość',
  database_duplicate: 'Duplikat w bazie',
  file_internal_duplicate: 'Duplikat w pliku',
  missing_symbol: 'Brak symbolu',
};

const txIcon = (type: StagingRow['type']) => {
  if (type === 'BUY' || type === 'SELL') return <CircleDollarSign className="h-4 w-4" />;
  if (type === 'DEPOSIT' || type === 'WITHDRAW' || type === 'INTEREST') return <Landmark className="h-4 w-4" />;
  return <ShieldAlert className="h-4 w-4" />;
};

const ImportStagingModal: React.FC<ImportStagingModalProps> = ({ session, subPortfolios, onBook, onCancel }) => {
  const [rows, setRows] = useState(session.rows);
  const [globalSubPortfolio, setGlobalSubPortfolio] = useState<number | null>(null);
  const [confirmedConflicts, setConfirmedConflicts] = useState<Set<number>>(new Set());
  const [isBooking, setIsBooking] = useState(false);
  const [bookResult, setBookResult] = useState<BookResult | null>(null);
  const [isAssigning, setIsAssigning] = useState(false);

  const summary = useMemo(() => {
    const readyRows = rows.filter((row) => (row.status === 'pending' || row.status === 'assigned') && row.conflict_type === null);
    const conflictRows = rows.filter((row) => row.status === 'pending' && row.conflict_type !== null);
    const rejectedRows = rows.filter((row) => row.status === 'rejected');
    const bookableCount = readyRows.length + conflictRows.filter((row) => confirmedConflicts.has(row.id)).length;

    return {
      readyRows,
      conflictRows,
      rejectedRows,
      readyCount: readyRows.length,
      conflictCount: conflictRows.length,
      rejectedCount: rejectedRows.length,
      bookableCount,
    };
  }, [rows, confirmedConflicts]);

  const getSubName = (id: number | null) => {
    if (!id) return '—';
    const sub = subPortfolios.find((item) => item.id === id);
    return sub?.name ?? `Sub #${id}`;
  };

  const handleAssignRow = async (rowId: number, subId: number) => {
    setIsAssigning(true);
    try {
      const updated = await assignRow(session.session_id, rowId, subId);
      setRows((prev) => prev.map((row) => (row.id === rowId ? updated : row)));
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Nie udało się przypisać transakcji.');
    } finally {
      setIsAssigning(false);
    }
  };

  const handleAssignAll = async () => {
    if (!globalSubPortfolio) return;

    setIsAssigning(true);
    try {
      await assignAll(session.session_id, globalSubPortfolio);
      setRows((prev) =>
        prev.map((row) => {
          if (row.status !== 'pending' && row.status !== 'assigned') return row;
          return {
            ...row,
            target_sub_portfolio_id: globalSubPortfolio,
            status: 'assigned',
          };
        })
      );
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Nie udało się przypisać wszystkich transakcji.');
    } finally {
      setIsAssigning(false);
    }
  };

  const handleReject = async (rowId: number) => {
    setIsAssigning(true);
    try {
      const updated = await rejectRow(session.session_id, rowId);
      setRows((prev) => prev.map((row) => (row.id === rowId ? updated : row)));
      setConfirmedConflicts((prev) => {
        const next = new Set(prev);
        next.delete(rowId);
        return next;
      });
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Nie udało się odrzucić transakcji.');
    } finally {
      setIsAssigning(false);
    }
  };

  const toggleConflictConfirm = (rowId: number) => {
    setConfirmedConflicts((prev) => {
      const next = new Set(prev);
      if (next.has(rowId)) {
        next.delete(rowId);
      } else {
        next.add(rowId);
      }
      return next;
    });
  };

  const handleBook = async () => {
    setIsBooking(true);
    try {
      const result = await bookSession(session.session_id, Array.from(confirmedConflicts));
      setBookResult(result);
      onBook(result);
      setRows((prev) =>
        prev.map((row) => {
          const wasBookable = (row.status === 'pending' || row.status === 'assigned')
            && (row.conflict_type === null || confirmedConflicts.has(row.id));
          return wasBookable ? { ...row, status: 'booked' } : row;
        })
      );
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Nie udało się zaksięgować sesji.');
    } finally {
      setIsBooking(false);
    }
  };

  const handleCancelImport = () => {
    if (!confirm('Na pewno anulować import? Nieprzetworzone wiersze zostaną usunięte.')) return;
    onCancel();
  };

  const renderStatus = (row: StagingRow) => {
    if (row.status === 'rejected') {
      return <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700">rejected</span>;
    }
    if (row.conflict_type) {
      return <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800">conflict</span>;
    }
    if (row.status === 'assigned') {
      return <span className="rounded-full bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700">assigned</span>;
    }
    return <span className="rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-700">pending</span>;
  };

  if (bookResult) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
          <h3 className="mb-4 text-xl font-semibold text-gray-900">Podsumowanie księgowania</h3>
          <div className="space-y-2 text-sm text-gray-700">
            <p>✅ Zaksięgowano: <strong>{bookResult.booked}</strong> transakcji</p>
            <p>📋 Tylko historia: <strong>{bookResult.booked_tx_only}</strong> transakcji</p>
            <p>⏭️ Pominięto konfliktów: <strong>{bookResult.skipped_conflicts}</strong></p>
            <p>❌ Błędy: <strong>{bookResult.errors.length}</strong></p>
          </div>
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Zamknij
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-3 sm:p-4">
      <div className="flex max-h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="border-b border-gray-200 p-4 sm:p-6">
          <h3 className="text-xl font-semibold text-gray-900">Poczekalnia importu</h3>
          <p className="mt-1 text-sm text-gray-600">Sesja: {session.session_id} | Portfolio: {session.portfolio_id}</p>

          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-800">{summary.readyCount} gotowych</span>
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">{summary.conflictCount} konfliktów</span>
            <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-700">{summary.rejectedCount} odrzuconych</span>
          </div>
        </div>

        <div className="border-b border-gray-200 p-4 sm:p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <label className="text-sm font-medium text-gray-700">Przypisz wszystkie do:</label>
              <select
                value={globalSubPortfolio ?? ''}
                onChange={(event) => setGlobalSubPortfolio(event.target.value ? Number(event.target.value) : null)}
                disabled={isAssigning || isBooking}
                className="min-w-[200px] rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="">Wybierz sub-portfolio</option>
                {subPortfolios.map((sub) => (
                  <option key={sub.id} value={sub.id}>{sub.name}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleAssignAll}
                disabled={!globalSubPortfolio || isAssigning || isBooking}
                className={cn(
                  'rounded-md border border-gray-300 px-3 py-2 text-sm font-medium',
                  (!globalSubPortfolio || isAssigning || isBooking) && 'cursor-not-allowed opacity-50'
                )}
              >
                Przypisz wszystkie
              </button>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleBook}
                disabled={summary.bookableCount === 0 || isBooking || isAssigning}
                className={cn(
                  'rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700',
                  (summary.bookableCount === 0 || isBooking || isAssigning) && 'cursor-not-allowed opacity-50'
                )}
              >
                {isBooking ? 'Księgowanie…' : 'Zaksięguj zatwierdzone'}
              </button>
              <button
                type="button"
                onClick={handleCancelImport}
                disabled={isBooking || isAssigning}
                className={cn(
                  'rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700',
                  (isBooking || isAssigning) && 'cursor-not-allowed opacity-50'
                )}
              >
                Anuluj import
              </button>
            </div>
          </div>
        </div>

        <div className="overflow-auto p-2 sm:p-4">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Typ</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Ticker</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Ilość</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Wartość (PLN)</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Data</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Sub-portfolio</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Status</th>
                <th className="px-3 py-2 text-left font-medium text-gray-600">Akcje</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rows.map((row) => {
                const isConflict = row.status !== 'rejected' && row.conflict_type !== null;
                const canConfirmConflict = isConflict && row.status === 'pending';

                return (
                  <tr
                    key={row.id}
                    className={cn(
                      'align-top',
                      isConflict && 'bg-amber-50'
                    )}
                  >
                    <td className="px-3 py-2">
                      <div className="inline-flex items-center gap-2 font-medium text-gray-800">
                        {txIcon(row.type)} {row.type}
                      </div>
                    </td>
                    <td className="px-3 py-2 font-medium text-gray-900">{row.ticker}</td>
                    <td className="px-3 py-2 text-gray-700">{row.quantity ?? '—'}</td>
                    <td className="px-3 py-2 text-gray-700">{row.total_value.toFixed(2)}</td>
                    <td className="px-3 py-2 text-gray-700">{row.date}</td>
                    <td className="px-3 py-2">
                      {row.status === 'rejected' ? (
                        <span className="text-gray-500">—</span>
                      ) : (
                        <select
                          value={row.target_sub_portfolio_id ?? ''}
                          onChange={(event) => {
                            const value = Number(event.target.value);
                            if (!Number.isNaN(value) && value > 0) {
                              void handleAssignRow(row.id, value);
                            }
                          }}
                          disabled={isAssigning || isBooking}
                          className="min-w-[150px] rounded-md border border-gray-300 px-2 py-1 text-sm"
                        >
                          <option value="">—</option>
                          {subPortfolios.map((sub) => (
                            <option key={sub.id} value={sub.id}>{sub.name}</option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-col gap-1">
                        {renderStatus(row)}
                        {isConflict && row.conflict_type && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-900">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            {conflictLabel[row.conflict_type]}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        {row.status !== 'rejected' && (
                          <button
                            type="button"
                            onClick={() => void handleReject(row.id)}
                            disabled={isAssigning || isBooking}
                            className="rounded-md border border-red-200 p-1.5 text-red-600 hover:bg-red-50 disabled:opacity-50"
                            title="Odrzuć wiersz"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        )}

                        {canConfirmConflict && (
                          <button
                            type="button"
                            onClick={() => toggleConflictConfirm(row.id)}
                            disabled={isAssigning || isBooking}
                            className={cn(
                              'inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium',
                              confirmedConflicts.has(row.id)
                                ? 'border-green-300 bg-green-100 text-green-800'
                                : 'border-amber-300 bg-amber-100 text-amber-900'
                            )}
                            title="Transakcja zostanie zapisana tylko w historii, bez wpływu na gotówkę i holdings"
                          >
                            <Check className="h-3.5 w-3.5" />
                            Zatwierdź historycznie
                          </button>
                        )}
                      </div>
                      {row.target_sub_portfolio_id ? (
                        <p className="mt-1 text-xs text-gray-500">Przypisano: {getSubName(row.target_sub_portfolio_id)}</p>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="border-t border-gray-200 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-gray-600">
              {summary.bookableCount} transakcji gotowych do zaksięgowania
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleBook}
                disabled={summary.bookableCount === 0 || isBooking || isAssigning}
                className={cn(
                  'rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700',
                  (summary.bookableCount === 0 || isBooking || isAssigning) && 'cursor-not-allowed opacity-50'
                )}
              >
                {isBooking ? 'Księgowanie…' : 'Zaksięguj'}
              </button>
              <button
                type="button"
                onClick={onCancel}
                disabled={isBooking || isAssigning}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Zamknij
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImportStagingModal;
