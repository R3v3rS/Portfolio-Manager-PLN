import { useState } from 'react';
import { goalsApi, type GoalPortfolio, type InvestmentGoal, type GoalPlan } from '../../api_goals';
import { extractErrorMessageFromUnknown } from '../../http/response';
import { assetClasses, emptyAllocation, goalMoney, isDescendant, localToday } from './goalModel';

export default function GoalEditor({ goal, portfolios, initialPortfolio, onSaved, onCancel }: {
  goal?: InvestmentGoal; portfolios: GoalPortfolio[]; initialPortfolio?: number; onSaved: (id: number) => Promise<void>; onCancel: () => void;
}) {
  const defaultDate = `${Number(localToday().slice(0, 4)) + 5}${localToday().slice(4) === '-02-29' ? '-02-28' : localToday().slice(4)}`;
  const [name, setName] = useState(goal?.name ?? '');
  const [description, setDescription] = useState(goal?.description ?? '');
  const [target, setTarget] = useState(String(goal?.target_amount ?? ''));
  const [date, setDate] = useState(goal?.target_date ?? defaultDate);
  const [monthly, setMonthly] = useState(String(goal?.monthly_contribution ?? 0));
  const [annual, setAnnual] = useState(String(goal?.annual_return ?? 0));
  const [ids, setIds] = useState(goal?.portfolio_ids.filter(id => portfolios.some(p => p.id === id)) ?? (initialPortfolio && portfolios.some(p => p.id === initialPortfolio) ? [initialPortfolio] : []));
  const [withAllocation, setWithAllocation] = useState(Boolean(goal?.target_allocation));
  const [allocation, setAllocation] = useState(goal?.target_allocation ?? emptyAllocation());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const allocationSum = Object.values(allocation).reduce((sum, value) => sum + value, 0);
  const toggle = (id: number) => setIds(previous => previous.includes(id) ? previous.filter(value => value !== id) : [...previous.filter(value => !isDescendant(value, id, portfolios)), id]);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError('');
    if (!ids.length) { setError('Wybierz co najmniej jeden portfel.'); return; }
    if (withAllocation && Math.abs(allocationSum - 100) > .001) { setError('Docelowe udziały muszą sumować się do 100%.'); return; }
    const plan: GoalPlan = { name, description, target_amount: Number(target), target_date: date, monthly_contribution: Number(monthly), annual_return: Number(annual), portfolio_ids: ids, target_allocation: withAllocation ? allocation : null };
    setBusy(true);
    try {
      const result = goal ? await goalsApi.update(goal.id, plan) : await goalsApi.create(plan);
      await onSaved(result.id);
    } catch (err) { setError(extractErrorMessageFromUnknown(err)); }
    finally { setBusy(false); }
  };
  return <section className="goal-panel"><header className="goal-section-heading"><div><p className="page-eyebrow">TWÓJ PLAN</p><h2>{goal ? 'Edytuj cel inwestycyjny' : 'Nowy cel inwestycyjny'}</h2><p>Wybierz cel, źródła kapitału i własne założenia.</p></div></header>
    <form onSubmit={submit} className="goal-form">
      <div className="goal-form-grid"><label>Nazwa celu<input autoFocus value={name} onChange={e => setName(e.target.value)} required maxLength={100} placeholder="Np. emerytura, mieszkanie" /></label><label>Kwota celu · PLN<input type="number" min="0.01" max="1000000000000" step="0.01" value={target} onChange={e => setTarget(e.target.value)} required /></label><label>Termin celu<input type="date" min="2000-01-01" max={`${new Date().getFullYear() + 60}-12-31`} value={date} onChange={e => setDate(e.target.value)} required /></label><label>Miesięczna wpłata · PLN<input type="number" min="0" max="1000000000" step="0.01" value={monthly} onChange={e => setMonthly(e.target.value)} required /></label><label>Zakładany roczny zwrot · %<input type="number" min="-50" max="50" step="0.01" value={annual} onChange={e => setAnnual(e.target.value)} required /><small>0% pozwala planować wyłącznie na podstawie wpłat. Możesz przyjąć własną wartość.</small></label><label>Opis celu<textarea value={description} onChange={e => setDescription(e.target.value)} maxLength={1000} rows={3} placeholder="Na co przeznaczysz te środki?" /></label></div>
      <fieldset><legend>Portfele przypisane do celu</legend><p className="goal-note">Portfel główny obejmuje także aktywne podportfele. Ten sam kapitał jest liczony tylko raz w ramach celu.</p><div className="goal-portfolio-options">{portfolios.map(p => {
        const covered = ids.some(id => isDescendant(p.id, id, portfolios));
        return <label key={p.id} className={covered ? 'is-covered' : ''}><input type="checkbox" checked={ids.includes(p.id) || covered} disabled={covered || busy} onChange={() => toggle(p.id)} /><span><strong>{p.name}</strong><small>{p.account_type}{p.parent_portfolio_id ? ' · podportfel' : ''}{covered ? ' · uwzględniony w portfelu głównym' : ''}</small></span><b>{goalMoney(p.value)}</b></label>;
      })}</div>{!portfolios.length && <p className="goal-note">Najpierw dodaj portfel w sekcji Inwestycje.</p>}</fieldset>
      <fieldset><legend>Docelowa struktura</legend><label className="goal-check"><input type="checkbox" checked={withAllocation} onChange={e => setWithAllocation(e.target.checked)} />Chcę ustalić własne udziały kategorii</label>{withAllocation && <><div className="goal-allocation-inputs">{assetClasses.map(({ key, name }) => <label key={key}>{name} · %<input type="number" min="0" max="100" step="0.01" value={allocation[key]} required onChange={e => setAllocation(previous => ({ ...previous, [key]: Number(e.target.value) }))} /></label>)}</div><p className={Math.abs(allocationSum - 100) < .001 ? 'goal-note' : 'goal-error'}>Suma udziałów: {allocationSum.toLocaleString('pl-PL', { maximumFractionDigits: 2 })}% / 100%</p></>}</fieldset>
      {error && <p className="goal-error" role="alert">{error}</p>}
      <div className="goal-actions"><button className="goal-button primary" disabled={busy || !portfolios.length} type="submit">{busy ? 'Zapisywanie…' : 'Zapisz cel'}</button><button className="goal-button" type="button" disabled={busy} onClick={onCancel}>Anuluj</button></div>
      <p className="goal-note">Zapis celu przechowuje plan. Miesięczna wpłata i docelowe udziały nie księgują operacji ani nie zlecają zakupów.</p>
    </form>
  </section>;
}
