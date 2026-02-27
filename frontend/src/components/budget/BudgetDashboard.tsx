import React, { useEffect, useState } from 'react';
import { budgetApi, BudgetSummary, Envelope, EnvelopeLoan } from '../../api_budget';
import { Banknote, Plus, FolderPlus, Wallet, Send, MinusCircle, ArrowRightLeft, TrendingUp, PieChart } from 'lucide-react';
import TransactionHistory from './TransactionHistory';
import BudgetAnalytics from './BudgetAnalytics';

export default function BudgetDashboard() {
  const [summary, setSummary] = useState<BudgetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'envelopes' | 'analytics'>('envelopes');

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

  // Form Data
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedEnvelopeId, setSelectedEnvelopeId] = useState<number | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [targetAccountId, setTargetAccountId] = useState<number | null>(null);
  const [targetPortfolioId, setTargetPortfolioId] = useState<number | null>(null);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newEnvelopeName, setNewEnvelopeName] = useState('');
  const [targetAmount, setTargetAmount] = useState('');
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [newAccountName, setNewAccountName] = useState('');
  const [newAccountBalance, setNewAccountBalance] = useState('');

  const [categories, setCategories] = useState<any[]>([]);
  const [portfolios, setPortfolios] = useState<any[]>([]);

  useEffect(() => {
    fetchData();
    if (categories.length === 0) fetchCategories();
    if (portfolios.length === 0) fetchPortfolios();
  }, [selectedAccountId]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const data = await budgetApi.getSummary(selectedAccountId || undefined);
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
      await budgetApi.transferBetweenAccounts(selectedAccountId, targetAccountId, parseFloat(amount), description, transactionDate);
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
      await budgetApi.createEnvelope(selectedCategoryId, selectedAccountId, newEnvelopeName, '✉️', targetAmount ? parseFloat(targetAmount) : undefined);
      setShowEnvelopeModal(false);
      setNewEnvelopeName('');
      setTargetAmount('');
      fetchData();
    } catch (err: any) {
      alert(err.message);
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

  const handleRepay = async (loanId: number, amount: number) => {
    try {
      await budgetApi.repay(loanId, amount);
      fetchData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const resetForms = () => {
    setAmount('');
    setDescription('');
    setTransactionDate(new Date().toISOString().split('T')[0]);
    setSelectedEnvelopeId(null);
    setTargetAccountId(null);
    setTargetPortfolioId(null);
    // Don't reset selectedAccountId
  };

  if (loading && !summary) return <div className="p-8 text-center">Loading budget...</div>;
  if (error) return <div className="p-8 text-red-500">Error: {error}</div>;

  const envelopesByCategory = summary?.envelopes.reduce((acc, env) => {
    const catName = env.category_name || 'Uncategorized';
    if (!acc[catName]) acc[catName] = [];
    acc[catName].push(env);
    return acc;
  }, {} as Record<string, Envelope[]>) || {};

  const currentAccount = summary?.accounts.find(a => a.id === selectedAccountId);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
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
          
          {selectedAccountId && (
            <div className="flex gap-2">
             <button 
                onClick={() => setShowTransferModal(true)}
                className="px-4 py-2 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg flex items-center gap-2 text-sm font-medium transition"
             >
               <ArrowRightLeft className="w-4 h-4" /> Przelew Własny
             </button>
             <button 
                onClick={() => setShowInvestmentModal(true)}
                className="px-4 py-2 bg-purple-50 text-purple-700 hover:bg-purple-100 rounded-lg flex items-center gap-2 text-sm font-medium transition border border-purple-200"
             >
               <TrendingUp className="w-4 h-4" /> Wyślij na Inwestycje
             </button>
            </div>
          )}
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
          {/* Header Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <p className="text-sm text-gray-500 mb-1">Total Account Balance</p>
              <p className="text-3xl font-bold text-gray-900">{summary?.account_balance.toFixed(2)} PLN</p>
            </div>
            <div className="bg-green-50 p-6 rounded-xl shadow-sm border border-green-100 relative">
              <p className="text-sm text-green-600 mb-1">Free Pool (To Allocate)</p>
              <p className="text-3xl font-bold text-green-700">{summary?.free_pool.toFixed(2)} PLN</p>
              <div className="flex gap-2 mt-4">
                  <button 
                    onClick={() => setShowIncomeModal(true)}
                    className="flex-1 bg-green-600 text-white py-2 rounded-lg hover:bg-green-700 transition flex items-center justify-center gap-2 text-sm"
                  >
                    <Plus className="w-4 h-4" /> Income
                  </button>
                  <button 
                    onClick={() => setShowQuickExpenseModal(true)}
                    className="flex-1 bg-red-100 text-red-700 py-2 rounded-lg hover:bg-red-200 transition flex items-center justify-center gap-2 text-sm"
                    title="Quick Expense from Free Pool"
                  >
                    <MinusCircle className="w-4 h-4" /> Expense
                  </button>
              </div>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <p className="text-sm text-gray-500 mb-1">Total Allocated</p>
              <p className="text-3xl font-bold text-gray-900">{summary?.total_allocated.toFixed(2)} PLN</p>
            </div>
            <div className="bg-red-50 p-6 rounded-xl shadow-sm border border-red-100">
              <p className="text-sm text-red-600 mb-1">Internal Debt (Borrowed)</p>
              <p className="text-3xl font-bold text-red-700">{summary?.total_borrowed.toFixed(2)} PLN</p>
            </div>
          </div>

          {/* View Toggle & Actions */}
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 border-b border-gray-200 pb-4">
            <div className="flex bg-gray-100 p-1 rounded-lg">
                <button 
                    onClick={() => setActiveTab('envelopes')}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'envelopes' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                >
                    <div className="flex items-center gap-2">
                        <Banknote className="w-4 h-4" /> Koperty
                    </div>
                </button>
                <button 
                    onClick={() => setActiveTab('analytics')}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'analytics' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                >
                    <div className="flex items-center gap-2">
                        <PieChart className="w-4 h-4" /> Analiza
                    </div>
                </button>
            </div>

            {activeTab === 'envelopes' && (
                <div className="flex gap-2">
                    <button onClick={() => setShowCategoryModal(true)} className="px-3 py-2 bg-gray-50 hover:bg-gray-100 rounded-lg text-gray-600 text-sm flex items-center gap-2 border border-gray-200">
                    <FolderPlus className="w-4 h-4" /> New Category
                    </button>
                    <button onClick={() => setShowEnvelopeModal(true)} className="px-3 py-2 bg-gray-50 hover:bg-gray-100 rounded-lg text-gray-600 text-sm flex items-center gap-2 border border-gray-200">
                    <Banknote className="w-4 h-4" /> New Envelope
                    </button>
                </div>
            )}
          </div>

          {activeTab === 'analytics' ? (
              <BudgetAnalytics selectedAccountId={selectedAccountId} />
          ) : (
            <>
          {/* Envelopes Grid */}
          <div className="space-y-8">
            {Object.entries(envelopesByCategory).map(([category, envelopes]) => (
              <div key={category} className="space-y-4">
                <h3 className="text-xl font-semibold text-gray-800 flex items-center gap-2">
                  {category}
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {envelopes.map(env => (
                    <div key={env.id} className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition">
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <h4 className="font-bold text-lg text-gray-900">{env.icon} {env.name}</h4>
                          {env.target_amount && (
                            <p className="text-xs text-gray-500">Target: {env.target_amount} PLN</p>
                          )}
                        </div>
                        <span className={`px-3 py-1 rounded-full text-sm font-medium ${env.balance >= 0 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          {env.balance.toFixed(2)} PLN
                        </span>
                      </div>
                      
                      {/* Progress Bar if target exists */}
                      {env.target_amount && (
                        <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4">
                          <div 
                            className="bg-blue-600 h-2.5 rounded-full" 
                            style={{ width: `${Math.min((env.balance / env.target_amount) * 100, 100)}%` }}
                          ></div>
                        </div>
                      )}

                      <div className="flex gap-2 mt-4">
                        <button 
                          onClick={() => { setSelectedEnvelopeId(env.id); setShowAllocateModal(true); }}
                          className="flex-1 bg-blue-50 text-blue-700 py-2 rounded-lg text-sm hover:bg-blue-100"
                        >
                          Allocate
                        </button>
                        <button 
                          onClick={() => { setSelectedEnvelopeId(env.id); setShowExpenseModal(true); }}
                          className="flex-1 bg-red-50 text-red-700 py-2 rounded-lg text-sm hover:bg-red-100"
                        >
                          Spend
                        </button>
                        <button 
                          onClick={() => { setSelectedEnvelopeId(env.id); setShowBorrowModal(true); }}
                          className="flex-1 bg-orange-50 text-orange-700 py-2 rounded-lg text-sm hover:bg-orange-100"
                        >
                          Borrow
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Internal Loans Section */}
          {summary?.loans && summary.loans.length > 0 && (
            <div className="bg-white p-6 rounded-xl shadow-sm border border-orange-200 mt-8">
              <h3 className="text-lg font-bold text-orange-800 mb-4 flex items-center gap-2">
                ⚠️ Open Internal Loans (Borrowed from Envelopes)
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
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{loan.source_envelope}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{loan.reason}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-red-600">{loan.remaining.toFixed(2)} PLN</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          <button 
                            onClick={() => handleRepay(loan.id, loan.remaining)}
                            className="text-green-600 hover:text-green-900 font-medium"
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

          {/* Transaction History Section */}
          <TransactionHistory 
            selectedAccountId={selectedAccountId}
            categories={categories}
            envelopes={summary?.envelopes || []}
          />
          </>
          )}
        </>
      )}

      {/* Modals */}
      {(showIncomeModal || showAllocateModal || showExpenseModal || showQuickExpenseModal || showBorrowModal || showCategoryModal || showEnvelopeModal || showAccountModal || showTransferModal || showInvestmentModal) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full shadow-2xl">
            <h2 className="text-xl font-bold mb-4">
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
            </h2>

            <div className="space-y-4">
              {/* Income Fields */}
              {showIncomeModal && (
                <>
                  <div className="p-2 bg-gray-50 rounded border text-gray-600">
                    Adding to: <span className="font-bold">{currentAccount?.name}</span>
                  </div>
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border rounded" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  <input type="number" placeholder="Amount" className="w-full p-2 border rounded mt-2" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description" className="w-full p-2 border rounded" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Allocate Fields */}
              {showAllocateModal && (
                <>
                  <p className="text-sm text-gray-500">From Free Pool: {summary?.free_pool.toFixed(2)} PLN</p>
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border rounded" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  <input type="number" placeholder="Amount" className="w-full p-2 border rounded mt-2" value={amount} onChange={e => setAmount(e.target.value)} />
                </>
              )}

              {/* Expense Fields */}
              {showExpenseModal && (
                <>
                  <div className="p-2 bg-gray-50 rounded border text-gray-600">
                    Paying from: <span className="font-bold">{currentAccount?.name}</span>
                  </div>
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border rounded" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  <input type="number" placeholder="Amount" className="w-full p-2 border rounded mt-2" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description" className="w-full p-2 border rounded" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Quick Expense Fields */}
              {showQuickExpenseModal && (
                <>
                   <div className="p-2 bg-orange-50 rounded border border-orange-200 text-orange-800 text-sm">
                    This will be deducted directly from <b>Free Pool</b> (unallocated funds).
                  </div>
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border rounded" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  <input type="number" placeholder="Amount" className="w-full p-2 border rounded mt-2" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description" className="w-full p-2 border rounded" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Transfer Fields */}
              {showTransferModal && (
                <>
                   <div className="p-2 bg-blue-50 rounded border border-blue-200 text-blue-800 text-sm mb-2">
                    Transferring from: <b>{currentAccount?.name}</b> (Free Pool: {summary?.free_pool.toFixed(2)} PLN)
                  </div>
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border rounded mb-2" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />
                  
                  <label className="block text-sm font-medium text-gray-700">To Account:</label>
                  <select 
                    className="w-full p-2 border rounded"
                    value={targetAccountId || ''}
                    onChange={e => setTargetAccountId(Number(e.target.value))}
                  >
                    <option value="">Select Destination Account</option>
                    {summary?.accounts
                        .filter(a => a.id !== selectedAccountId)
                        .map(a => <option key={a.id} value={a.id}>{a.name}</option>)
                    }
                  </select>
                  <input type="number" placeholder="Amount" className="w-full p-2 border rounded" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description (Optional)" className="w-full p-2 border rounded" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Investment Transfer Fields */}
              {showInvestmentModal && (
                <>
                   <div className="p-2 bg-purple-50 rounded border border-purple-200 text-purple-800 text-sm mb-2">
                    <b>Sending to Investments</b><br/>
                    From Budget Account: {currentAccount?.name}
                  </div>
                  
                  <label className="block text-sm font-medium text-gray-700 mt-2">Date:</label>
                  <input type="date" className="w-full p-2 border rounded mb-2" value={transactionDate} onChange={e => setTransactionDate(e.target.value)} />

                  <label className="block text-sm font-medium text-gray-700">From Source (Envelope/Free Pool):</label>
                  <select 
                    className="w-full p-2 border rounded mb-2"
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
                    className="w-full p-2 border rounded mb-2"
                    value={targetPortfolioId || ''}
                    onChange={e => setTargetPortfolioId(Number(e.target.value))}
                  >
                    <option value="">Select Portfolio</option>
                    {portfolios.map(p => <option key={p.id} value={p.id}>📈 {p.name}</option>)}
                  </select>

                  <input type="number" placeholder="Amount" className="w-full p-2 border rounded" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Description (Optional)" className="w-full p-2 border rounded" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Borrow Fields */}
              {showBorrowModal && (
                <>
                  <p className="text-sm text-gray-500">Borrowing from envelope does not reduce account balance. It increases Free Pool.</p>
                  <input type="number" placeholder="Amount" className="w-full p-2 border rounded" value={amount} onChange={e => setAmount(e.target.value)} />
                  <input type="text" placeholder="Reason" className="w-full p-2 border rounded" value={description} onChange={e => setDescription(e.target.value)} />
                </>
              )}

              {/* Category Fields */}
              {showCategoryModal && (
                <input type="text" placeholder="Category Name" className="w-full p-2 border rounded" value={newCategoryName} onChange={e => setNewCategoryName(e.target.value)} />
              )}

              {/* Envelope Fields */}
              {showEnvelopeModal && (
                <>
                  <div className="p-2 bg-gray-50 rounded border text-gray-600">
                    Creating in: <span className="font-bold">{currentAccount?.name}</span>
                  </div>
                  <select 
                    className="w-full p-2 border rounded"
                    value={selectedCategoryId || ''}
                    onChange={e => setSelectedCategoryId(Number(e.target.value))}
                  >
                    <option value="">Select Category</option>
                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <input type="text" placeholder="Envelope Name" className="w-full p-2 border rounded" value={newEnvelopeName} onChange={e => setNewEnvelopeName(e.target.value)} />
                  <input type="number" placeholder="Target Amount (Optional)" className="w-full p-2 border rounded" value={targetAmount} onChange={e => setTargetAmount(e.target.value)} />
                </>
              )}

               {/* Account Fields */}
               {showAccountModal && (
                <>
                  <input type="text" placeholder="Account Name" className="w-full p-2 border rounded" value={newAccountName} onChange={e => setNewAccountName(e.target.value)} />
                  <input type="number" placeholder="Initial Balance" className="w-full p-2 border rounded" value={newAccountBalance} onChange={e => setNewAccountBalance(e.target.value)} />
                </>
              )}

              <div className="flex justify-end gap-2 mt-4">
                <button 
                  onClick={() => {
                    setShowIncomeModal(false); setShowAllocateModal(false); setShowExpenseModal(false);
                    setShowQuickExpenseModal(false); setShowTransferModal(false); setShowInvestmentModal(false);
                    setShowBorrowModal(false); setShowCategoryModal(false); setShowEnvelopeModal(false);
                    setShowAccountModal(false);
                  }}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded"
                >
                  Cancel
                </button>
                <button 
                  onClick={() => {
                    if (showIncomeModal) handleAddIncome();
                    if (showAllocateModal) handleAllocate();
                    if (showExpenseModal) handleExpense();
                    if (showQuickExpenseModal) handleExpense(); // Re-use handleExpense for quick expense
                    if (showTransferModal) handleTransfer();
                    if (showInvestmentModal) handleInvestmentTransfer();
                    if (showBorrowModal) handleBorrow();
                    if (showCategoryModal) handleCreateCategory();
                    if (showEnvelopeModal) handleCreateEnvelope();
                    if (showAccountModal) handleCreateAccount();
                  }}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
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
