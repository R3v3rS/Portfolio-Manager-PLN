import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, BookOpen, CalendarDays, Check, CheckCheck, ClipboardList, CreditCard, FileUp, Flag, Pencil, Plus, Radar, RefreshCw, Target, Wallet, X } from 'lucide-react';
import { actionsApi, type ActionCategory, type ActionsWorkspace, type DashboardAction, type TaskPlan } from '../../api_actions';
import { extractErrorMessageFromUnknown } from '../../http/response';
import './dashboardActions.css';

type Filter = 'all' | 'overdue' | 'today' | 'week' | 'unscheduled' | 'completed';
const categories: Record<ActionCategory, string> = { investments: 'Inwestycje', budget: 'Budżet', loans: 'Kredyty', other: 'Pozostałe' };
const sources = { manual: 'Twoje zadanie', journal: 'Dziennik inwestora', radar: 'Radar', bill: 'Rachunek', loan: 'Rata kredytu', import: 'Import transakcji', goal: 'Cel inwestycyjny', budget_plan: 'Plan budżetu', reserve: 'Rezerwa na wydatek', bond: 'Obligacje' };
const icons = { manual: ClipboardList, journal: BookOpen, radar: Radar, bill: Wallet, loan: CreditCard, import: FileUp, goal: Target, budget_plan: Wallet, reserve: Target, bond: CalendarDays };
const dateText = (value: string) => new Date(value + 'T12:00:00').toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: 'numeric' });
const money = (value: number) => new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN' }).format(value);
const countText = (value: number) => `${value} ${value === 1 ? 'sprawa' : value % 10 >= 2 && value % 10 <= 4 && (value % 100 < 12 || value % 100 > 14) ? 'sprawy' : 'spraw'}`;
const nextWeek = (value: string) => {
  const end = new Date(value + 'T12:00:00'); end.setDate(end.getDate() + 7);
  return `${end.getFullYear()}-${String(end.getMonth()+1).padStart(2,'0')}-${String(end.getDate()).padStart(2,'0')}`;
};

function TaskEditor({ entry, onCancel, onSaved }: { entry: DashboardAction | null; onCancel: () => void; onSaved: () => void }) {
  const [plan, setPlan] = useState<TaskPlan>(() => ({ title: entry?.title || '', notes: entry?.description || '', category: entry?.category || 'other', due_date: entry?.due_date || null, priority: entry?.priority || 'normal' }));
  const requestId = useRef(crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError('');
    try {
      if (entry) await actionsApi.update(entry.task_id!, plan, entry.version!);
      else await actionsApi.create(plan, requestId.current);
      onSaved();
    } catch (err) { setError(extractErrorMessageFromUnknown(err)); setBusy(false); }
  };
  return <form className="dc-editor" aria-label={entry ? 'Edytuj zadanie' : 'Nowe zadanie'} onSubmit={submit}>
    <div className="dc-section-heading"><div><p className="dc-eyebrow">Twoja lista</p><h3>{entry ? 'Edytuj zadanie' : 'Co chcesz załatwić?'}</h3></div><button type="button" className="dc-icon-button" aria-label="Zamknij formularz zadania" onClick={onCancel} disabled={busy}><X size={18}/></button></div>
    <fieldset disabled={busy}>
      <label className="dc-field dc-wide">Tytuł zadania<input required maxLength={160} autoFocus placeholder="np. Sprawdź opłaty na koncie maklerskim" value={plan.title} onChange={e => setPlan({ ...plan, title: e.target.value })}/></label>
      <label className="dc-field dc-wide">Opis i następny krok<textarea maxLength={2000} rows={3} placeholder="Co dokładnie sprawdzić lub przygotować?" value={plan.notes} onChange={e => setPlan({ ...plan, notes: e.target.value })}/></label>
      <label className="dc-field">Obszar<select value={plan.category} onChange={e => setPlan({ ...plan, category: e.target.value as ActionCategory })}>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="dc-field">Termin<input type="date" min="2000-01-01" value={plan.due_date || ''} onChange={e => setPlan({ ...plan, due_date: e.target.value || null })}/></label>
      <label className="dc-check dc-wide"><input type="checkbox" checked={plan.priority === 'high'} onChange={e => setPlan({ ...plan, priority: e.target.checked ? 'high' : 'normal' })}/>Ważne zadanie</label>
    </fieldset>
    {error && <p role="alert" className="dc-error">{error}</p>}
    <div className="dc-editor-actions"><button type="button" className="dc-button" disabled={busy} onClick={onCancel}>Anuluj</button><button type="submit" className="dc-button dc-primary" disabled={busy}>{busy ? 'Zapisywanie…' : 'Zapisz zadanie'}</button></div>
  </form>;
}

