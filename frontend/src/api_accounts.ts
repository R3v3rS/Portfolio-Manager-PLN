import { createApiClient } from './apiConfig';

export interface AccountLocation { account_id:number; account_name:string; amount:number }
export interface AccountReserve { id:number; name:string; version:number; locations:AccountLocation[] }
export interface ManagedAccount {
  account_type?:'BANK'|'CREDIT_CARD';
  id:number; name:string; balance:number; reserved:number; available:number; verified_on:string|null;
  opening_balance?:number|null; opening_date?:string|null; opening_record_id?:number|null; inferred_opening_balance?:number;
  allocations:{reserve_id:number;name:string;amount:number;due_date:string;version:number}[];
}
export interface AccountHistory {
  id:string; kind:'TRANSFER'|'LOCATION'|'RECONCILIATION'|'CARD_PAYMENT'; date:string; created_at:string;
  source_account_id:number|null; target_account_id:number|null; account_id:number|null;
  title:string; detail:string; notes:string; amount:number;
  previous_balance?:number; observed_balance?:number;
}
export interface AccountsWorkspace {
  as_of:string; accounts:ManagedAccount[]; reserves:AccountReserve[]; history:AccountHistory[]; warnings:string[];
  totals:{balance:number;reserved:number;available:number;cash_balance?:number;credit_card_debt?:number;credit_card_overpayment?:number};
}
export interface AccountTransferInput {
  source_account_id:number; target_account_id:number; amount:number; date:string; notes:string;
  move_money:boolean; reserve_id:number|null; version?:number; source_balance:number; target_balance:number;
  reserve_action?:'MOVE'|'FUND';
}
const client=createApiClient('/budget/accounts');
export const accountsApi={
  get:()=>client.get<AccountsWorkspace>(''),
  create:(name:string,balance:number,request_id:string,account_type?:'BANK'|'CREDIT_CARD')=>client.post<{id:number}>('',{name,balance,request_id,...(account_type?{account_type}:{})}),
  transfer:(input:AccountTransferInput,request_id:string)=>client.post<{id:number}>('/transfers',{...input,request_id}),
  openingBalance:(id:number,input:{balance?:number;from_reconciliation_id?:number;expected_balance:number;expected_opening_id:number|null;notes:string},request_id:string)=>
    client.post<{id:number}>(`/${id}/opening-balance`,{...input,request_id}),
  reconcile:(id:number,balance:number,expected_balance:number,notes:string,request_id:string)=>
    client.post<{id:number}>(`/${id}/reconcile`,{balance,expected_balance,notes,request_id}),
};
