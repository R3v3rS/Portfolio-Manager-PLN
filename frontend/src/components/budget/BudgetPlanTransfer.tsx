import {useBudgetFormGuard} from './budgetMode';
import { useRef, useState } from 'react';
import { budgetWorkspaceApi, type BudgetWorkspace, type PlanTransferPreview } from '../../api_budget_workspace';
import { HttpError } from '../../http';
import { extractErrorMessageFromUnknown } from '../../http/response';
import { ImportDialog } from './imports/ImportUi';
import { planningMoney as money, planningToday } from './planningHelpers';

type Props = { data: BudgetWorkspace; reload: () => Promise<void>; onClose: () => void };
export default function BudgetPlanTransfer({ data, reload, onClose:close }: Props) {
  const categories = data.categories.filter(category => !category.is_unassigned && !category.monthly_reserve_managed);
  const [source, setSource] = useState(''), [target, setTarget] = useState(''), [amount, setAmount] = useState('');
  const [preview, setPreview] = useState<PlanTransferPreview | null>(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [saved, setSaved] = useState(false);
  const requestId = useRef(crypto.randomUUID());
  const canClose=useBudgetFormGuard([source,target,amount]);
  const onClose=()=>{if(canClose())close();};
  const input = { month: data.month, source_id: Number(source), target_id: Number(target), amount: Number(amount) };
  const change = (setter: (value: string) => void, value: string) => {
    setter(value); setPreview(null); setError(''); requestId.current = crypto.randomUUID();
  };
  const check = async () => {
    setBusy(true); setError(''); setPreview(null);
    try { setPreview(await budgetWorkspaceApi.previewTransfer(input)); }
    catch (err) { setError(extractErrorMessageFromUnknown(err)); }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (!preview) return;
    setBusy(true); setError('');
    if (!saved) {
      try {
        await budgetWorkspaceApi.transferPlan(input, preview.token, requestId.current);
        setSaved(true);
      } catch (err) {
        setError(extractErrorMessageFromUnknown(err)); setBusy(false);
        if (err instanceof HttpError && err.status >= 400 && err.status < 500) {
          setPreview(null); requestId.current = crypto.randomUUID();
        }
        return;
      }
    }
    try { await reload(); close(); }
    catch (err) { setError('Limity zostały zapisane. Nie udało się odświeżyć planu: ' + extractErrorMessageFromUnknown(err)); }
    finally { setBusy(false); }
  };
  const past = data.month < planningToday().slice(0, 7);
  return <ImportDialog title="Przenieś limit między kategoriami" busy={busy} onClose={onClose}>
    <p>Przenosisz plan w {data.month}. Salda kont i zapisane wydatki pozostają bez zmian. Rachunki i odłożenia muszą zachować pokrycie.</p>
    {saved && <p role="status" className="budget-feedback is-success">Przeniesienie limitu zapisane. Ponowne odświeżenie nie wykonuje kolejnej zmiany.</p>}
    {error && <p role="alert" className="budget-feedback is-error">{error}</p>}
    <form onSubmit={event => { event.preventDefault(); void (preview ? save() : check()); }}>
      <fieldset disabled={busy || saved || past} className="budget-form-stack">
        <label>Z której kategorii<select required value={source} onChange={event => change(setSource, event.target.value)}>
          <option value="">Wybierz wolny limit</option>
          {categories.filter(category => (category.plan_details?.ordinary_remaining ?? category.remaining) > 0).map(category =>
            <option key={category.id} value={category.id}>{category.path ?? category.name} · pozostało {money(category.plan_details?.ordinary_remaining ?? category.remaining)}</option>)}
        </select></label>
        <label>Do której kategorii<select required value={target} onChange={event => change(setTarget, event.target.value)}>
          <option value="">Wybierz kategorię</option>
          {categories.filter(category => category.id !== Number(source)).map(category => <option key={category.id} value={category.id}>{category.path ?? category.name}</option>)}
        </select></label>
        <label>Kwota limitu (PLN)<input required type="number" min="0.01" step="0.01" value={amount} onChange={event => change(setAmount, event.target.value)}/></label>
      </fieldset>
      {preview && <div className="budget-transfer-preview" aria-label="Podgląd przeniesienia limitu">
        <p>{preview.source_name}: <b>{money(preview.source_before)} → {money(preview.source_after)}</b></p>
        <p>{preview.target_name}: <b>{money(preview.target_before)} → {money(preview.target_after)}</b></p>
        {preview.related_limits?.map(row => <p key={row.name}>Wspólny limit {row.name}: <b>{money(row.before)} → {money(row.after)}</b></p>)}
        <p>Łączny plan kategorii: {money(preview.total_before)} → {money(preview.total_after)}.</p>
        <p>Zmiana dotyczy tego miesiąca. Domyślne limity zostają zachowane.</p>
      </div>}
      <div className="budget-form-actions">
        <button type="button" disabled={busy} className="budget-button-quiet" onClick={onClose}>{saved ? 'Zamknij' : 'Anuluj'}</button>
        <button className="budget-button-primary" type="submit" disabled={busy || past}>{busy ? 'Sprawdzanie…' : saved ? 'Odśwież plan' : preview ? 'Zatwierdź przeniesienie' : 'Sprawdź podgląd'}</button>
      </div>
    </form>
  </ImportDialog>;
}
