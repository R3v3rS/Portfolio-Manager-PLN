import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Wallet, PieChart, Landmark, PiggyBank, Radar, Moon, Sun, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '../lib/utils';
import { useTheme } from '../hooks/useTheme';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const { isDark, toggleTheme } = useTheme();
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  useEffect(() => {
    setIsMobileNavOpen(false);
  }, [location.pathname]);

  const navItems = [
    { name: 'Pulpit', path: '/', icon: LayoutDashboard, iconStyle: 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-200' },
    { name: 'Inwestycje', path: '/portfolios', icon: Wallet, iconStyle: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200' },
    { name: 'Radar', path: '/radar', icon: Radar, iconStyle: 'bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-200' },
    { name: 'Kredyty', path: '/loans', icon: Landmark, iconStyle: 'bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-200' },
    { name: 'Budżet', path: '/budget', icon: PiggyBank, iconStyle: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-200' },
    { name: 'Admin', path: '/admin', icon: Settings, iconStyle: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200' },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 flex flex-col transition-colors duration-200">
      <nav className="bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800 sticky top-0 z-50 transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <button
                type="button"
                onClick={() => setIsMobileNavOpen((prev) => !prev)}
                className="flex flex-shrink-0 items-center rounded-md px-2 py-1 text-left transition-colors hover:bg-gray-100 dark:hover:bg-gray-800 sm:pointer-events-none sm:px-0 sm:py-0 sm:hover:bg-transparent"
                aria-expanded={isMobileNavOpen}
                aria-label="Przełącz nawigację mobilną"
              >
                <PieChart className="h-8 w-8 text-blue-600" />
                <span className="ml-2 text-xl font-bold text-gray-900 dark:text-gray-100">Portfolio Manager</span>
                <span className="ml-2 sm:hidden">
                  {isMobileNavOpen ? <ChevronUp className="h-4 w-4 text-gray-500 dark:text-gray-300" /> : <ChevronDown className="h-4 w-4 text-gray-500 dark:text-gray-300" />}
                </span>
              </button>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
                  return (
                    <Link
                      key={item.name}
                      to={item.path}
                      className={cn(
                        isActive
                          ? 'bg-[var(--color-background-secondary)] text-gray-900 dark:text-gray-100'
                          : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100',
                        'inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors'
                      )}
                    >
                      <span className={cn('inline-flex h-7 w-7 items-center justify-center rounded-md', item.iconStyle, isActive && 'ring-1 ring-black/5 dark:ring-white/10')}>
                        <Icon className="h-4 w-4" />
                      </span>
                      <span>{item.name}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
            <div className="flex items-center">
              <button
                type="button"
                onClick={toggleTheme}
                className="inline-flex items-center gap-2 rounded-md border border-gray-300 dark:border-gray-700 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Przełącz motyw"
              >
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                <span>{isDark ? 'Jasny' : 'Ciemny'}</span>
              </button>
            </div>
          </div>

          {isMobileNavOpen && (
            <div className="border-t border-gray-200 py-3 dark:border-gray-800 sm:hidden">
              <div className="grid grid-cols-1 gap-2">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
                  return (
                    <Link
                      key={item.name}
                      to={item.path}
                      className={cn(
                        isActive
                          ? 'bg-[var(--color-background-secondary)] text-gray-900 dark:text-gray-100'
                          : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800',
                        'inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors'
                      )}
                    >
                      <span className={cn('inline-flex h-7 w-7 items-center justify-center rounded-md', item.iconStyle, isActive && 'ring-1 ring-black/5 dark:ring-white/10')}>
                        <Icon className="h-4 w-4" />
                      </span>
                      <span>{item.name}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </nav>

      <main className="flex-1 max-w-7xl w-full mx-auto py-6 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  );
};

export default Layout;
