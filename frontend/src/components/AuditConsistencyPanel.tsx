import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, RefreshCcw, XCircle } from 'lucide-react';
import { portfolioApi, type PortfolioConsistencyAuditResponse } from '../api';
import type { Portfolio } from '../types';
import { extractErrorMessageFromUnknown } from '../http/response';
import TransferModal from './modals/TransferModal';

const EMPTY_AUDIT: PortfolioConsistencyAuditResponse = {
  checked_at: null,
  portfolios: [],
  summary: {
    ok: 0,
    warning: 0,
    error: 0,
  },
};

const STATUS_ICON: Record<'ok' | 'warning' | 'error', React.ReactNode> = {
  ok: <CheckCircle2 className="h-4 w-4 text-green-600" />,
  warning: <AlertTriangle className="h-4 w-4 text-amber-500" />,
  error: <XCircle className="h-4 w-4 text-red-600" />,
};

const CHECK_LABELS: Record<string, string> = {
  value_match: 'Suma głównego portfela i strategii',
  orphan_transactions: 'Transakcje bez prawidłowej strategii',
  interest_leaked: 'Odsetki przypisane do strategii',
  archived_child_transactions: 'Transakcje po archiwizacji strategii',
  cash_negative_days: 'Historyczne ujemne saldo strategii',
};

