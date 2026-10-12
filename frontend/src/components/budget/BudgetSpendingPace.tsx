import { Gauge } from 'lucide-react';
import type { BudgetWorkspace } from '../../api_budget_workspace';
import { budgetSpendingPace } from './spendingPaceModel';

const money = (amount: number) => new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(amount);
export default function BudgetSpendingPace({ data, today = new Date().toLocaleDateString('sv-SE') }: { data: BudgetWorkspace; today?: string }) {
  const p = budgetSpendingPace(data, today);
  const available = p.day > 0 && p.spent !== null && p.monthlyPlan > 0;
  const over = available && p.spent! > p.monthlyPlan;
  const ahead = available && p.daysAhead! > 0;
  const headline = !p.day ? 'Tempo będzie widoczne po rozpoczęciu miesiąca'
    : p.spent === null ? 'Brak danych o aktualnym tempie'
    : !p.monthlyPlan ? 'Ustaw plan codziennych wydatków'
    : over ? 'Przekroczony plan codziennych wydatków'
    : !p.current ? 'Podsumowanie tempa za cały miesiąc'
    : ahead ? `Około ${p.daysAhead} ${p.daysAhead === 1 ? 'dzień' : 'dni'} przed planem`
    : p.daysAhead! < 0 ? `Około ${-p.daysAhead!} ${p.daysAhead === -1 ? 'dzień' : 'dni'} zapasu względem planu`
    : 'Wydatki w tempie planu';
  return <section className={`budget-pace-card${ahead || over ? ' is-ahead' : ''}`} aria-label="Tempo wydawania względem planu">
    <div className="budget-pace-heading"><Gauge size={22} aria-hidden="true"/><div><span>Codzienne wydatki · {p.current ? `stan na ${p.day}. dzień miesiąca` : data.month}</span><h3>{headline}</h3></div></div>
    {available && <>
      <p>{over ? `Plan całego miesiąca przekroczony o ${money(p.spent! - p.monthlyPlan)}.` : p.equivalentDay === 0 ? 'Nie wykorzystano jeszcze nawet jednego dnia planu.' : `Obecne wydatki odpowiadają orientacyjnie ${p.equivalentDay}. dniowi planu.`}{p.current && ahead && !over && ' Codzienne zakupy wyprzedzają zaplanowane tempo.'}</p>
      <div className="budget-pace-values"><span>Wydano do {p.current ? 'dziś' : 'końca miesiąca'}<strong>{money(p.spent!)}</strong></span><span>Plan do {p.current ? 'dziś' : 'końca miesiąca'}<strong>{money(p.plannedToday)}</strong></span><span>Plan całego miesiąca<strong>{money(p.monthlyPlan)}</strong></span></div>
    </>}
    <small>Porównujemy zakupy po zwrotach z równomiernym planem dziennym. Powiązane rachunki, raty, płatności z rezerw i miesięczne pule mediów nie przyspieszają tego wskaźnika. Odłożenia nie są zakupami.</small>
  </section>;
}
