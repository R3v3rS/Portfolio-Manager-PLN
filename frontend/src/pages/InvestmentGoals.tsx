import { useCallback, useEffect, useState } from 'react';
import { Archive, Plus, Target } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { goalsApi, type GoalsWorkspace, type InvestmentGoal } from '../api_goals';
import { extractErrorMessageFromUnknown } from '../http/response';
import GoalEditor from '../components/goals/GoalEditor';
import GoalDetail from '../components/goals/GoalDetail';
import { goalMoney, goalPercent } from '../components/goals/goalModel';
import '../components/goals/goals.css';

export default function InvestmentGoals() {
  const [params] = useSearchParams();
  const initialPortfolio = Number(params.get('portfolio')) || undefined;
  const [data, setData] = useState<GoalsWorkspace>({ goals: [], portfolios: [], as_of: '' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState<number | null>(Number(params.get('goal')) || null);
  const [editor, setEditor] = useState<'new' | InvestmentGoal | null>(params.get('new') === '1' ? 'new' : null);
  const [archived, setArchived] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const workspace = await goalsApi.workspace(); setData(workspace); setError(''); return workspace;
  }, []);
  useEffect(() => { let active = true; goalsApi.workspace().then(result => { if (active) { setData(result); setError(''); } }).catch(err => { if (active) setError(extractErrorMessageFromUnknown(err)); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  const visible = data.goals.filter(goal => goal.is_archived === archived);
  const goal = visible.find(item => item.id === selected) ?? visible.find(item => initialPortfolio && item.portfolio_ids.includes(initialPortfolio)) ?? visible[0];
  const activeGoals = data.goals.filter(item => !item.is_archived);
  const complete = activeGoals.filter(item => item.current_value !== null && item.current_value >= item.target_amount).length;
  const changeArchive = async (item: InvestmentGoal) => {
    setBusy(true); setError('');
    try { await goalsApi.archive(item.id, !item.is_archived); await load(); setNotice(item.is_archived ? 'Cel przywrócony.' : 'Cel przeniesiony do archiwum. Możesz go przywrócić.'); }
    catch (err) { setError(extractErrorMessageFromUnknown(err)); }
    finally { setBusy(false); }
  };
  return <div className="page-stack investment-goals"><header className="goal-page-heading"><div><p className="page-eyebrow">TWÓJ PLAN INWESTYCYJNY</p><h1>Cele inwestycyjne</h1><p>Nadaj kapitałowi kierunek. Sprawdź postęp, zaplanuj wpłaty i ustal własną strukturę.</p></div><button className="goal-button primary" disabled={loading || busy || Boolean(error && !data.as_of)} onClick={() => { setEditor('new'); setNotice(''); }}><Plus size={18} />Nowy cel</button></header>
    {notice && <p className="goal-success" role="status">{notice}</p>}
    {error && <div className="goal-alert" role="alert"><p>{error}</p><button className="goal-button" disabled={busy} onClick={() => { setBusy(true); load().catch(err => setError(extractErrorMessageFromUnknown(err))).finally(() => setBusy(false)); }}>Spróbuj ponownie</button></div>}
    {loading ? <p className="goal-panel">Ładowanie celów…</p> : editor ? <GoalEditor key={editor === 'new' ? 'new' : editor.id} goal={editor === 'new' ? undefined : editor} portfolios={data.portfolios} initialPortfolio={initialPortfolio} onCancel={() => setEditor(null)} onSaved={async id => {
      setSelected(id); setArchived(editor !== 'new' && editor.is_archived); setEditor(null);
      setNotice('Cel zapisany. Postęp korzysta z wyceny przypisanych portfeli.');
      try { await load(); } catch { setError('Cel został zapisany, ale nie udało się odświeżyć wyceny. Spróbuj ponownie.'); }
    }} /> : <>
      <section className="goal-summary-strip" aria-label="Podsumowanie celów"><div><span>Aktywne cele</span><strong>{activeGoals.length}</strong></div><div><span>Osiągnięte w aktualnej wycenie</span><strong>{complete}</strong></div><div><span>Planowane wpłaty do aktywnych celów</span><strong>{goalMoney(activeGoals.reduce((sum, item) => sum + item.monthly_contribution, 0))}<small>/ miesiąc</small></strong></div></section>
      <div className="goal-view-tabs"><button className="goal-button" aria-pressed={!archived} onClick={() => { setArchived(false); setSelected(null); }}>Aktywne</button><button className="goal-button" aria-pressed={archived} onClick={() => { setArchived(true); setSelected(null); }}><Archive size={15} />Archiwum ({data.goals.filter(item => item.is_archived).length})</button></div>
      {!visible.length ? <section className="goal-panel goal-empty"><div className="goal-empty-icon"><Target size={32} /></div><h2>{archived ? 'Archiwum jest puste' : 'Na co pracuje Twój kapitał?'}</h2><p>{archived ? 'Zarchiwizowane cele możesz tutaj przywrócić.' : 'Połącz portfele z celem: emeryturą, mieszkaniem lub własnym planem. Zobaczysz postęp i wpływ regularnych wpłat.'}</p>{!archived && <button className="goal-button primary" onClick={() => setEditor('new')}><Plus size={17} />Utwórz pierwszy cel</button>}</section> : <div className="goal-workspace"><aside className="goal-list" aria-label="Lista celów">{visible.map(item => {
        const progress = item.current_value === null ? 0 : Math.max(0, item.current_value / item.target_amount * 100);
        return <article key={item.id} className={`goal-list-card ${goal?.id === item.id ? 'is-selected' : ''}`}><button className="goal-select" onClick={() => { setSelected(item.id); setNotice(''); }} aria-pressed={goal?.id === item.id}><strong>{item.name}</strong><span>{item.portfolio_names.join(' · ')}</span><b>{item.current_value === null ? 'Niepełna wycena' : goalPercent(progress)}<small>cel {goalMoney(item.target_amount)}</small></b><div className="goal-progress"><i style={{ width: `${Math.min(progress, 100)}%` }} /></div><span>{goalMoney(item.monthly_contribution)} / mies.</span></button><button className="goal-archive" disabled={busy} onClick={() => changeArchive(item)} aria-label={`${item.is_archived ? 'Przywróć' : 'Archiwizuj'} cel ${item.name}`}><Archive size={14} />{item.is_archived ? 'Przywróć cel' : 'Archiwizuj'}</button></article>;
      })}</aside>{goal && <GoalDetail key={`${goal.id}-${goal.monthly_contribution}-${goal.annual_return}`} goal={goal} asOf={data.as_of} onEdit={() => setEditor(goal)} />}</div>}
    </>}
  </div>;
}
