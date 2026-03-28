import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, RefreshCcw, XCircle } from 'lucide-react';
import { portfolioApi, type PortfolioConsistencyAuditResponse } from '../api';
import { extractErrorMessageFromUnknown } from '../http/response';

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
};

const AuditConsistencyPanel: React.FC = () => {
  const [audit, setAudit] = useState<PortfolioConsistencyAuditResponse>(EMPTY_AUDIT);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAudit = useCallback(async () => {
    try {
      setLoading(true);
      const response = await portfolioApi.getConsistencyAudit();
      setAudit(response);
      setError(null);
    } catch (err) {
      setError(extractErrorMessageFromUnknown(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAudit();
    const interval = window.setInterval(() => {
      fetchAudit();
    }, 30000);

    return () => window.clearInterval(interval);
  }, [fetchAudit]);

  return (
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
                            </div>
                          </details>
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
  );
};

export default AuditConsistencyPanel;
