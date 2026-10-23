import { planningMoney as money } from './planningHelpers';

export default function BudgetFundingProgress({ name, planned, funded, month, zeroPlanNote }: { name: string; planned: number; funded: number; month?: string; zeroPlanNote?: string }) {
  const percent = planned > 0 ? Math.max(0, funded) / planned * 100 : null;
  const monthLabel=month?new Date(month+'-01T12:00:00').toLocaleDateString('pl-PL',{month:'long',year:'numeric'}):null;
  return <div className="budget-funding-progress"><div><span>Wykonanie planu{monthLabel?` · ${monthLabel}`:' miesiąca'}</span><b>{money(funded)} / {money(planned)}</b></div>
    {percent !== null ? <><div className="budget-segment-track" role="progressbar" aria-label={`Wykonanie odłożeń: ${name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100, percent)} aria-valuetext={`${Math.round(percent)}% planu; ${money(funded)} z ${money(planned)}`}><span className="is-funding" style={{ width: `${Math.min(100, percent)}%` }}/></div><small>{Math.round(percent)}% planu{funded > planned && ` · ponad plan ${money(funded - planned)}`}</small></> : <small>{zeroPlanNote??'Odkładanie ręczne — brak obowiązkowej wpłaty w tym miesiącu.'}</small>}
  </div>;
}
