import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { chartsApi, type PerformanceMatrix } from '../../api_charts';
import { chartColors, chartDate, chartTooltip } from '../charts/chartTheme';
const months = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze', 'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru'];
import { monthlyPoints } from './performanceModel';
export default function PerformanceHeatmap({ portfolioId, data, from }: { portfolioId: number; data?: PerformanceMatrix; from?: string }) {
  const [matrix, setMatrix] = useState<PerformanceMatrix | null>(null);
  const [error, setError] = useState('');
  const [view, setView] = useState<'chart' | 'map'>('chart');
  useEffect(() => {
    if (data) return;
    let active = true;
    chartsApi.performance(portfolioId).then(result => { if (active) { setMatrix(result.matrix); setError(''); } }).catch(() => { if (active) setError('Nie udało się pobrać wyników.'); });
    return () => { active = false; };
  }, [portfolioId, data]);
  const source = data ?? matrix;
  const points = source ? monthlyPoints(source).filter(point => !from || point.date >= from.slice(0, 7)) : [];
  const currentMonth = new Date().toLocaleDateString('sv-SE').slice(0, 7);
  const format = (value: number | null | undefined) => value == null ? '—' : `${value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
  return <section className="chart-panel"><div className="chart-heading"><div><h2>Wyniki miesiąc po miesiącu</h2><p>Szacunek Modified Dietz: wpłaty i wypłaty ważone datą w miesiącu. Bieżący miesiąc jest niezamknięty.</p></div><div className="chart-toolbar"><button type="button" aria-pressed={view === 'chart'} onClick={() => setView('chart')}>Wykres</button><button type="button" aria-pressed={view === 'map'} onClick={() => setView('map')}>Mapa miesięcy</button></div></div>
    {error ? <p role="alert">{error}</p> : !source ? <p className="chart-empty">Ładowanie wyników…</p> : !points.length ? <p className="chart-empty">Brak wyników w tym okresie.</p> : view === 'chart' ? <ResponsiveContainer width="100%" height={270}><BarChart data={points}><CartesianGrid stroke={chartColors.grid} vertical={false} /><XAxis dataKey="date" tickFormatter={chartDate} minTickGap={45} tick={{ fill: chartColors.text, fontSize: 11 }} /><YAxis width={55} tickFormatter={value => `${Number(value).toFixed(0)}%`} tick={{ fill: chartColors.text, fontSize: 11 }} /><Tooltip contentStyle={chartTooltip} labelFormatter={label => `${chartDate(String(label))}${String(label) === currentMonth ? ' · miesiąc niezamknięty' : ''}`} formatter={value => [format(Number(value)), 'Szacowana stopa zwrotu']} /><ReferenceLine y={0} stroke={chartColors.muted} /><Bar dataKey="value" radius={[4, 4, 0, 0]} isAnimationActive={false}>{points.map(point => <Cell key={point.date} fill={(point.value ?? 0) < 0 ? chartColors.negative : chartColors.positive} fillOpacity={point.date === currentMonth ? .55 : 1} />)}</Bar></BarChart></ResponsiveContainer> : <div className="chart-table-wrap"><table className="chart-table"><thead><tr><th>Rok</th>{months.map(month => <th key={month}>{month}</th>)}<th>YTD</th></tr></thead><tbody>{Object.keys(source).sort().reverse().filter(year => points.some(point => point.date.startsWith(year))).map(year => <tr key={year}><th>{year}</th>{months.map((month, index) => { const date = `${year}-${String(index + 1).padStart(2, '0')}`; const value = from && date < from.slice(0, 7) ? undefined : source[year][String(index + 1)]; return <td key={month} title={`${date}${date === currentMonth ? ' · miesiąc niezamknięty' : ''}${value == null ? ' · brak danych' : ''}`} style={{ color: value == null ? chartColors.muted : value < 0 ? chartColors.negative : chartColors.positive }}>{format(value)}{date === currentMonth && <sup> *</sup>}</td>; })}<td title="Łączny wynik roku, niezależny od wybranego zakresu">{format(source[year].YTD)}</td></tr>)}</tbody></table></div>}
    <p className="chart-note">0,00% oznacza brak zmiany; — oznacza brak danych. YTD obejmuje dostępny okres całego roku. * Miesiąc niezamknięty.</p>
  </section>;
}
