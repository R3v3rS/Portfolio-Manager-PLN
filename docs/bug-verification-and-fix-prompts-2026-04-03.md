# Weryfikacja zgłoszonych problemów i plan poprawek (2026-04-03)

Zakres: **tylko weryfikacja** i przygotowanie materiału wdrożeniowego.
Nie zmieniano kodu aplikacji produkcyjnej.

## Podsumowanie statusu

| # | Obszar | Status weryfikacji | Wniosek |
|---|---|---|---|
| 1 | RSI i dzielenie przez zero | ✅ Potwierdzone | Komentarz nie odpowiada implementacji; `loss == 0` daje RSI=100 zamiast `NaN/None`. |
| 2 | `warmup_cache` i ticker `CASH` | ✅ Potwierdzone | `warmup_cache` pobiera także `CASH`. |
| 3 | `get_quotes` fallback po błędzie bulk | ✅ Potwierdzone | Gałąź fallback jest placeholderem (`pass`) i nie uzupełnia braków. |
| 4 | `get_quotes` zwraca `price: 0.0` przy braku danych | ✅ Potwierdzone | W kilku miejscach brak danych oznaczany jest jako `0.0` zamiast `None`. |
| 5 | `inserted_rows` zawiera także UPDATE | ✅ Potwierdzone | Log „Inserted ... new history rows” jest semantycznie nieprecyzyjny przy UPSERT. |
| 6 | Thread safety cache | ✅ Potwierdzone | Cache class-level modyfikowany bez dedykowanego locka. |
| 7 | `datetime.utcnow()` | ✅ Potwierdzone | Występuje użycie `utcnow`; zalecana wersja timezone-aware. |
| 8 | `datetime.fromtimestamp()` bez `tz` | ✅ Potwierdzone | Konwersja zależna od lokalnej strefy serwera. |
| 9 | `_latest_expected_market_day` i święta | ✅ Potwierdzone (niski priorytet) | Funkcja pomija tylko weekendy, nie kalendarz świąt giełdowych. |
|10| `change_1y` i długość historii | ✅ Potwierdzone | Liczenie 1Y używa pierwszej dostępnej ceny nawet przy krótszym oknie niż 1 rok. |

---

## Szczegóły weryfikacji i rekomendacja

### 1) RSI: obsługa dzielenia przez zero
- W kodzie jest:
  - `rs = gain / loss`
  - `hist['RSI'] = 100 - (100 / (1 + rs))`
  - komentarz: „Handle division by zero or NaN if loss is 0”.
- Przy `loss == 0`, `rs` staje się `inf`, co daje RSI=100. To nie realizuje semantyki „brak danych”, tylko „skrajnie wykupiony”.

**Rekomendacja:**
- Zastąpić dzielenie przez `loss.replace(0, float('nan'))`, a wynikowe `NaN` mapować na `None` dla API.

### 2) `warmup_cache` wysyła `CASH` do providerów
- `warmup_cache` pobiera tickery z `SELECT DISTINCT ticker FROM holdings` bez filtra `CASH`.
- W tym samym module istnieje już poprawny filtr w audycie jakości historii (`ticker != 'CASH'`).

**Rekomendacja:**
- Ujednolicić zapytanie w `warmup_cache` do wersji wykluczającej `NULL` i `CASH`.

### 3) `get_quotes`: pusty fallback po awarii bulk
- W `except` dla bulk download jest pętla po tickerach i `pass`.
- Efekt: część lub wszystkie tickery mogą nie trafić do wyniku wcale.

**Rekomendacja:**
- Wdrożyć realny fallback per ticker **albo** co najmniej gwarantować wpis z `price: None` i zmianami `None` dla każdego brakującego tickera.

### 4) `get_quotes`: `price: 0.0` jako sygnał braku danych
- W kilku miejscach na ścieżkach błędu/no-data zwracane jest `price: 0.0`.
- To miesza semantykę „realna cena 0” i „brak kwotowania”.

**Rekomendacja:**
- Dla „brak danych” zwracać `price: None`.
- Utrzymać spójność z innymi polami (`change_*`), które już są `None`.

### 5) `inserted_rows` i log UPSERT
- W sync historii stosowane jest `INSERT ... ON CONFLICT ... DO UPDATE`.
- `cursor.rowcount` inkrementuje się także dla UPDATE.
- Komunikat „Inserted X new history rows” jest mylący przy odświeżaniu istniejących rekordów.

**Rekomendacja:**
- Zmienić komunikat logu na „Upserted X history rows (new + refreshed)”.

### 6) Thread safety cache
- `_price_cache`, `_price_cache_updated_at`, `_metadata_cache`, `_metadata_cache_updated_at` są słownikami class-level.
- W module jest lock agregacji błędów, ale nie ma dedykowanego locka wokół odczytu/zapisu cache.

**Rekomendacja:**
- Dodać lock dla operacji cache (najlepiej jeden wspólny lub osobne dla price/meta).
- Objąć lockiem modyfikacje i krytyczne sekwencje read-modify-write.

### 7) `datetime.utcnow()`
- Występuje użycie `datetime.utcnow().strftime(...)`.

**Rekomendacja:**
- Przejść na timezone-aware UTC, np. `datetime.now(timezone.utc)`.

### 8) `datetime.fromtimestamp()` bez timezone
- Daty eventów rynkowych są liczone `datetime.fromtimestamp(ts)` bez `tz`.
- To zależy od strefy serwera i może powodować przesunięcia dat.

**Rekomendacja:**
- Użyć `datetime.fromtimestamp(ts, tz=timezone.utc)`.

### 9) `_latest_expected_market_day` ignoruje święta
- Funkcja cofa się tylko po weekendach.
- W dni wolne od sesji (np. święta) może błędnie uznać, że dane są „stare”.

**Rekomendacja (niski priorytet):**
- Rozważyć kalendarz giełdowy (np. `exchange_calendars`) albo prosty adapter per rynek.

