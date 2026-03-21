const JSON_CONTENT_TYPES = ['application/json', '+json'];
const FALLBACK_ERROR_MESSAGE = 'Nie udało się przetworzyć odpowiedzi serwera.';

const isPlainObject = (value: unknown): value is Record<string, unknown> => {
  return Object.prototype.toString.call(value) === '[object Object]';
};

const isJsonContentType = (contentType: string | null) => {
  if (!contentType) return false;
  const normalized = contentType.toLowerCase();
  return JSON_CONTENT_TYPES.some((marker) => normalized.includes(marker));
};

const maybeParseJsonText = (text: string) => {
  const trimmed = text.trim();
  if (!trimmed) return undefined;

  if (!['{', '[', '"'].includes(trimmed[0]) && trimmed !== 'null' && trimmed !== 'true' && trimmed !== 'false' && !/^-?\d/.test(trimmed)) {
    return undefined;
  }

  try {
    return JSON.parse(trimmed);
  } catch {
    return undefined;
  }
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
    return value.flatMap((entry) => collectDetailMessages(entry, depth + 1)).filter(Boolean);
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

const getErrorContainer = (body: unknown): Record<string, unknown> | undefined => {
  if (!isPlainObject(body)) {
    return undefined;
  }

  if (isPlainObject(body.error)) {
    return body.error;
  }

  return body;
};

const hasBusinessError = (body: unknown): boolean => {
  if (!isPlainObject(body)) {
    return false;
  }

  if (body.success === false || body.ok === false) {
    return true;
  }

  const errorField = body.error;
  if (typeof errorField === 'string') {
    return Boolean(errorField.trim());
  }

  if (isPlainObject(errorField)) {
    return Boolean(
      normalizeText(errorField.message) ||
        normalizeText(errorField.details) ||
        normalizeText(errorField.code)
    );
  }

  return false;
};

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) {
    return undefined;
  }

  const text = await response.text();
  if (!text.trim()) {
    return undefined;
  }

  const contentType = response.headers.get('content-type');

  if (isJsonContentType(contentType)) {
    try {
      return JSON.parse(text);
    } catch {
      if (response.ok) {
        throw new Error('Nie udało się odczytać odpowiedzi JSON z serwera.');
      }

      return text;
    }
  }

  return maybeParseJsonText(text) ?? text;
}

export function extractPayload<T = unknown>(responseBody: unknown): T {
  if (responseBody === undefined) {
    return undefined as T;
  }

  if (responseBody === null) {
    return null as T;
  }

  if (isPlainObject(responseBody)) {
    if ('payload' in responseBody) {
      return responseBody.payload as T;
    }

    if ('data' in responseBody) {
      return responseBody.data as T;
    }
  }

  return responseBody as T;
}

export function extractErrorMessage(errorBody: unknown): string {
  const directMessage = normalizeText(errorBody);
  if (directMessage) {
    return directMessage;
  }

  const container = getErrorContainer(errorBody);
  if (!container) {
    return FALLBACK_ERROR_MESSAGE;
  }

  const message = normalizeText(container.message);
  if (message) {
    return message;
  }

  const detail = normalizeText(container.detail);
  if (detail) {
    return detail;
  }

  const legacyError = normalizeText(container.error);
  if (legacyError) {
    return legacyError;
  }

  const details = container.details;
  const detailMessage = normalizeText(details);
  if (detailMessage) {
    return detailMessage;
  }

  const detailParts = collectDetailMessages(details);
  if (detailParts.length > 0) {
    return detailParts.join(', ');
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

export async function parseJsonApiResponse<T = unknown>(response: Response): Promise<T> {
  const body = await parseBody(response);

  if (!response.ok || hasBusinessError(body)) {
    const error = new Error(extractErrorMessage(body)) as Error & { body?: unknown };
    error.body = body;
    throw error;
  }

  return extractPayload<T>(body);
}
