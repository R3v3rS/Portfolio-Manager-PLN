# Zadanie 7 — raport testów (logowanie integracji yfinance)

Data: 2026-03-27

## Zakres

Uruchomiono i zweryfikowano:
- testy jednostkowe helperów logowania (`_log_provider_event`, `_classify_error`),
- testy scenariuszowe z mockami `yfinance` (sukces, retry, fallback, częściowy sukces fallbacku),
- manualny przegląd wygenerowanych payloadów logów na podstawie scenariuszy testowych (format JSON i wymagane pola kontraktu z Zadania 2).

## Dług techniczny / ograniczenia

`backend/test_api_contract.py` jest obecnie poza zakresem Zadania 7 i failuje z powodu brakujących request builderów niezwiązanych z integracją `yfinance`. Zgodnie z ustaleniem, plik został pominięty przy uruchamianiu testów dla tego zadania.

## Wynik uruchomionych testów

- `backend/test_price_service_logging.py`: **7/7** testów PASS,
- `backend/test_price_service_scenarios.py`: **5/5** testów PASS,
- łącznie: **12/12** testów PASS.

## Jakie logi wygenerowały scenariusze

Scenariusze pokrywają i emitują (bezpośrednio lub przez helper) logi zawierające pola kontraktu:
- `provider`, `operation`, `status`,
- kontekst żądania (`ticker` / `tickers_count`),
- retry (`attempt`, `max_attempts`),
- czas (`duration_ms`),
- diagnostykę błędu (`error_type`, `error_message`) tam, gdzie dotyczy.

Przykładowe zdarzenia zweryfikowane scenariuszami:
- retry po timeout (`status=retry`, `level=WARNING`),
- finalna porażka retry (`status=failed`, `level=ERROR`),
- aktywacja fallbacku per ticker (`operation=get_prices.fallback`, `status=start`),
- częściowy sukces fallbacku (`operation=get_prices.fallback`, `status=partial`).

## Test manualny

Wykonano manualną weryfikację czytelności i kompletności payloadów logów na bazie przebiegów scenariuszy mockujących zachowanie produkcyjne (`yfinance` timeout, empty data, partial fallback). Format wpisów i poziomy logowania są spójne z kontraktem z Zadania 2.

Status testu manualnego: **zaakceptowany**.
