import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import MainDashboard from './pages/MainDashboard';

const PortfolioDashboard = lazy(() => import('./pages/PortfolioDashboard'));
const PortfolioDetails = lazy(() => import('./pages/PortfolioDetails'));
const Transactions = lazy(() => import('./pages/Transactions'));
const LoansDashboard = lazy(() => import('./components/loans/LoansDashboard'));
const LoanSimulator = lazy(() => import('./components/loans/LoanSimulator'));
const BudgetDashboard = lazy(() => import('./components/budget/BudgetDashboard'));
const InvestmentRadar = lazy(() => import('./pages/InvestmentRadar'));
const SymbolMappingPanel = lazy(() => import('./pages/SymbolMappingPanel'));
const AdminHome = lazy(() => import('./pages/admin/AdminHome'));
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
            <Route path="/portfolios" element={<PortfolioDashboard />} />
            <Route path="/portfolio/:id" element={<PortfolioDetails />} />
            <Route path="/radar" element={<InvestmentRadar />} />
            <Route path="/transactions" element={<Navigate to="/admin/transactions" replace />} />
            <Route path="/loans" element={<LoansDashboard />} />
            <Route path="/loans/:id" element={<LoanSimulator />} />
            <Route path="/budget" element={<BudgetDashboard />} />
            <Route path="/admin" element={<AdminHome />} />
            <Route path="/admin/transactions" element={<Transactions />} />
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
