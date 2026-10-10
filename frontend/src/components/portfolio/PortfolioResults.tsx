import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { PortfolioHistoryPoint } from '../../api';
import { chartsApi, type Attribution, type PerformanceMatrix } from '../../api_charts';
import { TrendChart } from '../charts/ChartKit';
import { chartColors, chartMoney, chartTooltip } from '../charts/chartTheme';
import PerformanceHeatmap from './PerformanceHeatmap';
import { monthlyPoints } from './performanceModel';
import ActualResultsPanel from './ActualResultsPanel';

const benchmarks = [['', 'Bez porównania'], ['__INFLATION__', 'Inflacja PL'], ['^GSPC', 'S&P 500'], ['ETFBW20TR.WA', 'WIG20 TR'], ['ETFBM40TR.WA', 'mWIG40 TR'], ['VT', 'Cały świat VT'], ['EEM', 'Rynki wschodzące'], ['^STOXX', 'STOXX 600']];
export default function PortfolioResults({ portfolioId, history, benchmark, onBenchmark, dailyProfit }: {
  portfolioId: number; history: PortfolioHistoryPoint[]; benchmark: string; onBenchmark: (value: string) => void; dailyProfit: PortfolioHistoryPoint[];
}) {
  const [period, setPeriod] = useState('all');
  const [metric, setMetric] = useState<'value' | 'profit' | 'return'>('value');
  const [matrix, setMatrix] = useState<PerformanceMatrix>();
  const [attribution, setAttribution] = useState<Attribution>();
  const [error, setError] = useState('');
  const [attributionError, setAttributionError] = useState('');
  const [showAllContributors, setShowAllContributors] = useState(false);
  const [showDaily, setShowDaily] = useState(false);
  const today = new Date().toLocaleDateString('sv-SE');
  const cutoff = new Date(today + 'T12:00:00');
  cutoff.setDate(1);
  if (period !== 'all') cutoff.setMonth(cutoff.getMonth() - (Number(period) - 1));
  const from = period === 'all' ? (history[0]?.date ?? today.slice(0, 7)) + '-01' : cutoff.toLocaleDateString('sv-SE');
  const points = history.filter(point => point.date >= from.slice(0, 7));
  useEffect(() => {
    let active = true;
    setMatrix(undefined); setError('');
    chartsApi.performance(portfolioId).then(result => { if (active) setMatrix(result.matrix); }).catch(() => { if (active) setError('Nie udało się wczytać miesięcznych wyników.'); });
    return () => { active = false; };
  }, [portfolioId]);
  useEffect(() => {
    let active = true;
    setAttribution(undefined); setAttributionError('');
    chartsApi.attribution(portfolioId, from, today).then(result => { if (active) setAttribution(result); }).catch(() => { if (active) setAttributionError('Nie udało się wczytać wkładu instrumentów.'); });
    return () => { active = false; };
  }, [portfolioId, from, today]);
  let cumulative: number | null = 1;
  const returns = monthlyPoints(matrix ?? {}).filter(point => point.date >= from.slice(0, 7)).map(point => {
    cumulative = point.value == null || cumulative == null ? null : cumulative * (1 + point.value / 100);
    return { date: point.date, value: cumulative == null ? null : (cumulative - 1) * 100 };
  });
  const values = points.map(point => ({ ...point, value: Number.isFinite(point.value) ? metric === 'profit' ? point.value - (point.net_contributions ?? 0) : point.value : null }));
  const series = metric === 'return' ? [{ key: 'value', name: 'Szacowana stopa zwrotu', area: true }] : metric === 'profit' ? [{ key: 'value', name: 'Skumulowany zysk / strata', area: true }] : [
    { key: 'value', name: 'Wartość portfela' },
    { key: 'net_contributions', name: 'Wpłaty netto', color: chartColors.muted, dashed: true },
    ...(benchmark ? [{ key: 'benchmark_value', name: benchmarks.find(item => item[0] === benchmark)?.[1] ?? benchmark, color: chartColors.secondary, dashed: true }] : []),
  ];
  const daily = dailyProfit.map((point, index) => ({ date: point.date, value: index && Number.isFinite(point.value) && Number.isFinite(dailyProfit[index - 1].value) ? point.value - dailyProfit[index - 1].value : null }));
  const contributors = attribution?.items ?? [];
  const tail = contributors.slice(8);
  const positiveTail = tail.filter(item => item.value >= 0).reduce((sum, item) => sum + item.value, 0);
  const negativeTail = tail.filter(item => item.value < 0).reduce((sum, item) => sum + item.value, 0);
  const visibleContributors = showAllContributors || contributors.length <= 10 ? contributors : [...contributors.slice(0, 8),
    ...(positiveTail ? [{ ticker: 'Pozostałe zyski', value: positiveTail, dividends: 0 }] : []),
    ...(negativeTail ? [{ ticker: 'Pozostałe straty', value: negativeTail, dividends: 0 }] : []),
  ];
  return <div className="space-y-5"><section className="chart-panel"><div className="chart-heading"><div><h2>Wyniki portfela</h2><p>{from} – {today} · miesięczne wyceny · PLN</p></div><div className="chart-toolbar"><label>Okres<select aria-label="Okres wyników" value={period} onChange={event => setPeriod(event.target.value)}><option value="3">3 miesiące</option><option value="6">6 miesięcy</option><option value="12">1 rok</option><option value="all">Cała historia</option></select></label></div></div>
    <div className="chart-heading"><div className="chart-toolbar">{([['value', 'Wartość PLN'], ['profit', 'Zysk / strata PLN'], ['return', 'Stopa zwrotu %']] as const).map(([key, label]) => <button key={key} aria-pressed={metric === key} type="button" onClick={() => setMetric(key)}>{label}</button>)}</div>{metric === 'value' && <div className="chart-toolbar"><select aria-label="Benchmark wyników" value={benchmark} onChange={event => onBenchmark(event.target.value)}>{benchmarks.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>}</div>
    {points.some(point => !Number.isFinite(point.value)) && <p className="chart-alert">Historia zawiera niepełne wyceny. Brakujące ceny i kursy walut są pokazane jako przerwy.</p>}
    {metric === 'return' && returns.some(point => point.value === null) && <p className="chart-alert">Pełna stopa zwrotu za ten okres jest niedostępna z powodu brakujących wycen lub zerowej podstawy. Wybierz krótszy okres.</p>}
    <TrendChart data={metric === 'return' ? returns : values} series={series} unit={metric === 'return' ? '%' : 'PLN'} zero={metric !== 'value'} height={330} />
    <p className="chart-note">{metric === 'return' ? 'Szacowany wynik łączony z miesięcznych stóp Modified Dietz, z uwzględnieniem dat wpłat i wypłat. Nie jest to dokładna dzienna stopa TWR.' : metric === 'profit' ? 'Poziom łącznego zysku: wycena pomniejszona o wpłaty netto. Zmiana zysku w PLN jest dostępna niżej.' : 'Wartość zawiera wpływ wpłat i wypłat. Benchmark w PLN symuluje te same przepływy; porównuje zapisane ceny bez osobnego doliczania dywidend.'}</p>
  </section><ActualResultsPanel portfolioId={portfolioId} from={from} />{error ? <p role="alert" className="chart-alert">{error}</p> : matrix && <PerformanceHeatmap portfolioId={portfolioId} data={matrix} from={from} />}
  <section className="chart-panel"><div className="chart-heading"><div><h2>Co tworzy wynik tego okresu?</h2><p>Zmiana wartości pozycji + wpływy ze sprzedaży − koszty zakupów + zaksięgowane dywidendy · PLN</p></div></div>
    {attributionError ? <p role="alert" className="chart-alert">{attributionError}</p> : !attribution ? <p className="chart-empty">Ładowanie wkładu instrumentów…</p> : attribution.items.length ? <><ResponsiveContainer width="100%" height={Math.max(220, visibleContributors.length * 34)}><BarChart data={visibleContributors} layout="vertical" margin={{ left: 0, right: 15 }}><CartesianGrid stroke={chartColors.grid} horizontal={false} /><XAxis type="number" tick={{ fill: chartColors.text, fontSize: 11 }} tickFormatter={value => new Intl.NumberFormat('pl-PL', { notation: 'compact' }).format(Number(value))} /><YAxis type="category" dataKey="ticker" width={115} tick={{ fill: chartColors.text, fontSize: 11 }} /><Tooltip contentStyle={chartTooltip} formatter={value => [chartMoney(Number(value)), 'Wkład w wynik']} /><ReferenceLine x={0} stroke={chartColors.muted} /><Bar dataKey="value" radius={4} isAnimationActive={false}>{visibleContributors.map(item => <Cell key={item.ticker} fill={item.value < 0 ? chartColors.negative : chartColors.positive} />)}</Bar></BarChart></ResponsiveContainer><details><summary className="chart-note">Dokładne wartości ({attribution.items.length} instrumentów)</summary><div className="chart-table-wrap"><table className="chart-table"><thead><tr><th>Instrument</th><th>Wkład w wynik</th><th>W tym dywidendy</th></tr></thead><tbody>{attribution.items.map(item => <tr key={item.ticker}><th>{item.ticker}</th><td>{chartMoney(item.value)}</td><td>{chartMoney(item.dividends)}</td></tr>)}</tbody></table></div></details></> : <p className="chart-empty">{attribution.status === 'unsupported_account' ? 'Ten typ konta ma odrębną metodę analizy.' : 'Brak instrumentów z pełną wyceną w tym okresie.'}</p>}
    {contributors.length > 10 && <div className="chart-actions"><button type="button" onClick={() => setShowAllContributors(!showAllContributors)}>{showAllContributors ? 'Pokaż 8 największych wkładów' : `Pokaż wszystkie (${contributors.length})`}</button></div>}
    {!!attribution?.missing_tickers?.length && <p className="chart-alert">Pominięto z powodu braku wyceny: {attribution.missing_tickers.join(', ')}.</p>}
    <p className="chart-note">Obejmuje także pozycje zamknięte w okresie. Kwoty transakcji uwzględniają zaksięgowane koszty, a wycena stosuje tę samą opłatę walutową co historia portfela. Odsetki gotówki i nieprzypisane operacje nie są przypisane do instrumentów.</p>
  </section><div className="chart-actions"><button type="button" aria-expanded={showDaily} onClick={() => setShowDaily(!showDaily)}>{showDaily ? 'Ukryj' : 'Pokaż'} dzienną zmianę zysku (30 dni)</button></div>{showDaily && <section className="chart-panel"><div className="chart-heading"><div><h2>Dzienna zmiana zysku</h2><p>Różnica skumulowanego wyniku między kolejnymi dniami · PLN</p></div></div><TrendChart data={daily} series={[{ key: 'value', name: 'Zmiana zysku', area: true }]} zero /></section>}</div>;
}
