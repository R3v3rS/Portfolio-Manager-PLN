import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { LoanScheduleEntry } from '../../api_loans';
import { chartColors, chartDate, chartMoney, chartTooltip } from '../charts/chartTheme';
export default function LoanPaymentChart({ schedule }: { schedule: LoanScheduleEntry[] }) {
  const [all, setAll] = useState(false);
  const today = new Date().toLocaleDateString('sv-SE');
  const future = schedule.filter(row => row.date >= today);
  const rows = all ? schedule : future.slice(0, 12);
  const hasInterest = rows.some(row => row.interest_part > .005);
  return <section className="chart-panel mt-5"><div className="chart-heading"><div><h2>Z czego składa się rata?</h2><p>Kapitał i odsetki według modelowego harmonogramu · PLN</p></div><div className="chart-toolbar"><button type="button" aria-pressed={!all} onClick={() => setAll(false)}>Najbliższe 12 rat</button><button type="button" aria-pressed={all} onClick={() => setAll(true)}>Cały harmonogram</button></div></div>
    {!rows.length ? <p className="chart-empty">Brak kolejnych rat. Zobacz cały harmonogram.</p> : <ResponsiveContainer width="100%" height={270}><BarChart data={rows}><CartesianGrid stroke={chartColors.grid} vertical={false} /><XAxis dataKey="date" tickFormatter={chartDate} minTickGap={35} tick={{ fill: chartColors.text, fontSize: 11 }} /><YAxis width={65} tick={{ fill: chartColors.text, fontSize: 11 }} /><Tooltip contentStyle={chartTooltip} labelFormatter={label => String(label)} formatter={(value, name) => [chartMoney(Number(value)), name]} /><Legend wrapperStyle={{ fontSize: 12 }} /><Bar dataKey="principal_part" name="Kapitał" stackId="payment" fill={chartColors.primary} isAnimationActive={false} />{hasInterest && <Bar dataKey="interest_part" name="Odsetki" stackId="payment" fill={chartColors.secondary} isAnimationActive={false} />}</BarChart></ResponsiveContainer>}
    <p className="chart-note">{hasInterest ? 'Suma słupka to rata z harmonogramu. Opłaty dodatkowe i nadpłaty są rozliczane osobno.' : 'W tym zakresie odsetki wynoszą 0 PLN, więc rata składa się z kapitału.'} Prognoza zakłada terminowe spłaty; potwierdzone płatności są w historii.</p>
  </section>;
}
