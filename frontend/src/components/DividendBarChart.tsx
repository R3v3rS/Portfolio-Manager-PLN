import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { chartColors, chartDate, chartMoney, chartTooltip } from './charts/chartTheme';
export default function DividendBarChart({ data }: { data: { label: string; amount: number; key?: string }[] }) {
  const [all, setAll] = useState(false);
  const today = new Date();
  const currentMonth = today.toLocaleDateString('sv-SE').slice(0, 7);
  const cutoff = new Date(today.getFullYear(), today.getMonth() - 11, 1).toLocaleDateString('sv-SE').slice(0, 7);
  const source = data.map(point => ({ ...point, date: point.key ?? point.label }));
  const recent = source.filter(point => !point.key || point.key >= cutoff && point.key <= currentMonth);
  const points = all ? source : recent;
  const received = recent.reduce((sum, point) => sum + point.amount, 0);
  return <section className="chart-panel"><div className="chart-heading"><div><h2>Dochód z dywidend</h2><p>Wyłącznie zaksięgowane wypłaty · PLN</p></div><div className="chart-toolbar"><button type="button" aria-pressed={!all} onClick={() => setAll(false)}>Ostatnie 12 miesięcy</button><button type="button" aria-pressed={all} onClick={() => setAll(true)}>Cała historia</button></div></div><div className="chart-stat-row"><div><span>Otrzymano przez ostatnie 12 miesięcy</span><strong>{chartMoney(received)}</strong></div></div>{!points.length ? <p className="chart-empty">Brak zaksięgowanych dywidend w tym okresie.</p> : <ResponsiveContainer width="100%" height={240}><BarChart data={points}><CartesianGrid stroke={chartColors.grid} vertical={false} /><XAxis dataKey="date" tickFormatter={chartDate} minTickGap={40} tick={{ fill: chartColors.text, fontSize: 11 }} /><YAxis width={65} tick={{ fill: chartColors.text, fontSize: 11 }} /><Tooltip contentStyle={chartTooltip} formatter={value => [chartMoney(Number(value)), 'Otrzymano']} labelFormatter={label => chartDate(String(label))} /><Bar dataKey="amount" fill={chartColors.primary} radius={[5, 5, 0, 0]} isAnimationActive={false} /></BarChart></ResponsiveContainer>}<p className="chart-note">Bieżący miesiąc jest niezamknięty. Miesiące bez wypłat nie są rysowane jako osobne słupki. To historia otrzymanych środków, bez prognoz dywidend.</p></section>;
}
