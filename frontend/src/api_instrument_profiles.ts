import { createApiClient } from './apiConfig';

const instrumentHttp = createApiClient('/instrument-profiles');
const categoryHttp = createApiClient('/categories');
const etfHttp = createApiClient('/etf-allocations');

export const listInstrumentProfiles = () => instrumentHttp.get<any[]>('');
export const upsertInstrumentProfile = (payload: unknown) => instrumentHttp.post<any>('', payload);
export const getCategories = (type: 'SECTOR' | 'COUNTRY') => categoryHttp.get<any[]>(`?type=${type}`);
export const aiClassifyInstrument = (ticker: string, payload: unknown) => instrumentHttp.post<any>(`/${ticker}/ai-classify`, payload);
export const getEtfAllocations = (ticker: string) => etfHttp.get<any[]>(`/${ticker}`);
export const replaceEtfAllocations = (ticker: string, allocations: unknown[]) => etfHttp.put<any[]>(`/${ticker}`, { allocations });
export const aiClassifyEtf = (ticker: string, text: string) => instrumentHttp.post<any>(`/${ticker}/ai-classify-etf`, { text });
