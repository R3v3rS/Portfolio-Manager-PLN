import { useRef,useState } from 'react';
import { X } from 'lucide-react';
import { bondsApi,type BondPosition } from '../../../api_bonds';
import type { BudgetAccount } from '../../../api_budget';
import { extractErrorMessageFromUnknown } from '../../../http/response';
import { bondDate,bondMoney,bondPercent,bondToday } from './bondUi';

export default function BondOperations({bond,mode,cash,accounts,onSaved,onClose}:{bond:BondPosition;mode:'SETTLE'|'RATE'|'CALCULATE'|'CANCEL';cash:number;accounts:BudgetAccount[];onSaved:()=>void;onClose:()=>void}) {
  const unpaid=bond.periods.filter(p=>p.complete && p.pays_cash && !p.capitalizes && !p.paid);
  const editable=bond.periods.filter(p=>p.period>1 && p.start_date<=bondToday());
  const [kind,setKind]=useState<'COUPON'|'REDEEM'>(unpaid.length?'COUPON':'REDEEM');
  const [period,setPeriod]=useState(mode==='RATE'?(editable[editable.length-1]?.period||2):(unpaid[0]?.period||2));
  const [rate,setRate]=useState(String(bond.current_rate));
  const [quantity,setQuantity]=useState(bond.remaining_quantity);
  const [net,setNet]=useState('');const [when,setWhen]=useState(bondToday());
  const [confirmed,setConfirmed]=useState(false);const [transfer,setTransfer]=useState(false);
  const [history,setHistory]=useState(false);
  const [calculation,setCalculation]=useState<BondPosition|null>(null);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const key=useRef({id:crypto.randomUUID(),payload:''});
  const account=accounts.find(a=>a.id===bond.payout_account_id);
  const title={SETTLE:'Zapisz faktyczną wypłatę',RATE:'Oprocentowanie okresu',CALCULATE:'Kalkulator wartości i wykupu',CANCEL:'Anuluj błędny zakup'}[mode];
  const submit=async(e:React.FormEvent)=>{e.preventDefault();if(busy)return;setBusy(true);setError('');
    try {
      const payload={kind,period,quantity,net_amount:Number(net),date:when,confirmed_actual:confirmed,transfer_to_budget:transfer,history_only:history,rate:Number(rate)};
      const serialized=JSON.stringify(payload);if(key.current.payload && key.current.payload!==serialized)key.current.id=crypto.randomUUID();key.current.payload=serialized;
      if(mode==='CALCULATE'){setCalculation(await bondsApi.estimate(bond,when,Number(rate)));setBusy(false);return;}
      if(mode==='RATE')await bondsApi.rate(bond,period,Number(rate),key.current.id);
      if(mode==='CANCEL')await bondsApi.cancel(bond,key.current.id);
      if(mode==='SETTLE')await bondsApi.settle(bond,{...payload,quantity:kind==='COUPON'?bond.remaining_quantity:quantity},key.current.id);
      onSaved();
    }catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}
  };
  const ratio=quantity/bond.remaining_quantity;
  const calculationRatio=calculation && calculation.remaining_quantity>0?quantity/calculation.remaining_quantity:0;
  const suggested=kind==='COUPON'?unpaid.find(p=>p.period===period)?.net:bond.status==='MATURED'?bond.estimated_value_net:bond.early_redemption_net;
  return <div className="bw-overlay"><form role="dialog" aria-modal="true" aria-labelledby="bond-operation-heading" className="bw-dialog" onSubmit={submit}>
    <div className="bw-heading"><div><p className="bw-eyebrow">{bond.name}</p><h2 id="bond-operation-heading">{title}</h2></div><button type="button" className="bw-icon" aria-label="Zamknij działanie obligacji" disabled={busy} onClick={onClose}><X size={20}/></button></div>
    <fieldset disabled={busy} className="bw-form">
      {mode==='RATE' && <><label>Okres odsetkowy<select required value={period} onChange={e=>{const n=Number(e.target.value);setPeriod(n);setRate(String(bond.periods.find(p=>p.period===n)?.rate||0));}}>{editable.map(p=><option key={p.period} value={p.period}>{p.period}. od {bondDate(p.start_date)}</option>)}</select></label><label>Potwierdzona stopa roczna (%)<input required type="number" min={0} max={100} step="0.001" value={rate} onChange={e=>setRate(e.target.value)}/></label><p className="bw-note bw-wide">Wpisz stopę ogłoszoną dla tej serii i okresu. Założenia przyszłego oprocentowania ustaw w kalkulatorze.</p></>}
      {mode==='SETTLE' && <>
        <label className="bw-wide">Rodzaj wypłaty<select value={kind} onChange={e=>{setKind(e.target.value as typeof kind);setNet('');}}><option value="REDEEM">Wykup całości lub części obligacji</option>{unpaid.length>0 && <option value="COUPON">Wypłata odsetek za zakończony okres</option>}</select></label>
        {kind==='COUPON'?<label className="bw-wide">Rozliczany okres<select value={period} onChange={e=>setPeriod(Number(e.target.value))}>{unpaid.map(p=><option key={p.period} value={p.period}>{p.period}. zakończony {bondDate(p.end_date)} · szacunek {bondMoney(p.net)} netto</option>)}</select></label>:<label>Liczba wykupionych sztuk<input required type="number" min={1} max={bond.remaining_quantity} step={1} value={quantity} onChange={e=>setQuantity(Number(e.target.value))}/></label>}
        <label>Data faktycznej wypłaty<input required type="date" min={bond.purchase_date} max={bondToday()} value={when} onChange={e=>setWhen(e.target.value)}/></label>
        <label>Rzeczywiście otrzymano netto (zł)<input required type="number" min="0.01" step="0.01" value={net} onChange={e=>setNet(e.target.value)}/></label>
        <p className="bw-note bw-wide">Szacunek na {bondDate(bond.as_of)}: {bondMoney(suggested==null?null:suggested*(kind==='REDEEM'?ratio:1))}. Wpisz kwotę z faktycznej wypłaty po podatku i opłatach. Zapis nie zleca wykupu w banku.</p>
        {account && <label className="bw-check bw-wide"><input type="checkbox" checked={transfer} onChange={e=>{setTransfer(e.target.checked);if(e.target.checked)setHistory(false);}}/>Wypłata trafiła już na {account.name} — zapisz także transfer z inwestycji</label>}
        <label className="bw-check bw-wide"><input type="checkbox" checked={history} onChange={e=>{setHistory(e.target.checked);if(e.target.checked)setTransfer(false);}}/>Starsza wypłata poza portfel — aktualne saldo konta już ją uwzględnia</label>
        {history && <p className="bw-note bw-wide">Uzupełnimy historię wypłaty i wycofania pieniędzy z inwestycji. Saldo portfela oraz kont budżetowych pozostanie bez zmian.</p>}
        <label className="bw-check bw-wide"><input required type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Potwierdzam wykonaną operację i rzeczywistą kwotę wypłaty</label>
      </>}
      {mode==='CALCULATE' && <><label>Data wyceny / rozliczenia<input required type="date" min={bond.purchase_date} max="2100-12-31" value={when} onChange={e=>setWhen(e.target.value)}/></label><label>Nieznane stopy w symulacji (%)<input required type="number" min={0} max={100} step="0.01" value={rate} onChange={e=>setRate(e.target.value)}/></label><label>Liczba sztuk<input required type="number" min={1} max={bond.remaining_quantity} value={quantity} onChange={e=>setQuantity(Number(e.target.value))}/></label><p className="bw-note bw-wide">Szacunek na wybraną datę. Daty bankowego rozliczenia, dni robocze i zasady konkretnej emisji mogą zmienić kwotę. Kalkulator nie zmienia sald.</p></>}
      {mode==='CANCEL' && <><p className="bw-note bw-wide">Zakup zostanie oznaczony jako anulowany, a w historii zapiszemy operację odwracającą. {bond.acquisition==='BUY'?`Do gotówki portfela wróci ${bondMoney(bond.principal)}.`:'Cofniemy dodany kapitał początkowy; gotówka pozostanie bez zmian.'} Później możesz dodać poprawiony zakup.</p><label className="bw-check bw-wide"><input type="checkbox" required checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Chcę anulować ten zakup</label></>}
    </fieldset>
    {mode==='SETTLE' && <div className="bw-preview"><p>{history?'Historia — salda już uwzględniają wypłatę; nie zmienimy ich.':transfer && account?`${account.name}: ${bondMoney(account.balance)} → ${bondMoney(account.balance+Number(net))}`:`Gotówka portfela: ${bondMoney(cash)} → ${bondMoney(cash+Number(net))}`}</p></div>}
    {calculation && <div className="bw-calculation"><p>Wycena na {bondDate(calculation.as_of)} · stopa {bondPercent(calculation.current_rate)}</p><dl><div><dt>Narosłe odsetki brutto</dt><dd>{bondMoney(calculation.accrued_interest*calculationRatio)}</dd></div><div><dt>Wartość netto bez opłaty</dt><dd>{bondMoney(calculation.estimated_value_net*calculationRatio)}</dd></div><div><dt>Opłata wcześniejszego wykupu</dt><dd>{bondMoney(calculation.early_redemption_fee==null?null:calculation.early_redemption_fee*calculationRatio)}</dd></div><div><dt>Szacowana wypłata po opłacie</dt><dd>{bondMoney(calculation.early_redemption_net==null?null:calculation.early_redemption_net*calculationRatio)}</dd></div></dl>{calculation.early_redemption_net==null && <p>Uzupełnij opłatę w warunkach zakupu, aby obliczyć wcześniejszy wykup.</p>}{calculation.warnings.map(w=><p className="bw-alert" key={w}>{w}</p>)}</div>}
    {error && <p className="bw-alert" role="alert">{error}</p>}
    <div className="bw-actions"><button type="button" className="bw-button" disabled={busy} onClick={onClose}>Zamknij</button><button className="bw-button bw-primary" disabled={busy || (mode==='RATE' && !editable.length)}>{busy?'Przetwarzanie…':mode==='CALCULATE'?'Przelicz':mode==='CANCEL'?'Anuluj zakup':'Zapisz'}</button></div>
  </form></div>;
}
