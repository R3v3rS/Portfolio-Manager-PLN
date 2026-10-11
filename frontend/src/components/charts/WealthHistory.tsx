import { useEffect, useState } from 'react';
import { chartsApi, type WealthPoint } from '../../api_charts';
import { TrendChart } from './ChartKit';
import { chartColors, chartMoney } from './chartTheme';
export default function WealthHistory() {
  const [points, setPoints] = useState<WealthPoint[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => { let active = true; chartsApi.wealth().then(result => { if (active) setPoints(result.history); }).catch(() => { if (active) setError('Nie udało się pobrać historii majątku.'); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  return <section className="chart-panel"><div className="chart-heading"><div><h2>Majątek netto w czasie</h2><p>Aktywa minus kredyty uwzględnione w majątku netto · PLN</p></div></div>{loading ? <p className="chart-empty">Ładowanie historii…</p> : error ? <p role="alert" className="chart-alert">{error}</p> : points.length < 2 ? <p className="chart-empty">{points.length ? `Pierwszy zapis: ${points[0].date} · ${chartMoney(points[0].net_worth)}. Kolejny dzień z zapisanym stanem pozwoli pokazać trend.` : 'Historia zacznie się od pierwszego zapisanego stanu pulpitu.'}</p> : <TrendChart data={points} series={[{ key: 'net_worth', name: 'Majątek netto', area: true }, { key: 'total_assets', name: 'Aktywa', color: chartColors.secondary, dashed: true }, { key: 'total_liabilities', name: 'Dług uwzględniony w majątku', color: chartColors.muted, dashed: true }]} />}
    <p className="chart-note">Stan zapisuje się podczas otwierania pulpitu, najwyżej jeden punkt na dzień, aktualizowany przy kolejnej wizycie. Przeszłe salda nie są odtwarzane z dzisiejszych danych. Daty bez zapisów nie oznaczają zerowego majątku.</p></section>;
}
