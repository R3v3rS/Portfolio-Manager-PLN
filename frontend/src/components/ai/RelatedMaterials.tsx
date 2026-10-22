import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {investmentAnalysisApi as api,type RelatedMaterial} from '../../api_investment_analysis';
import {extractErrorMessageFromUnknown as errorText} from '../../http/response';
import './investmentAssistant.css';
export default function RelatedMaterials({portfolioId}:{portfolioId:number}){
 const [items,setItems]=useState<RelatedMaterial[]>([]),[error,setError]=useState('');
 useEffect(()=>{let live=true;api.related(portfolioId).then(x=>{if(live)setItems(x);}).catch(e=>{if(live)setError(errorText(e));});return()=>{live=false;};},[portfolioId]);
 return <details className="ia-panel"><summary>Materiały dotyczące posiadanych spółek · {items.length}</summary><p>Twoje zapisane analizy i potwierdzone fragmenty. Niezatwierdzone szkice AI nie trafiają do tej listy.</p>{error&&<p role="alert">{error}</p>}
 {!items.length&&<p>Brak przypisanych materiałów. <Link to="/ideas">Otwórz Pomysły inwestycyjne</Link>, aby przeanalizować publikacje.</p>}
 <div className="ia-grid">{items.map(i=><article key={i.id} className="ia-material"><strong>{i.ticker}</strong><p>{i.source_id} · {i.published_on}</p><a href={i.url} target="_blank" rel="noreferrer">{i.title}</a><p>{i.evidence||i.thesis}</p></article>)}</div></details>;
}
