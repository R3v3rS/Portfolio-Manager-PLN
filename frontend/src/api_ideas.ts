import { createApiClient } from './apiConfig';
export type ResearchSource = {id:string;name:string;kind:string;url:string;checked_at:string|null;status:string;message:string};
export type Publication = {id:number;source_id:string;url:string;title:string;published_on:string;excerpt:string;publisher:string;provenance:string;suggestions:string[];captured_at:string};
export type IdeaPlan = {publication_id:number;ticker:string;opinion:string;stage:string;thesis:string;risks:string;evidence:string;horizon:string};
export type ResearchIdea = IdeaPlan & {id:number;source_id:string;title:string;url:string;published_on:string;company_name:string;is_held:boolean;is_watched:boolean};
export type ResearchWorkspace = {sources:ResearchSource[];publications:Publication[];ideas:ResearchIdea[];months:string[];instruments:{ticker:string;company_name:string}[];as_of:string};
const client=createApiClient('/investment-ideas');
export const ideasApi={
  workspace:(month:string)=>client.get<ResearchWorkspace>('',{params:month?{month}:{}}),
  refresh:()=>client.post<{sources:{source_id:string;status:string;message:string}[]}>('/refresh',{}),
  publication:(data:{source_id:string;url:string;title:string;published_on:string})=>client.post<{id:number}>('/publications',data),
  save:(data:IdeaPlan,id?:number)=>id?client.put<{id:number}>(`/ideas/${id}`,data):client.post<{id:number}>('/ideas',data),
};
