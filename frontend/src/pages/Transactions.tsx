import React, { useEffect, useMemo, useState } from 'react';
import { portfolioApi } from '../api';
import type { FlattenedPortfolio, Portfolio, Transaction } from '../types';
import { cn } from '../lib/utils';
import { flattenPortfolios } from '../utils/portfolioUtils';

interface ExtendedTransaction extends Transaction {
  portfolio_name?: string;
}

const ARCHIVED_LABEL = '(archiwalny)';

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

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [tRes, pRes] = await Promise.all([portfolioApi.listTransactions(), portfolioApi.list()]);
        setTransactions(tRes.transactions);
        setPortfolioTree(pRes.portfolios);
      } catch (err) {
        console.error('Failed to fetch data', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

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

    if (filterType !== 'all' && transaction.type !== filterType) return false;
    if (filterTicker !== 'all' && transaction.ticker !== filterTicker) return false;
    return true;
  });

  if (loading) return <div className="p-4 text-center">Loading transactions...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Transaction History</h1>

      <div className="bg-white shadow rounded-lg p-4 flex flex-col sm:flex-row flex-wrap gap-4">
        <div className="flex-1 min-w-[220px]">
          <label htmlFor="portfolio" className="block text-sm font-medium text-gray-700">
            Portfolio / Sub-portfolio
          </label>
          <select
            id="portfolio"
            value={filterPortfolio}
            onChange={(e) => setFilterPortfolio(e.target.value)}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border"
          >
            <option value="all">All Portfolios</option>
            {flatPortfolios.map((portfolio) => (
              <option key={portfolio.id} value={portfolio.id}>
                {formatPortfolioOptionLabel(portfolio)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 min-w-[150px]">
          <label htmlFor="type" className="block text-sm font-medium text-gray-700">
            Type
          </label>
          <select
            id="type"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border"
          >
            <option value="all">All Types</option>
            <option value="BUY">Buy</option>
            <option value="SELL">Sell</option>
            <option value="DEPOSIT">Deposit</option>
            <option value="WITHDRAW">Withdraw</option>
            <option value="DIVIDEND">Dividend</option>
            <option value="INTEREST">Interest</option>
          </select>
        </div>
        <div className="flex-1 min-w-[150px]">
          <label htmlFor="ticker" className="block text-sm font-medium text-gray-700">
            Ticker
          </label>
          <select
            id="ticker"
            value={filterTicker}
            onChange={(e) => setFilterTicker(e.target.value)}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border"
          >
            <option value="all">All Tickers</option>
            {uniqueTickers.map((ticker) => (
              <option key={ticker} value={ticker}>
                {ticker}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Portfolio</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sub-portfolio</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ticker</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Total Value</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredTransactions.map((transaction) => (
                <tr key={transaction.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(transaction.date).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {transaction.portfolio_name ||
                      flatPortfolios.find((portfolio) => portfolio.id === transaction.portfolio_id)?.name ||
                      transaction.portfolio_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {transaction.sub_portfolio_name ||
                      (transaction.sub_portfolio_id
                        ? flatPortfolios.find((portfolio) => portfolio.id === transaction.sub_portfolio_id)?.name
                        : '-') ||
                      '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span
                      className={cn(
                        'px-2 inline-flex text-xs leading-5 font-semibold rounded-full',
                        transaction.type === 'BUY'
                          ? 'bg-green-100 text-green-800'
                          : transaction.type === 'SELL'
                            ? 'bg-red-100 text-red-800'
                            : transaction.type === 'DEPOSIT'
                              ? 'bg-blue-100 text-blue-800'
                              : transaction.type === 'DIVIDEND'
                                ? 'bg-indigo-100 text-indigo-800'
                                : 'bg-orange-100 text-orange-800'
                      )}
                    >
                      {transaction.type}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{transaction.ticker === 'CASH' ? '-' : transaction.ticker}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{transaction.quantity}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{transaction.price.toFixed(2)} PLN</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-medium text-gray-900">{transaction.total_value.toFixed(2)} PLN</td>
                </tr>
              ))}
              {filteredTransactions.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-6 py-4 text-center text-sm text-gray-500">
                    No transactions found.
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