### 10) `change_1y` liczy „od początku danych”, niekoniecznie 1 rok
- Warunek `if len(hist) > 0` jest zbyt słaby dla metryki 1Y.
- `hist['Close'].iloc[0]` to najstarszy punkt z dostępnego okna, które bywa krótsze niż rok.

**Rekomendacja:**
- Dodać minimalny próg długości historii (np. ~250 sesji) lub liczyć od daty `today - 365d` z najbliższym punktem.

---

## Gotowe prompty do wdrożenia poprawek (po kolei)

Poniższe prompty są przygotowane tak, aby można je wykonywać sekwencyjnie jako osobne taski.

### Prompt 1 — RSI division by zero
```text
Napraw backend/price_service.py w logice RSI (sekcja technicals), aby loss=0 nie dawał RSI=100 przez inf.
Wymagania:
1) Użyj dzielenia przez loss.replace(0, float('nan')).
2) Zachowaj aktualny interfejs wyjściowy technicals (rsi14/sma50/sma200).
3) Upewnij się, że wynik NaN jest mapowany do None dla technicals["rsi14"].
4) Dodaj/uzupełnij test jednostkowy pokrywający przypadek loss=0.
5) Nie zmieniaj innych zachowań biznesowych.
Po zmianach uruchom testy związane z PriceService i pokaż diff.
```

### Prompt 2 — warmup_cache bez CASH
```text
Popraw backend/price_service.py: warmup_cache ma ignorować CASH i puste tickery.
Wymagania:
1) Zmień SQL w warmup_cache na wersję filtrującą ticker IS NOT NULL oraz ticker != 'CASH'.
2) Zachowaj dotychczasowe logowanie.
3) Dodaj test (lub zaktualizuj istniejący), który potwierdza, że get_prices nie dostaje CASH z warmup_cache.
4) Nie wprowadzaj zmian poza tym zakresem.
Uruchom odpowiednie testy i pokaż wynik.
```

### Prompt 3 — get_quotes fallback po błędzie bulk
```text
Uzupełnij fallback w backend/price_service.py::get_quotes na wypadek wyjątku w bulk download.
Wymagania:
1) Każdy ticker z wejścia ma być obecny w słowniku wynikowym (nawet po totalnej awarii bulk).
2) W fallbacku zaimplementuj per-ticker próbę pobrania danych LUB minimum bezpieczny placeholder.
3) Jeśli brak danych, zwracaj price=None i wszystkie change_* jako None.
4) Dodaj test, który wymusza wyjątek w bulk i sprawdza kompletność odpowiedzi.
5) Nie zmieniaj publicznego formatu odpowiedzi.
Uruchom testy PriceService.
```

### Prompt 4 — price None zamiast 0.0 przy no-data
```text
Popraw backend/price_service.py::get_quotes, aby brak danych cenowych nie był reprezentowany jako 0.0.
Wymagania:
1) We wszystkich gałęziach no-data/error ustaw price=None (zamiast 0.0).
2) Zachowaj None dla change_1d/change_7d/change_1m/change_1y.
3) Dodaj/zmień testy, aby rozróżniały brak danych od prawidłowej liczby.
4) Sprawdź, czy serializacja/API kontrakt nadal działa poprawnie.
Uruchom testy i przedstaw ewentualne miejsca zależne od starej semantyki 0.0.
```

### Prompt 5 — precyzyjny log UPSERT
```text
Popraw komunikat logowania w backend/price_service.py::sync_stock_history.
Wymagania:
1) Ponieważ używany jest UPSERT (INSERT + UPDATE), komunikat nie może mówić "Inserted ... new history rows".
2) Zmień tekst na "Upserted {n} history rows (new + refreshed)" albo równoważny.
3) Nie zmieniaj logiki liczenia rowcount.
4) Dodaj test/asercję logu jeśli istnieje infrastruktura testów logowania.
Uruchom testy związane z sync_stock_history.
```

### Prompt 6 — thread safety cache
```text
Wprowadź thread-safety dla cache w backend/price_service.py.
Wymagania:
1) Dodaj dedykowany lock (lub locki) dla _price_cache/_price_cache_updated_at oraz _metadata_cache/_metadata_cache_updated_at.
2) Obejmij lockiem wszystkie zapisy i kluczowe sekwencje read-modify-write.
3) Zminimalizuj czas trzymania locka (bez ciężkich wywołań sieciowych pod lockiem).
4) Dodaj test(y) konkurencyjne lub przynajmniej deterministyczny test regresji dla spójności cache.
5) Nie zmieniaj zewnętrznego API klasy PriceService.
Uruchom testy PriceService.
```

### Prompt 7 — datetime.utcnow deprecacja
```text
Zastąp użycie datetime.utcnow() w backend/price_service.py wersją timezone-aware.
Wymagania:
1) Użyj datetime.now(timezone.utc).
2) Dodaj brakujący import timezone.
3) Zachowaj dotychczasowy format zapisu daty (jeśli wymagany przez DB/API).
4) Przejrzyj plik pod kątem podobnych użyć i popraw spójnie.
Uruchom testy modułu.
```

### Prompt 8 — fromtimestamp z timezone
```text
Popraw backend/price_service.py::fetch_market_events, aby fromtimestamp był jawnie w UTC.
Wymagania:
1) Użyj datetime.fromtimestamp(ts, tz=timezone.utc) dla earningsTimestamp i exDividendDate.
2) Zachowaj format końcowy YYYY-MM-DD.
3) Dodaj test regresyjny potwierdzający stabilność względem lokalnej strefy serwera.
Uruchom testy związane z fetch_market_events.
```

### Prompt 9 — market day i święta
```text
Rozszerz backend/price_service.py::_latest_expected_market_day o obsługę dni wolnych rynku.
Wymagania:
1) Zachowaj obecną logikę weekendową jako fallback.
2) Dodaj warstwę kalendarza sesyjnego (np. exchange_calendars) albo adapter konfigurowalny per rynek.
3) Jeśli zależność zewnętrzna jest zbyt ciężka, przygotuj prosty interfejs i implementację minimalną z możliwością podmiany.
4) Dodaj testy dla weekendu i przykładowego święta (np. 25 grudnia).
Opisz kompromisy i wpływ na częstotliwość sync.
```

