import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BookOpen, ChevronRight, FileText, History, Landmark, LayoutDashboard, Lightbulb, Menu, PieChart, PiggyBank, Radar, Settings, Target, Wallet, X } from 'lucide-react';
import { portfolioApi } from '../api';
import { cn } from '../lib/utils';
import { flattenPortfolios } from '../utils/portfolioUtils';

const investmentLinks = [
  { name: 'Portfele', path: '/portfolios', icon: Wallet },
  { name: 'Cele inwestycyjne', path: '/goals', icon: Target },
  { name: 'Dziennik inwestora', path: '/journal', icon: BookOpen },
  { name: 'Radar', path: '/radar', icon: Radar },
  { name: 'Pomysły inwestycyjne', path: '/ideas', icon: Lightbulb },
  { name: 'Historia transakcji', path: '/transactions', icon: History },
];

const toolLinks = [
  { name: 'Portfele', path: '/admin/portfolios' },
  { name: 'Mapowanie symboli', path: '/admin/symbol-mapping' },
  { name: 'Audyt spójności', path: '/admin/consistency-audit' },
  { name: 'Audyt cen', path: '/admin/price-history-audit' },
  { name: 'Serwis budżetu', path: '/admin/budget' },
];

const toolNames: Record<string, string> = {
  '/admin/portfolios': 'Portfele',
  '/admin/symbol-mapping': 'Mapowanie symboli',
  '/admin/consistency-audit': 'Audyt spójności',
  '/admin/price-history-audit': 'Audyt cen',
  '/admin/budget': 'Serwis budżetu',
};

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { pathname } = useLocation();
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [portfolioName, setPortfolioName] = useState<{ id: string; name: string } | null>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLDivElement>(null);
  const drawerCloseButton = useRef<HTMLButtonElement>(null);
  const portfolioId = pathname.match(/^\/(?:admin\/)?portfolio\/(\d+)$/)?.[1];
  const isToolRoute = pathname === '/admin' || pathname.startsWith('/admin/');

  useEffect(() => { setIsMobileNavOpen(false); }, [pathname]);

  useEffect(() => {
    if (!portfolioId) return;
    let active = true;
    portfolioApi.list().then(({ portfolios }) => {
      const portfolio = flattenPortfolios(portfolios).find(item => String(item.id) === portfolioId);
      if (active && portfolio) setPortfolioName({ id: portfolioId, name: portfolio.name });
    }).catch(() => { /* Keep the fallback label when the list is unavailable. */ });
    return () => { active = false; };
  }, [portfolioId]);

  useEffect(() => {
    if (!isMobileNavOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    drawerCloseButton.current?.focus();
    const close = () => { setIsMobileNavOpen(false); menuButton.current?.focus(); };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { close(); return; }
      if (event.key !== 'Tab' || !drawer.current) return;
      const controls = Array.from(drawer.current.querySelectorAll<HTMLElement>('a[href], button:not(:disabled)'));
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    const desktopQuery = window.matchMedia('(min-width: 1280px)');
    desktopQuery.addEventListener('change', close);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      desktopQuery.removeEventListener('change', close);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [isMobileNavOpen]);

  const active = (path: string) => path === '/' ? pathname === '/' :
    path === '/portfolios' ? pathname === path || pathname.startsWith('/portfolio/') :
    pathname === path;

  const navLink = (name: string, path: string, Icon: typeof Wallet) => (
    <Link key={path} to={path} aria-current={active(path) ? 'page' : undefined}
      className={cn('app-nav-link', active(path) && 'is-active')}>
      <Icon className="h-[18px] w-[18px] shrink-0" />
      <span className="flex-1">{name}</span>
      {active(path) && <ChevronRight className="h-4 w-4 opacity-60" aria-hidden="true" />}
    </Link>
  );

  const navigation = (mobile = false) => (
    <nav aria-label={mobile ? 'Nawigacja mobilna' : 'Nawigacja główna'} className="app-navigation">
      {navLink('Centrum finansów', '/', LayoutDashboard)}
      {navLink('Raport miesięczny', '/reports/monthly', FileText)}
      <p className="app-nav-section">Inwestycje</p>
      {investmentLinks.map(({ name, path, icon }) => navLink(name, path, icon))}
      <div className="app-nav-divider" />
      {navLink('Budżet', '/budget', PiggyBank)}
      {(pathname === '/budget' || pathname.startsWith('/budget/')) && <div className="app-nav-subitems">{[
        {path:'/budget/imports',name:'Importy i paragony'}, {path:'/budget/forecast',name:'Prognoza pieniędzy'},
        {path:'/budget/accounts',name:'Konta i przelewy'}, {path:'/budget/reserves',name:'Rezerwy na wydatki'},
      ].map(item=><Link key={item.path} to={item.path} className={cn('app-nav-sublink',pathname===item.path&&'is-active')} aria-current={pathname===item.path?'page':undefined}>{item.name}</Link>)}</div>}
      {navLink('Kredyty', '/loans', Landmark)}
      <div className="app-nav-tools">
        <p className="app-nav-section">Narzędzia</p>
        <Link to="/admin" aria-current={pathname === '/admin' ? 'page' : undefined}
          className={cn('app-nav-link', isToolRoute && 'is-active')}>
          <Settings className="h-[18px] w-[18px] shrink-0" />
          <span className="flex-1">Centrum narzędzi</span>
          {isToolRoute && <ChevronRight className="h-4 w-4 opacity-60" aria-hidden="true" />}
        </Link>
        {isToolRoute && <div className="app-nav-subitems">
          {toolLinks.map(({ name, path }) => (
            <Link key={path} to={path} aria-current={pathname === path ? 'page' : undefined}
              className={cn('app-nav-sublink', pathname === path && 'is-active')}>{name}</Link>
          ))}
        </div>}
      </div>
    </nav>
  );

  const portfolioLabel = portfolioId && portfolioName?.id === portfolioId ? portfolioName.name : 'Portfel';
  let section = 'Centrum finansów';
  let sectionPath: string | undefined;
  let current = '';
  if (pathname === '/portfolios') { section = 'Inwestycje'; sectionPath = '/portfolios'; current = 'Portfele'; }
  else if (pathname.startsWith('/portfolio/')) { section = 'Inwestycje'; sectionPath = '/portfolios'; current = portfolioLabel; }
  else if (pathname === '/radar') { section = 'Inwestycje'; sectionPath = '/portfolios'; current = 'Radar'; }
  else if (pathname === '/ideas') { section = 'Inwestycje'; sectionPath = '/portfolios'; current = 'Pomysły inwestycyjne'; }
  else if (pathname === '/goals') { section = 'Inwestycje'; sectionPath = '/portfolios'; current = 'Cele inwestycyjne'; }
  else if (pathname === '/journal') { section = 'Inwestycje'; sectionPath = '/portfolios'; current = 'Dziennik inwestora'; }
  else if (pathname === '/transactions' || pathname === '/admin/transactions') { section = 'Inwestycje'; sectionPath = '/portfolios'; current = 'Historia transakcji'; }
  else if (pathname.startsWith('/loans/')) { section = 'Kredyty'; sectionPath = '/loans'; current = 'Szczegóły kredytu'; }
  else if (pathname === '/loans') section = 'Kredyty';
  else if (pathname === '/budget') section = 'Budżet';
  else if (pathname === '/budget/reserves') { section = 'Budżet'; sectionPath = '/budget'; current = 'Rezerwy na wydatki'; }
  else if (pathname === '/budget/forecast') { section = 'Budżet'; sectionPath = '/budget'; current = 'Prognoza pieniędzy'; }
  else if (pathname === '/budget/imports') { section = 'Budżet'; sectionPath = '/budget'; current = 'Importy i paragony'; }
  else if (pathname === '/budget/accounts') { section = 'Budżet'; sectionPath = '/budget'; current = 'Konta i przelewy'; }
  else if (pathname === '/reports/monthly') { section = 'Raporty'; current = 'Miesięczny'; }
  else if (isToolRoute) {
    section = 'Narzędzia'; sectionPath = '/admin';
    current = pathname.startsWith('/admin/portfolio/') ? portfolioLabel : toolNames[pathname] ?? '';
  }

  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">Przejdź do treści</a>
      <aside className="app-sidebar hidden xl:flex">
        <Link to="/" className="flex items-center gap-3 px-2 py-2" aria-label="Portfolio Manager — pulpit">
          <span className="brand-mark"><PieChart className="h-6 w-6" /></span>
          <span><span className="block text-base font-bold tracking-tight">Portfolio Manager</span>
            <span className="text-xs text-gray-500">Twoje finanse w jednym miejscu</span></span>
        </Link>
        {navigation()}
      </aside>
      <div className="min-w-0 flex-1 xl:pl-64">
        <header className="app-topbar">
          <div className="flex min-w-0 items-center gap-3">
            <button ref={menuButton} type="button" onClick={() => setIsMobileNavOpen(true)}
              className="app-icon-button xl:hidden" aria-label="Otwórz menu"
              aria-expanded={isMobileNavOpen} aria-controls="mobile-navigation">
              <Menu className="h-5 w-5" />
            </button>
            <nav aria-label="Ścieżka nawigacji" className="app-breadcrumb">
              {sectionPath ? <Link to={sectionPath}>{section}</Link> : <span>{section}</span>}
              {current && <><ChevronRight className="h-4 w-4 shrink-0" aria-hidden="true" /><span aria-current="page" className="app-breadcrumb-current">{current}</span></>}
            </nav>
          </div>
          <span className="app-topbar-mark" aria-hidden="true" />
        </header>
        <main id="main-content" tabIndex={-1} className="app-content">{children}</main>
      </div>
      {isMobileNavOpen && <div className="app-mobile-overlay xl:hidden">
        <button type="button" className="app-mobile-backdrop" aria-label="Zamknij menu" onClick={() => { setIsMobileNavOpen(false); menuButton.current?.focus(); }} />
        <div id="mobile-navigation" ref={drawer} role="dialog" aria-modal="true" aria-label="Menu nawigacji" className="app-mobile-drawer">
          <div className="app-mobile-drawer-header"><span className="font-semibold">Menu</span>
            <button ref={drawerCloseButton} type="button" className="app-icon-button" aria-label="Zamknij menu"
              onClick={() => { setIsMobileNavOpen(false); menuButton.current?.focus(); }}><X className="h-5 w-5" /></button>
          </div>
          {navigation(true)}
        </div>
      </div>}
    </div>
  );
};

export default Layout;
