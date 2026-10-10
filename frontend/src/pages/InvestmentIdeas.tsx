import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, BookOpen, Check, FileText, Lightbulb, Plus, RefreshCw, Search, X } from 'lucide-react';
import { ideasApi, type IdeaPlan, type Publication, type ResearchIdea, type ResearchWorkspace } from '../api_ideas';
import { radarApi } from '../api_radar';
import { extractErrorMessageFromUnknown } from '../http/response';
import './investmentIdeas.css';

const opinions:Record<string,string>={MENTION:'Wspomina',WATCH:'Obserwuje',HOLD:'Deklaruje posiadanie',BUY:'Deklaruje zakup',SELL:'Deklaruje sprzedaż'};
const stages:Record<string,string>={NEW:'Do sprawdzenia',ANALYZING:'Analizuję',WATCHING:'Obserwuję',REJECTED:'Odrzucone'};
const localDay=()=>new Date().toLocaleDateString('sv-SE');
const blank=(publication_id:number,ticker=''):IdeaPlan=>({publication_id,ticker,opinion:'MENTION',stage:'NEW',thesis:'',risks:'',evidence:'',horizon:''});
const dateText=(value:string|null)=>value?new Date(value.length===10?value+'T12:00:00':value).toLocaleDateString('pl-PL'):'Jeszcze nie sprawdzono';

