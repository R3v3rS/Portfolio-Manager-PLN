import React, { lazy, useCallback, useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Plus, RefreshCw, HelpCircle, Trash2, ShieldAlert, Wrench } from 'lucide-react';
import api, {
  portfolioApi,
  normalizeXtbImportError,
  normalizeXtbImportResult,
  type PortfolioAuditResult,
  type XtbImportResult,
} from '../api';
import { budgetApi, BudgetAccount } from '../api_budget';
import { Portfolio, Holding, Transaction, PortfolioValue, Bond, ClosedPosition, ClosedPositionCycle } from '../types';
import TransferModal from '../components/modals/TransferModal';
import TransactionModal from '../components/modals/TransactionModal';
import SellModal from '../components/modals/SellModal';
import { cn } from '../lib/utils.ts';
import { PPKSummary, PPKTransaction as PPKTx } from '../services/ppkCalculator';
import { symbolMapApi, MappingCurrency } from '../api_symbol_map';


const PortfolioChart = lazy(() => import('../components/PortfolioChart'));
const PortfolioAnalytics = lazy(() => import('../components/PortfolioAnalytics'));
const PriceHistoryChart = lazy(() => import('../components/PriceHistoryChart'));
const DividendBarChart = lazy(() => import('../components/DividendBarChart'));
const PortfolioHistoryChart = lazy(() => import('../components/PortfolioHistoryChart'));
const PortfolioProfitChart = lazy(() => import('../components/PortfolioProfitChart'));
const PerformanceHeatmap = lazy(() => import('../components/portfolio/PerformanceHeatmap'));
const Profit30dMatrix = lazy(() => import('../components/portfolio/Profit30dMatrix'));

const createMissingSymbolDrafts = (symbols: string[]) =>
  symbols.reduce<Record<string, { ticker: string; currency: MappingCurrency }>>((acc, symbol) => {
    acc[symbol] = { ticker: '', currency: 'PLN' };
    return acc;
  }, {});

