import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
export function ImportDialog({title,busy,onClose,children}:{title:string;busy:boolean;onClose:()=>void;children:React.ReactNode}){
  const dialog=useRef<HTMLElement>(null);
  useEffect(()=>{const before=document.activeElement as HTMLElement|null;const overflow=document.body.style.overflow;document.body.style.overflow='hidden';dialog.current?.querySelector<HTMLElement>('input,select,button')?.focus();return()=>{document.body.style.overflow=overflow;before?.focus();};},[]);
  useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.key==='Escape'&&!busy)onClose();if(e.key!=='Tab'||!dialog.current)return;const controls=[...dialog.current.querySelectorAll<HTMLElement>('input:not(:disabled),select:not(:disabled),button:not(:disabled),textarea:not(:disabled)')];const first=controls[0],last=controls.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}};document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key);},[busy,onClose]);
  return <div className="budget-modal-backdrop"><section ref={dialog} className="budget-modal br-modal" role="dialog" aria-modal="true" aria-labelledby="import-dialog-title"><div className="budget-modal-header"><h2 id="import-dialog-title">{title}</h2><button type="button" className="budget-icon-button" disabled={busy} onClick={onClose} aria-label="Zamknij formularz"><X size={18}/></button></div>{children}</section></div>;
}
