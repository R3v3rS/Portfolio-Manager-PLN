import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, ArrowDownRight, DollarSign, PieChart } from 'lucide-react';
import api from '../api';
import { Portfolio, Holding, Transaction, PortfolioValue } from '../types';
import PortfolioChart from '../components/PortfolioChart';
import PriceHistoryChart from '../components/PriceHistoryChart';
import DividendBarChart from '../components/DividendBarChart';
import { cn } from '../lib/utils';

const PortfolioDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [valueData, setValueData] = useState<PortfolioValue | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'holdings' | 'buy' | 'sell' | 'deposit' | 'withdraw' | 'dividend'>('holdings');
  
  // History state
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<{ date: string; close_price: number }[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Monthly Dividend state
  const [monthlyDividends, setMonthlyDividends] = useState<{ label: string; amount: number }[]>([]);

  // Form states
  const [ticker, setTicker] = useState('');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);

  const initiateSell = (h: Holding) => {
    setActiveTab('sell');
    setTicker(h.ticker);
    setQuantity(h.quantity.toString());
    setPrice((h.current_price || h.average_buy_price).toString());
  };

  const fetchData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [pRes, hRes, vRes, mRes] = await Promise.all([
        api.get(`/list`), 
        api.get(`/holdings/${id}`),
        api.get(`/value/${id}`),
        api.get(`/dividends/monthly/${id}`)
      ]);
      
      const found = pRes.data.portfolios.find((p: Portfolio) => p.id === parseInt(id));
      setPortfolio(found || null);
      setHoldings(hRes.data.holdings);
      setValueData(vRes.data);
      setMonthlyDividends(mRes.data.monthly_dividends);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async (ticker: string) => {
    setHistoryLoading(true);
    setSelectedTicker(ticker);
    try {
      const response = await api.get(`/history/${ticker}`);
      setHistoryData(response.data.history);
      setLastUpdated(response.data.last_updated);
    } catch (err) {
      console.error('Failed to fetch history', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;

    try {
      let endpoint = '';
      let payload: any = { portfolio_id: parseInt(id) };

      if (activeTab === 'buy') {
        endpoint = '/buy';
        payload = { ...payload, ticker, quantity: parseFloat(quantity), price: parseFloat(price), date };
      } else if (activeTab === 'sell') {
        endpoint = '/sell';
        payload = { ...payload, ticker, quantity: parseFloat(quantity), price: parseFloat(price) };
      } else if (activeTab === 'deposit') {
        endpoint = '/deposit';
        payload = { ...payload, amount: parseFloat(amount) };
      } else if (activeTab === 'withdraw') {
        endpoint = '/withdraw';
        payload = { ...payload, amount: parseFloat(amount) };
      } else if (activeTab === 'dividend') {
        endpoint = '/dividend';
        payload = { ...payload, ticker, amount: parseFloat(amount), date };
      }

      await api.post(endpoint, payload);
      
      // Reset forms
      setTicker('');
      setQuantity('');
      setPrice('');
      setAmount('');
      setDate(new Date().toISOString().split('T')[0]);
      setActiveTab('holdings');
      
      // Refresh data
      fetchData();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.error || 'Transaction failed');
    }
  };

  if (loading) return <div className="p-4 text-center">Loading details...</div>;
  if (!portfolio || !valueData) return <div className="p-4 text-center">Portfolio not found</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-4">
        <Link to="/portfolios" className="text-gray-500 hover:text-gray-700">
          <ArrowLeft className="h-6 w-6" />
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">{portfolio.name}</h1>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-5">
        <div className="bg-white overflow-hidden shadow rounded-lg p-5">
          <dt className="text-sm font-medium text-gray-500 truncate">Total Value</dt>
          <dd className="mt-1 text-2xl font-semibold text-gray-900">{valueData.portfolio_value.toFixed(2)} PLN</dd>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5">
          <dt className="text-sm font-medium text-gray-500 truncate">Cash Balance</dt>
          <dd className="mt-1 text-2xl font-semibold text-gray-900">{valueData.cash_value.toFixed(2)} PLN</dd>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5">
          <dt className="text-sm font-medium text-gray-500 truncate">Total Profit/Loss</dt>
          <dd className={cn("mt-1 text-2xl font-semibold", valueData.total_result >= 0 ? "text-green-600" : "text-red-600")}>
            {valueData.total_result.toFixed(2)} PLN
          </dd>
          <dd className={cn("text-sm font-medium", valueData.total_result >= 0 ? "text-green-600" : "text-red-600")}>
            {valueData.total_result_percent.toFixed(2)}%
          </dd>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5">
          <dt className="text-sm font-medium text-gray-500 truncate">Total Dividends</dt>
          <dd className="mt-1 text-2xl font-semibold text-blue-600">
            {valueData.total_dividends.toFixed(2)} PLN
          </dd>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5">
            <dt className="text-sm font-medium text-gray-500 truncate">Allocation</dt>
            <div className="h-24">
                 <PortfolioChart holdings={holdings} cash={valueData.cash_value} />
            </div>
        </div>
      </div>

      {/* Action Tabs */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex">
            {['holdings', 'buy', 'sell', 'deposit', 'withdraw', 'dividend'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={cn(
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                  'w-1/6 py-4 px-1 text-center border-b-2 font-medium text-sm capitalize'
                )}
              >
                {tab}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'holdings' && (
            <div className="space-y-6">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ticker</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Avg Price</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Current Price</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">P/L</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Weight</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {holdings.map((h) => (
                      <tr 
                        key={h.ticker} 
                        className={cn("cursor-pointer hover:bg-gray-50", selectedTicker === h.ticker && "bg-blue-50")}
                        onClick={() => fetchHistory(h.ticker)}
                      >
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{h.ticker}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{h.quantity}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{h.average_buy_price.toFixed(2)} PLN</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                          {h.current_price ? `${h.current_price.toFixed(2)} PLN` : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                          {h.current_value ? `${h.current_value.toFixed(2)} PLN` : '-'}
                        </td>
                        <td className={cn(
                          "px-6 py-4 whitespace-nowrap text-sm text-right font-medium",
                          (h.profit_loss || 0) >= 0 ? "text-green-600" : "text-red-600"
                        )}>
                          {h.profit_loss ? `${h.profit_loss.toFixed(2)} PLN` : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500 font-medium">
                          {h.weight_percent ? `${h.weight_percent}%` : '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-medium">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              initiateSell(h);
                            }}
                            className="text-red-600 hover:text-red-900 bg-red-50 px-3 py-1 rounded-md transition-colors"
                          >
                            Sell
                          </button>
                        </td>
                      </tr>
                    ))}
                    {holdings.length === 0 && (
                      <tr>
                        <td colSpan={8} className="px-6 py-4 text-center text-sm text-gray-500">No holdings yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* History Chart Section */}
              {selectedTicker && (
                <div className="mt-8 border-t pt-8">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-medium text-gray-900">Performance History: {selectedTicker}</h3>
                    {lastUpdated && (
                      <span className="text-xs text-gray-500">Last Synced: {lastUpdated}</span>
                    )}
                  </div>
                  <div className="bg-gray-50 p-4 rounded-lg">
                    {historyLoading ? (
                      <div className="h-64 flex items-center justify-center">Loading history...</div>
                    ) : historyData.length > 0 ? (
                      <PriceHistoryChart ticker={selectedTicker} data={historyData} />
                    ) : (
                      <div className="h-64 flex items-center justify-center text-gray-500">No historical data available.</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {(activeTab === 'buy' || activeTab === 'sell') && (
            <form onSubmit={handleTransaction} className="max-w-lg mx-auto space-y-4">
              <h3 className="text-lg font-medium text-gray-900 capitalize">{activeTab} Stock</h3>
              <div>
                <label className="block text-sm font-medium text-gray-700">Ticker Symbol</label>
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Quantity</label>
                <input
                  type="number"
                  step="any"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Price per Share (PLN)</label>
                <input
                  type="number"
                  step="0.01"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Date</label>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  required
                />
              </div>
              <button
                type="submit"
                className={cn(
                  "w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2",
                  activeTab === 'buy' ? "bg-green-600 hover:bg-green-700 focus:ring-green-500" : "bg-red-600 hover:bg-red-700 focus:ring-red-500"
                )}
              >
                {activeTab === 'buy' ? 'Buy Stock' : 'Sell Stock'}
              </button>
            </form>
          )}

          {(activeTab === 'deposit' || activeTab === 'withdraw') && (
            <form onSubmit={handleTransaction} className="max-w-lg mx-auto space-y-4">
              <h3 className="text-lg font-medium text-gray-900 capitalize">{activeTab} Cash</h3>
              <div>
                <label className="block text-sm font-medium text-gray-700">Amount (PLN)</label>
                <input
                  type="number"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  required
                />
              </div>
              <button
                type="submit"
                className={cn(
                  "w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2",
                  activeTab === 'deposit' ? "bg-blue-600 hover:bg-blue-700 focus:ring-blue-500" : "bg-orange-600 hover:bg-orange-700 focus:ring-orange-500"
                )}
              >
                {activeTab === 'deposit' ? 'Deposit Funds' : 'Withdraw Funds'}
              </button>
            </form>
          )}

          {activeTab === 'dividend' && (
            <>
              <form onSubmit={handleTransaction} className="max-w-lg mx-auto space-y-4">
                <h3 className="text-lg font-medium text-gray-900 capitalize">Record Dividend</h3>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Ticker Symbol</label>
                  <select
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value)}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                    required
                  >
                    <option value="">Select a stock</option>
                    {holdings.map(h => (
                      <option key={h.ticker} value={h.ticker}>{h.ticker}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Dividend Amount (Total PLN)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Date Received</label>
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                    required
                  />
                </div>
                <button
                  type="submit"
                  className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Record Dividend
                </button>
              </form>

              {/* Monthly Dividend Chart */}
              <div className="mt-12 border-t pt-8">
                <h3 className="text-lg font-medium text-gray-900 mb-6">Monthly Dividend Income</h3>
                <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                  {monthlyDividends.length > 0 ? (
                    <DividendBarChart data={monthlyDividends} />
                  ) : (
                    <div className="h-64 flex items-center justify-center text-gray-500 italic">
                      No dividends recorded yet.
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default PortfolioDetails;
