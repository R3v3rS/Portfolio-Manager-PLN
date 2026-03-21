import { http } from '../http';

const PPK_PRICE_URL =
  'https://mojefundusze.pl/Fundusze/PPK/Nationale-Nederlanden-DFE-Nasze-Jutro-2055-PPK';
const REQUEST_TIMEOUT_MS = 5000;
const MAX_ATTEMPTS = 2;

type PriceResult = { price: number; date: string };

interface PriceProvider {
  getPrice(): Promise<PriceResult>;
}

type CachedPrice = PriceResult & { fetchedAt: string };

class PriceProviderError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

class NetworkError extends PriceProviderError {}
class PriceParseError extends PriceProviderError {}

class DailyPriceCache {
  private cachedValue: CachedPrice | null = null;

  get(today: string): PriceResult | null {
    if (!this.cachedValue) {
      return null;
    }

    if (this.cachedValue.date === today) {
      return {
        price: this.cachedValue.price,
        date: this.cachedValue.date,
      };
    }

    return null;
  }

  set(value: PriceResult): void {
    this.cachedValue = {
      ...value,
      fetchedAt: new Date().toISOString(),
    };
  }
}

const dailyPriceCache = new DailyPriceCache();

function getTodayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function sanitizeHtml(html: string): string {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '')
    .replace(/<!--([\s\S]*?)-->/g, '')
    .replace(/\0/g, '');
}

function parsePriceFromHtml(rawHtml: string): PriceResult {
  const html = sanitizeHtml(rawHtml);

  const blockMatch = html.match(/<div\s+class=["'][^"']*col-md-8[^"']*["'][^>]*>([\s\S]*?)<\/div>/i);
  if (!blockMatch) {
    throw new PriceParseError('Unable to locate target container: div.col-md-8');
  }

  const blockHtml = blockMatch[1];

  const dateMatch = blockHtml.match(/<strong>\s*(\d{4}-\d{2}-\d{2})\s*<\/strong>/i);
  const priceMatch = blockHtml.match(/<h1>\s*([^<]+)\s*<\/h1>/i);

  const date = dateMatch?.[1]?.trim() ?? '';
  const rawPrice = priceMatch?.[1]?.trim() ?? '';

  if (!date) {
    throw new PriceParseError('Price date is missing in HTML structure.');
  }

  if (!rawPrice) {
    throw new PriceParseError('Price value is missing in HTML structure.');
  }

  const normalizedPrice = rawPrice
    .replace(/\s+/g, '')
    .replace(/PLN/gi, '')
    .replace(',', '.');

  const price = Number.parseFloat(normalizedPrice);

  if (!Number.isFinite(price)) {
    throw new PriceParseError(`Invalid parsed price value: "${rawPrice}".`);
  }

  return { price, date };
}

async function fetchWithTimeout(url: string, timeoutMs: number): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await http.getText(url, {
      headers: { Accept: 'text/html' },
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof PriceProviderError) {
      throw error;
    }

    if (error instanceof Error && error.name === 'AbortError') {
      throw new NetworkError(`PPK request timed out after ${timeoutMs}ms.`);
    }

    const errorDetails = error instanceof Error ? ` ${error.message}` : '';
    throw new NetworkError(`PPK request failed due to a network error.${errorDetails}`);
  } finally {
    clearTimeout(timeout);
  }
}

class PPKWebScraperProvider implements PriceProvider {
  async getPrice(): Promise<PriceResult> {
    let lastError: unknown;

    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
      try {
        const html = await fetchWithTimeout(PPK_PRICE_URL, REQUEST_TIMEOUT_MS);
        return parsePriceFromHtml(html);
      } catch (error) {
        lastError = error;

        if (attempt === MAX_ATTEMPTS) {
          throw error;
        }
      }
    }

    throw lastError instanceof Error
      ? lastError
      : new NetworkError('PPK request failed after retry.');
  }
}

const provider: PriceProvider = new PPKWebScraperProvider();

export async function getCurrentPPKPrice(): Promise<PriceResult> {
  const today = getTodayIsoDate();
  const cachedPrice = dailyPriceCache.get(today);

  if (cachedPrice) {
    return cachedPrice;
  }

  const freshPrice = await provider.getPrice();
  dailyPriceCache.set(freshPrice);

  return freshPrice;
}
