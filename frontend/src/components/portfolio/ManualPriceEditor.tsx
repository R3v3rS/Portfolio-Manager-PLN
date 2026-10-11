import { useState } from 'react';
import type { Holding } from '../../types';
import { portfolioApi } from '../../api';
import { extractErrorMessageFromUnknown } from '../../http/response';
import { ImportDialog } from '../budget/imports/ImportUi';
import '../budget/budgetWorkspace.css';

export default function ManualPriceEditor({holding,onClose,onSaved}:{holding:Holding;onClose:()=>void;onSaved:()=>Promise<void>}) {
  const today=new Date().toLocaleDateString('sv-SE');
  const [price,setPrice]=useState(holding.current_price==null?'':String(holding.current_price));
  const [date,setDate]=useState(holding.price_basis==='manual'?holding.price_last_updated_at?.slice(0,10)??today:today);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const save=async(clear=false)=>{
    setBusy(true);setError('');
    let saved=false;
    try {
      await portfolioApi.setManualPrice(holding.ticker,{price:Number(price),date,version:holding.manual_price_version??0,clear});
      saved=true;
      await onSaved();
      onClose();
    } catch(err) {setError(saved?'Cena została zapisana. Odśwież portfel, aby zobaczyć nową wycenę.':extractErrorMessageFromUnknown(err));}
    finally {setBusy(false);}
  };
  return <ImportDialog title={`Cena ręczna: ${holding.ticker}`} busy={busy} onClose={onClose}>
    <p className="pr-manual-help">Cena jednej akcji w {holding.currency??'PLN'}. Obowiązuje we wszystkich portfelach zawierających ten instrument, aż wrócisz do notowań automatycznych. Nie zmienia zakupów ani gotówki. Wynik pozostaje orientacyjny. Nie uzupełnia historii potrzebnej do wykresów i analiz ryzyka.</p>
    {error&&<p role="alert" className="budget-feedback is-error">{error}</p>}
    <form onSubmit={e=>{e.preventDefault();void save();}} className="budget-entry-form">
      <label>Cena jednej akcji ({holding.currency??'PLN'})<input type="number" min="0.000001" max="1000000000" step="any" required value={price} disabled={busy} onChange={e=>setPrice(e.target.value)}/></label>
      <label>Data ceny<input type="date" required max={today} value={date} disabled={busy} onChange={e=>setDate(e.target.value)}/></label>
      <div className="budget-form-actions"><button type="button" className="budget-button-quiet" disabled={busy} onClick={onClose}>Anuluj</button><button type="submit" className="budget-button-primary" disabled={busy}>Zapisz cenę</button></div>
      {holding.price_basis==='manual'&&<button type="button" className="budget-text-button" disabled={busy} onClick={()=>void save(true)}>Wróć do notowań automatycznych</button>}
    </form>
  </ImportDialog>;
}
