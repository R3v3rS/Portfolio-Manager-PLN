# Plan wykonawczy dla agenta AI: Lepsze logowanie błędów integracji z yfinance

> Cel dokumentu: dać agentowi AI **jednoznaczną instrukcję wdrożenia krok po kroku** w formacie: **Zadanie 1, Zadanie 2, ...**

## Definicja celu (co ma być osiągnięte)
Agent ma wdrożyć spójne, użyteczne i „produkcyjnie bezpieczne” logowanie dla integracji `yfinance` w backendzie, tak aby:
- każdy błąd miał pełny kontekst (co, gdzie, dla jakiego tickera, która próba),
- retry i fallback były widoczne w logach,
- zminimalizować `print(...)` i niespójne komunikaty,
- ograniczyć szum logów przy awariach masowych.

---

## Zasady wykonania dla agenta
1. Pracuj **sekwencyjnie**: nie zaczynaj kolejnego zadania, dopóki poprzednie nie spełnia kryteriów odbioru.
2. Po każdym zadaniu wykonaj mini-raport: `co zrobiono`, `jak sprawdzono`, `wynik`.
3. Jeśli zadanie jest zablokowane (np. brak testów/infrastruktury), zapisz to jawnie i przejdź do wariantu fallback z dokumentu.
4. W commitach używaj prefiksów: `task-1`, `task-2`, ...

---

## Zadanie 1 — Audyt obecnej integracji i logowania

### Cel
Zidentyfikować wszystkie punkty, w których backend komunikuje się z `yfinance` oraz jak obecnie logowane są błędy.

### Kroki implementacyjne
1. Przeszukaj kod pod kątem `yfinance`, `yf.Ticker`, `download`, `history`, `info`.
2. Zrób listę miejsc w `backend/price_service.py` (i ewentualnie innych plikach), gdzie:
   - używane jest `print(...)`,
   - łapane są wyjątki,
   - wykonywany jest retry/fallback.
3. Utwórz krótką tabelę „miejsce → obecny log → brakujący kontekst”.

### Artefakt wyjściowy
- Sekcja `AUDYT` w tym pliku lub osobny plik `docs/yfinance_logging_audit.md`.

### Kryteria odbioru
- Jest kompletna lista punktów integracji.
- Dla każdego punktu jest wskazana luka w logowaniu.

---

## Zadanie 2 — Kontrakt logowania (docelowy format logów)

### Cel
Zdefiniować jednolity schemat logów dla integracji zewnętrznej `yfinance`.

### Kroki implementacyjne
1. Ustal wymagane pola logu:
   - `provider`,
   - `operation`,
   - `ticker` / `tickers_count`,
   - `attempt`, `max_attempts`,
   - `duration_ms`,
   - `status` (`success|retry|failed|partial`),
   - `error_type`, `error_message`,
   - `request_id` lub `trace_id` (jeśli dostępne).
2. Ustal poziomy logowania:
   - `DEBUG` — detale techniczne,
   - `INFO` — start/sukces,
   - `WARNING` — retry/fallback/degradacja,
   - `ERROR` — finalna porażka.
3. Zapisz kontrakt w dokumentacji technicznej.

### Artefakt wyjściowy
- Sekcja `KONTRAKT LOGÓW` w dokumentacji.

### Kryteria odbioru
- Każda operacja `yfinance` ma przypisany `operation` i oczekiwany poziom logu.

---

## KONTRAKT LOGÓW

> Dotyczy wszystkich wywołań zewnętrznego providera `yfinance` realizowanych przez `PriceService`.

### 1) Schemat pola logu (wymagany)

| Pole | Typ | Wymagane | Opis / zasada |
|---|---|---|---|
| `provider` | `string` | tak | Stała wartość: `yfinance`. |
| `operation` | `string` | tak | Nazwa operacji biznesowo-technicznej (patrz tabela operacji poniżej). |
| `ticker` | `string` | warunkowo | Wymagane dla operacji pojedynczego waloru. |
| `tickers_count` | `int` | warunkowo | Wymagane dla operacji zbiorczych (`bulk`). |
| `attempt` | `int` | warunkowo | Numer próby dla retry (1..`max_attempts`). |
| `max_attempts` | `int` | warunkowo | Maksymalna liczba prób dla operacji z retry. |
| `duration_ms` | `int` | tak | Czas trwania pojedynczej operacji / próby w milisekundach. |
| `status` | `enum` | tak | Jedna z wartości: `success`, `retry`, `failed`, `partial`. |
| `error_type` | `string` | warunkowo | Wymagane przy `status=retry|failed|partial` (np. `network_timeout`, `rate_limit`, `empty_data`, `invalid_ticker`, `parsing_error`, `unknown`). |
| `error_message` | `string` | warunkowo | Skrócony, bezpieczny opis błędu (bez danych wrażliwych). |
| `request_id` / `trace_id` | `string` | warunkowo | Jeżeli dostępne w kontekście requestu; przynajmniej jedno z pól powinno być przekazane. |

