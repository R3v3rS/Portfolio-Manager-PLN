import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { goalsApi, type InvestmentGoal } from '../../api_goals';
import { goalMoney, goalPercent } from './goalModel';
import './goals.css';

export default function GoalsSummary({ portfolioId }: { portfolioId?: number }) {
  const [goals, setGoals] = useState<InvestmentGoal[]>([]);
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');
  useEffect(() => {
    let active = true;
    goalsApi.workspace().then(data => { if (active) { setGoals(data.goals.filter(goal => !goal.is_archived && (!portfolioId || goal.portfolio_ids.includes(portfolioId) || data.portfolios.some(p => p.id === portfolioId && p.parent_portfolio_id && goal.portfolio_ids.includes(p.parent_portfolio_id))))); setStatus('ok'); } }).catch(() => { if (active) setStatus('error'); });
    return () => { active = false; };
  }, [portfolioId]);
  const path = portfolioId ? `/goals?portfolio=${portfolioId}` : '/goals';
  return <section className="goal-panel" aria-label="Cele inwestycyjne"><header className="goal-pulse-header"><h2>{portfolioId ? 'Cele tego portfela' : 'Twoje cele inwestycyjne'}</h2><Link to={path}>Przejdź do celów →</Link></header>
    {status === 'loading' ? <p className="goal-note">Ładowanie celów…</p> : status === 'error' ? <p className="goal-note">Nie udało się odczytać celów. Otwórz sekcję celów, aby spróbować ponownie.</p> : !goals.length ? <div className="mt-4"><p className="goal-note">Połącz kapitał z planem: emeryturą, mieszkaniem lub własnym celem. Zobacz postęp i wpływ regularnych wpłat.</p><Link className="goal-button mt-4" to={`${path}${portfolioId ? '&' : '?'}new=1`}>Wyznacz {portfolioId ? 'cel dla portfela' : 'pierwszy cel'}</Link></div> : <><div className="goal-pulse-list">{goals.slice(0, 3).map(goal => {
      const progress = goal.current_value === null ? 0 : Math.max(0, goal.current_value / goal.target_amount * 100);
      return <Link key={goal.id} to={`/goals?goal=${goal.id}`}><h3>{goal.name}</h3><p>{goalMoney(goal.current_value)} / {goalMoney(goal.target_amount)}</p><div className="goal-progress"><i style={{ width: `${Math.min(progress, 100)}%` }} /></div><p>{goal.current_value === null ? 'Niepełna wycena' : goalPercent(progress)} · termin {new Date(goal.target_date + 'T12:00:00').toLocaleDateString('pl-PL')}</p></Link>;
    })}</div>{goals.some(goal => goal.overlapping_goals.length > 0) && <p className="goal-note">Część celów korzysta ze wspólnych środków. Ich postępu nie należy sumować.</p>}</>}
  </section>;
}
