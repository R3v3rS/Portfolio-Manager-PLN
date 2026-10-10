import {useEffect,useState} from 'react';
import {portfolioApi} from '../../api';
import type {Holding} from '../../types';
import {ImportDialog} from '../budget/imports/ImportUi';
import {extractErrorMessageFromUnknown} from '../../http/response';
import '../budget/budgetWorkspace.css';
import './assetTransfer.css';

type Position=Holding & {source_id:number|null;source_name:string;current_price_pln?:number|null};
export default function AssetTransfer({parentId,onSaved}:{parentId:number;onSaved:()=>Promise<void>}) {
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [positions,setPositions]=useState<Position[]>([]),[scopes,setScopes]=useState<{id:number|null;name:string}[]>([]);
  const [index,setIndex]=useState(''),[target,setTarget]=useState(''),[qty,setQty]=useState(''),[price,setPrice]=useState('');
  useEffect(()=>{if(open){setError('');setIndex('');setTarget('');setQty('');setPrice('');setBusy(true);void portfolioApi.assetTransferPositions(parentId).then(d=>{setPositions(d.positions);setScopes(d.scopes);}).catch(e=>setError(extractErrorMessageFromUnknown(e))).finally(()=>setBusy(false));}},[open,parentId]);
  const holding=index===''?null:positions[Number(index)];
  const pick=(value:string)=>{setIndex(value);setTarget('');const h=positions[Number(value)];setQty(h?String(h.quantity):'');setPrice(h?.current_price_pln==null?'':String(h.current_price_pln));};
  const submit=async()=>{
    if(!holding||target==='')return;setBusy(true);setError('');let saved=false;
    try{await portfolioApi.transferAsset({portfolio_id:parentId,source_id:holding.source_id,target_id:target==='main'?null:Number(target),ticker:holding.ticker,quantity:Number(qty),price_pln:Number(price),expected_quantity:holding.quantity});saved=true;await onSaved();setOpen(false);}
    catch(e){setError(saved?'Przeniesienie zapisane. Odśwież stronę przed kolejną operacją.':extractErrorMessageFromUnknown(e));if(saved)setIndex('');}
    finally{setBusy(false);}
  };
  return <><button className="pr-button" onClick={()=>setOpen(true)}>Przenieś akcje do podkonta</button>{open&&<ImportDialog title="Przeniesienie akcji między podkontami" busy={busy} onClose={()=>setOpen(false)}>
    <p className="pr-manual-help">Przeniesienie dzisiaj. Nowe podkonto zacznie liczyć wynik od podanej wartości. Pierwotny koszt i historia całego IKE pozostają zachowane. Gotówka nie zmieni się. Gotówkę przeniesiesz osobno przyciskiem Transfer.</p>
    {error&&<p role="alert" className="budget-feedback is-error">{error}</p>}
    <form className="budget-entry-form asset-transfer-form" onSubmit={e=>{e.preventDefault();void submit();}}>
      <label>Pozycja i konto źródłowe<select required value={index} disabled={busy} onChange={e=>pick(e.target.value)}><option value="">Wybierz pozycję</option>{positions.map((h,i)=><option key={`${h.source_id}:${h.ticker}`} value={i}>{h.ticker} · {h.source_name} · {h.quantity} szt.</option>)}</select></label>
      <label>Konto docelowe<select required value={target} disabled={busy||!holding} onChange={e=>setTarget(e.target.value)}><option value="">Wybierz podkonto</option>{scopes.filter(s=>s.id!==holding?.source_id).map(s=><option key={s.id??'main'} value={s.id??'main'}>{s.name}</option>)}</select></label>
      <label>Liczba jednostek<input type="number" required min="0.00000001" step="any" max={holding?.quantity} value={qty} disabled={busy||!holding} onChange={e=>setQty(e.target.value)}/></label>
      <label>Wartość jednej jednostki na start (PLN)<input type="number" required min="0.00000001" max="1000000000" step="any" value={price} disabled={busy||!holding} onChange={e=>setPrice(e.target.value)}/></label>
      <p className="pr-manual-help">Wartość startowa: {new Intl.NumberFormat('pl-PL',{style:'currency',currency:'PLN'}).format((Number(qty)||0)*(Number(price)||0))}. Sprawdź proponowaną wycenę; możesz wpisać własną, również dla spółki bez notowania.</p>
      {scopes.length<2&&<p>Najpierw utwórz nowe podkonto w głównym portfelu.</p>}
      <div className="budget-form-actions"><button type="button" className="budget-button-quiet" disabled={busy} onClick={()=>setOpen(false)}>Anuluj</button><button type="submit" className="budget-button-primary" disabled={busy||!holding||!target}>Przenieś i rozpocznij historię</button></div>
    </form></ImportDialog>}</>;
}
