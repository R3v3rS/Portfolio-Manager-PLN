import { parseJsonApiResponse } from './http/response';

export type QueryParamValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | Array<string | number | boolean | null | undefined>;

export type QueryParams = Record<string, QueryParamValue>;

export interface HttpRequestOptions {
  headers?: HeadersInit;
  params?: QueryParams;
  signal?: AbortSignal;
}

export interface HttpClientOptions extends HttpRequestOptions {
  baseURL?: string;
}

export class HttpError<T = unknown> extends Error {
  status: number;
  data?: T;

  constructor(message: string, status: number, data?: T) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
    this.data = data;
  }
}

const isBodyInit = (value: unknown): value is BodyInit => {
  return (
    typeof value === 'string' ||
    value instanceof FormData ||
    value instanceof URLSearchParams ||
    value instanceof Blob ||
    value instanceof ArrayBuffer ||
    ArrayBuffer.isView(value)
  );
};

const mergeHeaders = (...headersList: Array<HeadersInit | undefined>) => {
  const result = new Headers();

  headersList.forEach((headers) => {
    if (!headers) return;
    new Headers(headers).forEach((value, key) => {
      result.set(key, value);
    });
  });

  return result;
};

const buildUrl = (baseURL: string, path: string, params?: QueryParams) => {
  const url = new URL(path, window.location.origin);

  if (!/^https?:\/\//.test(path) && !path.startsWith('/')) {
    const normalizedBase = baseURL.endsWith('/') ? baseURL : `${baseURL}/`;
    const normalizedPath = path.startsWith('./') ? path.slice(2) : path;
    return buildUrl(baseURL, `${normalizedBase}${normalizedPath}`, params);
  }

  if (baseURL && path.startsWith('/')) {
    const normalizedBase = baseURL.endsWith('/') ? baseURL.slice(0, -1) : baseURL;
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return buildUrl('', `${normalizedBase}${normalizedPath}`, params);
  }

  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value === null || value === undefined) return;

    if (Array.isArray(value)) {
      value.forEach((entry) => {
        if (entry !== null && entry !== undefined) {
          url.searchParams.append(key, String(entry));
        }
      });
      return;
    }

    url.searchParams.set(key, String(value));
  });

  return `${url.pathname}${url.search}${url.hash}`;
};

const prepareBody = (body: unknown, headers: Headers) => {
  if (body === undefined || body === null) {
    headers.delete('Content-Type');
    return undefined;
  }

  if (body instanceof FormData) {
    headers.delete('Content-Type');
    return body;
  }

  if (isBodyInit(body)) {
    return body;
  }

  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return JSON.stringify(body);
};

async function request<T>(
  method: string,
  path: string,
  body: unknown = undefined,
  options: HttpClientOptions = {},
  parser: (response: Response) => Promise<T> = parseJsonApiResponse
): Promise<T> {
  const headers = mergeHeaders({ Accept: 'application/json' }, options.headers);
  const response = await fetch(buildUrl(options.baseURL ?? '', path, options.params), {
    method,
    headers,
    body: prepareBody(body, headers),
    signal: options.signal,
  });

  try {
    return await parser(response);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Request failed';
    const data = typeof error === 'object' && error !== null && 'body' in error ? (error as { body?: T }).body : undefined;
    throw new HttpError<T>(message, response.status, data);
  }
}

async function requestText(
  method: string,
  path: string,
  body: unknown = undefined,
  options: HttpClientOptions = {}
): Promise<string> {
  const headers = mergeHeaders({ Accept: 'text/plain, text/html, */*' }, options.headers);
  const response = await fetch(buildUrl(options.baseURL ?? '', path, options.params), {
    method,
    headers,
    body: prepareBody(body, headers),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new HttpError(`Request failed with status ${response.status}`, response.status);
  }

  return response.text();
}

export const http = {
  get: <T>(path: string, options?: HttpClientOptions) => request<T>('GET', path, undefined, options),
  getText: (path: string, options?: HttpClientOptions) => requestText('GET', path, undefined, options),
  post: <T>(path: string, body?: unknown, options?: HttpClientOptions) => request<T>('POST', path, body, options),
  put: <T>(path: string, body?: unknown, options?: HttpClientOptions) => request<T>('PUT', path, body, options),
  patch: <T>(path: string, body?: unknown, options?: HttpClientOptions) => request<T>('PATCH', path, body, options),
  delete: <T>(path: string, options?: HttpClientOptions) => request<T>('DELETE', path, undefined, options),
};

export const createHttpClient = (baseURL: string, defaults: Omit<HttpClientOptions, 'baseURL'> = {}) => ({
  get: <T>(path: string, options?: HttpRequestOptions) =>
    http.get<T>(path, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
  getText: (path: string, options?: HttpRequestOptions) =>
    http.getText(path, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
  post: <T>(path: string, body?: unknown, options?: HttpRequestOptions) =>
    http.post<T>(path, body, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
  put: <T>(path: string, body?: unknown, options?: HttpRequestOptions) =>
    http.put<T>(path, body, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
  patch: <T>(path: string, body?: unknown, options?: HttpRequestOptions) =>
    http.patch<T>(path, body, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
  delete: <T>(path: string, options?: HttpRequestOptions) =>
    http.delete<T>(path, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
});