#### Reguły walidacyjne kontraktu
- Dla zdarzeń `success` pola `error_type` i `error_message` **powinny być puste** (`null`).
- Dla zdarzeń `retry` pole `attempt` **musi** być `< max_attempts`.
- Dla zdarzeń `failed` w operacjach z retry pole `attempt` **musi** być równe `max_attempts`.
- Dla zdarzeń `partial` należy dodać kontekst degradacji (np. fallback użyty, część tickerów bez wyniku).

### 2) Poziomy logowania (severity)

- `DEBUG` — detale techniczne (parametry yfinance, diagnostyka parsowania, informacje pomocnicze dla dewelopera).
- `INFO` — start oraz pełny sukces operacji.
- `WARNING` — retry, fallback, degradacja jakości danych (`partial`) lub odzysk po błędzie.
- `ERROR` — finalna porażka operacji (`failed`) po wyczerpaniu dostępnych mechanizmów.

### 3) Mapa operacji `yfinance` → `operation` + oczekiwane poziomy

| Miejsce integracji | `operation` | Kiedy logować | Oczekiwany poziom |
|---|---|---|---|
| `_download_with_retry` (próba pobrania `yf.download`) | `yf_download_retry_attempt` | każda próba i pomiar czasu | `INFO` (start), `WARNING` (retry), `ERROR` (porażka końcowa), `INFO` (sukces) |
| `get_prices` (bulk `yf.download`) | `yf_get_prices_bulk` | start, sukces, błąd bulk, przejście do fallbacku | `INFO` (start/sukces), `WARNING` (fallback), `ERROR` (brak możliwości odzyskania) |
| `get_prices` (`Ticker.history` per ticker) | `yf_get_prices_ticker_history` | pobranie ceny dla pojedynczego tickera | `INFO` (sukces), `WARNING` (brak danych / przejście do fast_info), `ERROR` (finalna porażka tickera) |
| `get_prices` (`fast_info.last_price`) | `yf_get_prices_ticker_fast_info` | awaryjna próba ostatniej ceny | `DEBUG` (detale), `INFO` (sukces), `WARNING` (brak wartości), `ERROR` (wyjątek końcowy) |
| `sync_stock_history` (`yf.download`) | `yf_sync_stock_history` | synchronizacja historii cen | `INFO` (start/sukces/no-op), `WARNING` (puste dane/close), `ERROR` (porażka finalna) |
| `fetch_metadata` (`Ticker.info`) | `yf_fetch_metadata` | odczyt metadanych emitenta | `INFO` (cache hit/sukces), `WARNING` (użycie stale cache), `ERROR` (brak danych po fallbackach) |
| `get_quotes` (`yf.download`) | `yf_get_quotes_bulk` | notowania bieżące dla listy tickerów | `INFO` (start/sukces), `WARNING` (częściowe braki / retry), `ERROR` (porażka końcowa) |
| `fetch_market_events` (`Ticker.calendar`) | `yf_fetch_market_events_calendar` | odczyt kalendarza zdarzeń | `INFO` (sukces), `WARNING` (fallback do info), `ERROR` (porażka finalna) |
| `fetch_market_events` (`Ticker.info`) | `yf_fetch_market_events_info` | fallback/dodatkowe źródło eventów | `DEBUG` (detale mapowania), `INFO` (sukces), `WARNING` (częściowy wynik), `ERROR` (porażka finalna) |
| `get_stock_analysis` (`Ticker.info`) | `yf_stock_analysis_info` | dane fundamentalne do analizy | `INFO` (sukces), `WARNING` (wynik częściowy), `ERROR` (porażka finalna) |
| `get_stock_analysis` (`Ticker.history(period=\"1y\")`) | `yf_stock_analysis_history` | dane historyczne do wskaźników technicznych | `INFO` (sukces), `WARNING` (braki danych/partial), `ERROR` (porażka finalna) |

### 4) Przykładowy rekord logu (JSON)

```json
{
  "provider": "yfinance",
  "operation": "yf_get_prices_bulk",
  "tickers_count": 42,
  "attempt": 1,
  "max_attempts": 3,
  "duration_ms": 287,
  "status": "retry",
  "error_type": "network_timeout",
  "error_message": "ReadTimeout while calling yf.download",
  "trace_id": "0f5f29d0f3a34d53"
}
```

---

## Zadanie 3 — Refaktoryzacja kodu logowania

### Cel
Usunąć niespójne logowanie i wdrożyć wspólny mechanizm logowania zdarzeń integracji.

### Kroki implementacyjne
1. Zamień `print(...)` na `logger` w ścieżkach `yfinance`.
2. Dodaj helper, np. `_log_provider_event(...)`, który przyjmuje pola z kontraktu.
3. Zastąp ręcznie składane komunikaty wywołaniem helpera.
4. Upewnij się, że logowane są zarówno sukcesy, jak i porażki operacji.

### Artefakt wyjściowy
- Zmiany w `backend/price_service.py` (i pomocniczych modułach, jeśli potrzebne).

### Kryteria odbioru
- Brak `print(...)` w krytycznych ścieżkach `yfinance`.
- Wszystkie logi integracji używają spójnego formatu.

