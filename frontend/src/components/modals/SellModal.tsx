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
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && holding) {
      setQuantity(holding.quantity.toString());
      setPrice((holding.current_price || holding.average_buy_price).toString());
      setDate(new Date().toISOString().split('T')[0]);
    }
  }, [isOpen, holding]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!holding) return;
    
    setLoading(true);
    try {
      await api.post('/sell', {
        portfolio_id: portfolioId,
        ticker: holding.ticker,
        quantity: parseFloat(quantity),
        price: parseFloat(price),
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
            <label className="block text-sm font-medium text-gray-700">Cena Sprzedaży ({holding.currency || 'PLN'})</label>
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
