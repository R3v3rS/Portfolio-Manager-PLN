export interface ApiSuccessEnvelope<T> {
  status: 'success';
  message?: string;
  payload: T;
}

export interface ApiErrorEnvelope {
  status: 'error';
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
}

type ApiEnvelope<T> = ApiSuccessEnvelope<T> | ApiErrorEnvelope | T;

export function extractPayload<T>(data: ApiEnvelope<T>): T {
  if (
    data &&
    typeof data === 'object' &&
    'status' in data &&
    (data as { status?: string }).status === 'success' &&
    'payload' in data
  ) {
    return (data as ApiSuccessEnvelope<T>).payload;
  }

  return data as T;
}

export function extractErrorMessage(data: unknown, fallback: string = 'Request failed'): string {
  if (!data || typeof data !== 'object') {
    return fallback;
  }

  if ('error' in data) {
    const errorValue = (data as { error?: unknown }).error;
    if (typeof errorValue === 'string' && errorValue.trim()) {
      return errorValue;
    }
    if (
      errorValue &&
      typeof errorValue === 'object' &&
      'message' in errorValue &&
      typeof (errorValue as { message?: unknown }).message === 'string'
    ) {
      return (errorValue as { message: string }).message;
    }
  }

  if ('message' in data && typeof (data as { message?: unknown }).message === 'string') {
    return (data as { message: string }).message;
  }

  return fallback;
}

export async function parseJsonApiResponse<T>(response: Response, fallbackMessage = 'Request failed'): Promise<T> {
  const raw = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(extractErrorMessage(raw, fallbackMessage));
  }

  return extractPayload<T>(raw as ApiEnvelope<T>);
}
