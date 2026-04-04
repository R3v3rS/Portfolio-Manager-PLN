import { createApiClient } from './apiConfig';
import type { BookResult, StagingRow, StagingSession } from './types/importStaging';

const portfolioHttp = createApiClient('/portfolio');

export type ImportMode = 'staging' | 'direct';

export const createStagingSession = async (
  portfolioId: number,
  file: File,
  subPortfolioId?: number | null,
  mode: ImportMode = 'staging'
): Promise<StagingSession | Record<string, unknown>> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('portfolio_id', String(portfolioId));
  formData.append('mode', mode);

  if (subPortfolioId !== null && subPortfolioId !== undefined) {
    formData.append('sub_portfolio_id', String(subPortfolioId));
  }

  return portfolioHttp.post<StagingSession | Record<string, unknown>>('/import/staging', formData);
};

export const getSession = async (sessionId: string): Promise<StagingSession> => {
  return portfolioHttp.get<StagingSession>(`/import/staging/${sessionId}`);
};

export const assignRow = async (sessionId: string, rowId: number, targetSubPortfolioId: number): Promise<StagingRow> => {
  return portfolioHttp.put<StagingRow>(`/import/staging/${sessionId}/rows/${rowId}/assign`, {
    target_sub_portfolio_id: targetSubPortfolioId,
  });
};

export const assignAll = async (
  sessionId: string,
  targetSubPortfolioId: number
): Promise<{ assigned: number; skipped: number }> => {
  return portfolioHttp.put<{ assigned: number; skipped: number }>(`/import/staging/${sessionId}/assign-all`, {
    target_sub_portfolio_id: targetSubPortfolioId,
  });
};

export const rejectRow = async (sessionId: string, rowId: number): Promise<StagingRow> => {
  return portfolioHttp.delete<StagingRow>(`/import/staging/${sessionId}/rows/${rowId}`);
};

export const bookSession = async (sessionId: string, confirmedRowIds?: number[]): Promise<BookResult> => {
  return portfolioHttp.post<BookResult>(`/import/staging/${sessionId}/book`,
    confirmedRowIds ? { confirmed_row_ids: confirmedRowIds } : {}
  );
};

export const deleteSession = async (sessionId: string): Promise<{ deleted: number }> => {
  return portfolioHttp.delete<{ deleted: number }>(`/import/staging/${sessionId}`);
};
