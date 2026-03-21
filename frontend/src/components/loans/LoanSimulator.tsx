import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Chart as ChartJS,
  ChartData,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { ArrowLeft, TrendingUp, DollarSign, Calendar, Calculator, List, Wallet } from 'lucide-react';
import { getSchedule, addOverpayment, addRate } from '../../api_loans';
import { budgetApi, Envelope, BudgetAccount } from '../../api_budget';



type OverpaymentType = 'REDUCE_TERM' | 'REDUCE_INSTALLMENT';

interface ScheduleEntry {
  month: number;
  date: string;
  interest_rate: number;
  installment: number;
  principal_part: number;
  interest_part: number;
  overpayment: number;
  remaining_balance: number;
  overpayment_type: OverpaymentType | null;
}

interface OverpaymentEntry {
  amount: number;
  date: string;
  type?: OverpaymentType;
}

interface LoanScheduleResponse {
  loan: {
    id: number;
    name: string;
    category?: string;
    initial_rate: number;
  };
  baseline: {
    schedule: ScheduleEntry[];
    total_interest: number;
  };
  simulation: {
    schedule: ScheduleEntry[];
    total_interest: number;
  };
  actual_metrics: {
    interest_saved: number;
    months_saved: number;
    interest_saved_to_date: number;
  };
  simulated_metrics: {
    interest_saved: number;
    months_saved: number;
    total_interest: number;
  };
  overpayments_list: OverpaymentEntry[];
}

