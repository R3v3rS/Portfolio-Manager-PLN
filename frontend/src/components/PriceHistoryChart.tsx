import { TrendChart } from './charts/ChartKit';

export default function PriceHistoryChart({ ticker, data, currency }: { ticker: string; data: { date: string; close_price: number }[]; currency?: string | null }) {
  return <><TrendChart data={data.map(point => ({ ...point, date: point.date.split('T')[0].split(' ')[0] }))} series={[{ key: 'close_price', name: 'Cena ' + ticker }]} unit={currency || 'waluta notowania'} /><p className="chart-note">Zapisane ceny instrumentu. {currency ? 'Waluta: ' + currency + '.' : 'Waluta notowania nie została ustalona.'}</p></>;
}