### Prompt 10 — poprawna definicja change_1y
```text
Popraw backend/price_service.py::get_quotes w liczeniu change_1y.
Wymagania:
1) Nie licz change_1y, jeśli historia jest krótsza niż sensowny próg (np. ~250 sesji) — wtedy ustaw None.
2) Alternatywnie: licz względem punktu najbliższego dacie today-365d; jeśli brak takiego zakresu, zwróć None.
3) Dodaj testy dla:
   - pełnego roku danych,
   - krótkiej historii (np. 60 sesji),
   - granicznego przypadku.
4) Zachowaj kompatybilność reszty pól odpowiedzi.
Uruchom testy modułu PriceService.
```

---

## Sugerowana kolejność wdrożenia
1. #3 fallback bulk (ryzyko brakujących danych w odpowiedzi)
2. #4 `price=None` (semantyka braków danych)
3. #1 RSI dzielenie przez zero
4. #10 `change_1y`
5. #2 `warmup_cache` bez `CASH`
6. #7 i #8 (strefy czasowe)
7. #5 (precyzja logów)
8. #6 (thread safety)
9. #9 (kalendarz świąt — ulepszenie)

Taka kolejność najpierw zabezpiecza poprawność danych zwracanych przez API, potem porządkuje stabilność i utrzymanie.

---

# Weryfikacja kolejnych zgłoszeń (transactions/history) + gotowe prompty naprawcze

Zakres: **weryfikacja realnych bugów z routes_transactions.py i portfolio_history_service.py** oraz przygotowanie promptów do wdrożenia poprawek.

## Podsumowanie statusu

| # | Obszar | Status weryfikacji | Wniosek |
|---|---|---|---|
| 1 | `_legacy_cash_seed_for_child_scope` i `sub_portfolio_id = 0` | ✅ Potwierdzone | Fallback faktycznie szuka `sub_portfolio_id = 0` i w praktyce najczęściej zwraca `0.0`; dziś to dead/legacy bridge. |
| 2 | `assign_transaction` / `run_bulk_recalculation` i błędny argument `repair_portfolio_state` | ✅ Potwierdzone | Do funkcji przekazywany jest `sub_portfolio_id` jako `portfolio_id` (parent slot), co jest niezgodne z sygnaturą. |
| 3 | Brak walidacji `sub_portfolio_id` w GET query-string | ✅ Potwierdzone | GET używa gołego `int()`, więc `0` i liczby ujemne przechodzą; niespójne względem POST. |
| 4 | `print()` zamiast loggera | ✅ Potwierdzone | W `_build_price_context` wyjątek sync historii idzie do stdout przez `print`, bez strukturalnego logowania. |
| 6 | `validate_assign_payload` zwraca różne typy | ✅ Potwierdzone | Zależnie od flagi funkcja zwraca `int|None` albo `tuple`, co zwiększa ryzyko błędów integracyjnych. |
| 7 | Złożoność `O(days × transactions)` w daily/monthly history | ✅ Potwierdzone | Obie ścieżki liczą stan od zera dla każdego punktu czasu; koszt rośnie kwadratowo względem horyzontu. |

## Szczegóły i rekomendacje

### 1) `_legacy_cash_seed_for_child_scope` nadal szuka `sub_portfolio_id = 0`
- Funkcja `_legacy_cash_seed_for_child_scope` używa warunku:
  - `WHERE portfolio_id = ? AND (sub_portfolio_id IS NULL OR sub_portfolio_id = 0)`.
- Jest dalej wywoływana po `repair_portfolio_state(...)`, a jej wynik (jeśli niezerowy) jest dodawany do `current_cash`.
- W czystej bazie (bez legacy `0`) to faktycznie kończy jako `+0.0` i nie wnosi wartości.

**Rekomendacja:**
- Preferowane: usunąć fallback i całą ścieżkę legacy seed.
- Alternatywa: zostawić, ale wyraźnie oznaczyć jako tymczasowy most migracyjny (komentarz + TODO z datą/usunięciem).

### 2) Błędne wywołanie `repair_portfolio_state` po assign/bulk assign
- Sygnatura serwisu: `repair_portfolio_state(portfolio_id, subportfolio_id=None)`.
- W `assign_transaction` i `run_bulk_recalculation` występuje:
  - `PortfolioService.repair_portfolio_state(sub_portfolio_id)`
  - `PortfolioService.repair_portfolio_state(old_sub_portfolio_id)`
- To przekazuje child ID jako `portfolio_id` (parent scope), zamiast jako `subportfolio_id` przy właściwym parent ID.

**Rekomendacja:**
- Ujednolicić wszystkie wywołania do postaci:
  - `PortfolioService.repair_portfolio_state(portfolio_id, subportfolio_id=<child_id>)`.
- Dla parent scope pozostać przy `PortfolioService.repair_portfolio_state(portfolio_id, subportfolio_id=None)`.

### 3) GET `sub_portfolio_id` bez walidacji dodatniości
- W GET `/transactions/<portfolio_id>` i `/transactions/all` jest `int(sub_portfolio_id)` w `try/except`.
- `"0"` i wartości ujemne przechodzą parsowanie i trafiają dalej do service/SQL.
- POST endpointy (`buy/sell/dividend/assign`) korzystają z walidatorów `optional_positive_int` lub podobnych reguł dodatniości.

**Rekomendacja:**
- W GET wprowadzić spójną walidację: tylko dodatni int albo `none`/brak.
- Dla niepoprawnych wartości zwracać 422 z kodem walidacyjnym (zamiast milczącego `None`).

### 4) `print()` zamiast loggera w `portfolio_history_service.py`
- W `_build_price_context` jest `print(f"Failed to sync history for {ticker}: {e}")`.
- To omija system logowania i utrudnia monitoring, agregację i alerting.

