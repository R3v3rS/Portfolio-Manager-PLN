export type BudgetFilterValues={search:string;account:string;category:string;kind:string;scope:string};
export type SavedBudgetFilter=BudgetFilterValues&{name:string};
const key='portfolio-manager.budget-filters.v1';
const fields=['search','account','category','kind','scope'] as const;
export function readBudgetFilters():SavedBudgetFilter[]{
  try{const raw:unknown=JSON.parse(localStorage.getItem(key)??'[]');if(!Array.isArray(raw))return [];return raw.filter((item):item is SavedBudgetFilter=>!!item&&typeof item==='object'&&typeof item.name==='string'&&item.name.length>0&&item.name.length<=60&&fields.every(field=>typeof item[field]==='string'&&item[field].length<=200)).slice(0,12);}catch{return [];}
}
export function writeBudgetFilters(items:SavedBudgetFilter[]){localStorage.setItem(key,JSON.stringify(items.slice(0,12)));}
