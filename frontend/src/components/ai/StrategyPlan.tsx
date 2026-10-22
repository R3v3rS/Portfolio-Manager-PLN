import {useEffect,useState} from 'react';
import {investmentAnalysisApi as api,type PlanWorkspace,type Simulation,type StrategyPlan as Plan} from '../../api_investment_analysis';
import {extractErrorMessageFromUnknown as errorText} from '../../http/response';
import './investmentAssistant.css';
const money=(n:number)=>n.toLocaleString('pl-PL',{style:'currency',currency:'PLN'});
export default function StrategyPlan({portfolioId}:{portfolioId:number}){
 const [workspace,setWorkspace]=useState<PlanWorkspace>(),[plan,setPlan]=useState<Plan>(),[simulation,setSimulation]=useState<Simulation>();
 const [amount,setAmount]=useState(500),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 useEffect(()=>{let live=true;api.plan(portfolioId).then(x=>{if(live){setWorkspace(x);setPlan(x.plan);}}).catch(e=>{if(live)setError(errorText(e));});return()=>{live=false;};},[portfolioId]);
 const dirty=JSON.stringify(plan)!==JSON.stringify(workspace?.plan);
 const update=(next:Plan)=>{setPlan(next);setSimulation(undefined);setNotice('');};
 const run=async(action:()=>Promise<void>)=>{if(busy)return;setBusy(true);setError('');try{await action();}catch(e){setError(errorText(e));}finally{setBusy(false);}};
 if(!workspace||!plan)return <div className="ia-panel" role={error?'alert':'status'}>{error||'Ładowanie założeń strategii…'}</div>;
 const equity=!['PPK','BONDS','SAVINGS'].includes(workspace.account_type);
 const total=plan.targets.reduce((sum,row)=>sum+Number(row.percent||0),0);
 const keys=plan.mode==='STRATEGY'?[{key:'OWN',name:'Część główna'},...workspace.children.map(c=>({key:String(c.id),name:c.name}))]:[{key:'CASH',name:'Gotówka'},...workspace.instruments.map(key=>({key,name:key}))];
 return <section className="ia-panel"><h2>Założenia i plan udziałów</h2><p>Opisz cel, horyzont i ograniczenia. Asystent odniesie analizę do zapisanych założeń.</p>
 {error&&<p role="alert" className="ia-warning">{error}</p>}{notice&&<p role="status">{notice}</p>}
 <form onSubmit={e=>{e.preventDefault();void run(async()=>{const x=await api.savePlan(portfolioId,{...plan,version:workspace.version});setWorkspace(x);setPlan(x.plan);setNotice('Zapisano założenia. Nowe przeglądy asystenta będą je uwzględniać.');});}}>
 <fieldset disabled={busy||workspace.archived} style={{border:0,padding:0}}><div className="ia-grid">
 <label>Cel strategii<textarea maxLength={2000} value={plan.goal} onChange={e=>update({...plan,goal:e.target.value})} placeholder="Po co inwestuję w tej części portfela?"/></label>
 <label>Horyzont<input maxLength={2000} value={plan.horizon} onChange={e=>update({...plan,horizon:e.target.value})} placeholder="np. 10 lat"/></label>
 <label>Ograniczenia i zasady<textarea maxLength={2000} value={plan.constraints} onChange={e=>update({...plan,constraints:e.target.value})} placeholder="np. maksymalny udział jednej spółki, zasady dopłat"/></label></div>
 {equity&&<><label>Plan udziałów<select value={plan.mode} onChange={e=>update({...plan,mode:e.target.value as Plan['mode'],targets:[]})}><option value="INSTRUMENT">Instrumenty i gotówka</option>{workspace.children.length>0&&<option value="STRATEGY">Strategie i część główna</option>}</select></label>
 <datalist id={`plan-instruments-${portfolioId}`}>{keys.map(k=><option key={k.key} value={k.key}>{k.name}</option>)}</datalist>
 {plan.targets.map((row,index)=><div className="ia-target" key={index}>
 <label>{plan.mode==='STRATEGY'?'Strategia':'Ticker lub CASH'}{plan.mode==='STRATEGY'?<select aria-label={`Cel ${index+1}`} value={row.key} onChange={e=>update({...plan,targets:plan.targets.map((r,i)=>i===index?{...r,key:e.target.value}:r)})}><option value="">Wybierz</option>{keys.map(k=><option key={k.key} value={k.key}>{k.name}</option>)}</select>:<input required aria-label={`Cel ${index+1}`} list={`plan-instruments-${portfolioId}`} maxLength={32} value={row.key} onChange={e=>update({...plan,targets:plan.targets.map((r,i)=>i===index?{...r,key:e.target.value.toUpperCase()}:r)})}/>}</label>
 <label>Docelowy udział %<input aria-label={`Udział ${index+1}`} type="number" min={0} max={100} step="0.01" required value={row.percent} onChange={e=>update({...plan,targets:plan.targets.map((r,i)=>i===index?{...r,percent:Number(e.target.value)}:r)})}/></label>
 <button type="button" aria-label={`Usuń cel ${index+1}`} onClick={()=>update({...plan,targets:plan.targets.filter((_,i)=>i!==index)})}>Usuń</button></div>)}
 <div className="ia-toolbar"><button type="button" onClick={()=>update({...plan,targets:[...plan.targets,{key:'',percent:0}]})}>Dodaj udział</button><span>Suma: {total.toFixed(2)}%{plan.targets.length>0&&Math.abs(total-100)>.001?' · powinna wynosić 100%':''}</span></div></>}
 <button disabled={!dirty||(plan.targets.length>0&&Math.abs(total-100)>.001)}>Zapisz założenia</button></fieldset></form>
 {equity&&!workspace.archived&&<div className="ia-section"><h3>Rozdziel nową wpłatę</h3><p>Symulacja uzupełnia braki względem zapisanych udziałów. Obecna gotówka pozostaje na miejscu. Kwoty są orientacyjne — bez zleceń, prowizji i zaokrąglania do całych jednostek.</p>
 <div className="ia-toolbar"><label>Nowa wpłata PLN<input type="number" min={0} max={1000000000} step="0.01" value={amount} onChange={e=>{setAmount(Number(e.target.value));setSimulation(undefined);}}/></label><button disabled={busy||dirty||!plan.targets.length} onClick={()=>void run(async()=>setSimulation(await api.simulate(portfolioId,amount)))}>Oblicz podział</button></div>
 {dirty&&<p>Zapisz zmiany planu przed symulacją.</p>}
 {simulation&&<><div className="ia-table-wrap"><table><thead><tr><th>Cel</th><th>Obecnie</th><th>Z nowej wpłaty</th><th>Po wpłacie</th><th>Udział / cel</th></tr></thead><tbody>{simulation.rows.map(row=><tr key={row.key}><th>{row.label}</th><td>{money(row.before)}</td><td>{money(row.contribution)}</td><td>{money(row.after)}</td><td>{row.after_percent.toFixed(1)}% / {row.target_percent.toFixed(1)}%</td></tr>)}</tbody></table></div><p>{simulation.note}</p>{simulation.warnings.map((w,i)=><p key={i} className="ia-warning">{w}</p>)}</>}
 </div>}</section>;
}