interface ScheduleQueryParams {
  monthly_overpayment?: number;
  simulated_action?: OverpaymentType;
}
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const LoanSimulator: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<LoanScheduleResponse | null>(null);
  
  // Forms state
  const [overpaymentAmount, setOverpaymentAmount] = useState('');
  const [overpaymentDate, setOverpaymentDate] = useState(new Date().toISOString().split('T')[0]);
  const [overpaymentType, setOverpaymentType] = useState<OverpaymentType>('REDUCE_TERM');
  
  const [newRate, setNewRate] = useState('');
  const [rateDate, setRateDate] = useState(new Date().toISOString().split('T')[0]);

  // Monthly Simulation State
  const [monthlyOverpayment, setMonthlyOverpayment] = useState<number>(0);
  const [debouncedMonthlyOverpayment, setDebouncedMonthlyOverpayment] = useState<number>(0);
  const [simulatedAction, setSimulatedAction] = useState<OverpaymentType>('REDUCE_TERM');

  // Budget Integration State
  const [envelopes, setEnvelopes] = useState<Envelope[]>([]);
  const [accounts, setAccounts] = useState<BudgetAccount[]>([]);
  const [payInstallmentModalOpen, setPayInstallmentModalOpen] = useState(false);
  const [payFromEnvelope, setPayFromEnvelope] = useState(false); // For overpayment form
  const [selectedEnvelopeId, setSelectedEnvelopeId] = useState<number | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  
  // Pay Installment Modal State
  const [installmentEnvelopeId, setInstallmentEnvelopeId] = useState<number | null>(null);
  const [installmentAccountId, setInstallmentAccountId] = useState<number | null>(null);

  useEffect(() => {
    const fetchBudget = async () => {
      try {
        const summary = await budgetApi.getSummary();
        setEnvelopes(summary.envelopes);
        setAccounts(summary.accounts);
        if (summary.accounts.length > 0) {
           setInstallmentAccountId(summary.accounts[0].id);
           setSelectedAccountId(summary.accounts[0].id);
        }
      } catch (err) {
        console.error("Failed to fetch budget data", err);
      }
    };
    fetchBudget();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedMonthlyOverpayment(monthlyOverpayment);
    }, 500); // 500ms debounce

    return () => clearTimeout(timer);
  }, [monthlyOverpayment]);

  const fetchData = useCallback(async (loanId: number) => {
    try {
      setLoading(true);
      const params: ScheduleQueryParams = {};
      if (debouncedMonthlyOverpayment > 0) {
        params.monthly_overpayment = debouncedMonthlyOverpayment;
        params.simulated_action = simulatedAction;
      }
      const response = await getSchedule(loanId, params);
      setData(response as LoanScheduleResponse);
    } catch (error) {
      console.error('Error fetching loan schedule:', error);
    } finally {
      setLoading(false);
    }
  }, [debouncedMonthlyOverpayment, simulatedAction]);

  useEffect(() => {
    if (id) {
      fetchData(parseInt(id));
    }
  }, [id, fetchData]);

  const handleAddOverpayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    try {
      // 1. If Pay from Envelope is checked, record expense in Budget
      if (payFromEnvelope && selectedEnvelopeId && selectedAccountId) {
          await budgetApi.expense(
              selectedEnvelopeId, 
              selectedAccountId, 
              parseFloat(overpaymentAmount), 
              `Nadpłata kredytu: ${loan?.name}`
          );
      }

      // 2. Add Overpayment to Loan
      await addOverpayment(parseInt(id), {
        amount: parseFloat(overpaymentAmount),
        date: overpaymentDate,
        type: overpaymentType,
      });
      setOverpaymentAmount('');
      setPayFromEnvelope(false);
      fetchData(parseInt(id));
    } catch (error) {
      console.error('Error adding overpayment:', error);
      alert('Error processing payment. Check console.');
    }
  };

  const handlePayInstallment = async () => {
      if (!installmentEnvelopeId || !installmentAccountId || !currentInstallment) return;
      try {
          await budgetApi.expense(
              installmentEnvelopeId,
              installmentAccountId,
              currentInstallment,
              `Rata kredytu: ${loan?.name}`
          );
          setPayInstallmentModalOpen(false);
          alert('Rata została opłacona z budżetu (Wydatek zarejestrowany).');
      } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Nieznany błąd';
          alert(`Błąd płatności: ${errorMessage}`);
      }
  };

  const handleAddRate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    try {
      await addRate(parseInt(id), {
        interest_rate: parseFloat(newRate),
        valid_from_date: rateDate,
      });
      setNewRate('');
      fetchData(parseInt(id));
    } catch (error) {
      console.error('Error adding rate:', error);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(amount);
  };

  if (loading && !data) return <div className="p-8 text-center">Loading...</div>;
  if (!data) return <div className="p-8 text-center">Loan not found</div>;

  const { loan, baseline, simulation, actual_metrics, simulated_metrics, overpayments_list } = data;

  // Unified Chart Data Logic
  const allDates = Array.from(new Set([
    ...baseline.schedule.map((entry) => entry.date),
    ...simulation.schedule.map((entry) => entry.date)
  ])).sort();

  let lastBaseline = baseline.schedule[0]?.remaining_balance || 0;
  let lastSimulated = simulation.schedule[0]?.remaining_balance || 0;

  const unifiedChartData = allDates.map((date) => {
    const basePoint = baseline.schedule.find((entry) => entry.date === date);
    const simPoint = simulation.schedule.find((entry) => entry.date === date);

    if (basePoint) lastBaseline = basePoint.remaining_balance;
    if (simPoint) lastSimulated = simPoint.remaining_balance;

    return {
      date: date,
      formattedDate: new Date(date).toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric' }),
      baseline_balance: lastBaseline,
      simulated_balance: lastSimulated
    };
  });

  const chartData: ChartData<'line', number[], string> = {
    labels: unifiedChartData.map(d => d.formattedDate),
    datasets: [
      {
        label: 'Harmonogram Bazowy',
        data: unifiedChartData.map(d => d.baseline_balance),
        borderColor: 'rgb(255, 99, 132)', // Red
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
        stepped: 'before',
        tension: 0.1,
      },
      {
        label: 'Symulacja (z nadpłatami)',
        data: unifiedChartData.map(d => d.simulated_balance),
        borderColor: 'rgb(53, 162, 235)', // Blue
        backgroundColor: 'rgba(53, 162, 235, 0.5)',
        stepped: 'before',
        tension: 0.1,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Symulacja Spłaty Kredytu',
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Pozostały Kapitał (PLN)'
        }
      }
    }
  };

  // Current Stats
  const today = new Date();
  const currentEntry = simulation.schedule.find((entry) => new Date(entry.date) > today) || simulation.schedule[simulation.schedule.length - 1];
  
  const currentBalance = currentEntry ? currentEntry.remaining_balance : 0;
  const currentRate = currentEntry ? currentEntry.interest_rate : loan.initial_rate; 
  const currentInstallment = currentEntry ? currentEntry.installment : 0;
  
  const actualInterestSaved = actual_metrics ? actual_metrics.interest_saved : 0;
  const actualMonthsSaved = actual_metrics ? actual_metrics.months_saved : 0;
  const interestSavedToDate = actual_metrics ? actual_metrics.interest_saved_to_date : 0;

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
      <div className="flex items-center">
        <button onClick={() => navigate('/loans')} className="mr-4 text-gray-500 hover:text-gray-700">
          <ArrowLeft className="h-6 w-6" />
        </button>
        <div className="flex items-center space-x-3">
             <h1 className="text-2xl font-bold text-gray-900">{loan.name}</h1>
             <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full items-center ${getCategoryBadge(loan.category).color}`}>
                <span className="mr-1">{getCategoryBadge(loan.category).icon}</span>
                {getCategoryBadge(loan.category).label}
             </span>
        </div>
      </div>

      {/* Top Stats */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <div className="bg-white overflow-hidden shadow rounded-lg p-5">
          <dt className="text-sm font-medium text-gray-500 truncate">Pozostały Kapitał</dt>
          <dd className="mt-1 text-2xl font-semibold text-gray-900">{formatCurrency(currentBalance)}</dd>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5">
          <dt className="text-sm font-medium text-gray-500 truncate">Obecne Oprocentowanie</dt>
          <dd className="mt-1 text-2xl font-semibold text-gray-900">{currentRate}%</dd>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg p-5">
          <dt className="text-sm font-medium text-gray-500 truncate">Bieżąca Rata</dt>
          <dd className="mt-1 text-2xl font-semibold text-gray-900">{formatCurrency(currentInstallment)}</dd>
          <button 
            onClick={() => setPayInstallmentModalOpen(true)}
            className="mt-2 text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
          >
            <Wallet className="w-4 h-4 mr-1" /> Zapłać z Budżetu
          </button>
        </div>
      </div>

      {/* Savings Summary (Actual) */}
      <div className="bg-green-50 border-l-4 border-green-400 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <TrendingUp className="h-5 w-5 text-green-400" />
          </div>
          <div className="ml-3 w-full">
            <h3 className="text-lg leading-6 font-medium text-green-800">Zrealizowane Oszczędności</h3>
            <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-green-700">
              <div>
                 <p className="text-xs uppercase tracking-wide font-semibold text-green-600">Całkowita oszczędność</p>
                 <p className="font-bold text-xl">{formatCurrency(actualInterestSaved)}</p>
              </div>
              <div>
                 <p className="text-xs uppercase tracking-wide font-semibold text-green-600">Czas skrócony o</p>
                 <p className="font-bold text-xl">{actualMonthsSaved} miesięcy</p>
              </div>
              <div className="bg-green-100 p-2 rounded-md">
                 <p className="text-xs uppercase tracking-wide font-bold text-green-800">Zaoszczędzone do dzisiaj</p>
                 <p className="font-bold text-xl text-green-900">{formatCurrency(interestSavedToDate)}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart & Simulation */}
        <div className="lg:col-span-2 space-y-6">
            <div className="bg-white shadow rounded-lg p-4">
                <Line options={options} data={chartData} />
            </div>

             {/* Monthly Simulation Input */}
             <div className="bg-white shadow rounded-lg p-4">
                <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
                    <Calculator className="h-5 w-5 mr-2 text-indigo-500" />
                    Symulator Przyszłości
                </h3>
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Symulowana stała nadpłata (co miesiąc)</label>
                        <div className="mt-1 flex rounded-md shadow-sm">
                            <span className="inline-flex items-center px-3 rounded-l-md border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                                PLN
                            </span>
                            <input
                                type="number"
                                min="0"
                                step="50"
                                className="focus:ring-indigo-500 focus:border-indigo-500 flex-1 block w-full rounded-none rounded-r-md sm:text-sm border-gray-300"
                                placeholder="0.00"
                                value={monthlyOverpayment}
                                onChange={(e) => setMonthlyOverpayment(parseFloat(e.target.value) || 0)}
                            />
                        </div>
                    </div>
                    
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Cel symulacji</label>
                        <select
                            className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                            value={simulatedAction}
                            onChange={(e) => setSimulatedAction(e.target.value as OverpaymentType)}
                        >
                            <option value="REDUCE_TERM">Skrócenie okresu</option>
                            <option value="REDUCE_INSTALLMENT">Zmniejszenie raty</option>
                        </select>
                    </div>

                    <p className="text-sm text-gray-500">
                        Wpisz kwotę, którą planujesz nadpłacać co miesiąc, aby zobaczyć jak zmieni się wykres i oszczędności.
                    </p>

                    {simulated_metrics && monthlyOverpayment > 0 && (
                        <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mt-4">
                            <div className="flex">
                                <div className="ml-3">
                                    <h3 className="text-sm font-medium text-blue-800">Wyniki Symulacji</h3>
                                    <div className="mt-2 text-sm text-blue-700">
                                        <p>Potencjalne oszczędności: <span className="font-bold">{formatCurrency(simulated_metrics.interest_saved)}</span></p>
                                        <p>Potencjalne skrócenie czasu: <span className="font-bold">{simulated_metrics.months_saved} miesięcy</span></p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
             
             {/* Executed Overpayments List */}
             {overpayments_list && overpayments_list.length > 0 && (
                 <div className="bg-white shadow rounded-lg p-4">
                     <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
                         <List className="h-5 w-5 mr-2 text-gray-500" />
                         Wprowadzone nadpłaty jednorazowe
                     </h3>
                     <div className="overflow-x-auto">
                         <table className="min-w-full divide-y divide-gray-200">
                             <thead className="bg-gray-50">
                                 <tr>
                                     <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Data</th>
                                     <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Kwota</th>
                                 </tr>
                             </thead>
                             <tbody className="bg-white divide-y divide-gray-200">
                                {overpayments_list.map((op, idx: number) => (
                                    <tr key={idx}>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                            {new Date(op.date).toLocaleDateString('pl-PL')}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                                            {formatCurrency(op.amount)}
                                            {op.type ? (
                                                <span className={`ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                                    op.type === 'REDUCE_INSTALLMENT' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
                                                }`}>
                                                    {op.type === 'REDUCE_INSTALLMENT' ? 'Zmniejszenie Raty' : 'Skrócenie Okresu'}
                                                </span>
                                            ) : (
                                                <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                                    Skrócenie Okresu
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                         </table>
                     </div>
                 </div>
             )}
        </div>

        {/* Forms */}
        <div className="space-y-6">
          {/* Add Overpayment */}
          <div className="bg-white shadow rounded-lg p-4">
            <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
              <DollarSign className="h-5 w-5 mr-2 text-blue-500" />
              Dodaj Nadpłatę (Jednorazową)
            </h3>
            <form onSubmit={handleAddOverpayment} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">Kwota (PLN)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                  value={overpaymentAmount}
                  onChange={(e) => setOverpaymentAmount(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Data</label>
                <input
                  type="date"
                  required
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                  value={overpaymentDate}
                  onChange={(e) => setOverpaymentDate(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Cel Nadpłaty</label>
                <select
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                  value={overpaymentType}
                  onChange={(e) => setOverpaymentType(e.target.value as OverpaymentType)}
                >
                  <option value="REDUCE_TERM">Skrócenie Okresu</option>
                  <option value="REDUCE_INSTALLMENT">Zmniejszenie Raty</option>
                </select>
              </div>

              {/* Budget Integration for Overpayment */}
              <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                  <div className="flex items-center mb-2">
                      <input 
                        type="checkbox" 
                        id="payFromEnvelope" 
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        checked={payFromEnvelope}
                        onChange={e => setPayFromEnvelope(e.target.checked)}
                      />
                      <label htmlFor="payFromEnvelope" className="ml-2 block text-sm text-gray-900">
                          Pobierz środki z Koperty (Budżet)
                      </label>
                  </div>
                  {payFromEnvelope && (
                      <div className="space-y-2 mt-2">
                          <select 
                             className="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
                             value={selectedAccountId || ''}
                             onChange={e => setSelectedAccountId(Number(e.target.value))}
                             required={payFromEnvelope}
                          >
                              <option value="">Wybierz Konto</option>
                              {accounts.map(a => <option key={a.id} value={a.id}>{a.name} ({a.balance} {a.currency})</option>)}
                          </select>
                          <select 
                             className="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
                             value={selectedEnvelopeId || ''}
                             onChange={e => setSelectedEnvelopeId(Number(e.target.value))}
                             required={payFromEnvelope}
                          >
                              <option value="">Wybierz Kopertę</option>
                              {envelopes.map(e => <option key={e.id} value={e.id}>{e.icon} {e.name} ({e.balance} PLN)</option>)}
                          </select>
                      </div>
                  )}
              </div>

              <button
                type="submit"
                className="w-full inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Zapisz Nadpłatę
              </button>
            </form>
          </div>

          {/* Add Rate Change */}
          <div className="bg-white shadow rounded-lg p-4">
            <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
              <Calendar className="h-5 w-5 mr-2 text-orange-500" />
              Zmiana Oprocentowania
            </h3>
            <form onSubmit={handleAddRate} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">Nowe Oprocentowanie (%)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                  value={newRate}
                  onChange={(e) => setNewRate(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Obowiązuje od</label>
                <input
                  type="date"
                  required
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                  value={rateDate}
                  onChange={(e) => setRateDate(e.target.value)}
                />
              </div>
              <button
                type="submit"
                className="w-full inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-orange-600 hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500"
              >
                Zapisz Zmianę
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Pay Installment Modal */}
      {payInstallmentModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl">
             <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                 <Wallet className="h-6 w-6 text-blue-600" />
                 Opłać Ratę z Budżetu
             </h2>
             <div className="space-y-4">
                 <p className="text-gray-600">
                     Zarejestruj wydatek w budżecie na kwotę bieżącej raty: 
                     <span className="font-bold text-gray-900 ml-1">{formatCurrency(currentInstallment)}</span>
                 </p>
                 
                 <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Z Konta</label>
                    <select 
                        className="w-full p-2 border rounded"
                        value={installmentAccountId || ''}
                        onChange={e => setInstallmentAccountId(Number(e.target.value))}
                    >
                        <option value="">Wybierz Konto</option>
                        {accounts.map(a => <option key={a.id} value={a.id}>{a.name} ({a.balance} {a.currency})</option>)}
                    </select>
                 </div>

                 <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Z Koperty</label>
                    <select 
                        className="w-full p-2 border rounded"
                        value={installmentEnvelopeId || ''}
                        onChange={e => setInstallmentEnvelopeId(Number(e.target.value))}
                    >
                        <option value="">Wybierz Kopertę</option>
                        {envelopes.map(e => <option key={e.id} value={e.id}>{e.icon} {e.name} ({e.balance} PLN)</option>)}
                    </select>
                 </div>

                 <div className="flex justify-end gap-2 mt-6">
                     <button 
                        onClick={() => setPayInstallmentModalOpen(false)}
                        className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
                     >
                        Anuluj
                     </button>
                     <button 
                        onClick={handlePayInstallment}
                        disabled={!installmentAccountId || !installmentEnvelopeId}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                     >
                        Potwierdź Płatność
                     </button>
                 </div>
             </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LoanSimulator;
