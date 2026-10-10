import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import MainDashboard from './pages/MainDashboard';

const PortfolioDashboard = lazy(() => import('./pages/PortfolioDashboard'));
const PortfolioDetails = lazy(() => import('./pages/PortfolioDetails'));
const Transactions = lazy(() => import('./pages/Transactions'));
const LoansDashboard = lazy(() => import('./components/loans/LoansWorkspaceDashboard'));
const LoanSimulator = lazy(() => import('./components/loans/LoanWorkspaceDetail'));
const BudgetDashboard = lazy(() => import('./components/budget/BudgetWorkspaceDashboard'));
const BudgetReserves = lazy(() => import('./pages/BudgetReserves'));
const BudgetAccounts = lazy(() => import('./pages/BudgetAccounts'));
const CashForecast = lazy(() => import('./pages/CashForecast'));
const BudgetImports = lazy(() => import('./pages/BudgetImports'));
const InvestmentRadar = lazy(() => import('./pages/InvestmentRadar'));
const InvestmentIdeas = lazy(() => import('./pages/InvestmentIdeas'));
const InvestmentGoals = lazy(() => import('./pages/InvestmentGoals'));
const InvestorJournal = lazy(() => import('./pages/InvestorJournal'));
const MonthlyReport = lazy(() => import('./pages/MonthlyReport'));
const SymbolMappingPanel = lazy(() => import('./pages/SymbolMappingPanel'));
const AdminHome = lazy(() => import('./pages/admin/AdminHome'));
const AdminBackups = lazy(() => import('./pages/admin/AdminBackups'));
const AdminPortfolios = lazy(() => import('./pages/admin/AdminPortfolios'));
const AdminPortfolioTools = lazy(() => import('./pages/admin/AdminPortfolioTools'));
const AdminConsistencyAudit = lazy(() => import('./pages/admin/AdminConsistencyAudit'));
const AdminBudget = lazy(() => import('./pages/admin/AdminBudget'));
const AdminPriceHistoryAudit = lazy(() => import('./pages/admin/AdminPriceHistoryAudit'));

function App() {
  return (
    <Router>
      <Layout>
        <Suspense fallback={<div className="p-4 text-sm text-gray-500">Ładowanie widoku...</div>}>
          <Routes>
            <Route path="/" element={<MainDashboard />} />
            <Route path="/admin/backups" element={<AdminBackups />} />
            <Route path="/portfolios" element={<PortfolioDashboard />} />
            <Route path="/portfolio/:id" element={<PortfolioDetails />} />
            <Route path="/radar" element={<InvestmentRadar />} />
            <Route path="/ideas" element={<InvestmentIdeas />} />
            <Route path="/goals" element={<InvestmentGoals />} />
            <Route path="/journal" element={<InvestorJournal />} />
            <Route path="/reports/monthly" element={<MonthlyReport />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/loans" element={<LoansDashboard />} />
            <Route path="/loans/:id" element={<LoanSimulator />} />
            <Route path="/budget" element={<BudgetDashboard />} />
            <Route path="/budget/reserves" element={<BudgetReserves />} />
            <Route path="/budget/accounts" element={<BudgetAccounts />} />
            <Route path="/budget/forecast" element={<CashForecast />} />
            <Route path="/budget/imports" element={<BudgetImports />} />
            <Route path="/admin" element={<AdminHome />} />
            <Route path="/admin/transactions" element={<Navigate to="/transactions" replace />} />
            <Route path="/admin/portfolios" element={<AdminPortfolios />} />
            <Route path="/admin/portfolio/:id" element={<AdminPortfolioTools />} />
            <Route path="/admin/symbol-mapping" element={<SymbolMappingPanel />} />
            <Route path="/admin/consistency-audit" element={<AdminConsistencyAudit />} />
            <Route path="/admin/price-history-audit" element={<AdminPriceHistoryAudit />} />
            <Route path="/admin/budget" element={<AdminBudget />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </Layout>
    </Router>
  );
}

export default App;
