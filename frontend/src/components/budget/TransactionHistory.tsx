import React, { useEffect, useState } from 'react';
import { budgetApi, Envelope, EnvelopeCategory } from '../../api_budget';
import { ArrowDownRight, ArrowUpRight, ArrowRight, RefreshCw, AlertCircle, CheckCircle } from 'lucide-react';

interface Transaction {
  id: number;
  type: string;
  amount: number;
  description: string;
  date: string;
  envelope_name?: string;
  envelope_icon?: string;
  category_name?: string;
  category_icon?: string;
}

interface TransactionHistoryProps {
  selectedAccountId: number | null;
  categories: EnvelopeCategory[];
  envelopes: Envelope[];
}

export default function TransactionHistory({ selectedAccountId, categories, envelopes }: TransactionHistoryProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [selectedEnvelopeId, setSelectedEnvelopeId] = useState<number | null>(null);

  const fetchTransactions = async () => {
    if (!selectedAccountId) return;
    setLoading(true);
    try {
      const data = await budgetApi.getTransactions(selectedAccountId, selectedEnvelopeId, selectedCategoryId);
      setTransactions(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchTransactions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAccountId, selectedCategoryId, selectedEnvelopeId]);

  // Filter envelopes based on selected category if any
  const filteredEnvelopes = selectedCategoryId
    ? envelopes.filter(e => e.category_id === selectedCategoryId)
    : envelopes;

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'INCOME': return <ArrowDownRight className="text-green-600" />;
      case 'EXPENSE': return <ArrowUpRight className="text-red-600" />;
      case 'ALLOCATE': return <ArrowRight className="text-blue-600" />;
      case 'BORROW': return <AlertCircle className="text-orange-600" />;
      case 'REPAY': return <CheckCircle className="text-green-600" />;
      default: return <RefreshCw className="text-gray-600" />;
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'INCOME': return 'Wpływ';
      case 'EXPENSE': return 'Wydatek';
      case 'ALLOCATE': return 'Alokacja';
      case 'BORROW': return 'Pożyczka wew.';
      case 'REPAY': return 'Spłata wew.';
      default: return type;
    }
  };

  const formatAmount = (type: string, amount: number) => {
    const isNegative = ['EXPENSE'].includes(type);
    const colorClass = isNegative ? 'text-red-600' : 'text-green-600';
    const prefix = isNegative ? '-' : '+';
    // Allocate, Borrow, Repay are internal movements, maybe neutral color or specific?
    // Let's keep Allocate as Neutral/Blue, Borrow as Orange, Repay as Green.
    
    if (type === 'ALLOCATE') return <span className="text-blue-600">{amount.toFixed(2)} PLN</span>;
    if (type === 'BORROW') return <span className="text-orange-600">{amount.toFixed(2)} PLN</span>;
    if (type === 'REPAY') return <span className="text-green-600">{amount.toFixed(2)} PLN</span>;

    return <span className={`font-bold ${colorClass}`}>{prefix}{amount.toFixed(2)} PLN</span>;
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 mt-8">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
        <h3 className="text-xl font-bold text-gray-800">Historia Transakcji</h3>
        
        <div className="flex gap-4 w-full md:w-auto">
          {/* Category Filter */}
          <select
            className="p-2 border rounded-lg text-sm w-full md:w-48"
            value={selectedCategoryId || ''}
            onChange={(e) => {
              setSelectedCategoryId(e.target.value ? Number(e.target.value) : null);
              setSelectedEnvelopeId(null); // Reset envelope when category changes
            }}
          >
            <option value="">Wszystkie Kategorie</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
            ))}
          </select>

          {/* Envelope Filter */}
          <select
            className="p-2 border rounded-lg text-sm w-full md:w-48"
            value={selectedEnvelopeId || ''}
            onChange={(e) => setSelectedEnvelopeId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Wszystkie Koperty</option>
            {filteredEnvelopes.map(e => (
              <option key={e.id} value={e.id}>{e.icon} {e.name}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Data</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Typ</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Opis</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Koperta / Kategoria</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Kwota</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-gray-500">Ładowanie...</td>
              </tr>
            ) : transactions.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-gray-500">Brak transakcji dla wybranych filtrów.</td>
              </tr>
            ) : (
              transactions.map(t => (
                <tr key={t.id} className="hover:bg-gray-50 transition">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(t.date).toLocaleDateString('pl-PL')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <div className="flex items-center gap-2">
                      {getTypeIcon(t.type)}
                      <span className="font-medium text-gray-700">{getTypeLabel(t.type)}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 max-w-xs truncate" title={t.description}>
                    {t.description}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {t.envelope_name ? (
                      <span className="flex items-center gap-1">
                        {t.envelope_icon} {t.envelope_name} 
                        {t.category_name && <span className="text-gray-400 text-xs ml-1">({t.category_name})</span>}
                      </span>
                    ) : (
                      <span className="text-gray-500 italic">Wolne Środki / Konto</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right">
                    {formatAmount(t.type, t.amount)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
