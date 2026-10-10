import { useEffect, useState } from 'react';
import { Archive, BookOpen, Download, Plus, Search } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { journalApi, type JournalDetail as Detail, type JournalFilters, type JournalWorkspace } from '../api_journal';
import JournalEditor from '../components/journal/JournalEditor';
import JournalReviewEditor from '../components/journal/JournalReviewEditor';
import JournalDetail from '../components/journal/JournalDetail';
import { dateText, kinds, statuses } from '../components/journal/journalModel';
import { extractErrorMessageFromUnknown } from '../http/response';
import '../components/journal/journal.css';

const baseFilters:JournalFilters={q:'',status:'all',kind:'all',portfolio:'',archived:'0',due:'0',tag:'',ticker:'',page:1};
export default function InvestorJournal() {
  const [params] = useSearchParams();
  const initialPortfolio = Number(params.get('portfolio'))||undefined;
  const initialTicker = params.get('ticker')?.trim().toUpperCase()||'';
  const [filters,setFilters] = useState<JournalFilters>({...baseFilters,portfolio:initialPortfolio?String(initialPortfolio):'',ticker:initialTicker});
  const [query,setQuery] = useState('');
  const [data,setData] = useState<JournalWorkspace>();
  const [loading,setLoading] = useState(true);
  const [selected,setSelected] = useState<number|null>(Number(params.get('entry'))||null);
  const [detail,setDetail] = useState<Detail>();
  const [editor,setEditor] = useState<'new'|'edit'|'review'|null>(params.get('new')==='1'?'new':null);
  const [editTarget,setEditTarget] = useState<Detail>();
  const [refresh,setRefresh] = useState(0);
  const [error,setError] = useState('');
  const [detailError,setDetailError] = useState('');
  const [notice,setNotice] = useState('');
  const [busy,setBusy] = useState(false);
  const effectiveId = selected??data?.entries[0]?.id;
  useEffect(()=>{const timer=window.setTimeout(()=>setFilters(current=>current.q===query?current:{...current,q:query,page:1}),250);return()=>window.clearTimeout(timer);},[query]);
  useEffect(()=>{
    let active=true;setLoading(true);setError('');
    journalApi.list(filters).then(result=>{if(active)setData(result);}).catch(err=>{if(active)setError(extractErrorMessageFromUnknown(err));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[filters,refresh]);
  useEffect(()=>{
    let active=true;setDetail(undefined);setDetailError('');
    if(effectiveId)journalApi.detail(effectiveId).then(result=>{if(active)setDetail(result);}).catch(err=>{if(active)setDetailError(extractErrorMessageFromUnknown(err));});
    return()=>{active=false;};
  },[effectiveId,refresh]);
  const change = <K extends keyof JournalFilters>(key:K,value:JournalFilters[K]) => {setFilters(current=>({...current,[key]:value,page:key==='page'?Number(value):1}));setSelected(null);setEditor(null);};
  const saved = async (id:number,archived=false) => {
    setEditor(null);setSelected(id);setQuery('');setFilters({...baseFilters,archived:archived?'1':'0'});setRefresh(value=>value+1);
    setNotice('Zapisano w dzienniku. Wcześniejsze wersje i przeglądy pozostają w historii.');
  };
  const cancelEditor = () => {setEditor(null);setRefresh(value=>value+1);};
  const archive = async () => {
    if(!detail||busy)return;setBusy(true);setError('');
    try{await journalApi.archive(detail.id,!detail.is_archived,detail.version);await saved(detail.id,!detail.is_archived);setNotice(detail.is_archived?'Wpis przywrócony.':'Wpis przeniesiono do archiwum. Możesz go przywrócić.');}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const download = async () => {
    setBusy(true);setError('');
    try{const exported=await journalApi.export();const url=URL.createObjectURL(new Blob([JSON.stringify(exported,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`dziennik-inwestora-${exported.exported_at.slice(0,10)}.json`;link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);setNotice('Pobrano kopię całego dziennika z przeglądami i historią zmian, także wpisami z archiwum.');}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  return <div className="page-stack investor-journal"><header className="journal-heading journal-page-heading"><div><p className="page-eyebrow">TWOJE DECYZJE, ZAŁOŻENIA I WNIOSKI</p><h1>Dziennik inwestora</h1><p>Zapisz, dlaczego inwestujesz. Wracaj do faktów, weryfikuj tezy i ucz się z własnych decyzji.</p></div><div className="journal-actions"><button className="journal-button" disabled={busy||!data||Boolean(editor)} onClick={download}><Download size={16}/>Eksport</button><button className="journal-button primary" disabled={busy||!data||Boolean(editor)} onClick={()=>{setEditor('new');setNotice('');}}><Plus size={17}/>Nowy wpis</button></div></header>
    {notice&&<p className="journal-success" role="status">{notice}</p>}{error&&<div className="journal-alert" role="alert"><p>{error}</p><button className="journal-button" disabled={busy} onClick={()=>setRefresh(value=>value+1)}>Wczytaj ponownie</button></div>}
    {!data?loading?<p className="journal-panel" role="status">Ładowanie dziennika…</p>:null:editor==='new'||(editor==='edit'&&editTarget)?<JournalEditor key={editor==='new'?'new':editTarget!.id} entry={editor==='edit'?editTarget:undefined} portfolios={data.portfolios} initialPortfolio={initialPortfolio} initialTicker={initialTicker} onCancel={cancelEditor} onSaved={id=>saved(id,editor==='edit'&&Boolean(editTarget?.is_archived))}/>:editor==='review'&&editTarget?<JournalReviewEditor entry={editTarget} onCancel={cancelEditor} onSaved={()=>saved(editTarget.id)}/>:<>
      <section className="journal-stats" aria-label="Podsumowanie dziennika"><button onClick={()=>{setFilters({...baseFilters,status:'ACTIVE'});setSelected(null);setQuery('');}}><span>Aktywne tezy</span><strong>{data.stats.active}</strong></button><button onClick={()=>{setFilters({...baseFilters,status:'WATCHING'});setSelected(null);setQuery('');}}><span>Do obserwacji</span><strong>{data.stats.watching}</strong></button><button className={data.stats.due?'is-due':''} onClick={()=>{setFilters({...baseFilters,due:'1'});setSelected(null);setQuery('');}}><span>Przegląd na dziś lub zaległy</span><strong>{data.stats.due}</strong></button><button onClick={()=>{setFilters({...baseFilters,status:'CLOSED'});setSelected(null);setQuery('');}}><span>Zamknięte tezy</span><strong>{data.stats.closed}</strong></button></section>
      <section className="journal-panel journal-filters" aria-label="Filtry dziennika"><label className="journal-search"><Search size={16}/><input aria-label="Szukaj w dzienniku" maxLength={200} value={query} onChange={e=>{setQuery(e.target.value);setSelected(null);}} placeholder="Szukaj w tytule, symbolu i tezach…"/></label><label>Status<select value={filters.status} onChange={e=>change('status',e.target.value)}><option value="all">Wszystkie statusy</option>{Object.entries(statuses).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><label>Decyzja<select value={filters.kind} onChange={e=>change('kind',e.target.value)}><option value="all">Wszystkie decyzje</option>{Object.entries(kinds).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><label>Portfel<select value={filters.portfolio} onChange={e=>change('portfolio',e.target.value)}><option value="">Wszystkie portfele</option>{data.portfolios.map(p=><option key={p.id} value={p.id}>{p.name}{p.is_archived?' · archiwum':''}</option>)}</select></label><label>Etykieta<select value={filters.tag} onChange={e=>change('tag',e.target.value)}><option value="">Wszystkie etykiety</option>{data.tags.map(tag=><option key={tag}>{tag}</option>)}</select></label>
        <div className="journal-filter-actions"><button className="journal-button" aria-pressed={filters.archived==='1'} onClick={()=>change('archived',filters.archived==='1'?'0':'1')}><Archive size={14}/>Archiwum ({data.stats.archived})</button><button className="journal-button" aria-pressed={filters.due==='1'} onClick={()=>change('due',filters.due==='1'?'0':'1')}>Do przeglądu</button>{filters.ticker&&<span>Symbol: <b>{filters.ticker}</b></span>}<button className="journal-button" onClick={()=>{setFilters(baseFilters);setQuery('');setSelected(null);}}>Wyczyść filtry</button><span>{loading?'Wczytywanie…':`${data.total} wpisów`}</span></div></section>
      {!data.entries.length&&!effectiveId?<section className="journal-panel journal-empty"><BookOpen size={34}/><h2>{data.stats.active+data.stats.watching+data.stats.closed+data.stats.archived===0?'Zacznij od jednej decyzji':'Brak wpisów dla tych filtrów'}</h2><p>Zapisz argumenty, ryzyka i warunki zmiany zdania. Przy kolejnym przeglądzie porównasz je z tym, co wydarzyło się później.</p><button className="journal-button primary" onClick={()=>setEditor('new')}>Dodaj wpis do dziennika</button></section>:<div className="journal-workspace"><aside className="journal-list" aria-label="Lista wpisów">{data.entries.map(entry=><button key={entry.id} className={`journal-list-item ${effectiveId===entry.id?'is-selected':''}`} aria-pressed={effectiveId===entry.id} onClick={()=>{setSelected(entry.id);setNotice('');}}><span className="journal-card-meta">{kinds[entry.kind]} · {dateText(entry.entry_date)}</span><strong>{entry.title}</strong><span>{[entry.ticker,entry.portfolio_name].filter(Boolean).join(' · ')||'Decyzja ogólna'}</span><span className="journal-card-status">{statuses[entry.status]}{entry.review_due&&<b>Do przeglądu</b>}</span><small>{entry.review_count} przeglądów · termin {dateText(entry.review_date)}</small></button>)}{data.total>data.page_size&&<div className="journal-pagination"><button className="journal-button" disabled={data.page<=1||loading} onClick={()=>change('page',data.page-1)}>Poprzednia</button><span>{data.page}/{Math.ceil(data.total/data.page_size)}</span><button className="journal-button" disabled={data.page*data.page_size>=data.total||loading} onClick={()=>change('page',data.page+1)}>Następna</button></div>}</aside>
      {detailError?<div className="journal-alert" role="alert"><p>{detailError}</p><button className="journal-button" onClick={()=>setRefresh(value=>value+1)}>Wczytaj wpis ponownie</button></div>:detail?<JournalDetail entry={detail} busy={busy} onEdit={()=>{setEditTarget(detail);setEditor('edit');}} onReview={()=>{setEditTarget(detail);setEditor('review');}} onArchive={archive}/>:<p className="journal-panel" role="status">Ładowanie wpisu…</p>}</div>}
    </>}
  </div>;
}