**Rekomendacja:**
- Zamienić na logger (`current_app.logger` lub dedykowany logger modułu) z tickerem i stack/exception context.

### 6) `validate_assign_payload` ma niestabilny kontrakt zwracanych danych
- `require_transaction_ids=False` → zwraca `sub_portfolio_id`.
- `require_transaction_ids=True` → zwraca `(transaction_ids, sub_portfolio_id)`.
- To działa dziś, ale jest kruche przy refaktorach i zwiększa coupling między callerami i flagą.

**Rekomendacja:**
- Ujednolicić kontrakt: zawsze zwracać obiekt/dict o stałych kluczach, np.:
  - `{ "transaction_ids": [...]/None, "sub_portfolio_id": ... }`.

### 7) Wydajność: `O(days × transactions)` w daily i monthly
- `get_portfolio_profit_history_daily` dla każdego dnia iteruje wszystkie transakcje od początku.
- `_calculate_historical_metrics` analogicznie dla każdego month-end iteruje cały zbiór transakcji.
- To daje koszt rzędu `days * N` i `months * N` zamiast pojedynczego przejścia z rolling state.

**Rekomendacja:**
- Przebudować na algorytm inkrementalny:
  - posortowane transakcje,
  - wskaźnik index po transakcjach,
  - rolling `cash`, `invested_capital`, `holdings_qty` aktualizowane tylko dla nowych zdarzeń między punktami czasu.
- Zachować obecne zasady wyceny i live override dla bieżącego dnia.

## Gotowe prompty do fixów

### Prompt A — usunięcie/udokumentowanie legacy cash seed
```text
Zweryfikuj i napraw legacy fallback w backend/routes_transactions.py dotyczący _legacy_cash_seed_for_child_scope.
Zakres:
1) Przeanalizuj użycie _legacy_cash_seed_for_child_scope i warunku sub_portfolio_id = 0.
2) Jeśli fallback nie jest już potrzebny migracyjnie: usuń _legacy_cash_seed_for_child_scope oraz jego wywołanie z _repair_cash_transfer_scope.
3) Jeśli fallback ma zostać tymczasowo: dodaj wyraźny komentarz techniczny (legacy bridge), TODO z datą usunięcia i guard ograniczający wykonanie tylko gdy istnieją rekordy legacy.
4) Nie zmieniaj logiki repair_portfolio_state poza tym zakresem.
5) Dodaj test(y) regresyjne dla _repair_cash_transfer_scope (z i bez rekordów legacy).
Uruchom testy endpointów transakcyjnych i pokaż diff.
```

### Prompt B — poprawne argumenty `repair_portfolio_state` w assign i bulk
```text
Napraw backend/routes_transactions.py: wywołania PortfolioService.repair_portfolio_state w assign_transaction i assign_transactions_bulk.
Wymagania:
1) Zachowaj parent rebuild: PortfolioService.repair_portfolio_state(portfolio_id, subportfolio_id=None).
2) Dla child scopes przekazuj parent_id jako pierwszy argument i child jako named argument:
   - PortfolioService.repair_portfolio_state(portfolio_id, subportfolio_id=sub_portfolio_id)
   - PortfolioService.repair_portfolio_state(portfolio_id, subportfolio_id=old_sub_portfolio_id)
3) Nie przekazuj child ID jako portfolio_id.
4) Dodaj testy, które wykryją błędny porządek argumentów (mock/spies).
5) Nie zmieniaj API endpointów.
Uruchom testy routes_transactions.
```

### Prompt C — walidacja `sub_portfolio_id` w GET
```text
Ujednolić walidację query param `sub_portfolio_id` w backend/routes_transactions.py dla GET:
- /transactions/<int:portfolio_id>
- /transactions/all
Wymagania:
1) Dopuszczalne wartości: brak parametru, "none", dodatni integer (>0).
2) Wartości 0, ujemne, bool-like i nienumeryczne mają dawać 422 ASSIGN/VALIDATION-style error (spójny kod błędu dla endpointu).
3) Usuń obecne int(...)+fallback na None, który ukrywa błąd użytkownika.
4) Zachowaj kompatybilność dla poprawnych zapytań.
5) Dodaj testy dla: "none", "5", "0", "-3", "abc".
Uruchom testy endpointów transakcji.
```

### Prompt D — logger zamiast print w history sync
```text
Popraw backend/portfolio_history_service.py: zastąp print w _build_price_context.
Wymagania:
1) Zamień print(f"Failed to sync history...") na logger (current_app.logger lub modułowy logger).
2) Log ma zawierać ticker i treść wyjątku; preferowany logger.exception lub exc_info=True.
3) Nie przerywaj pętli sync po pojedynczym błędzie (zachowaj best-effort behavior).
4) Dodaj test, który asertywnie sprawdza że błąd jest logowany (nie printowany).
Uruchom testy portfolio_history_service.
```

### Prompt E — stabilny kontrakt `validate_assign_payload`
```text
Refaktoruj backend/routes_transactions.py::validate_assign_payload tak, aby zawsze zwracał jeden typ danych.
Wymagania:
1) Zwracaj zawsze dict:
   {
     "sub_portfolio_id": int|None,
     "transaction_ids": list[int]|None
   }
2) Dostosuj call sites:
   - assign_transaction
   - assign_transactions_bulk
3) Zachowaj dotychczasowe reguły walidacji biznesowej i kody błędów.
4) Dodaj testy regresyjne dla obu ścieżek (single/bulk).
5) Nie zmieniaj kontraktu HTTP endpointów.
Uruchom testy routes_transactions.
```

