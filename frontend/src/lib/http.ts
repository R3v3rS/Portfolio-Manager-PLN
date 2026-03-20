import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';

export interface ApiErrorDetails {
  error?: string;
  message?: string;
  detail?: string;
  details?: string | string[] | Record<string, unknown>;
  errors?: Record<string, unknown>;
  code?: string;
  status?: number;
}

export class ApiError extends Error {
  status?: number;
  code?: string;
  details?: ApiErrorDetails['details'];
  validation?: ApiErrorDetails['errors'];
  cause?: unknown;

  constructor(message: string, options: { status?: number; code?: string; details?: ApiErrorDetails['details']; validation?: ApiErrorDetails['errors']; cause?: unknown } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
    this.validation = options.validation;
    this.cause = options.cause;
  }
}

const DEFAULT_ERROR_MESSAGE = 'Nie udało się wykonać żądania.';

const resolveMessage = (payload: ApiErrorDetails | undefined, fallback = DEFAULT_ERROR_MESSAGE) => {
  if (!payload) return fallback;
  return payload.message || payload.error || payload.detail || fallback;
};

const normalizeApiError = (error: unknown, fallbackMessage = DEFAULT_ERROR_MESSAGE) => {
  if (error instanceof ApiError) return error;

  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorDetails>;
    const payload = axiosError.response?.data;
    return new ApiError(resolveMessage(payload, fallbackMessage), {
      status: axiosError.response?.status,
      code: payload?.code,
      details: payload?.details,
      validation: payload?.errors,
      cause: error,
    });
  }

  if (error instanceof Error) {
    return new ApiError(error.message || fallbackMessage, { cause: error });
  }

  return new ApiError(fallbackMessage, { cause: error });
};

export const getErrorMessage = (error: unknown, fallbackMessage = DEFAULT_ERROR_MESSAGE) =>
  normalizeApiError(error, fallbackMessage).message;

export const getValidationErrors = (error: unknown) => normalizeApiError(error).validation;

export const createApiClient = (baseURL?: string): AxiosInstance => {
  const client = axios.create({
    baseURL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  client.interceptors.response.use(
    (response) => response,
    (error) => Promise.reject(normalizeApiError(error)),
  );

  return client;
};

const rootApi = createApiClient();

export const http = {
  get: async <T>(url: string, config?: AxiosRequestConfig) => (await rootApi.get<T>(url, config)).data,
  post: async <TResponse, TPayload = unknown>(url: string, data?: TPayload, config?: AxiosRequestConfig) =>
    (await rootApi.post<TResponse>(url, data, config)).data,
  put: async <TResponse, TPayload = unknown>(url: string, data?: TPayload, config?: AxiosRequestConfig) =>
    (await rootApi.put<TResponse>(url, data, config)).data,
  patch: async <TResponse, TPayload = unknown>(url: string, data?: TPayload, config?: AxiosRequestConfig) =>
    (await rootApi.patch<TResponse>(url, data, config)).data,
  delete: async <TResponse>(url: string, config?: AxiosRequestConfig) => (await rootApi.delete<TResponse>(url, config)).data,
};

export const toSearchParams = (params?: Record<string, string | number | boolean | null | undefined>) => {
  const searchParams = new URLSearchParams();
  if (!params) return searchParams;

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value));
    }
  });

  return searchParams;
};
