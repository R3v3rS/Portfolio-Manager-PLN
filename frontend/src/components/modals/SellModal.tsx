import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import api from '../../api';
import { Holding } from '../../types';
import { cn } from '../../lib/utils';

interface SellModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  portfolioId: number;
  holding: Holding | null;
}

const SellModal: React.FC<SellModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  portfolioId,
  holding,
}) => {
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [priceNative, setPriceNative] = useState('');
  const [tradeCurrency, setTradeCurrency] = useState('PLN');
  const [fxRate, setFxRate] = useState('1');
  const [commission, setCommission] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && holding) {
      setQuantity(holding.quantity.toString());
      setPrice((holding.current_price || holding.average_buy_price).toString());
      setPriceNative((holding.avg_buy_price_native || holding.average_buy_price).toString());
      setTradeCurrency(holding.instrument_currency || 'PLN');
      setFxRate((holding.avg_buy_fx_rate || 1).toString());
      setCommission('');
      setDate(new Date().toISOString().split('T')[0]);
    }
  }, [isOpen, holding]);

  useEffect(() => {
    if (tradeCurrency === 'PLN') {
      setFxRate('1');
    }
  }, [tradeCurrency]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!holding) return;
    
    setLoading(true);
    try {
      await api.post('/sell', {
        portfolio_id: portfolioId,
        ticker: holding.ticker,
        quantity: parseFloat(quantity),
        price: parseFloat(priceNative) || parseFloat(price),
        price_native: parseFloat(priceNative),
        trade_currency: tradeCurrency,
        fx_rate: parseFloat(fxRate),
        commission_native: parseFloat(commission) || 0,
        date
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.error || 'Transaction failed');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen || !holding) return null;

  const quantityValue = parseFloat(quantity) || 0;
  const nativePriceValue = parseFloat(priceNative) || 0;
  const grossNative = quantityValue * nativePriceValue;
  const commissionValue = parseFloat(commission) || grossNative * 0.005;
  const totalNative = grossNative - commissionValue;
  const totalPln = totalNative * (parseFloat(fxRate) || 1);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex justify-between items-center p-4 border-b bg-red-50">
          <h2 className="text-lg font-medium text-red-900">Sprzedaj {holding.ticker}</h2>
          <button onClick={onClose} className="text-red-400 hover:text-red-500">
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Ilość (Posiadasz: {holding.quantity})</label>
            <input
              type="number"
              step="any"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500 p-2 border"
              required
              max={holding.quantity}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Cena Sprzedaży (PLN)</label>
            <input
              type="number"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500 p-2 border"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">price_native</label>
            <input
              type="number"
              step="0.0001"
              value={priceNative}
              onChange={(e) => setPriceNative(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500 p-2 border"
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">trade_currency</label>
              <input
                type="text"
                maxLength={3}
                value={tradeCurrency}
                onChange={(e) => setTradeCurrency(e.target.value.toUpperCase())}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500 p-2 border"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">fx_rate</label>
              <input
                type="number"
                step="0.0001"
                value={fxRate}
                onChange={(e) => setFxRate(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500 p-2 border"
                required
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">commission ({tradeCurrency})</label>
            <input
              type="number"
              step="0.01"
              value={commission}
              onChange={(e) => setCommission(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500 p-2 border"
              placeholder={(grossNative * 0.005).toFixed(2)}
            />
          </div>

          <div className="rounded-md bg-gray-50 p-3 text-sm space-y-1 border border-gray-200">
            <div className="font-semibold text-gray-700">Preview</div>
            <div className="flex justify-between"><span>commission</span><span>{commissionValue.toFixed(2)} {tradeCurrency}</span></div>
            <div className="flex justify-between"><span>total native</span><span>{totalNative.toFixed(2)} {tradeCurrency}</span></div>
            <div className="flex justify-between"><span>total PLN</span><span>{totalPln.toFixed(2)} PLN</span></div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Data</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500 p-2 border"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className={cn(
              "w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500",
              loading && "opacity-50 cursor-not-allowed"
            )}
          >
            {loading ? 'Przetwarzanie...' : 'Sprzedaj Akcje'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default SellModal;
