import { createHttpClient } from './http';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').trim();

const normalizeApiPath = (path: string): string => {
  const trimmed = path.trim();
  if (!trimmed) return '/api';

  const normalized = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  return normalized.startsWith('/api/') || normalized === '/api' ? normalized : `/api${normalized}`;
};

export const buildApiPath = (path: string): string => {
  const normalizedPath = normalizeApiPath(path);
  if (!API_BASE_URL) {
    return normalizedPath;
  }

  const normalizedBase = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL;
  return `${normalizedBase}${normalizedPath}`;
};

// Architektura frontendu: komponenty nie wykonują bezpośrednich requestów HTTP.
// Każdy request do backendu powinien przechodzić przez moduł API korzystający ze wspólnego klienta HTTP.
export const createApiClient = (path: string) => createHttpClient(buildApiPath(path));

export const ANALYTICS_ENDPOINTS = {
  summary: '/summary',
} as const;
