import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpError, http } from './http';

describe('http client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('serializes query params and skips undefined/null values', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ payload: { ok: true } }), { status: 200 })
    );

    await http.get('/api/items', {
      params: {
        q: 'abc',
        page: 2,
        active: true,
        omittedA: undefined,
        omittedB: null,
        tags: ['x', undefined, null, 'y'],
      },
    });

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toBe('/api/items?q=abc&page=2&active=true&tags=x&tags=y');
  });

  it('sends JSON body by default and keeps explicit body for text requests', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ payload: { ok: true } }), { status: 200 })
    );

    await http.post('/api/create', { name: 'Portfolio', amount: 123 });

    const [, init] = vi.mocked(fetch).mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get('Content-Type')).toContain('application/json');
    expect(init?.body).toBe(JSON.stringify({ name: 'Portfolio', amount: 123 }));
  });

  it.each([400, 401, 403, 404, 409, 422, 500])('wraps parser errors into HttpError for status %s', async (status) => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ error: { code: 'E_GENERIC', message: `Status ${status}`, details: { status } } }), {
        status,
      })
    );

    await expect(http.get('/api/fail')).rejects.toMatchObject({
      name: 'HttpError',
      status,
      data: { error: { code: 'E_GENERIC', message: `Status ${status}`, details: { status } } },
    });
  });

  it('keeps AbortError for cancellation and does not remap into HttpError', async () => {
    const abortError = Object.assign(new Error('The operation was aborted.'), { name: 'AbortError' });
    vi.mocked(fetch).mockRejectedValueOnce(abortError);

    await expect(http.get('/api/cancel')).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('keeps network errors as-is when fetch rejects', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(http.get('/api/network')).rejects.toBeInstanceOf(TypeError);
  });
});
