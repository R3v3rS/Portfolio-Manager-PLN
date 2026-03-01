import React, { useEffect, useState } from 'react';
import { budgetApi, BudgetSummary, Envelope, EnvelopeLoan } from '../../api_budget';
import { Banknote, Plus, FolderPlus, Wallet, Send, MinusCircle, ArrowRightLeft, TrendingUp, PieChart, AlertTriangle, ChevronDown, Percent, ChevronLeft, ChevronRight, Copy, XCircle, Pencil } from 'lucide-react';
import TransactionHistory from './TransactionHistory';
import BudgetAnalytics from './BudgetAnalytics';

export default function BudgetDashboard() {
  const [summary, setSummary] = useState<BudgetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'envelopes' | 'analytics'>('envelopes');
  const [selectedMonth, setSelectedMonth] = useState(new Date().toISOString().slice(0, 7));
  const [newEnvelopeType, setNewEnvelopeType] = useState<'MONTHLY' | 'LONG_TERM'>('MONTHLY');

  // Modal States
  const [showIncomeModal, setShowIncomeModal] = useState(false);
  const [showAllocateModal, setShowAllocateModal] = useState(false);
  const [showExpenseModal, setShowExpenseModal] = useState(false);
  const [showQuickExpenseModal, setShowQuickExpenseModal] = useState(false);
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showInvestmentModal, setShowInvestmentModal] = useState(false);
  const [showBorrowModal, setShowBorrowModal] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [showEnvelopeModal, setShowEnvelopeModal] = useState(false);
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [showEditPlanModal, setShowEditPlanModal] = useState(false);

  // Form Data
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedEnvelopeId, setSelectedEnvelopeId] = useState<number | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [sourceEnvelopeId, setSourceEnvelopeId] = useState<number | null>(null);
  const [targetAccountId, setTargetAccountId] = useState<number | null>(null);
  const [targetEnvelopeId, setTargetEnvelopeId] = useState<number | null>(null);
  const [targetAccountEnvelopes, setTargetAccountEnvelopes] = useState<Envelope[]>([]);
  const [targetPortfolioId, setTargetPortfolioId] = useState<number | null>(null);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newEnvelopeName, setNewEnvelopeName] = useState('');
  const [targetAmount, setTargetAmount] = useState('');
  const [editPlanAmount, setEditPlanAmount] = useState('');
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [newAccountName, setNewAccountName] = useState('');
  const [newAccountBalance, setNewAccountBalance] = useState('');

  const [categories, setCategories] = useState<any[]>([]);
  const [portfolios, setPortfolios] = useState<any[]>([]);

  useEffect(() => {
    fetchData();
    if (categories.length === 0) fetchCategories();
    if (portfolios.length === 0) fetchPortfolios();
  }, [selectedAccountId, selectedMonth]);

  useEffect(() => {
    if (targetAccountId) {
      budgetApi.getEnvelopes(targetAccountId).then(setTargetAccountEnvelopes).catch(console.error);
    } else {
      setTargetAccountEnvelopes([]);
    }
    setTargetEnvelopeId(null);
  }, [targetAccountId]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const data = await budgetApi.getSummary(selectedAccountId || undefined, selectedMonth);
      setSummary(data);
      if (data.accounts.length > 0 && !selectedAccountId) {
        setSelectedAccountId(data.accounts[0].id);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await fetch('http://localhost:5000/api/budget/categories');
      const data = await res.json();
      setCategories(data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchPortfolios = async () => {
    try {
      const res = await fetch('http://localhost:5000/api/portfolio/list');
      const data = await res.json();
      setPortfolios(data.portfolios || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddIncome = async () => {
    if (!selectedAccountId || !amount) return;
    try {
      await budgetApi.addIncome(selectedAccountId, parseFloat(amount), description, transactionDate);
      setShowIncomeModal(false);
      resetForms();
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleAllocate = async () => {
    if (!selectedEnvelopeId || !amount) return;
    try {
      await budgetApi.allocate(selectedEnvelopeId, parseFloat(amount), transactionDate);
      setShowAllocateModal(false);
      resetForms();
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleExpense = async () => {
    if (!selectedAccountId || !amount) return;
    try {
      // If selectedEnvelopeId is null, it's a Quick Expense (Direct from Free Pool)
      await budgetApi.expense(selectedEnvelopeId || null, selectedAccountId, parseFloat(amount), description, transactionDate);
      setShowExpenseModal(false);
      setShowQuickExpenseModal(false);
      resetForms();
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleTransfer = async () => {
    if (!selectedAccountId || !targetAccountId || !amount) return;
    if (selectedAccountId === targetAccountId) {
      alert("Source and Destination accounts must be different.");
      return;
    }
    try {
      await budgetApi.transferBetweenAccounts(selectedAccountId, targetAccountId, parseFloat(amount), description, transactionDate, targetEnvelopeId, sourceEnvelopeId);
      setShowTransferModal(false);
      resetForms();
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleInvestmentTransfer = async () => {
    if (!selectedAccountId || !targetPortfolioId || !amount) return;
    try {
      await budgetApi.transferToPortfolio(
        selectedAccountId, 
        targetPortfolioId, 
        parseFloat(amount), 
        selectedEnvelopeId || null, // null means Free Pool
        description || "Transfer to Investments",
        transactionDate
      );
      setShowInvestmentModal(false);
      resetForms();
      fetchData();
      alert("Pomyślnie przesłano środki do portfela inwestycyjnego!");
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleBorrow = async () => {
    if (!selectedEnvelopeId || !amount) return;
    try {
      await budgetApi.borrow(selectedEnvelopeId, parseFloat(amount), description);
      setShowBorrowModal(false);
      resetForms();
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleCreateCategory = async () => {
    if (!newCategoryName) return;
    try {
      await budgetApi.createCategory(newCategoryName);
      setShowCategoryModal(false);
      setNewCategoryName('');
      fetchCategories();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleCreateEnvelope = async () => {
    if (!newEnvelopeName || !selectedCategoryId || !selectedAccountId) return;
    try {
      await budgetApi.createEnvelope(
          selectedCategoryId, 
          selectedAccountId, 
          newEnvelopeName, 
          '✉️', 
          targetAmount ? parseFloat(targetAmount) : undefined,
          newEnvelopeType,
          selectedMonth
      );
      setShowEnvelopeModal(false);
      setNewEnvelopeName('');
      setTargetAmount('');
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleCloseEnvelope = async (id: number) => {
    if (confirm("Czy na pewno chcesz zamknąć tę kopertę? Środki z kopert miesięcznych wrócą do puli wolnych środków.")) {
      try {
        await budgetApi.closeEnvelope(id);
        fetchData();
      } catch (err: any) {
        alert(err.message);
      }
    }
  };

  const changeMonth = (delta: number) => {
    const [year, month] = selectedMonth.split('-').map(Number);
    const date = new Date(year, month - 1 + delta, 1);
    const newMonth = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    setSelectedMonth(newMonth);
  };

  const handleCloneBudget = async () => {
    if (!selectedAccountId) return;
    const [year, month] = selectedMonth.split('-').map(Number);
    
    // Previous month
    const prevDate = new Date(year, month - 2, 1);
    const prevMonthStr = `${prevDate.getFullYear()}-${String(prevDate.getMonth() + 1).padStart(2, '0')}`;
    
    if (confirm(`Czy na pewno chcesz skopiować budżet miesięczny z ${prevMonthStr} do ${selectedMonth}?`)) {
         try {
             await budgetApi.cloneBudget(selectedAccountId, prevMonthStr, selectedMonth);
             fetchData();
         } catch (err: any) {
             alert(err.message);
         }
    }
  };

  const handleCreateAccount = async () => {
    if (!newAccountName) return;
    try {
      await budgetApi.createAccount(newAccountName, parseFloat(newAccountBalance || '0'));
      setShowAccountModal(false);
      setNewAccountName('');
      setNewAccountBalance('');
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleUpdatePlan = async () => {
    if (!selectedEnvelopeId || !editPlanAmount) return;
    try {
      await budgetApi.updateEnvelope(selectedEnvelopeId, parseFloat(editPlanAmount));
      setShowEditPlanModal(false);
      setEditPlanAmount('');
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleRepay = async (loanId: number, amount: number) => {
    try {
      await budgetApi.repay(loanId, amount);
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleReset = async () => {
    if (confirm("WARNING: This will DELETE ALL budget data (Transactions, Envelopes, Loans). Are you sure?")) {
      try {
        await fetch('http://localhost:5000/api/budget/reset', { method: 'POST' });
        alert("Budget data reset successfully.");
        window.location.reload(); // Reload to clear all states
      } catch (err: any) {
        alert("Error resetting data: " + err.message);
      }
    }
  };

  const resetForms = () => {
    setAmount('');
    setDescription('');
    setTransactionDate(new Date().toISOString().split('T')[0]);
    setSelectedEnvelopeId(null);
    setSourceEnvelopeId(null);
    setTargetAccountId(null);
    setTargetEnvelopeId(null);
    setTargetPortfolioId(null);
    setEditPlanAmount('');
    // Don't reset selectedAccountId
  };

  const getProgressColorClass = (balance: number, target: number) => {
    if (balance < 0) return 'bg-red-500';
    if (!target) return 'bg-blue-500';
    const ratio = balance / target;
    if (ratio >= 1) return 'bg-green-500'; // Well funded
    if (ratio > 0.2) return 'bg-yellow-400'; // Moderate
    return 'bg-red-400'; // Nearly empty / Critical
  };

  if (loading && !summary) return <div className="p-8 text-center">Loading budget...</div>;
  if (error) return <div className="p-8 text-red-500">Error: {error}</div>;

  const monthlyEnvelopes = summary?.envelopes.filter(e => (e.type === 'MONTHLY' || !e.type)) || [];
  const activeMonthly = monthlyEnvelopes.filter(e => e.status !== 'CLOSED');
  const closedMonthly = monthlyEnvelopes.filter(e => e.status === 'CLOSED');
  
  const longTermEnvelopes = summary?.envelopes.filter(e => e.type === 'LONG_TERM' && e.status !== 'CLOSED') || [];

  const groupByCategory = (envs: Envelope[]) => envs.reduce((acc, env) => {
    const catName = env.category_name || 'Uncategorized';
    if (!acc[catName]) acc[catName] = [];
    acc[catName].push(env);
    return acc;
  }, {} as Record<string, Envelope[]>);

  const monthlyByCategory = groupByCategory(activeMonthly);
  const closedByCategory = groupByCategory(closedMonthly);
  const longTermByCategory = groupByCategory(longTermEnvelopes);

  const currentAccount = summary?.accounts.find(a => a.id === selectedAccountId);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 bg-gray-50 min-h-screen">
      {/* Account Tabs */}
      {summary?.accounts && summary.accounts.length > 0 ? (
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-gray-200 pb-2 gap-4">
          <div className="flex space-x-2 overflow-x-auto w-full sm:w-auto">
            {summary.accounts.map(account => (
              <button
                key={account.id}
                onClick={() => setSelectedAccountId(account.id)}
                className={`
                  px-4 py-2 rounded-t-lg text-sm font-medium transition-all whitespace-nowrap border-b-2
                  ${selectedAccountId === account.id 
                    ? 'border-blue-600 text-blue-600 bg-blue-50' 
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'}
                `}
              >
                {account.name}
              </button>
            ))}
            <button 
              onClick={() => setShowAccountModal(true)}
              className="px-3 py-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
              title="Add New Account"
            >
              <Plus className="w-5 h-5" />
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-yellow-50 p-6 rounded-xl border border-yellow-200 text-yellow-800 mb-6 flex flex-col items-center justify-center">
          <p className="mb-4 text-lg font-medium">Dodaj swoje pierwsze konto bankowe, aby rozpocząć budżetowanie.</p>
          <button 
            onClick={() => setShowAccountModal(true)} 
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
          >
            <Wallet className="w-5 h-5" /> Add New Account
          </button>
        </div>
      )}

      {/* Only show content if we have an account selected */}
      {selectedAccountId && (
        <>
          {/* Header Controls */}
          <div className="flex justify-end mb-2">
               <button 
                 onClick={handleReset}
                 className="text-xs text-red-500 hover:text-red-700 hover:underline"
               >
                 [DEBUG] Reset All Budget Data
               </button>
          </div>

          {/* Control Panel (Top Stats) */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            
            {/* Free Pool Widget */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 relative overflow-hidden">
               <div className="absolute top-0 right-0 p-2 opacity-10">
                   <Wallet className="w-24 h-24 text-green-600" />
               </div>
              <p className="text-sm text-gray-500 mb-1 font-medium">Free Pool (To Allocate)</p>
              <p className="text-3xl font-bold text-green-600">{summary?.free_pool.toFixed(2)} PLN</p>
              <div className="flex gap-2 mt-4 relative z-10">
                  <button 
                    onClick={() => setShowAllocateModal(true)}
                    className="flex-1 bg-green-100 text-green-700 py-2 rounded-lg hover:bg-green-200 transition flex items-center justify-center gap-2 text-sm font-medium"
                  >
                    Allocate
                  </button>
                  <button 
                    onClick={() => setShowIncomeModal(true)}
                    className="flex-1 bg-gray-100 text-gray-700 py-2 rounded-lg hover:bg-gray-200 transition flex items-center justify-center gap-2 text-sm font-medium"
                  >
                    <Plus className="w-4 h-4" /> Income
                  </button>
              </div>
            </div>

            {/* Savings Rate Widget */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 relative overflow-hidden">
              <div className="absolute top-0 right-0 p-2 opacity-10">
                   <Percent className="w-24 h-24 text-blue-600" />
               </div>
              <p className="text-sm text-gray-500 mb-1 font-medium">Savings Rate</p>
              <div className="flex items-baseline gap-2">
                <p className="text-3xl font-bold text-blue-600">
                    {summary?.flow_analysis?.savings_rate.toFixed(1)}%
                </p>
                <span className="text-xs text-gray-400">Target: 20%+</span>
              </div>
              <div className="mt-4 text-sm text-gray-500">
                  Inv. Transfer: <span className="font-semibold text-gray-700">{summary?.flow_analysis?.investment_transfers.toFixed(0)} PLN</span>
              </div>
              <button 
                onClick={() => setShowInvestmentModal(true)}
                className="w-full mt-2 bg-blue-50 text-blue-700 py-2 rounded-lg hover:bg-blue-100 transition text-sm font-medium flex items-center justify-center gap-2"
              >
                <TrendingUp className="w-4 h-4" /> Transfer to Invest
              </button>
            </div>

             {/* Internal Debt Widget */}
             <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <p className="text-sm text-gray-500 mb-1 font-medium">Internal Debt</p>
              <p className="text-3xl font-bold text-red-600">{summary?.total_borrowed.toFixed(2)} PLN</p>
              <div className="mt-4 flex gap-2">
                   {/* Borrow / Repay Menu */}
                   <button 
                     onClick={() => setShowBorrowModal(true)}
                     className="flex-1 bg-red-50 text-red-700 py-2 rounded-lg hover:bg-red-100 transition text-sm font-medium"
                   >
                     Borrow
                   </button>
                   {/* Repay is usually done per loan, but maybe a quick action? For now just Borrow */}
                   <button 
                     onClick={() => document.getElementById('loans-section')?.scrollIntoView({ behavior: 'smooth' })}
                     className="flex-1 bg-gray-50 text-gray-700 py-2 rounded-lg hover:bg-gray-100 transition text-sm font-medium"
                   >
                     Manage Loans
                   </button>
              </div>
            </div>

            {/* Quick Actions / Summary */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col justify-between">
                <div>
                    <p className="text-sm text-gray-500 mb-1 font-medium">Account Balance</p>
                    <p className="text-2xl font-bold text-gray-900">{summary?.account_balance.toFixed(2)} PLN</p>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-4">
                     <button 
                        onClick={() => setShowQuickExpenseModal(true)}
                        className="bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-1"
                     >
                         <MinusCircle className="w-4 h-4" /> Expense
                     </button>
                     <button 
                        onClick={() => setShowTransferModal(true)}
                        className="bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-1"
                     >
                         <ArrowRightLeft className="w-4 h-4" /> Transfer
                     </button>
                </div>
            </div>
          </div>

          {/* View Toggle & Actions */}
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 border-b border-gray-200 pb-4">
            <div className="flex bg-white p-1 rounded-lg shadow-sm border border-gray-200">
                <button 
                    onClick={() => setActiveTab('envelopes')}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'envelopes' ? 'bg-gray-100 text-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
                >
                    <div className="flex items-center gap-2">
                        <Banknote className="w-4 h-4" /> Envelope Grid
                    </div>
                </button>
                <button 
                    onClick={() => setActiveTab('analytics')}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'analytics' ? 'bg-gray-100 text-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
                >
                    <div className="flex items-center gap-2">
                        <PieChart className="w-4 h-4" /> Analytics
                    </div>
                </button>
            </div>

            {activeTab === 'envelopes' && (
                <div className="flex gap-2">
                    <button onClick={() => setShowCategoryModal(true)} className="px-3 py-2 bg-white hover:bg-gray-50 rounded-lg text-gray-600 text-sm flex items-center gap-2 border border-gray-200 shadow-sm transition">
                    <FolderPlus className="w-4 h-4" /> New Category
                    </button>
                    <button onClick={() => setShowEnvelopeModal(true)} className="px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm flex items-center gap-2 shadow-sm transition">
                    <Banknote className="w-4 h-4" /> New Envelope
                    </button>
                </div>
            )}
          </div>

          {activeTab === 'analytics' ? (
              <BudgetAnalytics selectedAccountId={selectedAccountId} />
          ) : (
            <>
          {/* Month Progress & Selector */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
              {/* Selector */}
              <div className="flex items-center justify-between bg-white p-4 rounded-xl shadow-sm border border-gray-100">
                  <button onClick={() => changeMonth(-1)} className="p-2 hover:bg-gray-100 rounded-full transition">
                      <ChevronLeft className="w-5 h-5 text-gray-600" />
                  </button>
                  <span className="text-xl font-bold text-gray-800">{selectedMonth}</span>
                  <button onClick={() => changeMonth(1)} className="p-2 hover:bg-gray-100 rounded-full transition">
                      <ChevronRight className="w-5 h-5 text-gray-600" />
                  </button>
                  
                  <button 
                      onClick={handleCloneBudget}
                      className="ml-4 flex items-center gap-2 px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 transition text-sm font-medium"
                      title="Copy budget from previous month"
                  >
                      <Copy className="w-4 h-4" /> Clone
                  </button>
              </div>

              {/* Progress Widget */}
              {(() => {
                  const { day, daysInMonth, percent } = ((monthStr) => {
                      const now = new Date();
                      const [year, month] = monthStr.split('-').map(Number);
                      const days = new Date(year, month, 0).getDate();
                      if (year < now.getFullYear() || (year === now.getFullYear() && month < now.getMonth() + 1)) return { day: days, daysInMonth: days, percent: 100 };
                      if (year > now.getFullYear() || (year === now.getFullYear() && month > now.getMonth() + 1)) return { day: 0, daysInMonth: days, percent: 0 };
                      return { day: now.getDate(), daysInMonth: days, percent: (now.getDate() / days) * 100 };
                  })(selectedMonth);
                  
                  const totalBudget = monthlyEnvelopes.reduce((sum, env) => sum + (env.target_amount || 0), 0);
                  const totalSpent = monthlyEnvelopes.reduce((sum, env) => sum + (env.total_spent || 0), 0);
                  const budgetPercent = totalBudget > 0 ? (totalSpent / totalBudget) * 100 : 0;

                  return (
                      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-col justify-center">
                          <div className="flex justify-between text-sm text-gray-600 mb-1">
                              <span>Month Progress ({day}/{daysInMonth})</span>
                              <span className="font-bold">{percent.toFixed(0)}%</span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-2 mb-3">
                              <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${percent}%` }}></div>
                          </div>
                          
                          <div className="flex justify-between text-sm text-gray-600 mb-1">
                              <span>Budget Used ({totalSpent.toFixed(0)}/{totalBudget.toFixed(0)})</span>
                              <span className={`font-bold ${budgetPercent > percent ? 'text-red-500' : 'text-green-600'}`}>
                                  {budgetPercent.toFixed(0)}%
                              </span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-2">
                              <div 
                                  className={`h-2 rounded-full ${budgetPercent > percent ? 'bg-red-500' : 'bg-green-500'}`} 
                                  style={{ width: `${Math.min(budgetPercent, 100)}%` }}
                              ></div>
                          </div>
                      </div>
                  );
              })()}
          </div>

          {/* Envelopes Grid */}
          <div className="space-y-12">
            
            {/* Monthly Envelopes */}
            <div>
                <h2 className="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2">
                    <Banknote className="w-6 h-6 text-blue-600" /> Bieżące (Miesięczne)
                </h2>
                {Object.keys(monthlyByCategory).length === 0 ? (
                    <div className="text-center py-8 bg-white rounded-xl border border-dashed border-gray-300">
                        <p className="text-gray-500 italic mb-2">Brak aktywnych kopert miesięcznych na ten miesiąc.</p>
                        <button onClick={handleCloneBudget} className="text-indigo-600 font-medium hover:underline text-sm">Skopiuj z poprzedniego miesiąca</button>
                    </div>
                ) : (
                    Object.entries(monthlyByCategory).map(([category, envelopes]) => (
                      <div key={category} className="space-y-4 mb-8">
                        <h3 className="text-lg font-bold text-gray-700 flex items-center gap-2 pl-2 border-l-4 border-blue-400">
                          {category}
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                          {envelopes.map(env => {
                            const totalSpent = env.total_spent || 0;
                            const target = env.target_amount || 0;
                            const progress = target > 0 ? (totalSpent / target) * 100 : 0;
                            const isPaid = totalSpent >= target && env.balance === 0;
                            const isOverBudget = totalSpent > target;
                            
                            // Dim if balance is 0 and fully paid
                            const shouldDim = isPaid;

                            return (
                            <div key={env.id} className={`bg-white p-5 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition duration-200 relative group ${shouldDim ? 'opacity-60 grayscale-[0.5]' : ''}`}>
                              {/* Header */}
                              <div className="flex justify-between items-start mb-3">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-xl">
                                        {env.icon}
                                    </div>
                                    <div className="flex-1">
                                        <h4 className="font-bold text-gray-900 leading-tight">{env.name}</h4>
                                        {/* Badges */}
                                        <div className="flex gap-1 mt-1 flex-wrap">
                                            {isPaid && (
                                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                                    OPŁACONE ✅
                                                </span>
                                            )}
                                            {isOverBudget && (
                                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                                                    PRZEKROCZONE ⚠️
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                              </div>

                              {/* Stats Row */}
                              <div className="grid grid-cols-3 gap-2 mb-3 text-center text-sm border-t border-b border-gray-50 py-2 bg-gray-50/50 rounded-lg">
                                  <div>
                                      <p className="text-xs text-gray-500 uppercase tracking-wide">Plan</p>
                                      <div className="flex items-center justify-center gap-1 group/edit">
                                          <p className="font-semibold text-gray-700">{target.toFixed(0)}</p>
                                          <button 
                                              onClick={(e) => {
                                                  e.stopPropagation();
                                                  setSelectedEnvelopeId(env.id);
                                                  setEditPlanAmount(target.toString());
                                                  setShowEditPlanModal(true);
                                              }}
                                              className="opacity-0 group-hover/edit:opacity-100 text-gray-400 hover:text-blue-600 transition"
                                              title="Edit Plan"
                                          >
                                              <Pencil className="w-3 h-3" />
                                          </button>
                                      </div>
                                  </div>
                                  <div>
                                      <p className="text-xs text-gray-500 uppercase tracking-wide">Wydano</p>
                                      <p className="font-semibold text-blue-600">{totalSpent.toFixed(0)}</p>
                                  </div>
                                  <div>
                                      <p className="text-xs text-gray-500 uppercase tracking-wide">Zostało</p>
                                      <p className={`font-semibold ${env.balance < 0 ? 'text-red-600' : 'text-green-600'}`}>
                                          {env.balance.toFixed(0)}
                                      </p>
                                  </div>
                              </div>

                              {/* Loan Badge */}
                              {env.outstanding_loans && env.outstanding_loans > 0 ? (
                                  <div className="mb-3 bg-red-50 border border-red-100 rounded-md px-2 py-1 flex items-center gap-2 text-xs text-red-700 font-medium">
                                      <AlertTriangle className="w-3 h-3" />
                                      Debt: {env.outstanding_loans.toFixed(2)} PLN
                                  </div>
                              ) : null}
                              
                              {/* Progress Bar (Consumption) */}
                              {target > 0 && (
                                <div className="w-full bg-gray-100 rounded-full h-2.5 mb-4 overflow-hidden relative">
                                  <div 
                                    className={`h-full rounded-full transition-all duration-500 ${isOverBudget ? 'bg-red-500' : (isPaid ? 'bg-green-500' : 'bg-blue-500')}`}
                                    style={{ width: `${Math.min(progress, 100)}%` }}
                                  ></div>
                                </div>
                              )}

                              {/* Actions */}
                              <div className="grid grid-cols-4 gap-2 mt-2">
                                <button 
                                  onClick={() => { setSelectedEnvelopeId(env.id); setShowAllocateModal(true); }}
                                  className="col-span-2 bg-blue-600 text-white py-1.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition shadow-sm"
                                >
                                  {env.outstanding_loans && env.outstanding_loans > 0 ? 'Repay' : 'Allocate'}
                                </button>
                                <button 
                                  onClick={() => { setSelectedEnvelopeId(env.id); setShowExpenseModal(true); }}
                                  className="bg-white text-gray-700 border border-gray-200 py-1.5 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
                                >
                                  Spend
                                </button>
                                <button 
                                  onClick={() => { setSelectedEnvelopeId(env.id); setShowBorrowModal(true); }}
                                  className="bg-amber-50 text-amber-700 border border-amber-200 py-1.5 rounded-lg text-sm font-medium hover:bg-amber-100 transition"
                                >
                                  Borrow
                                </button>
                              </div>
                              
                              {/* Close Button */}
                              <button 
                                  onClick={() => handleCloseEnvelope(env.id)}
                                  className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition"
                                  title="Close Envelope"
                              >
                                  <XCircle className="w-4 h-4" />
                              </button>
                            </div>
                          )})}
                        </div>
                      </div>
                    ))
                )}
            </div>

            {/* Closed (Rozliczone) Envelopes */}
            {Object.keys(closedByCategory).length > 0 && (
                <div className="bg-gray-100 p-6 rounded-xl border border-gray-200">
                    <h2 className="text-xl font-bold text-gray-600 mb-4 flex items-center gap-2">
                        <XCircle className="w-5 h-5" /> Rozliczone (Zamknięte)
                    </h2>
                    {Object.entries(closedByCategory).map(([category, envelopes]) => (
                      <div key={category} className="space-y-4 mb-6 last:mb-0">
                        <h3 className="text-md font-bold text-gray-500 pl-2 border-l-4 border-gray-300">
                          {category}
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                          {envelopes.map(env => (
                            <div key={env.id} className="bg-white p-4 rounded-lg shadow-sm border border-gray-200 opacity-70 hover:opacity-100 transition">
                                <div className="flex justify-between items-center mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className="text-lg grayscale">{env.icon}</span>
                                        <span className="font-bold text-gray-700">{env.name}</span>
                                    </div>
                                    <span className="text-xs font-bold text-gray-500 bg-gray-100 px-2 py-1 rounded">CLOSED</span>
                                </div>
                                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                                    <div>
                                        <span className="text-gray-400">Plan</span>
                                        <p className="font-semibold text-gray-600">{(env.target_amount || 0).toFixed(0)}</p>
                                    </div>
                                    <div>
                                        <span className="text-gray-400">Wydano</span>
                                        <p className="font-semibold text-blue-600">{(env.total_spent || 0).toFixed(0)}</p>
                                    </div>
                                    <div>
                                        <span className="text-gray-400">Zostało</span>
                                        <p className={`font-semibold ${env.balance < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                                            {env.balance.toFixed(0)}
                                        </p>
                                    </div>
                                </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                </div>
            )}

            {/* Long Term Envelopes */}
            <div>
                <h2 className="text-2xl font-bold text-gray-800 mb-6 flex items-center gap-2 border-t pt-8">
                    <TrendingUp className="w-6 h-6 text-purple-600" /> Cele (Długoterminowe)
                </h2>
                {Object.keys(longTermByCategory).length === 0 ? (
                    <p className="text-gray-500 italic pl-4">Brak celów długoterminowych.</p>
                ) : (
                    Object.entries(longTermByCategory).map(([category, envelopes]) => (
                      <div key={category} className="space-y-4 mb-8">
                        <h3 className="text-lg font-bold text-gray-700 flex items-center gap-2 pl-2 border-l-4 border-purple-400">
                          {category}
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                          {envelopes.map(env => (
                            <div key={env.id} className="bg-white p-5 rounded-xl shadow-sm border border-purple-100 hover:shadow-md transition duration-200 relative group">
                              {/* Header */}
                              <div className="flex justify-between items-start mb-3">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-full bg-purple-50 flex items-center justify-center text-xl">
                                        {env.icon}
                                    </div>
                                    <div>
                                        <h4 className="font-bold text-gray-900 leading-tight">{env.name}</h4>
                                        {env.target_amount ? (
                                            <p className="text-xs text-gray-500 mt-0.5">Goal: {env.target_amount} PLN</p>
                                        ) : <p className="text-xs text-gray-400 mt-0.5">No target</p>}
                                    </div>
                                </div>
                                <div className="text-right">
                                     <span className="text-lg font-bold text-gray-900">
                                        {env.balance.toFixed(2)}
                                     </span>
                                     <span className="text-xs text-gray-400 block">Saved</span>
                                </div>
                              </div>
                              
                              {/* Progress Bar (Always show for Long Term if target exists) */}
                              {env.target_amount && (
                                <div className="w-full bg-gray-100 rounded-full h-3 mb-2 overflow-hidden">
                                  <div 
                                    className={`h-3 rounded-full transition-all duration-500 bg-purple-500`}
                                    style={{ width: `${Math.min((Math.max(env.balance, 0) / env.target_amount) * 100, 100)}%` }}
                                  ></div>
                                </div>
                              )}
                              {env.target_amount && (
                                  <p className="text-xs text-right text-gray-500 mb-4">
                                      {((env.balance / env.target_amount) * 100).toFixed(0)}% Complete
                                  </p>
                              )}

                              {/* Actions */}
                              <div className="grid grid-cols-3 gap-2 mt-2">
                                <button 
                                  onClick={() => { setSelectedEnvelopeId(env.id); setShowAllocateModal(true); }}
                                  className="bg-purple-600 text-white py-1.5 rounded-lg text-sm font-medium hover:bg-purple-700 transition shadow-sm"
                                >
                                  Add Funds
                                </button>
                                <button 
                                  onClick={() => { setSelectedEnvelopeId(env.id); setShowExpenseModal(true); }}
                                  className="bg-white text-gray-700 border border-gray-200 py-1.5 rounded-lg text-sm font-medium hover:bg-gray-50 transition"
                                >
                                  Spend
                                </button>
                                <button 
                                  onClick={() => handleCloseEnvelope(env.id)}
                                  className="bg-gray-50 text-gray-600 border border-gray-200 py-1.5 rounded-lg text-sm font-medium hover:bg-gray-100 transition"
                                >
                                  Close
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))
                )}
            </div>

          </div>

          {/* Internal Loans Section */}
          <div id="loans-section" className="scroll-mt-8">
          {summary?.loans && summary.loans.length > 0 && (
            <div className="bg-white p-6 rounded-xl shadow-sm border border-red-100 mt-12">
              <h3 className="text-lg font-bold text-red-800 mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5" /> Active Internal Loans
              </h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Source Envelope</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Reason</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Remaining</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {summary.loans.map(loan => (
                      <tr key={loan.id}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">{loan.source_envelope}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{loan.reason}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-red-600">{loan.remaining.toFixed(2)} PLN</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          <button 
                            onClick={() => handleRepay(loan.id, loan.remaining)}
                            className="text-green-600 hover:text-green-900 font-medium border border-green-200 px-3 py-1 rounded bg-green-50 hover:bg-green-100 transition"
                          >
                            Repay Full
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          </div>

          {/* Transaction History Section */}
          <div className="mt-12">
             <h3 className="text-xl font-bold text-gray-800 mb-4">Recent Transactions</h3>
              <TransactionHistory 
                selectedAccountId={selectedAccountId}
                categories={categories}
                envelopes={summary?.envelopes || []}
              />
          </div>
          </>
          )}
        </>
      )}

      {/* Modals */}
      {(showIncomeModal || showAllocateModal || showExpenseModal || showQuickExpenseModal || showBorrowModal || showCategoryModal || showEnvelopeModal || showAccountModal || showTransferModal || showInvestmentModal || showEditPlanModal) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50 backdrop-blur-sm">
          <div className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl transform transition-all">
            <h2 className="text-xl font-bold mb-4 text-gray-800 border-b pb-2">
              {showIncomeModal && 'Add Income'}
              {showAllocateModal && 'Allocate to Envelope'}
              {showExpenseModal && 'Record Expense'}
              {showQuickExpenseModal && 'Quick Expense (Free Pool)'}
              {showTransferModal && 'Transfer Between Accounts'}
              {showInvestmentModal && 'Transfer to Investment Portfolio'}
              {showBorrowModal && 'Borrow from Envelope'}
              {showCategoryModal && 'New Category'}
              {showEnvelopeModal && 'New Envelope'}
              {showAccountModal && 'New Account'}
              {showEditPlanModal && 'Edit Envelope Plan'}
            </h2>

            <div className="space-y-4">
              {/* Income Fields */}
              {showIncomeModal && (
                <>
                  <div className="p-3 bg-green-50 rounded-lg border border-green-100 text-green-800 text-sm">
                    Adding to: <span className="font-bold">{currentAccount?.name}</span>
                  </div>
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  <input type="number" placeholder="Amount" className="w-full p-2 border border-gray-300 rounded-lg mt-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description" className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Allocate Fields */}
              {showAllocateModal && (
                <>
                  <div className="p-3 bg-blue-50 rounded-lg border border-blue-100 text-blue-800 text-sm">
                      Available Free Pool: <b>{summary?.free_pool.toFixed(2)} PLN</b>
                  </div>
                  {!selectedEnvelopeId && (
                      <select 
                        className="w-full p-2 border border-gray-300 rounded-lg mt-2"
                        onChange={e => setSelectedEnvelopeId(Number(e.target.value))}
                      >
                          <option value="">Select Envelope</option>
                          {summary?.envelopes.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                      </select>
                  )}
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border border-gray-300 rounded-lg" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  <input type="number" placeholder="Amount" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={amount} onChange={e => setAmount(e.target.value)} />
                </>
              )}

              {/* Expense Fields */}
              {showExpenseModal && (
                <>
                  <div className="p-3 bg-red-50 rounded-lg border border-red-100 text-red-800 text-sm">
                    Paying from: <span className="font-bold">{currentAccount?.name}</span>
                  </div>
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border border-gray-300 rounded-lg" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  <input type="number" placeholder="Amount" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description" className="w-full p-2 border border-gray-300 rounded-lg" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Quick Expense Fields */}
              {showQuickExpenseModal && (
                <>
                   <div className="p-3 bg-orange-50 rounded-lg border border-orange-200 text-orange-800 text-sm">
                    This will be deducted directly from <b>Free Pool</b> (unallocated funds).
                  </div>
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border border-gray-300 rounded-lg" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  <input type="number" placeholder="Amount" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description" className="w-full p-2 border border-gray-300 rounded-lg" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Transfer Fields */}
              {showTransferModal && (
                <>
                   <div className="p-3 bg-blue-50 rounded-lg border border-blue-200 text-blue-800 text-sm mb-2">
                    Transferring from: <b>{currentAccount?.name}</b>
                  </div>
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border border-gray-300 rounded-lg mb-2" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  
                  <label className="block text-sm font-medium text-gray-700">Source (Koperta źródłowa):</label>
                  <select 
                    className="w-full p-2 border border-gray-300 rounded-lg mb-2"
                    value={sourceEnvelopeId || ''}
                    onChange={e => setSourceEnvelopeId(e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">-- Wolne Środki (Free Pool) --</option>
                    {summary?.envelopes.map(e => (
                       <option key={e.id} value={e.id}>{e.icon} {e.name} ({e.balance.toFixed(2)})</option>
                    ))}
                  </select>
                  
                  {sourceEnvelopeId ? (
                      <p className="text-xs text-gray-500 mb-2">
                          Available in Envelope: <b>{summary?.envelopes.find(e => e.id === sourceEnvelopeId)?.balance.toFixed(2)} PLN</b>
                      </p>
                  ) : (
                      <p className="text-xs text-gray-500 mb-2">
                          Available in Free Pool: <b>{summary?.free_pool.toFixed(2)} PLN</b>
                      </p>
                  )}

                  <label className="block text-sm font-medium text-gray-700">To Account:</label>
                  <select 
                    className="w-full p-2 border border-gray-300 rounded-lg"
                    value={targetAccountId || ''}
                    onChange={e => setTargetAccountId(Number(e.target.value))}
                  >
                    <option value="">Select Destination Account</option>
                    {summary?.accounts
                        .filter(a => a.id !== selectedAccountId)
                        .map(a => <option key={a.id} value={a.id}>{a.name}</option>)
                    }
                  </select>

                  {targetAccountId && (
                      <>
                        <label className="block text-sm font-medium text-gray-700 mt-2">Cel (Koperta docelowa) - Opcjonalnie:</label>
                        <select 
                            className="w-full p-2 border border-gray-300 rounded-lg"
                            value={targetEnvelopeId || ''}
                            onChange={e => setTargetEnvelopeId(e.target.value ? Number(e.target.value) : null)}
                        >
                            <option value="">-- Przelew na Wolne Środki (Free Pool) --</option>
                            {targetAccountEnvelopes.map(e => (
                                <option key={e.id} value={e.id}>{e.icon} {e.name} ({e.balance.toFixed(2)})</option>
                            ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-1">Jeśli wybierzesz kopertę, środki trafią bezpośrednio do niej, a nie do puli wolnych środków.</p>
                      </>
                  )}
                  <input type="number" placeholder="Amount" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description (Optional)" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Investment Transfer Fields */}
              {showInvestmentModal && (
                <>
                   <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 text-purple-800 text-sm mb-2">
                    <b>Sending to Investments</b><br/>
                    From Budget Account: {currentAccount?.name}
                  </div>
                  
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border border-gray-300 rounded-lg mb-2" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />

                  <label className="block text-sm font-medium text-gray-700">From Source (Envelope/Free Pool):</label>
                  <select 
                    className="w-full p-2 border border-gray-300 rounded-lg mb-2"
                    value={selectedEnvelopeId || ''}
                    onChange={e => setSelectedEnvelopeId(e.target.value ? Number(e.target.value) : null)}
                  >
                    <option value="">🟢 Wolne Środki (Free Pool)</option>
                    {summary?.envelopes.map(e => (
                       <option key={e.id} value={e.id}>✉️ {e.name} ({e.balance.toFixed(2)} PLN)</option>
                    ))}
                  </select>

                  <label className="block text-sm font-medium text-gray-700">To Investment Portfolio:</label>
                  <select 
                    className="w-full p-2 border border-gray-300 rounded-lg mb-2"
                    value={targetPortfolioId || ''}
                    onChange={e => setTargetPortfolioId(Number(e.target.value))}
                  >
                    <option value="">Select Portfolio</option>
                    {portfolios.map(p => <option key={p.id} value={p.id}>📈 {p.name}</option>)}
                  </select>

                  <input type="number" placeholder="Amount" className="w-full p-2 border border-gray-300 rounded-lg" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description (Optional)" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Borrow Fields */}
              {showBorrowModal && (
                <>
                  <div className="p-3 bg-red-50 rounded-lg border border-red-200 text-red-800 text-sm">
                    Borrowing from envelope does not reduce account balance. It increases Free Pool for reallocation.
                  </div>
                  <input type="number" placeholder="Amount" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Reason" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Category Fields */}
              {showCategoryModal && (
                <input type="text" placeholder="Category Name" className="w-full p-2 border border-gray-300 rounded-lg" value={newCategoryName} onChange={e => setNewCategoryName(e.target.value)} />
              )}

              {/* Envelope Fields */}
              {showEnvelopeModal && (
                <>
                  <div className="p-3 bg-gray-50 rounded-lg border text-gray-600">
                    Creating in: <span className="font-bold">{currentAccount?.name}</span>
                  </div>
                  
                  {/* Type Selection */}
                  <div className="flex gap-4 mt-4">
                      <label className="flex items-center gap-2 cursor-pointer">
                          <input 
                              type="radio" 
                              name="envType" 
                              value="MONTHLY" 
                              checked={newEnvelopeType === 'MONTHLY'} 
                              onChange={() => setNewEnvelopeType('MONTHLY')}
                              className="w-4 h-4 text-blue-600"
                          />
                          <span className="text-sm font-medium text-gray-700">Miesięczna</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                          <input 
                              type="radio" 
                              name="envType" 
                              value="LONG_TERM" 
                              checked={newEnvelopeType === 'LONG_TERM'} 
                              onChange={() => setNewEnvelopeType('LONG_TERM')}
                              className="w-4 h-4 text-purple-600"
                          />
                          <span className="text-sm font-medium text-gray-700">Długoterminowa (Cel)</span>
                      </label>
                  </div>
                  <p className="text-xs text-gray-500 mt-1 mb-2">
                      {newEnvelopeType === 'MONTHLY' 
                          ? 'Zniknie/rozliczy się na koniec miesiąca (np. Jedzenie, Paliwo).' 
                          : 'Będzie trwać dopóki jej nie zamkniesz (np. Wakacje, Ubezpieczenie).'}
                  </p>

                  <select 
                    className="w-full p-2 border border-gray-300 rounded-lg mt-2"
                    value={selectedCategoryId || ''}
                    onChange={e => setSelectedCategoryId(Number(e.target.value))}
                  >
                    <option value="">Select Category</option>
                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <input type="text" placeholder="Envelope Name" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={newEnvelopeName} onChange={e => setNewEnvelopeName(e.target.value)} />
                  <input type="number" placeholder="Target Amount (Optional)" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={targetAmount} onChange={e => setTargetAmount(e.target.value)} />
                </>
              )}

               {/* Account Fields */}
               {showAccountModal && (
                <>
                  <input type="text" placeholder="Account Name" className="w-full p-2 border border-gray-300 rounded-lg" value={newAccountName} onChange={e => setNewAccountName(e.target.value)} />
                  <input type="number" placeholder="Initial Balance" className="w-full p-2 border border-gray-300 rounded-lg mt-2" value={newAccountBalance} onChange={e => setNewAccountBalance(e.target.value)} />
                </>
              )}

              {/* Edit Plan Fields */}
              {showEditPlanModal && (
                <>
                  <label className="block text-sm font-medium text-gray-700 mt-2">New Target Amount (Plan):</label>
                  <input 
                    type="number" 
                    placeholder="Enter amount" 
                    className="w-full p-2 border border-gray-300 rounded-lg mt-2" 
                    value={editPlanAmount} 
                    onChange={e => setEditPlanAmount(e.target.value)}
                    min="0"
                  />
                  <p className="text-xs text-gray-500 mt-1">This will update the monthly budget goal for this envelope.</p>
                </>
              )}

              <div className="flex justify-end gap-2 mt-6">
                <button 
                  onClick={() => {
                    setShowIncomeModal(false); setShowAllocateModal(false); setShowExpenseModal(false);
                    setShowQuickExpenseModal(false); setShowTransferModal(false); setShowInvestmentModal(false);
                    setShowBorrowModal(false); setShowCategoryModal(false); setShowEnvelopeModal(false);
                    setShowAccountModal(false); setShowEditPlanModal(false);
                    resetForms();
                  }}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition"
                >
                  Cancel
                </button>
                <button 
                  onClick={() => {
                    if (showIncomeModal) handleAddIncome();
                    if (showAllocateModal) handleAllocate();
                    if (showExpenseModal) handleExpense();
                    if (showQuickExpenseModal) handleExpense();
                    if (showTransferModal) handleTransfer();
                    if (showInvestmentModal) handleInvestmentTransfer();
                    if (showBorrowModal) handleBorrow();
                    if (showCategoryModal) handleCreateCategory();
                    if (showEnvelopeModal) handleCreateEnvelope();
                    if (showAccountModal) handleCreateAccount();
                    if (showEditPlanModal) handleUpdatePlan();
                  }}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium shadow-md"
                >
                  Confirm
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}