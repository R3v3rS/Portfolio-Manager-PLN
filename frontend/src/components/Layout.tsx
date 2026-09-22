import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Wallet, PieChart, Landmark, PiggyBank, Radar, Moon, Sun, Settings, Menu, X, ChevronRight } from 'lucide-react';
import { cn } from '../lib/utils';
import { useTheme } from '../hooks/useTheme';

const navItems = [
  { name: 'Pulpit', path: '/', icon: LayoutDashboard, description: 'Przegląd finansów' },
  { name: 'Inwestycje', path: '/portfolios', icon: Wallet, description: 'Portfele i aktywa' },
  { name: 'Radar', path: '/radar', icon: Radar, description: 'Obserwowane inwestycje' },
  { name: 'Kredyty', path: '/loans', icon: Landmark, description: 'Zobowiązania i raty' },
  { name: 'Budżet', path: '/budget', icon: PiggyBank, description: 'Codzienne finanse' },
  { name: 'Admin', path: '/admin', icon: Settings, description: 'Narzędzia i ustawienia' },
];

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { pathname } = useLocation();
  const { isDark, toggleTheme } = useTheme();
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const isActive = (path: string) => path === '/' ? pathname === '/' :
    pathname.startsWith(path) || (path === '/portfolios' && pathname.startsWith('/portfolio/'));
  const activeItem = navItems.find(item => isActive(item.path)) ?? navItems[0];

  useEffect(() => { setIsMobileNavOpen(false); }, [pathname]);
  useEffect(() => {
    if (!isMobileNavOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMobileNavOpen(false);
        menuButton.current?.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isMobileNavOpen]);

  const navigation = (mobile = false) => (
    <nav aria-label={mobile ? 'Nawigacja mobilna' : 'Nawigacja główna'} className="space-y-1.5">
      {navItems.map(({ name, path, icon: Icon }) => (
        <Link key={path} to={path} aria-current={isActive(path) ? 'page' : undefined}
          className={cn('app-nav-link', isActive(path) && 'is-active')}>
          <Icon className="h-[18px] w-[18px] shrink-0" />
          <span className="flex-1">{name}</span>
          {isActive(path) && <ChevronRight className="h-4 w-4 opacity-60" />}
        </Link>
      ))}
    </nav>
  );

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">Przejdź do treści</a>
      <aside className="app-sidebar hidden xl:flex">
        <Link to="/" className="flex items-center gap-3 px-2 py-2" aria-label="Portfolio Manager — pulpit">
          <span className="brand-mark"><PieChart className="h-6 w-6" /></span>
          <span><span className="block text-base font-bold tracking-tight">Portfolio Manager</span>
            <span className="text-xs text-gray-500">Twoje finanse w jednym miejscu</span></span>
        </Link>
        <div className="mb-3 mt-12 px-4 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-500">Przestrzeń finansowa</div>
        {navigation()}
        <div className="mt-auto border-t border-gray-200 px-3 pt-5 text-xs leading-relaxed text-gray-500">
          <span className="mb-1 block font-semibold text-gray-700">Wszystko pod kontrolą</span>
          Majątek, inwestycje i codzienny budżet.
        </div>
      </aside>
      <div className="min-w-0 flex-1 xl:pl-64">
        <header className="app-topbar">
          <div className="flex min-w-0 items-center gap-3">
            <button ref={menuButton} type="button" onClick={() => setIsMobileNavOpen(open => !open)}
              className="app-icon-button xl:hidden" aria-label="Przełącz nawigację mobilną"
              aria-expanded={isMobileNavOpen} aria-controls="mobile-navigation">
              {isMobileNavOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-gray-900">{activeItem.name}</p>
              <p className="truncate text-xs text-gray-500">{activeItem.description}</p>
            </div>
          </div>
          <button type="button" onClick={toggleTheme} className="app-theme-button" aria-label="Przełącz motyw">
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            <span className="hidden sm:inline">{isDark ? 'Jasny' : 'Ciemny'}</span>
          </button>
        </header>
        {isMobileNavOpen && <div id="mobile-navigation" className="app-mobile-nav xl:hidden">{navigation(true)}</div>}
        <main id="main-content" tabIndex={-1} className="app-content">{children}</main>
      </div>
    </div>
  );
};

export default Layout;
