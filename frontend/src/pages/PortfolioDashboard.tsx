import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, ChevronRight, ChevronDown, Archive, ArrowUpRight, Wallet } from 'lucide-react';
import { portfolioApi, type TaxLimitsResponse } from '../api';
import { Portfolio } from '../types';
import { cn } from '../lib/utils';
import { finite, money, percent } from '../components/portfolio/researchModel';
import './PortfolioDashboard.css';

const accountLabels: Record<Portfolio['account_type'], string> = {
  STANDARD: 'Rachunek inwestycyjny', IKE: 'IKE', IKZE: 'IKZE',
  BONDS: 'Obligacje', SAVINGS: 'Oszczędności', PPK: 'PPK',
};
const accountColors: Record<Portfolio['account_type'], string> = {
  STANDARD: '#a2c1df', IKE: '#78b0f1', IKZE: '#dbad72',
  BONDS: '#e6c577', SAVINGS: '#67ded2', PPK: '#bba1e8',
};
const assetValue = (p: Portfolio) => p.valuation_status === 'incomplete' ? undefined : p.asset_value ?? p.portfolio_value;
const investmentResult = (p: Portfolio) => p.valuation_status === 'incomplete' ? undefined : p.investment_result ?? p.total_result;
const resultTone = (value: unknown) => finite(value) ? value > 0 ? 'io-positive' : value < 0 ? 'io-negative' : '' : '';
const normalize = (value: string) => value.toLocaleLowerCase('pl-PL').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ł/g, 'l');