function ImportXtbCsvButton({ portfolioId, onSuccess }: { portfolioId: number, onSuccess: () => void }) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [missingSymbols, setMissingSymbols] = useState<string[]>([]);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [mappingDrafts, setMappingDrafts] = useState<Record<string, { ticker: string; currency: MappingCurrency }>>({});
  const [savingMappings, setSavingMappings] = useState(false);

  const openMissingSymbolsModal = (symbols: string[], file: File) => {
    setMissingSymbols(symbols);
    setPendingFile(file);
    setMappingDrafts(createMissingSymbolDrafts(symbols));
  };

  const importFile = async (file: File) => {
    try {
      const result = normalizeXtbImportResult(await portfolioApi.importXtbCsv(portfolioId, file));

      if (result.missingSymbols.length > 0) {
        openMissingSymbolsModal(result.missingSymbols, file);
        return;
      }

      if (!result.ok) {
        alert('Import failed: ' + (result.message ?? 'Unknown error'));
        return;
      }

      alert('Import successful!');
      onSuccess();
    } catch (err: unknown) {
      const result = normalizeXtbImportError(err);

      if (result.missingSymbols.length > 0) {
        openMissingSymbolsModal(result.missingSymbols, file);
        return;
      }

      alert('Import failed: ' + (result.message ?? 'Unknown error'));
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    const file = e.target.files[0];
    await importFile(file);
    e.target.value = '';
  };

  const closeMissingModal = () => {
    setMissingSymbols([]);
    setPendingFile(null);
    setMappingDrafts({});
    setSavingMappings(false);
  };

  const saveMappingsAndRetry = async () => {
    if (!pendingFile) return;

    for (const symbol of missingSymbols) {
      const draft = mappingDrafts[symbol];
      if (!draft || !draft.ticker.trim()) {
        alert(`Provide ticker for ${symbol}`);
        return;
      }
    }

    setSavingMappings(true);
    try {
      for (const symbol of missingSymbols) {
        const draft = mappingDrafts[symbol];
        await symbolMapApi.create({
          symbol_input: symbol,
          ticker: draft.ticker.trim().toUpperCase(),
          currency: draft.currency,
        });
      }

      closeMissingModal();
      await importFile(pendingFile);
    } catch (error) {
      const parsedError = normalizeXtbImportError(error);
      alert(parsedError.message ?? 'Failed to save mappings');
      setSavingMappings(false);
    }
  };

  return (
    <>
      <button
        className="inline-flex items-center rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
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

      {missingSymbols.length > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-2xl rounded-lg bg-white p-5 shadow-xl dark:bg-gray-900">
            <h3 className="mb-2 text-lg font-semibold text-gray-900 dark:text-gray-100">Missing symbol mappings</h3>
            <p className="mb-4 text-sm text-gray-600 dark:text-gray-300">
              Add mappings for missing symbols and retry import.
            </p>

            <div className="space-y-3">
              {missingSymbols.map((symbol) => (
                <div key={symbol} className="grid grid-cols-1 gap-2 rounded-md border border-gray-200 p-3 md:grid-cols-3 dark:border-gray-700">
                  <input
                    value={symbol}
                    readOnly
                    className="rounded-md border border-gray-300 bg-gray-100 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800"
                  />
                  <input
                    value={mappingDrafts[symbol]?.ticker ?? ''}
                    onChange={(e) =>
                      setMappingDrafts((prev) => ({
                        ...prev,
                        [symbol]: {
                          ...(prev[symbol] ?? { ticker: '', currency: 'PLN' as MappingCurrency }),
                          ticker: e.target.value,
                        },
                      }))
                    }
                    placeholder="Ticker (e.g. AAPL)"
                    className="rounded-md border border-gray-300 px-3 py-2 text-sm uppercase dark:border-gray-700 dark:bg-gray-800"
                  />
                  <select
                    value={mappingDrafts[symbol]?.currency ?? 'PLN'}
                    onChange={(e) =>
                      setMappingDrafts((prev) => ({
                        ...prev,
                        [symbol]: {
                          ...(prev[symbol] ?? { ticker: '', currency: 'PLN' as MappingCurrency }),
                          currency: e.target.value as MappingCurrency,
                        },
                      }))
                    }
                    className="rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800"
                  >
                    <option value="PLN">PLN</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                  </select>
                </div>
              ))}
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={closeMissingModal}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={saveMappingsAndRetry}
                disabled={savingMappings}
                className="rounded-md bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {savingMappings ? 'Saving...' : 'Save mappings & retry import'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}



function ClearPortfolioButton({ portfolioId, portfolioName, onSuccess }: { portfolioId: number; portfolioName: string; onSuccess: () => void }) {
  const [clearing, setClearing] = useState(false);

  const handleClear = async () => {
    const confirmed = window.confirm(
      `To usunie wszystkie transakcje, aktywa, dywidendy i obligacje z portfela "${portfolioName}". Czy kontynuować?`
    );

    if (!confirmed) return;

    setClearing(true);
    try {
      await portfolioApi.clear(portfolioId);
      alert('Portfolio zostało wyczyszczone. Możesz zaimportować dane od nowa.');
      onSuccess();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Nie udało się wyczyścić portfela';
      alert(message);
    } finally {
      setClearing(false);
    }
  };

  return (
    <button
      type="button"
      className="mb-4 inline-flex items-center gap-2 rounded bg-red-600 px-4 py-2 text-white hover:bg-red-700 disabled:opacity-60"
      onClick={handleClear}
      disabled={clearing}
    >
      <Trash2 className="h-4 w-4" />
      {clearing ? 'Czyszczenie...' : 'Wyczyść portfolio'}
    </button>
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
      <button type="submit" className="px-3 py-2 text-sm bg-purple-600 text-white rounded">+ Dodaj miesięczną wpłatę</button>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="p-2 border rounded" required />
        <input type="number" step="0.0001" value={employeeUnits} onChange={(e) => setEmployeeUnits(e.target.value)} placeholder="Jednostki pracownika" className="p-2 border rounded" required />
        <input type="number" step="0.0001" value={employerUnits} onChange={(e) => setEmployerUnits(e.target.value)} placeholder="Jednostki pracodawcy" className="p-2 border rounded" required />
        <input type="number" step="0.0001" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="Cena za jednostkę" className="p-2 border rounded" required />
      </div>
    </form>
  );
}

const formatSellDate = (value?: string | null) => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('pl-PL');
};

type ActiveTab = 'holdings' | 'analytics' | 'value_history' | 'history' | 'bonds' | 'savings' | 'closed' | 'closed_cycles' | 'results' | 'ppk' | 'ppk_history';

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
  const [activeTab, setActiveTab] = useState<ActiveTab>('holdings');
  
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
  const [refreshingPrices, setRefreshingPrices] = useState(false);
  const [portfolioTransactions, setPortfolioTransactions] = useState<Transaction[]>([]);
  const [auditResult, setAuditResult] = useState<PortfolioAuditResult | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [rebuildLoading, setRebuildLoading] = useState(false);

  // Monthly Dividend state
  const [monthlyDividends, setMonthlyDividends] = useState<{ label: string; amount: number }[]>([]);
  
  // Portfolio History (Monthly)
  const [portfolioHistory, setPortfolioHistory] = useState<{ date: string; label: string; value: number; benchmark_value?: number }[]>([]);
  const [portfolioProfitHistory, setPortfolioProfitHistory] = useState<{ date: string; label: string; value: number }[]>([]);
  const [portfolioProfit30dHistory, setPortfolioProfit30dHistory] = useState<{ date: string; label: string; value: number }[]>([]);
  const [portfolioValue30dHistory, setPortfolioValue30dHistory] = useState<{ date: string; label: string; value: number }[]>([]);
  const [selectedBenchmark, setSelectedBenchmark] = useState<string>('');

  // Closed Positions
  const [closedPositions, setClosedPositions] = useState<ClosedPosition[]>([]);
  const [totalClosedProfit, setTotalClosedProfit] = useState(0);
  const [closedPositionCycles, setClosedPositionCycles] = useState<ClosedPositionCycle[]>([]);
  const [totalClosedCyclesProfit, setTotalClosedCyclesProfit] = useState(0);

  const dividendTickers = Array.from(
    new Set([
      ...holdings.map((h) => h.ticker),
      ...closedPositions.map((p) => p.ticker),
      ...closedPositionCycles.map((p) => p.ticker),
    ])
  );

  // Budget Integration
  const [budgetAccounts, setBudgetAccounts] = useState<BudgetAccount[]>([]);

  const initiateSell = (h: Holding) => {
    setSelectedHoldingForSell(h);
    setIsSellModalOpen(true);
  };

  const closePositionAtLastPrice = async (holding: Holding) => {
    if (!id) return;

    if (!holding.current_price || holding.current_price <= 0) {
      alert(`Brak aktualnej ceny dla ${holding.ticker}. Najpierw odśwież ceny.`);
      return;
    }

    const confirmed = window.confirm(
      `Zamknąć całą pozycję ${holding.ticker} (${Number(holding.quantity).toFixed(4)} szt.) po ${holding.current_price.toFixed(4)} ${holding.currency || 'PLN'}?`
    );

    if (!confirmed) return;

    try {
      await api.post('/sell', {
        portfolio_id: parseInt(id),
        ticker: holding.ticker,
        quantity: holding.quantity,
        price: holding.current_price,
      });
      await fetchData();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Nieznany błąd';
      alert('Nie udało się zamknąć pozycji: ' + message);
    }
  };

  const fetchData = useCallback(async () => {
    if (!id) return;
    const portfolioId = parseInt(id, 10);
    if (Number.isNaN(portfolioId)) return;
    setLoading(true);
    try {
      const [pRes, hRes, vRes, mRes, tRes, cRes, ccRes, bAccRes] = await Promise.all([
        portfolioApi.listNormalized(),
        portfolioApi.getHoldings(portfolioId),
        portfolioApi.getValue(portfolioId),
        portfolioApi.getMonthlyDividends(portfolioId),
        portfolioApi.getTransactions(portfolioId),
        portfolioApi.getClosedPositions(portfolioId),
        portfolioApi.getClosedPositionCycles(portfolioId),
        budgetApi.getSummary()
      ]);
      
      const found = pRes.find((p: Portfolio) => p.id === portfolioId) ?? null;
      setPortfolio(found || null);
      setHoldings(hRes ?? []);
      setValueData(vRes);
      setMonthlyDividends(mRes ?? []);
      setPortfolioTransactions(tRes ?? []);
      setClosedPositions(cRes.positions ?? []);
      setTotalClosedProfit(cRes.total_historical_profit ?? 0);
      setClosedPositionCycles(ccRes.positions || []);
      setTotalClosedCyclesProfit(ccRes.total_historical_profit || 0);
      setBudgetAccounts(bAccRes.accounts || []);

      if (found?.account_type === 'BONDS') {
        const bRes = await portfolioApi.getBonds(portfolioId);
        setBonds(bRes ?? []);
      } else {
        setBonds([]);
      }
      
      if (found?.account_type === 'SAVINGS') {
        const histRes = await portfolioApi.getMonthlyHistory(portfolioId);
        setPortfolioHistory(histRes ?? []);
      } else {
        setPortfolioHistory([]);
      }
      if (found?.account_type === 'PPK') {
        const ppkRes = await portfolioApi.getPpkTransactions(portfolioId);
        setPpkTransactions(ppkRes.transactions ?? []);
        setPpkSummary(ppkRes.summary ?? null);
        setPpkCurrentPrice(ppkRes.currentPrice ?? null);
      } else {
        setPpkTransactions([]);
        setPpkSummary(null);
        setPpkCurrentPrice(null);
      }
      
      // Only set active tab if it's the first load (to preserve tab on refresh)
      // Actually, standard behavior is fine, but let's just ensure we don't overwrite user selection if we were to re-fetch periodically
      if (found) {
        setActiveTab((currentTab) => {
          if (currentTab !== 'holdings') return currentTab;
          if (found.account_type === 'BONDS') return 'bonds';
          if (found.account_type === 'SAVINGS') return 'savings';
          if (found.account_type === 'PPK') return 'ppk';
          return currentTab;
        });
      }

      // Fetch histories for standard portfolios
      if (found?.account_type !== 'BONDS' && found?.account_type !== 'SAVINGS') {
        const [histRes, profitRes, profit30dRes, value30dRes] = await Promise.all([
          portfolioApi.getMonthlyHistory(portfolioId),
          portfolioApi.getProfitHistory(portfolioId),
          portfolioApi.getProfitHistory(portfolioId, 30),
          portfolioApi.getValueHistory(portfolioId, 30),
        ]);
        setPortfolioHistory(histRes ?? []);
        
        setPortfolioProfitHistory(profitRes ?? []);
        setPortfolioProfit30dHistory(profit30dRes ?? []);
        setPortfolioValue30dHistory(value30dRes ?? []);
      } else {
        setPortfolioProfitHistory([]);
        setPortfolioProfit30dHistory([]);
        setPortfolioValue30dHistory([]);
      }

    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  const refreshStockPrices = async () => {
    if (!id || !(portfolio?.account_type === 'STANDARD' || portfolio?.account_type === 'IKE')) return;
    const portfolioId = parseInt(id, 10);
    if (Number.isNaN(portfolioId)) return;

    setRefreshingPrices(true);
    try {
      const [holdingsResponse, valueResponse] = await Promise.all([
        portfolioApi.getHoldings(portfolioId, { refresh: 1 }),
        portfolioApi.getValue(portfolioId),
      ]);

      setHoldings(holdingsResponse ?? []);
      setValueData(valueResponse);
    } catch (err) {
      console.error('Failed to refresh stock prices', err);
      alert('Nie udało się odświeżyć cen akcji. Spróbuj ponownie.');
    } finally {
      setRefreshingPrices(false);
    }
  };

  const runAudit = async () => {
    if (!id) return;
    const portfolioId = parseInt(id, 10);
    if (Number.isNaN(portfolioId)) return;

    setAuditLoading(true);
    try {
      const response = await portfolioApi.runAudit(portfolioId);
      setAuditResult(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Nie udało się uruchomić audytu portfela.';
      alert(message);
    } finally {
      setAuditLoading(false);
    }
  };

  const runRebuild = async () => {
    if (!id) return;
    const portfolioId = parseInt(id, 10);
    if (Number.isNaN(portfolioId)) return;

    const confirmed = window.confirm(
      'Naprawa nadpisze holdings i stan gotówki na podstawie transakcji. Czy kontynuować?'
    );
    if (!confirmed) return;

    setRebuildLoading(true);
    try {
      await portfolioApi.rebuild(portfolioId);
      await Promise.all([runAudit(), fetchData()]);
      alert('Portfolio zostało przebudowane na podstawie transakcji.');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Nie udało się przebudować portfela.';
      alert(message);
    } finally {
      setRebuildLoading(false);
    }
  };

  const fetchHistory = async (ticker: string) => {
    setHistoryLoading(true);
    setSelectedTicker(ticker);
    try {
      const response = await portfolioApi.getPriceHistory(ticker);
      setHistoryData(response.history ?? []);
      setLastUpdated(response.last_updated ?? null);
    } catch (err) {
      console.error('Failed to fetch history', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    // Fetch history separately when tab changes or initially
    if (activeTab === 'value_history' && id) {
      const portfolioId = parseInt(id, 10);
      if (Number.isNaN(portfolioId)) return;

      Promise.all([
        portfolioApi.getMonthlyHistory(portfolioId, selectedBenchmark || undefined),
        portfolioApi.getProfitHistory(portfolioId),
      ])
        .then(([history, profitHistory]) => {
          setPortfolioHistory(history ?? []);
          setPortfolioProfitHistory(profitHistory ?? []);
        })
        .catch((err) => {
          console.error('Failed to refresh value history tab', err);
          setPortfolioHistory([]);
          setPortfolioProfitHistory([]);
        });
    }
  }, [activeTab, id, selectedBenchmark]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);


  const formatPriceUpdateTimestamp = (timestamp?: string | null) => {
    if (!timestamp) return '-';

    const parsedDate = new Date(timestamp);
    if (Number.isNaN(parsedDate.getTime())) return timestamp;

    return parsedDate.toLocaleString('pl-PL', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const tabLabels: Record<string, string> = {
    holdings: 'Aktywa',
    analytics: 'Analiza',
    results: 'Wyniki',
    value_history: 'Wartość Historyczna',
    history: 'Historia Transakcji',
    bonds: 'Obligacje',
    savings: 'Oszczędności',
    closed: 'Zamknięte Pozycje',
    closed_cycles: 'Zamknięte Pozycje (cykle)',
    ppk: 'PPK',
    ppk_history: 'Historia wpłat'
  };

  if (loading) return <div className="p-4 text-center">Ładowanie szczegółów...</div>;
  if (!portfolio || !valueData) return <div className="p-4 text-center">Nie znaleziono portfela</div>;

  const visibleTabs: ActiveTab[] =
    portfolio.account_type === 'SAVINGS'
      ? ['savings', 'history']
      : portfolio.account_type === 'BONDS'
        ? ['bonds', 'history']
        : portfolio.account_type === 'PPK'
          ? ['ppk', 'ppk_history']
          : ['holdings', 'analytics', 'results', 'value_history', 'history', 'closed', 'closed_cycles'];

  return (
    <div className="space-y-6">
      {/* Import / reset actions */}
      {portfolio && portfolio.account_type !== 'PPK' && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <ImportXtbCsvButton portfolioId={portfolio.id} onSuccess={fetchData} />
          <ClearPortfolioButton portfolioId={portfolio.id} portfolioName={portfolio.name} onSuccess={fetchData} />
          <button
            type="button"
            onClick={runAudit}
            disabled={auditLoading}
            className="inline-flex items-center gap-2 rounded border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-60"
          >
            <ShieldAlert className="h-4 w-4" />
            {auditLoading ? 'Audytowanie...' : 'Audit portfolio'}
          </button>
          <button
            type="button"
            onClick={runRebuild}
            disabled={rebuildLoading}
            className="inline-flex items-center gap-2 rounded border border-indigo-300 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 disabled:opacity-60"
          >
            <Wrench className="h-4 w-4" />
            {rebuildLoading ? 'Rebuild...' : 'Rebuild from transactions'}
          </button>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/portfolios"
          className="inline-flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-800"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Wróć do inwestycji</span>
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
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-6">
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
          {(portfolio.account_type !== 'SAVINGS' && portfolio.account_type !== 'BONDS') && (
            <div className="mt-3 space-y-1 text-xs text-gray-500">
              <div className="flex items-center justify-between">
                <span>Zamknięte pozycje</span>
                <span className={cn("font-medium", totalClosedProfit >= 0 ? "text-green-600" : "text-red-600")}>{totalClosedProfit.toFixed(2)} PLN</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Otwarte pozycje</span>
                <span className={cn("font-medium", (valueData.open_positions_result || 0) >= 0 ? "text-green-600" : "text-red-600")}>{(valueData.open_positions_result || 0).toFixed(2)} PLN</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Dywidendy</span>
                <span className="font-medium text-blue-600">{valueData.total_dividends.toFixed(2)} PLN</span>
              </div>
              {(valueData.total_interest || 0) !== 0 && (
                <div className="flex items-center justify-between">
                  <span>Odsetki / free funds interest</span>
                  <span className="font-medium text-emerald-600">{(valueData.total_interest || 0).toFixed(2)} PLN</span>
                </div>
              )}
            </div>
          )}
          
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
        <div className="bg-white overflow-hidden shadow rounded-lg p-5 border-t-4 border-emerald-500">
          <dt className="text-sm font-medium text-gray-500 truncate">Otwarte pozycje</dt>
          <dd className={cn("mt-1 text-2xl font-semibold", (valueData.open_positions_result || 0) >= 0 ? "text-green-600" : "text-red-600")}>
            {(valueData.open_positions_result || 0).toFixed(2)} PLN
          </dd>
          <dd className="mt-2 text-xs text-gray-400">Aktualny zysk/strata niezrealizowanych pozycji.</dd>
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

      {auditResult && (
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Audit integralności portfela</h2>
              <p className="text-sm text-slate-500">
                Stan odtworzony wyłącznie z transakcji vs aktualne holdings i cash.
              </p>
            </div>
            <span
              className={cn(
                'inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide',
                auditResult.is_consistent
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-amber-100 text-amber-800'
              )}
            >
              {auditResult.is_consistent ? 'Consistent' : 'Mismatch detected'}
            </span>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-xs uppercase tracking-wide text-slate-500">Rebuilt cash</div>
              <div className="mt-1 text-lg font-semibold text-slate-900">
                {auditResult.rebuilt_state?.cash?.toFixed(2) ?? '0.00'} PLN
              </div>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-xs uppercase tracking-wide text-slate-500">Realized profit</div>
              <div className="mt-1 text-lg font-semibold text-slate-900">
                {auditResult.rebuilt_state?.realized_profit_total?.toFixed(2) ?? '0.00'} PLN
              </div>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-xs uppercase tracking-wide text-slate-500">Rebuilt holdings</div>
              <div className="mt-1 text-lg font-semibold text-slate-900">
                {Object.keys(auditResult.rebuilt_state?.holdings || {}).length}
              </div>
            </div>
          </div>

          <div className="mt-4">
            {auditResult.differences.length === 0 ? (
              <p className="rounded-md bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                Brak rozbieżności między stanem zapisanym a stanem odtworzonym z transakcji.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-slate-500">Typ</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-500">Ticker</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-500">Expected</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-500">Actual</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {auditResult.differences.map((diff, index) => (
                      <tr key={`${diff.type}-${diff.ticker || 'cash'}-${index}`}>
                        <td className="px-4 py-2 text-slate-700">{diff.type}</td>
                        <td className="px-4 py-2 text-slate-700">{diff.ticker || 'CASH'}</td>
                        <td className="px-4 py-2 text-slate-700">{diff.expected.toFixed(2)}</td>
                        <td className="px-4 py-2 text-slate-700">{diff.actual.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Navigation & Actions */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="flex flex-col justify-between space-y-4 border-b border-gray-200 px-6 py-4 md:flex-row md:items-center md:space-y-0">
          {/* Left: View Tabs */}
          <div className="w-full overflow-x-auto pb-1 md:w-auto md:pb-0">
            <nav className="inline-flex min-w-max items-center gap-2">
            {visibleTabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
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
          </div>

          {/* Right: Action Buttons */}
          {portfolio.account_type !== 'PPK' && (
            <div className="flex w-full flex-wrap justify-end gap-3 md:w-auto">
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
            <PortfolioAnalytics holdings={holdings} cashBalance={valueData.cash_value} historyData={portfolioHistory} />
          )}

          {activeTab === 'results' && (
            <div className="space-y-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Macierz Wyników (MoM)</h3>
              <PerformanceHeatmap portfolioId={portfolio.id} />
              <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                <PortfolioProfitChart
                  data={portfolioProfit30dHistory}
                  title="Zmiana zysku - ostatnie 30 dni (PLN)"
                />
              </div>

              <div className="space-y-3">
                <h4 className="text-base font-medium text-gray-900">Macierz zmiany zysku % (30D)</h4>
                <Profit30dMatrix data={portfolioProfit30dHistory} rowLabel="% zmiany zysku" />
              </div>

              <div className="space-y-3">
                <h4 className="text-base font-medium text-gray-900">Macierz zmiany wartości portfela % (30D)</h4>
                <Profit30dMatrix data={portfolioValue30dHistory} rowLabel="% zmiany wartości" />
              </div>
            </div>
          )}

          {activeTab === 'holdings' && (
            <div className="space-y-6">
              {(portfolio.account_type === 'STANDARD' || portfolio.account_type === 'IKE') && (
                <div className="flex justify-end">
                  <button
                    onClick={refreshStockPrices}
                    disabled={refreshingPrices}
                    className="inline-flex items-center px-4 py-2 border border-indigo-200 shadow-sm text-sm font-medium rounded-md text-indigo-700 bg-indigo-50 hover:bg-indigo-100 disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    <RefreshCw className={cn('mr-2 h-4 w-4', refreshingPrices && 'animate-spin')} />
                    {refreshingPrices ? 'Odświeżanie cen...' : 'Odśwież ceny z giełdy'}
                  </button>
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="min-w-[980px] divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="min-w-[220px] px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Symbol</th>
                      <th className="min-w-[90px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Ilość</th>
                      <th className="min-w-[110px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Śr. Cena</th>
                      <th className="min-w-[120px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Obecna Cena</th>
                      <th className="min-w-[140px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Aktualizacja Ceny</th>
                      <th className="min-w-[120px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Wartość</th>
                      <th className="min-w-[120px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Zysk/Strata</th>
                      <th className="min-w-[90px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Waga</th>
                      <th className="min-w-[130px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Akcje</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {holdings.map((h) => (
                      <tr 
                        key={h.ticker} 
                        className={cn("cursor-pointer hover:bg-gray-50", selectedTicker === h.ticker && "bg-blue-50")}
                        onClick={() => fetchHistory(h.ticker)}
                      >
                        <td className="px-4 py-4 align-top text-sm font-medium text-gray-900">
                          <div className="min-w-[220px]">
                            <div className="font-bold leading-snug break-words whitespace-normal">{h.company_name || h.ticker}</div>
                            <div className="text-xs text-gray-500 break-all sm:break-normal">{h.ticker}</div>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {h.sector && h.sector !== 'Unknown' && (
                                <span className="inline-flex max-w-full items-center rounded px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 whitespace-normal break-words">
                                  🏢 {h.sector}
                                </span>
                              )}
                              {h.industry && h.industry !== 'Unknown' && (
                                <span className="inline-flex max-w-full items-center rounded px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-800 whitespace-normal break-words">
                                  💻 {h.industry}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-4 text-sm text-right text-gray-500">
                          {parseFloat(Number(h.quantity).toFixed(4))}
                        </td>
                        <td className="px-3 py-4 text-sm text-right text-gray-500">{h.average_buy_price.toFixed(2)} PLN</td>
                        <td className="px-3 py-4 text-sm text-right text-gray-500">
                          {h.current_price ? `${h.current_price.toFixed(2)} ${h.currency || 'PLN'}` : '-'}
                        </td>
                        <td className="px-3 py-4 text-sm text-right text-gray-500">
                          {formatPriceUpdateTimestamp(h.price_last_updated_at)}
                        </td>
                        <td className="px-3 py-4 text-sm text-right text-gray-500">
                          {h.current_value ? `${h.current_value.toFixed(2)} PLN` : '-'}
                        </td>
                        <td className={cn(
                          "px-4 py-4 text-sm text-right font-medium",
                          (h.profit_loss || 0) >= 0 ? "text-green-600" : "text-red-600"
                        )}>
                          <div className="flex items-center justify-end gap-1 whitespace-nowrap">
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
                        <td className="px-3 py-4 text-sm text-right text-gray-500 font-medium">
                          {h.weight_percent ? `${h.weight_percent}%` : '-'}
                        </td>
                        <td className="px-3 py-4 text-sm text-right font-medium">
                          <div className="flex flex-wrap justify-end gap-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                initiateSell(h);
                              }}
                              className="rounded-md bg-red-50 px-2.5 py-1 text-xs text-red-600 transition-colors hover:text-red-900 sm:px-3 sm:text-sm"
                            >
                              Sprzedaj
                            </button>
                            {(portfolio.account_type === 'IKE' || portfolio.account_type === 'STANDARD') && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  closePositionAtLastPrice(h);
                                }}
                                className="rounded-md bg-orange-100 px-2.5 py-1 text-xs text-orange-700 transition-colors hover:text-orange-900 sm:px-3 sm:text-sm"
                                title="Sprzedaje całą pozycję po ostatniej zaktualizowanej cenie"
                              >
                                Zamknij
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                    {holdings.length === 0 && (
                      <tr>
                        <td colSpan={9} className="px-6 py-4 text-center text-sm text-gray-500">Brak aktywów.</td>
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
              <div className="overflow-x-auto lg:overflow-x-visible">
                <table className="w-full table-fixed divide-y divide-gray-200">
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
                  <p className="text-sm text-purple-700">Wartość możliwa do wypłaty (po podatku)</p>
                  <p className="text-2xl font-bold text-purple-900">{ppkSummary ? `${ppkSummary.totalNetValue.toFixed(2)} PLN` : '-'}</p>
                </div>
              </div>

              <PPKContributionForm portfolioId={portfolio.id} onSuccess={fetchData} />

              <div className="overflow-x-auto">
                <p className="text-sm text-gray-500 mb-3">Szczegóły wpłat znajdziesz w zakładce „Historia wpłat”.</p>
              </div>
            </div>
          )}

          {activeTab === 'ppk_history' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900">Historia wpłat PPK</h3>
                <p className="text-sm text-gray-500">Podsumowanie każdej wpłaty: data, łączna suma, jednostki i cena.</p>
              </div>

              <div className="overflow-x-auto lg:overflow-x-visible">
                <table className="w-full table-fixed divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Data</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Suma wpłaty</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Ilość jednostek pracodawcy</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Ilość jednostek pracownika</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Cena</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {ppkTransactions.map((tx) => (
                      <tr key={tx.id}>
                        <td className="px-4 py-3 text-sm text-gray-900">{tx.date}</td>
                        <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">
                          {((Number(tx.employee_units) + Number(tx.employer_units)) * Number(tx.price_per_unit)).toFixed(2)} PLN
                        </td>
                        <td className="px-4 py-3 text-sm text-right">{Number(tx.employer_units).toFixed(4)}</td>
                        <td className="px-4 py-3 text-sm text-right">{Number(tx.employee_units).toFixed(4)}</td>
                        <td className="px-4 py-3 text-sm text-right">{Number(tx.price_per_unit).toFixed(4)} PLN</td>
                      </tr>
                    ))}
                    {ppkTransactions.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-4 py-3 text-center text-sm text-gray-500">Brak historii wpłat.</td>
                      </tr>
                    )}
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
                <p className="mt-2 text-sm text-gray-500">
                  Ta wartość obejmuje tylko zrealizowany wynik na transakcjach SELL. Całkowity wynik portfela może być inny,
                  bo uwzględnia też otwarte pozycje, dywidendy oraz odsetki gotówkowe.
                </p>
                {(valueData?.total_interest || 0) !== 0 && (
                  <p className="mt-2 text-sm text-emerald-600">
                    Odsetki zaksięgowane w portfelu: {(valueData?.total_interest || 0).toFixed(2)} PLN
                  </p>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-[760px] divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="min-w-[140px] px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Symbol</th>
                      <th className="min-w-[220px] px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Nazwa spółki</th>
                      <th className="min-w-[120px] px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Ostatnia sprzedaż</th>
                      <th className="min-w-[120px] px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Kapitał</th>
                      <th className="min-w-[120px] px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Zysk</th>
                      <th className="min-w-[100px] px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Zysk %</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {closedPositions.map((p) => (
                      <tr key={p.ticker}>
                        <td className="px-4 py-4 align-top text-sm font-medium text-gray-900">
                          <div className="min-w-[140px] break-all sm:break-normal">{p.ticker}</div>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-700 break-words">
                          <div className="min-w-[220px] break-words">{p.company_name || "-"}</div>
                        </td>
                        <td className="px-4 py-4 text-sm text-gray-700 whitespace-nowrap">{formatSellDate(p.last_sell_date)}</td>
                        <td className="px-4 py-4 text-sm text-right text-gray-700 whitespace-nowrap">{p.invested_capital.toFixed(2)} PLN</td>
                        <td className={cn(
                          "px-4 py-4 text-sm text-right font-medium whitespace-nowrap",
                          p.realized_profit >= 0 ? "text-green-600" : "text-red-600"
                        )}>
                          {p.realized_profit.toFixed(2)} PLN
                        </td>
                        <td className={cn(
                          "px-4 py-4 text-sm text-right font-medium whitespace-nowrap",
                          (p.profit_percent_on_capital ?? 0) >= 0 ? "text-green-600" : "text-red-600"
                        )}>
                          {p.profit_percent_on_capital === null || p.profit_percent_on_capital === undefined
                            ? "-"
                            : `${p.profit_percent_on_capital.toFixed(2)}%`}
                        </td>
                      </tr>
                    ))}
                    {closedPositions.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-6 py-4 text-center text-sm text-gray-500">Brak zamkniętych pozycji.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'closed_cycles' && (
            <div className="space-y-6">
              <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mb-6">
                <h3 className="text-lg font-medium text-gray-900">Całkowity Zrealizowany Zysk (cykle)</h3>
                <p className={cn("text-3xl font-bold mt-2", totalClosedCyclesProfit >= 0 ? "text-green-600" : "text-red-600")}>
                  {totalClosedCyclesProfit.toFixed(2)} PLN
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-[1120px] divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="min-w-[140px] px-3 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Symbol</th>
                      <th className="min-w-[80px] px-3 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Cykl</th>
                      <th className="min-w-[180px] px-3 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
                      <th className="min-w-[220px] px-3 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Nazwa spółki</th>
                      <th className="min-w-[120px] px-3 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Otwarcie</th>
                      <th className="min-w-[120px] px-3 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">Zamknięcie</th>
                      <th className="min-w-[120px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Kapitał</th>
                      <th className="min-w-[120px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Zysk</th>
                      <th className="min-w-[100px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Zysk %</th>
                      <th className="min-w-[130px] px-3 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">Stopa roczna</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {closedPositionCycles.map((p) => (
                      <tr key={`${p.ticker}-${p.cycle_id}`}>
                        <td className="px-3 py-4 align-top text-sm font-medium text-gray-900">
                          <div className="min-w-[140px] break-all sm:break-normal">{p.ticker}</div>
                        </td>
                        <td className="px-3 py-4 align-top text-sm text-gray-700 whitespace-nowrap">#{p.cycle_id}</td>
                        <td className="px-3 py-4 text-sm text-gray-700">
                          {p.is_partially_closed ? (
                            <span className="inline-flex max-w-full items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 leading-5 whitespace-normal break-words">
                              Częściowo zamknięta ({(p.remaining_quantity ?? 0).toFixed(4)} szt.)
                            </span>
                          ) : (
                            <span className="inline-flex max-w-full items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 whitespace-normal break-words">
                              Zamknięta
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-4 text-sm text-gray-700 break-words"><div className="min-w-[220px] break-words">{p.company_name || '-'}</div></td>
                        <td className="px-3 py-4 text-sm text-gray-700 whitespace-nowrap">{formatSellDate(p.opened_at)}</td>
                        <td className="px-3 py-4 text-sm text-gray-700 whitespace-nowrap">{p.closed_at ? formatSellDate(p.closed_at) : '-'}</td>
                        <td className="px-3 py-4 text-sm text-right text-gray-700 whitespace-nowrap">{p.invested_capital.toFixed(2)} PLN</td>
                        <td className={cn(
                          "px-3 py-4 text-sm text-right font-medium whitespace-nowrap",
                          p.realized_profit >= 0 ? "text-green-600" : "text-red-600"
                        )}>
                          {p.realized_profit.toFixed(2)} PLN
                        </td>
                        <td className={cn(
                          "px-3 py-4 text-sm text-right font-medium whitespace-nowrap",
                          (p.profit_percent_on_capital ?? 0) >= 0 ? "text-green-600" : "text-red-600"
                        )}>
                          {p.profit_percent_on_capital === null || p.profit_percent_on_capital === undefined
                            ? '-'
                            : `${p.profit_percent_on_capital.toFixed(2)}%`}
                        </td>
                        <td className={cn(
                          "px-3 py-4 text-sm text-right font-medium whitespace-nowrap",
                          (p.annualized_return_percent ?? 0) >= 0 ? "text-green-600" : "text-red-600"
                        )} title={p.average_invested_capital && p.holding_period_days
                          ? `Średnio zaangażowany kapitał: ${p.average_invested_capital.toFixed(2)} PLN | Okres: ${p.holding_period_days.toFixed(1)} dni`
                          : undefined}>
                          {p.annualized_return_percent === null || p.annualized_return_percent === undefined
                            ? '-'
                            : `${p.annualized_return_percent.toFixed(2)}%`}
                        </td>
                      </tr>
                    ))}
                    {closedPositionCycles.length === 0 && (
                      <tr>
                        <td colSpan={10} className="px-6 py-4 text-center text-sm text-gray-500">Brak zamkniętych lub częściowo zamkniętych pozycji cyklicznych.</td>
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
        dividendTickers={dividendTickers}
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
