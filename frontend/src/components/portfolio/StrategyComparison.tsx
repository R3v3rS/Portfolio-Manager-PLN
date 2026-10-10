import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {reviewApi,type StrategyRow} from '../../api_investment_review';
import {money,percent} from './researchModel';
import {extractErrorMessageFromUnknown} from '../../http/response';

export default function StrategyComparison({portfolioId}:{portfolioId:number}){
 const [rows,setRows]=useState<StrategyRow[]>(),[error,setError]=useState(''),[archived,setArchived]=useState(true);
 useEffect(()=>{let active=true;reviewApi.strategies(portfolioId).then(d=>{if(active)setRows(d.items);}).catch(e=>{if(active)setError(extractErrorMessageFromUnknown(e));});return()=>{active=false;};},[portfolioId]);
 return <section className="chart-panel"><div className="chart-heading"><div><h2>Porównanie strategii</h2><p>Każda strategia od własnego startu. Archiwalne wyniki zatrzymano przy zamknięciu i nie dodajemy ich wartości ponownie do majątku.</p></div><label><input type="checkbox" checked={archived} onChange={e=>setArchived(e.target.checked)}/> Pokaż archiwum</label></div>
 {error&&<p role="alert">{error}</p>}{!rows&&!error&&<p role="status">Ładowanie strategii…</p>}{rows&&<><div className="chart-table-wrap"><table className="chart-table"><thead><tr><th>Strategia</th><th>Okres</th><th>Kapitał startowy</th><th>Późniejsze wpłaty</th><th>Wartość / przy zamknięciu</th><th>Wynik</th><th>Zwrot prosty</th><th>XIRR rocznie</th></tr></thead><tbody>{rows.filter(r=>archived||!r.archived).map(r=><tr key={r.id}><th><Link to={`/portfolio/${r.id}`}>{r.name}</Link><small>{r.archived?'Archiwum':'Aktywna'}{r.archived&&!r.frozen?(r.started_at?' · brak zapisanego raportu':' · dawna historia scalona'):''}</small></th><td>{r.started_at??'—'} → {r.closed_at?.slice(0,10)??'obecnie'}</td><td>{money(r.starting_capital)}</td><td>{money(r.additional_capital)}</td><td>{money(r.value)}</td><td>{money(r.result)}</td><td>{percent(r.return_percent)}</td><td>{percent(r.xirr_percent)}</td></tr>)}</tbody></table></div>{!rows.filter(r=>archived||!r.archived).length&&<p>Brak strategii w tym widoku. Utwórz podkonto w głównym portfelu.</p>}<p className="chart-note">Porównuj daty i wielkość kapitału: strategie mogą działać przez różny czas. Późniejsze wpłaty to kapitał, nie zysk. Zwrot prosty i roczny XIRR są różnymi miarami.</p></>}
 </section>;
}
