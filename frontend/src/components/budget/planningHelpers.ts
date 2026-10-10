import {useState} from 'react';
import {extractErrorMessageFromUnknown} from '../../http/response';

export const planningMoney=(n:number)=>new Intl.NumberFormat('pl-PL',{style:'currency',currency:'PLN'}).format(n);
export const planningDay=(s:string)=>new Date(s+'T12:00:00').toLocaleDateString('pl-PL',{day:'numeric',month:'short',year:'numeric'});
export const planningToday=()=>new Date().toLocaleDateString('sv-SE');

export function usePlanningAction(reload:()=>Promise<void>){
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const run=async(work:()=>Promise<unknown>,message:string,done?:()=>void)=>{
    setBusy(true);setError('');setNotice('');
    let saved=false;
    try{await work();saved=true;done?.();setNotice(message);await reload();}
    catch(err){setError((saved?'Zapisano zmianę, ale nie udało się odświeżyć danych. Odśwież widok. ':'')+extractErrorMessageFromUnknown(err));}
    finally{setBusy(false);}
  };
  return {busy,error,notice,run};
}