### Prompt F — optymalizacja daily/monthly history do rolling state
```text
Zoptymalizuj backend/portfolio_history_service.py:
- _calculate_historical_metrics
- get_portfolio_profit_history_daily
Cel: usunąć O(points × transactions) i przejść na rolling/incremental approach.
Wymagania:
1) Użyj jednego przejścia po posortowanych transakcjach z indeksem przesuwanym wraz z kolejnymi punktami czasu.
2) Aktualizuj rolling: cash, invested_capital, holdings_qty, (benchmark_shares/inflation_shares dla monthly).
3) Zachowaj istniejące zasady wyceny (FX, fees, live override dla today).
4) Zachowaj format odpowiedzi i zaokrąglenia.
5) Dodaj testy porównawcze: nowa implementacja daje te same wyniki co stara dla przykładowego datasetu.
6) Dodaj prosty benchmark/test wydajnościowy pokazujący spadek liczby operacji lub czasu dla większego inputu.
Uruchom testy portfolio_history_service i pokaż metrykę before/after.
```

## Sugerowana kolejność wdrożenia
1. Prompt B (błędne argumenty repair — bug funkcjonalny)
2. Prompt C (spójna walidacja GET)
3. Prompt D (observability/logging)
4. Prompt A (legacy bridge cleanup)
5. Prompt E (stabilny kontrakt helpera)
6. Prompt F (wydajność)

Taka kolejność najpierw eliminuje błędy wpływające bezpośrednio na poprawność stanu portfela, następnie porządkuje walidację i diagnostykę, a na końcu optymalizuje wydajność.

---

# Uzupełnienie: kolejne realne bugi w PortfolioValuationService (2026-04-03)

Zakres: weryfikacja dodatkowych zgłoszeń i przygotowanie gotowych promptów do naprawy.

## Podsumowanie statusu

| # | Obszar | Status | Wniosek |
|---|---|---|---|
| 1 | `DIVIDEND` pominięty w `tx_delta` | ✅ Potwierdzone | Dywidendy nie zwiększają salda w `_compute_cash_negative_days`, co może generować false-positive incydenty. |
| 2 | `legacy_row` w `get_cash_balance_on_date` | ✅ Potwierdzone | W legacy query używany jest `sub_portfolio_id` jako `portfolio_id`, więc przy regule parent-ID wynik jest praktycznie zawsze 0. |
| 3 | `get_holdings` i aktualizacja metadanych tylko po `MAX(id)` | ✅ Potwierdzone | W agregacji aktualizowany jest pojedynczy rekord holdings, co zostawia inne rekordy tickera z NULL metadata. |
| 4 | Legacy warunki `sub_portfolio_id = 0` | ✅ Potwierdzone | Występują nadal w 4 miejscach; przy czystej bazie są zbędne i utrudniają czytelność zapytań. |
| 5 | `_compute_cash_negative_days` iteracja dzień-po-dniu | ✅ Potwierdzone | Pętla `while current_day <= last_day` skaluje się słabo dla długiej historii i blokuje request synchroniczny. |
| 6 | N+1 zapytania w wycenie i audycie | ✅ Potwierdzone | `get_portfolio_value` i audit wykonują kaskadowe per-portfolio zapytania (`get_portfolio`, `_calculate_single_portfolio_value`). |
| 7 | `datetime.utcnow()` w audycie | ✅ Potwierdzone | Występuje w `get_parent_child_consistency_audit`; zalecane timezone-aware UTC. |
| 8 | `print()` zamiast loggera (XIRR) | ✅ Potwierdzone | Błędy XIRR w dwóch miejscach trafiają do stdout, nie do systemu logowania. |
| 9 | Komentarz/TODO jako pseudo-docstring | ✅ Potwierdzone | `_calculate_single_portfolio_value` zaczyna się komentarzem refaktoryzacyjnym zamiast właściwego docstringa. |

## Szczegóły i rekomendacje

### 1) `DIVIDEND` nie jest traktowany jako cash credit w `tx_delta`
W `_compute_cash_negative_days` funkcja `tx_delta` kredytuje `DEPOSIT/INTEREST/SELL`, ale pomija `DIVIDEND`, który wpada do `return 0.0`.

**Wpływ:**
- Zaniżanie running cash balance w audycie cash-negative-days.
- Fałszywe alerty dla portfeli finansujących zakupy dywidendami.

**Rekomendacja:**
- Dodać `DIVIDEND` do credit bucketu (`('DEPOSIT', 'INTEREST', 'SELL', 'DIVIDEND')`).

### 2) `legacy_row` w `get_cash_balance_on_date` używa niepoprawnego klucza portfolio
Gałąź child scope liczy poprawnie `row` po `(portfolio_id, sub_portfolio_id)`, ale `legacy_row` wykonuje zapytanie z `(sub_portfolio_id, as_of_date)` podstawiając child ID do `portfolio_id`.

**Wpływ:**
- Przy modelu „transactions.portfolio_id = parent_id” legacy query prawie zawsze daje 0.
- Dodatkowe, kosztowne SQL bez realnego efektu.

**Rekomendacja:**
- Usunąć legacy query albo, jeśli tymczasowo konieczne, poprawić parametr na parent ID i ograniczyć execution guardem tylko gdy istnieją rekordy legacy.

### 3) `get_holdings` aktualizuje metadata tylko dla jednego rekordu w agregacji
Tryb agregowany opiera się na `MAX(id) as id`, po czym `UPDATE holdings ... WHERE id = ?` aktualizuje tylko ten jeden rekord.

**Wpływ:**
- Powtarzające się `fetch_metadata` dla tego samego tickera.
- Niespójne dane `company_name/sector/industry` między rekordami tego samego tickera.

**Rekomendacja:**
- Aktualizować metadane po kluczu biznesowym (`portfolio_id + ticker [+ currency]`) lub batchowo dla wszystkich rekordów grupy, nie po pojedynczym `id` agregatu.

### 4) Pozostałe legacy warunki `sub_portfolio_id = 0`
Warunki `IS NULL OR = 0` pozostają w `_compute_cash_negative_days` i `get_cash_balance_on_date`.

**Rekomendacja:**
- Po jednorazowej walidacji danych (`COUNT(*) WHERE sub_portfolio_id = 0`) uprościć zapytania do `IS NULL`.
- Jeśli decyzja o zachowaniu kompatybilności: dodać komentarz i plan usunięcia.

