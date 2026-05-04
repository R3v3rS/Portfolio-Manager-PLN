import React from 'react';
import { Link } from 'react-router-dom';
import { Wrench, SlidersHorizontal, ListTree, PiggyBank, ShieldAlert, History, Building2 } from 'lucide-react';

const AdminHome: React.FC = () => {
  const tiles = [
    {
      title: 'Portfele',
      description: 'Lista portfeli + narzędzia (import, audit, rebuild, clear).',
      to: '/admin/portfolios',
      icon: ListTree,
    },
    {
      title: 'Transakcje',
      description: 'Globalna historia transakcji z filtrami.',
      to: '/admin/transactions',
      icon: History,
    },
    {
      title: 'Symbol Mapping',
      description: 'Mapowanie symbol_input → ticker/currency.',
      to: '/admin/symbol-mapping',
      icon: SlidersHorizontal,
    },
    {
      title: 'Audyt spójności',
      description: 'Sprawdzenie spójności parent/child.',
      to: '/admin/consistency-audit',
      icon: ShieldAlert,
    },
    {
      title: 'Audyt cen',
      description: 'Globalny audit jakości historii cen.',
      to: '/admin/price-history-audit',
      icon: Wrench,
    },
    {
      title: 'Budżet (Danger zone)',
      description: 'Operacje serwisowe budżetu.',
      to: '/admin/budget',
      icon: PiggyBank,
    },
    {
      title: 'Instrument Profiles',
      description: 'Klasyfikacja sektor/kraj i alokacje ETF.',
      to: '/admin/instrument-profiles',
      icon: Building2,
    },
  ];

  return (
    <div className="space-y-5 px-4 sm:px-0">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Admin</h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">Narzędzia utrzymaniowe i konfiguracje.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((tile) => {
          const Icon = tile.icon;
          return (
            <Link
              key={tile.to}
              to={tile.to}
              className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition-colors hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:hover:bg-gray-800"
            >
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-blue-50 p-2 text-blue-700 dark:bg-blue-950 dark:text-blue-200">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <div className="font-medium text-gray-900 dark:text-gray-100">{tile.title}</div>
                  <div className="mt-1 text-sm text-gray-600 dark:text-gray-300">{tile.description}</div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
};

export default AdminHome;
