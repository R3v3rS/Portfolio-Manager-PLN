import { Link, useSearchParams } from 'react-router-dom';
import { useState } from 'react';
import { CalendarDays, Camera, ChevronLeft, ChevronRight, FileUp, LayoutDashboard, List, Pencil, Plus, ReceiptText, Settings2, Target, TrendingUp, Wallet } from 'lucide-react';
import { planningToday } from './planningHelpers';
import './budgetClarity.css';
import './budgetUsability.css';
import './budgetModes.css';
import './budgetReadability.css';
import { confirmBudgetNavigation, useBudgetMode } from './budgetMode';

export const budgetMonth = (value: string | null) => /^\d{4}-(0[1-9]|1[0-2])$/.test(value ?? '') ? value! : planningToday().slice(0, 7);
export const budgetHref = (view: string, month: string) => `/budget?view=${view}&month=${month}`;
const shift = (month: string, delta: number) => {
  const [year, current] = month.split('-').map(Number);
  const next = new Date(year, current - 1 + delta, 1);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`;
};
type Props = { active: string; month?: string; onMonth?: (month: string) => void; onView?: (view: string) => void; current?: boolean; onExpense?: () => void; onIncome?: () => void };

export default function BudgetNavigation({ active, month: selected, onMonth, onView, current = false, onExpense, onIncome }: Props) {
  const [params, setParams] = useSearchParams();
  const [menu, setMenu] = useState(false);
  const { management, setManagement } = useBudgetMode();
  const month = selected ?? budgetMonth(params.get('month'));
  const changeMonth = (value: string) => {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(value)) return;
    if (!confirmBudgetNavigation()) return;
    if (onMonth) onMonth(value);
    else { const next = new URLSearchParams(params); next.set('month', value); setParams(next); }
  };
  const tabs = [
    { id: 'overview', name: 'Podsumowanie', icon: LayoutDashboard, href: budgetHref('overview', month), local: true },
    { id: 'plan', name: 'Plan miesiąca', icon: CalendarDays, href: budgetHref('plan', month), local: true },
    { id: 'entries', name: 'Transakcje', icon: List, href: budgetHref('entries', month), local: true },
    { id: 'bills', name: 'Rachunki i raty', icon: ReceiptText, href: budgetHref('bills', month), local: true },
    { id: 'reserves', name: 'Rezerwy', icon: Target, href: `/budget/reserves?month=${month}` },
    { id: 'accounts', name: 'Konta', icon: Wallet, href: `/budget/accounts?month=${month}` },
    { id: 'forecast', name: 'Prognoza', icon: TrendingUp, href: `/budget/forecast?month=${month}` },
  ];
  const primary=active==='imports'?'entries':active;
  return <div className="budget-navigation">
    <div className={`budget-navigation-tools budget-toolbar ${management?'is-managing':''}`}>
      <div className="budget-month-picker" aria-label="Wybór miesiąca">
        <button type="button" aria-label="Poprzedni miesiąc" onClick={() => changeMonth(shift(month, -1))}><ChevronLeft size={17}/></button>
        <input type="month" aria-label="Miesiąc budżetu" value={month} onChange={event => changeMonth(event.target.value)}/>
        <button type="button" aria-label="Następny miesiąc" onClick={() => changeMonth(shift(month, 1))}><ChevronRight size={17}/></button>
      </div>
      <div className="budget-mode-control"><span className="budget-mode-name">{management?'Zarządzanie':'Przegląd'}</span><button type="button" className="budget-button-secondary" aria-label={management?'Zakończ zarządzanie':'Włącz zarządzanie'} aria-pressed={management} title={management?'Zakończ zmienianie limitów i ustawień':'Pokaż edycję limitów, kategorii i ustawień'} onClick={()=>setManagement(!management)}><Pencil size={14}/><span className="budget-mode-full">{management?'Zakończ':'Zarządzaj'}</span><span className="budget-mode-short" aria-hidden="true">{management?'Gotowe':'Edytuj'}</span></button></div>
      <div className="budget-navigation-actions">
        {management && <Link className={`budget-button-quiet ${active === 'settings' ? 'is-active' : ''}`} aria-current={active === 'settings' ? 'page' : undefined} to={budgetHref('settings', month)}><Settings2 size={16}/>Ustawienia</Link>}
        {onExpense&&<button className="budget-button-primary" onClick={onExpense}><Plus size={16}/>Wydatek</button>}
        <details className="budget-add-menu" open={menu}><summary className="budget-button-secondary" aria-expanded={menu} onClick={event=>{event.preventDefault();setMenu(!menu);}}><Plus size={16}/>Dodaj / Importuj</summary>
          {menu&&<div onClick={()=>setMenu(false)}>
            {!onExpense&&<Link to={`${budgetHref('entries', month)}&add=expense`}>Wydatek</Link>}
            {onIncome ? <button onClick={onIncome}>Wpływ</button> : <Link to={`${budgetHref('entries', month)}&add=income`}>Wpływ</Link>}
            <Link to={`/budget/imports?tab=csv&month=${month}`}><FileUp size={15}/>Wyciąg bankowy</Link>
            <Link to={`/budget/imports?tab=receipt&month=${month}`}><Camera size={15}/>Paragon</Link>
            <Link to={`/budget/imports?tab=pending&month=${month}`}>Do sprawdzenia</Link>
          </div>}
        </details>
      </div>
    </div>
    <nav className="budget-primary-nav" aria-label="Widoki budżetu">
      {tabs.map(({ icon: Icon, ...tab }) => <Link key={tab.id} to={tab.href} aria-current={primary === tab.id ? 'page' : undefined}
        className={primary === tab.id ? 'is-active' : ''} onClick={event => {
          if (tab.local && onView && !event.ctrlKey && !event.metaKey && !event.shiftKey && event.button === 0) {
            event.preventDefault(); onView(tab.id);
          }
        }}><Icon size={16}/>{tab.name}</Link>)}
    </nav>
    {primary==='entries'&&<nav className="budget-secondary-nav" aria-label="Transakcje i importy"><Link className={active==='entries'?'is-active':''} to={budgetHref('entries',month)}>Historia transakcji</Link><Link className={active==='imports'?'is-active':''} to={`/budget/imports?tab=pending&month=${month}`}>Importy i paragony</Link></nav>}
    {current && <p className="budget-time-context">Salda i rezerwy: stan teraz. Plan i transakcje: {month}.</p>}
  </div>;
}