### 5) Wydajność: iteracja dzień-po-dniu w `_compute_cash_negative_days`
Algorytm przechodzi od pierwszej transakcji do dziś dzień po dniu.

**Wpływ:**
- Dla portfeli wieloletnich tysiące iteracji na pojedynczy audit.
- Dodatkowe obciążenie synchronicznego endpointu.

**Rekomendacja:**
- Przejść na event/range-based approach (iteracja po datach zdarzeń i odcinkach stanu), zamiast pełnego kalendarza.
- Przy inkrementacji dat używać idiomatycznie `current_day += timedelta(days=1)` jeśli pętla dzienna zostaje.

### 6) N+1 zapytania: `get_portfolio_value` i `get_parent_child_consistency_audit`
- `get_portfolio_value` dla każdego dziecka robi `get_portfolio(child_id)` i osobne liczenie.
- Audit dla każdego parenta odpala `get_portfolio_value(parent_id)` i kolejne wyliczenia child/own.

**Rekomendacja:**
- Prefetch parents/children jednym zapytaniem.
- Rozdzielić warstwę pobrania danych i warstwę kalkulacji, aby unikać wielokrotnych round-tripów DB.
- Rozważyć „bulk valuation context” dla audytu.

### 7) `datetime.utcnow()`
W audycie nadal użyte `datetime.utcnow().replace(microsecond=0).isoformat()`.

**Rekomendacja:**
- Użyć `datetime.now(timezone.utc).replace(microsecond=0).isoformat()`.

### 8) `print()` zamiast loggera dla błędów XIRR
Błędy XIRR są printowane (`Aggregated...`, `Single...`).

**Rekomendacja:**
- Zamienić na logger z `exc_info=True`/`logger.exception`, dodać kontekst `portfolio_id`.

### 9) Komentarz refaktoryzacyjny jako „docstring replacement”
`_calculate_single_portfolio_value` zaczyna się komentarzem „Move the existing logic...”.

**Rekomendacja:**
- Zastąpić komentarz docstringiem opisującym wejście/wyjście i zakres odpowiedzialności funkcji.

## Gotowe prompty do fixów

### Prompt G — `DIVIDEND` w `tx_delta`
```text
Napraw backend/portfolio_valuation_service.py::_compute_cash_negative_days tak, aby dywidendy były liczone jako wpływ gotówki.
Wymagania:
1) W tx_delta dodaj 'DIVIDEND' do bucketu credit.
2) Nie zmieniaj innych reguł znaków dla BUY/SELL/DEPOSIT/WITHDRAW/INTEREST.
3) Dodaj test regresyjny: scenariusz, gdzie dywidenda zapobiega wejściu poniżej zera.
4) Uruchom testy audytu parent-child consistency.
```

### Prompt H — usunięcie/poprawa `legacy_row` w `get_cash_balance_on_date`
```text
Popraw backend/portfolio_valuation_service.py::get_cash_balance_on_date (gałąź sub_portfolio_id != None).
Wymagania:
1) Zweryfikuj czy legacy_row jest nadal potrzebny przy modelu transactions.portfolio_id=parent.
2) Jeśli niepotrzebny: usuń legacy query i zwracaj tylko cash_balance dla (portfolio_id, sub_portfolio_id).
3) Jeśli potrzebny tymczasowo: popraw parametr query (parent_id zamiast sub_portfolio_id jako portfolio_id) i dodaj guard wykonywany tylko gdy istnieją rekordy legacy (=0/null mapping).
4) Dodaj testy dla child scope oraz case bez danych legacy.
```

### Prompt I — poprawa update metadata w `get_holdings` (agregacja)
```text
Napraw backend/portfolio_valuation_service.py::get_holdings dla aggregate=True, aby aktualizacja metadata nie dotyczyła tylko MAX(id).
Wymagania:
1) Nie opieraj UPDATE o pojedyncze id z agregatu.
2) Aktualizuj wszystkie rekordy holdings należące do danej grupy (portfolio_id + ticker + currency), albo zastosuj dedykowany mechanizm upsert metadata.
3) Ogranicz liczbę wywołań fetch_metadata (cache per ticker w ramach requestu).
4) Dodaj test potwierdzający, że przy wielu rekordach tego samego tickera metadata trafia do wszystkich rekordów grupy.
```

### Prompt J — cleanup `sub_portfolio_id = 0` warunków
```text
Przeprowadź cleanup legacy SQL w backend/portfolio_valuation_service.py dla warunków `(sub_portfolio_id IS NULL OR sub_portfolio_id = 0)`.
Wymagania:
1) Najpierw dodaj check/migracyjny guard potwierdzający brak rekordów z sub_portfolio_id = 0.
2) Jeśli brak rekordów: uprość zapytania do `sub_portfolio_id IS NULL`.
3) Jeśli rekordy istnieją: zostaw kompatybilność, ale dodaj komentarz z planem usunięcia i telemetryczny licznik użyć.
4) Dodaj testy dla parent/child scope.
```

### Prompt K — optymalizacja `_compute_cash_negative_days`
```text
Zoptymalizuj backend/portfolio_valuation_service.py::_compute_cash_negative_days.
Wymagania:
1) Usuń pełną iterację dzień-po-dniu i przejdź na event/range-based computation.
2) Incidenty mają dalej raportować datę, saldo i triggering transaction metadata.
3) Zachowaj semantykę carrying_trigger dla ciągłych okresów ujemnego salda.
4) Dodaj benchmark/regresję porównującą stare i nowe wyniki na tym samym zbiorze danych.
5) Jeśli zostaje pętla dzienna, użyj `current_day += timedelta(days=1)` zamiast fromordinal/toordinal.
```

