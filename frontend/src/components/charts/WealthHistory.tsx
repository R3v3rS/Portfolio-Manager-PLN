import { useEffect, useState } from 'react';
import { chartsApi, type WealthPoint } from '../../api_charts';
import { TrendChart } from './ChartKit';
import { chartColors, chartMoney } from './chartTheme';
import { wealthRange, wealthRanges, type WealthRange } from './wealthRangeModel';
import './wealthHistory.css';
const dateLabel = (value: string) => new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(value + 'T12:00:00'));
export default function WealthHistory() {
  const [points, setPoints] = useState<WealthPoint[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<WealthRange>('ALL');
  useEffect(() => { let active = true; chartsApi.wealth().then(result => { if (active) setPoints(result.history); }).catch(() => { if (active) setError('Nie udało się pobrać historii majątku.'); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  const filtered = wealthRange(points, range, new Date().toLocaleDateString('sv-SE'));
  const visible = filtered.points;
  return <section className="chart-panel" aria-label="Historia majątku netto"><div className="chart-heading"><div><h2>Majątek netto w czasie</h2><p>Aktywa minus kredyty uwzględnione w majątku netto · PLN</p></div></div>
    <div className="wealth-range-selector" role="group" aria-label="Zakres historii majątku">{wealthRanges.map(r => <button key={r.key} type="button" aria-pressed={range === r.key} onClick={() => setRange(r.key)}>{r.label}</button>)}</div>
    {!loading && !error && <p className="chart-note" aria-live="polite">{filtered.from ? `Wybrany zakres: ${dateLabel(filtered.from)} – ${dateLabel(filtered.to)}.` : 'Wybrany zakres: cała dostępna historia.'}{filtered.firstAvailable && ` Historia jest dostępna od ${dateLabel(filtered.firstAvailable)}.`}{filtered.from && filtered.firstAvailable && filtered.firstAvailable > filtered.from && ' Dla wcześniejszych dat nie ma zapisanych stanów majątku.'}</p>}
    {loading ? <p className="chart-empty">Ładowanie historii…</p> : error ? <p role="alert" className="chart-alert">{error}</p> : visible.length < 2 ? <p className="chart-empty">{visible.length ? `Jeden zapis w tym zakresie: ${dateLabel(visible[0].date)} · ${chartMoney(visible[0].net_worth)}. Potrzeba co najmniej dwóch zapisów, aby pokazać trend.` : points.length ? 'Brak zapisów w wybranym zakresie. Wybierz szerszy zakres lub całą historię.' : 'Historia zacznie się od pierwszego zapisanego stanu Centrum finansów.'}</p> : <TrendChart data={visible} series={[{ key: 'net_worth', name: 'Majątek netto', area: true }, { key: 'total_assets', name: 'Aktywa', color: chartColors.secondary, dashed: true }, { key: 'total_liabilities', name: 'Dług uwzględniony w majątku', color: chartColors.muted, dashed: true }]} />}
    <p className="chart-note">Stan zapisuje się podczas otwierania pulpitu, najwyżej jeden punkt na dzień, aktualizowany przy kolejnej wizycie. Przeszłe salda nie są odtwarzane z dzisiejszych danych. Daty bez zapisów nie oznaczają zerowego majątku.</p></section>;
}
