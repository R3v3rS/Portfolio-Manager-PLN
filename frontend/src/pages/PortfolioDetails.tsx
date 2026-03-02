import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Plus, RefreshCw, HelpCircle } from 'lucide-react';
import api from '../api';
import { budgetApi, BudgetAccount } from '../api_budget';
import { Portfolio, Holding, Transaction, PortfolioValue, Bond, ClosedPosition } from '../types';
import PortfolioChart from '../components/PortfolioChart';
import PortfolioAnalytics from '../components/PortfolioAnalytics';
import PriceHistoryChart from '../components/PriceHistoryChart';
import DividendBarChart from '../components/DividendBarChart';
import PortfolioHistoryChart from '../components/PortfolioHistoryChart';
import PortfolioProfitChart from '../components/PortfolioProfitChart';
import PerformanceHeatmap from '../components/portfolio/PerformanceHeatmap';
import TransferModal from '../components/modals/TransferModal';
import TransactionModal from '../components/modals/TransactionModal';
import SellModal from '../components/modals/SellModal';
import { cn } from '../lib/utils';
import { PPKSummary, PPKTransaction as PPKTx } from '../services/ppkCalculator';

function ImportXtbCsvButton({ portfolioId, onSuccess }: { portfolioId: number, onSuccess: () => void }) {
  const fileInput = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append('file', file);
    try {
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


function PPKContributionForm({ portfolioId, onSuccess }: { portfolioId: number; onSuccess: () => void }) {
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [employeeUnits, setEmployeeUnits] = useState('');
  const [employerUnits, setEmployerUnits] = useState('');
  const [price, setPrice] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post('/ppk/transactions', {
      portfolio_id: portfolioId,
      date,
      employeeUnits: parseFloat(employeeUnits),
      employerUnits: parseFloat(employerUnits),
      pricePerUnit: parseFloat(price),
    });
    setEmployeeUnits('');
    setEmployerUnits('');
    setPrice('');
    onSuccess();
  };

  return (
    <form onSubmit={submit} className="bg-white border border-purple-100 rounded-lg p-4 space-y-3">
      <button type="submit" className="px-3 py-2 text-sm bg-purple-600 text-white rounded">+ Add Monthly Contribution</button>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="p-2 border rounded" required />
        <input type="number" step="0.0001" value={employeeUnits} onChange={(e) => setEmployeeUnits(e.target.value)} placeholder="Employee units" className="p-2 border rounded" required />
        <input type="number" step="0.0001" value={employerUnits} onChange={(e) => setEmployerUnits(e.target.value)} placeholder="Employer units" className="p-2 border rounded" required />
        <input type="number" step="0.0001" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="Price per unit" className="p-2 border rounded" required />
      </div>
    </form>
  );
}

const PortfolioDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [bonds, setBonds] = useState<Bond[]>([]);
  const [ppkTransactions, setPpkTransactions] = useState<PPKTx[]>([]);
  const [ppkSummary, setPpkSummary] = useState<PPKSummary | null>(null);
  const [ppkCurrentPrice, setPpkCurrentPrice] = useState<{ price: number; date: string } | null>(null);
  const [valueData, setValueData] = useState<PortfolioValue & { live_interest?: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'holdings' | 'analytics' | 'value_history' | 'history' | 'bonds' | 'savings' | 'closed' | 'results' | 'ppk'>('holdings');
  
  // Modals state
  const [isTransferModalOpen, setIsTransferModalOpen] = useState(false);
  const [isTransactionModalOpen, setIsTransactionModalOpen] = useState(false);
  const [isSellModalOpen, setIsSellModalOpen] = useState(false);
  const [selectedHoldingForSell, setSelectedHoldingForSell] = useState<Holding | null>(null);

  // History state
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<{ date: string; close_price: number }[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [portfolioTransactions, setPortfolioTransactions] = useState<Transaction[]>([]);

  // Monthly Dividend state
  const [monthlyDividends, setMonthlyDividends] = useState<{ label: string; amount: number }[]>([]);
  
  // Portfolio History (Monthly)
  const [portfolioHistory, setPortfolioHistory] = useState<{ date: string; label: string; value: number; benchmark_value?: number }[]>([]);
  const [portfolioProfitHistory, setPortfolioProfitHistory] = useState<{ date: string; label: string; value: number }[]>([]);
  const [selectedBenchmark, setSelectedBenchmark] = useState<string>('');

  // Closed Positions
  const [closedPositions, setClosedPositions] = useState<ClosedPosition[]>([]);
  const [totalClosedProfit, setTotalClosedProfit] = useState(0);

  // Budget Integration
  const [budgetAccounts, setBudgetAccounts] = useState<BudgetAccount[]>([]);

  const initiateSell = (h: Holding) => {
    setSelectedHoldingForSell(h);
    setIsSellModalOpen(true);
  };

  const fetchData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [pRes, hRes, vRes, mRes, tRes, cRes, bAccRes] = await Promise.all([
        api.get(`/list`), 
        api.get(`/holdings/${id}`),
        api.get(`/value/${id}`),
        api.get(`/dividends/monthly/${id}`),
        api.get(`/transactions/${id}`),
        api.get(`/${id}/closed-positions`),
        budgetApi.getSummary() // Fetch budget accounts
      ]);
      
      const found = pRes.data.portfolios.find((p: Portfolio) => p.id === parseInt(id));
      setPortfolio(found || null);
      setHoldings(hRes.data.holdings);
      setValueData(vRes.data);
      setMonthlyDividends(mRes.data.monthly_dividends);
      setPortfolioTransactions(tRes.data.transactions);
      setClosedPositions(cRes.data.positions);
      setTotalClosedProfit(cRes.data.total_historical_profit);
      setBudgetAccounts(bAccRes.accounts || []);

      if (found?.account_type === 'BONDS') {
        const bRes = await api.get(`/bonds/${id}`);
        setBonds(bRes.data.bonds);
      }
      
      if (found?.account_type === 'SAVINGS') {
        const histRes = await api.get(`/history/monthly/${id}`);
        setPortfolioHistory(histRes.data.history);
      }
      if (found?.account_type === 'PPK') {
        const ppkRes = await api.get(`/ppk/transactions/${id}`);
        setPpkTransactions(ppkRes.data.transactions || []);
        setPpkSummary(ppkRes.data.summary || null);
        setPpkCurrentPrice(ppkRes.data.currentPrice || null);
      }
      
      // Only set active tab if it's the first load (to preserve tab on refresh)
      // Actually, standard behavior is fine, but let's just ensure we don't overwrite user selection if we were to re-fetch periodically
      if (activeTab === 'holdings' && found) {
          if (found.account_type === 'BONDS') setActiveTab('bonds');
          else if (found.account_type === 'SAVINGS') setActiveTab('savings');
          else if (found.account_type === 'PPK') setActiveTab('ppk');
      }

      // Fetch histories for standard portfolios
      if (found?.account_type !== 'BONDS' && found?.account_type !== 'SAVINGS') {
        const histRes = await api.get(`/history/monthly/${id}`);
        setPortfolioHistory(histRes.data.history);
        
        const profitRes = await api.get(`/history/profit/${id}`);
        setPortfolioProfitHistory(profitRes.data.history);
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
      const url = selectedBenchmark 
        ? `/history/monthly/${id}?benchmark=${selectedBenchmark}`
        : `/history/monthly/${id}`;

      api.get(url).then(res => {
        setPortfolioHistory(res.data.history);
      });
      api.get(`/history/profit/${id}`).then(res => {
        setPortfolioProfitHistory(res.data.history);
      });
    }
  }, [activeTab, id, selectedBenchmark]);

  useEffect(() => {
    fetchData();
  }, [id]);

  const tabLabels: Record<string, string> = {
    holdings: 'Aktywa',
    analytics: 'Analiza',
    results: 'Wyniki',
    value_history: 'Wartość Historyczna',
    history: 'Historia Transakcji',
    bonds: 'Obligacje',
    savings: 'Oszczędności',
    closed: 'Zamknięte Pozycje',
    ppk: 'PPK'
  };

  if (loading) return <div className="p-4 text-center">Ładowanie szczegółów...</div>;
  if (!portfolio || !valueData) return <div className="p-4 text-center">Nie znaleziono portfela</div>;

  return (
    <div className="space-y-6">
      {/* Import XTB CSV button */}
      {portfolio && portfolio.account_type !== 'PPK' && (
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
            portfolio.account_type === 'PPK' ? "bg-purple-100 text-purple-800" :
            "bg-gray-100 text-gray-800"
          )}>
            {portfolio.account_type}
          </span>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-5">
        <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-blue-500">
          <dt className="text-sm font-medium text-gray-500 truncate">Wartość Całkowita</dt>
          <dd className="mt-1 text-2xl font-semibold text-gray-900">{valueData.portfolio_value.toFixed(2)} PLN</dd>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-gray-400">
          <dt className="text-sm font-medium text-gray-500 truncate">
            {portfolio.account_type === 'SAVINGS' ? 'Obecne Saldo' : 'Gotówka'}
          </dt>
          <dd className="mt-1 text-2xl font-semibold text-gray-900">{valueData.cash_value.toFixed(2)} PLN</dd>
          {portfolio.account_type === 'SAVINGS' && valueData.live_interest && valueData.live_interest > 0 ? (
            <dd className="text-xs text-emerald-600 font-medium">w tym {valueData.live_interest.toFixed(2)} PLN odsetek</dd>
          ) : null}
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-green-500">
          <dt className="text-sm font-medium text-gray-500 truncate">Zysk/Strata</dt>
          <dd className={cn("mt-1 text-2xl font-semibold", valueData.total_result >= 0 ? "text-green-600" : "text-red-600")}>
            {valueData.total_result.toFixed(2)} PLN
          </dd>
          
          <div className="mt-2 flex justify-between items-end text-sm border-t pt-2">
            <div className="flex flex-col">
              <span className="text-xs text-gray-400 uppercase tracking-wide">Prosty</span>
              <span className={cn("font-bold", valueData.total_result >= 0 ? "text-green-600" : "text-red-600")}>
                {valueData.total_result_percent.toFixed(2)}%
              </span>
            </div>
            
            {valueData.xirr_percent !== undefined && (
              <div className="flex flex-col items-end">
                <div className="flex items-center gap-1 group relative cursor-help">
                  <span className="text-xs text-gray-400 uppercase tracking-wide">XIRR</span>
                  <HelpCircle className="w-3 h-3 text-gray-400" />
                  <div className="absolute bottom-full right-0 mb-2 hidden group-hover:block w-48 p-2 bg-gray-800 text-white text-xs rounded shadow-lg z-10">
                    Roczna, zannualizowana stopa zwrotu (XIRR)
                  </div>
                </div>
                <span className={cn("font-bold", (valueData.xirr_percent || 0) >= 0 ? "text-green-600" : "text-red-600")}>
                  {(valueData.xirr_percent || 0).toFixed(2)}%
                </span>
              </div>
            )}
          </div>
        </div>
        {portfolio.account_type !== 'SAVINGS' && portfolio.account_type !== 'BONDS' ? (
          <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-indigo-500">
            <dt className="text-sm font-medium text-gray-500 truncate">Dywidendy</dt>
            <dd className="mt-1 text-2xl font-semibold text-blue-600">
              {valueData.total_dividends.toFixed(2)} PLN
            </dd>
          </div>
        ) : (
          <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-indigo-500">
            <dt className="text-sm font-medium text-gray-500 truncate">
              {portfolio.account_type === 'SAVINGS' ? 'Oprocentowanie' : 'Kapitał'}
            </dt>
            <dd className="mt-1 text-2xl font-semibold text-indigo-600">
              {portfolio.account_type === 'SAVINGS' ? `${portfolio.savings_rate}%` : `${(valueData.holdings_value || 0).toFixed(2)} PLN`}
            </dd>
          </div>
        )}
        <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-amber-500">
            <dt className="text-sm font-medium text-gray-500 truncate">Alokacja</dt>
            <div className="h-24">
                 <PortfolioChart holdings={holdings} cash={valueData.cash_value} />
            </div>
        </div>
      </div>

      {/* Navigation & Actions */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="border-b border-gray-200 px-6 py-4 flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
          {/* Left: View Tabs */}
          <nav className="flex space-x-4 overflow-x-auto">
            {(portfolio.account_type === 'SAVINGS' 
                ? ['savings', 'history'] 
                : portfolio.account_type === 'BONDS'
                  ? ['bonds', 'history']
                  : portfolio.account_type === 'PPK'
                    ? ['ppk']
                    : ['holdings', 'analytics', 'results', 'value_history', 'history', 'closed']
            ).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={cn(
                  activeTab === tab
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50',
                  'px-3 py-2 font-medium text-sm rounded-md transition-colors whitespace-nowrap'
                )}
              >
                {tabLabels[tab] || tab}
              </button>
            ))}
          </nav>

          {/* Right: Action Buttons */}
          {portfolio.account_type !== 'PPK' && (
            <div className="flex space-x-3">
               <button
                  onClick={() => setIsTransferModalOpen(true)}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
               >
                  <RefreshCw className="-ml-1 mr-2 h-4 w-4 text-gray-500" />
                  Transfer
               </button>
               <button
                  onClick={() => setIsTransactionModalOpen(true)}
                  className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
               >
                  <Plus className="-ml-1 mr-2 h-4 w-4" />
                  Nowa Operacja
               </button>
            </div>
          )}
        </div>

        <div className="p-6">
          {activeTab === 'analytics' && (
            <PortfolioAnalytics holdings={holdings} cashBalance={valueData.cash_value} />
          )}

          {activeTab === 'results' && (
            <div className="space-y-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Macierz Wyników (MoM)</h3>
              <PerformanceHeatmap portfolioId={portfolio.id} />
            </div>
          )}

          {activeTab === 'holdings' && (
            <div className="space-y-6">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Ilość</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Śr. Cena</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Obecna Cena</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Wartość</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Zysk/Strata</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Waga</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Akcje</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {holdings.map((h) => (
                      <tr 
                        key={h.ticker} 
                        className={cn("cursor-pointer hover:bg-gray-50", selectedTicker === h.ticker && "bg-blue-50")}
                        onClick={() => fetchHistory(h.ticker)}
                      >
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          <div>
                            <div className="font-bold">{h.company_name || h.ticker}</div>
                            <div className="text-xs text-gray-500">{h.ticker}</div>
                            <div className="flex gap-1 mt-1 flex-wrap">
                              {h.sector && h.sector !== 'Unknown' && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                                  🏢 {h.sector}
                                </span>
                              )}
                              {h.industry && h.industry !== 'Unknown' && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                                  💻 {h.industry}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
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
                          <div className="flex items-center justify-end gap-1">
                              {h.profit_loss ? `${h.profit_loss.toFixed(2)} PLN` : '-'}
                              {h.auto_fx_fees && (
                                  <div className="group relative">
                                      <HelpCircle className="w-3 h-3 text-gray-400 cursor-help" />
                                      <div className="absolute bottom-full right-0 mb-2 hidden group-hover:block w-56 p-2 bg-gray-800 text-white text-xs rounded shadow-lg z-20 text-left">
                                          Zysk netto ("na rękę") uwzględniający szacowaną prowizję 0.5% przy sprzedaży.
                                          {h.fx_rate_used && (
                                              <div className="mt-1 text-gray-300">
                                                  Kurs FX: {h.fx_rate_used.toFixed(4)}
                                              </div>
                                          )}
                                      </div>
                                  </div>
                              )}
                          </div>
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
                            Sprzedaj
                          </button>
                        </td>
                      </tr>
                    ))}
                    {holdings.length === 0 && (
                      <tr>
                        <td colSpan={8} className="px-6 py-4 text-center text-sm text-gray-500">Brak aktywów.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* History Chart Section */}
              {selectedTicker && (
                <div className="mt-8 border-t pt-8">
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-medium text-gray-900">Historia Wyników: {selectedTicker}</h3>
                    {lastUpdated && (
                      <span className="text-xs text-gray-500">Ostatnia aktualizacja: {lastUpdated}</span>
                    )}
                  </div>
                  <div className="bg-gray-50 p-4 rounded-lg">
                    {historyLoading ? (
                      <div className="h-64 flex items-center justify-center">Ładowanie historii...</div>
                    ) : historyData.length > 0 ? (
                      <PriceHistoryChart ticker={selectedTicker} data={historyData} />
                    ) : (
                      <div className="h-64 flex items-center justify-center text-gray-500">Brak danych historycznych.</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'value_history' && (
            <div className="space-y-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900">Historia Wartości Portfela</h3>
                <div className="flex items-center space-x-2">
                  <label htmlFor="benchmark" className="text-sm text-gray-700">Benchmark:</label>
                  <select
                    id="benchmark"
                    value={selectedBenchmark}
                    onChange={(e) => setSelectedBenchmark(e.target.value)}
                    className="block w-48 pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
                  >
                    <option value="">Brak</option>
                    <option value="^GSPC">S&P 500 (^GSPC)</option>
                    <option value="ETFBW20TR.WA">WIG20 TR (BETA ETF)</option>
                    <option value="ETFBM40TR.WA">mWIG40 TR (BETA ETF)</option>
                    <option value="SPOL.L">MSCI Poland</option>
                    <option value="VT">Cały Świat (VT)</option>
                    <option value="EEM">Rynki Wschodzące (EEM)</option>
                    <option value="^STOXX">Europa STOXX 600 (^STOXX)</option>
                  </select>
                </div>
              </div>
              {portfolioHistory.length > 0 ? (
                <div className="space-y-8">
                    <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                      <PortfolioHistoryChart data={portfolioHistory} />
                    </div>
                    
                    <h3 className="text-lg font-medium text-gray-900 mb-4">Historia Zysku/Straty</h3>
                    <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                      <PortfolioProfitChart data={portfolioProfitHistory} />
                    </div>
                </div>
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-500">
                  Zbyt mało danych do wyświetlenia historii.
                </div>
              )}
            </div>
          )}

          {activeTab === 'history' && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Data</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Typ</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Ilość</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Cena</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Wartość</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Zrealizowany Zysk</th>
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
                      <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">Brak transakcji.</td>
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
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nazwa Obligacji</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Data Zakupu</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Kapitał</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Oprocentowanie</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Naliczone</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Wartość Całkowita</th>
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
                        <td colSpan={6} className="px-6 py-4 text-center text-sm text-gray-500">Brak obligacji.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'savings' && (
            <div className="space-y-8">
              <div className="bg-emerald-50 p-8 rounded-2xl border border-emerald-100 text-center max-w-2xl mx-auto shadow-sm">
                <p className="text-emerald-600 font-semibold uppercase tracking-widest text-sm mb-2">Całkowite Oszczędności</p>
                <h2 className="text-5xl font-bold text-emerald-900 mb-4">
                  {valueData.portfolio_value.toFixed(2)} <span className="text-2xl font-normal text-emerald-700">PLN</span>
                </h2>
                <div className="flex justify-center items-center space-x-6 text-emerald-700">
                   <div className="flex flex-col">
                      <span className="text-xs uppercase font-medium">Oprocentowanie</span>
                      <span className="text-lg font-bold">{portfolio.savings_rate}%</span>
                   </div>
                   <div className="w-px h-8 bg-emerald-200"></div>
                   <div className="flex flex-col">
                      <span className="text-xs uppercase font-medium">Naliczone Odsetki</span>
                      <span className="text-lg font-bold">+{valueData.live_interest?.toFixed(2)} PLN</span>
                   </div>
                </div>
              </div>

              {/* Monthly History Chart */}
              {portfolioHistory.length > 0 && (
                <div className="mt-8 border-t pt-8">
                  <h3 className="text-lg font-medium text-gray-900 mb-6 text-center">Historia Salda</h3>
                  <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                     <PortfolioHistoryChart data={portfolioHistory} />
                  </div>
                </div>
              )}
            </div>
          )}


          {activeTab === 'ppk' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-purple-50 p-4 rounded-lg border border-purple-100">
                  <p className="text-sm text-purple-700">Total units</p>
                  <p className="text-2xl font-bold text-purple-900">{(ppkSummary?.totalUnits ?? 0).toFixed(4)}</p>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg border border-purple-100">
                  <p className="text-sm text-purple-700">Average price</p>
                  <p className="text-2xl font-bold text-purple-900">{(ppkSummary?.averagePrice ?? 0).toFixed(2)} PLN</p>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg border border-purple-100">
                  <p className="text-sm text-purple-700">Aktualna cena pakietu PPK</p>
                  <p className="text-2xl font-bold text-purple-900">{ppkCurrentPrice ? `${ppkCurrentPrice.price.toFixed(2)} PLN` : '-'}</p>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg border border-purple-100">
                  <p className="text-sm text-purple-700">Ostatnia aktualizacja ceny</p>
                  <p className="text-2xl font-bold text-purple-900">{ppkCurrentPrice?.date || '-'}</p>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg border border-purple-100 md:col-span-2">
                  <p className="text-sm text-purple-700">Wartość bieżąca (wg aktualnej ceny)</p>
                  <p className="text-2xl font-bold text-purple-900">{ppkSummary ? `${ppkSummary.currentValue.toFixed(2)} PLN` : '-'}</p>
                </div>
              </div>

              <PPKContributionForm portfolioId={portfolio.id} onSuccess={fetchData} />

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Employee units</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Employer units</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Price / unit</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Employee amount</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Employer amount</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {ppkTransactions.map((tx) => (
                      <tr key={tx.id}>
                        <td className="px-4 py-3 text-sm text-gray-900">{tx.date}</td>
                        <td className="px-4 py-3 text-sm text-right">{Number(tx.employee_units).toFixed(4)}</td>
                        <td className="px-4 py-3 text-sm text-right">{Number(tx.employer_units).toFixed(4)}</td>
                        <td className="px-4 py-3 text-sm text-right">{Number(tx.price_per_unit).toFixed(4)} PLN</td>
                        <td className="px-4 py-3 text-sm text-right">{(Number(tx.employee_units) * Number(tx.price_per_unit)).toFixed(2)} PLN</td>
                        <td className="px-4 py-3 text-sm text-right">{(Number(tx.employer_units) * Number(tx.price_per_unit)).toFixed(2)} PLN</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'closed' && (
            <div className="space-y-6">
              <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mb-6">
                <h3 className="text-lg font-medium text-gray-900">Całkowity Zrealizowany Zysk</h3>
                <p className={cn("text-3xl font-bold mt-2", totalClosedProfit >= 0 ? "text-green-600" : "text-red-600")}>
                  {totalClosedProfit.toFixed(2)} PLN
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nazwa spółki</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Zrealizowany Zysk</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {closedPositions.map((p) => (
                      <tr key={p.ticker}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{p.ticker}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">{p.company_name || "-"}</td>
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
                        <td colSpan={3} className="px-6 py-4 text-center text-sm text-gray-500">Brak zamkniętych pozycji.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          
          {/* Dividend Bar Chart - Only show in analytics or maybe create a specific view? 
              Original code showed it under 'dividend' tab. 
              Let's put it in Analytics for now or create a 'Dividends' View? 
              For now, I'll add it to the Analytics tab if the portfolio type supports it. 
              Actually, the prompt didn't specify where to put it, but Analytics is a good place.
          */}
          {activeTab === 'analytics' && portfolio.account_type !== 'SAVINGS' && portfolio.account_type !== 'BONDS' && (
             <div className="mt-8 border-t pt-8">
                <h3 className="text-lg font-medium text-gray-900 mb-6">Miesięczne Dywidendy</h3>
                <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                  {monthlyDividends.length > 0 ? (
                    <DividendBarChart data={monthlyDividends} />
                  ) : (
                    <div className="h-64 flex items-center justify-center text-gray-500 italic">
                      Brak zarejestrowanych dywidend.
                    </div>
                  )}
                </div>
              </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <TransferModal
        isOpen={isTransferModalOpen}
        onClose={() => setIsTransferModalOpen(false)}
        onSuccess={fetchData}
        portfolioId={portfolio.id}
        budgetAccounts={budgetAccounts}
        maxCash={valueData.cash_value}
      />

      <TransactionModal
        isOpen={isTransactionModalOpen}
        onClose={() => setIsTransactionModalOpen(false)}
        onSuccess={fetchData}
        portfolioId={portfolio.id}
        portfolioType={portfolio.account_type}
        holdings={holdings}
      />

      <SellModal
        isOpen={isSellModalOpen}
        onClose={() => setIsSellModalOpen(false)}
        onSuccess={fetchData}
        portfolioId={portfolio.id}
        holding={selectedHoldingForSell}
      />

    </div>
  );
};

export default PortfolioDetails;
