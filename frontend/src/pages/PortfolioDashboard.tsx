import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDownRight, Wallet, TrendingUp, DollarSign, PieChart, Plus } from 'lucide-react';
import { portfolioApi, type TaxLimitsResponse, type ConfigResponse } from '../api';
import { Portfolio } from '../types';
import { cn } from '../lib/utils';
import { ChevronRight, ChevronDown, Archive } from 'lucide-react';

const PortfolioRow: React.FC<{ 
  portfolio: Portfolio; 
  level?: number;
  onChildCreate?: (parentId: number) => void;
}> = ({ portfolio, level = 0, onChildCreate }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const hasChildren = portfolio.children && portfolio.children.length > 0;

  return (
    <>
      <tr className={cn(
        "transition-colors hover:bg-gray-50 dark:hover:bg-slate-900/50 group",
        portfolio.is_archived && "opacity-60 bg-gray-50/50 dark:bg-slate-900/30"
      )}>
        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-slate-100">
          <div className="flex items-center" style={{ paddingLeft: `${level * 1.5}rem` }}>
            {hasChildren ? (
              <button 
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1 hover:bg-gray-200 dark:hover:bg-slate-800 rounded mr-1 text-gray-500 dark:text-slate-400"
              >
                {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
            ) : (
              <div className="w-6" />
            )}
            <Link to={`/portfolio/${portfolio.id}`} className="flex flex-col hover:text-blue-600 dark:hover:text-blue-400">
              <span className="text-base font-semibold flex items-center">
                {portfolio.name}
                {portfolio.is_archived && <Archive className="ml-2 h-3 w-3 text-gray-400 dark:text-slate-500" />}
              </span>
              <span className="text-[10px] text-gray-500 dark:text-slate-400 font-bold uppercase">{portfolio.account_type}</span>
            </Link>
            
            {!portfolio.parent_portfolio_id && ['IKE', 'STANDARD'].includes(portfolio.account_type) && (
              <button
                onClick={() => onChildCreate?.(portfolio.id)}
                className="ml-2 p-1 text-gray-400 hover:text-blue-600 dark:text-slate-500 dark:hover:text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity"
                title="Dodaj sub-portfel"
              >
                <Plus className="h-4 w-4" />
              </button>
            )}
          </div>
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500 dark:text-slate-400 tabular-nums">
          {portfolio.portfolio_value?.toFixed(2)} PLN
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-blue-600 dark:text-blue-400 font-medium tabular-nums">
          {portfolio.total_dividends?.toFixed(2)} PLN
        </td>
        <td className={cn("px-6 py-4 whitespace-nowrap text-sm text-right font-bold tabular-nums", 
          (portfolio.total_result || 0) >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400")}>
          {portfolio.total_result?.toFixed(2)} PLN
        </td>
        <td className={cn("px-6 py-4 whitespace-nowrap text-sm text-right font-bold tabular-nums", 
          (portfolio.total_result_percent || 0) >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400")}>
          {portfolio.total_result_percent?.toFixed(2)}%
        </td>
      </tr>
      {isExpanded && hasChildren && portfolio.children?.map(child => (
        <PortfolioRow 
          key={child.id} 
          portfolio={child} 
          level={level + 1} 
          onChildCreate={onChildCreate}
        />
      ))}
    </>
  );
};

const PortfolioDashboard: React.FC = () => {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [taxLimits, setTaxLimits] = useState<TaxLimitsResponse | null>(null);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [parentPortfolioId, setParentPortfolioId] = useState<number | null>(null);
  const [newPortfolioName, setNewPortfolioName] = useState('');
  const [initialCash, setInitialCash] = useState('');
  const [accountType, setAccountType] = useState<'STANDARD' | 'IKE' | 'BONDS' | 'SAVINGS' | 'PPK'>('STANDARD');
  const [createdAt, setCreatedAt] = useState(new Date().toISOString().split('T')[0]);

  const fetchData = async () => {
    try {
      const [listRes, limitsRes, configRes] = await Promise.all([
        portfolioApi.list(),
        portfolioApi.limits(),
        portfolioApi.config()
      ]);
      setPortfolios(listRes.portfolios);
      setTaxLimits(limitsRes.limits);
      setConfig(configRes);
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
      if (parentPortfolioId) {
        await portfolioApi.createChild(parentPortfolioId, {
          name: newPortfolioName,
          initial_cash: parseFloat(initialCash) || 0,
          account_type: accountType,
          created_at: createdAt,
          parent_portfolio_id: parentPortfolioId
        });
      } else {
        await portfolioApi.create({
          name: newPortfolioName,
          initial_cash: parseFloat(initialCash) || 0,
          account_type: accountType,
          created_at: createdAt
        });
      }
      setNewPortfolioName('');
      setInitialCash('');
      setAccountType('STANDARD');
      setParentPortfolioId(null);
      setCreatedAt(new Date().toISOString().split('T')[0]);
      setIsCreating(false);
      fetchData();
    } catch (err) {
      console.error('Failed to create portfolio', err);
      alert('Failed to create portfolio');
    }
  };

  const handleAddSubPortfolio = (parentId: number) => {
    const parent = portfolios.find(p => p.id === parentId);
    if (parent) {
      setAccountType(parent.account_type);
      setParentPortfolioId(parentId);
      setIsCreating(true);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  if (loading) return <div className="p-4 text-center">Ładowanie...</div>;
  if (error) return <div className="p-4 text-center text-red-600">{error}</div>;

  const totalValue = portfolios.reduce((sum, p) => sum + (p.portfolio_value || 0), 0);
  const totalDeposits = portfolios.reduce((sum, p) => sum + (p.total_deposits || 0), 0);
  const totalDividends = portfolios.reduce((sum, p) => sum + (p.total_dividends || 0), 0);
  const totalResult = portfolios.reduce((sum, p) => sum + (p.total_result || 0), 0);
  const totalNetContributions = totalValue - totalResult;
  const totalResultPercent = totalNetContributions > 0 ? (totalResult / totalNetContributions) * 100 : 0;

  const cards = [
    {
      name: 'Wartość Portfeli',
      value: `${totalValue.toFixed(2)} PLN`,
      icon: Wallet,
      color: 'bg-blue-500 dark:bg-blue-600',
    },
    {
      name: 'Wpłaty Ogółem',
      value: `${totalDeposits.toFixed(2)} PLN`,
      icon: DollarSign,
      color: 'bg-slate-500 dark:bg-slate-600',
    },
    {
      name: 'Dywidendy',
      value: `${totalDividends.toFixed(2)} PLN`,
      icon: PieChart,
      color: 'bg-indigo-500 dark:bg-indigo-600',
    },
    {
      name: 'Zysk/Strata',
      value: `${totalResult.toFixed(2)} PLN`,
      subValue: `${totalResultPercent.toFixed(2)}%`,
      icon: totalResult >= 0 ? TrendingUp : ArrowDownRight,
      color: totalResult >= 0 ? 'bg-emerald-500 dark:bg-emerald-600' : 'bg-red-500 dark:bg-red-600',
      textColor: totalResult >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400',
    },
  ];

  return (
    <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Inwestycje - Dashboard</h1>
            <button
              onClick={() => setIsCreating(!isCreating)}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-semibold rounded-lg shadow-sm text-white bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
            >
              <Plus className="mr-2 h-4 w-4" />
              Nowy Portfel
            </button>
          </div>
    
          {isCreating && (
            <div className="bg-white dark:bg-slate-900 shadow-sm rounded-xl p-6 border border-gray-200 dark:border-slate-800">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">
                  {parentPortfolioId ? `Dodaj Sub-portfel dla: ${portfolios.find(p => p.id === parentPortfolioId)?.name}` : 'Utwórz Nowy Portfel'}
                </h3>
              </div>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-slate-300">Nazwa Portfela</label>
                    <input
                      type="text"
                      id="name"
                      value={newPortfolioName}
                      onChange={(e) => setNewPortfolioName(e.target.value)}
                      className="mt-1 block w-full rounded-lg border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border transition-colors"
                      placeholder="np. Emerytura IKE"
                      required
                    />
                  </div>
                  <div>
                    <label htmlFor="cash" className="block text-sm font-medium text-gray-700 dark:text-slate-300">Gotówka na start (PLN)</label>
                    <input
                      type="number"
                      id="cash"
                      value={initialCash}
                      onChange={(e) => setInitialCash(e.target.value)}
                      className="mt-1 block w-full rounded-lg border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border transition-colors"
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                    />
                  </div>
                  <div>
                    <label htmlFor="type" className="block text-sm font-medium text-gray-700 dark:text-slate-300">Typ Konta</label>
                    <select
                      id="type"
                      value={accountType}
                      onChange={(e) => setAccountType(e.target.value as 'STANDARD' | 'IKE' | 'BONDS' | 'SAVINGS' | 'PPK')}
                      disabled={!!parentPortfolioId}
                      className="mt-1 block w-full rounded-lg border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border disabled:bg-gray-100 dark:disabled:bg-slate-800/50 transition-colors"
                    >
                      <option value="STANDARD">Standardowe Akcje</option>
                      <option value="IKE">IKE (Akcje)</option>
                      <option value="BONDS">Obligacje</option>
                      <option value="SAVINGS">Konto Oszczędnościowe</option>
                      <option value="PPK">PPK</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="createdAt" className="block text-sm font-medium text-gray-700 dark:text-slate-300">Data Utworzenia</label>
                    <input
                      type="date"
                      id="createdAt"
                      value={createdAt}
                      onChange={(e) => setCreatedAt(e.target.value)}
                      className="mt-1 block w-full rounded-lg border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border transition-colors"
                      required
                    />
                  </div>
                </div>
                <div className="flex justify-end space-x-3 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreating(false);
                      setParentPortfolioId(null);
                    }}
                    className="px-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm font-semibold text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 focus:outline-none transition-colors"
                  >
                    Anuluj
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-500 focus:outline-none transition-colors"
                  >
                    {parentPortfolioId ? 'Dodaj Sub-portfel' : 'Utwórz Portfel'}
                  </button>
                </div>
              </form>
            </div>
          )}
      
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-4">
        {cards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div key={idx} className="bg-white dark:bg-slate-900 overflow-hidden shadow-sm border border-gray-200 dark:border-slate-800 rounded-xl transition-colors">
              <div className="p-5">
                <div className="flex items-center">
                  <div className={cn("flex-shrink-0 rounded-lg p-3 shadow-sm", card.color)}>
                    <Icon className="h-6 w-6 text-white" aria-hidden="true" />
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 dark:text-slate-400 truncate">{card.name}</dt>
                      <dd className="text-lg font-bold text-gray-900 dark:text-slate-100 tabular-nums tracking-tight">{card.value}</dd>
                      {card.subValue && (
                        <dd className={cn("text-sm font-bold tabular-nums", card.textColor)}>
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

      {taxLimits && (
        <div className="bg-white dark:bg-slate-900 shadow-sm border border-gray-200 dark:border-slate-800 rounded-xl p-6 transition-colors">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-5">Limity Podatkowe ({taxLimits.year})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* IKE */}
            <div className="space-y-2">
              <div className="flex justify-between items-end mb-1">
                <span className="text-sm font-semibold text-gray-700 dark:text-slate-300">IKE</span>
                <span className={cn("text-sm font-medium tabular-nums", taxLimits.IKE.percentage >= 100 ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-gray-500 dark:text-slate-400")}>
                  {taxLimits.IKE.percentage >= 100 ? "Limit wyczerpany!" : `${taxLimits.IKE.deposited.toFixed(2)} / ${taxLimits.IKE.limit.toFixed(2)} PLN`}
                </span>
              </div>
              <div className="w-full bg-gray-100 dark:bg-slate-800 rounded-full h-3 overflow-hidden shadow-inner">
                <div 
                  className={cn("h-full rounded-full transition-all duration-1000 ease-out", 
                    taxLimits.IKE.percentage >= 100 ? "bg-emerald-500 dark:bg-emerald-400" : "bg-blue-600 dark:bg-blue-500"
                  )} 
                  style={{ width: `${Math.min(taxLimits.IKE.percentage, 100)}%` }}
                ></div>
              </div>
              <div className="mt-1 text-xs font-bold text-right text-gray-500 dark:text-slate-400 tabular-nums">{taxLimits.IKE.percentage.toFixed(1)}%</div>
            </div>

            {/* IKZE */}
            <div className="space-y-2">
              <div className="flex justify-between items-end mb-1">
                <span className="text-sm font-semibold text-gray-700 dark:text-slate-300">IKZE</span>
                <span className={cn("text-sm font-medium tabular-nums", taxLimits.IKZE.percentage >= 100 ? "text-emerald-600 dark:text-emerald-400 font-bold" : "text-gray-500 dark:text-slate-400")}>
                  {taxLimits.IKZE.percentage >= 100 ? "Limit wyczerpany!" : `${taxLimits.IKZE.deposited.toFixed(2)} / ${taxLimits.IKZE.limit.toFixed(2)} PLN`}
                </span>
              </div>
              <div className="w-full bg-gray-100 dark:bg-slate-800 rounded-full h-3 overflow-hidden shadow-inner">
                <div 
                  className={cn("h-full rounded-full transition-all duration-1000 ease-out", 
                    taxLimits.IKZE.percentage >= 100 ? "bg-emerald-500 dark:bg-emerald-400" : "bg-blue-600 dark:bg-blue-500"
                  )} 
                  style={{ width: `${Math.min(taxLimits.IKZE.percentage, 100)}%` }}
                ></div>
              </div>
              <div className="mt-1 text-xs font-bold text-right text-gray-500 dark:text-slate-400 tabular-nums">{taxLimits.IKZE.percentage.toFixed(1)}%</div>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-slate-900 shadow-sm border border-gray-200 dark:border-slate-800 rounded-xl overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-200 dark:border-slate-800 bg-gray-50/50 dark:bg-slate-900/50">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Twoje Portfele</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-800">
            <thead className="bg-gray-50/80 dark:bg-slate-900/80 backdrop-blur-sm">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">Nazwa</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">Wartość</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">Dywidendy</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">Wynik</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">Zwrot %</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-slate-950 divide-y divide-gray-100 dark:divide-slate-800/50">
              {portfolios.map((portfolio) => (
                <PortfolioRow 
                  key={portfolio.id} 
                  portfolio={portfolio} 
                  onChildCreate={handleAddSubPortfolio}
                />
              ))}
              {portfolios.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-sm text-gray-500 dark:text-slate-400">
                    Brak portfeli. Utwórz nowy, aby rozpocząć!
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
