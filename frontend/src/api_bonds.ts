import { createApiClient } from './apiConfig';
export type BondKind='OTS'|'ROR'|'DOR'|'TOS'|'COI'|'EDO'|'ROS'|'ROD'|'CUSTOM';
export interface BondPlan {
  name:string; kind:BondKind; quantity:number; nominal:number; purchase_price:number; purchase_date:string;
  maturity_date?:string; interest_rate:number; tax_rate:number; redemption_fee:number|null;
  fee_policy:'CAP_INTEREST'|'FIRST_PERIOD'|'FULL'; payout_account_id:number|null; forecast_enabled:boolean; notes:string;
  acquisition:'BUY'|'EXISTING';
}
export interface BondPeriod {
  period:number;start_date:string;end_date:string;rate:number;assumed:boolean;gross:number;net:number;
  capitalizes:boolean;pays_cash:boolean;paid:boolean;complete:boolean;
}
export interface BondPosition extends Omit<BondPlan,'kind'|'acquisition'> {
  id:number;portfolio_id:number;principal:number;version:number;kind:BondKind|'LEGACY';acquisition:'BUY'|'EXISTING'|'LEGACY';
  remaining_quantity:number;nominal_value:number;cost_remaining:number;accrued_interest:number;estimated_interest_net:number;
  current_period_interest:number;capitalized_interest:number;pending_interest:number;total_value:number;estimated_value_net:number;
  open_profit:number;paid_interest_net:number;current_rate:number;status:'ACTIVE'|'MATURED'|'CLOSED'|'VOID';
  early_redemption_net:number|null;early_redemption_fee:number|null;warnings:string[];as_of:string;
  periods:BondPeriod[];next_event:BondPeriod|null;rates:{period:number;rate:number}[];
  events:{id:number;kind:string;date:string;quantity:number;period:number|null;net_amount:number;notes:string}[];
}
export interface BondWorkspaceData {
  as_of:string;items:BondPosition[];summary:Record<string,number>;
  kinds:Record<BondKind,{label:string;months:number|null;interval:number;capitalizes:boolean;coupons:boolean;variable:boolean}>;
  events:{key:string;bond_id:number;name:string;date:string;kind:'MATURITY'|'COUPON'|'CAPITALIZATION';net_amount:number;assumed:boolean}[];
  forecast:{date:string;bond_id:number;value:number;coupons:number}[];warnings:string[];
}
export interface BondImportRow {line:number;plan:BondPlan|null;duplicate:boolean;error:string|null}
const client=createApiClient('/portfolio/bonds');
export const bondsApi={
  workspace:(pid:number,assumed_rate?:number)=>client.get<BondWorkspaceData>(`/workspace/${pid}`,{params:{assumed_rate}}),
  create:(pid:number,plan:BondPlan,request_id:string)=>client.post<{id:number}>('',{...plan,portfolio_id:pid,request_id}),
  update:(bond:BondPosition,plan:BondPlan,request_id:string)=>client.put(`/position/${bond.id}`,{...plan,version:bond.version,request_id}),
  rate:(bond:BondPosition,period:number,rate:number,request_id:string)=>client.post(`/position/${bond.id}/rate`,{period,rate,version:bond.version,request_id}),
  settle:(bond:BondPosition,input:{kind:'COUPON'|'REDEEM';period?:number;quantity:number;net_amount:number;date:string;confirmed_actual:boolean;transfer_to_budget:boolean;history_only?:boolean},request_id:string)=>client.post(`/position/${bond.id}/settle`,{...input,version:bond.version,request_id}),
  cancel:(bond:BondPosition,request_id:string)=>client.post(`/position/${bond.id}/cancel`,{version:bond.version,request_id}),
  estimate:(bond:BondPosition,date:string,assumed_rate?:number)=>client.get<BondPosition>(`/position/${bond.id}/estimate`,{params:{date,assumed_rate}}),
  preview:(pid:number,text:string)=>client.post<{rows:BondImportRow[]}>('/import/preview',{portfolio_id:pid,text}),
  import:(pid:number,rows:BondPlan[],request_id:string)=>client.post<{ids:number[]}>('/import/book',{portfolio_id:pid,rows,request_id}),
};
