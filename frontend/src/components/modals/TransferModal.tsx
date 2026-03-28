import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { portfolioApi } from '../../api';
import { budgetApi, BudgetAccount } from '../../api_budget';
import { Portfolio } from '../../types';
import { cn } from '../../lib/utils';

interface TransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  portfolioId: number;
  budgetAccounts: BudgetAccount[];
  maxCash: number;
  subPortfolios?: Portfolio[];
}

const TransferModal: React.FC<TransferModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  portfolioId,
  budgetAccounts,
  maxCash,
  subPortfolios = [],
}) => {
  const [type, setType] = useState<'DEPOSIT' | 'WITHDRAW'>('DEPOSIT');
  const [amount, setAmount] = useState('');
  const [subPortfolioId, setSubPortfolioId] = useState<string>('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedBudgetAccountId, setSelectedBudgetAccountId] = useState('');
  const [loading, setLoading] = useState(false);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setAmount('');
      setSubPortfolioId('');
      setDate(new Date().toISOString().split('T')[0]);
      setSelectedBudgetAccountId('');
      setType('DEPOSIT');
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const subId = subPortfolioId ? parseInt(subPortfolioId) : null;

    try {
      if (type === 'WITHDRAW') {
        if (selectedBudgetAccountId) {
          await budgetApi.withdrawFromPortfolio(
            portfolioId,
            parseInt(selectedBudgetAccountId),
            parseFloat(amount),
            "Wypłata z portfela inwestycyjnego",
            date
          );
        } else {
          await portfolioApi.withdraw({
            portfolio_id: portfolioId,
            amount: parseFloat(amount),
            date,
            sub_portfolio_id: subId
          });
        }
      } else {
        await portfolioApi.deposit({
          portfolio_id: portfolioId,
          amount: parseFloat(amount),
          date,
          sub_portfolio_id: subId
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex justify-between items-center p-4 border-b">
          <h2 className="text-lg font-medium text-gray-900">Transfer Środków</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Type Toggle */}
          <div className="flex rounded-md shadow-sm mb-6">
            <button
              type="button"
              onClick={() => setType('DEPOSIT')}
              className={cn(
                "flex-1 py-2 text-sm font-medium border first:rounded-l-md focus:z-10 focus:ring-2 focus:ring-blue-500",
                type === 'DEPOSIT' 
                  ? "bg-blue-600 text-white border-blue-600" 
                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
              )}
            >
              Wpłata
            </button>
            <button
              type="button"
              onClick={() => setType('WITHDRAW')}
              className={cn(
                "flex-1 py-2 text-sm font-medium border -ml-px last:rounded-r-md focus:z-10 focus:ring-2 focus:ring-blue-500",
                type === 'WITHDRAW' 
                  ? "bg-orange-600 text-white border-orange-600" 
                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
              )}
            >
              Wypłata
            </button>
          </div>

          {/* Sub-portfolio selector */}
          {subPortfolios.length > 0 && (
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

          {/* Withdraw specific fields */}
          {type === 'WITHDRAW' && (
            <div>
              <label className="block text-sm font-medium text-gray-700">Na konto budżetowe (Opcjonalnie)</label>
              <select
                value={selectedBudgetAccountId}
                onChange={(e) => setSelectedBudgetAccountId(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              >
                <option value="">-- Wypłata Zewnętrzna (Brak transferu) --</option>
                {budgetAccounts.map(acc => (
                  <option key={acc.id} value={acc.id}>{acc.name} ({acc.balance.toFixed(2)} {acc.currency})</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">Wybierz konto, aby przelać środki do budżetu. Pozostaw puste dla wypłaty poza system.</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700">Kwota (PLN)</label>
            <input
              type="number"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              required
              min="0.01"
              max={type === 'WITHDRAW' ? maxCash : undefined}
            />
            {type === 'WITHDRAW' && (
                <p className="text-xs text-gray-500 mt-1">Dostępne: {maxCash.toFixed(2)} PLN</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Data</label>
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
            disabled={loading}
            className={cn(
              "w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2",
              type === 'DEPOSIT' 
                ? "bg-blue-600 hover:bg-blue-700 focus:ring-blue-500" 
                : "bg-orange-600 hover:bg-orange-700 focus:ring-orange-500",
              loading && "opacity-50 cursor-not-allowed"
            )}
          >
            {loading ? 'Przetwarzanie...' : (type === 'DEPOSIT' ? 'Wpłać' : 'Wypłać')}
          </button>
        </form>
      </div>
    </div>
  );
};

export default TransferModal;
