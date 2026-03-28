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
  value_match: 'Spójność wartości parent = own + children',
  orphan_transactions: 'Orphan transactions',
  interest_leaked: 'INTEREST przypisany do childa',
  archived_child_transactions: 'Transakcje po archiwizacji childa',
  cash_negative_days: 'Ujemne saldo gotówki',
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
        <span className="mr-4">Warning: <strong>{audit.summary.warning}</strong></span>
        <span>Error: <strong>{audit.summary.error}</strong></span>
      </div>

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
                  <td className="px-3 py-2 align-top">{STATUS_ICON[portfolio.status]}</td>
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
                                  <div className="overflow-x-auto">
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
                                  </div>
                                  <div className="text-[11px] text-amber-900">
                                    Użyj Transferu wewnętrznego aby uzupełnić brakującą gotówkę z datą wsteczną
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
