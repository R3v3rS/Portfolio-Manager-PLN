import { Link } from 'react-router-dom';
import {useState} from 'react';
import { ArrowUpRight } from 'lucide-react';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { TrendChart } from '../charts/ChartKit';
import { chartColors } from '../charts/chartTheme';
import { budgetChartData } from './budgetChartModel';

export default function BudgetCharts({ data }: { data: BudgetWorkspace }) {
  const [metric,setMetric]=useState<'daily'|'cash'|'budget'>('daily');
  const chart = budgetChartData(data, new Date().toLocaleDateString('sv-SE'), 0);
  const pace=data.chart?.map(p=>({date:p.date,spent:metric==='daily'?(p.daily_spent===undefined?chart.dailyPace.find(d=>d.date===p.date)?.spent??null:p.daily_spent):metric==='cash'?p.cash_spent:p.budget_spent,plan:metric==='daily'?(p.daily_plan??chart.dailyPace.find(d=>d.date===p.date)?.plan??0):metric==='cash'?p.cash_plan:p.budget_plan}))??(metric==='daily'?chart.dailyPace:chart.pace);
  const fixed=data.fixed_costs;
  const money=(amount:number)=>new Intl.NumberFormat('pl-PL',{style:'currency',currency:'PLN'}).format(amount);
  return <div className="budget-chart-stack">
    <section className="chart-panel">
      <div className="chart-heading"><div><h2>{metric==='daily'?'Tempo codziennych wydatków':'Wydatki na tle planu miesiąca'}</h2><p>Narastająco od początku miesiąca · PLN</p></div></div>
      <div className="bp-switch bp-chart-modes"><button aria-pressed={metric==='daily'} onClick={()=>setMetric('daily')}>Codzienne wydatki</button><button aria-pressed={metric==='budget'} onClick={()=>setMetric('budget')}>Obciążenie budżetu</button><button aria-pressed={metric==='cash'} onClick={()=>setMetric('cash')}>Faktyczne wydatki</button></div>
      <TrendChart data={pace} series={[{ key: 'spent', name: metric==='daily'?'Codzienne zakupy po zwrotach':metric==='cash'?'Wydatki po zwrotach':'Wydatki i odłożenia', area: true }, { key: 'plan', name: metric==='daily'?'Plan codziennych wydatków':'Plan do tego dnia', dashed: true, color: chartColors.secondary }]} height={250} note="Wydatki pokazujemy do dziś, plan — do końca miesiąca. Kliknij legendę, aby ukryć serię." />
      <details className="budget-calculation-help"><summary>Jak czytać wykres?</summary><p className="chart-note">{metric==='daily'?'Powiązane rachunki, raty i płatności z rezerw oraz kategorie miesięcznych mediów są poza tym wykresem. Codzienny limit rozkładamy równomiernie na dni miesiąca.':`${metric==='cash'?'Płatności po zwrotach, bez odłożeń.':'Wydatki i nowe odłożenia, pomniejszone o zwolnienia i rozliczone rezerwy.'} Wcześniejsza płatność rachunku lub raty przesuwa także plan na dzień zapłaty. Plan zachowuje przewidywaną kwotę, więc przekroczenia pozostają widoczne.`}</p></details>
      {fixed&&fixed.count>0&&<section className="bp-fixed-summary" aria-label="Stałe opłaty w miesiącu"><h3>Stałe opłaty — rachunki i raty</h3><div><span>Zaplanowano<strong>{money(fixed.planned)}</strong></span><span>Opłacono<strong>{money(fixed.paid)}</strong></span><span>Do opłacenia<strong>{money(fixed.pending)}</strong></span></div><p>{fixed.paid_count} z {fixed.count} rozliczonych.{fixed.early_count>0&&` Zapłacone przed terminem: ${fixed.early_count}. To wykonanie zobowiązania, a nie szybsze codzienne wydawanie.`}</p>{fixed.over_plan>0&&<p className="budget-negative">Kwoty opłaconych zobowiązań ponad plan: {money(fixed.over_plan)}.</p>}<Link to={`/budget?view=bills&month=${data.month}`}>Przejrzyj rachunki <ArrowUpRight size={14}/></Link></section>}
    </section>

  </div>;
}
