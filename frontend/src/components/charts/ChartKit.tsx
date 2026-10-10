import { useState } from 'react';
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import './charts.css';

import { chartColors, chartDate, chartTooltip } from './chartTheme';
export type TrendSeries = { key: string; name: string; color?: string; area?: boolean; dashed?: boolean };
export function TrendChart<T extends object>({ data, series, unit = 'PLN', height = 300, zero = false, note = 'Kliknij nazwę serii w legendzie, aby ją ukryć. Przerwy oznaczają brak wyceny.' }: {
  data: T[]; series: TrendSeries[]; unit?: string; height?: number; zero?: boolean; note?:string;
}) {
  const [hidden, setHidden] = useState<string[]>([]);
  const [table, setTable] = useState(false);
  const showDots = (key: string) => data.filter(point => typeof (point as Record<string, unknown>)[key] === 'number' && Number.isFinite((point as Record<string, unknown>)[key])).length < 3;
  const format = (value: number) => `${value.toLocaleString('pl-PL', { maximumFractionDigits: 2 })}${unit === '%' ? '%' : ' ' + unit}`;
  if (!data.length) return <p className="chart-empty">Brak wystarczających danych w wybranym okresie.</p>;
  return <div className="chart-view">
    <div className="chart-actions"><span>{data.length} obserwacji · {unit}</span><button type="button" onClick={() => setTable(!table)} aria-pressed={table}>{table ? 'Pokaż wykres' : 'Tabela danych'}</button></div>
    {table ? <div className="chart-table-wrap"><table className="chart-table"><thead><tr><th>Data</th>{series.map(item => <th key={item.key}>{item.name}</th>)}</tr></thead><tbody>{data.map((point, index) => {
      const row = point as Record<string, unknown>;
      return <tr key={index}><th>{String(row.date ?? row.label ?? index)}</th>{series.map(item => <td key={item.key}>{typeof row[item.key] === 'number' && Number.isFinite(row[item.key]) ? format(row[item.key] as number) : 'Brak danych'}</td>)}</tr>;
    })}</tbody></table></div> : <div role="img" aria-label={`${series.map(item => item.name).join(', ')} w czasie. Jednostka: ${unit}. Dokładne wartości dostępne w tabeli danych.`}><ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 12, right: 14, bottom: 8, left: 0 }}>
        <CartesianGrid stroke={chartColors.grid} vertical={false} strokeDasharray="3 6" />
        <XAxis dataKey="date" tickFormatter={chartDate} minTickGap={40} tick={{ fill: chartColors.text, fontSize: 11 }} tickLine={false} axisLine={false} />
        <YAxis width={65} tickFormatter={value => `${new Intl.NumberFormat('pl-PL', { notation: 'compact' }).format(Number(value))}${unit === '%' ? '%' : ''}`} tick={{ fill: chartColors.text, fontSize: 11 }} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={chartTooltip} labelStyle={{ color: '#edf7fa' }} labelFormatter={label => chartDate(String(label))} formatter={(value, name) => [format(Number(value)), name]} />
        {zero && <ReferenceLine y={0} stroke={chartColors.muted} />}
        <Legend onClick={item => { const key = String(item.dataKey); setHidden(previous => previous.includes(key) ? previous.filter(value => value !== key) : [...previous, key]); }} wrapperStyle={{ fontSize: 12, cursor: 'pointer', paddingTop: 12 }} />
        {series.map((item, index) => item.area ? <Area key={item.key} dataKey={item.key} name={item.name} type="linear" hide={hidden.includes(item.key)} fill={item.color ?? chartColors.primary} fillOpacity={.13} stroke={item.color ?? chartColors.primary} strokeWidth={2} dot={showDots(item.key)} connectNulls={false} isAnimationActive={false} /> : <Line key={item.key} dataKey={item.key} name={item.name} type="linear" hide={hidden.includes(item.key)} stroke={item.color ?? (index ? chartColors.secondary : chartColors.primary)} strokeWidth={2} dot={showDots(item.key)} connectNulls={false} strokeDasharray={item.dashed ? '5 5' : undefined} isAnimationActive={false} />)}
      </ComposedChart>
    </ResponsiveContainer></div>}
    <p className="chart-note">{note}</p>
  </div>;
}
