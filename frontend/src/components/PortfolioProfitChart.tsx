import { TrendChart } from './charts/ChartKit';

export default function PortfolioProfitChart({ data, title = 'Skumulowany zysk / strata' }: { data: { date: string; label: string; value: number }[]; title?: string }) {
  return <div><h3 className="mb-4 font-semibold">{title}</h3><TrendChart data={data} series={[{ key: 'value', name: 'Skumulowany wynik', area: true }]} zero /></div>;
}
