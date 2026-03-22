import React, { useEffect, useState } from 'react';
import { X, TrendingUp, TrendingDown, AlertCircle, Activity, DollarSign, Users, BarChart3, ShieldCheck, PieChart, Info } from 'lucide-react';
import { radarApi } from '../api_radar';
import { extractErrorMessageFromUnknown } from '../http/response';
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
        setData(null);
        setError(extractErrorMessageFromUnknown(err));
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [ticker]);

  if (!ticker) return null;

  const formatNumber = (val: number | null, decimals = 2) => {
    if (val === null || val === undefined) return 'Brak danych';
    return val.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  };

  const formatLargeNumber = (val: number | null) => {
    if (val === null || val === undefined) return 'Brak danych';
    if (val >= 1e9) return `${(val / 1e9).toFixed(2)}B`;
    if (val >= 1e6) return `${(val / 1e6).toFixed(2)}M`;
    return val.toLocaleString();
  };

  const formatPercent = (val: number | null) => {
    if (val === null || val === undefined) return 'Brak danych';
    return `${(val * 100).toFixed(2)}%`;
  };

  const formatRawPercent = (val: number | null) => {
     if (val === null || val === undefined) return 'Brak danych';
     return `${val.toFixed(2)}%`;
  }

  const getScoreColor = (score: number | null) => {
    if (score === null) return 'text-gray-400';
    if (score >= 70) return 'text-green-600';
    if (score >= 40) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreBg = (score: number | null) => {
    if (score === null) return 'bg-gray-100';
    if (score >= 70) return 'bg-green-100';
    if (score >= 40) return 'bg-yellow-100';
    return 'bg-red-100';
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
      <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        
        {/* Background overlay */}
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={onClose}></div>

        <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

        {/* Modal panel */}
        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-5xl sm:w-full">
          
          {/* Header */}
          <div className="bg-white px-4 py-4 sm:px-6 flex justify-between items-center border-b border-gray-200">
            <div className="flex items-center space-x-4">
              <h3 className="text-xl leading-6 font-bold text-gray-900" id="modal-title">
                {ticker}
              </h3>
              {data && (
                <div className={`px-3 py-1 rounded-full text-sm font-bold flex items-center ${getScoreBg(data.score)} ${getScoreColor(data.score)}`}>
                  Score: {data.score}/100
                </div>
              )}
            </div>
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
          <div className="px-4 py-5 sm:p-6 bg-gray-50 min-h-[400px]">
            {loading ? (
              <div className="flex flex-col justify-center items-center h-full py-24">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                <p className="mt-4 text-gray-500">Pobieranie danych z rynku...</p>
              </div>
            ) : error ? (
              <div className="flex flex-col justify-center items-center h-full py-24 text-red-500">
                <AlertCircle className="h-12 w-12 mb-4" />
                <p className="font-medium text-lg">{error}</p>
                <button 
                  onClick={() => window.location.reload()}
                  className="mt-4 text-blue-600 hover:underline"
                >
                  Spróbuj ponownie
                </button>
              </div>
            ) : data ? (
              <div className="space-y-6">
                
                {/* Score Breakdown */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Quality Score</p>
                      <p className="text-2xl font-bold text-gray-900">{data.details.quality}/40</p>
                    </div>
                    <div className="p-2 bg-blue-50 rounded-full">
                      <ShieldCheck className="h-6 w-6 text-blue-600" />
                    </div>
                  </div>
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Growth Score</p>
                      <p className="text-2xl font-bold text-gray-900">{data.details.growth}/30</p>
                    </div>
                    <div className="p-2 bg-green-50 rounded-full">
                      <BarChart3 className="h-6 w-6 text-green-600" />
                    </div>
                  </div>
                  <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100 flex items-center justify-between">
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Risk Score</p>
                      <p className="text-2xl font-bold text-gray-900">{data.details.risk}/30</p>
                    </div>
                    <div className="p-2 bg-red-50 rounded-full">
                      <AlertCircle className="h-6 w-6 text-red-600" />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  
                  {/* Card 1: Quality & Fundamentals */}
                  <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
                    <div className="px-4 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
                      <DollarSign className="h-5 w-5 text-blue-600 mr-2" />
                      <h4 className="font-bold text-gray-900">Jakość i Rentowność</h4>
                    </div>
                    <div className="p-4">
                      <dl className="space-y-3">
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Marża Operacyjna</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatPercent(data.fundamentals.operatingMargins)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Marża Zysku</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatPercent(data.fundamentals.profitMargins)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">ROE</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatPercent(data.fundamentals.returnOnEquity)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">ROA</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatPercent(data.fundamentals.returnOnAssets)}</dd>
                        </div>
                        <div className="flex justify-between border-t pt-2 mt-2">
                          <dt className="text-sm text-gray-600">Free Cash Flow</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatLargeNumber(data.fundamentals.freeCashflow)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Operating Cash Flow</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatLargeNumber(data.fundamentals.operatingCashflow)}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>

                  {/* Card 2: Growth */}
                  <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
                    <div className="px-4 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
                      <BarChart3 className="h-5 w-5 text-green-600 mr-2" />
                      <h4 className="font-bold text-gray-900">Wzrost</h4>
                    </div>
                    <div className="p-4">
                      <dl className="space-y-3">
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Wzrost Przychodów (r/r)</dt>
                          <dd className={`text-sm font-semibold ${data.growth.revenueGrowth && data.growth.revenueGrowth > 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {formatPercent(data.growth.revenueGrowth)}
                          </dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Wzrost Zysków (r/r)</dt>
                          <dd className={`text-sm font-semibold ${data.growth.earningsGrowth && data.growth.earningsGrowth > 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {formatPercent(data.growth.earningsGrowth)}
                          </dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Wzrost Zysków (kwartalny)</dt>
                          <dd className={`text-sm font-semibold ${data.growth.earningsQuarterlyGrowth && data.growth.earningsQuarterlyGrowth > 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {formatPercent(data.growth.earningsQuarterlyGrowth)}
                          </dd>
                        </div>
                        <div className="flex justify-between border-t pt-2 mt-2">
                          <dt className="text-sm text-gray-600">C/Z (Trailing P/E)</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatNumber(data.fundamentals.trailingPE)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">C/WK (Price to Book)</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatNumber(data.fundamentals.priceToBook)}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>

                  {/* Card 3: Risk & Stability */}
                  <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
                    <div className="px-4 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
                      <ShieldCheck className="h-5 w-5 text-red-600 mr-2" />
                      <h4 className="font-bold text-gray-900">Ryzyko i Stabilność</h4>
                    </div>
                    <div className="p-4">
                      <dl className="space-y-3">
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Debt to Equity</dt>
                          <dd className={`text-sm font-semibold ${(data.risk.debtToEquity || 0) > 150 ? 'text-red-600' : 'text-gray-900'}`}>
                            {formatNumber(data.risk.debtToEquity)}
                          </dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Current Ratio</dt>
                          <dd className={`text-sm font-semibold ${(data.risk.currentRatio || 0) < 1.0 ? 'text-red-600' : 'text-green-600'}`}>
                            {formatNumber(data.risk.currentRatio)}
                          </dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Quick Ratio</dt>
                          <dd className={`text-sm font-semibold ${(data.risk.quickRatio || 0) < 1.0 ? 'text-red-600' : 'text-green-600'}`}>
                            {formatNumber(data.risk.quickRatio)}
                          </dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Beta (Zmienność)</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatNumber(data.risk.beta)}</dd>
                        </div>
                        <div className="flex justify-between border-t pt-2 mt-2">
                          <dt className="text-sm text-gray-600">Payout Ratio</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatPercent(data.fundamentals.payoutRatio)}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>

                  {/* Card 4: Market & Sentiment */}
                  <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
                    <div className="px-4 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
                      <PieChart className="h-5 w-5 text-orange-600 mr-2" />
                      <h4 className="font-bold text-gray-900">Rynek i Sentyment</h4>
                    </div>
                    <div className="p-4">
                      <dl className="space-y-3">
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Udział Instytucji</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatPercent(data.market.heldPercentInstitutions)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Udział Insiderów</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatPercent(data.market.heldPercentInsiders)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Short Interest</dt>
                          <dd className={`text-sm font-semibold ${(data.market.shortPercentOfFloat || 0) > 0.1 ? 'text-red-600' : 'text-gray-900'}`}>
                            {formatPercent(data.market.shortPercentOfFloat)}
                          </dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Short Ratio</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatNumber(data.market.shortRatio)}</dd>
                        </div>
                        <div className="flex justify-between border-t pt-2 mt-2">
                          <dt className="text-sm text-gray-600">Średni Wolumen</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatLargeNumber(data.market.averageVolume)}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>

                  {/* Card 5: Analyst Consensus */}
                  <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
                    <div className="px-4 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
                      <Users className="h-5 w-5 text-indigo-600 mr-2" />
                      <h4 className="font-bold text-gray-900">Analitycy</h4>
                    </div>
                    <div className="p-4">
                      <dl className="space-y-3">
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Cena Docelowa</dt>
                          <dd className="text-sm font-bold text-gray-900">{formatNumber(data.analyst.targetMeanPrice)}</dd>
                        </div>
                        <div className="flex justify-between items-center">
                          <dt className="text-sm text-gray-600">Potencjał</dt>
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
                          <dt className="text-sm text-gray-600">Rekomendacja</dt>
                          <dd className="text-sm font-bold text-gray-900 uppercase">
                              {data.analyst.recommendationKey || 'Brak'}
                          </dd>
                        </div>
                        <div className="flex justify-between border-t pt-2 mt-2">
                          <dt className="text-sm text-gray-600">Zakres 52-tyg (L)</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatNumber(data.market.fiftyTwoWeekLow)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">Zakres 52-tyg (H)</dt>
                          <dd className="text-sm font-semibold text-gray-900">{formatNumber(data.market.fiftyTwoWeekHigh)}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>

                  {/* Card 6: Technicals */}
                  <div className="bg-white overflow-hidden shadow-sm rounded-lg border border-gray-200">
                    <div className="px-4 py-4 border-b border-gray-100 bg-gray-50 flex items-center">
                      <Activity className="h-5 w-5 text-purple-600 mr-2" />
                      <h4 className="font-bold text-gray-900">Analiza Techniczna</h4>
                    </div>
                    <div className="p-4">
                      <dl className="space-y-3">
                        <div className="flex justify-between items-center">
                          <dt className="text-sm text-gray-600">RSI (14)</dt>
                          <dd className="flex items-center space-x-2">
                              <span className={`text-sm font-bold ${
                                data.technicals.rsi14 !== null && (data.technicals.rsi14 > 70 || data.technicals.rsi14 < 30) ? 'text-orange-600' : 'text-gray-900'
                              }`}>{formatNumber(data.technicals.rsi14)}</span>
                              {data.technicals.rsi14 !== null && data.technicals.rsi14 > 70 && (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 uppercase">
                                      Wykupiona
                                  </span>
                              )}
                              {data.technicals.rsi14 !== null && data.technicals.rsi14 < 30 && (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-800 uppercase">
                                      Wyprzedana
                                  </span>
                              )}
                          </dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">SMA 50</dt>
                          <dd className="text-sm font-bold text-gray-900">{formatNumber(data.technicals.sma50)}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt className="text-sm text-gray-600">SMA 200</dt>
                          <dd className="text-sm font-bold text-gray-900">{formatNumber(data.technicals.sma200)}</dd>
                        </div>
                      </dl>
                      <div className="mt-6 flex items-start p-2 bg-blue-50 rounded text-xs text-blue-800">
                        <Info className="h-4 w-4 mr-2 mt-0.5 flex-shrink-0" />
                        <p>Dane techniczne oparte na historycznych cenach zamknięcia z ostatniego roku.</p>
                      </div>
                    </div>
                  </div>

                </div>
              </div>
            ) : null}
          </div>
          
          {/* Footer */}
          <div className="bg-white px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse border-t border-gray-200">
            <button
              type="button"
              className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-6 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:ml-3 sm:w-auto sm:text-sm"
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