### Prompt L — redukcja N+1 w wycenie i audycie
```text
Zredukuj N+1 zapytania w backend/portfolio_valuation_service.py dla:
- get_portfolio_value
- get_parent_child_consistency_audit
Wymagania:
1) Prefetchuj parent+children jednym/małą liczbą zapytań.
2) Uniknij wielokrotnego get_portfolio(child_id) w pętlach.
3) Przy audycie nie wywołuj get_portfolio_value(parent_id) jeśli te same dane i tak są liczone lokalnie — użyj wspólnego kontekstu wyceny.
4) Dodaj test/licznik zapytań (lub mock DB execute count) pokazujący spadek liczby query.
```

### Prompt M — deprecacja UTC + logger + docstring hygiene
```text
W backend/portfolio_valuation_service.py wykonaj porządki techniczne:
1) Zamień datetime.utcnow() na datetime.now(timezone.utc) (+ import timezone).
2) Zamień print(...) dla błędów XIRR na logger.exception/logger.error z kontekstem portfolio_id.
3) Zastąp komentarz "Move the existing logic..." przy _calculate_single_portfolio_value właściwym docstringiem opisującym działanie helpera.
4) Dodaj test(y) lub asercje logowania tam, gdzie infrastruktura to umożliwia.
```

## Sugerowana kolejność wdrożenia (to uzupełnienie)
1. Prompt G (poprawność audytu cash-negative)
2. Prompt H (martwa/niepoprawna gałąź legacy_row)
3. Prompt L (redukcja N+1)
4. Prompt K (optymalizacja cash-negative-days)
5. Prompt I (metadata spójność)
6. Prompt J (cleanup legacy `=0`)
7. Prompt M (deprecacje i higiena logowania/dokumentacji)

Ta kolejność najpierw eliminuje ryzyko fałszywych alarmów i błędnej semantyki gotówki, potem adresuje koszt zapytań i wydajność, a na końcu porządkuje techniczne długi utrzymaniowe.

---

# Uzupełnienie 2: nowe znaleziska (core/trade/audit/import) — 2026-04-03

Zakres: weryfikacja kolejnych zgłoszeń i przygotowanie promptów do fixów w tym samym stylu.

## Podsumowanie statusu

| Priorytet | Obszar | Status | Wniosek |
|---|---|---|---|
| 🔴 | `get_tax_limits`: IKE query łapie IKZE | ✅ Potwierdzone | `LIKE '%IKE%'` obejmuje również nazwy zawierające `IKZE` (np. „My IKZE ...”), więc IKE bywa zawyżone. |
| 🟡 | `assign_transactions_bulk`: commit per transakcja | ✅ Potwierdzone | Bulk deleguje do metody, która sama commit-uje; przy błędzie w połowie możliwy partial success. |
| 🟡 | `rebuild_holdings_from_transactions`: `ValueError` dla nowego typu | ✅ Potwierdzone | Nieznany `tx_type` przerywa cały rebuild/audit zamiast degradować łagodnie. |
| 🟡 | `unconfirmed_conflicts` w imporcie | ✅ Potwierdzone | Filtr sprawdza tylko `confirmed_hashes is None`, więc logika potwierdzeń jest błędna binarnie (wszystko/zero). |
| 🟡 | `repair_portfolio_state(sub_portfolio_id)` w routes | ✅ Doprecyzowane | Kod działa „przypadkiem” przez auto-resolve scope, ale jest nieczytelny i łatwy do zepsucia w refaktorze. |
| 🟢 | `create_portfolio` dead-branch w `interest_date` | ✅ Potwierdzone | Po normalizacji `created_at` gałąź `else` jest martwa. |
| 🟢 | `archive_portfolio`: `datetime.utcnow()` | ✅ Potwierdzone | Kolejne użycie API wymagającego migracji do timezone-aware UTC. |
| 🟢 | `list_portfolios`: `print()` zamiast loggera | ✅ Potwierdzone | Błędy DB trafiają do stdout, bez struktury i poziomu logowania. |
| 🟢 | `get_tax_limits`: hardcoded fallback 2026 | ✅ Potwierdzone | Każdy rok >2026 używa limitów 2026, co z czasem da błędne dane biznesowe. |
| 🟢 | `resolve_symbol_mapping`: ładuje całą tabelę | ✅ Potwierdzone | Dla fuzzy-match pobierane są wszystkie rekordy `symbol_mappings` do pamięci. |
| 🟢 | `import_xtb_csv`: check `tx_total < 0` po `abs()` | ✅ Potwierdzone | Warunek jest martwy logicznie i nie wnosi walidacji. |
| 🟢 | Dev-komentarz w kodzie produkcyjnym | ✅ Potwierdzone | Komentarz „For simplicity, I'll search and replace...” powinien zostać usunięty/zastąpiony. |

## Szczegóły i rekomendacje

### 🔴 1) `get_tax_limits`: IKE query obejmuje IKZE
- Obecnie: `SELECT id FROM portfolios WHERE upper(name) LIKE '%IKE%'`.
- To dopasowuje także napisy zawierające `IKZE` (ciąg `IKE`), co prowadzi do mieszania limitów IKE i IKZE.

**Rekomendacja:**
- Minimalny fix SQL: `LIKE '%IKE%' AND NOT LIKE '%IKZE%'`.
- Docelowo lepiej oprzeć klasyfikację o jawne pole typu konta, nie nazwę portfela.

### 🟡 2) `assign_transactions_bulk`: brak atomowości całej operacji
- Bulk pętli po `transaction_ids` wywołuje `assign_transaction_to_subportfolio`, a ta metoda commit-uje wewnętrznie.
- W razie błędu środkowego wpisy wcześniejsze już są utrwalone.

**Rekomendacja:**
- Dodać tryb „bez autocommitu” dla assign single i opakować bulk w jedną transakcję (`BEGIN ... COMMIT/ROLLBACK`).

### 🟡 3) `rebuild_holdings_from_transactions`: `raise ValueError` na nieznanym typie
- Gałąź `else: raise ValueError(...)` powoduje twarde przerwanie rebuild.

**Rekomendacja:**
- Zmienić na `logger.warning(...); continue` (+ licznik pominiętych typów w wyniku), żeby audit był odporny na rozszerzenia słownika typów.

