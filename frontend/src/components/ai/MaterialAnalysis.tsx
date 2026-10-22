import {useEffect,useRef,useState} from 'react';
import type {Publication} from '../../api_ideas';
import {investmentAnalysisApi as api,type MaterialClaim,type MaterialReview} from '../../api_investment_analysis';
import {extractErrorMessageFromUnknown as errorText} from '../../http/response';
import AISettings from './AISettings';
import './investmentAssistant.css';
const opinions={MENTION:'Wspomina',WATCH:'Obserwuje',HOLD:'Deklaruje posiadanie',BUY:'Deklaruje zakup',SELL:'Deklaruje sprzedaż'};
function Claim({claim,index,reviewId,saved,onSaved}:{claim:MaterialClaim;index:number;reviewId:string;saved?:number;onSaved:()=>void}){
 const [draft,setDraft]=useState(claim),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const change=(key:keyof MaterialClaim,value:string)=>{setDraft({...draft,[key]:value});setConfirmed(false);};
 return <form className="ia-material" onSubmit={async e=>{e.preventDefault();if(!confirmed||busy)return;setBusy(true);setError('');try{await api.confirmMaterial(reviewId,index,{...draft,confirmed:true});onSaved();}catch(e){setError(errorText(e));}finally{setBusy(false);}}}>
 <h3>{claim.company||claim.ticker||`Wzmianka ${index+1}`}</h3><a href={claim.source_url} target="_blank" rel="noreferrer">{claim.seconds==null?'Otwórz źródło':`Sprawdź moment ${Math.floor(claim.seconds/60)}:${String(claim.seconds%60).padStart(2,'0')}`}</a>
 <p>{claim.matched_excerpt?'Fragment znaleziony we wklejonym tekście; sprawdź przypisanie osoby i kontekst.':'Wymaga porównania z materiałem. Opis filmu jest parafrazą AI, nie cytatem.'}</p>
 {saved?<p role="status">Zapisano i przypisano do Twoich analiz.</p>:<fieldset disabled={busy} style={{border:0,padding:0}}>
 <div className="ia-grid"><label>Ticker<input required maxLength={32} value={draft.ticker} onChange={e=>change('ticker',e.target.value.toUpperCase())}/></label><label>Opinia autora<select value={draft.opinion} onChange={e=>change('opinion',e.target.value)}>{Object.entries(opinions).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label></div>
 <label>Potwierdzenie i osoba wypowiadająca się<textarea required maxLength={1000} value={draft.evidence} onChange={e=>change('evidence',e.target.value)}/></label><label>Argumenty / teza<textarea maxLength={4000} value={draft.thesis} onChange={e=>change('thesis',e.target.value)}/></label><label>Ryzyka<textarea maxLength={4000} value={draft.risks} onChange={e=>change('risks',e.target.value)}/></label><label>Horyzont<input maxLength={1000} value={draft.horizon} onChange={e=>change('horizon',e.target.value)}/></label>
 <label className="ia-check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Sprawdziłem źródło, ticker i przypisanie opinii.</label><button disabled={!confirmed||!draft.ticker||!draft.evidence}>Potwierdź i zapisz analizę</button></fieldset>}{error&&<p role="alert">{error}</p>}</form>;
}
export default function MaterialAnalysis({publication,onClose,onSaved}:{publication:Publication;onClose:()=>void;onSaved:()=>void}){
 const video=/^https:\/\/(www\.)?(youtube\.com|youtu\.be)\//.test(publication.url);
 const [kind,setKind]=useState(video?'VIDEO':'ARTICLE'),[text,setText]=useState(''),[reviews,setReviews]=useState<MaterialReview[]>([]),[selected,setSelected]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [article,setArticle]=useState<{text:string;captured_at:string;source_url:string;truncated:boolean}|null>(null);
 useEffect(()=>{let live=true;if(!video)api.article(publication.id).then(x=>{if(live)setArticle(x);}).catch(e=>{if(live)setError(errorText(e));});return()=>{live=false;};},[publication.id,video]);
 const fetchArticle=async()=>{setBusy(true);setError('');try{setArticle(await api.fetchArticle(publication.id));}catch(e){setError(errorText(e));}finally{setBusy(false);}};
 const request=useRef<{key:string;id:string}>();
 useEffect(()=>{let live=true;api.reviews(publication.id).then(r=>{if(live){setReviews(r);setSelected(r[0]?.id||'');}}).catch(e=>{if(live)setError(errorText(e));});return()=>{live=false;};},[publication.id]);
 const active=reviews.find(r=>r.id===selected);
 const reload=()=>{void api.reviews(publication.id).then(setReviews).catch(e=>setError(errorText(e)));onSaved();};
 const analyze=async()=>{if(busy)return;setBusy(true);setError('');try{const key=JSON.stringify([kind,text,article?.captured_at]);if(request.current?.key!==key)request.current={key,id:crypto.randomUUID()};const r=await api.analyzeMaterial(publication.id,{request_id:request.current.id,input_kind:kind,text,captured_at:article?.captured_at});setReviews(r);setSelected(r.find(x=>x.id===request.current?.id)?.id||r[0]?.id||'');}catch(e){setError(errorText(e));}finally{setBusy(false);}};
 return <section className="ia-panel" aria-label="Analiza treści materiału"><div className="ia-toolbar"><h2>Analiza treści: {publication.title}</h2><button disabled={busy} onClick={onClose}>Zamknij</button></div>
 <p>AI przygotuje szkic wzmianek o spółkach. Dopiero Twoje potwierdzenie zapisze opinię w Pomysłach i udostępni ją w portfelu.</p>
 <fieldset disabled={busy} style={{border:0,padding:0}}><label>Źródło treści<select value={kind} onChange={e=>setKind(e.target.value)}>{video?<option value="VIDEO">Publiczny film YouTube</option>:<option value="ARTICLE">Treść artykułu ze źródła</option>}<option value="TRANSCRIPT">Wklejona transkrypcja / fragment</option></select></label>
 {kind==='ARTICLE'&&<><button onClick={()=>void fetchArticle()}>{article?'Odśwież treść artykułu':'Pobierz treść artykułu'}</button>{article&&<details open><summary>Podgląd tekstu · pobrano {new Date(article.captured_at).toLocaleString('pl-PL')}</summary>{article.truncated&&<p className="ia-warning">Tekst skrócono do pierwszych 60 000 znaków. Analiza obejmie tylko tę część.</p>}<pre>{article.text}</pre></details>}</>}
 {kind==='TRANSCRIPT'&&<label>Treść do analizy<textarea minLength={50} maxLength={60000} rows={8} value={text} onChange={e=>setText(e.target.value)} placeholder="Wklej fragment z nazwą rozmówcy i oznaczeniem czasu, jeśli jest dostępne."/></label>}
 <p>Po kliknięciu analizy do Google zostanie wysłany {kind==='VIDEO'?'link do tego filmu':kind==='ARTICLE'?'tekst z podglądu':'wklejony tekst'} i opis publikacji. Analiza wykorzystuje wspólny limit kosztów AI.</p>
 <button disabled={(kind==='TRANSCRIPT'&&text.trim().length<50)||(kind==='ARTICLE'&&!article)} onClick={()=>void analyze()}>{busy?'Przetwarzanie…':'Przygotuj szkic AI'}</button></fieldset>
 {error&&<div role="alert" className="ia-warning">{error}<button disabled={busy} onClick={()=>{request.current=undefined;setError('');}}>Przygotuj nowe żądanie</button></div>}
 <AISettings/>
 {reviews.length>0&&<label>Zapisane odczyty<select value={selected} onChange={e=>setSelected(e.target.value)}>{reviews.map(r=><option key={r.id} value={r.id}>{new Date(r.created_at).toLocaleString('pl-PL')} · {r.input_kind==='VIDEO'?'film':'tekst'}</option>)}</select></label>}
 {active&&<><h3>Podsumowanie materiału</h3><p>{active.result.summary}</p>{!active.result.claims.length&&<p>Nie wyodrębniono wzmianek o spółkach. Możesz przypisać własną analizę ręcznie.</p>}<div className="ia-grid">{active.result.claims.map((claim,index)=><Claim key={`${active.id}-${index}`} claim={claim} index={index} reviewId={active.id} saved={active.confirmed[String(index)]} onSaved={reload}/>)}</div></>}
 </section>;
}
