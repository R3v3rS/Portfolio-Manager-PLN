import ManualPriceEditor from './ManualPriceEditor';
import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { TrendChart } from '../charts/ChartKit';

import { ArrowDownUp, ArrowUpRight, ChartNoAxesCombined, Search, SlidersHorizontal, X } from 'lucide-react';
import type { Holding, PortfolioValue } from '../../types';
import { exposure, filterPositions, finite, money, percent, positionKey, tone } from './researchModel';
import './portfolioResearch.css';

type HistoryPoint = { date: string; label: string; value: number };

export function PortfolioSummary({ value, closedProfit }: { value: PortfolioValue; closedProfit: number }) {
  const investedShare = finite(value.portfolio_value) && finite(value.holdings_value) && value.portfolio_value > 0 ? value.holdings_value / value.portfolio_value * 100 : null;
  return <section className="pr-summary" aria-label="Podsumowanie portfela">
    <div className="pr-total"><span className="pr-eyebrow">TWÓJ PORTFEL · PLN</span><h2>{value.portfolio_value==null&&finite(value.estimated_portfolio_value)?'Wartość orientacyjna portfela':'Wartość portfela'}</h2><strong>{money(value.portfolio_value??value.estimated_portfolio_value)}</strong>{(value.reference_positions_count??0)>0&&<p className="pr-reference-note">Pozycje z ceną ręczną lub bez notowań: {value.reference_positions_count}. Koszt zakupu nie jest aktualnym kursem.</p>}
      <div className="pr-capital-bar" role="img" aria-label={`Udział inwestycji ${percent(investedShare)}`}><span style={{ width: `${Math.min(100, Math.max(0, investedShare ?? 0))}%` }} /></div>
      <div className="pr-capital-labels"><span><i /> Inwestycje <b>{money(value.holdings_value)}</b></span><span><i /> Gotówka <b>{money(value.cash_value)}</b></span></div>
    </div>
    <div className="pr-total-result"><span className="pr-eyebrow">OD POCZĄTKU INWESTOWANIA</span><h2>Łączny wynik</h2><strong className={tone(value.total_result)}>{finite(value.total_result) && value.total_result > 0 ? '+' : ''}{money(value.total_result)}</strong><div className="pr-return"><span>Zwrot prosty <b className={tone(value.total_result_percent)}>{percent(value.total_result_percent)}</b></span><span title="Roczna stopa zwrotu uwzględniająca daty wpłat i wypłat">XIRR rocznie <b>{percent(value.xirr_percent)}</b></span></div>
      <details className="pr-result-details"><summary>Skąd pochodzi wynik?</summary><dl>{([['Otwarte pozycje', value.open_positions_result], ['Zamknięte pozycje', closedProfit], ['Dywidendy', value.total_dividends], ['Odsetki', value.total_interest ?? 0]] as const).map(([label, amount]) => <div key={label}><dt>{label}</dt><dd className={tone(amount)}>{money(amount)}</dd></div>)}</dl></details>
    </div>
  </section>;
}

interface Props {
  holdings: Holding[];
  value: PortfolioValue;
  history: HistoryPoint[];
  profitHistory: HistoryPoint[];
  dailyHistory: HistoryPoint[];
  dailyProfit: HistoryPoint[];
  onHistory: (ticker: string) => void;
  onSell: (holding: Holding) => void;
  onClose: (holding: Holding) => void;
  onRisk: () => void;
  onResults?: () => void;
  onInstrument?: (ticker:string)=>void;
  onRefresh?: () => Promise<void>;
}

