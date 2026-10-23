import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { planningMoney as money, planningToday } from './planningHelpers';

export default function BudgetSpendingBreakdown({ data }: { data: BudgetWorkspace }) {
  const [all, setAll] = useState(false);
  const [metric, setMetric] = useState<'PLAN' | 'SHARE'>('PLAN');
  const totals = new Map<number, number>();
  data.entries.filter(entry => entry.date.startsWith(data.month) && entry.date <= planningToday() && (entry.kind === 'EXPENSE' || entry.kind === 'REFUND')).forEach(entry => {
    entry.lines.forEach(line => {
      const category = data.categories.find(item => item.id === line.category_id);
      const id = category?.parent_id ?? line.category_id;
      totals.set(id, (totals.get(id) ?? 0) + Math.round(line.amount * 100) * (entry.kind === 'REFUND' ? -1 : 1));
    });
  });
  const rows = data.categories.filter(category => !category.parent_id && totals.has(category.id) && totals.get(category.id) !== 0).sort((a, b) => (totals.get(b.id) ?? 0) - (totals.get(a.id) ?? 0));
  const total = [...totals.values()].reduce((sum, value) => sum + value, 0);
  const shareBase = [...totals.values()].reduce((sum, value) => sum + Math.max(0, value), 0);
  const visible = all ? rows : rows.slice(0, 7);
  const hiddenTotal = rows.slice(7).reduce((sum, category) => sum + (totals.get(category.id) ?? 0), 0);
  const hasNegative = [...totals.values()].some(value => value < 0);
  return <section className="budget-panel budget-spending-breakdown" aria-label="Na co wydano">
    <div className="budget-section-heading"><div><p className="page-eyebrow">Wydatki po zwrotach</p><h2>Na co wydano?</h2><p>Kliknij kategorię, aby sprawdzić jej transakcje. Bez przelewów i nowych odłożeń.</p></div><div className="budget-ranking-total"><span>Wszystkie kategorie</span><strong>{money(total / 100)}</strong></div></div>
    <div className="br-tabs budget-ranking-tabs" aria-label="Miara wykresu wydatków"><button type="button" aria-pressed={metric === 'PLAN'} className={metric === 'PLAN' ? 'is-active' : ''} onClick={() => setMetric('PLAN')}>Wykorzystanie planu</button><button type="button" aria-pressed={metric === 'SHARE'} className={metric === 'SHARE' ? 'is-active' : ''} onClick={() => setMetric('SHARE')}>Udział w wydatkach</button></div>
    <p className="budget-ranking-explanation">{metric === 'PLAN' ? 'Pełny pasek oznacza 100% planu danej kategorii. Przekroczenie pokazujemy kwotą i kolorem.' : hasNegative ? `Udziały liczymy w dodatnich kwotach kategorii po zwrotach: ${money(shareBase / 100)}. Kategorie z przewagą zwrotów pokazujemy osobno.` : 'Długość paska i procent pokazują udział kategorii w łącznych wydatkach po zwrotach.'}</p>
    {rows.length ? <div className="budget-spending-ranking">{visible.map(category => {
      const value = totals.get(category.id) ?? 0;
      const plan = Math.max(0, Math.round(category.planned * 100));
      const executed = Math.round(category.spent * 100);
      const over = metric === 'PLAN' && executed > plan;
      const percent = value < 0 ? null : metric === 'PLAN' ? plan > 0 ? Math.max(0, executed) / plan * 100 : null : shareBase > 0 ? value / shareBase * 100 : null;
      const percentText = percent === null ? '' : new Intl.NumberFormat('pl-PL', {maximumFractionDigits:1}).format(percent);
      return <Link key={category.id} className={over ? 'is-over' : ''} to={`/budget?view=entries&month=${data.month}&category=${category.id}`}>
        <span><strong>{category.name}</strong><b>{money(value / 100)}</b></span>
        {percent === null ? <span className="budget-ranking-track is-unplanned" aria-hidden="true"/> : <span className="budget-ranking-track" role="progressbar" aria-label={`${metric === 'PLAN' ? 'Wykorzystanie planu' : 'Udział w wydatkach'}: ${category.name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100, percent)} aria-valuetext={`${percentText}%${metric === 'PLAN' ? ' planu' : ' wydatków'}`}><i style={{ width: `${Math.min(100, percent)}%` }}/></span>}
        <small>{value < 0 ? `Zwroty przewyższają zakupy o ${money(-value / 100)}` : metric === 'SHARE' ? `${percentText}% wydatków` : plan > 0 ? `${percentText}% planu · plan ${money(plan / 100)}` : 'Bez zaplanowanej kwoty'}</small>
        {metric === 'PLAN' && value >= 0 && executed !== value && <small>Wykonanie planu: {money(executed / 100)}. Uwzględnia odłożenia mediów i rozliczenie wcześniejszych rezerw.</small>}
        {over && value >= 0 && <small className="budget-ranking-overrun">{plan > 0 ? 'Ponad plan' : 'Wydatek bez planu'}: {money((executed - plan) / 100)}</small>}
      </Link>;
    })}</div> : <p className="budget-small-empty">Brak wydatków w wybranym miesiącu. Zapisane zakupy pojawią się tutaj po ich wykonaniu.</p>}
    {rows.length > 7 && <div className="budget-ranking-footer">{!all && <small>Pokazano 7 z {rows.length} kategorii. Pozostałe kategorie: {money(hiddenTotal / 100)}. Suma u góry obejmuje wszystkie.</small>}<button className="budget-text-button" onClick={() => setAll(!all)}>{all ? 'Pokaż najważniejsze' : `Wszystkie kategorie (${rows.length})`}</button></div>}
  </section>;
}
