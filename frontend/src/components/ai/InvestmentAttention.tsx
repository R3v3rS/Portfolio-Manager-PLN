import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {investmentAnalysisApi as api} from '../../api_investment_analysis';
import type {PortfolioValue} from '../../types';
import './investmentAssistant.css';
export default function InvestmentAttention({portfolioId,value}:{portfolioId:number;value:PortfolioValue}){
 const [missingPlan,setMissingPlan]=useState(false);
 useEffect(()=>{let live=true;api.plan(portfolioId).then(p=>{if(live)setMissingPlan(!p.plan.goal&&!p.archived);}).catch(()=>{if(live)setMissingPlan(false);});return()=>{live=false;};},[portfolioId]);
 const tasks:{title:string;detail:string;to:string}[]=[];
 if(value.valuation_status==='incomplete'||value.valuation_status==='stale')tasks.push({title:value.valuation_status==='incomplete'?'Uzupełnij wycenę':'Sprawdź aktualność notowań',detail:'Wyniki i analizy opierają się na zapisanych cenach. Lista braków znajduje się w jakości danych.',to:`/portfolio/${portfolioId}?tab=ai`});
 if((value.reference_positions_count??0)>0)tasks.push({title:'Sprawdź pozycje wyceniane orientacyjnie',detail:'Cena ręczna lub koszt zakupu wymagają odróżnienia od notowania rynkowego.',to:`/portfolio/${portfolioId}?tab=holdings`});
 if(missingPlan)tasks.push({title:'Zapisz założenia strategii',detail:'Cel i docelowe udziały pozwolą odnieść analizę do Twojego planu.',to:`/portfolio/${portfolioId}?tab=analytics&analysis=plan`});
 if(!tasks.length)return null;
 return <section className="ia-panel" aria-label="Do sprawdzenia w portfelu"><h2>Do sprawdzenia</h2><div className="ia-grid">{tasks.slice(0,3).map(t=><div key={t.title}><Link to={t.to}>{t.title}</Link><p>{t.detail}</p></div>)}</div></section>;
}
