import { createApiClient } from './apiConfig';
export type ForecastKind='INCOME'|'BILL'|'LOAN'|'DAILY'|'GOAL'|'RESERVE_ADD'|'RESERVE_COST'|'EXPENSE'|'TRANSFER_IN'|'ADJUSTMENT';
export interface ExpectedIncomePlan { name:string;account_id:number;amount:number;start_date:string;end_date:string|null;frequency:'ONCE'|'MONTHLY' }
export interface ExpectedIncome extends ExpectedIncomePlan { id:number;account_name:string;active:boolean;version:number;next_occurrence:string|null;overdue:boolean;received_count:number }
export interface ForecastOptions { income_percent?:number;buffer?:number;variable_monthly?:number;excluded?:string;purchase_id?:number;purchase_amount?:number;purchase_date?:string }
export interface ForecastSummary { days:number;date:string;balance:number|null;available:number|null;reserved:number;minimum:number|null;minimum_date:string;minimum_balance:number|null;first_shortfall:string|null;first_below_buffer:string|null;totals:Record<ForecastKind,number> }
export interface ForecastEvent { key:string;date:string;scheduled_date:string;kind:ForecastKind;title:string;amount:number;cash_delta:number;reserved_delta:number;href:string;detail:string;recorded:boolean;account_id?:number|null;account_name?:string|null }
export interface AccountForecast {id:number;name:string;opening:{balance:number;reserved:number;available:number};points:CashForecast['points'];summaries:{days:number;date:string;balance:number;reserved:number;available:number;minimum:number;first_shortfall:string|null}[]}
export interface CashForecast {
  month_plans?:ForecastMonthPlan[];
  as_of:string;end_date:string;accounts:{id:number;name:string;balance:number}[];
  opening:{balance:number;reserved:number;available:number};
  options:{income_percent:number;buffer:number;variable_monthly:number|null;default_variable_monthly:number;excluded:string[]};
  points:{date:string;balance:number;available:number;reserved:number}[];summaries:ForecastSummary[];events:ForecastEvent[];
  sources:{key:string;kind:ForecastKind;name:string;amount:number;href:string;included:boolean}[];incomes:ExpectedIncome[];
  recent_incomes:{id:number;account_id:number;date:string;description:string;amount:number}[];warnings:string[];
  account_forecasts?:AccountForecast[];
  transfer_suggestions?:{source_account_id:number;source_name:string;target_account_id:number;target_name:string;amount:number;by_date:string;reason:string}[];
  before_income?:{next_payday:string;through:string;minimum:number;must_pay:number;balance:number;available:number};
}
export interface ForecastMonthPlan {month:string;ordinary_limit:number;ordinary_remaining:number;income:number;bills:number;loans:number;reserves:number;reserve_payments:number;investments:number;scenario:boolean;categories:{category_id:number;name:string;amount:number;source:'DEFAULT'|'MONTH'|'ESTIMATE'|'MEDIA'|'NONE';source_month:string|null}[]}
export interface IncomeReceiptInput { occurrence_date:string;amount?:number;date?:string;existing_entry_id?:number }
const client=createApiClient('/budget/forecast');
export const forecastApi={
  get:(options:ForecastOptions={})=>client.get<CashForecast>('',{params:{...options}}),
  createIncome:(plan:ExpectedIncomePlan,request_id:string)=>client.post<{id:number}>('/incomes',{...plan,request_id}),
  updateIncome:(id:number,plan:ExpectedIncomePlan,version:number)=>client.put(`/incomes/${id}`,{...plan,version}),
  setIncomeActive:(id:number,active:boolean,version:number)=>client.put(`/incomes/${id}/active`,{active,version}),
  receiveIncome:(id:number,input:IncomeReceiptInput,version:number,request_id:string)=>client.post<{id:number;budget_entry_id:number}>(`/incomes/${id}/receive`,{...input,version,request_id}),
};
