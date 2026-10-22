import { buildApiPath, createApiClient } from './apiConfig';

export type CategoryState = 'UNASSIGNED'|'GENERAL'|'SPLIT';
export type BalanceMode = 'HISTORY'|'APPLY';
export type CsvField = 'date'|'amount'|'description'|'merchant'|'currency'|'reference'|'debit'|'credit';
export type CsvMapping = Record<CsvField,string>;
export interface ImportAccount { id:number;name:string;balance:number;verified_on:string|null;account_type?:'BANK'|'CREDIT_CARD' }
export interface CategoryRuleInput { name?:string;pattern:string;match_field:'ANY'|'MERCHANT'|'DESCRIPTION';match_type:'CONTAINS'|'EQUALS'|'STARTS_WITH';category_id:number|null;new_category?:string;account_id:number|null;priority:number;active:boolean }
export interface CategoryRule extends CategoryRuleInput { id:number;version:number;name:string;category_name:string;account_name:string|null }
export interface ReserveTransferRuleInput { pattern:string;source_account_id:number;target_account_id:number;reserve_id:number;active:boolean }
export interface ReserveTransferRule extends ReserveTransferRuleInput { id:number;version:number;source_name:string;target_name:string;reserve_name:string;reserve_active:boolean }
export interface ExpenseCandidate { id:number;account_id:number;account_name:string;date:string;amount:number;description:string;merchant:string|null;version:number;has_receipt:boolean;classification_status:CategoryState;merchant_match:boolean;lines:{category_id:number;category_name:string;amount:number;label:string}[] }
export interface PendingExpense { id:number;account_id:number;account_name:string;date:string;amount:number;description:string;merchant:string|null;version:number;has_receipt:boolean }
export interface BudgetImportsWorkspace {
  accounts:ImportAccount[];categories:{id:number;name:string;parent_id?:number|null;selection_label?:string}[];rules:CategoryRule[];pending:PendingExpense[];pending_count:number;
  reserves?:{id:number;name:string;version:number}[];transfer_rules?:ReserveTransferRule[];
  sessions:{id:number;filename:string;created_at:string;status:'PENDING'|'COMMITTED';version:number;balance_mode:BalanceMode;account_name:string;row_count:number}[];
  receipts:{id:number;filename:string;status:'PENDING'|'COMMITTED';entry_id:number|null;created_at:string}[];
  ocr:{available:boolean;local:boolean};selected_entry:ExpenseCandidate|null;
}
export interface CsvPreview { columns:string[];sample:string[][];count:number;header_index:number;encoding:string;delimiter:string;mapping:CsvMapping;remembered:boolean }
export interface BankImportRow {
  id:number;row_number:number;action:'NEW'|'MATCH'|'SKIP';kind:'INCOME'|'EXPENSE'|'TRANSFER';bank_kind:'INCOME'|'EXPENSE';
  date:string;amount:number;description:string;merchant:string;category_id:number|null;rule_name?:string|null;
  entry_id:number|null;transfer_id:number|null;target_account_id:number|null;errors:string[];warnings:string[];
  candidates:ExpenseCandidate[];source_exists:boolean;
  reserve_id?:number|null;reserve_version?:number|null;transfer_rule_name?:string|null;
  transfer_candidates:{id:number;source_name:string;target_name:string;amount:number;date:string}[];
}
export interface BankImportSession {
  id:number;account_id:number;account_name:string;filename:string;balance_mode:BalanceMode;status:'PENDING'|'COMMITTED';version:number;
  opening_balance:number;expected_balance:number;closing_balance:number;cash_delta:number;rows:BankImportRow[];
  result:{created:number;linked:number;skipped:number;transfers:number;balance:number;balance_mode:BalanceMode;bill_matches?:{bill_id:number;title:string;month:string;entry_ids:number[]}[]}|null;
}
export interface ReceiptLine { label:string;amount:number;category_id:number|null }
export interface ReceiptDraft {
  id:number;version:number;status:'PENDING'|'COMMITTED';account_id:number|null;entry_id:number|null;filename:string;is_pdf:boolean;raw_text:string;
  data:{merchant:string;date:string;amount:number|null;category_id:number|null;lines:ReceiptLine[]};warnings:string[];candidates:ExpenseCandidate[];
}
export interface ReceiptCommit {
  action:'NEW'|'MATCH';account_id:number;amount:number;date:string;merchant:string;entry_id?:number;entry_version?:number;
  classification_mode:'KEEP'|'GENERAL'|'SPLIT';category_id?:number|null;lines?:ReceiptLine[];
  balance_mode:BalanceMode;expected_balance:number;confirm_separate:boolean;
}
const client=createApiClient('/budget/imports');
function upload(file:File,data:object){const form=new FormData();form.append('file',file);form.append('data',JSON.stringify(data));return form;}
export const budgetImportsApi={
  get:(entry_id?:number,limit=200)=>client.get<BudgetImportsWorkspace>('',{params:{entry_id,limit}}),
  preview:(file:File,header_index?:number)=>client.post<CsvPreview>('/csv/preview',upload(file,{header_index})),
  stage:(file:File,data:{account_id:number;balance_mode:BalanceMode;mapping:CsvMapping;header_index:number},request_id:string)=>client.post<{id:number}>('/csv',upload(file,{...data,request_id})),
  session:(id:number)=>client.get<BankImportSession>(`/sessions/${id}`),
  updateRow:(id:number,row:number,data:{version:number;action?:BankImportRow['action'];kind?:BankImportRow['kind'];category_id?:number|null;target_account_id?:number|null;reserve_id?:number|null;entry_id?:number;transfer_id?:number})=>client.put(`/sessions/${id}/rows/${row}`,data),
  refresh:(id:number,version:number)=>client.post(`/sessions/${id}/refresh`,{version}),
  commit:(id:number,version:number,request_id:string)=>client.post<NonNullable<BankImportSession['result']>>(`/sessions/${id}/commit`,{version,request_id}),
  saveRule:(data:CategoryRuleInput,request_id:string)=>client.post<{id:number}>('/rules',{...data,request_id}),
  updateRule:(id:number,data:CategoryRuleInput,version:number)=>client.put(`/rules/${id}`,{...data,version}),
  saveTransferRule:(data:ReserveTransferRuleInput,request_id:string)=>client.post<{id:number}>('/transfer-rules',{...data,request_id}),
  updateTransferRule:(id:number,data:ReserveTransferRuleInput,version:number)=>client.put(`/transfer-rules/${id}`,{...data,version}),
  categorize:(entry_ids:number[],versions:Record<string,number>,category_id?:number,lines?:ReceiptLine[])=>client.post<{updated:number}>('/categorize',{entry_ids,versions,category_id,lines}),
  applyRules:(entry_ids:number[],versions:Record<string,number>)=>client.post<{updated:number;unmatched:number}>('/categorize/rules',{entry_ids,versions}),
  matches:(data:{account_id?:number;date:string;amount:number;merchant:string})=>client.get<ExpenseCandidate[]>('/matches',{params:{...data}}),
  uploadReceipt:(file:File,account_id:number|null,request_id:string)=>client.post<{id:number}>('/receipts',upload(file,{account_id,request_id})),
  receipt:(id:number)=>client.get<ReceiptDraft>(`/receipts/${id}`),
  deleteReceipt:(id:number,version:number)=>client.delete<{deleted:number}>(`/receipts/${id}`,{params:{version}}),
  receiptFile:(id:number)=>buildApiPath(`/budget/imports/receipts/${id}/file`),
  parseReceipt:(id:number,text:string,version:number)=>client.post(`/receipts/${id}/parse`,{text,version}),
  recognizeReceipt:(id:number,version:number)=>client.post(`/receipts/${id}/recognize`,{version}),
  commitReceipt:(id:number,data:ReceiptCommit,version:number,request_id:string)=>client.post<{entry_id:number;linked:boolean}>(`/receipts/${id}/commit`,{...data,version,request_id}),
};
