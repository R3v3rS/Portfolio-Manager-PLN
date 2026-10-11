import { useState } from 'react';
import type { JournalDetail, JournalPlan, JournalWorkspace } from '../../api_journal';
import { journalApi } from '../../api_journal';
import { extractErrorMessageFromUnknown } from '../../http/response';
import { kinds, localToday, statuses } from './journalModel';

export default function JournalEditor({entry,portfolios,initialPortfolio,initialTicker,onSaved,onCancel}:{entry?:JournalDetail;portfolios:JournalWorkspace['portfolios'];initialPortfolio?:number;initialTicker?:string;onSaved:(id:number)=>Promise<void>;onCancel:()=>void}) {
  const [form,setForm] = useState<JournalPlan>(() => entry ? {...entry} : {title:'',entry_date:localToday(),kind:'IDEA',status:'WATCHING',ticker:initialTicker||null,portfolio_id:portfolios.some(p=>p.id===initialPortfolio&&!p.is_archived)?initialPortfolio!:null,confidence:null,thesis:'',risks:'',invalidation:'',exit_plan:'',review_date:null,tags:[]});
  const [tagText,setTagText] = useState(entry?.tags.join(', ')||'');
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const change = <K extends keyof JournalPlan>(key:K,value:JournalPlan[K]) => setForm(current=>({...current,[key]:value}));
  return <form className="journal-panel journal-editor" aria-label={entry?'Edycja wpisu':'Nowy wpis dziennika'} onSubmit={async e=>{
    e.preventDefault();if(busy)return;setBusy(true);setError('');
    const plan:JournalPlan = {title:form.title.trim(),entry_date:form.entry_date,kind:form.kind,status:form.status,ticker:form.ticker?.trim().toUpperCase()||null,portfolio_id:form.portfolio_id,confidence:form.confidence,thesis:form.thesis.trim(),risks:form.risks.trim(),invalidation:form.invalidation.trim(),exit_plan:form.exit_plan.trim(),review_date:form.review_date||null,tags:tagText.split(',').map(tag=>tag.trim()).filter(Boolean)};
    try {const result=entry?await journalApi.update(entry.id,plan,entry.version):await journalApi.create(plan);await onSaved(result.id);}
    catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}
  }}><header className="journal-heading"><div><p className="page-eyebrow">ZAPISZ SWOJE ROZUMOWANIE</p><h2>{entry?'Edytuj wpis':'Nowa decyzja lub obserwacja'}</h2><p>{entry?'Poprzednia wersja pozostanie w historii wpisu.':'Zapisz, co wiesz teraz i co skłoni Cię do zmiany zdania.'}</p></div><button className="journal-button" type="button" disabled={busy} onClick={onCancel}>Anuluj</button></header>
    {error&&<p className="journal-alert" role="alert">{error}</p>}
    <fieldset disabled={busy}><div className="journal-form-grid"><label className="journal-span">Tytuł wpisu<input required maxLength={150} value={form.title} onChange={e=>change('title',e.target.value)} placeholder="Np. Dlaczego zwiększam udział ETF-u?" /></label>
      <label>Data decyzji<input required type="date" min="2000-01-01" max={localToday()} value={form.entry_date} onChange={e=>change('entry_date',e.target.value)} /></label><label>Rodzaj decyzji<select value={form.kind} onChange={e=>change('kind',e.target.value as JournalPlan['kind'])}>{Object.entries(kinds).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <label>Status tezy<select value={form.status} onChange={e=>change('status',e.target.value as JournalPlan['status'])}>{Object.entries(statuses).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><label>Portfel<select value={form.portfolio_id??''} onChange={e=>change('portfolio_id',e.target.value?Number(e.target.value):null)}><option value="">Bez przypisanego portfela</option>{portfolios.filter(p=>!p.is_archived||p.id===entry?.portfolio_id).map(p=><option key={p.id} value={p.id}>{p.name}{p.is_archived?' · archiwum':''}</option>)}</select></label>
      <label>Symbol instrumentu<input maxLength={40} value={form.ticker??''} onChange={e=>change('ticker',e.target.value)} placeholder="Np. CSPX.L · opcjonalnie" /></label><label>Pewność tezy<select value={form.confidence??''} onChange={e=>change('confidence',e.target.value?Number(e.target.value):null)}><option value="">Bez oceny</option>{[1,2,3,4,5].map(n=><option key={n} value={n}>{n}/5{n===1?' · niska':n===5?' · wysoka':''}</option>)}</select></label>
      <label className="journal-span">Teza i powód decyzji<textarea rows={5} maxLength={5000} value={form.thesis} onChange={e=>change('thesis',e.target.value)} placeholder="Co przemawia za tą decyzją? Jakie fakty ją wspierają?" /></label>
      <label>Najważniejsze ryzyka<textarea rows={4} maxLength={5000} value={form.risks} onChange={e=>change('risks',e.target.value)} placeholder="Co może pójść inaczej, niż zakładam?" /></label><label>Co podważy moją tezę?<textarea rows={4} maxLength={5000} value={form.invalidation} onChange={e=>change('invalidation',e.target.value)} placeholder="Zdarzenia lub dane, po których zmienię zdanie." /></label>
      <label className="journal-span">Warunki zmiany lub wyjścia<textarea rows={3} maxLength={5000} value={form.exit_plan} onChange={e=>change('exit_plan',e.target.value)} placeholder="Kiedy utrzymam, ograniczę lub zamknę pozycję?" /></label>
      <label>Termin przeglądu<input type="date" min={form.entry_date} value={form.review_date??''} onChange={e=>change('review_date',e.target.value||null)} /></label><label>Etykiety<input aria-label="Etykiety" aria-describedby="journal-tags-help" value={tagText} maxLength={215} onChange={e=>setTagText(e.target.value)} placeholder="Np. ETF, emerytura · oddziel przecinkami" /><small id="journal-tags-help">Do 8 etykiet, każda do 25 znaków.</small></label>
    </div></fieldset><footer className="journal-form-footer"><p>To zapis decyzji. Nie składa zlecenia ani nie zmienia portfela.</p><button className="journal-button primary" disabled={busy} type="submit">{busy?'Zapisywanie…':entry?'Zapisz zmiany':'Zapisz wpis'}</button></footer>
  </form>;
}
