import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, ArrowDownRight, Wallet, TrendingUp, DollarSign, PieChart, Plus } from 'lucide-react';
import api from '../api';
import { Portfolio } from '../types';
import { cn } from '../lib/utils';

interface TaxLimitItem {
  portfolio_id: number;
  portfolio_name: string;
  type: 'IKE' | 'IKZE';
  deposited: number;
  limit: number;
  percentage: number;
}

interface TaxLimitsResponse {
  year: number;
  limits: TaxLimitItem[];
}

const PortfolioDashboard: React.FC = () => {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [taxLimits, setTaxLimits] = useState<TaxLimitsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newPortfolioName, setNewPortfolioName] = useState('');
  const [initialCash, setInitialCash] = useState('');
  const [accountType, setAccountType] = useState<'STANDARD' | 'IKE' | 'BONDS' | 'SAVINGS'>('STANDARD');
  const [createdAt, setCreatedAt] = useState(new Date().toISOString().split('T')[0]);

  const fetchData = async () => {
    try {
      const [listRes, limitsRes] = await Promise.all([
        api.get('/list'),
        api.get('/limits')
      ]);
      setPortfolios(listRes.data.portfolios);
      // Backend returns { limits: [...], year: 2026 }
      setTaxLimits({
        year: limitsRes.data.year,
        limits: limitsRes.data.limits
      });
    } catch (err) {
      setError('Failed to fetch dashboard data');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPortfolioName.trim()) return;

    try {
      await api.post('/create', {
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
      fetchData();
    } catch (err) {
      console.error('Failed to create portfolio', err);
      alert('Failed to create portfolio');
    }
  };

  if (loading) return <div className="p-4 text-center">Ładowanie...</div>;
  if (error) return <div className="p-4 text-center text-red-600">{error}</div>;

  const totalValue = portfolios.reduce((sum, p) => sum + (p.portfolio_value || 0), 0);
  const totalDeposits = portfolios.reduce((sum, p) => sum + (p.total_deposits || 0), 0);
  const totalDividends = portfolios.reduce((sum, p) => sum + (p.total_dividends || 0), 0);
  const totalResult = totalValue - totalDeposits;
  const totalResultPercent = totalDeposits > 0 ? (totalResult / totalDeposits) * 100 : 0;

  const cards = [
    {
      name: 'Wartość Portfeli',
      value: `${totalValue.toFixed(2)} PLN`,
      icon: Wallet,
      color: 'bg-blue-500',
    },
    {
      name: 'Wpłaty Ogółem',
      value: `${totalDeposits.toFixed(2)} PLN`,
      icon: DollarSign,
      color: 'bg-gray-500',
    },
    {
      name: 'Dywidendy',
      value: `${totalDividends.toFixed(2)} PLN`,
      icon: PieChart,
      color: 'bg-indigo-500',
    },
    {
      name: 'Zysk/Strata',
      value: `${totalResult.toFixed(2)} PLN`,
      subValue: `${totalResultPercent.toFixed(2)}%`,
      icon: totalResult >= 0 ? TrendingUp : ArrowDownRight,
      color: totalResult >= 0 ? 'bg-green-500' : 'bg-red-500',
      textColor: totalResult >= 0 ? 'text-green-600' : 'text-red-600',
    },
  ];

  return (
    <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900">Inwestycje - Dashboard</h1>
            <button
              onClick={() => setIsCreating(!isCreating)}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <Plus className="mr-2 h-4 w-4" />
              Nowy Portfel
            </button>
          </div>
    
          {isCreating && (
            <div className="bg-white shadow rounded-lg p-6 border border-blue-100">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Utwórz Nowy Portfel</h3>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-700">Nazwa Portfela</label>
                    <input
                      type="text"
                      id="name"
                      value={newPortfolioName}
                      onChange={(e) => setNewPortfolioName(e.target.value)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                      placeholder="np. Emerytura IKE"
                      required
                    />
                  </div>
                  <div>
                    <label htmlFor="cash" className="block text-sm font-medium text-gray-700">Gotówka na start (PLN)</label>
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
                    <label htmlFor="type" className="block text-sm font-medium text-gray-700">Typ Konta</label>
                    <select
                      id="type"
                      value={accountType}
                      onChange={(e) => setAccountType(e.target.value as any)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                    >
                      <option value="STANDARD">Standardowe Akcje</option>
                      <option value="IKE">IKE (Akcje)</option>
                      <option value="BONDS">Obligacje</option>
                      <option value="SAVINGS">Konto Oszczędnościowe</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="createdAt" className="block text-sm font-medium text-gray-700">Data Utworzenia</label>
                    <input
                      type="date"
                      id="createdAt"
                      value={createdAt}
                      onChange={(e) => setCreatedAt(e.target.value)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                      required
                    />
                  </div>
                </div>
                <div className="flex justify-end space-x-3">
                  <button
                    type="button"
                    onClick={() => setIsCreating(false)}
                    className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
                  >
                    Anuluj
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none"
                  >
                    Utwórz
                  </button>
                </div>
              </form>
            </div>
          )}
      
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-4">
        {cards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div key={idx} className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className={cn("flex-shrink-0 rounded-md p-3", card.color)}>
                    <Icon className="h-6 w-6 text-white" aria-hidden="true" />
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">{card.name}</dt>
                      <dd className="text-lg font-medium text-gray-900">{card.value}</dd>
                      {card.subValue && (
                        <dd className={cn("text-sm font-semibold", card.textColor)}>
                          {card.subValue}
                        </dd>
                      )}
                    </dl>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {taxLimits && taxLimits.limits.length > 0 && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Limity Podatkowe ({taxLimits.year})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {taxLimits.limits.map((item) => (
              <div key={item.portfolio_id}>
                <div className="flex justify-between mb-1">
                  <span className="text-sm font-medium text-gray-700">{item.portfolio_name}</span>
                  <span className={cn("text-sm font-medium", item.percentage >= 100 ? "text-emerald-600 font-bold" : "text-gray-500")}>
                    {item.percentage >= 100 ? "Limit wyczerpany!" : `${item.deposited.toFixed(2)} / ${item.limit.toFixed(2)} PLN`}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
                  <div 
                    className={cn("h-4 rounded-full transition-all duration-500", 
                      item.percentage >= 100 ? "bg-emerald-500" : "bg-blue-600"
                    )} 
                    style={{ width: `${Math.min(item.percentage, 100)}%` }}
                  ></div>
                </div>
                <div className="mt-1 text-xs text-right text-gray-500">{item.percentage.toFixed(1)}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Twoje Portfele</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nazwa</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Wartość</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Dywidendy</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Wynik</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Zwrot %</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {portfolios.map((portfolio) => (
                <tr key={portfolio.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    <Link to={`/portfolio/${portfolio.id}`} className="flex flex-col hover:text-blue-600">
                      <span className="text-base font-semibold">{portfolio.name}</span>
                      <span className="text-[10px] text-gray-500 font-bold uppercase">{portfolio.account_type}</span>
                    </Link>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                    {portfolio.portfolio_value?.toFixed(2)} PLN
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-blue-600 font-medium">
                    {portfolio.total_dividends?.toFixed(2)} PLN
                  </td>
                  <td className={cn("px-6 py-4 whitespace-nowrap text-sm text-right font-medium", 
                    (portfolio.total_result || 0) >= 0 ? "text-green-600" : "text-red-600")}>
                    {portfolio.total_result?.toFixed(2)} PLN
                  </td>
                  <td className={cn("px-6 py-4 whitespace-nowrap text-sm text-right font-medium", 
                    (portfolio.total_result_percent || 0) >= 0 ? "text-green-600" : "text-red-600")}>
                    {portfolio.total_result_percent?.toFixed(2)}%
                  </td>
                </tr>
              ))}
              {portfolios.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">
                    No portfolios found. Create one to get started!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default PortfolioDashboard;