const AuditConsistencyPanel: React.FC = () => {
  const [audit, setAudit] = useState<PortfolioConsistencyAuditResponse>(EMPTY_AUDIT);
  const [portfoliosTree, setPortfoliosTree] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isTransferModalOpen, setIsTransferModalOpen] = useState(false);
  const [transferDate, setTransferDate] = useState<string | null>(null);
  const [transferPortfolioId, setTransferPortfolioId] = useState<number | null>(null);

  const fetchAudit = useCallback(async () => {
    try {
      setLoading(true);
      const [auditResponse, portfoliosResponse] = await Promise.all([
        portfolioApi.getConsistencyAudit(),
        portfolioApi.list({ tree: 1 }),
      ]);
      setAudit(auditResponse);
      setPortfoliosTree(portfoliosResponse.portfolios || []);
      setError(null);
    } catch (err) {
      setError(extractErrorMessageFromUnknown(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const getParentPortfolioById = useCallback(
    (portfolioId: number): Portfolio | null => {
      const directParent = portfoliosTree.find((p) => p.id === portfolioId && (!p.parent_portfolio_id || p.parent_portfolio_id === null));
      if (directParent) return directParent;
      const parentWithChild = portfoliosTree.find((p) => (p.children || []).some((c) => c.id === portfolioId));
      return parentWithChild || null;
    },
    [portfoliosTree],
  );

  const openTransferForDate = useCallback(
    (portfolioId: number, date: string) => {
      const parent = getParentPortfolioById(portfolioId);
      if (!parent) return;
      setTransferPortfolioId(parent.id);
      setTransferDate(date);
      setIsTransferModalOpen(true);
    },
    [getParentPortfolioById],
  );

  useEffect(() => {
    fetchAudit();
    const interval = window.setInterval(() => {
      fetchAudit();
    }, 30000);

    return () => window.clearInterval(interval);
  }, [fetchAudit]);

  return (
    <>
    <section className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Audyt spójności</h2>
          <p className="text-sm text-gray-500">
            Ostatnie sprawdzenie:{' '}
            <span className="font-medium text-gray-700">
              {audit.checked_at ? new Date(audit.checked_at).toLocaleString('pl-PL') : 'brak'}
            </span>
          </p>
        </div>

        <button
          type="button"
          onClick={fetchAudit}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60"
        >
          <RefreshCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Sprawdź spójność
        </button>
      </div>

      <div className="text-sm text-gray-700">
        <span className="mr-4">OK: <strong>{audit.summary.ok}</strong></span>
        <span className="mr-4">Ostrzeżenia: <strong>{audit.summary.warning}</strong></span>
        <span>Błędy przypisania lub spójności: <strong>{audit.summary.error}</strong></span>
      </div>
      <p className="rounded-xl border border-slate-700 bg-slate-900 p-4 text-sm text-slate-300">Audyt rozróżnia błędne przypisanie operacji i ujemne salda w historii. Ostrzeżenie o dawnym saldzie nie oznacza, że obecne pieniądze są policzone nieprawidłowo. Korekty powinny odzwierciedlać rzeczywiste operacje.</p>
      {(() => {
        const cashChecks = audit.portfolios.map(p => p.checks.cash_negative_days).filter(c => c.current_ledger_cash!=null && c.current_stored_cash!=null);
        if (!cashChecks.length) return null;
        const matched = cashChecks.filter(c => Math.abs(c.current_stored_cash!-c.current_ledger_cash!)<=.01).length;
        return <p className={matched===cashChecks.length ? 'text-sm text-emerald-400' : 'text-sm text-amber-300'}>Obecne salda zgodne z historią: <strong>{matched} z {cashChecks.length}</strong>. Ostrzeżenia historyczne są oceniane osobno.</p>;
      })()}

      {error && <div className="text-sm text-red-600">{error}</div>}

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead>
            <tr>
              <th className="px-3 py-2 text-left font-semibold text-gray-600">Status</th>
              <th className="px-3 py-2 text-left font-semibold text-gray-600">Portfel</th>
              <th className="px-3 py-2 text-left font-semibold text-gray-600">Problemy</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {audit.portfolios.map((portfolio) => {
              const failingChecks = Object.entries(portfolio.checks).filter(([, result]) => !result.ok);
              return (
                <tr key={portfolio.portfolio_id}>
                  <td className="px-3 py-2 align-top"><span className="inline-flex items-center gap-2">{STATUS_ICON[portfolio.status]}{{ok:'Zgodny',warning:'Ostrzeżenie',error:'Do wyjaśnienia'}[portfolio.status]}</span></td>
                  <td className="px-3 py-2 align-top">{portfolio.portfolio_name}</td>
                  <td className="px-3 py-2">
                    {failingChecks.length === 0 ? (
                      <span className="text-green-700">Brak problemów</span>
                    ) : (
                      <div className="space-y-2">
                        {failingChecks.map(([key, result]) => (
                          (() => {
                            const incidents = key === 'cash_negative_days' && Array.isArray((result as { incidents?: unknown[] }).incidents)
                              ? (result as { incidents: Array<{ date: string; balance_pln: number; triggering_transaction_id: number; triggering_type: string; triggering_amount: number }> }).incidents
                              : [];
                            return (
                          <details key={key} className="rounded border border-amber-200 bg-amber-50 p-2">
                            <summary className="cursor-pointer font-medium text-amber-900">
                              {CHECK_LABELS[key] || key}
                            </summary>
                            <div className="mt-1 text-xs text-amber-900">
                              {result.explanation && <p className="my-2 leading-5">{result.explanation}</p>}
                              {result.amount_pln !== undefined && <p>Łączna kwota: {result.amount_pln.toLocaleString('pl-PL', {style:'currency',currency:'PLN'})}</p>}
                              {key === 'cash_negative_days' && (() => {
                                const cash = portfolio.checks.cash_negative_days;
                                if (cash.current_ledger_cash == null || cash.current_stored_cash == null) return null;
                                const difference = cash.current_stored_cash-cash.current_ledger_cash;
                                return <p className="my-2 font-medium">Obecne saldo: {cash.current_stored_cash.toFixed(2)} zł · Z historii: {cash.current_ledger_cash.toFixed(2)} zł · {Math.abs(difference)<=0.01 ? 'Salda są zgodne.' : `Różnica: ${difference.toFixed(2)} zł — wymaga wyjaśnienia.`}</p>;
                              })()}
                              {result.diff_pln !== undefined && (
                                <div>Różnica: {result.diff_pln.toFixed(2)} PLN</div>
                              )}
                              {result.count !== undefined && <div>Liczba: {result.count}</div>}
                              {Array.isArray(result.ids) && result.ids.length > 0 && (
                                <div>ID: {result.ids.join(', ')}</div>
                              )}
                              {key === 'cash_negative_days' && incidents.length > 0 && (
                                <div className="mt-2 space-y-2">
                                  <div className="font-semibold">⚠️ {incidents.length} dni z ujemnym saldem</div>
                                  <details><summary className="cursor-pointer">Pokaż dni i operacje wywołujące ostrzeżenie</summary><div className="overflow-x-auto">
                                    <table className="min-w-full text-xs border border-amber-200">
                                      <thead>
                                        <tr className="bg-amber-100">
                                          <th className="px-2 py-1 text-left">DATA</th>
                                          <th className="px-2 py-1 text-left">SALDO</th>
                                          <th className="px-2 py-1 text-left">TRANSAKCJA</th>
                                          <th className="px-2 py-1 text-left">KWOTA</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {incidents.map((incident, index) => (
                                          <tr key={`${incident.date}-${incident.triggering_transaction_id}-${index}`} className="border-t border-amber-100">
                                            <td className="px-2 py-1">
                                              <button
                                                type="button"
                                                onClick={() => openTransferForDate(portfolio.portfolio_id, incident.date)}
                                                className="underline hover:no-underline text-blue-700"
                                              >
                                                {incident.date}
                                              </button>
                                            </td>
                                            <td className="px-2 py-1 text-red-700 font-medium">{incident.balance_pln.toFixed(2)} PLN</td>
                                            <td className="px-2 py-1">#{incident.triggering_transaction_id} · {incident.triggering_type}</td>
                                            <td className="px-2 py-1">{incident.triggering_amount.toFixed(2)} PLN</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div></details>
                                  <div className="text-[11px] text-amber-900">
                                    Sprawdź datę i przypisanie wskazanej operacji. Transfer wsteczny dodawaj wyłącznie, jeśli rzeczywiście miał miejsce.
                                  </div>
                                </div>
                              )}
                            </div>
                          </details>
                            );
                          })()
                        ))}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
            {audit.portfolios.length === 0 && (
              <tr>
                <td className="px-3 py-4 text-gray-500" colSpan={3}>
                  Brak parent portfeli z childami do audytu.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
    {transferPortfolioId !== null && (
      <TransferModal
        isOpen={isTransferModalOpen}
        onClose={() => setIsTransferModalOpen(false)}
        onSuccess={fetchAudit}
        portfolioId={transferPortfolioId}
        budgetAccounts={[]}
        maxCash={getParentPortfolioById(transferPortfolioId)?.current_cash || 0}
        subPortfolios={getParentPortfolioById(transferPortfolioId)?.children || []}
        initialMode="INTERNAL_TRANSFER"
        initialDate={transferDate || undefined}
      />
    )}
    </>
  );
};

export default AuditConsistencyPanel;