---

## Zadanie 4 — Retry i fallback z pełnym śladem diagnostycznym

### Cel
Sprawić, by retry i fallback były jednoznacznie widoczne i mierzalne.

### Kroki implementacyjne
1. W `_download_with_retry` loguj każdą próbę (`attempt/max_attempts`).
2. Mierz czas próby i zapisuj `duration_ms`.
3. Przy aktywacji fallbacku (bulk → per ticker) loguj `WARNING`.
4. Po zakończeniu fallbacku loguj podsumowanie (`success/failed/partial`).

### Artefakt wyjściowy
- Rozszerzone logi retry/fallback.

### Kryteria odbioru
- Dla incydentu można odtworzyć: ile było prób, które się nie powiodły i czy fallback pomógł.

---

## Zadanie 5 — Klasyfikacja błędów

### Cel
Rozróżniać kategorie błędów, aby szybciej diagnozować przyczynę.

### Kroki implementacyjne
1. Dodaj mapowanie wyjątków na `error_type`, np.:
   - `network_timeout`,
   - `rate_limit`,
   - `empty_data`,
   - `invalid_ticker`,
   - `parsing_error`,
   - `unknown`.
2. Użyj klasyfikacji w helperze logowania.
3. Dodaj bezpieczne skracanie komunikatów błędów (np. limit długości).

### Artefakt wyjściowy
- Funkcja/warstwa klasyfikacji błędów.

### Kryteria odbioru
- Każdy log błędu ma `error_type` z kontrolowanego zbioru wartości.

---

## Zadanie 6 — Ograniczenie szumu logów (noise control)

### Cel
Zapobiec zalewaniu logów przy dużej liczbie podobnych błędów.

### Kroki implementacyjne
1. Dodaj agregację lub sampling dla powtarzalnych błędów.
2. Wprowadź konfigurację poziomu szczegółowości (np. `VERBOSE_PROVIDER_LOGS`).
3. W produkcji domyślnie zostaw `INFO`, a detale pod feature flag.

### Artefakt wyjściowy
- Mechanizm ograniczania szumu + konfiguracja.

### Kryteria odbioru
- Przy masowym błędzie logi pozostają czytelne i diagnostyczne.

---

## Zadanie 7 — Testy automatyczne i manualne

### Cel
Potwierdzić, że logowanie działa zgodnie z kontraktem.

### Kroki implementacyjne
1. Dodaj testy jednostkowe helpera logowania:
   - kompletność pól,
   - poprawne poziomy,
   - brak awarii przy polach opcjonalnych.
2. Dodaj testy scenariuszy integracji (mock `yfinance`):
   - sukces,
   - retry + sukces,
   - retry + porażka,
   - fallback,
   - częściowy sukces.
3. Wykonaj test manualny i przeanalizuj logi.

### Artefakt wyjściowy
- Testy + krótki raport z wynikami.

### Kryteria odbioru
- Testy przechodzą, a logi zawierają wymagane pola.

---

## Zadanie 8 — Monitoring i alerty (etap 2)

### Cel
Przekuć logi w sygnały operacyjne.

### Kroki implementacyjne
1. Dodaj dashboard metryk (`error_rate`, `retry_rate`, `latency`).
2. Ustaw alerty na skoki błędów `provider=yfinance`.
3. Przygotuj mini-runbook „co sprawdzić najpierw”.

### Artefakt wyjściowy
- Dashboard + alerty + runbook.

### Kryteria odbioru
- Zespół dostaje szybki, praktyczny sygnał o awarii integracji.

---

## Zadanie 9 — Rollout krok po kroku

### Cel
Bezpiecznie wdrożyć zmiany na środowiska.

### Kroki implementacyjne
1. Wdrożenie na środowisko testowe/staging.
2. Obserwacja 3–7 dni: wolumen logów, jakość informacji, fałszywe alarmy.
3. Korekty poziomów/samplingu.
4. Wdrożenie produkcyjne po akceptacji.

### Artefakt wyjściowy
- Notatka wdrożeniowa z decyzją `GO/NO-GO`.

### Kryteria odbioru
- Brak regresji funkcjonalnych i akceptowalny wolumen logów.

---

## Definition of Done (całość projektu)
- [ ] Brak `print(...)` w krytycznych ścieżkach `yfinance`.
- [ ] Każdy błąd ma `provider`, `operation`, `status`, `error_type`, kontekst próby i czas.
- [ ] Retry/fallback są widoczne i możliwe do policzenia.
- [ ] Istnieją testy scenariuszy błędowych.
- [ ] Logi są czytelne i nie powodują nadmiernego szumu.

---

## Szablon raportu po każdym zadaniu (dla agenta AI)
Wypełnij po `Zadanie N`:

1. **Zakres wykonany:**
2. **Pliki zmienione:**
3. **Testy/komendy uruchomione:**
4. **Wynik i status (`DONE` / `BLOCKED`):**
5. **Ryzyka / uwagi do kolejnego zadania:**