const PortfolioRow: React.FC<{
  portfolio: Portfolio;
  level?: number;
  searching: boolean;
  onChildCreate: (parentId: number) => void;
}> = ({ portfolio, level = 0, searching, onChildCreate }) => {
  const [expanded, setExpanded] = useState(false);
  const children = portfolio.children ?? [];
  const open = searching || expanded;
  const value = assetValue(portfolio);
  const withdrawal = portfolio.withdrawable_value ?? portfolio.portfolio_value;
  const result = investmentResult(portfolio);
  const differentWithdrawal = finite(value) && finite(withdrawal) && Math.abs(value - withdrawal) >= 0.01;
  return <>
    <tr className={cn('io-row', level > 0 && 'io-strategy', portfolio.is_archived && 'io-archived')}>
      <td className="io-name-cell">
        <div className="io-name" style={{ paddingLeft: `${level * 12}px` }}>
          {children.length > 0 && <button className="io-icon-button" aria-label={`${open ? 'Zwiń' : 'Rozwiń'} strategie: ${portfolio.name}`} aria-expanded={open} onClick={() => setExpanded(!expanded)} disabled={searching}>
            {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </button>}
          <Link to={`/portfolio/${portfolio.id}`} className="io-account-link">
            <strong>{portfolio.name}<ArrowUpRight size={14} aria-hidden="true" /></strong>
            <span>{level > 0 ? 'Strategia' : accountLabels[portfolio.account_type]}{portfolio.is_archived && <> · Archiwum <Archive size={12} aria-hidden="true" /></>}</span>
          </Link>
          {!level && !portfolio.is_archived && ['IKE', 'STANDARD'].includes(portfolio.account_type) && <button className="io-icon-button io-add-strategy" onClick={() => onChildCreate(portfolio.id)} aria-label={`Dodaj strategię: ${portfolio.name}`} title="Dodaj strategię"><Plus size={15} /></button>}
        </div>
        {children.length > 0 && <span className="io-strategy-count">Strategie: {children.length} · zawarte w wartości konta</span>}
      </td>
      <td className="io-amount" data-label="Wartość aktywów">
        <strong>{money(value)}</strong>{!finite(value)&&finite(portfolio.estimated_portfolio_value)&&<span>Orientacyjnie ≈ {money(portfolio.estimated_portfolio_value)}</span>}
        {differentWithdrawal && <span>Wypłata ≈ {money(withdrawal)}</span>}
        {portfolio.valuation_status && portfolio.valuation_status !== 'ok' && <span className="io-quality">{portfolio.valuation_status === 'incomplete' ? 'Niepełna wycena' : 'Wycena orientacyjna'}</span>}
      </td>
      <td className="io-amount" data-label="Wynik od początku">
        <strong className={resultTone(result)}>{money(result)}</strong>
        <span className={resultTone(result)}>{percent(finite(result) ? portfolio.total_result_percent : undefined)}</span>
      </td>
    </tr>
    {open && children.map(child => <PortfolioRow key={child.id} portfolio={child} level={level + 1} searching={searching} onChildCreate={onChildCreate} />)}
  </>;
};

const PortfolioDashboard: React.FC = () => {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('value');
  const [hideEmpty, setHideEmpty] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [taxLimits, setTaxLimits] = useState<TaxLimitsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [parentPortfolioId, setParentPortfolioId] = useState<number | null>(null);
  const [newPortfolioName, setNewPortfolioName] = useState('');
  const [initialCash, setInitialCash] = useState('');
  const [accountType, setAccountType] = useState<'STANDARD' | 'IKE' | 'IKZE' | 'BONDS' | 'SAVINGS' | 'PPK'>('STANDARD');
  const [createdAt, setCreatedAt] = useState(new Date().toISOString().split('T')[0]);

  const [limitsError, setLimitsError] = useState(false);
  const [ppkRefreshWarning, setPpkRefreshWarning] = useState<string | null>(null);
  const ppkChecked = useRef<number | null>(null);
  const fetchData = async () => {
    setError(null); setLimitsError(false);
    const [listRes, limitsRes] = await Promise.allSettled([portfolioApi.list(), portfolioApi.limits()]);
    if (listRes.status === 'fulfilled') setPortfolios(listRes.value.portfolios);
    else setError('Nie udało się wczytać portfeli.');
    if (limitsRes.status === 'fulfilled') setTaxLimits(limitsRes.value.limits);
    else { setTaxLimits(null); setLimitsError(true); }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    const ppk = portfolios.find(p => p.account_type === 'PPK' && !p.is_archived);
    if (!ppk || ppkChecked.current === ppk.id) return;
    ppkChecked.current = ppk.id;
    let active = true;
    void portfolioApi.refreshPpkPrice(ppk.id).then(async result => {
      if (!active) return;
      setPpkRefreshWarning(result.warning);
      if (result.changed) {
        const list = await portfolioApi.list();
        if (active) setPortfolios(list.portfolios);
      }
    }).catch(() => {
      if (active) setPpkRefreshWarning('Nie udało się sprawdzić wyceny PPK. Zachowano ostatnią zapisaną cenę.');
    });
    return () => { active = false; };
  }, [portfolios]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPortfolioName.trim()) return;

    try {
      if (parentPortfolioId) {
        await portfolioApi.createChild(parentPortfolioId, {
          name: newPortfolioName,
          initial_cash: parseFloat(initialCash) || 0,
          account_type: accountType,
          created_at: createdAt,
          parent_portfolio_id: parentPortfolioId
        });
      } else {
        await portfolioApi.create({
          name: newPortfolioName,
          initial_cash: parseFloat(initialCash) || 0,
          account_type: accountType,
          created_at: createdAt
        });
      }
      setNewPortfolioName('');
      setInitialCash('');
      setAccountType('STANDARD');
      setParentPortfolioId(null);
      setCreatedAt(new Date().toISOString().split('T')[0]);
      setIsCreating(false);
      fetchData();
    } catch (err) {
      console.error('Failed to create portfolio', err);
      alert('Failed to create portfolio');
    }
  };

  const handleAddSubPortfolio = (parentId: number) => {
    const parent = portfolios.find(p => p.id === parentId);
    if (parent) {
      setAccountType(parent.account_type);
      setParentPortfolioId(parentId);
      setIsCreating(true);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  if (loading) return <div className="p-4 text-center">Ładowanie...</div>;
  if (error) return <div className="p-4 text-center text-red-600">{error}</div>;

  const active = portfolios.filter(p => !p.is_archived && !p.parent_portfolio_id);
  const incomplete = active.some(p => p.valuation_status === 'incomplete' || !finite(assetValue(p)) || !finite(investmentResult(p)) || !finite(p.withdrawable_value ?? p.portfolio_value));
  const stale = active.some(p => p.valuation_status === 'stale');
  const totalValue = incomplete ? null : active.reduce((sum, p) => sum + (p.asset_value ?? p.portfolio_value ?? 0), 0);
  const totalWithdrawal = incomplete ? null : active.reduce((sum, p) => sum + (p.withdrawable_value ?? p.portfolio_value ?? 0), 0);
  const totalResult = incomplete ? null : active.reduce((sum, p) => sum + (p.investment_result ?? p.total_result ?? 0), 0);
  const contributions = active.map(p => finite(p.net_contributions) ? p.net_contributions : finite(assetValue(p)) && finite(investmentResult(p)) ? assetValue(p)! - investmentResult(p)! : undefined);
  const totalNetContributions = contributions.every(finite) ? contributions.reduce((sum, value) => sum + value, 0) : null;
  const totalResultPercent = totalResult !== null && totalNetContributions !== null && totalNetContributions > 0 ? totalResult / totalNetContributions * 100 : null;
  const warnings = [...new Set(active.flatMap(p => p.valuation_warnings ?? []))];

  const search = normalize(query.trim());
  const matches = (p: Portfolio) => normalize(`${p.name} ${accountLabels[p.account_type]}`).includes(search);
  const compare = (a: Portfolio, b: Portfolio) => {
    if (sort === 'name') return a.name.localeCompare(b.name, 'pl');
    const av = sort === 'result' ? investmentResult(a) : assetValue(a);
    const bv = sort === 'result' ? investmentResult(b) : assetValue(b);
    if (!finite(av)) return finite(bv) ? 1 : a.name.localeCompare(b.name, 'pl');
    if (!finite(bv)) return -1;
    return bv - av || a.name.localeCompare(b.name, 'pl');
  };
  const filterTree = (p: Portfolio, parentMatched = false): Portfolio | null => {
    if (!showArchived && p.is_archived) return null;
    const matched = parentMatched || !search || matches(p);
    const children = (p.children ?? []).map(child => filterTree(child, matched)).filter((child): child is Portfolio => child !== null).sort(compare);
    if (!matched && !children.length) return null;
    if (hideEmpty && finite(assetValue(p)) && Math.abs(assetValue(p)!) < 0.005 && !children.length) return null;
    return { ...p, children };
  };
  const roots = portfolios.filter(p => !p.parent_portfolio_id);
  const visible = roots.map(p => filterTree(p)).filter((p): p is Portfolio => p !== null).sort(compare);
  const allocation = Object.entries(accountLabels).map(([type, label]) => ({
    type: type as Portfolio['account_type'], label,
    value: active.filter(p => p.account_type === type).reduce((sum, p) => sum + (assetValue(p) ?? 0), 0),
  })).filter(group => group.value > 0).sort((a, b) => b.value - a.value);
  const canAllocate = totalValue !== null && totalValue > 0 && active.every(p => finite(assetValue(p)) && assetValue(p)! >= 0);
  const resetFilters = () => { setQuery(''); setHideEmpty(false); setShowArchived(false); };

  return (
    <div className="investment-overview">
      <div className="page-heading io-heading">
        <div><p className="page-eyebrow">Portfele i aktywa</p><h1>Przegląd inwestycji</h1><p>Cały kapitał w jednym miejscu. Zobacz, gdzie jest i jak pracuje.</p></div>
        <button onClick={() => { setParentPortfolioId(null); setIsCreating(!isCreating); }} className="io-button io-primary"><Plus size={17} />Nowy Portfel</button>
      </div>
          {isCreating && (
            <div className="bg-white dark:bg-slate-900 shadow-sm rounded-xl p-6 border border-gray-200 dark:border-slate-800">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">
                  {parentPortfolioId ? `Dodaj Sub-portfel dla: ${portfolios.find(p => p.id === parentPortfolioId)?.name}` : 'Utwórz Nowy Portfel'}
                </h3>
              </div>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-slate-300">Nazwa Portfela</label>
                    <input
                      type="text"
                      id="name"
                      value={newPortfolioName}
                      onChange={(e) => setNewPortfolioName(e.target.value)}
                      className="mt-1 block w-full rounded-lg border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border transition-colors"
                      placeholder="np. Emerytura IKE"
                      required
                    />
                  </div>
                  <div>
                    <label htmlFor="cash" className="block text-sm font-medium text-gray-700 dark:text-slate-300">Gotówka na start (PLN)</label>
                    <input
                      type="number"
                      id="cash"
                      value={initialCash}
                      onChange={(e) => setInitialCash(e.target.value)}
                      className="mt-1 block w-full rounded-lg border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border transition-colors"
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                    />
                  </div>
                  <div>
                    <label htmlFor="type" className="block text-sm font-medium text-gray-700 dark:text-slate-300">Typ Konta</label>
                    <select
                      id="type"
                      value={accountType}
                      onChange={(e) => setAccountType(e.target.value as 'STANDARD' | 'IKE' | 'IKZE' | 'BONDS' | 'SAVINGS' | 'PPK')}
                      disabled={!!parentPortfolioId}
                      className="mt-1 block w-full rounded-lg border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border disabled:bg-gray-100 dark:disabled:bg-slate-800/50 transition-colors"
                    >
                      <option value="STANDARD">Standardowe Akcje</option>
                      <option value="IKE">IKE (Akcje)</option>
                      <option value="IKZE">IKZE (Akcje)</option>
                      <option value="BONDS">Obligacje</option>
                      <option value="SAVINGS">Konto Oszczędnościowe</option>
                      <option value="PPK">PPK</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="createdAt" className="block text-sm font-medium text-gray-700 dark:text-slate-300">Data Utworzenia</label>
                    <input
                      type="date"
                      id="createdAt"
                      value={createdAt}
                      onChange={(e) => setCreatedAt(e.target.value)}
                      className="mt-1 block w-full rounded-lg border-gray-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border transition-colors"
                      required
                    />
                  </div>
                </div>
                <div className="flex justify-end space-x-3 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreating(false);
                      setParentPortfolioId(null);
                    }}
                    className="px-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm font-semibold text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 focus:outline-none transition-colors"
                  >
                    Anuluj
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-500 focus:outline-none transition-colors"
                  >
                    {parentPortfolioId ? 'Dodaj Sub-portfel' : 'Utwórz Portfel'}
                  </button>
                </div>
              </form>
            </div>
          )}

      {(incomplete || stale) && <div role="status" className="io-notice"><strong>{incomplete ? 'Niepełna wycena — brakuje cen lub kursów walut' : 'Wycena orientacyjna — część notowań jest nieaktualna'}</strong>{warnings.map(note => <p key={note}>{note}</p>)}</div>}
      {ppkRefreshWarning && <p role="status" className="io-notice">{ppkRefreshWarning}</p>}
      {limitsError && <p role="alert" className="io-notice">Limity wpłat są chwilowo niedostępne. <button onClick={fetchData}>Spróbuj ponownie</button></p>}
      <section className="io-summary" aria-label="Podsumowanie aktywnych kont">
        <dl className="io-summary-main">
          <div className="io-total"><dt><Wallet size={17} aria-hidden="true" />Wartość aktywów</dt><dd>{money(totalValue)}</dd><p>Łącznie na aktywnych kontach · strategie wliczone tylko raz</p></div>
          <div className="io-result"><dt>Wynik inwestowania</dt><dd className={resultTone(totalResult)}>{money(totalResult)}</dd><p><strong className={resultTone(totalResult)}>{percent(totalResultPercent)}</strong> · od początku, bez nowych wpłat</p></div>
        </dl>
        <dl className="io-summary-secondary">
          <div><dt>Kapitał wpłacony netto</dt><dd>{money(totalNetContributions)}</dd></div>
          <div><dt>Szacowana wypłata</dt><dd>{money(totalWithdrawal)}</dd></div>
        </dl>
      </section>
      <div className="io-layout">
        <section className="io-panel io-portfolios" aria-labelledby="portfolio-list-title">
          <div className="io-panel-heading"><div><h2 id="portfolio-list-title">Twoje portfele</h2><p>Widoczne konta: {visible.length} z {roots.length}</p></div><span className="io-period">Wynik od początku</span></div>
          <div className="io-filters">
            <label className="io-search"><Search size={17} aria-hidden="true" /><input aria-label="Szukaj portfela lub strategii" placeholder="Szukaj konta lub strategii…" value={query} onChange={e => setQuery(e.target.value)} type="search" /></label>
            <label className="io-sort"><span className="sr-only">Sortowanie portfeli</span><select aria-label="Sortowanie portfeli" value={sort} onChange={e => setSort(e.target.value)}><option value="value">Największa wartość</option><option value="result">Największy wynik w PLN</option><option value="name">Nazwa A–Z</option></select></label>
            <div className="io-filter-options"><label><input type="checkbox" checked={hideEmpty} onChange={e => setHideEmpty(e.target.checked)} />Ukryj puste</label><label><input type="checkbox" checked={showArchived} onChange={e => setShowArchived(e.target.checked)} />Pokaż archiwalne</label></div>
          </div>
          <table className="io-table"><caption className="sr-only">Wartość i wynik portfeli. Szacowaną wypłatę pokazujemy pod wartością, kiedy kwoty się różnią.</caption><thead><tr><th scope="col">Konto / strategia</th><th scope="col">Wartość aktywów</th><th scope="col">Wynik od początku</th></tr></thead><tbody>
            {visible.map(p => <PortfolioRow key={p.id} portfolio={p} searching={!!search} onChildCreate={handleAddSubPortfolio} />)}
            {!visible.length && <tr><td className="io-empty" colSpan={3}>{!roots.length ? 'Brak portfeli. Utwórz nowy, aby rozpocząć!' : <><p>Brak kont pasujących do filtrów.</p><button className="io-button" onClick={resetFilters}>Wyczyść filtry</button></>}</td></tr>}
          </tbody></table>
          <details className="io-explanation"><summary>Jak liczymy wartość, wynik i wypłatę?</summary><p>Wartość aktywów obejmuje gotówkę i inwestycje, w PPK wartość jednostek brutto. Kapitał wpłacony netto to wpłaty pomniejszone o wypłaty. Wynik to zmiana wartości względem wpłat netto — wpłaty pracodawcy nie są zyskiem. Procent pokazuje prosty wynik od początku, bez uwzględnienia dat wpłat; nie jest roczną stopą zwrotu. Szacowana wypłata uwzględnia potrącenia przy zwrocie PPK przed 60. rokiem życia. W akcjach uwzględniamy szacowaną opłatę walutową, w obligacjach podatek od odsetek; wcześniejszy wykup może dodatkowo zmniejszyć wypłatę. Nie sumujemy podportfeli ponownie.</p></details>
        </section>
        <aside className="io-sidebar">
          <section className="io-panel io-allocation" aria-labelledby="allocation-title"><h2 id="allocation-title">Gdzie są Twoje pieniądze</h2><p>Struktura aktywnych kont</p>
            {canAllocate ? <><div className="io-allocation-bar" aria-hidden="true">{allocation.map(group => <span key={group.type} style={{ width: `${group.value / totalValue * 100}%`, background: accountColors[group.type] }} />)}</div><ul>{allocation.map(group => <li key={group.type}><div><span className="io-dot" style={{ background: accountColors[group.type] }} /><span>{group.label}</span><strong>{percent(group.value / totalValue * 100)}</strong></div><p>{money(group.value)}</p></li>)}</ul><small>Podział według kont obejmuje również ich gotówkę. Strategie są wliczone w konto główne.</small></> : <p className="io-empty-allocation">{incomplete ? 'Uzupełnij wycenę, aby zobaczyć pełną strukturę.' : 'Struktura pojawi się po dodaniu środków i pełnej wycenie kont.'}</p>}
          </section>
          {taxLimits && <section className="io-panel io-limits" aria-labelledby="limits-title"><h2 id="limits-title">Limity wpłat · {taxLimits.year}</h2><p>Miejsce na kolejne wpłaty</p>{(['IKE', 'IKZE'] as const).map(type => {
            const data = taxLimits[type];
            const remaining = finite(data.limit) ? data.limit - data.deposited : null;
            const progress = finite(data.percentage) ? Math.max(0, Math.min(100, data.percentage)) : 0;
            return <div className="io-limit" key={type}><h3>{type}<span>{percent(data.percentage)}</span></h3><div className="io-progress" role="progressbar" aria-label={`Wykorzystanie limitu ${type}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={finite(data.percentage) ? progress : undefined} aria-valuetext={finite(data.percentage) ? percent(data.percentage) : 'Limit nieopublikowany'}><span style={{ width: `${progress}%` }} /></div><dl><div><dt>Wpłacono</dt><dd>{money(data.deposited)}</dd></div><div className={remaining !== null && remaining < 0 ? 'io-negative' : ''}><dt>{remaining !== null && remaining < 0 ? 'Przekroczenie' : 'Pozostało'}</dt><dd>{money(remaining !== null ? Math.abs(remaining) : null)}</dd></div></dl><small>{finite(data.limit) ? `Limit: ${money(data.limit)}` : 'Limit nieopublikowany'}</small></div>;
          })}</section>}
        </aside>
      </div>
    </div>
  );
};

export default PortfolioDashboard;
