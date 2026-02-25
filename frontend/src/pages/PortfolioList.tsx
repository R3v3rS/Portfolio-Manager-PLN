import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, ChevronRight } from 'lucide-react';
import api from '../api';
import { Portfolio } from '../types';
import { cn } from '../lib/utils';

const PortfolioList: React.FC = () => {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [newPortfolioName, setNewPortfolioName] = useState('');
  const [initialCash, setInitialCash] = useState('');

  const fetchPortfolios = async () => {
    try {
      const response = await api.get('/list');
      setPortfolios(response.data.portfolios);
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
      await api.post('/create', {
        name: newPortfolioName,
        initial_cash: parseFloat(initialCash) || 0
      });
      setNewPortfolioName('');
      setInitialCash('');
      setIsCreating(false);
      fetchPortfolios();
    } catch (err) {
      console.error('Failed to create portfolio', err);
      alert('Failed to create portfolio');
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
        {portfolios.map((portfolio) => (
          <Link
            key={portfolio.id}
            to={`/portfolio/${portfolio.id}`}
            className="block hover:no-underline"
          >
            <div className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow duration-200">
              <div className="px-4 py-5 sm:p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium leading-6 text-gray-900 truncate">
                    {portfolio.name}
                  </h3>
                  <ChevronRight className="h-5 w-5 text-gray-400" />
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
        ))}
      </div>
    </div>
  );
};

export default PortfolioList;