### 🟡 4) `unconfirmed_conflicts`: błędny filtr
- Obecnie: `unconfirmed_conflicts = [c for c in potential_conflicts if confirmed_hashes is None]`.
- Logika nie sprawdza `row_hash` konfliktu względem listy potwierdzeń.

**Rekomendacja:**
- Użyć filtra per hash, np. `c['row_hash'] not in set(confirmed_hashes or [])` (z obsługą duplikatów najlepiej przez Counter).

### 🟡 5) `repair_portfolio_state(sub_portfolio_id)` — działa, ale przypadkowo
- Wywołanie z child ID w miejscu parent argumentu działa dzięki wewnętrznej logice resolve w `repair_portfolio_state`.

**Rekomendacja:**
- Mimo że runtime bywa poprawny, ujednolicić semantycznie poprawny call-site:
  `repair_portfolio_state(parent_id, subportfolio_id=child_id)`.

### 🟢 6) Pozostałe niskie (cleanup)
- `create_portfolio`: martwa gałąź w ustalaniu `interest_date`.
- `archive_portfolio`: `datetime.utcnow()`.
- `list_portfolios`: `print()` zamiast logger.
- `get_tax_limits`: hardcoded 2026 fallback.
- `resolve_symbol_mapping`: full-table scan do pamięci przed fuzzy match.
- `import_xtb_csv`: martwy warunek po `abs()`.
- komentarz deweloperski w kodzie produkcyjnym.

**Rekomendacja:**
- Zgrupować do jednego technicznego patcha „higiena + deprecacje + observability + micro-perf”.

## Gotowe prompty do fixów

### Prompt N — poprawka IKE/IKZE w `get_tax_limits` (HOTFIX)
```text
Napraw backend/portfolio_core_service.py::get_tax_limits, aby IKE nie obejmowało IKZE.
Wymagania:
1) Zmień query IKE na:
   WHERE upper(name) LIKE '%IKE%' AND upper(name) NOT LIKE '%IKZE%'
2) Zachowaj istniejące wyliczenia i format odpowiedzi.
3) Dodaj test regresyjny: portfel o nazwie zawierającej IKZE nie może zwiększać IKE.
4) Uruchom testy endpointu /tax-limits.
```

### Prompt O — atomowość `assign_transactions_bulk`
```text
Zapewnij atomowość bulk assign w backend/portfolio_trade_service.py.
Wymagania:
1) assign_transactions_bulk ma działać w jednej transakcji DB (all-or-nothing).
2) assign_transaction_to_subportfolio nie może wymuszać commit przy użyciu z bulk (dodaj flagę autocommit=False albo wydziel wersję internal).
3) Przy błędzie rollback ma cofnąć wszystkie przypisania z tej paczki.
4) Dodaj test: błąd na N-tej transakcji nie zostawia częściowo przypisanych rekordów.
```

### Prompt P — odporność rebuild na nowe typy transakcji
```text
Popraw backend/portfolio_audit_service.py::rebuild_holdings_from_transactions.
Wymagania:
1) Zastąp `raise ValueError("Unsupported transaction type...")` logowaniem warning i `continue`.
2) Dodaj licznik/składnik wyniku informujący o pominiętych nieobsługiwanych typach.
3) Zachowaj deterministykę dla wspieranych typów.
4) Dodaj test z nieznanym typem (np. TRANSFER), który nie przerywa rebuild.
```

### Prompt Q — poprawny filtr `unconfirmed_conflicts`
```text
Napraw backend/portfolio_import_service.py logikę `unconfirmed_conflicts`.
Wymagania:
1) Filtruj po hashu konfliktu, nie po samym None-check.
2) Użyj semantyki: konflikt jest niepotwierdzony, jeśli jego row_hash nie ma dostępnego potwierdzenia.
3) Uwzględnij wielokrotne wystąpienia tego samego hash (Counter).
4) Dodaj testy:
   - confirmed_hashes=None => warning dla wszystkich konfliktów,
   - confirmed_hashes częściowe => warning tylko dla niepotwierdzonych,
   - confirmed_hashes pełne => brak warning.
```

### Prompt R — czytelność call-site `repair_portfolio_state`
```text
Uczyść call-site w backend/routes_transactions.py dla wywołań repair_portfolio_state po assign.
Wymagania:
1) Zastąp wywołania `repair_portfolio_state(sub_portfolio_id)` i analogiczne wersją jawnie semantyczną:
   repair_portfolio_state(portfolio_id, subportfolio_id=sub_portfolio_id)
2) Zachowaj aktualne zachowanie runtime.
3) Dodaj test/mocked assertion na argumenty wywołania.
```

### Prompt S — pakiet low-priority cleanup
```text
Wykonaj pakiet cleanup w backend/portfolio_core_service.py + backend/portfolio_import_service.py:
1) Zamień datetime.utcnow() na datetime.now(timezone.utc).
2) Zamień print(...) na logger.exception/logger.error.
3) Usuń martwe gałęzie i dead checks (interest_date else, tx_total<0 po abs).
4) Usuń/zmień deweloperskie komentarze na merytoryczne docstringi/komentarze produkcyjne.
5) Dla get_tax_limits przygotuj strategię na lata > 2026 (konfiguracja/tabela limitów zamiast hardcoded fallback).
6) Dla resolve_symbol_mapping ogranicz full-table scan (prefilter SQL lub indeksowane podejście).
Dodaj testy regresyjne i krótki changelog techniczny.
```

## Sugerowana kolejność wdrożenia (to uzupełnienie)
1. Prompt N (błąd biznesowy IKE/IKZE)
2. Prompt O (atomowość bulk assign)
3. Prompt Q (logika potwierdzeń importu)
4. Prompt R (czytelność + maintainability napraw route)
5. Prompt P (odporność rebuild)
6. Prompt S (cleanup niskiego priorytetu)

Ta kolejność najpierw zamyka błędy wpływające na poprawność biznesową i integralność danych, potem porządkuje niezawodność importu, a na końcu wykonuje higienę techniczną i optymalizacje.
