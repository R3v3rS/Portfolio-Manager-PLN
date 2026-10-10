import React, { useState, useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { portfolioApi } from '../../api';
import { Holding, Portfolio } from '../../types';
import { cn } from '../../lib/utils';
import BondEditor from '../portfolio/bonds/BondEditor';
import type { BudgetAccount } from '../../api_budget';

interface TransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  portfolioId: number;
  cash?: number;
  budgetAccounts?: BudgetAccount[];
  portfolioType: 'STANDARD' | 'IKE' | 'IKZE' | 'BONDS' | 'SAVINGS' | 'PPK';
  holdings: Holding[];
  dividendTickers?: string[];
  subPortfolios?: Portfolio[];
}

type TransactionType = 'BUY' | 'DIVIDEND' | 'SAVINGS_RATE' | 'SAVINGS_INTEREST';

const TransactionModal: React.FC<TransactionModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  portfolioId,
  cash = 0,
  budgetAccounts = [],
  portfolioType,
  holdings,
  dividendTickers = [],
  subPortfolios = [],
}) => {
  const [type, setType] = useState<TransactionType>('BUY');
  const [ticker, setTicker] = useState('');
  const [subPortfolioId, setSubPortfolioId] = useState<string>('');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [amount, setAmount] = useState('');
  const [date, setDate] = useState(new Date().toLocaleDateString('sv-SE'));

  const [interestRate, setInterestRate] = useState('');
  const [commission, setCommission] = useState('');
  const [autoFxFees, setAutoFxFees] = useState(false);
  const [loading, setLoading] = useState(false);
  const buyRequest=useRef({payload:'',id:''});

  // Set default type based on portfolio type
  useEffect(() => {
    if (isOpen) {
      if (portfolioType === 'SAVINGS') setType('SAVINGS_INTEREST');
      else setType('BUY');
      
      // Reset fields
      setTicker('');
      setQuantity('');
      setPrice('');
      setAmount('');

      setInterestRate('');
      setCommission('');
      setAutoFxFees(false);
      buyRequest.current={payload:'',id:''};
      setDate(new Date().toLocaleDateString('sv-SE'));
    }
  }, [isOpen, portfolioType]);

  // Auto-calculate commission for XTB PLN
  useEffect(() => {
    if (autoFxFees && quantity && price) {
        const val = parseFloat(quantity) * parseFloat(price);
        if (!isNaN(val)) {
            setCommission((val * 0.005).toFixed(2));
        }
    }
  }, [autoFxFees, quantity, price]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const subId = subPortfolioId ? parseInt(subPortfolioId) : null;
    
    try {
      if (type === 'BUY') {
        const payload={
          portfolio_id: portfolioId,
          ticker,
          quantity: parseFloat(quantity),
          price: parseFloat(price),
          date,
          commission: parseFloat(commission) || 0,
          auto_fx_fees: autoFxFees,
          sub_portfolio_id: subId
        };
        const fingerprint=JSON.stringify(payload);
        if(buyRequest.current.payload!==fingerprint)buyRequest.current={payload:fingerprint,id:crypto.randomUUID()};
        await portfolioApi.buy(payload,buyRequest.current.id);
      } else if (type === 'DIVIDEND') {
        await portfolioApi.addDividend({
          portfolio_id: portfolioId,
          ticker,
          amount: parseFloat(amount),
          date,
          sub_portfolio_id: subId
        });
      } else if (type === 'SAVINGS_RATE') {
        await portfolioApi.updateSavingsRate({
          portfolio_id: portfolioId,
          rate: parseFloat(interestRate)
        });
      } else if (type === 'SAVINGS_INTEREST') {
        await portfolioApi.addSavingsInterest({
          portfolio_id: portfolioId,
          amount: parseFloat(amount),
          date
        });
      }

      onSuccess();
      onClose();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : 'Transaction failed');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;
  if (portfolioType === 'BONDS') return <BondEditor pid={portfolioId} cash={cash} accounts={budgetAccounts} onClose={onClose} onSaved={() => { onSuccess(); onClose(); }}/>;

  const tickerOptions = Array.from(
    new Set([
      ...holdings.map((h) => h.ticker),
      ...dividendTickers,
    ])
  ).sort((a, b) => a.localeCompare(b));

  const renderTypeSelector = () => {

    
    if (portfolioType === 'SAVINGS') {
        return (
            <div className="flex rounded-md shadow-sm mb-6">
                <button
                type="button"
                onClick={() => setType('SAVINGS_INTEREST')}
                className={cn(
                    "flex-1 py-2 text-sm font-medium border first:rounded-l-md focus:z-10 focus:ring-2 focus:ring-emerald-500",
                    type === 'SAVINGS_INTEREST' 
                    ? "bg-emerald-600 text-white border-emerald-600" 
                    : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
                )}
                >
                Dodaj Odsetki
                </button>
                <button
                type="button"
                onClick={() => setType('SAVINGS_RATE')}
                className={cn(
                    "flex-1 py-2 text-sm font-medium border -ml-px last:rounded-r-md focus:z-10 focus:ring-2 focus:ring-emerald-500",
                    type === 'SAVINGS_RATE' 
                    ? "bg-emerald-600 text-white border-emerald-600" 
                    : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
                )}
                >
                Zmień %
                </button>
            </div>
        );
    }

    if (portfolioType === 'IKE') {
      return (
        <div className="grid grid-cols-3 rounded-md shadow-sm mb-6">
          <button
            type="button"
            onClick={() => setType('BUY')}
            className={cn(
              "py-2 text-sm font-medium border first:rounded-l-md focus:z-10 focus:ring-2 focus:ring-indigo-500",
              type === 'BUY'
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
            )}
          >
            Kup Akcje
          </button>
          <button
            type="button"
            onClick={() => setType('DIVIDEND')}
            className={cn(
              "py-2 text-sm font-medium border -ml-px focus:z-10 focus:ring-2 focus:ring-indigo-500",
              type === 'DIVIDEND'
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
            )}
          >
            Dywidenda
          </button>
          <button
            type="button"
            onClick={() => setType('SAVINGS_INTEREST')}
            className={cn(
              "py-2 text-sm font-medium border -ml-px last:rounded-r-md focus:z-10 focus:ring-2 focus:ring-indigo-500",
              type === 'SAVINGS_INTEREST'
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
            )}
          >
            Odsetki
          </button>
        </div>
      );
    }

    return (
      <div className="flex rounded-md shadow-sm mb-6">
        <button
          type="button"
          onClick={() => setType('BUY')}
          className={cn(
            "flex-1 py-2 text-sm font-medium border first:rounded-l-md focus:z-10 focus:ring-2 focus:ring-blue-500",
            type === 'BUY' 
              ? "bg-blue-600 text-white border-blue-600" 
              : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
          )}
        >
          Kup Akcje
        </button>
        <button
          type="button"
          onClick={() => setType('DIVIDEND')}
          className={cn(
            "flex-1 py-2 text-sm font-medium border -ml-px last:rounded-r-md focus:z-10 focus:ring-2 focus:ring-blue-500",
            type === 'DIVIDEND' 
              ? "bg-indigo-600 text-white border-indigo-600" 
              : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
          )}
        >
          Dywidenda
        </button>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex justify-between items-center p-4 border-b">
          <h2 className="text-lg font-medium text-gray-900">
            {type === 'BUY' && 'Kup Akcje'}
            {type === 'DIVIDEND' && 'Rejestracja Dywidendy'}

            {type === 'SAVINGS_INTEREST' && 'Dodaj Odsetki'}
            {type === 'SAVINGS_RATE' && 'Aktualizuj Oprocentowanie'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {renderTypeSelector()}

          {/* Sub-portfolio selector (for BUY and DIVIDEND) */}
          {(type === 'BUY' || type === 'DIVIDEND') && subPortfolios.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700">Sub-portfel (opcjonalnie)</label>
              <select
                value={subPortfolioId}
                onChange={(e) => setSubPortfolioId(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              >
                <option value="">Portfel Główny (Parent)</option>
                {subPortfolios.filter(p => !p.is_archived).map((sp) => (
                  <option key={sp.id} value={sp.id}>{sp.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* BUY Fields */}
          {type === 'BUY' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700">Symbol (Ticker)</label>
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  list="known-ticker-options"
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  placeholder="np. AAPL"
                  required
                />
                <datalist id="known-ticker-options">
                  {tickerOptions.map((symbol) => (
                    <option key={symbol} value={symbol} />
                  ))}
                </datalist>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Ilość</label>
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
                <label className="block text-sm font-medium text-gray-700">Cena za sztukę (PLN)</label>
                <input
                  type="number"
                  step="0.01"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  required
                />
              </div>

              <div className="flex items-center space-x-2 my-2">
                <input
                  id="autoFxFees"
                  type="checkbox"
                  checked={autoFxFees}
                  onChange={(e) => setAutoFxFees(e.target.checked)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="autoFxFees" className="text-sm font-medium text-gray-700">
                  Konto PLN w XTB (Prowizja FX 0.5%)
                </label>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Prowizja (PLN)</label>
                <input
                  type="number"
                  step="0.01"
                  value={commission}
                  onChange={(e) => setCommission(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  placeholder="0.00"
                />
              </div>
            </>
          )}

          {/* DIVIDEND Fields */}
          {type === 'DIVIDEND' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700">Symbol (Ticker)</label>
                <select
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  required
                >
                  <option value="">Wybierz akcję</option>
                  {tickerOptions.map((symbol) => (
                    <option key={symbol} value={symbol}>{symbol}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Kwota Dywidendy (PLN)</label>
                <input
                  type="number"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  required
                />
              </div>
            </>
          )}

          {/* SAVINGS Fields */}
          {type === 'SAVINGS_INTEREST' && (
             <div>
                <label className="block text-sm font-medium text-gray-700">Kwota (PLN)</label>
                <input
                    type="number"
                    step="0.01"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500 p-2 border"
                    required
                />
            </div>
          )}

          {type === 'SAVINGS_RATE' && (
             <div>
                <label className="block text-sm font-medium text-gray-700">Nowe Oprocentowanie (%)</label>
                <input
                    type="number"
                    step="0.01"
                    value={interestRate}
                    onChange={(e) => setInterestRate(e.target.value)}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500 p-2 border"
                    required
                />
                 <p className="mt-2 text-xs text-gray-500 italic text-center">Zmiana oprocentowania automatycznie skapitalizuje obecne odsetki.</p>
            </div>
          )}

          {/* Date Field (Common) */}
          {type !== 'SAVINGS_RATE' && (
            <div>
                <label className="block text-sm font-medium text-gray-700">
                    Data
                </label>
                <input
                type="date"
                max={new Date().toLocaleDateString('sv-SE')}
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                required
                />
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className={cn(
              "w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2",
              (type === 'BUY' || type === 'DIVIDEND') ? "bg-blue-600 hover:bg-blue-700 focus:ring-blue-500" : 

              "bg-emerald-600 hover:bg-emerald-700 focus:ring-emerald-500",
              loading && "opacity-50 cursor-not-allowed"
            )}
          >
            {loading ? 'Przetwarzanie...' : 'Zatwierdź'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default TransactionModal;
