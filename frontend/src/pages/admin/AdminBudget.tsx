import React, { useState } from 'react';
import { budgetApi } from '../../api_budget';
import { extractErrorMessageFromUnknown } from '../../http/response';

const AdminBudget: React.FC = () => {
  const [resetting, setResetting] = useState(false);

  const handleReset = async () => {
    const confirmed = window.confirm('To usunie WSZYSTKIE dane budżetu (Transactions, Envelopes, Loans). Czy kontynuować?');
    if (!confirmed) return;

    setResetting(true);
    try {
      const result = await budgetApi.reset();
      alert(result.message ?? 'Dane budżetu zostały zresetowane.');
      window.location.reload();
    } catch (err) {
      alert(extractErrorMessageFromUnknown(err));
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="space-y-4 px-4 sm:px-0">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Admin → Budżet</h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">Operacje serwisowe budżetu.</p>
      </div>

      <section className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900/40 dark:bg-red-950/40">
        <div className="text-sm font-medium text-red-900 dark:text-red-100">Danger zone</div>
        <div className="mt-1 text-sm text-red-800 dark:text-red-200">Reset usuwa wszystkie transakcje budżetowe, koperty i pożyczki.</div>
        <div className="mt-4">
          <button
            type="button"
            onClick={handleReset}
            disabled={resetting}
            className="rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
          >
            {resetting ? 'Resetowanie...' : 'Resetuj dane budżetu'}
          </button>
        </div>
      </section>
    </div>
  );
};

export default AdminBudget;
