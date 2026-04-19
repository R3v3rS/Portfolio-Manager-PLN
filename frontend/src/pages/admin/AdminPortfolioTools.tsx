import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { portfolioApi, type PortfolioAuditResult } from '../../api';
import type { Portfolio } from '../../types';
import { extractErrorMessageFromUnknown } from '../../http/response';
import { ImportXtbCsvButton } from '../PortfolioDetails';

const findPortfolioInTree = (items: Portfolio[], id: number): Portfolio | null => {
  for (const item of items) {
    if (item.id === id) return item;
    if (Array.isArray(item.children) && item.children.length > 0) {
      const found = findPortfolioInTree(item.children, id);
      if (found) return found;
    }
  }
  return null;
};

const flattenTree = (items: Portfolio[]): Portfolio[] => {
  const result: Portfolio[] = [];
  for (const item of items) {
    result.push(item);
    if (Array.isArray(item.children) && item.children.length > 0) {
      result.push(...flattenTree(item.children));
    }
  }
  return result;
};

const AdminPortfolioTools: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const portfolioId = Number(id);

  const [tree, setTree] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [auditLoading, setAuditLoading] = useState(false);
  const [auditResult, setAuditResult] = useState<PortfolioAuditResult | null>(null);

  const [rebuildLoading, setRebuildLoading] = useState(false);
  const [clearLoading, setClearLoading] = useState(false);

  const fetchPortfolios = useCallback(async () => {
    try {
      setLoading(true);
      const response = await portfolioApi.list({ tree: 1 });
      setTree(response.portfolios ?? []);
      setError(null);
    } catch (err) {
      setError(extractErrorMessageFromUnknown(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPortfolios();
  }, [fetchPortfolios]);

  const allPortfolios = useMemo(() => flattenTree(tree), [tree]);
  const portfolio = useMemo(() => (Number.isFinite(portfolioId) ? findPortfolioInTree(tree, portfolioId) : null), [portfolioId, tree]);
  const subPortfolios = useMemo(() => allPortfolios.filter((p) => p.parent_portfolio_id === portfolioId), [allPortfolios, portfolioId]);

  const runAudit = async () => {
    if (!portfolio) return;
    setAuditLoading(true);
    try {
      const result = await portfolioApi.runAudit(portfolio.id);
      setAuditResult(result);
    } catch (err) {
      alert(extractErrorMessageFromUnknown(err));
    } finally {
      setAuditLoading(false);
    }
  };

  const runRebuild = async () => {
    if (!portfolio) return;
    const confirmed = window.confirm(`Rebuild z transakcji dla "${portfolio.name}"?`);
    if (!confirmed) return;

    setRebuildLoading(true);
    try {
      const result = await portfolioApi.rebuild(portfolio.id);
      alert(result.message ?? 'Rebuild zakończony.');
    } catch (err) {
      alert(extractErrorMessageFromUnknown(err));
    } finally {
      setRebuildLoading(false);
    }
  };

  const clearPortfolio = async () => {
    if (!portfolio) return;
    const confirmed = window.confirm(`To usunie wszystkie dane z portfela "${portfolio.name}". Czy kontynuować?`);
    if (!confirmed) return;

    setClearLoading(true);
    try {
      await portfolioApi.clear(portfolio.id);
      alert('Portfolio zostało wyczyszczone.');
      setAuditResult(null);
    } catch (err) {
      alert(extractErrorMessageFromUnknown(err));
    } finally {
      setClearLoading(false);
    }
  };

  if (!Number.isFinite(portfolioId)) {
    return (
      <div className="px-4 sm:px-0">
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/40 dark:text-red-200">
          Niepoprawne ID portfela.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 px-4 sm:px-0">
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to="/admin/portfolios"
          className="inline-flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          Wróć do listy portfeli
        </Link>
        {portfolio ? (
          <Link
            to={`/portfolio/${portfolio.id}`}
            className="inline-flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-800 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            Otwórz portfel
          </Link>
        ) : null}
      </div>

      <div>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Admin → Narzędzia portfela</h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">
          {portfolio ? (
            <>
              Portfel: <span className="font-medium text-gray-800 dark:text-gray-100">{portfolio.name}</span> ({portfolio.account_type})
            </>
          ) : (
            'Ładowanie portfela...'
          )}
        </p>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/40 dark:text-red-200">{error}</div>}

      {loading ? (
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
          Ładowanie...
        </div>
      ) : !portfolio ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-200">
          Nie znaleziono portfela.
        </div>
      ) : (
        <div className="space-y-4">
          <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">Import</div>
            <div className="mt-3">
              <ImportXtbCsvButton portfolioId={portfolio.id} onSuccess={fetchPortfolios} subPortfolios={subPortfolios} />
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">Diagnostyka</div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={runAudit}
                disabled={auditLoading}
                className="inline-flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-60"
              >
                {auditLoading ? 'Audytowanie...' : 'Audyt integralności'}
              </button>
              <button
                type="button"
                onClick={() => setAuditResult(null)}
                className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                Wyczyść wynik
              </button>
            </div>

            {auditResult ? (
              <pre className="mt-3 overflow-auto rounded-md bg-gray-50 p-3 text-xs text-gray-800 dark:bg-gray-950 dark:text-gray-100">
                {JSON.stringify(auditResult, null, 2)}
              </pre>
            ) : null}
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900">
            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">Operacje</div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={runRebuild}
                disabled={rebuildLoading}
                className="inline-flex items-center gap-2 rounded-md border border-indigo-300 bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 disabled:opacity-60"
              >
                {rebuildLoading ? 'Rebuild...' : 'Rebuild from transactions'}
              </button>
              <button
                type="button"
                onClick={clearPortfolio}
                disabled={clearLoading}
                className="inline-flex items-center gap-2 rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
              >
                {clearLoading ? 'Czyszczenie...' : 'Wyczyść portfolio'}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
};

export default AdminPortfolioTools;
