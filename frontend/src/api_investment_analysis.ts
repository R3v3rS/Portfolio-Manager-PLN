import {createApiClient} from './apiConfig';
import type {PortfolioValue, Holding} from './types';
import type {ActualResults} from './api_actual_results';
export type Source={id:string;label:string;href:string;data:unknown};
export type AnalysisSnapshot={portfolio_id:number;name:string;account_type:string;include_subportfolios:boolean;created_at:string;start:string;end:string;value:PortfolioValue;positions:Holding[];results:ActualResults;warnings:string[];sources:Source[];subportfolios_count:number};
export type AnswerItem={text:string;source_ids:string[]};
export type AnalysisAnswer={title:string;mode:'ai'|'data';changed:AnswerItem[];why:AnswerItem[];check:AnswerItem[];limitations:AnswerItem[]};
export type AnalysisMessage={id:string;question:string;answer:AnalysisAnswer;created_at:string;journal_id:number|null};
export type AnalysisSession={id:string;portfolio_id:number;title:string;created_at:string;snapshot:AnalysisSnapshot;messages:AnalysisMessage[]};
export type SessionList={id:string;title:string;created_at:string;messages:number};
export type AISettings={model:string;daily_budget_usd:number;input_usd_per_million:number;output_usd_per_million:number;max_output_tokens:number;version:number;used_usd:number;configured:boolean;price_note:string;budget_day:string};
export type StrategyPlan={goal:string;horizon:string;constraints:string;mode:'INSTRUMENT'|'STRATEGY';targets:{key:string;percent:number}[]};
export type PlanWorkspace={plan:StrategyPlan;version:number;portfolio_id:number;archived:boolean;instruments:string[];children:{id:number;name:string}[];account_type:string};
export type Simulation={rows:{key:string;label:string;target_percent:number;before:number;contribution:number;after:number;after_percent:number;difference:number}[];total:number;contribution:number;warnings:string[];note:string;version:number};
export type Exposure={items:{ticker:string;value:number;weight_percent:number|null;overlap:boolean;sources:{instrument:string;value:number;direct:boolean}[]}[];funds:{ticker:string;coverage_percent:number;source_date:string|null;retrieved_at:string|null;source_url:string|null;stale:boolean}[];coverage_percent:number|null;unknown_value:number;warnings:string[];missing_tickers?:string[]};
export type MaterialClaim={ticker:string;company:string;opinion:string;evidence:string;seconds:number|null;thesis:string;risks:string;horizon:string;matched_excerpt:boolean;status:string;source_url:string};
export type MaterialReview={id:string;publication_id:number;input_kind:string;created_at:string;result:{summary:string;claims:MaterialClaim[]};confirmed:Record<string,number>};
export type RelatedMaterial={id:number;ticker:string;opinion:string;evidence:string;thesis:string;title:string;url:string;published_on:string;source_id:string};
const ai=createApiClient('/ai'),analysis=createApiClient('/investment-analysis');
export const investmentAnalysisApi={
 context:(id:number,include:boolean,from:string,to:string)=>ai.get<AnalysisSnapshot>(`/context/${id}`,{params:{include_subportfolios:include?'1':'0',from,to}}),
 sessions:(id:number)=>ai.get<SessionList[]>(`/sessions/${id}`),
 session:(id:string)=>ai.get<AnalysisSession>(`/session/${id}`),
 ask:(data:{portfolio_id:number;question:string;mode:'ai'|'data';request_id:string;include_subportfolios:boolean;from:string;to:string;session_id?:string;expected_last_id?:string})=>ai.post<AnalysisSession>('/portfolio-analysis',data),
 journal:(id:string)=>ai.post<{id:number}>(`/messages/${id}/journal`,{}),
 settings:()=>ai.get<AISettings>('/settings'),saveSettings:(data:AISettings)=>ai.put<AISettings>('/settings',data),
 plan:(id:number)=>analysis.get<PlanWorkspace>(`/plans/${id}`),
 savePlan:(id:number,data:StrategyPlan & {version:number})=>analysis.put<PlanWorkspace>(`/plans/${id}`,data),
 simulate:(id:number,contribution:number)=>analysis.post<Simulation>(`/plans/${id}/simulate`,{contribution}),
 exposure:(id:number)=>analysis.get<Exposure>(`/exposure/${id}`),
 refreshFund:(ticker:string)=>analysis.post(`/funds/${encodeURIComponent(ticker)}/refresh`,{}),
 saveFund:(ticker:string,data:{source_url:string;source_date:string;constituents:{ticker:string;percent:number}[]})=>analysis.put(`/funds/${encodeURIComponent(ticker)}`,data),
 reviews:(id:number)=>analysis.get<MaterialReview[]>(`/materials/${id}`),
 article:(id:number)=>analysis.get<{text:string;captured_at:string;source_url:string;truncated:boolean}|null>(`/materials/${id}/text`),
 fetchArticle:(id:number)=>analysis.post<{text:string;captured_at:string;source_url:string;truncated:boolean}>(`/materials/${id}/text`,{}),
 analyzeMaterial:(id:number,data:{request_id:string;input_kind:string;text:string;captured_at?:string})=>analysis.post<MaterialReview[]>(`/materials/${id}/analyze`,data),
 confirmMaterial:(id:string,index:number,data:MaterialClaim & {confirmed:boolean})=>analysis.post<{id:number}>(`/material-reviews/${id}/${index}/confirm`,data),
 related:(id:number)=>analysis.get<RelatedMaterial[]>(`/related/${id}`),
};
