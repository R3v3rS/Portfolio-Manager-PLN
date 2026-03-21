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

const JSON_CONTENT_TYPES = ['application/json', '+json'];

const isJsonContentType = (contentType: string | null) => {
  if (!contentType) return false;
  const normalized = contentType.toLowerCase();
  return JSON_CONTENT_TYPES.some((marker) => normalized.includes(marker));
};

const maybeParseJsonText = (text: string) => {
  const trimmed = text.trim();
  if (!trimmed) return undefined;

  if (!['{', '[', '"'].includes(trimmed[0]) && trimmed !== 'null' && trimmed !== 'true' && trimmed !== 'false' && !/^\d/.test(trimmed)) {
    return undefined;
  }

  try {
    return JSON.parse(trimmed);
  } catch {
    return undefined;
  }
};

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

const extractMessage = (status: number, data: unknown, fallbackText?: string) => {
  if (typeof data === 'string' && data.trim()) return data;

  if (data && typeof data === 'object') {
    const candidate = data as Record<string, unknown>;
    const value = candidate.error ?? candidate.message ?? candidate.detail;
    if (typeof value === 'string' && value.trim()) return value;
  }

  if (fallbackText?.trim()) return fallbackText.trim();
  return `Request failed (${status})`;
};

const parseResponse = async <T>(response: Response): Promise<T> => {
  if (response.status === 204 || response.status === 205) {
    return undefined as T;
  }

  const text = await response.text();
  if (!text.trim()) {
    if (!response.ok) {
      throw new HttpError(extractMessage(response.status, undefined), response.status);
    }
    return undefined as T;
  }

  const contentType = response.headers.get('content-type');
  const shouldParseAsJson = isJsonContentType(contentType);

  let parsed: unknown;
  if (shouldParseAsJson) {
    try {
      parsed = JSON.parse(text);
    } catch {
      if (!response.ok) {
        throw new HttpError(extractMessage(response.status, undefined, text), response.status);
      }
      throw new HttpError('Nie udało się odczytać odpowiedzi JSON z serwera.', response.status);
    }
  } else {
    parsed = maybeParseJsonText(text) ?? text;
  }

  if (!response.ok) {
    throw new HttpError(extractMessage(response.status, parsed, text), response.status, parsed as T);
  }

  return parsed as T;
};

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options: HttpClientOptions = {}
): Promise<T> {
  const headers = mergeHeaders({ Accept: 'application/json' }, options.headers);
  const response = await fetch(buildUrl(options.baseURL ?? '', path, options.params), {
    method,
    headers,
    body: prepareBody(body, headers),
    signal: options.signal,
  });

  return parseResponse<T>(response);
}

export const http = {
  get: <T>(path: string, options?: HttpClientOptions) => request<T>('GET', path, undefined, options),
  post: <T>(path: string, body?: unknown, options?: HttpClientOptions) => request<T>('POST', path, body, options),
  put: <T>(path: string, body?: unknown, options?: HttpClientOptions) => request<T>('PUT', path, body, options),
  patch: <T>(path: string, body?: unknown, options?: HttpClientOptions) => request<T>('PATCH', path, body, options),
  delete: <T>(path: string, options?: HttpClientOptions) => request<T>('DELETE', path, undefined, options),
};

export const createHttpClient = (baseURL: string, defaults: Omit<HttpClientOptions, 'baseURL'> = {}) => ({
  get: <T>(path: string, options?: HttpRequestOptions) =>
    http.get<T>(path, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
  post: <T>(path: string, body?: unknown, options?: HttpRequestOptions) =>
    http.post<T>(path, body, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
  put: <T>(path: string, body?: unknown, options?: HttpRequestOptions) =>
    http.put<T>(path, body, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
  patch: <T>(path: string, body?: unknown, options?: HttpRequestOptions) =>
    http.patch<T>(path, body, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
  delete: <T>(path: string, options?: HttpRequestOptions) =>
    http.delete<T>(path, { ...defaults, ...options, baseURL, headers: mergeHeaders(defaults.headers, options?.headers) }),
});
