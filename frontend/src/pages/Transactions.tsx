import React, { useEffect, useMemo, useState } from 'react';
import { ArrowLeftRight } from 'lucide-react';
import { portfolioApi } from '../api';
import type { FlattenedPortfolio, Portfolio, Transaction } from '../types';
import { cn } from '../lib/utils';
import { flattenPortfolios } from '../utils/portfolioUtils';

interface ExtendedTransaction extends Transaction {
  portfolio_name?: string;
}

const ARCHIVED_LABEL = '(archiwalny)';
const typeLabels: Record<string, string> = {
  BUY: 'Kupno', SELL: 'Sprzedaż', DEPOSIT: 'Wpłata', WITHDRAW: 'Wypłata',
  DIVIDEND: 'Dywidenda', INTEREST: 'Odsetki',
};

const formatPortfolioOptionLabel = (portfolio: FlattenedPortfolio): string => {
  const archivedSuffix = portfolio.is_archived ? ` ${ARCHIVED_LABEL}` : '';

  if (portfolio.parent_name) {
    return `  └ ${portfolio.name} (${portfolio.parent_name})${archivedSuffix}`;
  }

  return `${portfolio.name}${archivedSuffix}`;
};

const Transactions: React.FC = () => {
  const [transactions, setTransactions] = useState<ExtendedTransaction[]>([]);
  const [portfolioTree, setPortfolioTree] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterPortfolio, setFilterPortfolio] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterTicker, setFilterTicker] = useState<string>('all');
  const [filterDateFrom, setFilterDateFrom] = useState<string>('');
  const [filterDateTo, setFilterDateTo] = useState<string>('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const params = {
          ...(filterType !== 'all' ? { type: filterType } : {}),
          ...(filterTicker !== 'all' ? { ticker: filterTicker } : {}),
          ...(filterDateFrom ? { date_from: filterDateFrom } : {}),
          ...(filterDateTo ? { date_to: filterDateTo } : {}),
        };
        const [tRes, pRes] = await Promise.all([portfolioApi.listTransactions(params), portfolioApi.list()]);
        setTransactions(tRes.transactions);
        setPortfolioTree(pRes.portfolios);
      } catch (err) {
        console.error('Failed to fetch data', err);
        alert(err instanceof Error ? err.message : 'Nie udało się pobrać transakcji');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [filterDateFrom, filterDateTo, filterTicker, filterType]);

  const flatPortfolios = useMemo(() => flattenPortfolios(portfolioTree), [portfolioTree]);

  const selectedPortfolio = useMemo(
    () => flatPortfolios.find((portfolio) => portfolio.id === Number(filterPortfolio)),
    [filterPortfolio, flatPortfolios]
  );

  const uniqueTickers = Array.from(new Set(transactions.map((t) => t.ticker).filter((t) => t && t !== 'CASH'))).sort();

  const filteredTransactions = transactions.filter((transaction) => {
    if (selectedPortfolio) {
      const isChild = Boolean(selectedPortfolio.parent_name);

      if (isChild) {
        if (transaction.sub_portfolio_id !== selectedPortfolio.id) return false;
      } else {
        if (transaction.portfolio_id !== selectedPortfolio.id) return false;
        if (transaction.sub_portfolio_id !== null && transaction.sub_portfolio_id !== undefined) return false;
      }
    }

    return true;
  });

  if (loading) return <div className="p-4 text-center">Ładowanie transakcji...</div>;

  return (
    <div className="space-y-6">
      <div className="page-heading">
        <p className="page-eyebrow">Inwestycje</p>
        <h1 className="text-2xl font-bold text-gray-900">Historia transakcji</h1>
        <p className="mt-1 text-sm text-gray-600">Przeglądaj operacje ze wszystkich portfeli w jednym miejscu.</p>
      </div>

      <div className="bg-white shadow rounded-lg p-4 flex flex-col sm:flex-row flex-wrap gap-4">
        <div className="flex-1 min-w-[220px]">
          <label htmlFor="portfolio" className="block text-sm font-medium text-gray-700">
            Portfel lub subportfel
          </label>
          <select
            id="portfolio"
            value={filterPortfolio}
            onChange={(e) => setFilterPortfolio(e.target.value)}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border"
          >
            <option value="all">Wszystkie portfele</option>
            {flatPortfolios.map((portfolio) => (
              <option key={portfolio.id} value={portfolio.id}>
                {formatPortfolioOptionLabel(portfolio)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 min-w-[150px]">
          <label htmlFor="type" className="block text-sm font-medium text-gray-700">
            Typ
          </label>
          <select
            id="type"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border"
          >
            <option value="all">Wszystkie typy</option>
            <option value="BUY">Kupno</option>
            <option value="SELL">Sprzedaż</option>
            <option value="DEPOSIT">Wpłata</option>
            <option value="WITHDRAW">Wypłata</option>
            <option value="DIVIDEND">Dywidenda</option>
            <option value="INTEREST">Odsetki</option>
          </select>
        </div>
        <div className="flex-1 min-w-[150px]">
          <label htmlFor="ticker" className="block text-sm font-medium text-gray-700">
            Symbol
          </label>
          <select
            id="ticker"
            value={filterTicker}
            onChange={(e) => setFilterTicker(e.target.value)}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border"
          >
            <option value="all">Wszystkie symbole</option>
            {uniqueTickers.map((ticker) => (
              <option key={ticker} value={ticker}>
                {ticker}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1 min-w-[170px]">
          <label htmlFor="dateFrom" className="block text-sm font-medium text-gray-700">
            Data od
          </label>
          <input
            id="dateFrom"
            type="date"
            value={filterDateFrom}
            onChange={(e) => setFilterDateFrom(e.target.value)}
            className="mt-1 block w-full py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border px-3"
          />
        </div>
        <div className="flex-1 min-w-[170px]">
          <label htmlFor="dateTo" className="block text-sm font-medium text-gray-700">
            Data do
          </label>
          <input
            id="dateTo"
            type="date"
            value={filterDateTo}
            onChange={(e) => setFilterDateTo(e.target.value)}
            className="mt-1 block w-full py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border px-3"
          />
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 shadow-sm border border-gray-200 dark:border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-800">
            <thead className="bg-gray-50/80 dark:bg-gray-900/80 backdrop-blur-sm">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Data</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Portfel</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Subportfel</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Typ</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Symbol</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Ilość</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Cena</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Wartość</th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-950 divide-y divide-gray-100 dark:divide-gray-800/50">
              {filteredTransactions.map((transaction) => (
                <tr key={transaction.id} className="transition-colors hover:bg-gray-50 dark:hover:bg-gray-900/50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400 tabular-nums">
                    {new Date(transaction.date).toLocaleDateString('pl-PL')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-gray-100">
                    {transaction.portfolio_name ||
                      flatPortfolios.find((portfolio) => portfolio.id === transaction.portfolio_id)?.name ||
                      transaction.portfolio_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {transaction.sub_portfolio_name ||
                      (transaction.sub_portfolio_id
                        ? flatPortfolios.find((portfolio) => portfolio.id === transaction.sub_portfolio_id)?.name
                        : '-') ||
                      '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'px-2.5 py-0.5 inline-flex text-[11px] leading-5 font-bold uppercase rounded-full border',
                          transaction.type === 'BUY' ? 'bg-green-50 text-green-700 border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800/50' :
                          transaction.type === 'SELL' ? 'bg-red-50 text-red-700 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800/50' :
                          transaction.type === 'DEPOSIT' ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800/50' :
                          transaction.type === 'DIVIDEND' ? 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-900/20 dark:text-indigo-400 dark:border-indigo-800/50' :
                          transaction.type === 'INTEREST' ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400 dark:border-emerald-800/50' :
                          'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-900/20 dark:text-orange-400 dark:border-orange-800/50'
                        )}
                      >
                        {typeLabels[transaction.type] ?? transaction.type}
                      </span>
                      {transaction.transfer_id && (
                        <span title="Przelew wewnętrzny" className="text-gray-400 dark:text-gray-500">
                          <ArrowLeftRight className="h-4 w-4" />
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-gray-100 tabular-nums">{transaction.ticker === 'CASH' ? '-' : transaction.ticker}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-700 dark:text-gray-300 tabular-nums">{parseFloat(Number(transaction.quantity).toFixed(4))}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500 dark:text-gray-400 tabular-nums">{transaction.price.toFixed(2)} PLN</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold text-gray-900 dark:text-gray-100 tabular-nums">{transaction.total_value.toFixed(2)} PLN</td>
                </tr>
              ))}
              {filteredTransactions.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-6 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                    Nie znaleziono transakcji dla wybranych filtrów.
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

export default Transactions;
