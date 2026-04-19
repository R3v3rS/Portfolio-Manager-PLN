import React, { useEffect, useMemo, useState } from 'react';
import { Plus, Pencil, Trash2, X } from 'lucide-react';
import {
  symbolMapApi,
  SymbolMapping,
  MappingCurrency,
  CreateSymbolMappingPayload,
} from '../api_symbol_map';

const CURRENCIES: MappingCurrency[] = ['PLN', 'USD', 'EUR', 'GBP'];

interface MappingModalState {
  mode: 'create' | 'edit';
  mapping: SymbolMapping | null;
}

const SymbolMappingPanel: React.FC = () => {
  const [mappings, setMappings] = useState<SymbolMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorToast, setErrorToast] = useState<string | null>(null);
  const [modalState, setModalState] = useState<MappingModalState | null>(null);
  const [symbolInput, setSymbolInput] = useState('');
  const [ticker, setTicker] = useState('');
  const [currency, setCurrency] = useState<MappingCurrency>('PLN');
  const [saving, setSaving] = useState(false);

  const sortedMappings = useMemo(
    () => [...mappings].sort((a, b) => a.symbol_input.localeCompare(b.symbol_input)),
    [mappings]
  );

  useEffect(() => {
    const run = async () => {
      try {
        const data = await symbolMapApi.getAll();
        setMappings(data);
      } catch (error) {
        setErrorToast(error instanceof Error ? error.message : 'Failed to load mappings');
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  useEffect(() => {
    if (!errorToast) return;
    const timer = setTimeout(() => setErrorToast(null), 3500);
    return () => clearTimeout(timer);
  }, [errorToast]);

  const openCreate = () => {
    setModalState({ mode: 'create', mapping: null });
    setSymbolInput('');
    setTicker('');
    setCurrency('PLN');
  };

  const openEdit = (mapping: SymbolMapping) => {
    setModalState({ mode: 'edit', mapping });
    setSymbolInput(mapping.symbol_input);
    setTicker(mapping.ticker);
    setCurrency(mapping.currency ?? 'PLN');
  };

  const closeModal = () => {
    setModalState(null);
    setSaving(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modalState) return;

    const normalizedSymbol = symbolInput.trim().toUpperCase();
    const normalizedTicker = ticker.trim().toUpperCase();

    if (!normalizedTicker || (modalState.mode === 'create' && !normalizedSymbol)) {
      setErrorToast('Please provide required fields');
      return;
    }

    setSaving(true);

    if (modalState.mode === 'create') {
      const optimisticId = -Date.now();
      const optimisticMapping: SymbolMapping = {
        id: optimisticId,
        symbol_input: normalizedSymbol,
        ticker: normalizedTicker,
        currency,
        created_at: new Date().toISOString(),
      };

      setMappings((prev) => [...prev, optimisticMapping]);

      const payload: CreateSymbolMappingPayload = {
        symbol_input: normalizedSymbol,
        ticker: normalizedTicker,
        currency,
      };

      try {
        const created = await symbolMapApi.create(payload);
        setMappings((prev) => prev.map((item) => (item.id === optimisticId ? created : item)));
        closeModal();
      } catch (error) {
        setMappings((prev) => prev.filter((item) => item.id !== optimisticId));
        setErrorToast(error instanceof Error ? error.message : 'Failed to create mapping');
      } finally {
        setSaving(false);
      }
      return;
    }

    if (!modalState.mapping) return;

    const prevMapping = modalState.mapping;
    const optimisticUpdated: SymbolMapping = {
      ...prevMapping,
      ticker: normalizedTicker,
      currency,
    };

    setMappings((prev) => prev.map((item) => (item.id === prevMapping.id ? optimisticUpdated : item)));

    try {
      const updated = await symbolMapApi.update(prevMapping.id, {
        ticker: normalizedTicker,
        currency,
      });
      setMappings((prev) => prev.map((item) => (item.id === prevMapping.id ? updated : item)));
      closeModal();
    } catch (error) {
      setMappings((prev) => prev.map((item) => (item.id === prevMapping.id ? prevMapping : item)));
      setErrorToast(error instanceof Error ? error.message : 'Failed to update mapping');
      setSaving(false);
    }
  };

  const handleDelete = async (mapping: SymbolMapping) => {
    const confirmed = window.confirm(`Delete mapping ${mapping.symbol_input} → ${mapping.ticker}?`);
    if (!confirmed) return;

    const previous = [...mappings];
    setMappings((prev) => prev.filter((item) => item.id !== mapping.id));

    try {
      await symbolMapApi.delete(mapping.id);
    } catch (error) {
      setMappings(previous);
      setErrorToast(error instanceof Error ? error.message : 'Failed to delete mapping');
    }
  };

  return (
    <div className="space-y-4 px-4 sm:px-0">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Admin → Symbol Mapping</h1>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          Add mapping
        </button>
      </div>

      {loading ? (
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300">
          Loading mappings...
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Symbol Input</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Ticker</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-500">Currency</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {sortedMappings.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                    No mappings yet.
                  </td>
                </tr>
              ) : (
                sortedMappings.map((mapping) => (
                  <tr key={mapping.id}>
                    <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{mapping.symbol_input}</td>
                    <td className="px-4 py-3 text-gray-700 dark:text-gray-200">{mapping.ticker}</td>
                    <td className="px-4 py-3 text-gray-700 dark:text-gray-200">{mapping.currency ?? '-'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          className="inline-flex items-center gap-1 rounded-md border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-800"
                          onClick={() => openEdit(mapping)}
                        >
                          <Pencil className="h-3.5 w-3.5" /> Edit
                        </button>
                        <button
                          className="inline-flex items-center gap-1 rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:border-red-700 dark:text-red-400 dark:hover:bg-red-900/20"
                          onClick={() => handleDelete(mapping)}
                        >
                          <Trash2 className="h-3.5 w-3.5" /> Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {errorToast && (
        <div className="fixed bottom-4 right-4 z-50 rounded-md bg-red-600 px-4 py-2 text-sm text-white shadow-lg">
          {errorToast}
        </div>
      )}

      {modalState && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-lg bg-white shadow-xl dark:bg-gray-900">
            <div className="flex items-center justify-between border-b border-gray-200 p-4 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {modalState.mode === 'create' ? 'Add mapping' : 'Edit mapping'}
              </h2>
              <button onClick={closeModal} className="text-gray-500 hover:text-gray-700">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 p-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">Symbol input</label>
                <input
                  value={symbolInput}
                  onChange={(e) => setSymbolInput(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm uppercase dark:border-gray-700 dark:bg-gray-800"
                  disabled={modalState.mode === 'edit'}
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">Ticker</label>
                <input
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm uppercase dark:border-gray-700 dark:bg-gray-800"
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">Currency</label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value as MappingCurrency)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800"
                >
                  {CURRENCIES.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-md bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-60"
                >
                  {saving ? 'Saving...' : modalState.mode === 'create' ? 'Add' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default SymbolMappingPanel;
