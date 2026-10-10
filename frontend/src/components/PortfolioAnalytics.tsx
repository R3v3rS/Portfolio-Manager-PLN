import { useState } from 'react';
import type { PortfolioHistoryPoint } from '../api';
import type { Holding, EquityAllocation } from '../types';
import { categoryColor, chartMoney } from './charts/chartTheme';
import { allocationRows, type AllocationGroup } from './portfolio/allocationModel';
import MonthlyAssetRatioChart from './MonthlyAssetRatioChart';
export default function PortfolioAnalytics({ holdings, cashBalance, historyData }: { holdings: Holding[]; cashBalance: number; historyData: PortfolioHistoryPoint[]; equityAllocation?: EquityAllocation[] }) {
  const [group, setGroup] = useState<AllocationGroup>('instrument');
  const [includeCash, setIncludeCash] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const allocation = allocationRows(holdings, cashBalance, group, includeCash);
  const remaining = allocation.rows.slice(5).reduce((sum, row) => sum + row.value, 0);
  const rows = expanded || allocation.rows.length <= 6 ? allocation.rows : [...allocation.rows.slice(0, 5), { name: 'Pozostałe', value: remaining, share: remaining / allocation.total * 100 }];
  return <div className="space-y-5"><section className="chart-panel">
    <div className="chart-heading"><div><h2>Jak rozłożony jest kapitał?</h2><p>Bieżąca wycena w PLN · {includeCash ? 'łącznie z gotówką' : 'część inwestycyjna bez gotówki'} · {chartMoney(allocation.total)}</p></div><label className="chart-toolbar"><input type="checkbox" checked={includeCash} onChange={event => setIncludeCash(event.target.checked)} /> Uwzględnij gotówkę</label></div>
    <div className="chart-toolbar" aria-label="Podział struktury">{([['instrument', 'Instrumenty'], ['sector', 'Sektory'], ['industry', 'Branże'], ['currency', 'Waluty']] as const).map(([key, label]) => <button key={key} type="button" aria-pressed={group === key} onClick={() => { setGroup(key); setExpanded(false); }}>{label}</button>)}</div>
    {allocation.missing.length > 0 && <p className="chart-alert">Brak wyceny: {allocation.missing.join(', ')}. Udziały dotyczą tylko wycenionej części; koszt zakupu nie zastępuje ceny.</p>}
    {rows.length ? <div aria-label="Udziały w wycenionej części portfela">{rows.map(row => <div className="chart-allocation-row" key={row.name}><span title={row.name}>{row.name}</span><span className="chart-track" aria-hidden="true"><i style={{ width: row.share + '%', backgroundColor: categoryColor(row.name) }} /></span><b>{chartMoney(row.value)}</b><small>{row.share.toLocaleString('pl-PL', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%</small></div>)}</div> : <p className="chart-empty">Brak wycenionych pozycji.</p>}
    {allocation.rows.length > 6 && <div className="chart-actions"><button type="button" onClick={() => setExpanded(!expanded)}>{expanded ? 'Pokaż największe udziały' : `Rozwiń wszystkie (${allocation.rows.length})`}</button></div>}
    <p className="chart-note">{group === 'currency' ? 'Waluta notowania instrumentu; wszystkie udziały liczone z wartości w PLN. Gotówka jest pokazywana osobno.' : group === 'sector' || group === 'industry' ? 'Klasyfikacja instrumentów według metadanych. Dla ETF nie jest to analiza składu funduszu.' : 'Pozycje tego samego instrumentu są zsumowane. Kolor kategorii pozostaje stały po sortowaniu.'}</p>
  </section><div className="chart-actions"><button type="button" aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}>{showHistory ? 'Ukryj' : 'Pokaż'} udział inwestycji i gotówki w czasie</button></div>{showHistory && <MonthlyAssetRatioChart data={historyData.filter(point => Number.isFinite(point.value))} />}</div>;
}
