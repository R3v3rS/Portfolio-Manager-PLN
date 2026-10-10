import { useState } from 'react';
import { journalApi, type JournalDetail, type ReviewPlan } from '../../api_journal';
import { extractErrorMessageFromUnknown } from '../../http/response';
import { localToday, outcomes, statuses } from './journalModel';

export default function JournalReviewEditor({entry,onSaved,onCancel}:{entry:JournalDetail;onSaved:()=>Promise<void>;onCancel:()=>void}) {
  const [form,setForm] = useState<ReviewPlan>({version:entry.version,review_date:localToday(),outcome:'NOTE',notes:'',lessons:'',next_review_date:null,entry_status:entry.status});
  const [busy,setBusy] = useState(false);const [error,setError] = useState('');
  const change=<K extends keyof ReviewPlan>(key:K,value:ReviewPlan[K])=>setForm(current=>({...current,[key]:value}));
  return <form className="journal-panel journal-editor" aria-label="Przegląd decyzji" onSubmit={async e=>{e.preventDefault();if(busy)return;setBusy(true);setError('');try{await journalApi.review(entry.id,form);await onSaved();}catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}}}>
    <header className="journal-heading"><div><p className="page-eyebrow">WRÓĆ DO PIERWOTNYCH ZAŁOŻEŃ</p><h2>Przegląd: {entry.title}</h2><p>Porównaj nowe informacje z tezą. Wnioski zostaną dopisane do historii.</p></div><button type="button" className="journal-button" disabled={busy} onClick={onCancel}>Anuluj</button></header>
    <blockquote className="journal-original"><span>Teza przed przeglądem</span>{entry.thesis||'Nie zapisano tezy.'}</blockquote>
    {error&&<p className="journal-alert" role="alert">{error}</p>}<fieldset disabled={busy}><div className="journal-form-grid"><label>Data przeglądu<input required type="date" min={entry.entry_date} max={localToday()} value={form.review_date} onChange={e=>change('review_date',e.target.value)} /></label><label>Ocena tezy<select value={form.outcome} onChange={e=>change('outcome',e.target.value as ReviewPlan['outcome'])}>{Object.entries(outcomes).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label className="journal-span">Co się zmieniło i co robię dalej?<textarea required rows={5} maxLength={5000} value={form.notes} onChange={e=>change('notes',e.target.value)} placeholder="Nowe fakty, porównanie z założeniami i kolejna decyzja." /></label><label className="journal-span">Wnioski na przyszłość<textarea rows={4} maxLength={5000} value={form.lessons} onChange={e=>change('lessons',e.target.value)} placeholder="Co warto powtórzyć, a czego unikać?" /></label>
      <label>Status po przeglądzie<select value={form.entry_status} onChange={e=>change('entry_status',e.target.value as ReviewPlan['entry_status'])}>{Object.entries(statuses).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><label>Kolejny termin przeglądu<input aria-label="Kolejny termin przeglądu" aria-describedby="journal-next-review-help" type="date" min={form.review_date} value={form.next_review_date??''} onChange={e=>change('next_review_date',e.target.value||null)} /><small id="journal-next-review-help">Puste pole usuwa termin następnego przeglądu.</small></label></div></fieldset>
    <footer className="journal-form-footer"><p>Przegląd dopisuje notatkę; nie nadpisuje pierwotnej tezy. Starszy przegląd nie zmienia terminu ustalonego przez nowszy.</p><button className="journal-button primary" disabled={busy} type="submit">{busy?'Zapisywanie…':'Zapisz przegląd'}</button></footer>
  </form>;
}
