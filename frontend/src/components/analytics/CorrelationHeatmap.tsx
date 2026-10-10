import { useState } from 'react';
import { chartColors } from '../charts/chartTheme';
type Row = Record<string, string | number | null>;
const label = (row: Row) => String(row.symbol ?? row.asset ?? row.name ?? row.label ?? '');
export default function CorrelationHeatmap({ rows, period }: { rows: Row[]; period: string }) {
  const columns = Array.from(new Set(rows.flatMap(row => Object.keys(row).filter(key => !['name', 'asset', 'label', 'symbol'].includes(key)))));
  const [selected, setSelected] = useState<string[] | null>(null);
  const visible = (selected ?? columns.slice(0, 6)).filter(key => columns.includes(key));
  const toggle = (key: string) => setSelected(visible.includes(key) ? visible.filter(item => item !== key) : [...visible, key]);
  const color = (value: number | null, diagonal: boolean) => value == null || diagonal ? '#22363f' : `hsl(${value < 0 ? 190 : 330} ${Math.round(Math.abs(value) * 32 + 10)}% ${Math.round(17 + Math.abs(value) * 17)}%)`;
  return <section className="chart-panel"><div className="chart-heading"><div><h2>Które instrumenty poruszają się razem?</h2><p>Korelacja zmian cen w walutach notowania · okres {period} · zależność od −1 do +1</p></div><div className="chart-toolbar"><button type="button" onClick={() => setSelected(columns)}>Pełna macierz</button><button type="button" onClick={() => setSelected(null)}>Pierwsze 6</button></div></div>
    <div className="chart-selection" aria-label="Instrumenty w macierzy">{columns.map(key => <label key={key}><input type="checkbox" checked={visible.includes(key)} onChange={() => toggle(key)} />{key}</label>)}</div>
    {visible.length < 2 ? <p className="chart-empty">Wybierz co najmniej dwa instrumenty z dostępną historią.</p> : <div className="chart-table-wrap"><table className="chart-table"><thead><tr><th>Instrument</th>{visible.map(key => <th key={key}>{key}</th>)}</tr></thead><tbody>{rows.filter(row => visible.includes(label(row))).map(row => <tr key={label(row)}><th>{label(row)}</th>{visible.map(key => { const raw = row[key]; const value = raw == null || !Number.isFinite(Number(raw)) ? null : Number(raw); const diagonal = key === label(row); return <td key={key} className="correlation-cell" style={{ backgroundColor: color(value, diagonal), color: diagonal ? chartColors.muted : '#edf7fa' }} title={`${label(row)} / ${key}: ${value == null ? 'brak danych' : value.toFixed(2)}`}>{value == null ? '—' : diagonal ? '1,00' : value.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>; })}</tr>)}</tbody></table></div>}
    <div className="correlation-scale" /><p className="chart-note">−1: przeciwny kierunek · 0: słaba zależność liniowa · +1: ten sam kierunek. Kolor pokazuje siłę, nie ocenę inwestycji. — oznacza brak wystarczających wspólnych danych.</p>
  </section>;
}
