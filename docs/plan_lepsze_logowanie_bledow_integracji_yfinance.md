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
