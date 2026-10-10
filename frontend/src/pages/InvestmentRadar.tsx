import { portfolioApi } from '../api';
import { chartTooltip } from '../components/charts/chartTheme';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Radar, Plus, RefreshCw, Search, ArrowUpRight, SlidersHorizontal, X, Bookmark, CalendarDays, ScanLine, Activity } from 'lucide-react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { RadarItem } from '../types';
import StockProfilerModal from '../components/StockProfilerModal';
import RadarDetails from '../components/radar/RadarDetails';
import { change, comparisonSeries, dataStatus, dateText, localDate, needsAttention, number, targetReached, tone, upcomingEvents, type HistoryPoint } from '../components/radar/radarModel';
import { radarApi } from '../api_radar';
import { extractErrorMessageFromUnknown } from '../http/response';
import { useSearchParams } from 'react-router-dom';
import '../components/radar/radar.css';

type Filters = { query:string; scope:string; sector:string; currency:string; type:string; status:string; sort:string };
const initialFilters: Filters = {query:'',scope:'all',sector:'all',currency:'all',type:'all',status:'all',sort:'ticker'};
const palette = ['#67ded2','#fbbf24','#c4a6f0','#84ccaa'];
function Sparkline({item}:{item:RadarItem}) {
  const points = item.sparkline || [];
  if (points.length < 2) return <span className="rd-help">Brak historii</span>;
  const values = points.map(point => point.close_price), low = Math.min(...values), high = Math.max(...values);
  const path = values.map((value,i) => `${i * 110/(values.length-1)},${30 - (value-low)/(high-low || 1)*26}`).join(' ');
  return <svg className={`rd-spark ${tone(values[values.length-1]-values[0])}`} viewBox="0 0 112 34" role="img" aria-label={`Cena: ${dateText(points[0].date)} – ${dateText(points[points.length-1].date)}`}><title>{dateText(points[0].date)} – {dateText(points[points.length-1].date)}</title><polyline points={path} fill="none" stroke="currentColor" strokeWidth="2"/></svg>;
}
export default function InvestmentRadar() {
  const [params] = useSearchParams();
  const [items,setItems] = useState<RadarItem[]>([]);
  const [loading,setLoading] = useState(true);
  const [busy,setBusy] = useState('');
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [auto,setAuto] = useState(false);
  const [now,setNow] = useState(Date.now());
  const [quote,setQuote] = useState<'native'|'PLN'>('native');
  const [missingFx,setMissingFx] = useState(0);
  const [view,setView] = useState<'list'|'compare'|'calendar'>('list');
  const [filters,setFilters] = useState<Filters>(() => ({ ...initialFilters, query: params.get('ticker') || '' }));
  const [newTicker,setNewTicker] = useState('');
  const [showAdd,setShowAdd] = useState(false);
  const [dividends,setDividends] = useState(false);
  const [selected,setSelected] = useState<string[]>([]);
  const [detail,setDetail] = useState<string | null>(() => params.get('ticker'));
  const [analysis,setAnalysis] = useState<string | null>(null);
  const [histories,setHistories] = useState<Record<string,HistoryPoint[]>>({});
  const [historyError,setHistoryError] = useState('');
  const [historyLoading,setHistoryLoading] = useState(false);
  const [days,setDays] = useState(365);
  const [saved,setSaved] = useState<Filters | null>(() => { try { const value = JSON.parse(localStorage.getItem('radar-view-v1') || 'null'); return value && typeof value === 'object' && Object.keys(initialFilters).every(key => typeof value[key] === 'string') ? value : null; } catch { return null; } });
  const working = useRef(false);
  const mounted = useRef(true);
  const load = useCallback(async () => {
    const result = await radarApi.getAll(false);
    if (mounted.current) { setItems(result); setNow(Date.now()); }
  },[]);
  useEffect(() => {
    mounted.current = true;
    load().catch(err => { if (mounted.current) setError(extractErrorMessageFromUnknown(err)); }).finally(() => { if (mounted.current) setLoading(false); });
    const timer = window.setInterval(() => setNow(Date.now()),60_000);
    return () => { mounted.current = false; window.clearInterval(timer); };
  },[load]);
  const refresh = useCallback(async (ticker?:string) => {
    if (working.current) return;
    working.current = true; setBusy(ticker || 'all'); setError(''); setNotice('');
    try { await radarApi.refresh(ticker ? [ticker] : undefined); await load(); if (mounted.current) setNotice('Odświeżanie zakończone. Status przy każdym instrumencie pokazuje wiek zapisanego notowania.'); }
    catch (err) { if (mounted.current) setError(extractErrorMessageFromUnknown(err)); }
    finally { working.current = false; if (mounted.current) setBusy(''); }
  },[load]);
  useEffect(() => {
    if (!auto) return;
    void refresh();
    const timer = window.setInterval(() => { if (document.visibilityState === 'visible') void refresh(); },300_000);
    return () => window.clearInterval(timer);
  },[auto,refresh]);
  const watch = async (ticker:string, remove = false) => {
    if (working.current) return;
    working.current = true; setBusy(ticker); setError(''); setNotice('');
    try {
      if (remove) await radarApi.removeFromWatchlist(ticker); else await radarApi.addToWatchlist(ticker);
      await load(); setNewTicker(''); setShowAdd(false);
      if (remove) setSelected(current => current.filter(value => value !== ticker));
      setNotice(remove ? `Usunięto ${ticker} z obserwowanych. Posiadane instrumenty pozostają na radarze.` : `Dodano ${ticker}. Jeśli brakuje notowań, użyj odświeżania.`);
    } catch (err) { setError(extractErrorMessageFromUnknown(err)); }
    finally { working.current = false; setBusy(''); }
  };
  const updateFilter = (key:keyof Filters,value:string) => setFilters(current => ({...current,[key]:value}));
  const events = useMemo(() => upcomingEvents(items,new Date(now)),[items,now]);
  const recent = items.filter(item => dataStatus(item,now) === 'recent');
  const attention = items.filter(item => needsAttention(item,now));
  const visible = useMemo(() => {
    const numericSort = ['change_1d','change_1m','change_1y','dividend_yield'].includes(filters.sort);
    return items.filter(item => {
      const text = `${item.ticker} ${item.company_name || ''}`.toLowerCase();
      return text.includes(filters.query.toLowerCase().trim()) &&
        (filters.scope === 'all' || (filters.scope === 'held' ? item.quantity > 0 : item.is_watched)) &&
        (filters.type === 'all' || (filters.type === 'ETF' ? item.instrument_type === 'ETF' : item.instrument_type !== 'ETF')) &&
        (filters.sector === 'all' || (item.sector || 'Nieprzypisany') === filters.sector) &&
        (filters.currency === 'all' || (item.currency || 'Nieznana') === filters.currency) &&
        (filters.status === 'all' || (filters.status === 'attention' ? needsAttention(item,now) : filters.status === 'target' ? targetReached(item,now) : dataStatus(item,now) === filters.status));
    }).sort((a,b) => {
      if (!numericSort) return a.ticker.localeCompare(b.ticker);
      const av = a[filters.sort as 'change_1d'], bv = b[filters.sort as 'change_1d'];
      return av == null ? (bv == null ? a.ticker.localeCompare(b.ticker) : 1) : bv == null ? -1 : bv-av;
    });
  },[items,filters,now]);
  const comparisonItems = selected.map(ticker => items.find(item => item.ticker === ticker)).filter((item):item is RadarItem => Boolean(item));
  useEffect(() => {
    if (view !== 'compare' || !selected.length) return;
    let live = true; setHistoryLoading(true); setHistoryError('');
    Promise.all(selected.map(async ticker => { if (quote === 'native') return { ticker, history: await radarApi.history(ticker), missing: 0 }; const result = await portfolioApi.getPriceHistory(ticker, 'PLN'); return { ticker, history: result.history, missing: result.missing_fx_dates?.length ?? 0 }; })).then(entries => { if(live) { setHistories(Object.fromEntries(entries.map(item => [item.ticker, item.history]))); setMissingFx(entries.reduce((sum, item) => sum + item.missing, 0)); } })
      .catch(() => { if(live) { setHistories({}); setHistoryError('Nie udało się pobrać historii. Zmień widok i spróbuj ponownie.'); } })
      .finally(() => { if(live) setHistoryLoading(false); });
    return () => { live = false; };
  },[selected,view,quote]);
  const series = comparisonSeries(histories,selected,days,new Date(now));
  const toggleSelection = (ticker:string) => setSelected(current => current.includes(ticker) ? current.filter(value => value !== ticker) : current.length < 4 ? [...current,ticker] : current);
  const selectedItem = items.find(item => item.ticker === detail);
  const relevantEvents = events.filter(event => visible.some(item => item.ticker === event.ticker));

  return <div className="rd-page">
    <header className="rd-heading"><div><span className="rd-eyebrow"><Radar size={15}/> TWOJA LISTA OBSERWACYJNA</span><h1>Radar inwestycyjny</h1><p>Obserwuj rynek. Porównuj pomysły. Wracaj do własnych założeń.</p></div><div className="rd-actions"><button className="rd-button" disabled={Boolean(busy) || loading} onClick={() => void refresh()}><RefreshCw size={16} className={busy ? 'rd-spin' : ''}/>{busy ? 'Odświeżanie…' : 'Odśwież dane'}</button><button className="rd-button rd-primary" aria-expanded={showAdd} onClick={() => setShowAdd(!showAdd)}><Plus size={17}/>Dodaj instrument</button></div></header>
    <div className="rd-refresh"><span><i className={recent.length === items.length && items.length ? 'rd-dot' : 'rd-dot rd-dot-warning'}/>{recent.length}/{items.length} notowań zapisanych w ostatnich 72 h · to nie są dane na żywo</span><label><input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)}/> Odświeżaj co 5 min w aktywnej karcie</label></div>
    {showAdd && <form className="rd-add rd-panel" onSubmit={e => {e.preventDefault(); void watch(newTicker.trim().toUpperCase());}}><label>Symbol giełdowy<input autoFocus value={newTicker} maxLength={40} onChange={e => setNewTicker(e.target.value)} placeholder="np. CDR.WA, NVDA" required/></label><button className="rd-button rd-primary" disabled={Boolean(busy) || !newTicker.trim()}>Dodaj do obserwowanych</button><p className="rd-help">Dla GPW użyj końcówki .WA. Posiadane instrumenty trafiają tu automatycznie.</p></form>}
    {error && <div className="rd-error" role="alert">{error} <button onClick={() => void load().then(() => setError('')).catch(err => setError(extractErrorMessageFromUnknown(err)))}>Ponów odczyt</button></div>}
    {notice && <div className="rd-notice" role="status">{notice}<button className="rd-icon" aria-label="Zamknij komunikat" onClick={() => setNotice('')}><X size={16}/></button></div>}
    <section className="rd-kpis" aria-label="Podsumowanie radaru">
      <button onClick={() => {setFilters(initialFilters);setView('list');}}><Bookmark size={19}/><span>Na Twoim radarze</span><strong>{items.length}</strong><small>{items.filter(item => item.quantity > 0).length} posiadanych · {items.filter(item => item.is_watched).length} obserwowanych</small></button>
      <button onClick={() => {setFilters({...initialFilters,status:'recent',sort:'change_1d'});setView('list');}}><Activity size={19}/><span>Ruch w ostatniej sesji</span><strong><em className="rd-positive">{recent.filter(item => (item.change_1d || 0) > 0).length} ↑</em> <em className="rd-negative">{recent.filter(item => (item.change_1d || 0) < 0).length} ↓</em></strong><small>Tylko niedawno zapisane notowania</small></button>
      <button onClick={() => {setFilters(initialFilters);setView('calendar');}}><CalendarDays size={19}/><span>Nadchodzące wydarzenia</span><strong>{events.filter(event => new Date(event.date).getTime() - now < 30*86400_000).length}</strong><small>Raporty, dywidendy i przeglądy · 30 dni</small></button>
      <button onClick={() => {setFilters({...initialFilters,status:'attention'});setView('list');}}><ScanLine size={19}/><span>Wymagają uwagi</span><strong>{attention.length}</strong><small>Braki, stare dane i Twoje warunki</small></button>
    </section>
    <section className="rd-panel rd-workspace">
      <div className="rd-workspace-top"><nav className="rd-tabs" aria-label="Widok radaru"><button aria-current={view === 'list' ? 'page' : undefined} onClick={() => setView('list')}>Lista instrumentów</button><button aria-current={view === 'compare' ? 'page' : undefined} onClick={() => setView('compare')}>Porównanie {selected.length > 0 && <b>{selected.length}</b>}</button><button aria-current={view === 'calendar' ? 'page' : undefined} onClick={() => setView('calendar')}>Kalendarz</button></nav><span className="rd-help">{visible.length} z {items.length} instrumentów</span></div>
      <div className="rd-filters"><label className="rd-search"><Search size={17}/><input type="search" aria-label="Szukaj instrumentu" placeholder="Szukaj spółki lub symbolu…" value={filters.query} onChange={e => updateFilter('query',e.target.value)}/></label><select aria-label="Zakres instrumentów" value={filters.scope} onChange={e => updateFilter('scope',e.target.value)}><option value="all">Wszystkie instrumenty</option><option value="held">Mam w portfelu</option><option value="watched">Obserwowane</option></select><select aria-label="Status danych" value={filters.status} onChange={e => updateFilter('status',e.target.value)}><option value="all">Wszystkie statusy</option><option value="recent">Zapisane w ciągu 72 h</option><option value="stale">Nieaktualne notowania</option><option value="missing">Brak ceny</option><option value="target">Osiągnięty poziom</option><option value="attention">Wymagają uwagi</option></select><details className="rd-filter-more"><summary><SlidersHorizontal size={16}/>Więcej filtrów</summary><div><label>Typ<select value={filters.type} onChange={e => updateFilter('type',e.target.value)}><option value="all">Wszystkie</option><option value="ETF">ETF</option><option value="other">Pozostałe instrumenty</option></select></label><label>Sektor<select value={filters.sector} onChange={e => updateFilter('sector',e.target.value)}><option value="all">Wszystkie sektory</option>{[...new Set(items.map(item => item.sector || 'Nieprzypisany'))].sort().map(sector => <option key={sector}>{sector}</option>)}</select></label><label>Waluta<select value={filters.currency} onChange={e => updateFilter('currency',e.target.value)}><option value="all">Wszystkie waluty</option>{[...new Set(items.map(item => item.currency || 'Nieznana'))].sort().map(currency => <option key={currency}>{currency}</option>)}</select></label></div></details></div>
      <div className="rd-toolbar"><label>Sortuj <select aria-label="Sortowanie radaru" value={filters.sort} onChange={e => updateFilter('sort',e.target.value)}><option value="ticker">Symbol A–Z</option><option value="change_1d">Zmiana 1D ↓</option><option value="change_1m">Zmiana 1M ↓</option><option value="change_1y">Zmiana 1R ↓</option><option value="dividend_yield">Stopa dywidendy ↓</option></select></label><button className="rd-text-button" onClick={() => setFilters(initialFilters)}>Wyczyść filtry</button><button className="rd-text-button" onClick={() => {try {localStorage.setItem('radar-view-v1',JSON.stringify(filters));setSaved({...filters});setNotice('Zapisano filtry w tej przeglądarce.');} catch {setError('Przeglądarka nie pozwala zapisać filtrów.');}}}>Zapisz widok</button>{saved && <button className="rd-text-button" onClick={() => setFilters({...saved})}>Mój zapisany widok</button>}{view === 'list' && <label className="rd-check"><input type="checkbox" checked={dividends} onChange={e => setDividends(e.target.checked)}/>Kolumna dywidendy</label>}</div>
      {selected.length > 0 && <div className="rd-selection"><span>Porównaj {selected.length}/4</span>{selected.map(ticker => <button key={ticker} onClick={() => toggleSelection(ticker)} aria-label={`Usuń ${ticker} z porównania`}>{ticker}<X size={12}/></button>)}<button className="rd-text-button" onClick={() => setView('compare')}>Otwórz porównanie <ArrowUpRight size={14}/></button></div>}
      {view === 'list' && <>
        <div className="rd-table-wrap"><table className="rd-table"><thead><tr><th aria-label="Wybór do porównania"/><th>Instrument</th><th>Cena / 1D</th><th>Historia ceny</th><th>1M / 1R</th>{dividends && <th>Stopa dywidendy</th>}<th>Status</th><th>Obserwacja</th></tr></thead><tbody>{visible.map(item => {
          const status = dataStatus(item,now), target = targetReached(item,now);
          return <tr key={item.ticker}><td className="rd-select-cell"><input type="checkbox" aria-label={`Porównaj ${item.ticker}`} checked={selected.includes(item.ticker)} disabled={selected.length >= 4 && !selected.includes(item.ticker)} onChange={() => toggleSelection(item.ticker)}/></td><td className="rd-instrument"><button onClick={() => setDetail(item.ticker)}><span className="rd-avatar">{item.ticker.slice(0,2)}</span><span><strong>{item.ticker}</strong><small>{item.company_name !== item.ticker ? item.company_name : 'Nazwa niedostępna'}</small><em>{item.instrument_type === 'ETF' ? 'ETF · ' : ''}{item.quantity > 0 ? 'W portfelu' : 'Obserwowany'}</em></span></button></td><td data-label="Cena / 1D"><strong>{number(item.price)} <small>{item.currency || '?'}</small></strong><span className={tone(item.change_1d)}>{change(item.change_1d)}</span></td><td className="rd-history-cell" data-label="Ostatnie 30 zapisanych sesji"><Sparkline item={item}/></td><td data-label="1M / 1R"><strong className={tone(item.change_1m)}>{change(item.change_1m)}</strong><span className={tone(item.change_1y)}>{change(item.change_1y)} <small>1R</small></span></td>{dividends && <td data-label="Stopa dywidendy"><strong>{item.dividend_yield == null ? '—' : `${number(item.dividend_yield)}%`}</strong><small>Dane: {dateText(item.events_updated_at)}</small></td>}<td data-label="Dane"><span className={`rd-status rd-${status}`}>{status === 'missing' ? 'Brak ceny' : status === 'stale' ? 'Nieaktualne' : 'Zapis ≤ 72 h'}</span><small>{dateText(item.last_updated_at)}</small></td><td className="rd-row-actions" data-label="Obserwacja">{target ? <button className="rd-target" onClick={() => setDetail(item.ticker)}>Poziom osiągnięty</button> : item.notes?.review_date && item.notes.review_date <= localDate(new Date(now)) ? <button className="rd-target" onClick={() => setDetail(item.ticker)}>Czas na przegląd</button> : <button className="rd-text-button" onClick={() => setDetail(item.ticker)}>Szczegóły <ArrowUpRight size={14}/></button>}<div><button className="rd-icon" disabled={Boolean(busy)} aria-label={`Odśwież ${item.ticker}`} onClick={() => void refresh(item.ticker)}><RefreshCw size={15} className={busy === item.ticker || busy === 'all' ? 'rd-spin' : ''}/></button><button className={`rd-icon ${item.is_watched ? 'rd-bookmarked' : ''}`} aria-label={`${item.is_watched ? 'Przestań obserwować' : 'Obserwuj'} ${item.ticker}`} aria-pressed={item.is_watched} disabled={Boolean(busy)} onClick={() => void watch(item.ticker,item.is_watched)}><Bookmark size={15}/></button></div></td></tr>;
        })}</tbody></table></div>
        {!visible.length && <div className="rd-empty"><Search size={28}/><h3>{loading ? 'Ładowanie radaru…' : items.length ? 'Brak pasujących instrumentów' : 'Zbuduj swoją listę obserwacyjną'}</h3><p>{items.length ? 'Zmień filtry lub wyczyść wyszukiwanie.' : 'Dodaj symbol giełdowy. Posiadane instrumenty pojawią się automatycznie.'}</p></div>}
        <p className="rd-footnote">Zaznacz do 4 instrumentów do porównania. Miniwykres: do 30 zapisanych sesji; najedź, aby zobaczyć daty. „—” oznacza brak danych, „?” — nieznaną walutę. Status 72 h opisuje wiek zapisu, nie potwierdza notowania na żywo.</p>
      </>}
      {view === 'compare' && <div className="rd-comparison"><div className="rd-section-heading"><div><span className="rd-eyebrow">WSPÓLNY PUNKT STARTOWY</span><h2>Jak zachowują się Twoje pomysły?</h2><p>Procentowa zmiana ceny na wspólnych datach sesji.</p></div><div className="chart-toolbar"><select aria-label="Waluta porównania" value={quote} onChange={event => setQuote(event.target.value as 'native'|'PLN')}><option value="native">Waluty instrumentów</option><option value="PLN">W przeliczeniu na PLN</option></select><select aria-label="Okres porównania" value={days} onChange={e => setDays(Number(e.target.value))}><option value={30}>30 dni</option><option value={90}>3 miesiące</option><option value={365}>1 rok</option><option value={730}>2 lata</option></select></div></div>
        {selected.length < 2 ? <div className="rd-empty"><h3>Wybierz od 2 do 4 instrumentów</h3><p>Zaznacz pola przy instrumentach na liście. Wybór pozostaje po zmianie filtrów.</p><button className="rd-button" onClick={() => setView('list')}>Wróć do listy</button></div> : historyLoading ? <p className="rd-empty">Ładowanie historii…</p> : historyError ? <p className="rd-error" role="alert">{historyError}</p> : series.length < 2 ? <p className="rd-empty">Brak co najmniej dwóch wspólnych dat w zapisanych historiach. Wybierz dłuższy okres lub inne instrumenty. Historie uzupełnisz w widoku portfela.</p> : <><div className="rd-chart"><ResponsiveContainer width="100%" height={300}><LineChart data={series}><CartesianGrid stroke="var(--line)" vertical={false}/><XAxis dataKey="date" tickFormatter={dateText} minTickGap={60} tick={{fontSize:11}}/><YAxis tickFormatter={value => `${number(value,0)}%`} width={55} tick={{fontSize:11}}/><Tooltip contentStyle={chartTooltip} labelFormatter={label => dateText(String(label))} formatter={(value,name) => [change(Number(value)),name]}/><Legend/>{selected.map((ticker,index) => <Line key={ticker} dataKey={ticker} stroke={palette[index]} strokeWidth={2} dot={false} type="linear" isAnimationActive={false}/>)}</LineChart></ResponsiveContainer></div><p className="rd-help">{dateText(series[0].date)} – {dateText(series[series.length-1].date)} · {series.length} wspólnych obserwacji. {quote === 'PLN' ? 'Zmiana cen po przeliczeniu historycznymi kursami na PLN, bez osobnego doliczania dywidend.' : 'Zmiana zapisanych cen w walucie każdego instrumentu, bez osobnego doliczania dywidend i przeliczenia na PLN.'}{missingFx > 0 && quote === 'PLN' ? ` Pominięto ${missingFx} obserwacji bez kursu waluty.` : ''}</p></>}
        <div className="rd-compare-cards">{comparisonItems.map((item,index) => <article key={item.ticker} style={{borderTopColor:palette[index]}}><h3>{item.ticker}</h3><p>{item.company_name}</p><dl><div><dt>Cena</dt><dd>{number(item.price)} {item.currency || '?'}</dd></div><div><dt>Zmiana 1M</dt><dd className={tone(item.change_1m)}>{change(item.change_1m)}</dd></div><div><dt>Zmiana 1R</dt><dd className={tone(item.change_1y)}>{change(item.change_1y)}</dd></div><div><dt>Sektor</dt><dd>{item.sector || 'Nieprzypisany'}</dd></div><div><dt>Zapis notowania</dt><dd>{dateText(item.last_updated_at)}</dd></div><div><dt>Twój poziom</dt><dd>{number(item.notes?.target_price)} {item.notes?.target_price ? item.currency : ''}</dd></div></dl><button className="rd-text-button" onClick={() => setDetail(item.ticker)}>Otwórz szczegóły <ArrowUpRight size={14}/></button></article>)}</div>
      </div>}
      {view === 'calendar' && <div className="rd-calendar"><div className="rd-section-heading"><div><span className="rd-eyebrow">CO PRZED NAMI</span><h2>Kalendarz obserwacji</h2><p>Przyszłe terminy dla instrumentów pasujących do filtrów.</p></div></div>{relevantEvents.length ? relevantEvents.map(event => <button className="rd-event" key={`${event.ticker}-${event.kind}`} onClick={() => setDetail(event.ticker)}><span className="rd-event-date">{dateText(event.date)}</span><span><strong>{event.ticker}</strong><small>{event.kind}</small></span><span className="rd-help">{event.stale ? 'Termin do weryfikacji' : event.kind === 'Twój przegląd' ? 'Twoja notatka' : 'Termin od dostawcy'}<ArrowUpRight size={16}/></span></button>) : <div className="rd-empty"><CalendarDays size={30}/><h3>Brak nadchodzących terminów</h3><p>Minione daty nie są pokazywane jako przyszłe. Możesz dodać własną datę przeglądu w szczegółach instrumentu.</p></div>}<p className="rd-help">Terminy od dostawcy mogą być szacunkowe. Daty odcięcia dywidendy nie są datami wypłaty. Zaległe własne przeglądy znajdziesz w „Wymagają uwagi”.</p></div>}
    </section>
    {selectedItem && <RadarDetails key={selectedItem.ticker} item={selectedItem} onClose={() => setDetail(null)} onSaved={load} onAnalysis={() => {setAnalysis(selectedItem.ticker);setDetail(null);}}/>}
    {analysis && <StockProfilerModal ticker={analysis} isFund={items.find(item => item.ticker === analysis)?.instrument_type === 'ETF'} onClose={() => {setAnalysis(null);setDetail(analysis);}}/>}
  </div>;
}
