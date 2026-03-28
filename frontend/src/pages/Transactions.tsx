import React, { useEffect, useState } from 'react';
import { portfolioApi } from '../api';
import { Transaction, Portfolio } from '../types';
import { cn } from '../lib/utils';

// Extend Transaction type to include portfolio_name for the list view
interface ExtendedTransaction extends Transaction {
  portfolio_name?: string;
}

const Transactions: React.FC = () => {
  const [transactions, setTransactions] = useState<ExtendedTransaction[]>([]);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterPortfolio, setFilterPortfolio] = useState<string>('all');
  const [filterSubPortfolio, setFilterSubPortfolio] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterTicker, setFilterTicker] = useState<string>('all');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [tRes, pRes] = await Promise.all([
          portfolioApi.listTransactions(),
          portfolioApi.list()
        ]);
        setTransactions(tRes.transactions);
        setPortfolios(pRes.portfolios);
      } catch (err) {
        console.error('Failed to fetch data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const uniqueTickers = Array.from(new Set(transactions.map(t => t.ticker).filter(t => t && t !== 'CASH'))).sort();
  
  const currentSubPortfolios = filterPortfolio !== 'all' 
    ? portfolios.filter(p => p.parent_portfolio_id === parseInt(filterPortfolio))
    : [];

  const filteredTransactions = transactions.filter(t => {
    if (filterPortfolio !== 'all' && t.portfolio_id !== parseInt(filterPortfolio)) return false;
    if (filterSubPortfolio !== 'all') {
        if (filterSubPortfolio === 'none') {
            if (t.sub_portfolio_id !== null && t.sub_portfolio_id !== undefined) return false;
        } else {
            if (t.sub_portfolio_id !== parseInt(filterSubPortfolio)) return false;
        }
    }
    if (filterType !== 'all' && t.type !== filterType) return false;
    if (filterTicker !== 'all' && t.ticker !== filterTicker) return false;
    return true;
  });

  if (loading) return <div className="p-4 text-center">Loading transactions...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Transaction History</h1>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg p-4 flex flex-col sm:flex-row flex-wrap gap-4">
        <div className="flex-1 min-w-[150px]">
          <label htmlFor="portfolio" className="block text-sm font-medium text-gray-700">Portfolio</label>
          <select
            id="portfolio"
            value={filterPortfolio}
            onChange={(e) => {
                setFilterPortfolio(e.target.value);
                setFilterSubPortfolio('all'); // Reset subportfolio when main portfolio changes
            }}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border"
          >
            <option value="all">All Portfolios</option>
            {portfolios.filter(p => !p.parent_portfolio_id).map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        {filterPortfolio !== 'all' && currentSubPortfolios.length > 0 && (
          <div className="flex-1 min-w-[150px]">
            <label htmlFor="subportfolio" className="block text-sm font-medium text-gray-700">Sub-portfolio</label>
            <select
              id="subportfolio"
              value={filterSubPortfolio}
              onChange={(e) => setFilterSubPortfolio(e.target.value)}
              className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border"
            >
              <option value="all">All Sub-portfolios</option>
              <option value="none">Main Portfolio Only</option>
              {currentSubPortfolios.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}

        <div className="flex-1 min-w-[150px]">
          <label htmlFor="type" className="block text-sm font-medium text-gray-700">Type</label>
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
          <label htmlFor="ticker" className="block text-sm font-medium text-gray-700">Ticker</label>
          <select
            id="ticker"
            value={filterTicker}
            onChange={(e) => setFilterTicker(e.target.value)}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md border"
          >
            <option value="all">All Tickers</option>
            {uniqueTickers.map(ticker => (
              <option key={ticker} value={ticker}>{ticker}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
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
              {filteredTransactions.map((t) => (
                <tr key={t.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(t.date).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {t.portfolio_name || portfolios.find(p => p.id === t.portfolio_id)?.name || t.portfolio_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {t.sub_portfolio_name || (t.sub_portfolio_id ? portfolios.find(p => p.id === t.sub_portfolio_id)?.name : '-') || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={cn(
                      "px-2 inline-flex text-xs leading-5 font-semibold rounded-full",
                      t.type === 'BUY' ? "bg-green-100 text-green-800" :
                      t.type === 'SELL' ? "bg-red-100 text-red-800" :
                      t.type === 'DEPOSIT' ? "bg-blue-100 text-blue-800" :
                      t.type === 'DIVIDEND' ? "bg-indigo-100 text-indigo-800" :
                      "bg-orange-100 text-orange-800"
                    )}>
                      {t.type}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {t.ticker === 'CASH' ? '-' : t.ticker}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                    {t.quantity}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                    {t.price.toFixed(2)} PLN
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-medium text-gray-900">
                    {t.total_value.toFixed(2)} PLN
                  </td>
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
