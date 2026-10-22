import {useEffect,useState} from 'react';
import {investmentAnalysisApi as api,type AISettings as Settings} from '../../api_investment_analysis';
import {extractErrorMessageFromUnknown as message} from '../../http/response';
export default function AISettings({onChange}:{onChange?:(s:Settings)=>void}){
 const [data,setData]=useState<Settings>(),[error,setError]=useState(''),[busy,setBusy]=useState(false),[saved,setSaved]=useState(false);
 useEffect(()=>{let active=true;api.settings().then(s=>{if(active)setData(s);}).catch(e=>{if(active)setError(message(e));});return()=>{active=false;};},[]);
 const save=async()=>{if(!data)return;setBusy(true);setError('');try{const s=await api.saveSettings(data);setData(s);onChange?.(s);setSaved(true);}catch(e){setError(message(e));}finally{setBusy(false);}};
 return <details className="ia-panel"><summary>Ustawienia AI i limit kosztów</summary>{error&&<p role="alert" className="ia-error">{error}</p>}{data&&<form onSubmit={e=>{e.preventDefault();void save();}} className="ia-workspace">
 <p className="ia-help">{data.configured?'Klucz Gemini jest skonfigurowany na serwerze.':'Brak klucza Gemini. Dodaj GEMINI_API_KEY do backend/.env i uruchom ponownie backend.'} Wykorzystano około {data.used_usd.toFixed(4)} USD / {data.daily_budget_usd.toFixed(2)} USD. {data.price_note}</p>
 <div className="ia-edit-grid"><label>Model<input required value={data.model} list="ia-models" onChange={e=>{setSaved(false);setData({...data,model:e.target.value});}}/><datalist id="ia-models"><option value="gemini-3.1-flash-lite"/></datalist></label>
 {([['daily_budget_usd','Dzienny limit szacowany (USD)',0,100],['input_usd_per_million','Cena wejścia za milion tokenów (USD)',.001,1000],['output_usd_per_million','Cena wyjścia za milion tokenów (USD)',.001,1000],['max_output_tokens','Maksymalna długość odpowiedzi (tokeny)',512,8192]] as const).map(([key,label,min,max])=><label key={key}>{label}<input type="number" step={key==='max_output_tokens'?1:.001} min={min} max={max} required value={data[key]} onChange={e=>{setSaved(false);setData({...data,[key]:Number(e.target.value)});}}/></label>)}</div>
 <p className="ia-help">Limit 0 blokuje płatne analizy. Po niepewnym błędzie dostawcy zachowujemy rezerwację kosztu; aplikacja nie ponawia płatnego wywołania automatycznie. <a href="https://ai.google.dev/gemini-api/docs/pricing" target="_blank" rel="noreferrer">Sprawdź aktualną taryfę Google</a>.</p>
 <div><button disabled={busy} className="ia-primary">Zapisz ustawienia</button>{saved&&<span role="status"> Zapisano.</span>}</div></form>}</details>;
}
