import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import MainDashboard from './pages/MainDashboard';
import PortfolioDashboard from './pages/PortfolioDashboard';
import PortfolioDetails from './pages/PortfolioDetails';
import Transactions from './pages/Transactions';
import LoansDashboard from './components/loans/LoansDashboard';
import LoanSimulator from './components/loans/LoanSimulator';
import BudgetDashboard from './components/budget/BudgetDashboard';
import InvestmentRadar from './pages/InvestmentRadar';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<MainDashboard />} />
          <Route path="/portfolios" element={<PortfolioDashboard />} />
          <Route path="/portfolio/:id" element={<PortfolioDetails />} />
          <Route path="/radar" element={<InvestmentRadar />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/loans" element={<LoansDashboard />} />
          <Route path="/loans/:id" element={<LoanSimulator />} />
          <Route path="/budget" element={<BudgetDashboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
