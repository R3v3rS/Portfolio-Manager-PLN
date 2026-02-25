import React, { useEffect, useState } from 'react';
import { ArrowUpRight, ArrowDownRight, Wallet, TrendingUp, DollarSign, PieChart } from 'lucide-react';
import api from '../api';
import { Portfolio } from '../types';
import { cn } from '../lib/utils';

const Dashboard: React.FC = () => {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.get('/list');
        setPortfolios(response.data.portfolios);
      } catch (err) {
        setError('Failed to fetch dashboard data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div className="p-4 text-center">Loading dashboard...</div>;
  if (error) return <div className="p-4 text-center text-red-600">{error}</div>;

  const totalValue = portfolios.reduce((sum, p) => sum + (p.portfolio_value || 0), 0);
  const totalDeposits = portfolios.reduce((sum, p) => sum + (p.total_deposits || 0), 0);
  const totalDividends = portfolios.reduce((sum, p) => sum + (p.total_dividends || 0), 0);
  const totalResult = totalValue - totalDeposits;
  const totalResultPercent = totalDeposits > 0 ? (totalResult / totalDeposits) * 100 : 0;

  const cards = [
    {
      name: 'Total Portfolio Value',
      value: `${totalValue.toFixed(2)} PLN`,
      icon: Wallet,
      color: 'bg-blue-500',
    },
    {
      name: 'Total Deposits',
      value: `${totalDeposits.toFixed(2)} PLN`,
      icon: DollarSign,
      color: 'bg-gray-500',
    },
    {
      name: 'Total Dividends',
      value: `${totalDividends.toFixed(2)} PLN`,
      icon: PieChart,
      color: 'bg-indigo-500',
    },
    {
      name: 'Total Profit/Loss',
      value: `${totalResult.toFixed(2)} PLN`,
      subValue: `${totalResultPercent.toFixed(2)}%`,
      icon: totalResult >= 0 ? TrendingUp : ArrowDownRight,
      color: totalResult >= 0 ? 'bg-green-500' : 'bg-red-500',
      textColor: totalResult >= 0 ? 'text-green-600' : 'text-red-600',
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.name} className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className={cn("flex-shrink-0 rounded-md p-3", card.color)}>
                    <Icon className="h-6 w-6 text-white" aria-hidden="true" />
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">{card.name}</dt>
                      <dd className="text-lg font-medium text-gray-900">{card.value}</dd>
                      {card.subValue && (
                        <dd className={cn("text-sm font-semibold", card.textColor)}>
                          {card.subValue}
                        </dd>
                      )}
                    </dl>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Your Portfolios</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Dividends</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Result</th>
                <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Return %</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {portfolios.map((portfolio) => (
                <tr key={portfolio.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{portfolio.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                    {portfolio.portfolio_value?.toFixed(2)} PLN
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-blue-600 font-medium">
                    {portfolio.total_dividends?.toFixed(2)} PLN
                  </td>
                  <td className={cn("px-6 py-4 whitespace-nowrap text-sm text-right font-medium", 
                    (portfolio.total_result || 0) >= 0 ? "text-green-600" : "text-red-600")}>
                    {portfolio.total_result?.toFixed(2)} PLN
                  </td>
                  <td className={cn("px-6 py-4 whitespace-nowrap text-sm text-right font-medium", 
                    (portfolio.total_result_percent || 0) >= 0 ? "text-green-600" : "text-red-600")}>
                    {portfolio.total_result_percent?.toFixed(2)}%
                  </td>
                </tr>
              ))}
              {portfolios.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">
                    No portfolios found. Create one to get started!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
