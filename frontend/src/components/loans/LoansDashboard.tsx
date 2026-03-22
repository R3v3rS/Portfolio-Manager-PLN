import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, CreditCard, Calendar, TrendingDown, Trash2 } from 'lucide-react';
import { getLoans, createLoan, deleteLoan, getSchedule, type LoanSummary, type LoanScheduleResponse, type LoanScheduleEntry } from '../../api_loans';

interface LoanWithDetails extends LoanSummary {
  current_balance: number;
  current_installment: number;
}

const LoansDashboard: React.FC = () => {
  const [loans, setLoans] = useState<LoanSummary[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [newLoan, setNewLoan] = useState({
    name: '',
    original_amount: '',
    duration_months: '',
    start_date: new Date().toISOString().split('T')[0],
    installment_type: 'EQUAL' as 'EQUAL' | 'DECREASING',
    initial_rate: '',
    category: 'GOTOWKOWY',
  });

  const navigate = useNavigate();

  useEffect(() => {
    fetchLoans();
  }, []);

  const fetchLoans = async () => {
    try {
      const response = await getLoans();
      setLoans(response);
    } catch (error) {
      console.error('Error fetching loans:', error);
    }
  };

  const handleCreateLoan = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createLoan({
        ...newLoan,
        original_amount: parseFloat(newLoan.original_amount),
        duration_months: parseInt(newLoan.duration_months),
        initial_rate: parseFloat(newLoan.initial_rate),
        category: newLoan.category,
      });
      setShowModal(false);
      fetchLoans();
      setNewLoan({
        name: '',
        original_amount: '',
        duration_months: '',
        start_date: new Date().toISOString().split('T')[0],
        installment_type: 'EQUAL',
        initial_rate: '',
        category: 'GOTOWKOWY',
      });
    } catch (error) {
      console.error('Error creating loan:', error);
    }
  };

  const handleDeleteLoan = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (window.confirm('Czy na pewno chcesz usunąć ten kredyt?')) {
      try {
        await deleteLoan(id);
        fetchLoans();
      } catch (error) {
        console.error('Error deleting loan:', error);
      }
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(amount);
  };

  // Note: We don't have remaining balance in the list API yet, only in details.
  // For now, I'll just show original amount sum or fetch details for each loan if needed.
  // The requirement says "Total Debt (Remaining Amount)". 
  // The list API only returns the loan basic info from the `loans` table.
  // To get remaining amount, I would need to calculate it or fetch it.
  // I'll update the backend to include remaining amount in the list API, or fetch details for each loan.
  // Fetching details for each loan is N+1 but acceptable for small number of loans.
  // Let's assume for now I show original amount or just leave it as placeholder until I update backend or fetch details.
  // Actually, I can fetch details for all loans in parallel.

  const [loansWithDetails, setLoansWithDetails] = useState<LoanWithDetails[]>([]);

  useEffect(() => {
    const fetchDetails = async () => {
      if (loans.length === 0) return;
      
      const detailsPromises = loans.map(loan => 
        // We can't easily get just the balance without calculating the whole schedule currently.
        // The schedule endpoint returns the full schedule. 
        // Let's rely on the schedule endpoint for now.
        // Or maybe I should update the backend to return current status?
        // Let's try to just fetch schedule for each loan to get current balance.
         getSchedule(loan.id)
      );
      
      try {
        const responses = await Promise.all(detailsPromises);
        const details = responses.map((res: LoanScheduleResponse) => {
            const schedule = res.baseline.schedule;
            // Find current status based on today's date?
            // Or just take the last entry if loan is finished?
            // Or find the entry corresponding to current month.
            // For now, let's just take the first entry's remaining balance? No, that's after 1st payment.
            // Let's use the schedule to find the latest "remaining_balance" that is closest to today.
            const today = new Date();
            const currentEntry = schedule.find((entry: LoanScheduleEntry) => new Date(entry.date) > today) || schedule[schedule.length - 1];
            
            // Find the original loan from the list to preserve fields like installment_type and original_amount
            const originalLoan = loans.find(l => l.id === res.loan.id);

            return {
                id: res.loan.id,
                name: res.loan.name,
                category: res.loan.category,
                original_amount: originalLoan?.original_amount ?? 0,
                duration_months: originalLoan?.duration_months ?? 0,
                start_date: originalLoan?.start_date ?? '',
                installment_type: originalLoan?.installment_type ?? 'EQUAL',
                current_balance: currentEntry ? currentEntry.remaining_balance : 0,
                current_installment: currentEntry ? currentEntry.installment : 0
            };
        });
        setLoansWithDetails(details);
      } catch (error) {
        console.error("Error fetching loan details", error);
      }
    };

    if (loans.length > 0) {
        fetchDetails();
    }
  }, [loans]);

  const totalRemaining = loansWithDetails.reduce((sum, loan) => sum + (loan.current_balance || 0), 0);
  const totalMonthly = loansWithDetails.reduce((sum, loan) => sum + (loan.current_installment || 0), 0);

  const getCategoryBadge = (category?: string) => {
    switch(category) {
        case 'HIPOTECZNY':
            return { label: 'Hipoteczny', icon: '🏠', color: 'bg-blue-100 text-blue-800' };
        case 'RATY_0':
            return { label: 'Raty 0%', icon: '🏷️', color: 'bg-green-100 text-green-800' };
        default:
            return { label: 'Gotówkowy', icon: '💸', color: 'bg-orange-100 text-orange-800' };
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Kredyty i Zobowiązania</h1>
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <Plus className="h-5 w-5 mr-2" />
          Dodaj Kredyt
        </button>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <TrendingDown className="h-6 w-6 text-gray-400" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Całkowite Zadłużenie</dt>
                  <dd className="text-lg font-medium text-gray-900">{formatCurrency(totalRemaining)}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <CreditCard className="h-6 w-6 text-gray-400" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">Miesięczne Obciążenie</dt>
                  <dd className="text-lg font-medium text-gray-900">{formatCurrency(totalMonthly)}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <ul className="divide-y divide-gray-200">
          {loans.map((loan) => {
            const details = loansWithDetails.find(d => d.id === loan.id);
            return (
            <li key={loan.id}>
              <button
                onClick={() => navigate(`/loans/${loan.id}`)}
                className="block hover:bg-gray-50 w-full text-left"
              >
                <div className="px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                        <span className="text-xl mr-2">{getCategoryBadge(loan.category).icon}</span>
                        <p className="text-sm font-medium text-blue-600 truncate">{loan.name}</p>
                    </div>
                    <div className="ml-2 flex-shrink-0 flex items-center space-x-2">
                      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getCategoryBadge(loan.category).color}`}>
                        {getCategoryBadge(loan.category).label}
                      </span>
                      <p className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                        {loan.installment_type === 'EQUAL' ? 'Raty Równe' : 'Raty Malejące'}
                      </p>
                      <button 
                        onClick={(e) => handleDeleteLoan(e, loan.id)}
                        className="text-gray-400 hover:text-red-500 transition-colors p-1"
                      >
                        <Trash2 className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                  <div className="mt-2 sm:flex sm:justify-between">
                    <div className="sm:flex">
                      <p className="flex items-center text-sm text-gray-500">
                        <CreditCard className="flex-shrink-0 mr-1.5 h-5 w-5 text-gray-400" />
                        Kwota: {formatCurrency(loan.original_amount)}
                      </p>
                      {details && (
                         <p className="mt-2 flex items-center text-sm text-gray-500 sm:mt-0 sm:ml-6">
                            Pozostało: {formatCurrency(details.current_balance)}
                         </p>
                      )}
                    </div>
                    <div className="mt-2 flex items-center text-sm text-gray-500 sm:mt-0">
                      <Calendar className="flex-shrink-0 mr-1.5 h-5 w-5 text-gray-400" />
                      <p>Start: {loan.start_date}</p>
                    </div>
                  </div>
                </div>
              </button>
            </li>
          )})}
        </ul>
      </div>

      {showModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" aria-hidden="true">
              <div className="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
              <div>
                <h3 className="text-lg leading-6 font-medium text-gray-900">Dodaj Nowy Kredyt</h3>
                <form onSubmit={handleCreateLoan} className="mt-5 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Kategoria</label>
                    <select
                      className="mt-1 block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      value={newLoan.category}
                      onChange={(e) => {
                        const cat = e.target.value;
                        setNewLoan({ 
                            ...newLoan, 
                            category: cat,
                            initial_rate: cat === 'RATY_0' ? '0' : newLoan.initial_rate
                        });
                      }}
                    >
                      <option value="GOTOWKOWY">Kredyt Gotówkowy</option>
                      <option value="HIPOTECZNY">Kredyt Hipoteczny</option>
                      <option value="RATY_0">Raty 0%</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Nazwa</label>
                    <input
                      type="text"
                      required
                      className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      value={newLoan.name}
                      onChange={(e) => setNewLoan({ ...newLoan, name: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Kwota Kredytu</label>
                    <input
                      type="number"
                      required
                      className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      value={newLoan.original_amount}
                      onChange={(e) => setNewLoan({ ...newLoan, original_amount: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Okres (miesiące)</label>
                    <input
                      type="number"
                      required
                      className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      value={newLoan.duration_months}
                      onChange={(e) => setNewLoan({ ...newLoan, duration_months: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Data Rozpoczęcia</label>
                    <input
                      type="date"
                      required
                      className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      value={newLoan.start_date}
                      onChange={(e) => setNewLoan({ ...newLoan, start_date: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Oprocentowanie Początkowe (%)</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      disabled={newLoan.category === 'RATY_0'}
                      className={`mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md ${newLoan.category === 'RATY_0' ? 'bg-gray-100' : ''}`}
                      value={newLoan.initial_rate}
                      onChange={(e) => setNewLoan({ ...newLoan, initial_rate: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Rodzaj Rat</label>
                    <select
                      className="mt-1 block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      value={newLoan.installment_type}
                      onChange={(e) => setNewLoan({ ...newLoan, installment_type: e.target.value as 'EQUAL' | 'DECREASING' })}
                    >
                      <option value="EQUAL">Raty Równe</option>
                      <option value="DECREASING">Raty Malejące</option>
                    </select>
                  </div>
                  <div className="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense">
                    <button
                      type="submit"
                      className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-blue-600 text-base font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:col-start-2 sm:text-sm"
                    >
                      Dodaj
                    </button>
                    <button
                      type="button"
                      className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:col-start-1 sm:text-sm"
                      onClick={() => setShowModal(false)}
                    >
                      Anuluj
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LoansDashboard;
