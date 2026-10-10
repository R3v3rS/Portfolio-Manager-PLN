import { chartTooltip } from '../charts/chartTheme';
import { useEffect, useRef, useState } from 'react';
import { X, ArrowUpRight, Save } from 'lucide-react';
import { Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from 'recharts';
import type { RadarItem, RadarNotes } from '../../types';
import { radarApi } from '../../api_radar';
import { extractErrorMessageFromUnknown } from '../../http/response';
import { change, dateText, emptyNotes, number, tone, type HistoryPoint } from './radarModel';

export default function RadarDetails({ item, onClose, onAnalysis, onSaved }: { item: RadarItem; onClose: () => void; onAnalysis: () => void; onSaved: () => Promise<void> }) {
  const [tab, setTab] = useState<'overview' | 'notes'>('overview');
  const [notes, setNotes] = useState<RadarNotes>({ ...emptyNotes, ...item.notes });
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let live = true;
    radarApi.history(item.ticker).then(data => { if (live) setHistory(data); })
      .catch(() => { if (live) setError('Nie udało się pobrać historii cen.'); })
      .finally(() => { if (live) setLoading(false); });
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { live = false; document.body.style.overflow = previousOverflow; previous?.focus(); };
  }, [item.ticker]);
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError(''); setMessage('');
    try { await radarApi.saveNotes(item.ticker, notes); await onSaved(); setMessage('Zapisano notatkę i poziom obserwacji.'); }
    catch (err) { setError(extractErrorMessageFromUnknown(err)); }
    finally { setSaving(false); }
  };
  return <div className="rd-overlay" onClick={onClose}>
    <div ref={panel} className="rd-drawer" role="dialog" aria-modal="true" aria-labelledby="radar-detail-title" onClick={event => event.stopPropagation()} onKeyDown={event => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab') return;
      const focusable = Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input, select, textarea') || []);
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
      <header><div><span className="rd-eyebrow">KARTA INSTRUMENTU</span><h2 id="radar-detail-title">{item.ticker}</h2><p>{item.company_name}</p></div><button className="rd-icon" onClick={onClose} aria-label="Zamknij szczegóły"><X size={20}/></button></header>
      <nav className="rd-tabs" aria-label="Szczegóły instrumentu"><button aria-current={tab === 'overview' ? 'page' : undefined} onClick={() => setTab('overview')}>Przegląd</button><button aria-current={tab === 'notes' ? 'page' : undefined} onClick={() => setTab('notes')}>Moja obserwacja</button></nav>
      {error && <p className="rd-error" role="alert">{error}</p>}
      {tab === 'overview' ? <div className="rd-detail-body">
        <div className="rd-detail-price"><strong>{number(item.price)} <small>{item.currency || 'waluta nieznana'}</small></strong><span className={tone(item.change_1d)}>{change(item.change_1d)} · 1D</span><p>Zapis notowania: {dateText(item.last_updated_at)}</p></div>
        <div className="rd-chart" aria-label={`Historia ceny ${item.ticker}`}>
          {loading ? <p className="rd-empty">Ładowanie historii…</p> : history.length < 2 ? <p className="rd-empty">Brak wystarczającej zapisanej historii do narysowania wykresu.</p> : <ResponsiveContainer width="100%" height={240}><LineChart data={history}><CartesianGrid stroke="var(--line)" vertical={false}/><XAxis dataKey="date" tickFormatter={dateText} minTickGap={50} tick={{fontSize:11}}/><YAxis width={60} domain={['auto','auto']} tick={{fontSize:11}}/><Tooltip contentStyle={chartTooltip} labelFormatter={label => dateText(String(label))} formatter={value => [`${number(Number(value))} ${item.currency || ''}`, 'Cena']}/>{item.notes?.target_price != null && <ReferenceLine y={item.notes.target_price} stroke="#e5bc70" strokeDasharray="5 5" ifOverflow="extendDomain" label={{ value: 'Mój poziom', fill: '#e5bc70', position: 'insideTopLeft' }} />}<Line isAnimationActive={false} dataKey="close_price" type="linear" stroke="#67ded2" strokeWidth={2} dot={false}/></LineChart></ResponsiveContainer>}
        </div>
        {history.length > 1 && <p className="rd-help">{dateText(history[0].date)} – {dateText(history[history.length - 1].date)} · {history.length} zapisanych sesji. Historia ceny w walucie instrumentu.</p>}
        {item.notes?.target_price != null && item.price != null && item.price > 0 && <p className="rd-help">Mój poziom: {number(item.notes.target_price)} {item.currency} · od obecnej ceny: {change((item.notes.target_price / item.price - 1) * 100)}</p>}
        <div className="rd-detail-stats"><div><span>7 dni</span><strong className={tone(item.change_7d)}>{change(item.change_7d)}</strong></div><div><span>1 miesiąc</span><strong className={tone(item.change_1m)}>{change(item.change_1m)}</strong></div><div><span>1 rok</span><strong className={tone(item.change_1y)}>{change(item.change_1y)}</strong></div><div><span>Posiadane jednostki</span><strong>{number(item.quantity,4)}</strong></div></div>
        <p className="rd-help">Sektor: {item.sector || 'Nieprzypisany'} · {item.is_watched ? 'Na liście obserwowanych' : 'Na radarze dzięki pozycji w portfelu'}</p>
        <button className="rd-button rd-primary" onClick={onAnalysis}>Fundamenty i wskaźniki <ArrowUpRight size={16}/></button>
        <Link className="rd-button" to={`/journal?new=1&ticker=${encodeURIComponent(item.ticker)}`}>Zapisz decyzję w dzienniku <ArrowUpRight size={16}/></Link>
        <p className="rd-help">Analiza wymaga pobrania danych od dostawcy. Ocena spółki nie jest stosowana do ETF; niepełne dane nie oznaczają słabej inwestycji.</p>
      </div> : <form className="rd-detail-body" onSubmit={save}>
        <label>Dlaczego obserwuję?<textarea maxLength={4000} rows={4} value={notes.thesis} onChange={e => setNotes({...notes, thesis:e.target.value})} placeholder="Pomysł, argumenty, na co czekasz…"/></label>
        <label>Co podważa mój pomysł?<textarea maxLength={4000} rows={3} value={notes.invalidation} onChange={e => setNotes({...notes, invalidation:e.target.value})} placeholder="Ryzyka i warunki do ponownej oceny"/></label>
        <label>Data następnego przeglądu<input type="date" value={notes.review_date || ''} onChange={e => setNotes({...notes, review_date:e.target.value || null})}/></label>
        <fieldset><legend>Twój poziom obserwacji · {item.currency || 'waluta instrumentu'}</legend><div className="rd-inline"><label>Warunek<select value={notes.target_direction} onChange={e => setNotes({...notes,target_direction:e.target.value as 'above'|'below'})}><option value="below">Cena ≤ poziom</option><option value="above">Cena ≥ poziom</option></select></label><label>Poziom ceny<input type="number" min="0.000001" step="any" value={notes.target_price ?? ''} onChange={e => setNotes({...notes,target_price:e.target.value === '' ? null : Number(e.target.value)})} placeholder="Bez alertu"/></label></div></fieldset>
        <p className="rd-help">Warunek jest sprawdzany podczas działania radaru, dla notowań zapisanych w ciągu ostatnich 72 godzin. Puste pole wyłącza alert. Notatki zapisujemy w lokalnej bazie aplikacji.</p>
        <button className="rd-button rd-primary" disabled={saving}><Save size={16}/>{saving ? 'Zapisywanie…' : 'Zapisz obserwację'}</button><p role="status" className="rd-positive">{message}</p>
      </form>}
    </div>
  </div>;
}
