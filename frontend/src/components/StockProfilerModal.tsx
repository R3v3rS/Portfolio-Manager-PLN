import React, { useEffect, useState } from 'react';
import { X, TrendingUp, TrendingDown, AlertCircle, Activity, DollarSign, Users } from 'lucide-react';
import { radarApi } from '../api_radar';
import { StockAnalysisData } from '../types';

interface StockProfilerModalProps {
  ticker: string | null;
  onClose: () => void;
}

const StockProfilerModal: React.FC<StockProfilerModalProps> = ({ ticker, onClose }) => {
  const [data, setData] = useState<StockAnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await radarApi.getAnalysis(ticker);
        setData(result);
      } catch (err) {
        console.error(err);
        setError(err instanceof Error ? err.message : 'Nie udało się pobrać danych analitycznych.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ticker]);

  if (!ticker) return null;

  const formatNumber = (val: number | null, decimals = 2) => {
    if (val === null || val === undefined) return 'Brak danych';
    return val.toFixed(decimals);
  };

  const formatPercent = (val: number | null) => {
    if (val === null || val === undefined) return 'Brak danych';
    return `${(val * 100).toFixed(2)}%`;
  };

  const formatRawPercent = (val: number | null) => {
     if (val === null || val === undefined) return 'Brak danych';
     return `${val.toFixed(2)}%`;
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
      <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        
        {/* Background overlay */}
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={onClose}></div>

        <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

        {/* Modal panel */}
        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full">
          
          {/* Header */}
          <div className="bg-gray-50 px-4 py-3 sm:px-6 flex justify-between items-center border-b border-gray-200">
            <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
              Analiza Spółki: <span className="font-bold text-blue-600">{ticker}</span>
            </h3>
            <button
              type="button"
              className="bg-white rounded-md text-gray-400 hover:text-gray-500 focus:outline-none"
              onClick={onClose}
            >
              <span className="sr-only">Zamknij</span>
              <X className="h-6 w-6" />
            </button>
          </div>

          {/* Content */}
          <div className="px-4 py-5 sm:p-6 bg-gray-50 min-h-[300px]">
            {loading ? (
              <div className="flex flex-col justify-center items-center h-full py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                <p className="mt-4 text-gray-500">Pobieranie danych z rynku...</p>
              </div>
            ) : error ? (
              <div className="flex flex-col justify-center items-center h-full py-12 text-red-500">
                <AlertCircle className="h-12 w-12 mb-4" />
                <p>{error}</p>
              </div>
            ) : data ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                
                {/* Card 1: Fundamentals */}
                <div className="bg-white overflow-hidden shadow rounded-lg border border-gray-100">
                  <div className="px-4 py-5 sm:p-6">
                    <div className="flex items-center mb-4">
                        <div className="p-2 bg-green-100 rounded-lg mr-3">
                            <DollarSign className="h-6 w-6 text-green-600" />
                        </div>
                        <h4 className="text-lg font-medium text-gray-900">Fundamenty</h4>
                    </div>
                    <dl className="space-y-3">
                      <div className="flex justify-between">
                        <dt className="text-sm font-medium text-gray-500">C/Z (P/E)</dt>
                        <dd className="text-sm font-bold text-gray-900">{formatNumber(data.fundamentals.trailingPE)}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-sm font-medium text-gray-500">C/WK (P/B)</dt>
                        <dd className="text-sm font-bold text-gray-900">{formatNumber(data.fundamentals.priceToBook)}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-sm font-medium text-gray-500">ROE</dt>
                        <dd className="text-sm font-bold text-gray-900">{formatPercent(data.fundamentals.returnOnEquity)}</dd>
                      </div>
                       <div className="flex justify-between">
                        <dt className="text-sm font-medium text-gray-500">Payout Ratio</dt>
                        <dd className="text-sm font-bold text-gray-900">{formatPercent(data.fundamentals.payoutRatio)}</dd>
                      </div>
                    </dl>
                  </div>
                </div>

                {/* Card 2: Analyst Consensus */}
                <div className="bg-white overflow-hidden shadow rounded-lg border border-gray-100">
                  <div className="px-4 py-5 sm:p-6">
                     <div className="flex items-center mb-4">
                        <div className="p-2 bg-blue-100 rounded-lg mr-3">
                            <Users className="h-6 w-6 text-blue-600" />
                        </div>
                        <h4 className="text-lg font-medium text-gray-900">Konsensus</h4>
                    </div>
                    <dl className="space-y-3">
                      <div className="flex justify-between">
                        <dt className="text-sm font-medium text-gray-500">Cena Docelowa</dt>
                        <dd className="text-sm font-bold text-gray-900">{formatNumber(data.analyst.targetMeanPrice)}</dd>
                      </div>
                      <div className="flex justify-between items-center">
                        <dt className="text-sm font-medium text-gray-500">Potencjał</dt>
                        <dd className={`text-sm font-bold ${
                            (data.analyst.upsidePotential || 0) > 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                           {data.analyst.upsidePotential !== null ? (
                               <span className="flex items-center">
                                   {(data.analyst.upsidePotential || 0) > 0 ? <TrendingUp className="h-3 w-3 mr-1"/> : <TrendingDown className="h-3 w-3 mr-1"/>}
                                   {formatRawPercent(data.analyst.upsidePotential)}
                               </span>
                           ) : 'Brak danych'}
                        </dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-sm font-medium text-gray-500">Rekomendacja</dt>
                        <dd className="text-sm font-bold text-gray-900 uppercase">
                            {data.analyst.recommendationKey || 'Brak'}
                        </dd>
                      </div>
                    </dl>
                  </div>
                </div>

                {/* Card 3: Technicals */}
                <div className="bg-white overflow-hidden shadow rounded-lg border border-gray-100">
                  <div className="px-4 py-5 sm:p-6">
                    <div className="flex items-center mb-4">
                        <div className="p-2 bg-purple-100 rounded-lg mr-3">
                            <Activity className="h-6 w-6 text-purple-600" />
                        </div>
                        <h4 className="text-lg font-medium text-gray-900">Techniczne</h4>
                    </div>
                    <dl className="space-y-3">
                      <div className="flex justify-between items-center">
                        <dt className="text-sm font-medium text-gray-500">RSI (14)</dt>
                        <dd className="flex items-center space-x-2">
                            <span className="text-sm font-bold text-gray-900">{formatNumber(data.technicals.rsi14)}</span>
                            {data.technicals.rsi14 !== null && data.technicals.rsi14 > 70 && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                                    Wykupiona
                                </span>
                            )}
                            {data.technicals.rsi14 !== null && data.technicals.rsi14 < 30 && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                    Wyprzedana
                                </span>
                            )}
                        </dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-sm font-medium text-gray-500">SMA 50</dt>
                        <dd className="text-sm font-bold text-gray-900">{formatNumber(data.technicals.sma50)}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-sm font-medium text-gray-500">SMA 200</dt>
                        <dd className="text-sm font-bold text-gray-900">{formatNumber(data.technicals.sma200)}</dd>
                      </div>
                    </dl>
                  </div>
                </div>

              </div>
            ) : null}
          </div>
          
          {/* Footer */}
          <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse border-t border-gray-200">
            <button
              type="button"
              className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:ml-3 sm:w-auto sm:text-sm"
              onClick={onClose}
            >
              Zamknij
            </button>
          </div>

        </div>
      </div>
    </div>
  );
};

export default StockProfilerModal;