export default function InvestmentIdeas(){
  const [month,setMonth]=useState(localDay().slice(0,7));
  const [source,setSource]=useState('all');
  const [query,setQuery]=useState('');
  const [topic,setTopic]=useState('investing');
  const [tab,setTab]=useState<'publications'|'ideas'|'compare'>('publications');
  const [data,setData]=useState<ResearchWorkspace>();
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [addLink,setAddLink]=useState(false);
  const [link,setLink]=useState({source_id:'podlacki',url:'',title:'',published_on:localDay()});
  const [edit,setEdit]=useState<{id?:number;plan:IdeaPlan}>();
  const [selected,setSelected]=useState<string[]>([]);
  const editor=useRef<HTMLFormElement>(null);
  useEffect(()=>{
    let active=true;setLoading(true);setError('');
    ideasApi.workspace(month).then(result=>{if(active)setData(result);}).catch(err=>{if(active)setError(extractErrorMessageFromUnknown(err));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[month]);
  useEffect(()=>{if(edit){editor.current?.scrollIntoView({behavior:'smooth',block:'center'});editor.current?.querySelector<HTMLInputElement>('input')?.focus();}},[edit?.id,edit?.plan.publication_id]);
  const run=async(task:()=>Promise<unknown>,message:string)=>{
    if(busy)return;setBusy(true);setError('');setNotice('');
    try{await task();setData(await ideasApi.workspace(month));setNotice(message);}
    catch(err){setError(extractErrorMessageFromUnknown(err));}
    finally{setBusy(false);}
  };
  const matches=(item:{source_id:string;title:string;ticker?:string;company_name?:string})=>(source==='all'||item.source_id===source)&&`${item.title} ${item.ticker||''} ${item.company_name||''}`.toLowerCase().includes(query.toLowerCase().trim());
  const publications=(data?.publications.filter(item=>matches(item)&&(topic==='all'||/spół|spol|akcj|portfel|ike|ikze|dywidend|pomysł|pomysl|typy|strategi/i.test(item.title)))||[])
    .sort((a,b)=>Number(/spół(?:ek|ki) na|typy na/i.test(b.title))-Number(/spół(?:ek|ki) na|typy na/i.test(a.title)));
  const ideas=data?.ideas.filter(matches)||[];
  const names=Object.fromEntries((data?.sources||[]).map(item=>[item.id,item.name]));
  const grouped=useMemo(()=>{
    const result:Record<string,ResearchIdea[]>={};
    for(const idea of ideas)(result[idea.ticker]??=[]).push(idea);
    return result;
  },[ideas]);
  const start=(publication:Publication,ticker='')=>{setEdit({plan:blank(publication.id,ticker)});setAddLink(false);};
  const change=(key:keyof IdeaPlan,value:string)=>setEdit(current=>current?{...current,plan:{...current.plan,[key]:value}}:current);
  const sourceCards=(data?.sources||[]).map(item=><article key={item.id} className="ri-source">
    <div className="ri-inline"><span className="ri-badge">{item.kind==='youtube'?'YouTube':'Tekstowe omówienia'}</span><span className={`ri-source-state ${item.status==='unavailable'?'ri-warning':''}`}>{item.status==='ok'?'Połączone':item.status==='unavailable'?'Niedostępne':'Gotowe do odświeżenia'}</span></div>
    <h2>{item.name}</h2><p>{item.kind==='youtube'?'Nowe filmy i opisy publikacji. Szczegóły wypowiedzi potwierdzasz w materiale.':'Artykuły wspominające Podlackiego. Autor tekstu i osoba cytowana mogą być różni.'}</p>
    <small>{dateText(item.checked_at)}{item.message&&` · ${item.message}`}</small>
    <a href={item.url} target="_blank" rel="noopener noreferrer">Przejdź do źródła <ArrowUpRight size={14}/></a>
  </article>);
  return <div className="ri-page">
    <header className="ri-heading"><div><p className="ri-eyebrow"><Lightbulb size={16}/> WARSZTAT INWESTORA</p><h1>Pomysły inwestycyjne</h1><p>Publikacje → spółki do sprawdzenia → Twoja własna analiza.</p></div>
      <div className="ri-inline"><button className="ri-button" disabled={busy} onClick={()=>{setAddLink(!addLink);setEdit(undefined);}}><Plus size={16}/>Dodaj materiał</button>
      <button className="ri-button ri-primary" disabled={busy} onClick={()=>void run(()=>ideasApi.refresh(),'Sprawdzono źródła. Ich status pokazuje, które udało się odczytać.')}><RefreshCw size={16}/>{busy?'Przetwarzanie…':'Odśwież publikacje'}</button></div></header>
    {error&&<div className="ri-error" role="alert">{error}</div>}{notice&&<div className="ri-notice" role="status"><Check size={16}/>{notice}</div>}
    <div className="ri-sources">{sourceCards}</div>
    <div className="ri-context"><BookOpen size={20}/><p><strong>Inspiracje z widocznym źródłem.</strong> Opisy filmów nie zastępują ich treści. Rozpoznane tickery są podpowiedziami do sprawdzenia; opinię autora potwierdzasz fragmentem lub momentem wypowiedzi. Odświeżanie pobiera ostatnie publikacje udostępniane przez źródła, a nie pełną historię kanałów. Comparic sprawdzamy wśród ostatnich 20 artykułów; starsze omówienia możesz dodać linkiem.</p></div>
    {addLink&&<form className="ri-panel ri-editor" onSubmit={event=>{event.preventDefault();void run(async()=>{await ideasApi.publication(link);setAddLink(false);setLink({...link,url:'',title:''});},'Zapisano materiał. Jeśli wybrany miesiąc jest inny, znajdziesz go w jego miesiącu publikacji.');}}>
      <div className="ri-section-heading"><h2>Dodaj link do materiału</h2><button type="button" className="ri-icon" aria-label="Zamknij dodawanie materiału" onClick={()=>setAddLink(false)}><X size={18}/></button></div>
      <p>Link zostanie zapisany bez pobierania treści. Autora i datę przypisujesz ręcznie. Starsze materiały trafią do odpowiedniego miesiąca.</p>
      <div className="ri-form-grid"><label>Źródło<select value={link.source_id} onChange={event=>setLink({...link,source_id:event.target.value})}>{data?.sources.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Data publikacji<input type="date" required max={localDay()} value={link.published_on} onChange={event=>setLink({...link,published_on:event.target.value})}/></label>
      <label className="ri-wide">Link do filmu lub artykułu<input type="url" required maxLength={2048} placeholder="https://…" value={link.url} onChange={event=>setLink({...link,url:event.target.value})}/></label>
      <label className="ri-wide">Tytuł materiału<input required maxLength={400} value={link.title} onChange={event=>setLink({...link,title:event.target.value})}/></label></div>
      <button className="ri-button ri-primary" disabled={busy}>Zapisz materiał</button></form>}
    {edit&&<form ref={editor} className="ri-panel ri-editor" aria-label="Twoja analiza spółki" onSubmit={event=>{event.preventDefault();void run(async()=>{await ideasApi.save(edit.plan,edit.id);setEdit(undefined);setTab('ideas');},'Zapisano Twoją analizę. Nie utworzono żadnej transakcji.');}}>
      <div className="ri-section-heading"><div><p className="ri-eyebrow">TWOJE WNIOSKI</p><h2>{edit.id?'Edytuj analizę':'Sprawdź pomysł'}</h2></div><button type="button" className="ri-icon" aria-label="Zamknij analizę" onClick={()=>setEdit(undefined)}><X size={18}/></button></div>
      <p>{data?.publications.find(item=>item.id===edit.plan.publication_id)?.title}</p>
      <div className="ri-form-grid"><label>Ticker<input required maxLength={32} list="research-instruments" placeholder="np. PZU.WA" value={edit.plan.ticker} onChange={event=>change('ticker',event.target.value.toUpperCase())}/></label>
      <label>Status mojej analizy<select value={edit.plan.stage} onChange={event=>change('stage',event.target.value)}>{Object.entries(stages).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></label>
      <label>Opinia autora · przypisujesz ręcznie<select value={edit.plan.opinion} onChange={event=>change('opinion',event.target.value)}>{Object.entries(opinions).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></label>
      <label>Horyzont autora<input maxLength={1000} placeholder="np. długoterminowo; nie podano" value={edit.plan.horizon} onChange={event=>change('horizon',event.target.value)}/></label>
      <label className="ri-wide">Potwierdzenie opinii: fragment lub moment filmu<textarea required={edit.plan.opinion!=='MENTION'} maxLength={1000} placeholder="np. 12:35 — autor mówi, że posiada akcje. Zaznacz, jeśli to wypowiedź gościa." value={edit.plan.evidence} onChange={event=>change('evidence',event.target.value)}/></label>
      <label>Moje argumenty za<textarea maxLength={4000} value={edit.plan.thesis} onChange={event=>change('thesis',event.target.value)}/></label>
      <label>Ryzyka i co chcę sprawdzić<textarea maxLength={4000} value={edit.plan.risks} onChange={event=>change('risks',event.target.value)}/></label></div>
      <button className="ri-button ri-primary" disabled={busy}>Zapisz analizę</button><datalist id="research-instruments">{data?.instruments.map(item=><option key={item.ticker} value={item.ticker}>{item.company_name}</option>)}</datalist></form>}
    <section className="ri-panel">
      <div className="ri-workspace-top"><nav aria-label="Widok pomysłów">{([['publications','Materiały'],['ideas','Moje analizy'],['compare','Porównanie']] as const).map(([key,label])=><button key={key} aria-pressed={tab===key} onClick={()=>setTab(key)}>{label}{key==='publications'?` · ${publications.length}`:key==='ideas'?` · ${ideas.length}`:''}</button>)}</nav>
        <label>Miesiąc<select aria-label="Miesiąc publikacji" disabled={busy} value={month} onChange={event=>{setMonth(event.target.value);setEdit(undefined);setSelected([]);}}><option value="">Wszystkie zapisane</option>{Array.from(new Set([localDay().slice(0,7),month,...(data?.months||[])])).filter(Boolean).sort().reverse().map(item=><option key={item} value={item}>{new Date(item+'-01T12:00:00').toLocaleDateString('pl-PL',{month:'long',year:'numeric'})}</option>)}</select></label></div>
      <div className="ri-filters"><label className="ri-search"><Search size={16}/><input aria-label="Szukaj materiału lub spółki" type="search" placeholder="Szukaj materiału lub spółki…" value={query} onChange={event=>setQuery(event.target.value)}/></label>
      <select aria-label="Filtr źródła" value={source} onChange={event=>setSource(event.target.value)}><option value="all">Wszystkie źródła</option>{data?.sources.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select>
      {tab==='publications'&&<select aria-label="Temat materiałów" value={topic} onChange={event=>setTopic(event.target.value)}><option value="investing">Spółki, portfele i strategie</option><option value="all">Wszystkie publikacje</option></select>}</div>
      {loading?<p className="ri-empty" role="status">Ładowanie zapisanych materiałów…</p>:tab==='publications'?<div className="ri-publications">
        {!publications.length&&<div className="ri-empty"><FileText size={28}/><h2>Brak materiałów w tym widoku</h2><p>Odśwież publikacje, wybierz wszystkie zapisane miesiące albo dodaj starszy materiał przez link.</p></div>}
        {publications.map(item=><article className="ri-publication" key={item.id}><div className="ri-inline"><span className="ri-badge">{names[item.source_id]}</span><time>{dateText(item.published_on)}</time>{item.provenance==='MANUAL'&&<span className="ri-badge">Dodano ręcznie</span>}</div>
          <h2><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}<ArrowUpRight size={17}/></a></h2>
          <p className="ri-help">{item.publisher&&`Autor / kanał: ${item.publisher} · `}{item.source_id==='comparic'?'Omówienie redakcyjne; sprawdź, czyja jest wypowiedź.':'Opis publikacji; pełną wypowiedź sprawdzisz w filmie.'}</p>
          {item.excerpt&&<details><summary>Opis ze źródła</summary><p className="ri-excerpt">{item.excerpt}</p></details>}
          {!!item.suggestions.length&&<div className="ri-suggestions"><span>Możliwe spółki · do potwierdzenia:</span>{item.suggestions.map(ticker=><button key={ticker} disabled={busy} onClick={()=>start(item,ticker)}>{ticker}<Plus size={12}/></button>)}</div>}
          <div className="ri-card-bottom"><span>{data?.ideas.filter(idea=>idea.publication_id===item.id).length||0} zapisanych analiz</span><button className="ri-button" disabled={busy} onClick={()=>start(item)}><Plus size={15}/>Przypisz spółkę i analizuj</button></div></article>)}</div>:tab==='ideas'?<div className="ri-idea-list">
        {!ideas.length&&<div className="ri-empty"><h2>Twoja lista do analizy jest pusta</h2><p>Otwórz Materiały, przypisz ticker i zapisz własne argumenty oraz ryzyka.</p></div>}
        {ideas.map(item=><article key={item.id} className="ri-idea"><div className="ri-section-heading"><div><p className="ri-eyebrow">{names[item.source_id]} · {dateText(item.published_on)}</p><h2>{item.ticker}<small>{item.company_name!==item.ticker?item.company_name:''}</small></h2></div><span className="ri-badge">{stages[item.stage]}</span></div>
          <a className="ri-material-link" href={item.url} target="_blank" rel="noopener noreferrer">{item.title}<ArrowUpRight size={14}/></a>
          <div className="ri-inline"><span className="ri-badge">Autor: {opinions[item.opinion]}</span>{item.is_held&&<span className="ri-badge ri-held">W moim portfelu</span>}{item.is_watched&&<span className="ri-badge">Na Radarze</span>}</div>
          {item.evidence&&<p className="ri-evidence">Potwierdzenie: {item.evidence}</p>}{item.horizon&&<p className="ri-help">Horyzont autora: {item.horizon}</p>}
          <div className="ri-analysis-columns"><div><h3>Moje argumenty</h3><p>{item.thesis||'Jeszcze nie zapisano.'}</p></div><div><h3>Ryzyka do sprawdzenia</h3><p>{item.risks||'Jeszcze nie zapisano.'}</p></div></div>
          <div className="ri-card-bottom"><label><input type="checkbox" checked={selected.includes(item.ticker)} disabled={!selected.includes(item.ticker)&&selected.length>=3} onChange={event=>setSelected(current=>event.target.checked?[...current,item.ticker]:current.filter(t=>t!==item.ticker))}/>Porównaj {item.ticker}</label>
          <div className="ri-inline"><button className="ri-button" disabled={busy} onClick={()=>setEdit({id:item.id,plan:{publication_id:item.publication_id,ticker:item.ticker,opinion:item.opinion,stage:item.stage,thesis:item.thesis,risks:item.risks,evidence:item.evidence,horizon:item.horizon}})}>Edytuj</button>
          {item.is_watched?<Link className="ri-button" to={`/radar?ticker=${encodeURIComponent(item.ticker)}`}>Otwórz Radar</Link>:<button className="ri-button" disabled={busy} onClick={()=>void run(()=>radarApi.addToWatchlist(item.ticker),`Dodano ${item.ticker} do Radaru.`)}>Dodaj do Radaru</button>}</div></div></article>)}</div>:<div className="ri-comparison">
        <p className="ri-help">Wybierz do trzech spółek w Moich analizach. Bez wyboru porównujemy wszystkie zapisane w tym widoku. Opinie są przypisane przez Ciebie — liczba wzmianek nie stanowi oceny spółki.</p>
        {Object.keys(grouped).length?<div className="ri-table-wrap"><table><thead><tr><th>Spółka</th><th>Materiały i opinie autorów</th><th>Moje argumenty</th><th>Ryzyka / pytania</th></tr></thead><tbody>{Object.entries(grouped).filter(([ticker])=>!selected.length||selected.includes(ticker)).map(([ticker,entries])=><tr key={ticker}><th>{ticker}<Link to={`/radar?ticker=${encodeURIComponent(ticker)}`}>Przejdź do Radaru</Link></th><td>{entries.map(item=><div key={item.id}><a href={item.url} target="_blank" rel="noopener noreferrer">{names[item.source_id]} · {dateText(item.published_on)}</a><p>{opinions[item.opinion]}</p><small>{item.evidence||'Tylko wzmianka; bez potwierdzonej decyzji.'}</small></div>)}</td><td>{entries.map(item=><p key={item.id}>{item.thesis||'Brak własnej analizy.'}</p>)}</td><td>{entries.map(item=><p key={item.id}>{item.risks||'Do uzupełnienia.'}</p>)}</td></tr>)}</tbody></table></div>:<div className="ri-empty">Najpierw zapisz analizę spółki z wybranego materiału.</div>}</div>}
    </section>
    <aside className="ri-context"><FileText size={20}/><p><strong>Portfel Zawodu Inwestora na myfund.</strong> Dostęp automatyczny nie został potwierdzony. <a href="https://myfund.pl/index.php?raport=ListaPortfeliPublicznych" target="_blank" rel="noopener noreferrer">Otwórz katalog portfeli</a>. Skład portfela i propozycje autora to różne informacje — nie przypisujemy zakupów z samego tytułu filmu.</p></aside>
  </div>;
}
