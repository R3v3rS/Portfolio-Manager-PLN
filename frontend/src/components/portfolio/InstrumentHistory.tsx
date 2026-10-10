import {useEffect,useState} from 'react';
import {reviewApi,eventName,type InstrumentReview} from '../../api_investment_review';
import {ImportDialog} from '../budget/imports/ImportUi';
import {money} from './researchModel';
import {extractErrorMessageFromUnknown} from '../../http/response';

export default function InstrumentHistory({portfolioId,ticker,onClose}:{portfolioId:number;ticker:string;onClose:()=>void}){
 const [data,setData]=useState<InstrumentReview>(),[error,setError]=useState(''),[page,setPage]=useState(0);
 useEffect(()=>{let active=true;setData(undefined);setError('');reviewApi.instrument(portfolioId,ticker).then(d=>{if(active)setData(d);}).catch(e=>{if(active)setError(extractErrorMessageFromUnknown(e));});return()=>{active=false;};},[portfolioId,ticker]);
 const rows=data?.events.slice().reverse()??[];
 return <ImportDialog title={`Historia instrumentu · ${ticker}`} busy={false} onClose={onClose}>
  {error&&<p role="alert">{error}</p>}{!data&&!error&&<p role="status">Ładowanie operacji…</p>}{data&&<>
   <p>{data.company_name} · {data.events.length} operacji{data.archived?' · zamknięta strategia':''}</p>
   <div className="actual-kpis"><div><span>Łączny wynik instrumentu</span><strong>{money(data.total_result)}</strong></div><div><span>Obecna wartość</span><strong>{money(data.current_value)}</strong></div><div><span>Dywidendy</span><strong>{money(data.dividends)}</strong></div></div>
   <p className="chart-note">Wynik obejmuje wycenę pozostałych jednostek, wszystkie zakupy, sprzedaże i dywidendy. W strategii przeniesione akcje liczymy od wartości startowej, a na głównym koncie od pierwotnego zakupu. Pozostało: {data.quantity.toLocaleString('pl-PL',{maximumFractionDigits:8})} jednostek.</p>
   {data.total_result===null&&<p role="status">Brakuje aktualnej wyceny. Historia operacji pozostaje dostępna.</p>}
   <div className="chart-table-wrap"><table className="chart-table"><thead><tr><th>Data</th><th>Operacja</th><th>Jednostki</th><th>Kwota</th><th>Pozostało</th><th>Strategia</th></tr></thead><tbody>{rows.slice(page*25,page*25+25).map(r=><tr key={r.id}><td>{r.date.slice(0,10)}</td><td>{eventName[r.type]??r.type}</td><td>{['BUY','SELL','ASSET_IN','ASSET_OUT'].includes(r.type)?r.quantity.toLocaleString('pl-PL',{maximumFractionDigits:8}):'—'}</td><td>{money(r.total_value)}</td><td>{r.remaining_quantity?.toLocaleString('pl-PL',{maximumFractionDigits:8})}</td><td>{r.strategy_name??'Część główna'}</td></tr>)}</tbody></table></div>
   <div className="chart-actions"><button disabled={!page} onClick={()=>setPage(page-1)}>Nowsze</button><span>{page+1} / {Math.max(1,Math.ceil(rows.length/25))}</span><button disabled={(page+1)*25>=rows.length} onClick={()=>setPage(page+1)}>Starsze</button></div>
  </>}
 </ImportDialog>;
}
