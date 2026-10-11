import {createApiClient} from './apiConfig';
const api=createApiClient('/backups');
export type BackupItem={name:string;created_at:string;size:number;kind:string};
export const backupsApi={
 get:()=>api.get<{items:BackupItem[];daily_retention:number;update_retention:number}>('/'),
 create:()=>api.post<{name:string}>('/'),
 restore:(name:string,confirmation:string)=>api.post<{restored:string;rescue_copy:string}>('/restore',{name,confirmation}),
};
