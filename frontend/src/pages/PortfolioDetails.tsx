import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, TrendingUp, ArrowDownRight, DollarSign, PieChart } from 'lucide-react';
import api from '../api';
import { Portfolio, Holding, Transaction, PortfolioValue, Bond, ClosedPosition } from '../types';
import PortfolioChart from '../components/PortfolioChart';
import PriceHistoryChart from '../components/PriceHistoryChart';
import DividendBarChart from '../components/DividendBarChart';
import PortfolioHistoryChart from '../components/PortfolioHistoryChart';
import { cn } from '../lib/utils';

function ImportXtbCsvButton({ portfolioId, onSuccess }: { portfolioId: number, onSuccess: () => void }) {
  const fileInput = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append('file', file);
    try {
      // Poprawiony endpoint — NIE powiela /portfolio
      await api.post(`/${portfolioId}/import/xtb`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert('Import successful!');
      onSuccess();
    } catch (err: any) {
      alert('Import failed: ' + (err.response?.data?.error || err.message));
    }
  };

  return (
    <>
      <button
        className="px-4 py-2 bg-blue-600 text-white rounded mb-4"
        onClick={() => fileInput.current?.click()}
      >
        Import XTB CSV
      </button>
      <input
        type="file"
        accept=".csv"
        ref={fileInput}
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
    </>
  );
}

const PortfolioDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [bonds, setBonds] = useState<Bond[]>([]);
  const [valueData, setValueData] = useState<PortfolioValue & { live_interest?: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'holdings' | 'value_history' | 'history' | 'buy' | 'sell' | 'deposit' | 'withdraw' | 'dividend' | 'bonds' | 'savings' | 'closed'>('holdings');
  
  // History state
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<{ date: string; close_price: number }[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [portfolioTransactions, setPortfolioTransactions] = useState<Transaction[]>([]);

  // Monthly Dividend state
  const [monthlyDividends, setMonthlyDividends] = useState<{ label: string; amount: number }[]>([]);
  
  // Portfolio History (Monthly)
  const [portfolioHistory, setPortfolioHistory] = useState<{ date: string; label: string; value: number }[]>([]);

  // Closed Positions
  const [closedPositions, setClosedPositions] = useState<ClosedPosition[]>([]);
  const [totalClosedProfit, setTotalClosedProfit] = useState(0);

  // Form states
  const [ticker, setTicker] = useState('');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [interestRate, setInterestRate] = useState('');
  const [bondName, setBondName] = useState('');

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
      const [pRes, hRes, vRes, mRes, tRes, cRes] = await Promise.all([
        api.get(`/list`), 
        api.get(`/holdings/${id}`),
        api.get(`/value/${id}`),
        api.get(`/dividends/monthly/${id}`),
        api.get(`/transactions/${id}`),
        api.get(`/${id}/closed-positions`)
      ]);
      
      const found = pRes.data.portfolios.find((p: Portfolio) => p.id === parseInt(id));
      setPortfolio(found || null);
      setHoldings(hRes.data.holdings);
      setValueData(vRes.data);
      setMonthlyDividends(mRes.data.monthly_dividends);
      setPortfolioTransactions(tRes.data.transactions);
      setClosedPositions(cRes.data.positions);
      setTotalClosedProfit(cRes.data.total_historical_profit);

      if (found?.account_type === 'BONDS') {
        const bRes = await api.get(`/bonds/${id}`);
        setBonds(bRes.data.bonds);
      }
      
      if (found?.account_type === 'SAVINGS') {
        const histRes = await api.get(`/history/monthly/${id}`);
        setPortfolioHistory(histRes.data.history);
      }
      
      // Default tab based on account type
      if (found?.account_type === 'BONDS') setActiveTab('bonds');
      else if (found?.account_type === 'SAVINGS') setActiveTab('savings');
      else {
        // Fetch history for standard portfolios too
        const histRes = await api.get(`/history/monthly/${id}`);
        setPortfolioHistory(histRes.data.history);
        setActiveTab('holdings');
      }

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
    // Fetch history separately when tab changes or initially
    if (activeTab === 'value_history' && id) {
      api.get(`/history/monthly/${id}`).then(res => {
        setPortfolioHistory(res.data.history);
      });
    }
  }, [activeTab, id]);

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
        payload = { ...payload, amount: parseFloat(amount), date };
      } else if (activeTab === 'withdraw') {
        endpoint = '/withdraw';
        payload = { ...payload, amount: parseFloat(amount), date };
      } else if (activeTab === 'dividend') {
        endpoint = '/dividend';
        payload = { ...payload, ticker, amount: parseFloat(amount), date };
      } else if (activeTab === 'bonds') {
        endpoint = '/bonds';
        payload = { ...payload, name: bondName, principal: parseFloat(amount), interest_rate: parseFloat(interestRate), purchase_date: date };
      } else if (activeTab === 'savings') {
        if (interestRate) {
           endpoint = '/savings/rate';
           payload = { ...payload, rate: parseFloat(interestRate) };
        } else {
           endpoint = '/savings/interest/manual';
           payload = { ...payload, amount: parseFloat(amount), date: date };
        }
      } else if (activeTab === 'closed') {
        endpoint = '/closed-positions';
        payload = { ...payload, portfolio_id: parseInt(id) };
      }

      await api.post(endpoint, payload);
      
      // Reset forms
      setTicker('');
      setQuantity('');
      setPrice('');
      setAmount('');
      setBondName('');
      setInterestRate('');
      setDate(new Date().toISOString().split('T')[0]);
      
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
      {/* Import XTB CSV button */}
      {portfolio && (
        <ImportXtbCsvButton portfolioId={portfolio.id} onSuccess={fetchData} />
      )}
      <div className="flex items-center space-x-4">
        <Link to="/portfolios" className="text-gray-500 hover:text-gray-700">
          <ArrowLeft className="h-6 w-6" />
        </Link>
        <div className="flex items-center space-x-2">
          <h1 className="text-2xl font-bold text-gray-900">{portfolio.name}</h1>
          <span className={cn(
            "text-xs uppercase tracking-wider font-bold px-2 py-1 rounded-full",
            portfolio.account_type === 'SAVINGS' ? "bg-emerald-100 text-emerald-800" :
            portfolio.account_type === 'BONDS' ? "bg-amber-100 text-amber-800" :
            portfolio.account_type === 'IKE' ? "bg-indigo-100 text-indigo-800" :
            "bg-gray-100 text-gray-800"
          )}>
            {portfolio.account_type}
          </span>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-5">
        <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-blue-500">
          <dt className="text-sm font-medium text-gray-500 truncate">Total Value</dt>
          <dd className="mt-1 text-2xl font-semibold text-gray-900">{valueData.portfolio_value.toFixed(2)} PLN</dd>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-gray-400">
          <dt className="text-sm font-medium text-gray-500 truncate">
            {portfolio.account_type === 'SAVINGS' ? 'Current Balance' : 'Cash Balance'}
          </dt>
          <dd className="mt-1 text-2xl font-semibold text-gray-900">{valueData.cash_value.toFixed(2)} PLN</dd>
          {portfolio.account_type === 'SAVINGS' && valueData.live_interest && valueData.live_interest > 0 ? (
            <dd className="text-xs text-emerald-600 font-medium">Incl. {valueData.live_interest.toFixed(2)} PLN live interest</dd>
          ) : null}
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-green-500">
          <dt className="text-sm font-medium text-gray-500 truncate">Total Profit/Loss</dt>
          <dd className={cn("mt-1 text-2xl font-semibold", valueData.total_result >= 0 ? "text-green-600" : "text-red-600")}>
            {valueData.total_result.toFixed(2)} PLN
          </dd>
          <dd className={cn("text-sm font-medium", valueData.total_result >= 0 ? "text-green-600" : "text-red-600")}>
            {valueData.total_result_percent.toFixed(2)}%
          </dd>
        </div>
        {portfolio.account_type !== 'SAVINGS' && portfolio.account_type !== 'BONDS' ? (
          <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-indigo-500">
            <dt className="text-sm font-medium text-gray-500 truncate">Total Dividends</dt>
            <dd className="mt-1 text-2xl font-semibold text-blue-600">
              {valueData.total_dividends.toFixed(2)} PLN
            </dd>
          </div>
        ) : (
          <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-indigo-500">
            <dt className="text-sm font-medium text-gray-500 truncate">
              {portfolio.account_type === 'SAVINGS' ? 'Interest Rate' : 'Principal'}
            </dt>
            <dd className="mt-1 text-2xl font-semibold text-indigo-600">
              {portfolio.account_type === 'SAVINGS' ? `${portfolio.savings_rate}%` : `${(valueData.holdings_value || 0).toFixed(2)} PLN`}
            </dd>
          </div>
        )}
        <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-amber-500">
            <dt className="text-sm font-medium text-gray-500 truncate">Allocation</dt>
            <div className="h-24">
                 <PortfolioChart holdings={holdings} cash={valueData.cash_value} />
            </div>
        </div>
      </div>

      {/* Action Tabs */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex overflow-x-auto">
            {(portfolio.account_type === 'SAVINGS' 
                ? ['savings', 'history', 'deposit', 'withdraw'] 
                : portfolio.account_type === 'BONDS'
                  ? ['bonds', 'history', 'deposit', 'withdraw']
                  : ['holdings', 'value_history', 'history', 'buy', 'sell', 'deposit', 'withdraw', 'dividend', 'bonds', 'savings', 'closed']
            ).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={cn(
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                  'flex-1 min-w-fit py-4 px-4 text-center border-b-2 font-medium text-sm capitalize whitespace-nowrap'
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
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                          {parseFloat(Number(h.quantity).toFixed(4))}
                        </td>
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

          {activeTab === 'value_history' && (
            <div className="space-y-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Portfolio Value History</h3>
              {portfolioHistory.length > 0 ? (
                <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                  <PortfolioHistoryChart data={portfolioHistory} />
                </div>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-500">
                  Not enough data to display history.
                </div>
              )}
            </div>
          )}

          {activeTab === 'history' && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ticker</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Quantity</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Total Value</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Realized Profit</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {portfolioTransactions.map((t) => (
                    <tr key={t.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(t.date).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={cn(
                          "px-2 inline-flex text-xs leading-5 font-semibold rounded-full",
                          t.type === 'BUY' ? "bg-green-100 text-green-800" :
                          t.type === 'SELL' ? "bg-red-100 text-red-800" :
                          t.type === 'DEPOSIT' ? "bg-blue-100 text-blue-800" :
                          t.type === 'DIVIDEND' ? "bg-indigo-100 text-indigo-800" :
                          t.type === 'INTEREST' ? "bg-emerald-100 text-emerald-800" :
                          "bg-orange-100 text-orange-800"
                        )}>
                          {t.type}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {t.ticker === 'CASH' ? '-' : t.ticker}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                        {parseFloat(Number(t.quantity).toFixed(4))}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                        {t.price.toFixed(2)} PLN
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-medium text-gray-900">
                        {t.total_value.toFixed(2)} PLN
                      </td>
                      <td className={cn("px-6 py-4 whitespace-nowrap text-sm text-right font-medium", t.realized_profit >= 0 ? "text-green-600" : "text-red-600")}>{typeof t.realized_profit === 'number' ? t.realized_profit.toFixed(2) + ' PLN' : '-'}</td>
                    </tr>
                  ))}
                  {portfolioTransactions.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">No transactions yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'bonds' && (
            <div className="space-y-8">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Bond Name</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Purchase Date</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Principal</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Interest Rate</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Accrued</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Total Value</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {bonds.map((b) => (
                      <tr key={b.id}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{b.name}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{b.purchase_date}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{b.principal.toFixed(2)} PLN</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">{b.interest_rate}%</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-emerald-600 font-medium">+{b.accrued_interest.toFixed(2)} PLN</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-bold text-gray-900">{b.total_value.toFixed(2)} PLN</td>
                      </tr>
                    ))}
                    {bonds.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-6 py-4 text-center text-sm text-gray-500">No bonds added yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg border border-gray-200 max-w-lg mx-auto">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Add New Bond</h3>
                <form onSubmit={handleTransaction} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Bond Name</label>
                    <input
                      type="text"
                      value={bondName}
                      onChange={(e) => setBondName(e.target.value)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                      placeholder="e.g. EDO0234"
                      required
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Principal (PLN)</label>
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
                      <label className="block text-sm font-medium text-gray-700">Interest Rate (%)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={interestRate}
                        onChange={(e) => setInterestRate(e.target.value)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                        required
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Purchase Date</label>
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
                    className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 focus:outline-none"
                  >
                    Add Bond
                  </button>
                </form>
              </div>
            </div>
          )}

          {activeTab === 'savings' && (
            <div className="space-y-8">
              <div className="bg-emerald-50 p-8 rounded-2xl border border-emerald-100 text-center max-w-2xl mx-auto shadow-sm">
                <p className="text-emerald-600 font-semibold uppercase tracking-widest text-sm mb-2">Total Savings Balance</p>
                <h2 className="text-5xl font-bold text-emerald-900 mb-4">
                  {valueData.portfolio_value.toFixed(2)} <span className="text-2xl font-normal text-emerald-700">PLN</span>
                </h2>
                <div className="flex justify-center items-center space-x-6 text-emerald-700">
                   <div className="flex flex-col">
                      <span className="text-xs uppercase font-medium">Interest Rate</span>
                      <span className="text-lg font-bold">{portfolio.savings_rate}%</span>
                   </div>
                   <div className="w-px h-8 bg-emerald-200"></div>
                   <div className="flex flex-col">
                      <span className="text-xs uppercase font-medium">Accrued Interest</span>
                      <span className="text-lg font-bold">+{valueData.live_interest?.toFixed(2)} PLN</span>
                   </div>
                </div>
              </div>

              <div className="bg-white p-6 rounded-lg border border-gray-200 max-w-lg mx-auto shadow-sm">
                <h3 className="text-lg font-medium text-gray-900 mb-4 text-center">Update Interest Rate</h3>
                <form onSubmit={handleTransaction} className="space-y-4">
                  <div>
                    <input
                      type="number"
                      step="0.01"
                      value={interestRate}
                      onChange={(e) => setInterestRate(e.target.value)}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500 p-2 border"
                      placeholder="New rate %"
                      required
                    />
                  </div>
                  <button
                    type="submit"
                    className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 focus:outline-none"
                  >
                    Update
                  </button>
                </form>
                <p className="mt-2 text-xs text-gray-500 italic text-center">Changing the rate will automatically capitalize your current interest.</p>
              </div>

              <div className="bg-white p-6 rounded-lg border border-gray-200 max-w-lg mx-auto shadow-sm">
                <h3 className="text-lg font-medium text-gray-900 mb-4 text-center">Add Manual Interest</h3>
                <form onSubmit={handleTransaction} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Amount (PLN)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500 p-2 border"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Date Received</label>
                    <input
                      type="date"
                      value={date}
                      onChange={(e) => setDate(e.target.value)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500 p-2 border"
                      required
                    />
                  </div>
                  <button
                    type="submit"
                    className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 focus:outline-none"
                  >
                    Add Interest
                  </button>
                </form>
              </div>

              {/* Monthly History Chart */}
              {portfolioHistory.length > 0 && (
                <div className="mt-8 border-t pt-8">
                  <h3 className="text-lg font-medium text-gray-900 mb-6 text-center">Balance History</h3>
                  <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                     <PortfolioHistoryChart data={portfolioHistory} />
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'closed' && (
            <div className="space-y-6">
              <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mb-6">
                <h3 className="text-lg font-medium text-gray-900">Total Realized Profit</h3>
                <p className={cn("text-3xl font-bold mt-2", totalClosedProfit >= 0 ? "text-green-600" : "text-red-600")}>
                  {totalClosedProfit.toFixed(2)} PLN
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ticker</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Realized Profit</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {closedPositions.map((p) => (
                      <tr key={p.ticker}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{p.ticker}</td>
                        <td className={cn(
                          "px-6 py-4 whitespace-nowrap text-sm text-right font-medium",
                          p.realized_profit >= 0 ? "text-green-600" : "text-red-600"
                        )}>
                          {p.realized_profit.toFixed(2)} PLN
                        </td>
                      </tr>
                    ))}
                    {closedPositions.length === 0 && (
                      <tr>
                        <td colSpan={2} className="px-6 py-4 text-center text-sm text-gray-500">No closed positions yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
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
