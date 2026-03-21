import type { ApiErrorBody, ApiErrorEnvelope, ApiSuccessEnvelope } from '../api-contract';

const FALLBACK_ERROR_MESSAGE = 'Nie udało się przetworzyć odpowiedzi serwera.';

const isPlainObject = (value: unknown): value is Record<string, unknown> => {
  return Object.prototype.toString.call(value) === '[object Object]';
};

const normalizeText = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim();
  return normalized || undefined;
};

const collectDetailMessages = (value: unknown, depth = 0): string[] => {
  if (depth > 2 || value === null || value === undefined) {
    return [];
  }

  const text = normalizeText(value);
  if (text) {
    return [text];
  }

  if (Array.isArray(value)) {
    return value.flatMap((entry) => collectDetailMessages(entry, depth + 1));
  }

  if (!isPlainObject(value)) {
    return [];
  }

  return Object.entries(value).flatMap(([key, entry]) => {
    const entryMessages = collectDetailMessages(entry, depth + 1);

    if (entryMessages.length === 0) {
      return [];
    }

    if (depth === 0 && key && entryMessages.every((message) => message !== key)) {
      return entryMessages.map((message) => `${key}: ${message}`);
    }

    return entryMessages;
  });
};

const isApiSuccessEnvelope = <TPayload>(value: unknown): value is ApiSuccessEnvelope<TPayload> => {
  return isPlainObject(value) && 'payload' in value;
};

const isApiErrorBody = (value: unknown): value is ApiErrorBody => {
  return isPlainObject(value);
};

const isApiErrorEnvelope = (value: unknown): value is ApiErrorEnvelope => {
  return isPlainObject(value) && isApiErrorBody(value.error);
};

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) {
    return undefined;
  }

  const text = await response.text();
  if (!text.trim()) {
    return undefined;
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new Error('Nie udało się odczytać odpowiedzi JSON z serwera.');
  }
}

export function extractPayload<TPayload>(responseBody: ApiSuccessEnvelope<TPayload>): TPayload;
export function extractPayload<TPayload>(responseBody: unknown): TPayload;
export function extractPayload<TPayload>(responseBody: unknown): TPayload {
  if (!isApiSuccessEnvelope<TPayload>(responseBody)) {
    throw new Error(FALLBACK_ERROR_MESSAGE);
  }

  return responseBody.payload;
}

export function extractErrorMessage(errorBody: unknown): string {
  if (!isApiErrorEnvelope(errorBody)) {
    return FALLBACK_ERROR_MESSAGE;
  }

  const { error } = errorBody;
  const message = normalizeText(error.message);
  if (message) {
    return message;
  }

  const details = error.details;
  const detailMessage = normalizeText(details);
  if (detailMessage) {
    return detailMessage;
  }

  const detailParts = collectDetailMessages(details);
  if (detailParts.length > 0) {
    return detailParts.join(', ');
  }

  const code = normalizeText(error.code);
  if (code) {
    return code;
  }

  return FALLBACK_ERROR_MESSAGE;
}

export function extractErrorMessageFromUnknown(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'body' in error) {
    const bodyMessage = extractErrorMessage((error as { body?: unknown }).body);
    if (bodyMessage !== FALLBACK_ERROR_MESSAGE) {
      return bodyMessage;
    }
  }

  if (error instanceof Error) {
    const message = normalizeText(error.message);
    if (message) {
      return message;
    }
  }

  return extractErrorMessage(error);
}

export async function parseJsonApiResponse<TPayload>(response: Response): Promise<TPayload> {
  const body = await parseBody(response);

  if (!response.ok) {
    const error = new Error(extractErrorMessage(body)) as Error & { body?: ApiErrorEnvelope };
    error.body = isApiErrorEnvelope(body) ? body : undefined;
    throw error;
  }

  return extractPayload<TPayload>(body);
}
