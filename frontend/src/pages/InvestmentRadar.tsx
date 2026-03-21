import React, { useState, useEffect } from 'react';
import { Radar, Plus, Trash2, TrendingUp, TrendingDown, Calendar, AlertCircle, RefreshCw, PauseCircle, PlayCircle } from 'lucide-react';
import { RadarItem } from '../types';
import StockProfilerModal from '../components/StockProfilerModal';
import { radarApi } from '../api_radar';

const InvestmentRadar: React.FC = () => {
  const [radarItems, setRadarItems] = useState<RadarItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newTicker, setNewTicker] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(false);
  const [refreshingTicker, setRefreshingTicker] = useState<string | null>(null);

  const fetchRadarData = async (refresh = false) => {
    setIsLoading(true);
    try {
      const data = await radarApi.getAll(refresh);
      setRadarItems(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching radar data:', err);
      setError(err instanceof Error ? err.message : 'Nie udało się pobrać danych radaru.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRadarData(autoRefreshEnabled);
  }, [autoRefreshEnabled]);

  const refreshSelectedTickers = async (tickers?: string[]) => {
    try {
      await radarApi.refresh(tickers);

      await fetchRadarData(false);
    } catch (err) {
      console.error('Error refreshing radar:', err);
      setError(err instanceof Error ? err.message : 'Nie udało się odświeżyć danych.');
    }
  };

  const handleRefreshAll = async () => {
    setRefreshingTicker('ALL');
    await refreshSelectedTickers();
    setRefreshingTicker(null);
  };

  const handleRefreshTicker = async (ticker: string) => {
    setRefreshingTicker(ticker);
    await refreshSelectedTickers([ticker]);
    setRefreshingTicker(null);
  };

  const handleAddTicker = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTicker.trim()) return;

    try {
      await radarApi.addToWatchlist(newTicker.toUpperCase());

      setNewTicker('');
      fetchRadarData(false);
    } catch (err) {
      console.error('Error adding ticker:', err);
      setError(err instanceof Error ? err.message : 'Nie udało się dodać tickera.');
    }
  };

  const handleRemoveTicker = async (ticker: string) => {
    if (!confirm(`Czy na pewno chcesz usunąć ${ticker} z obserwowanych?`)) return;

    try {
      await radarApi.removeFromWatchlist(ticker);

      fetchRadarData(false);
    } catch (err) {
      console.error('Error removing ticker:', err);
      setError(err instanceof Error ? err.message : 'Nie udało się usunąć tickera.');
    }
  };

  const formatPercent = (value: number | null) => {
    if (value === null) return '-';
    return `${value.toFixed(2)}%`;
  };

  const formatChangePercent = (value: number | null) => {
    if (value === null) return '-';
    return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Brak';
    return new Date(dateStr).toLocaleDateString('pl-PL');
  };

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return 'Brak';
    return new Date(dateStr).toLocaleString('pl-PL');
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center">
            <Radar className="mr-2 h-8 w-8 text-blue-600" />
            Radar Inwestycyjny
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Monitoruj swoje aktywa oraz obserwowane spółki w jednym miejscu.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setAutoRefreshEnabled((prev) => !prev)}
            className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-md border ${autoRefreshEnabled ? 'bg-green-50 border-green-300 text-green-700' : 'bg-yellow-50 border-yellow-300 text-yellow-700'}`}
          >
            {autoRefreshEnabled ? <PlayCircle className="mr-2 h-4 w-4" /> : <PauseCircle className="mr-2 h-4 w-4" />}
            {autoRefreshEnabled ? 'Auto-odświeżanie: WŁ.' : 'Auto-odświeżanie: WYŁ.'}
          </button>
          <button
            type="button"
            onClick={handleRefreshAll}
            disabled={isLoading || refreshingTicker === 'ALL'}
            className="inline-flex items-center px-3 py-2 text-sm font-medium rounded-md border border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100 disabled:opacity-50"
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshingTicker === 'ALL' ? 'animate-spin' : ''}`} />
            Odśwież wszystkie
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <AlertCircle className="h-5 w-5 text-red-400" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white shadow rounded-lg p-6">
        <form onSubmit={handleAddTicker} className="flex gap-4 items-end">
          <div className="flex-1 max-w-xs">
            <label htmlFor="ticker" className="block text-sm font-medium text-gray-700 mb-1">
              Dodaj spółkę do obserwacji
            </label>
            <input
              type="text"
              id="ticker"
              className="shadow-sm focus:ring-blue-500 focus:border-blue-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border"
              placeholder="np. NVDA, CDR.WA"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={isLoading || !newTicker.trim()}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            <Plus className="mr-2 h-4 w-4" />
            Dodaj do obserwowanych
          </button>
        </form>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Cena</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">1D %</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">7D %</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">1M %</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">1Y %</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Posiadane</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Najbliższy Raport</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Odcięcie Dywidendy</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Stopa Dyw.</th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ostatni update</th>
                <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Akcje</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading ? (
                <tr><td colSpan={12} className="px-6 py-4 text-center text-gray-500">Ładowanie danych...</td></tr>
              ) : radarItems.length === 0 ? (
                <tr><td colSpan={12} className="px-6 py-4 text-center text-gray-500">Brak danych. Dodaj spółki do obserwowanych lub kup aktywa.</td></tr>
              ) : (
                radarItems.map((item) => (
                  <tr key={item.ticker} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      <button onClick={() => setSelectedTicker(item.ticker)} className="text-blue-600 hover:text-blue-900 hover:underline cursor-pointer focus:outline-none">{item.ticker}</button>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">{item.price !== null ? item.price.toFixed(2) : '-'}</td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${(item.change_1d || 0) > 0 ? 'text-green-600' : (item.change_1d || 0) < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      <div className="flex items-center justify-end">{(item.change_1d || 0) > 0 ? <TrendingUp className="h-4 w-4 mr-1" /> : (item.change_1d || 0) < 0 ? <TrendingDown className="h-4 w-4 mr-1" /> : null}{formatChangePercent(item.change_1d)}</div>
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${(item.change_7d || 0) > 0 ? 'text-green-600' : (item.change_7d || 0) < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      <div className="flex items-center justify-end">{(item.change_7d || 0) > 0 ? <TrendingUp className="h-4 w-4 mr-1" /> : (item.change_7d || 0) < 0 ? <TrendingDown className="h-4 w-4 mr-1" /> : null}{formatChangePercent(item.change_7d)}</div>
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${(item.change_1m || 0) > 0 ? 'text-green-600' : (item.change_1m || 0) < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      <div className="flex items-center justify-end">{(item.change_1m || 0) > 0 ? <TrendingUp className="h-4 w-4 mr-1" /> : (item.change_1m || 0) < 0 ? <TrendingDown className="h-4 w-4 mr-1" /> : null}{formatChangePercent(item.change_1m)}</div>
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${(item.change_1y || 0) > 0 ? 'text-green-600' : (item.change_1y || 0) < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      <div className="flex items-center justify-end">{(item.change_1y || 0) > 0 ? <TrendingUp className="h-4 w-4 mr-1" /> : (item.change_1y || 0) < 0 ? <TrendingDown className="h-4 w-4 mr-1" /> : null}{formatChangePercent(item.change_1y)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">{item.quantity > 0 ? Number(item.quantity.toFixed(4)) : '-'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500"><div className="flex items-center">{item.next_earnings && <Calendar className="h-4 w-4 mr-1 text-gray-400" />}{formatDate(item.next_earnings)}</div></td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500"><div className="flex items-center">{item.ex_dividend_date && <Calendar className="h-4 w-4 mr-1 text-gray-400" />}{formatDate(item.ex_dividend_date)}</div></td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">{formatPercent(item.dividend_yield)}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatDateTime(item.last_updated_at)}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-center text-sm font-medium">
                      <div className="inline-flex items-center gap-2">
                        <button onClick={() => handleRefreshTicker(item.ticker)} className="text-blue-600 hover:text-blue-900 transition-colors" title="Odśwież dane tej spółki">
                          <RefreshCw className={`h-5 w-5 ${refreshingTicker === item.ticker ? 'animate-spin' : ''}`} />
                        </button>
                        {item.is_watched && (
                          <button onClick={() => handleRemoveTicker(item.ticker)} className="text-red-600 hover:text-red-900 transition-colors" title="Usuń z obserwowanych">
                            <Trash2 className="h-5 w-5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedTicker && <StockProfilerModal ticker={selectedTicker} onClose={() => setSelectedTicker(null)} />}
    </div>
  );
};

export default InvestmentRadar;
