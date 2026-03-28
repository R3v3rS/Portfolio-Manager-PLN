import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, ChevronRight, Trash2 } from 'lucide-react';
import { portfolioApi } from '../api';
import { Portfolio } from '../types';
import { cn } from '../lib/utils.ts';

const PortfolioList: React.FC = () => {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [newPortfolioName, setNewPortfolioName] = useState('');
  const [initialCash, setInitialCash] = useState('');
  const [accountType, setAccountType] = useState<'STANDARD' | 'IKE' | 'BONDS' | 'SAVINGS' | 'PPK'>('STANDARD');
  const [createdAt, setCreatedAt] = useState(new Date().toISOString().split('T')[0]);

  const fetchPortfolios = async () => {
    try {
      const response = await portfolioApi.list();
      setPortfolios(response.portfolios);
    } catch (err) {
      console.error('Failed to fetch portfolios', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolios();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPortfolioName.trim()) return;

    try {
      await portfolioApi.create({
        name: newPortfolioName,
        initial_cash: parseFloat(initialCash) || 0,
        account_type: accountType,
        created_at: createdAt
      });
      setNewPortfolioName('');
      setInitialCash('');
      setAccountType('STANDARD');
      setCreatedAt(new Date().toISOString().split('T')[0]);
      setIsCreating(false);
      fetchPortfolios();
    } catch (err) {
      console.error('Failed to create portfolio', err);
      alert('Failed to create portfolio');
    }
  };

  const handleDeletePortfolio = async (e: React.MouseEvent, portfolio: Portfolio) => {
    e.preventDefault();
    e.stopPropagation();

    if (!window.confirm(`Czy na pewno chcesz usunąć puste portfolio "${portfolio.name}"?`)) {
      return;
    }

    try {
      await portfolioApi.remove(portfolio.id);
      await fetchPortfolios();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Nie udało się usunąć portfolio. Usuń najpierw wszystkie operacje.';
      alert(message);
    }
  };

  if (loading) return <div className="p-4 text-center">Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">My Portfolios</h1>
        <button
          onClick={() => setIsCreating(!isCreating)}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <Plus className="mr-2 h-4 w-4" />
          Create Portfolio
        </button>
      </div>

      {isCreating && (
        <div className="bg-white shadow rounded-lg p-6 border border-blue-100">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Create New Portfolio</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">Portfolio Name</label>
              <input
                type="text"
                id="name"
                value={newPortfolioName}
                onChange={(e) => setNewPortfolioName(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                placeholder="e.g. Retirement Fund"
                required
              />
            </div>
            <div>
              <label htmlFor="cash" className="block text-sm font-medium text-gray-700">Initial Cash Deposit (PLN)</label>
              <input
                type="number"
                id="cash"
                value={initialCash}
                onChange={(e) => setInitialCash(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                placeholder="0.00"
                min="0"
                step="0.01"
              />
            </div>
            <div>
              <label htmlFor="type" className="block text-sm font-medium text-gray-700">Account Type</label>
              <select
                id="type"
                value={accountType}
                onChange={(e) => setAccountType(e.target.value as 'STANDARD' | 'IKE' | 'BONDS' | 'SAVINGS' | 'PPK')}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
              >
                <option value="STANDARD">Standard Stocks</option>
                <option value="IKE">IKE (Stocks)</option>
                <option value="BONDS">Bonds (Obligacje)</option>
                <option value="SAVINGS">Savings Account</option>
                <option value="PPK">PPK</option>
              </select>
            </div>
            <div>
              <label htmlFor="createdAt" className="block text-sm font-medium text-gray-700">Creation Date</label>
              <input
                type="date"
                id="createdAt"
                value={createdAt}
                onChange={(e) => setCreatedAt(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                required
              />
            </div>
            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={() => setIsCreating(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none"
              >
                Create
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {portfolios.map((portfolio) => {
          const isEmptyPortfolio =
            portfolio.is_empty ??
            ((portfolio.current_cash || 0) === 0 && (portfolio.portfolio_value || 0) === 0);

          return (
            <div key={portfolio.id} className="space-y-4">
              <Link
                to={`/portfolio/${portfolio.id}`}
                className="block hover:no-underline"
              >
                <div className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow duration-200 border-l-4 border-blue-500">
                  <div className="px-4 py-5 sm:p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex flex-col">
                        <h3 className="text-lg font-medium leading-6 text-gray-900 truncate">
                          {portfolio.name}
                        </h3>
                        <span className={cn(
                          "text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full mt-1 w-fit",
                          portfolio.account_type === 'SAVINGS' ? "bg-emerald-100 text-emerald-800" :
                          portfolio.account_type === 'BONDS' ? "bg-amber-100 text-amber-800" :
                          portfolio.account_type === 'IKE' ? "bg-indigo-100 text-indigo-800" :
                          portfolio.account_type === 'PPK' ? "bg-purple-100 text-purple-800" :
                          "bg-gray-100 text-gray-800"
                        )}>
                          {portfolio.account_type}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {isEmptyPortfolio && (
                          <button
                            type="button"
                            onClick={(e) => handleDeletePortfolio(e, portfolio)}
                            className="inline-flex items-center justify-center rounded-md p-2 text-red-600 hover:bg-red-50"
                            title="Usuń puste portfolio"
                            aria-label="Usuń puste portfolio"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                        <ChevronRight className="h-5 w-5 text-gray-400" />
                      </div>
                    </div>
                    <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
                      <div className="sm:col-span-2">
                        <dt className="text-sm font-medium text-gray-500">Total Value</dt>
                        <dd className="mt-1 text-2xl font-semibold text-gray-900">
                          {portfolio.portfolio_value?.toFixed(2)} PLN
                        </dd>
                      </div>
                      <div className="sm:col-span-1">
                        <dt className="text-xs font-medium text-gray-500">Cash</dt>
                        <dd className="mt-1 text-sm text-gray-900">{portfolio.current_cash?.toFixed(2)} PLN</dd>
                      </div>
                      <div className="sm:col-span-1 text-right">
                        <dt className="text-xs font-medium text-gray-500">Profit/Loss</dt>
                        <dd className={cn("mt-1 text-sm font-medium",
                          (portfolio.total_result || 0) >= 0 ? "text-green-600" : "text-red-600")}>
                          {portfolio.total_result_percent?.toFixed(2)}%
                        </dd>
                      </div>
                    </dl>
                  </div>
                </div>
              </Link>

              {/* Sub-portfolios list */}
              {portfolio.children && portfolio.children.length > 0 && (
                <div className="ml-8 space-y-2 border-l-2 border-gray-200 pl-4">
                  {portfolio.children.map((child) => (
                    <Link
                      key={child.id}
                      to={`/portfolio/${child.id}`}
                      className="block group"
                    >
                      <div className={cn(
                        "flex items-center justify-between p-3 rounded-md border transition-colors",
                        child.is_archived ? "bg-gray-50 border-gray-100 opacity-60" : "bg-white border-gray-100 hover:border-blue-200 hover:bg-blue-50/30"
                      )}>
                        <div className="flex flex-col">
                          <span className="text-sm font-medium text-gray-700 group-hover:text-blue-700">
                            {child.name}
                            {child.is_archived && <span className="ml-2 text-[10px] text-gray-400 font-normal">(Archived)</span>}
                          </span>
                          <span className="text-xs text-gray-500">
                            {child.portfolio_value?.toFixed(2)} PLN
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "text-[10px] font-bold",
                            (child.total_result || 0) >= 0 ? "text-green-600" : "text-red-600"
                          )}>
                            {child.total_result_percent?.toFixed(1)}%
                          </span>
                          <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-blue-400" />
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PortfolioList;