export default function PortfolioResearch({ holdings, value, history, profitHistory, dailyHistory, dailyProfit, onHistory, onSell, onClose, onRisk, onResults, onRefresh,onInstrument }: Props) {
  const [manualHolding,setManualHolding]=useState<Holding|null>(null);
  const [period, setPeriod] = useState('all');
  const [metric, setMetric] = useState<'value' | 'profit'>('value');
  const [query, setQuery] = useState('');
  const [sector, setSector] = useState('all');
  const [result, setResult] = useState('all');
  const [sort, setSort] = useState('value');
  const [selected, setSelected] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [rankMetric, setRankMetric] = useState<'value' | 'profit'>('value');
  const comparisonRef = useRef<HTMLElement>(null);
  const positions = holdings.filter(h => h.quantity > 0);
  const instrumentExposure = exposure(positions);
  const pricesComplete = positions.every(h => finite(h.current_value));
  const top3 = pricesComplete ? instrumentExposure.slice(0, 3).reduce((sum, h) => sum + h.weight, 0) : null;
  const equityValue = positions.reduce((sum, h) => sum + (finite(h.current_value) ? h.current_value : 0), 0);
  const weight = (h: Holding) => pricesComplete && finite(h.current_value) && equityValue > 0 ? h.current_value / equityValue * 100 : null;
  const winners = positions.filter(h => finite(h.profit_loss) && h.profit_loss > 0).length;
  const losers = positions.filter(h => finite(h.profit_loss) && h.profit_loss < 0).length;
  const source = period === '30d' ? (metric === 'value' ? dailyHistory : dailyProfit) : (metric === 'value' ? history : profitHistory);
  const sortedHistory = [...source].filter(p => Number.isFinite(Date.parse(p.date))).sort((a, b) => a.date.localeCompare(b.date));
  const endDate = sortedHistory.length ? new Date(sortedHistory[sortedHistory.length - 1].date) : null;
  const cutoff = endDate ? new Date(endDate) : null;
  if (cutoff && (period === '6m' || period === '1y')) cutoff.setUTCMonth(cutoff.getUTCMonth() - (period === '6m' ? 6 : 12));
  const points = sortedHistory.filter(p => period === 'all' || period === '30d' || !cutoff || new Date(p.date) >= cutoff);
  const change = points.length > 1 ? points[points.length - 1].value - points[0].value : null;
  const rows = filterPositions(positions, query, sector, result).sort((a, b) => {
    if (sort === 'name') return a.ticker.localeCompare(b.ticker);
    const field = sort === 'daily' ? 'change_1d_percent' : sort === 'return' ? 'profit_loss_percent' : sort === 'profit' || sort === 'loss' ? 'profit_loss' : 'current_value';
    const aVal = a[field]; const bVal = b[field];
    if (!finite(aVal)) return finite(bVal) ? 1 : 0;
    if (!finite(bVal)) return -1;
    return sort === 'loss' ? aVal - bVal : bVal - aVal;
  });
  const filteredValue = rows.some(h => !finite(h.current_value)) ? null : rows.reduce((sum, h) => sum + (h.current_value ?? 0), 0);
  const filteredProfit = rows.some(h => !finite(h.profit_loss)) ? null : rows.reduce((sum, h) => sum + (h.profit_loss ?? 0), 0);
  const comparison = positions.filter(h => selected.includes(positionKey(h)));
  const ranking = [...rows].filter(h => finite(rankMetric === 'value' ? h.current_value : h.profit_loss)).sort((a, b) => rankMetric === 'value' ? (b.current_value ?? 0) - (a.current_value ?? 0) : Math.abs(b.profit_loss ?? 0) - Math.abs(a.profit_loss ?? 0)).slice(0, 5);
  const rankMax = Math.max(1, ...ranking.map(h => Math.abs((rankMetric === 'value' ? h.current_value : h.profit_loss) ?? 0)));
  const toggleComparison = (key: string) => setSelected(prev => prev.includes(key) ? prev.filter(p => p !== key) : prev.length < 3 ? [...prev, key] : prev);

  return <div className="pr-workspace">
    <div className="pr-signal-grid">
      <div className="pr-signal"><span>Otwarte pozycje · wynik</span><strong className={tone(value.open_positions_result)}>{money(value.open_positions_result)}</strong><small>{winners} na plusie · {losers} na minusie</small></div>
      <div className="pr-signal"><span>Trzy największe instrumenty</span><strong>{instrumentExposure.length ? percent(top3) : '—'}</strong><small>udział w części akcyjnej</small></div>
      <div className="pr-signal"><span>Dochód z dywidend</span><strong>{money(value.total_dividends)}</strong><small>otrzymany od początku portfela</small></div>
      <button className="pr-signal pr-risk-link" onClick={onRisk}><ChartNoAxesCombined size={20} /><strong>Sprawdź ryzyko <ArrowUpRight size={18} /></strong><small>Sharpe, obsunięcie i VaR</small></button>
    </div>

    <section className="pr-panel pr-history">
      <div className="pr-section-head"><div><p className="pr-eyebrow">PERSPEKTYWA W CZASIE</p><h2>Jak zmienia się portfel?</h2></div><div className="pr-segment" aria-label="Miara na wykresie">{([['value', 'Wartość'], ['profit', 'Zysk / strata']] as const).map(([key, label]) => <button key={key} aria-pressed={metric === key} onClick={() => setMetric(key)}>{label}</button>)}</div></div>
      <div className="pr-chart-toolbar"><div><strong className={tone(change)}>{finite(change) && change > 0 ? '+' : ''}{money(change)}</strong><span>zmiana {metric === 'value' ? 'wartości' : 'skumulowanego wyniku'} w wybranym okresie</span></div><div className="pr-segment" aria-label="Okres historii">{[['30d', '30 dni'], ['6m', '6 mies.'], ['1y', 'Rok'], ['all', 'Całość']].map(([key, label]) => <button key={key} aria-pressed={period === key} onClick={() => setPeriod(key)}>{label}</button>)}</div></div>
      {points.length > 1 ? <TrendChart data={points.map(point => ({ ...point, value: finite(point.value) ? point.value : null }))} series={[{ key: 'value', name: metric === 'value' ? 'Wartość portfela' : 'Skumulowany wynik', area: true }]} zero={metric === 'profit'} height={220} /> : <div className="pr-empty">Za mało punktów historii dla tego okresu. Wybierz szerszy zakres.</div>}
      {onResults && <button type="button" className="pr-text-button" onClick={onResults}>Pełna analiza wyników i benchmark <ArrowUpRight size={15} /></button>}
      <div className="pr-chart-note"><span>{points.length ? `${new Date(points[0].date).toLocaleDateString('pl-PL')} – ${new Date(points[points.length - 1].date).toLocaleDateString('pl-PL')}` : 'Brak historii'} · {points.length} obserwacji</span><span>{metric === 'value' ? 'Wartość obejmuje gotówkę, wpłaty i wypłaty — jej zmiana nie jest stopą zwrotu.' : 'Wynik w PLN od początku inwestowania; nie jest roczną stopą zwrotu.'}</span></div>
    </section>

    <section className="pr-panel" aria-label="Analizator pozycji">
      <div className="pr-section-head"><div><p className="pr-eyebrow">TWÓJ WARSZTAT ANALITYCZNY</p><h2>Przeanalizuj pozycje</h2><p>Filtruj, porównuj i sprawdzaj, które instrumenty budują wynik.</p></div><SlidersHorizontal size={20} /></div>
      <div className="pr-filters"><label className="pr-search"><Search size={17} /><input type="search" aria-label="Szukaj pozycji" placeholder="Spółka, symbol lub sektor" value={query} onChange={e => setQuery(e.target.value)} /></label><label>Sektor<select aria-label="Filtr sektora" value={sector} onChange={e => setSector(e.target.value)}><option value="all">Wszystkie sektory</option>{[...new Set(positions.map(h => h.sector || 'Unknown'))].sort().map(s => <option key={s} value={s}>{s === 'Unknown' ? 'Nieprzypisany' : s}</option>)}</select></label><label>Wynik pozycji<select aria-label="Filtr wyniku" value={result} onChange={e => setResult(e.target.value)}><option value="all">Wszystkie</option><option value="positive">Na plusie</option><option value="negative">Na minusie</option></select></label><label>Sortowanie<select aria-label="Sortowanie pozycji" value={sort} onChange={e => setSort(e.target.value)}><option value="value">Wartość ↓</option><option value="profit">Zysk w PLN ↓</option><option value="loss">Największa strata</option><option value="return">Zwrot w % ↓</option><option value="daily">Zmiana 1D ↓</option><option value="name">Symbol A–Z</option></select></label></div>
      <div className="pr-filter-summary" aria-live="polite"><span><b>{rows.length}</b> z {positions.length} pozycji</span><span>Wartość wyboru <b>{money(filteredValue)}</b></span><span>Wynik wyboru <b className={tone(filteredProfit)}>{money(filteredProfit)}</b></span>{comparison.length > 0 && <button onClick={() => comparisonRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })}>Porównaj wybrane ({comparison.length}/3) <ArrowUpRight size={14} /></button>}{(query || sector !== 'all' || result !== 'all') && <button onClick={() => { setQuery(''); setSector('all'); setResult('all'); }}>Wyczyść filtry <X size={14} /></button>}</div>
      <div className="pr-table-scroll"><table className="pr-position-table"><thead><tr><th><span title="Zaznacz do trzech pozycji do porównania">Porównaj</span></th><th>Instrument</th><th>Wartość / udział¹</th><th>Wynik otwarty</th><th>Zwrot</th><th>Zmiana 1D</th><th>Operacje</th></tr></thead><tbody>{rows.map(h => <tr key={positionKey(h)} className={[selected.includes(positionKey(h))?'pr-selected':'',h.price_basis==='purchase'||h.price_basis==='manual'?'pr-reference-position':''].join(' ')}><td><input type="checkbox" aria-label={`Porównaj ${h.ticker}`} checked={selected.includes(positionKey(h))} disabled={selected.length >= 3 && !selected.includes(positionKey(h))} onChange={() => toggleComparison(positionKey(h))} /></td><td><button className="pr-instrument" aria-expanded={expanded === positionKey(h)} onClick={() => setExpanded(expanded === positionKey(h) ? null : positionKey(h))}><span className="pr-monogram">{h.ticker.slice(0, 2)}</span><span><b>{h.ticker}</b><small title={h.company_name}>{h.company_name || 'Szczegóły instrumentu'}</small>{h.valuation_status && h.valuation_status !== 'ok' && <small className="text-amber-300">{h.price_basis==='purchase'?'Bez notowań · według kosztu zakupu':h.price_basis==='manual'?`Cena ręczna · ${h.price_last_updated_at??'bez daty'}`:h.valuation_status==='incomplete'?'Niepełna wycena':'Nieaktualne notowanie'}</small>}</span></button></td><td><b>{money(h.current_value??h.estimated_current_value)}</b><small>{h.price_basis==='purchase'?'Wartość orientacyjna':percent(weight(h))}</small></td><td className={tone(h.profit_loss)}><b>{money(h.profit_loss)}</b></td><td className={tone(h.profit_loss_percent)}>{percent(h.profit_loss_percent)}</td><td className={tone(h.change_1d_percent)}>{finite(h.change_1d_percent) && h.change_1d_percent > 0 ? '+' : ''}{percent(h.change_1d_percent)}</td><td>{onRefresh&&<button className="pr-text-button" onClick={()=>setManualHolding(h)}>{h.price_basis==='manual'?'Zmień cenę ręczną':'Wpisz cenę ręcznie'}</button>}<button className="pr-text-button" onClick={() => onSell(h)}>Sprzedaj</button><details className="pr-more"><summary aria-label={`Więcej operacji ${h.ticker}`}>•••</summary><button disabled={h.price_basis==='purchase'||h.price_basis==='manual'||!finite(h.current_price)} onClick={() => onClose(h)}>Zamknij po ostatniej cenie</button></details></td></tr>)}</tbody></table></div>
      {!rows.length && <div className="pr-empty">Brak pozycji spełniających wybrane warunki.</div>}
      <p className="pr-footnote">¹ Udział w wartości otwartych pozycji, bez gotówki. Kliknij symbol, aby zobaczyć szczegóły. Zaznacz maksymalnie 3 pozycje do porównania. „—” oznacza brak danych.</p>
      {positions.filter(h => positionKey(h) === expanded).map(h => <div key={positionKey(h)} className="pr-position-detail"><div className="pr-section-head"><h3>{h.company_name || h.ticker}</h3><button className="pr-text-button" onClick={() => setExpanded(null)} aria-label="Zamknij szczegóły pozycji"><X size={18} /></button></div><dl className="pr-detail-grid">{[['Liczba jednostek', h.quantity.toLocaleString('pl-PL', { maximumFractionDigits: 6 })], ['Cena rynkowa', finite(h.current_price) ? `${h.current_price.toLocaleString('pl-PL')} ${h.currency || 'PLN'}` : '—'], ['Średnia cena zakupu', money(h.average_buy_price)], ['Cena wyjścia na zero', money(h.break_even_sell_price_pln)], ['Wynik zrealizowany', money(h.realized_profit)], ['Sektor', h.sector || 'Nieprzypisany']].map(([label, text]) => <div key={label}><dt>{label}</dt><dd>{text}</dd></div>)}</dl>{h.auto_fx_fees && <p className="pr-footnote">Wynik uwzględnia szacowaną prowizję walutową 0,5% przy sprzedaży.</p>}{onInstrument&&<button className="pr-button" onClick={()=>onInstrument(h.ticker)}>Historia operacji spółki</button>}<button className="pr-button" onClick={() => onHistory(h.ticker)}>Pokaż historię ceny <ArrowUpRight size={16} /></button></div>)}
    </section>

    {comparison.length > 0 && <section ref={comparisonRef} className="pr-panel" aria-label="Porównanie pozycji"><div className="pr-section-head"><div><p className="pr-eyebrow">OBOK SIEBIE</p><h2>Porównanie pozycji · {comparison.length}/3</h2><p>Bieżące pozycje i ich wynik od zakupu. Okres posiadania może się różnić.</p></div><button className="pr-text-button" onClick={() => setSelected([])}>Wyczyść <X size={14} /></button></div><div className="pr-comparison-grid">{comparison.map(h => <article key={positionKey(h)}><div className="pr-section-head"><h3>{h.ticker}</h3><button className="pr-text-button" aria-label={`Usuń ${h.ticker} z porównania`} onClick={() => toggleComparison(positionKey(h))}><X size={16} /></button></div><strong className={tone(h.profit_loss_percent)}>{percent(h.profit_loss_percent)}</strong><span>zwrot otwartej pozycji</span><dl>{[['Wynik w PLN', money(h.profit_loss)], ['Wartość', money(h.current_value)], ['Udział w akcjach', percent(weight(h))], ['Zmiana 1D', percent(h.change_1d_percent)]].map(([label, text]) => <div key={label}><dt>{label}</dt><dd>{text}</dd></div>)}</dl></article>)}</div></section>}

    <div className="pr-bottom-grid"><section className="pr-panel"><div className="pr-section-head"><div><p className="pr-eyebrow">DLA WYBRANYCH FILTRÓW</p><h2>{rankMetric === 'value' ? 'Największe pozycje' : 'Wpływ na wynik otwarty'}</h2></div><button className="pr-button" onClick={() => setRankMetric(rankMetric === 'value' ? 'profit' : 'value')}><ArrowDownUp size={15} />{rankMetric === 'value' ? 'Pokaż wynik' : 'Pokaż wartość'}</button></div><div className="pr-ranking">{ranking.map(h => { const amount = (rankMetric === 'value' ? h.current_value : h.profit_loss) ?? 0; return <button key={positionKey(h)} onClick={() => setQuery(h.ticker)} title={`Filtruj ${h.ticker}`}><span>{h.ticker}<b className={rankMetric === 'profit' ? tone(amount) : ''}>{money(amount)}</b></span><span className="pr-rank-track"><i style={{ width: `${Math.abs(amount) / rankMax * 100}%`, background: rankMetric === 'profit' && amount < 0 ? 'var(--pr-red)' : rankMetric === 'profit' ? 'var(--pr-green)' : '#3b82f6' }} /></span></button>; })}{!ranking.length && <p className="pr-empty">Brak danych dla tego wyboru.</p>}</div><p className="pr-footnote">{rankMetric === 'value' ? 'Pięć największych pozycji według wartości.' : 'Pięć największych zysków i strat według kwoty bezwzględnej.'} Kliknij wiersz, aby zawęzić tabelę.</p></section>
    <section className="pr-panel"><div className="pr-section-head"><div><p className="pr-eyebrow">ORGANIZACJA INWESTYCJI</p><h2>Podział portfela</h2></div></div><div className="pr-subportfolios">{value.breakdown?.length ? value.breakdown.map(item => <Link key={item.id} to={`/portfolio/${item.id}`}><span><b>{item.name.replace(' (Own)', ' · część główna')}</b><small>{percent(item.share_pct)} portfela</small></span><strong>{money(item.value)}</strong><ArrowUpRight size={16} /></Link>) : <p className="pr-footnote">Ten portfel nie ma sub-portfeli. Wszystkie pozycje analizujesz wspólnie.</p>}</div><div className="pr-context"><span>Największy instrument</span><b>{instrumentExposure[0]?.ticker ?? '—'} · {percent(pricesComplete ? instrumentExposure[0]?.weight : null)}</b><small>Udział w części akcyjnej, łącznie we wszystkich sub-portfelach.</small></div></section></div>
    {manualHolding&&onRefresh&&<ManualPriceEditor holding={manualHolding} onClose={()=>setManualHolding(null)} onSaved={onRefresh}/>}
  </div>;
}