export default function DashboardActions() {
  const [data, setData] = useState<ActionsWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [category, setCategory] = useState('all');
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(4);
  const [editor, setEditor] = useState<{ entry: DashboardAction | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  const working = useRef(false);
  const reload = useCallback(async () => {
    if (working.current) return;
    working.current = true; setLoading(true); setError('');
    try { const result = await actionsApi.get(); if (mounted.current) setData(result); }
    catch (err) { if (mounted.current) setError(extractErrorMessageFromUnknown(err)); }
    finally { working.current = false; if (mounted.current) setLoading(false); }
  }, []);
  useEffect(() => {
    mounted.current = true; void reload();
    return () => { mounted.current = false; };
  }, [reload]);
  const complete = async (item: DashboardAction) => {
    if (busy) return;
    setBusy(true); setNotice(''); setError('');
    try {
      await actionsApi.complete(item.task_id!, !item.completed_at, item.version!);
      // Apply the confirmed mutation before reloading: a failed GET must not leave a
      // stale completion button available for another write with the old version.
      setData(current => current ? { ...current, items: current.items.filter(row => row.key !== item.key), completed: current.completed.filter(row => row.key !== item.key) } : current);
      setNotice(item.completed_at ? 'Zadanie przywrócone.' : 'Zadanie wykonane. Znajdziesz je w historii.');
      await reload();
    } catch (err) { setError(extractErrorMessageFromUnknown(err)); }
    finally { if (mounted.current) setBusy(false); }
  };
  const changeFilter = (value: Filter) => { setFilter(value); setLimit(4); };
  const rows = (filter === 'completed' ? data?.completed : data?.items) || [];
  const visible = rows.filter(item => {
    if (category !== 'all' && item.category !== category) return false;
    if (query && !`${item.title} ${item.description} ${sources[item.source]}`.toLocaleLowerCase('pl-PL').includes(query.trim().toLocaleLowerCase('pl-PL'))) return false;
    if (filter === 'overdue' || filter === 'today' || filter === 'unscheduled') return item.timing === filter;
    if (filter === 'week') return Boolean(item.due_date && data && item.due_date >= data.as_of && item.due_date <= nextWeek(data.as_of));
    return true;
  });
  const stats = data?.stats;
  return <section className="dc-workspace" aria-labelledby="actions-heading">
    <div className="dc-section-heading dc-main-heading"><div><p className="dc-eyebrow">Od danych do działania</p><h2 id="actions-heading">Sprawy do załatwienia</h2><p className="dc-help">Przeglądy, płatności i Twoje zadania — zacznij od najważniejszego.</p></div><div className="dc-heading-actions"><button className="dc-icon-button" disabled={loading || busy || Boolean(editor)} onClick={() => void reload()} aria-label="Odśwież sprawy"><RefreshCw size={17} className={loading ? 'animate-spin' : ''}/></button><button className="dc-button dc-primary" onClick={() => { setEditor({ entry: null }); setNotice(''); }} disabled={loading || busy || Boolean(editor)}><Plus size={17}/>Dodaj zadanie</button></div></div>
    <div className="dc-stats">
      {([{ key: 'overdue', label: 'Po terminie', value: stats?.overdue, help: 'Sprawdź w pierwszej kolejności', icon: Flag }, { key: 'today', label: 'Na dziś', value: stats?.today, help: 'Termin przypada dzisiaj', icon: CalendarDays }, { key: 'week', label: 'Najbliższe 7 dni', value: stats?.week, help: 'Przygotuj się z wyprzedzeniem', icon: ClipboardList }, { key: 'completed', label: 'Wykonane zadania', value: stats?.completed, help: 'Historia Twoich zadań', icon: CheckCheck }] as const).map(stat => <button className={`dc-stat ${filter === stat.key ? 'is-selected' : ''}`} key={stat.key} aria-pressed={filter === stat.key} onClick={() => changeFilter(stat.key)}><span><stat.icon size={17}/>{stat.label}</span><strong>{stat.value ?? '—'}</strong><small>{stat.help}</small></button>)}
    </div>
    {editor && <TaskEditor key={editor.entry?.key || 'new'} entry={editor.entry} onCancel={() => setEditor(null)} onSaved={() => { setEditor(null); setNotice('Zadanie zapisane.'); changeFilter('all'); setCategory('all'); setQuery(''); void reload(); }}/ >}
    {notice && <p role="status" className="dc-notice">{notice}</p>}
    {error && <div className="dc-error" role="alert"><span>{error}{data && ' Lista może być nieaktualna.'}</span><button className="dc-button" disabled={loading} onClick={() => void reload()}>Spróbuj ponownie</button></div>}
    {data?.warnings.map(message => <p className="dc-warning" key={message}>{message}</p>)}
    <div className="dc-toolbar"><nav aria-label="Zakres spraw">{([{ key: 'all', label: 'Wszystkie' }, { key: 'overdue', label: 'Po terminie' }, { key: 'today', label: 'Dzisiaj' }, { key: 'week', label: '7 dni' }, { key: 'unscheduled', label: 'Bez terminu' }, { key: 'completed', label: 'Wykonane' }] as const).map(item => <button key={item.key} aria-pressed={filter === item.key} className={filter === item.key ? 'is-active' : ''} onClick={() => changeFilter(item.key)}>{item.label}</button>)}</nav><div className="dc-filters"><input type="search" aria-label="Szukaj sprawy" placeholder="Szukaj sprawy…" value={query} onChange={e => { setQuery(e.target.value); setLimit(4); }}/><select aria-label="Obszar spraw" value={category} onChange={e => { setCategory(e.target.value); setLimit(4); }}><option value="all">Wszystkie obszary</option>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div></div>
    <div className="dc-list" aria-busy={loading || busy}>
      {loading && !data ? <div role="status" className="dc-empty">Ładowanie spraw do załatwienia…</div> : !data ? <p className="dc-empty">Lista spraw jest chwilowo niedostępna.</p> : visible.length === 0 ? <div className="dc-empty"><CheckCheck size={28}/><h3>{filter === 'completed' ? 'Historia jest jeszcze pusta' : query || category !== 'all' || filter !== 'all' ? 'Brak spraw w tym widoku' : 'Nie ma teraz spraw do załatwienia'}</h3><p>{filter === 'completed' ? 'Wykonane własne zadania znajdziesz tutaj.' : 'Możesz dodać własne zadanie lub zaplanować przegląd w dzienniku inwestora.'}</p>{(filter !== 'all' || category !== 'all' || query) && <button className="dc-button" onClick={() => { changeFilter('all'); setCategory('all'); setQuery(''); }}>Pokaż wszystkie sprawy</button>}</div> : visible.slice(0, limit).map(item => {
        const Icon = icons[item.source];
        return <article className={`dc-row ${item.timing === 'overdue' ? 'is-overdue' : ''} ${item.completed_at ? 'is-completed' : ''}`} key={item.key}>
          <div className="dc-source-icon"><Icon size={20}/></div><div className="dc-row-body"><div className="dc-row-meta"><span>{sources[item.source]}</span>{item.priority === 'high' && <span className="dc-important"><Flag size={12}/>Ważne</span>}{item.timing === 'overdue' && <span className="dc-overdue">Po terminie</span>}{item.timing === 'today' && <span className="dc-today">Dzisiaj</span>}</div><h3>{item.title}</h3>{item.description && <p>{item.description}</p>}<div className="dc-row-details"><span><CalendarDays size={13}/>{item.due_date ? dateText(item.due_date) : 'Bez terminu'}</span><span>{categories[item.category]}</span>{item.amount != null && <strong>{money(item.amount)}</strong>}{item.completed_at && <span>Wykonano {dateText(item.completed_at.slice(0, 10))}</span>}</div></div>
          <div className="dc-row-actions">{item.href && <Link className="dc-button dc-action-link" to={item.href}>{item.action_label}<ArrowUpRight size={15}/></Link>}{item.source === 'manual' && <><button className="dc-icon-button" disabled={busy || loading || Boolean(editor)} aria-label={`Edytuj zadanie: ${item.title}`} onClick={() => setEditor({ entry: item })}><Pencil size={16}/></button><button className="dc-button" disabled={busy || loading || Boolean(editor)} onClick={() => void complete(item)}>{item.completed_at ? <RefreshCw size={15}/> : <Check size={16}/ >}{item.completed_at ? 'Przywróć' : 'Wykonane'}</button></>}</div>
        </article>;
      })}
    </div>
    {visible.length > limit && <button className="dc-button dc-more" onClick={() => setLimit(value => value+12)}>Pokaż kolejne sprawy ({visible.length-limit})</button>}
    {limit>4 && visible.length>4 && <button className="dc-button dc-more" onClick={() => setLimit(4)}>Zwiń do czterech spraw</button>}
    <div className="dc-footer"><p>{data ? `${dateText(data.as_of)} · ${countText(visible.length)} w widoku` : 'Sprawy z zapisanych danych aplikacji'} · Terminy automatyczne do 30 dni naprzód.</p><p>Sprawy z modułów znikają po rozliczeniu płatności, przeglądzie lub zmianie planu. „Wykonane” dotyczy własnych zadań.</p></div>
  </section>;
}
