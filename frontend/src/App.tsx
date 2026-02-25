import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import PortfolioList from './pages/PortfolioList';
import PortfolioDetails from './pages/PortfolioDetails';
import Transactions from './pages/Transactions';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/portfolios" element={<PortfolioList />} />
          <Route path="/portfolio/:id" element={<PortfolioDetails />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
