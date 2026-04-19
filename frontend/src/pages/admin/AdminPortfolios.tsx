import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { portfolioApi } from '../../api';
import type { Portfolio } from '../../types';
import { extractErrorMessageFromUnknown } from '../../http/response';

const flattenTree = (items: Portfolio[], depth = 0): Array<{ portfolio: Portfolio; depth: number }> => {
  const result: Array<{ portfolio: Portfolio; depth: number }> = [];
  for (const item of items) {
    result.push({ portfolio: item, depth });
    if (Array.isArray(item.children) && item.children.length > 0) {
      result.push(...flattenTree(item.children, depth + 1));
    }
  }
  return result;
};

const AdminPortfolios: React.FC = () => {
  const [tree, setTree] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  const flattened = useMemo(() => flattenTree(tree), [tree]);

  return (
    <div className="space-y-4 px-4 sm:px-0">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Admin → Portfele</h1>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">Wybierz portfel, aby otworzyć narzędzia.</p>
        </div>
        <button
          type="button"
          onClick={fetchPortfolios}
          className="inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          Odśwież
        </button>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/40 dark:text-red-200">{error}</div>}

      {loading ? (
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
          Ładowanie portfeli...
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Portfel</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Typ</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase text-gray-500">Akcje</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {flattened.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                    Brak portfeli.
                  </td>
                </tr>
              ) : (
                flattened.map(({ portfolio, depth }) => (
                  <tr key={portfolio.id}>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">
                      <span style={{ paddingLeft: `${depth * 16}px` }}>
                        {depth > 0 ? '↳ ' : ''}
                        {portfolio.name}
                        {portfolio.is_archived ? <span className="ml-2 text-xs text-gray-400">(Zarchiwizowany)</span> : null}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-200">{portfolio.account_type}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/admin/portfolio/${portfolio.id}`}
                        className="inline-flex items-center gap-1 rounded-md border border-blue-300 bg-blue-50 px-2.5 py-1.5 text-xs font-medium text-blue-800 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200 dark:hover:bg-blue-900/40"
                      >
                        Narzędzia
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default AdminPortfolios;
