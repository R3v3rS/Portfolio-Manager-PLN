import React, { useState } from 'react';
import { portfolioApi, type PriceHistoryAuditResult } from '../../api';
import { extractErrorMessageFromUnknown } from '../../http/response';

const AdminPriceHistoryAudit: React.FC = () => {
  const [days, setDays] = useState('30');
  const [threshold, setThreshold] = useState('25');
  const [refreshFlagged, setRefreshFlagged] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PriceHistoryAuditResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const parsedDays = Number(days);
      const parsedThreshold = Number(threshold);

      const response = await portfolioApi.runPriceHistoryAudit({
        days: Number.isFinite(parsedDays) ? parsedDays : undefined,
        threshold: Number.isFinite(parsedThreshold) ? parsedThreshold : undefined,
        refresh_flagged: refreshFlagged,
      });
      setResult(response);
    } catch (err) {
      setError(extractErrorMessageFromUnknown(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 px-4 sm:px-0">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Admin → Audyt cen</h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">Globalny audyt jakości historii cen (skoki, braki, flagi).</p>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700 dark:text-gray-200">Dni</div>
            <input
              value={days}
              onChange={(e) => setDays(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800"
              inputMode="numeric"
            />
          </label>
          <label className="text-sm">
            <div className="mb-1 font-medium text-gray-700 dark:text-gray-200">Próg skoku (%)</div>
            <input
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800"
              inputMode="decimal"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
            <input type="checkbox" checked={refreshFlagged} onChange={(e) => setRefreshFlagged(e.target.checked)} />
            Odśwież flagged
          </label>
        </div>

        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={run}
            disabled={loading}
            className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? 'Audytowanie...' : 'Uruchom audyt'}
          </button>
          <button
            type="button"
            onClick={() => {
              setResult(null);
              setError(null);
            }}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            Wyczyść wynik
          </button>
        </div>
      </section>

      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/40 dark:text-red-200">{error}</div>}

      {result && (
        <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
          <div className="text-sm font-medium text-gray-900 dark:text-gray-100">Wynik</div>
          <pre className="mt-2 overflow-auto rounded-md bg-gray-50 p-3 text-xs text-gray-800 dark:bg-gray-950 dark:text-gray-100">
            {JSON.stringify(result, null, 2)}
          </pre>
        </section>
      )}
    </div>
  );
};

export default AdminPriceHistoryAudit;
