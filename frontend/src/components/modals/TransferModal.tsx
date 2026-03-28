import React, { useMemo, useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { portfolioApi } from '../../api';
import { budgetApi, BudgetAccount } from '../../api_budget';
import { FlattenedPortfolio, Portfolio } from '../../types';
import { cn } from '../../lib/utils';
import { flattenPortfolios } from '../../utils/portfolioUtils';

interface TransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  portfolioId: number;
  budgetAccounts: BudgetAccount[];
  maxCash: number;
  subPortfolios?: Portfolio[];
  initialMode?: TransferMode;
  initialDate?: string;
}

type TransferMode = 'DEPOSIT' | 'WITHDRAW' | 'INTERNAL_TRANSFER';

const TransferModal: React.FC<TransferModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  portfolioId,
  budgetAccounts,
  maxCash,
  subPortfolios = [],
  initialMode = 'DEPOSIT',
  initialDate,
}) => {
  const [mode, setMode] = useState<TransferMode>('DEPOSIT');
  const [amount, setAmount] = useState('');
  const [subPortfolioId, setSubPortfolioId] = useState<string>('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedBudgetAccountId, setSelectedBudgetAccountId] = useState('');
  const [fromScopeId, setFromScopeId] = useState<string>('');
  const [toScopeId, setToScopeId] = useState<string>('');
  const [note, setNote] = useState('');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const today = new Date().toISOString().split('T')[0];

  const parentWithChildren = useMemo<Portfolio[]>(() => [{
    id: portfolioId,
    name: 'Portfel główny',
    account_type: 'STANDARD',
    current_cash: maxCash,
    total_deposits: 0,
    savings_rate: 0,
    children: subPortfolios,
  }], [portfolioId, maxCash, subPortfolios]);

  const transferScopes = useMemo<FlattenedPortfolio[]>(() => {
    return flattenPortfolios(parentWithChildren)
      .map((portfolio) => ({
        ...portfolio,
        name: portfolio.id === portfolioId ? 'Portfel Główny (Parent)' : portfolio.name,
      }))
      .filter((portfolio) => !portfolio.is_archived);
  }, [parentWithChildren, portfolioId]);

  const getParentRootId = (scope: FlattenedPortfolio | undefined): number | null => {
    if (!scope) return null;
    return scope.parent_portfolio_id ?? scope.id;
  };

  const pollJobStatus = async (jobId: string) => {
    try {
      const status = await portfolioApi.getJobStatus(jobId);
      if (status.status === 'done') {
        setStatusMessage('Przeliczanie historii zakończone.');
        onSuccess();
      } else if (status.status === 'failed') {
        setStatusMessage(`Przeliczanie historii nie powiodło się: ${status.error ?? 'nieznany błąd'}`);
      } else {
        setTimeout(() => {
          pollJobStatus(jobId);
        }, 1000);
      }
    } catch (error) {
      setStatusMessage(`Nie udało się sprawdzić statusu joba: ${error instanceof Error ? error.message : 'nieznany błąd'}`);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setAmount('');
      setSubPortfolioId('');
      setDate(initialDate && initialDate <= today ? initialDate : today);
      setSelectedBudgetAccountId('');
      setMode(initialMode);
      setFromScopeId('');
      setToScopeId('');
      setNote('');
      setStatusMessage(null);
    }
  }, [initialDate, initialMode, isOpen, today]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setStatusMessage(null);

    try {
      if (mode === 'INTERNAL_TRANSFER') {
        const fromScope = transferScopes.find((scope) => String(scope.id) === fromScopeId);
        const toScope = transferScopes.find((scope) => String(scope.id) === toScopeId);

        const numericAmount = parseFloat(amount);
        if (!fromScope || !toScope) {
          throw new Error('Wybierz portfel źródłowy i docelowy.');
        }
        if (fromScope.id === toScope.id) {
          throw new Error('Portfel źródłowy i docelowy nie mogą być takie same.');
        }
        if (getParentRootId(fromScope) !== getParentRootId(toScope)) {
          throw new Error('Przelew możliwy tylko w obrębie tego samego parenta.');
        }
        if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
          throw new Error('Kwota musi być dodatnia.');
        }
        if (!date || date > today) {
          throw new Error('Data nie może być z przyszłości.');
        }

        const response = await portfolioApi.transferCash({
          from_portfolio_id: fromScope.id,
          from_sub_portfolio_id: fromScope.parent_portfolio_id ? fromScope.id : null,
          to_portfolio_id: toScope.id,
          to_sub_portfolio_id: toScope.parent_portfolio_id ? toScope.id : null,
          amount: numericAmount,
          date,
          note: note.trim() ? note.trim() : null,
        });

        setStatusMessage('Trwa przeliczanie historii...');
        await pollJobStatus(response.job_id);
        onClose();
        return;
      }

      const subId = subPortfolioId ? parseInt(subPortfolioId, 10) : null;
      if (mode === 'WITHDRAW') {
        if (selectedBudgetAccountId) {
          await budgetApi.withdrawFromPortfolio(
            portfolioId,
            parseInt(selectedBudgetAccountId, 10),
            parseFloat(amount),
            'Wypłata z portfela inwestycyjnego',
            date
          );
        } else {
          await portfolioApi.withdraw({
            portfolio_id: portfolioId,
            amount: parseFloat(amount),
            date,
            sub_portfolio_id: subId,
          });
        }
      } else {
        await portfolioApi.deposit({
          portfolio_id: portfolioId,
          amount: parseFloat(amount),
          date,
          sub_portfolio_id: subId,
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

  const destinationScopes = transferScopes.filter((scope) => String(scope.id) !== fromScopeId);

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
          <div className="grid grid-cols-3 rounded-md shadow-sm mb-6">
            <button
              type="button"
              onClick={() => setMode('DEPOSIT')}
              className={cn(
                'py-2 text-sm font-medium border first:rounded-l-md focus:z-10 focus:ring-2 focus:ring-blue-500',
                mode === 'DEPOSIT'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              )}
            >
              Wpłata
            </button>
            <button
              type="button"
              onClick={() => setMode('WITHDRAW')}
              className={cn(
                'py-2 text-sm font-medium border -ml-px focus:z-10 focus:ring-2 focus:ring-blue-500',
                mode === 'WITHDRAW'
                  ? 'bg-orange-600 text-white border-orange-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              )}
            >
              Wypłata
            </button>
            <button
              type="button"
              onClick={() => setMode('INTERNAL_TRANSFER')}
              className={cn(
                'py-2 text-sm font-medium border -ml-px last:rounded-r-md focus:z-10 focus:ring-2 focus:ring-blue-500',
                mode === 'INTERNAL_TRANSFER'
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              )}
            >
              Sub→Sub
            </button>
          </div>

          {mode !== 'INTERNAL_TRANSFER' && subPortfolios.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700">Sub-portfel (opcjonalnie)</label>
              <select
                value={subPortfolioId}
                onChange={(e) => setSubPortfolioId(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              >
                <option value="">Portfel Główny (Parent)</option>
                {subPortfolios.filter((p) => !p.is_archived).map((sp) => (
                  <option key={sp.id} value={sp.id}>{sp.name}</option>
                ))}
              </select>
            </div>
          )}

          {mode === 'INTERNAL_TRANSFER' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700">Z portfela</label>
                <select
                  value={fromScopeId}
                  onChange={(e) => setFromScopeId(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border"
                  required
                >
                  <option value="">Wybierz źródło</option>
                  {transferScopes.map((scope) => (
                    <option key={scope.id} value={scope.id}>
                      {scope.parent_portfolio_id ? `↳ ${scope.name}` : scope.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Do portfela</label>
                <select
                  value={toScopeId}
                  onChange={(e) => setToScopeId(e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border"
                  required
                >
                  <option value="">Wybierz cel</option>
                  {destinationScopes.map((scope) => (
                    <option key={scope.id} value={scope.id}>
                      {scope.parent_portfolio_id ? `↳ ${scope.name}` : scope.name}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}

          {mode === 'WITHDRAW' && (
            <div>
              <label className="block text-sm font-medium text-gray-700">Na konto budżetowe (Opcjonalnie)</label>
              <select
                value={selectedBudgetAccountId}
                onChange={(e) => setSelectedBudgetAccountId(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              >
                <option value="">-- Wypłata Zewnętrzna (Brak transferu) --</option>
                {budgetAccounts.map((acc) => (
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
              max={mode === 'WITHDRAW' ? maxCash : undefined}
            />
            {mode === 'WITHDRAW' && <p className="text-xs text-gray-500 mt-1">Dostępne: {maxCash.toFixed(2)} PLN</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Data</label>
            <input
              type="date"
              value={date}
              max={today}
              onChange={(e) => setDate(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              required
            />
          </div>

          {mode === 'INTERNAL_TRANSFER' && (
            <div>
              <label className="block text-sm font-medium text-gray-700">Notatka (opcjonalnie)</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border"
                rows={2}
              />
            </div>
          )}

          {statusMessage && (
            <div className="rounded-md bg-blue-50 border border-blue-200 p-2 text-sm text-blue-700">
              {statusMessage}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className={cn(
              'w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2',
              mode === 'DEPOSIT'
                ? 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500'
                : mode === 'WITHDRAW'
                  ? 'bg-orange-600 hover:bg-orange-700 focus:ring-orange-500'
                  : 'bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500',
              loading && 'opacity-50 cursor-not-allowed'
            )}
          >
            {loading ? 'Przetwarzanie...' : mode === 'DEPOSIT' ? 'Wpłać' : mode === 'WITHDRAW' ? 'Wypłać' : 'Wykonaj przelew'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default TransferModal;
