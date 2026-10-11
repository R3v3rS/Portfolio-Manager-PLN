import { useRef,useState } from 'react';
import { X } from 'lucide-react';
import { bondsApi,type BondKind,type BondPlan,type BondPosition } from '../../../api_bonds';
import type { BudgetAccount } from '../../../api_budget';
import { extractErrorMessageFromUnknown } from '../../../http/response';
import { bondMoney,bondToday,kindLabels } from './bondUi';

export default function BondEditor({pid,bond,cash,accounts,onSaved,onClose}:{pid:number;bond?:BondPosition;cash:number;accounts:BudgetAccount[];onSaved:()=>void;onClose:()=>void}) {
  const [plan,setPlan]=useState<BondPlan>(()=>({name:bond?.name||'',kind:bond?.kind && bond.kind!=='LEGACY'?bond.kind:bond?'CUSTOM':'EDO',
    quantity:bond?.quantity||10,nominal:bond?.nominal||(bond?.kind==='LEGACY'?bond.principal:100),purchase_price:bond?.purchase_price||(bond?.kind==='LEGACY'?bond.principal:100),
    purchase_date:bond?.purchase_date||bondToday(),maturity_date:bond?.maturity_date||'',interest_rate:bond?.interest_rate??0,
    tax_rate:bond?.tax_rate??19,redemption_fee:bond?.redemption_fee??null,fee_policy:bond?.fee_policy||'CAP_INTEREST',
    payout_account_id:bond?.payout_account_id||null,forecast_enabled:!!bond?.forecast_enabled,notes:bond?.notes||'',
    acquisition:!bond || bond.acquisition==='BUY'?'BUY':'EXISTING'}));
  const [rateText,setRateText]=useState(bond?String(bond.interest_rate):'');
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const key=useRef({id:crypto.randomUUID(),payload:''});
  const cost=plan.quantity*plan.purchase_price;
  const locked=!!bond && bond.kind!=='LEGACY';
  const submit=async(e:React.FormEvent)=>{e.preventDefault();if(busy)return;setBusy(true);setError('');
    try {const payload={...plan,interest_rate:Number(rateText)};const serialized=JSON.stringify(payload);if(key.current.payload && key.current.payload!==serialized)key.current.id=crypto.randomUUID();key.current.payload=serialized;if(bond)await bondsApi.update(bond,payload,key.current.id);else await bondsApi.create(pid,payload,key.current.id);onSaved();}
    catch(err){setError(extractErrorMessageFromUnknown(err));setBusy(false);}
  };
  return <div className="bw-overlay"><form role="dialog" aria-modal="true" aria-labelledby="bond-editor-heading" className="bw-dialog" onSubmit={submit}>
    <div className="bw-heading"><div><p className="bw-eyebrow">Warunki konkretnego zakupu</p><h2 id="bond-editor-heading">{bond?'Edytuj warunki':'Dodaj obligacje'}</h2></div><button type="button" className="bw-icon" aria-label="Zamknij formularz obligacji" disabled={busy} onClick={onClose}><X size={20}/></button></div>
    <fieldset disabled={busy} className="bw-form">
      {!bond && <label className="bw-wide">Sposób dodania<select value={plan.acquisition} onChange={e=>setPlan({...plan,acquisition:e.target.value as BondPlan['acquisition']})}><option value="BUY">Zakup z gotówki portfela</option><option value="EXISTING">Mam już te obligacje — dodaj kapitał początkowy</option></select></label>}
      <label>Rodzaj<select value={plan.kind} onChange={e=>setPlan({...plan,kind:e.target.value as BondKind,nominal:100,fee_policy:['COI','ROR','DOR'].includes(e.target.value)?'FIRST_PERIOD':'CAP_INTEREST'})}>{Object.entries(kindLabels).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      <label>Seria / nazwa<input required maxLength={100} placeholder="np. EDO1036" value={plan.name} onChange={e=>setPlan({...plan,name:e.target.value})}/></label>
      <label>Liczba sztuk<input required type="number" min={1} max={1000000} step={1} readOnly={locked} value={plan.quantity} onChange={e=>setPlan({...plan,quantity:Number(e.target.value)})}/></label>
      <label>Cena zakupu jednej sztuki (zł)<input required type="number" min="0.01" step="0.01" readOnly={locked} value={plan.purchase_price} onChange={e=>setPlan({...plan,purchase_price:Number(e.target.value)})}/></label>
      <label>Data zakupu<input required type="date" min="2000-01-01" max={bondToday()} readOnly={locked} value={plan.purchase_date} onChange={e=>setPlan({...plan,purchase_date:e.target.value})}/></label>
      <label>Oprocentowanie pierwszego okresu (%)<input required type="number" min={0} max={100} step="0.001" value={rateText} onChange={e=>setRateText(e.target.value)}/></label>
      {plan.kind==='CUSTOM' && <><label>Nominał jednej sztuki (zł)<input required type="number" min="0.01" step="0.01" value={plan.nominal} onChange={e=>setPlan({...plan,nominal:Number(e.target.value)})}/></label><label>Termin wykupu<input required type="date" min={plan.purchase_date} value={plan.maturity_date} onChange={e=>setPlan({...plan,maturity_date:e.target.value})}/></label></>}
      <label>Podatek do szacunków (%)<input required type="number" min={0} max={100} step="0.01" value={plan.tax_rate} onChange={e=>setPlan({...plan,tax_rate:Number(e.target.value)})}/></label>
      <label>Opłata wcześniejszego wykupu za sztukę (zł)<input type="number" min={0} step="0.01" placeholder="Z listu emisyjnego; 0 gdy brak" value={plan.redemption_fee??''} onChange={e=>setPlan({...plan,redemption_fee:e.target.value===''?null:Number(e.target.value)})}/></label>
      <label className="bw-wide">Potrącenie opłaty — zgodnie z listem emisyjnym<select value={plan.fee_policy} onChange={e=>setPlan({...plan,fee_policy:e.target.value as BondPlan['fee_policy']})}><option value="CAP_INTEREST">Najwyżej narosłe odsetki</option><option value="FIRST_PERIOD">Najwyżej odsetki w 1. okresie; potem pełna opłata</option><option value="FULL">Pełna opłata, także z kapitału</option></select></label>
      <label className="bw-wide">Konto planowanych wypłat<select value={plan.payout_account_id||''} onChange={e=>setPlan({...plan,payout_account_id:Number(e.target.value)||null,forecast_enabled:e.target.value?plan.forecast_enabled:false})}><option value="">Gotówka pozostaje w portfelu obligacji</option>{accounts.filter(a=>(a.currency||'PLN')==='PLN').map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label className="bw-check bw-wide"><input type="checkbox" disabled={!plan.payout_account_id} checked={plan.forecast_enabled} onChange={e=>setPlan({...plan,forecast_enabled:e.target.checked})}/>Uwzględniaj plan przenoszenia wypłat na to konto w prognozie pieniędzy</label>
      <label className="bw-wide">Notatka<textarea maxLength={2000} value={plan.notes} onChange={e=>setPlan({...plan,notes:e.target.value})}/></label>
    </fieldset>
    <div className="bw-preview"><span>Wartość zakupu</span><strong>{bondMoney(cost)}</strong>{!bond && <p>{plan.acquisition==='BUY'?`Gotówka portfela: ${bondMoney(cash)} → ${bondMoney(cash-cost)}`:'Gotówka pozostaje bez zmian. Zapiszemy kapitał początkowy inwestycji i zakup; nie jest to dochód budżetu.'}</p>}</div>
    <p className="bw-note">Terminy dla OTS–ROD wynikają z rodzaju i daty zakupu. Stopy oraz opłaty wpisz z warunków swojej serii. Własna obligacja: stała stopa, odsetki bez kapitalizacji, wypłata przy wykupie.</p>
    {locked && <p className="bw-note">Księgowanej kwoty i daty nie zmieniamy wstecz. Błędny zakup możesz anulować, jeśli nie ma wypłat, i dodać ponownie.</p>}
    {error && <p className="bw-alert" role="alert">{error}</p>}
    <div className="bw-actions"><button type="button" className="bw-button" disabled={busy} onClick={onClose}>Anuluj</button><button className="bw-button bw-primary" disabled={busy || (!bond && plan.acquisition==='BUY' && cost>cash)}>{busy?'Zapisywanie…':'Zapisz zakup i warunki'}</button></div>
  </form></div>;
}
