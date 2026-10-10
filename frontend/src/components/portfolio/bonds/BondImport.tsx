import { useRef,useState } from 'react';
import { X,Download } from 'lucide-react';
import { bondsApi,type BondImportRow } from '../../../api_bonds';
import { extractErrorMessageFromUnknown } from '../../../http/response';
import { bondMoney,bondDate } from './bondUi';
export default function BondImport({pid,onSaved,onClose}:{pid:number;onSaved:()=>void;onClose:()=>void}) {
  const [rows,setRows]=useState<BondImportRow[]>([]);const [selected,setSelected]=useState<number[]>([]);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const key=useRef({id:crypto.randomUUID(),payload:''});
  const read=async(file?:File)=>{if(!file)return;setBusy(true);setError('');setRows([]);
    try{if(file.size>1000000)throw new Error('Plik może mieć najwyżej 1 MB.');const result=await bondsApi.preview(pid,await file.text());setRows(result.rows);setSelected(result.rows.filter(r=>r.plan && !r.duplicate).map(r=>r.line));}
    catch(err){setError(extractErrorMessageFromUnknown(err));}finally{setBusy(false);}
  };
  const save=async()=>{if(busy)return;setBusy(true);setError('');try{const plans=rows.filter(r=>r.plan && selected.includes(r.line)).map(r=>r.plan!);const payload=JSON.stringify(plans);if(key.current.payload && key.current.payload!==payload)key.current.id=crypto.randomUUID();key.current.payload=payload;await bondsApi.import(pid,plans,key.current.id);onSaved();}catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}};
  const download=()=>{const data='name;kind;quantity;purchase_price;purchase_date;interest_rate;redemption_fee;fee_policy\nEDO1036;EDO;10;100;2026-10-01;5.35;3;CAP_INTEREST\n';const url=URL.createObjectURL(new Blob(['\ufeff'+data],{type:'text/csv;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='obligacje-szablon.csv';link.click();URL.revokeObjectURL(url);};
  return <div className="bw-overlay"><section role="dialog" aria-modal="true" aria-labelledby="bond-import-heading" className="bw-dialog"><div className="bw-heading"><div><p className="bw-eyebrow">Najpierw podgląd, potem zapis</p><h2 id="bond-import-heading">Import posiadanych obligacji</h2></div><button className="bw-icon" aria-label="Zamknij import obligacji" onClick={onClose} disabled={busy}><X size={20}/></button></div>
    <p className="bw-note">Import dodaje wcześniej posiadane zakupy i ich kapitał początkowy. Nie pomniejsza dzisiejszej gotówki ani nie tworzy dochodu budżetu. Obsługiwany jest CSV w poniższym układzie; eksport banku może wymagać dostosowania kolumn.</p>
    <div className="bw-actions"><button className="bw-button" onClick={download}><Download size={16}/>Pobierz szablon CSV</button><label className="bw-button">Wybierz CSV<input aria-label="Plik CSV obligacji" type="file" accept=".csv,text/csv" disabled={busy} onChange={e=>void read(e.target.files?.[0])}/></label></div>
    <p className="bw-note">Kolumny: name, kind, quantity, purchase_price, purchase_date, interest_rate. Opcjonalnie: nominal, maturity_date (dla CUSTOM), tax_rate, redemption_fee, fee_policy. Daty: RRRR-MM-DD. Parametry przykładowe w szablonie należy sprawdzić przed importem.</p>
    {rows.length>0 && <ul className="bw-import-list">{rows.map(r=><li key={r.line}><label className="bw-check"><input type="checkbox" disabled={!r.plan || r.duplicate || busy} checked={selected.includes(r.line)} onChange={e=>setSelected(e.target.checked?[...selected,r.line]:selected.filter(n=>n!==r.line))}/><span>{r.plan?<><strong>{r.plan.name}</strong><small>{bondDate(r.plan.purchase_date)} · {r.plan.quantity} szt. · {bondMoney(r.plan.quantity*r.plan.purchase_price)}</small></>:<>Wiersz {r.line}</>}{r.error && <small className="bw-alert">{r.error}</small>}{r.duplicate && <small>Możliwy duplikat — pominięty</small>}</span></label></li>)}</ul>}
    {error && <p className="bw-alert" role="alert">{error}</p>}<div className="bw-actions"><button className="bw-button" onClick={onClose} disabled={busy}>Zamknij</button><button className="bw-button bw-primary" onClick={()=>void save()} disabled={busy || !selected.length}>{busy?'Przetwarzanie…':`Zapisz wybrane (${selected.length})`}</button></div>
  </section></div>;
}
