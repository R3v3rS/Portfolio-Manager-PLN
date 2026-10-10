import { TrendChart } from './charts/ChartKit';

interface Props {
  data: { date: string; label: string; value: number; net_value?: number; net_contributions?: number; benchmark_value?: number; benchmark_inflation?: number }[];
  title?: string; benchmarkName?: string; valueName?: string; unit?: string; netValueName?: string; contributionsName?: string;
}
export default function PortfolioHistoryChart({ data, title, benchmarkName = 'Benchmark', valueName = 'Wartość portfela', unit = 'PLN', netValueName = 'Wartość netto po podatku', contributionsName = 'Wpłaty netto' }: Props) {
  const series = [{ key: 'value', name: valueName }];
  if (data.some(point => point.net_value !== undefined)) series.push({ key: 'net_value', name: netValueName });
  if (data.some(point => point.net_contributions !== undefined)) series.push({ key: 'net_contributions', name: contributionsName });
  if (data.some(point => point.benchmark_value !== undefined)) series.push({ key: 'benchmark_value', name: benchmarkName });
  return <div>{title && <h3>{title}</h3>}<TrendChart data={data} series={series} unit={unit} /></div>;
}
