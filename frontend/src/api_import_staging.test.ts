import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpError } from './http';

const getMock = vi.fn();
const postMock = vi.fn();
const putMock = vi.fn();
const deleteMock = vi.fn();

vi.mock('./apiConfig', () => ({
  createApiClient: () => ({ get: getMock, post: postMock, put: putMock, delete: deleteMock }),
}));

describe('api_import_staging', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('createStagingSession returns payload on success', async () => {
    const { createStagingSession } = await import('./api_import_staging');
    const file = new File(['x'], 'import.csv', { type: 'text/csv' });
    postMock.mockResolvedValueOnce({ session_id: 'abc', portfolio_id: 1, rows: [], summary: { total: 0, pending: 0, conflicts: 0, rejected: 0, missing_symbols: [] } });

    const result = await createStagingSession(1, file, 2, 'staging');
    expect(result).toMatchObject({ session_id: 'abc', portfolio_id: 1 });

    const [path, body] = postMock.mock.calls[0];
    expect(path).toBe('/import/staging');
    expect(body).toBeInstanceOf(FormData);
    const form = body as FormData;
    expect(form.get('portfolio_id')).toBe('1');
    expect(form.get('sub_portfolio_id')).toBe('2');
    expect(form.get('mode')).toBe('staging');
  });

  it('createStagingSession throws on server error', async () => {
    const { createStagingSession } = await import('./api_import_staging');
    const file = new File(['x'], 'import.csv', { type: 'text/csv' });
    postMock.mockRejectedValueOnce(new HttpError('boom', 500));

    await expect(createStagingSession(1, file)).rejects.toThrow('boom');
  });

  it('getSession returns payload on success', async () => {
    const { getSession } = await import('./api_import_staging');
    getMock.mockResolvedValueOnce({ session_id: 's1', portfolio_id: 4, rows: [], summary: { total: 0, pending: 0, conflicts: 0, rejected: 0, missing_symbols: [] } });

    await expect(getSession('s1')).resolves.toMatchObject({ session_id: 's1' });
    expect(getMock).toHaveBeenCalledWith('/import/staging/s1');
  });

  it('getSession throws on server error', async () => {
    const { getSession } = await import('./api_import_staging');
    getMock.mockRejectedValueOnce(new HttpError('not found', 404));

    await expect(getSession('missing')).rejects.toThrow('not found');
  });

  it('assignRow returns payload on success', async () => {
    const { assignRow } = await import('./api_import_staging');
    putMock.mockResolvedValueOnce({ id: 1, status: 'assigned' });

    await expect(assignRow('s1', 1, 11)).resolves.toMatchObject({ id: 1, status: 'assigned' });
    expect(putMock).toHaveBeenCalledWith('/import/staging/s1/rows/1/assign', { target_sub_portfolio_id: 11 });
  });

  it('assignRow throws on server error', async () => {
    const { assignRow } = await import('./api_import_staging');
    putMock.mockRejectedValueOnce(new HttpError('unprocessable', 422));

    await expect(assignRow('s1', 1, 11)).rejects.toThrow('unprocessable');
  });

  it('assignAll returns payload on success', async () => {
    const { assignAll } = await import('./api_import_staging');
    putMock.mockResolvedValueOnce({ assigned: 3, skipped: 1 });

    await expect(assignAll('s1', 5)).resolves.toEqual({ assigned: 3, skipped: 1 });
    expect(putMock).toHaveBeenCalledWith('/import/staging/s1/assign-all', { target_sub_portfolio_id: 5 });
  });

  it('assignAll throws on server error', async () => {
    const { assignAll } = await import('./api_import_staging');
    putMock.mockRejectedValueOnce(new HttpError('boom', 500));

    await expect(assignAll('s1', 5)).rejects.toThrow('boom');
  });

  it('rejectRow returns payload on success', async () => {
    const { rejectRow } = await import('./api_import_staging');
    deleteMock.mockResolvedValueOnce({ id: 7, status: 'rejected' });

    await expect(rejectRow('s1', 7)).resolves.toMatchObject({ id: 7, status: 'rejected' });
    expect(deleteMock).toHaveBeenCalledWith('/import/staging/s1/rows/7');
  });

  it('rejectRow throws on server error', async () => {
    const { rejectRow } = await import('./api_import_staging');
    deleteMock.mockRejectedValueOnce(new HttpError('boom', 500));

    await expect(rejectRow('s1', 7)).rejects.toThrow('boom');
  });

  it('bookSession returns payload on success', async () => {
    const { bookSession } = await import('./api_import_staging');
    postMock.mockResolvedValueOnce({ booked: 1, booked_tx_only: 1, skipped_conflicts: 0, rejected: 0, errors: [] });

    await expect(bookSession('s1', [2, 3])).resolves.toMatchObject({ booked: 1, booked_tx_only: 1 });
    expect(postMock).toHaveBeenCalledWith('/import/staging/s1/book', { confirmed_row_ids: [2, 3] });
  });

  it('bookSession throws on server error', async () => {
    const { bookSession } = await import('./api_import_staging');
    postMock.mockRejectedValueOnce(new HttpError('boom', 500));

    await expect(bookSession('s1')).rejects.toThrow('boom');
  });

  it('deleteSession returns payload on success', async () => {
    const { deleteSession } = await import('./api_import_staging');
    deleteMock.mockResolvedValueOnce({ deleted: 4 });

    await expect(deleteSession('s1')).resolves.toEqual({ deleted: 4 });
    expect(deleteMock).toHaveBeenCalledWith('/import/staging/s1');
  });

  it('deleteSession throws on server error', async () => {
    const { deleteSession } = await import('./api_import_staging');
    deleteMock.mockRejectedValueOnce(new HttpError('boom', 500));

    await expect(deleteSession('s1')).rejects.toThrow('boom');
  });
});
