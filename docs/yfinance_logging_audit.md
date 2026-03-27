# AUDYT — integracja `yfinance` i logowanie błędów

## Zakres i metoda
Audyt wykonałem na podstawie przeszukania backendu pod kątem: `yfinance`, `yf.Ticker`, `download`, `history`, `info`, `print(...)`, `except`, `retry`, `fallback` oraz prześledzenia miejsc wywołań `PriceService`.  
Komendy użyte w audycie:
- `rg -n "yfinance|yf\.Ticker|download\(|history\(|\.info\b|print\(|except|retry|fallback" backend`
- `rg -n "import yfinance|yf\.Ticker|yf\.download|\.history\(|\.info\b|fast_info|calendar" backend`
- `rg -n "PriceService\.(sync_stock_history|get_prices|get_quotes|fetch_metadata|fetch_market_events|get_stock_analysis|warmup_cache|get_tickers_requiring_history_sync)" backend`

---

## 1) Kompletna lista punktów integracji z `yfinance`

### Bezpośrednia integracja (API calls do Yahoo przez `yfinance`)
W praktyce cała bezpośrednia integracja jest skupiona w `backend/price_service.py`:

1. `yf.download(...)` w `_download_with_retry` (wspólny wrapper dla pobierania danych).  
2. `yf.Ticker(...).history(period="5d")` w `get_prices` (fallback per ticker).  
3. `yf.Ticker(...).fast_info.last_price` w `get_prices` (ostatni fallback).  
4. `yf.download(...)` (przez `_download_with_retry`) w `sync_stock_history`.  
5. `yf.Ticker(...).info` w `fetch_metadata`.  
6. `yf.download(...)` (przez `_download_with_retry`) w `get_quotes`.  
7. `yf.Ticker(...).calendar` i `yf.Ticker(...).info` w `fetch_market_events`.  
8. `yf.Ticker(...).info` oraz `yf.Ticker(...).history(period="1y")` w `get_stock_analysis`.  

### Pośrednie punkty wejścia (moduły, które uruchamiają ścieżki `yfinance`)
1. `backend/routes_history.py` → `PriceService.sync_stock_history(ticker)`.  
2. `backend/portfolio_history_service.py` → `PriceService.fetch_metadata(...)`, `PriceService.get_tickers_requiring_history_sync(...)`, `PriceService.sync_stock_history(...)`.  
3. `backend/portfolio_trade_service.py` → `PriceService.fetch_metadata(...)`, `PriceService.sync_stock_history(...)`, `PriceService.get_prices(...)`.  
4. `backend/portfolio_valuation_service.py` → `PriceService.get_prices(...)`, `PriceService.fetch_metadata(...)`, `PriceService.get_quotes(...)`.  
5. `backend/routes_radar.py` → `PriceService.get_stock_analysis(...)`.  
6. `backend/app.py` → `PriceService.warmup_cache()` przy starcie aplikacji.  

---

## 2) Miejsca z `print(...)`, obsługą wyjątków i retry/fallback

## 3) Tabela: „miejsce → obecny log → brakujący kontekst”

| Miejsce | Obecny log / obsługa | Retry / fallback | Brakujący kontekst (luka) |
|---|---|---|---|
| `price_service.py` (init cache dir) | `print("Failed to create cache dir...")`, `print("Using yfinance cache...")` | fallback katalogu cache (`..._fallback`) | Brak `logger` + poziomu logowania; brak środowiska (host/pid), brak informacji czy fallback się udał. |
| `PriceService._download_with_retry` | `logging.warning` na próbach + `logging.error` po wyczerpaniu | retry 3x, exponential backoff | Brak tickera/zakresu dat/parametrów requestu w logu; brak czasu całkowitego i typu błędu (klasa wyjątku). |
| `PriceService.get_prices` (bulk) | `print("Fetching prices for...")`, `print("Bulk download returned empty...")`, `print("Bulk fetch failed...")`; dodatkowo `logger.error` per ticker | fallback z bulk do per-ticker | Mieszanie `print` i `logging`; brak request-id / portfolio-id; brak rozróżnienia: błąd sieci vs brak notowań vs rate limit. |
| `PriceService.get_prices` (per ticker) | `print("Fallback fetching for...")`, `print("No data for {ticker}")`, `logger.error(...)` | fallback `history` → `fast_info` → `None` cache | Brak metryki końcowej (ile tickerów sukces/porażka); `except:` bez typu przy `fast_info`; brak poziomu severity dla „No data”. |
| `PriceService.warmup_cache` | `print("Warming up...")`, `print("Cache warmup failed...")` | pośrednio używa fallbacków `get_prices` | Brak szczegółu które tickery nie przeszły; brak stacktrace (`exc_info=True`); brak czasu operacji. |
| `PriceService.sync_stock_history` | `logger.info(...)` dla przebiegu, `logger.warning` brak `Close`, `logger.error(...)` w `except` + rollback | retry przez `_download_with_retry`; overlap/self-heal zakresu dat | `logger.error(f"...")` bez `exc_info=True`; brak liczby rekordów odrzuconych/NaN; brak kodu ścieżki (np. skip/no-data/error). |
| `PriceService.fetch_metadata` | `logging.info` cache hit/fetch/refreshed; `logging.warning` na wyjątku | fallback do stale in-memory, potem stale DB | Brak informacji o wieku cache (TTL age); brak klasy wyjątku + stacktrace; brak flagi czy zwrócono dane nieświeże. |
| `PriceService.get_quotes` | `logging.error` per ticker i dla bulk failure | fallback tylko częściowy (po bulk fail brak pełnego per-ticker fetch) | Brak pełnego fallbacku po błędzie bulk; log nie zawiera listy tickerów i parametrów; brak telemetry ile tickerów ma default `0.0`. |
| `PriceService.fetch_market_events` | `print("Calendar fetch error...")`, `print("Info fetch error...")`, `print("Error fetching events...")` | fallback `calendar` → `info` → puste pola | Użycie `print` zamiast loggera; brak kontekstu etapu, brak `exc_info`, brak odróżnienia transient/permanent. |
| `PriceService.get_stock_analysis` | `print("Analyzing...")`, `print("Technical analysis failed...")`, `print("Analysis failed...")` | fallback: przy błędzie technical zwraca częściowy wynik | Brak strukturalnych logów (ticker, etap, duration); brak typu wyjątku; brak sygnału czy wynik jest częściowy (degraded mode). |
| `portfolio_history_service.py::_build_price_context` | `print("Failed to sync history for {ticker}: {e}")` | kontynuuje mimo błędu synchronizacji pojedynczego tickera | Brak `logger` i korelacji z `portfolio_id`; brak informacji o skutku biznesowym (np. brak ceny => 0). |

---

## Wniosek końcowy (skrót)
- **Integracja z `yfinance` jest scentralizowana w `backend/price_service.py`**; inne moduły korzystają z niej pośrednio przez `PriceService`.  
- **Największa luka**: niespójne logowanie (`print` vs `logging`) oraz brak kontekstu diagnostycznego (ticker, parametry zapytania, typ wyjątku, stacktrace, wynik fallbacku, wpływ na odpowiedź API).  
- **Retry/fallback istnieją**, ale nie są w pełni obserwowalne (brak metryk i jednolitego, strukturalnego logowania ścieżek degradacji).
