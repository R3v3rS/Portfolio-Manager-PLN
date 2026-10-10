import { createApiClient } from './apiConfig';
export type JournalKind = 'IDEA' | 'BUY' | 'ADD' | 'HOLD' | 'REDUCE' | 'SELL' | 'NOTE';
export type JournalStatus = 'WATCHING' | 'ACTIVE' | 'CLOSED';
export type ReviewOutcome = 'NOTE' | 'CONFIRMED' | 'CHANGED' | 'INVALIDATED';
export type JournalPlan = { title:string;entry_date:string;kind:JournalKind;status:JournalStatus;ticker:string|null;portfolio_id:number|null;confidence:number|null;thesis:string;risks:string;invalidation:string;exit_plan:string;review_date:string|null;tags:string[] };
export type JournalEntry = JournalPlan & { id:number;version:number;is_archived:boolean;created_at:string;updated_at:string;portfolio_name:string|null;portfolio_archived:boolean|null;review_count:number;review_due:boolean };
export type JournalReview = { id:number;entry_id:number;review_date:string;outcome:ReviewOutcome;notes:string;lessons:string;next_review_date:string|null;entry_status:JournalStatus;created_at:string };
export type ReviewPlan = Pick<JournalReview,'review_date'|'outcome'|'notes'|'lessons'|'next_review_date'|'entry_status'> & { version:number };
export type JournalDetail = JournalEntry & { reviews:JournalReview[];revisions:{version:number;reason:string;created_at:string;snapshot:JournalEntry}[] };
export type JournalWorkspace = { entries:JournalEntry[];total:number;page:number;page_size:number;stats:{active:number;watching:number;closed:number;due:number;archived:number};portfolios:{id:number;name:string;is_archived:boolean}[];tags:string[];as_of:string };
export type JournalFilters = { q:string;status:string;kind:string;portfolio:string;archived:string;due:string;tag:string;ticker:string;page:number };
const client = createApiClient('/investor-journal');
export const journalApi = {
  list:(filters:JournalFilters) => client.get<JournalWorkspace>('', {params:filters}),
  detail:(id:number) => client.get<JournalDetail>(`/${id}`),
  create:(plan:JournalPlan) => client.post<{id:number}>('',plan),
  update:(id:number,plan:JournalPlan,version:number) => client.put<{id:number}>(`/${id}`,{...plan,version}),
  archive:(id:number,archived:boolean,version:number) => client.put<{id:number}>(`/${id}/archive`,{archived,version}),
  review:(id:number,plan:ReviewPlan) => client.post<{id:number;entry_id:number}>(`/${id}/reviews`,plan),
  export:() => client.get<{schema_version:number;exported_at:string;entries:JournalDetail[]}>('/export'),
};
