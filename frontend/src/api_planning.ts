import { createApiClient } from './apiConfig';
import type { BudgetBill } from './api_budget_workspace';

export interface PlanningSettings {id:number;pay_day:number|null;income_id:number|null;spending_account_id:number|null;loan_account_id:number|null;version:number;resolved_pay_day:number;resolved_income_id:number|null;resolved_spending_account_id:number|null;resolved_loan_account_id:number|null}
export interface ReserveMonthPlan {reserve_id:number;name:string;account_id:number;account_name:string;due_date:string;category_id?:number|null;automatic?:boolean;monthly_amount?:number|null;open_ended?:boolean;contributed?:number;recommended:number;planned:number;funded:number;remaining:number;priority:number;version:number;reserve_version:number;active:boolean}
export interface MonthReview {closing_snapshot?:{recorded_at:string;changed:boolean;differences:{income:number;spent:number;refunds:number}}|null;token:string;accounts:{id:number;name:string;balance:number;reserved:number;verified_on:string|null}[];corrections:{id:number;name:string;date:string;amount:number;notes:string}[];unpaid_bills:{id:number;title:string;date:string;amount:number}[];unpaid_loans:LoanMonthPlan[];missing_reserves:ReserveMonthPlan[];unassigned:number;warnings:string[]}
export interface LoanMonthPlan {id:number;name:string;date:string;amount:number;paid:boolean;category_id:number|null;installment_month:number;paid_on?:string|null;paid_amount?:number|null}
export interface PlanningWorkspace {payment_matches?:PaymentMatch[];loans?:LoanMonthPlan[];loan_warnings?:string[];month_review?:MonthReview;month_plan?:{kind:string;name:string;planned:number;done:number;remaining:number;month_cost?:number|null}[]}
export interface CategoryPolicy {category_id:number;name:string;mode:'RESET'|'ROLLOVER'|'RESERVE'|'DECIDE';reserve_id:number|null;start_month:string;version:number}
export interface ClosingDecision {destination:'RESET'|'ROLLOVER'|'RESERVE'|'SAVINGS'|'INVESTMENTS';reserve_id?:number;account_id?:number}
export interface PlanningWorkspace {closing_items?:{category_id:number;name:string;destination:ClosingDecision['destination'];amount:number;reserve_name:string|null}[]}
export interface PurchaseInput {name:string;amount:number;low:number;high:number;due_date:string;account_id:number;category_id:number|null;status:'IDEA'|'PLANNED'|'CANCELLED';notes:string;reserve_version?:number}
export interface PurchasePlan extends Omit<PurchaseInput,'status'> {id:number;status:PurchaseInput['status']|'COMPLETED';account_name:string;reserve_id:number|null;saved:number;monthly_required:number;version:number}
export interface PlanningWorkspace {settings:PlanningSettings;reserve_plans:ReserveMonthPlan[];policies:CategoryPolicy[];purchases:PurchasePlan[];bill_catalog:BudgetBill[];cycle:{start:string;end:string;next_payday:string;income:number;spent:number;expected_income:number;bills_before_payday:number};closing:{id?:number;month?:string;created_at?:string}}
const client=createApiClient('/budget/planning');
export const planningApi={
  settings:(input:Pick<PlanningSettings,'pay_day'|'income_id'|'spending_account_id'|'loan_account_id'|'version'>)=>client.put('/settings',input),
  reservePlan:(id:number,input:{month:string;amount:number;priority:number;version:number})=>client.put(`/reserve-plans/${id}`,input),
  policy:(id:number,input:Omit<CategoryPolicy,'category_id'|'name'>)=>client.put(`/category-policies/${id}`,input),
  closeMonth:(month:string,category_versions:Record<string,number>,request_id:string,amounts:Record<string,number>,review_token?:string,decisions?:Record<string,ClosingDecision>)=>client.post('/close-month',{month,category_versions,request_id,amounts,review_token,decisions}),
  createPurchase:(input:PurchaseInput,request_id:string)=>client.post('/purchases',{...input,request_id}),
  updatePurchase:(id:number,input:PurchaseInput,version:number)=>client.put(`/purchases/${id}`,{...input,version}),
};

export interface PaymentMatch {kind:"BILL"|"RESERVE";id:number;title:string;candidates:{id:number;description:string;amount:number;date:string;version:number;account_id?:number}[]}
