# Weryfikacja zgłoszonych problemów i plan poprawek (2026-04-03)

Cel dokumentu: **jedna spójna lista otwartych tematów** do wdrożenia oraz skrócona ewidencja tematów już zamkniętych.

---

## 1) Tematy zamknięte (tylko tytuły)

Poniżej zostawiam wyłącznie tytuły błędów oznaczonych jako ukończone/zamknięte — bez promptów i bez szczegółowych instrukcji wdrożeniowych.

### PriceService / dane rynkowe
- RSI: obsługa dzielenia przez zero.
- `warmup_cache` i ticker `CASH`.
- `inserted_rows` zawiera także UPDATE (precyzja logu UPSERT).

### Transactions / History
- `assign_transaction` / `run_bulk_recalculation` i błędny argument `repair_portfolio_state`.
- `print()` zamiast loggera w `_build_price_context`.

---

## 2) Otwarta kolejka poprawek (aktywny backlog)

### A. PriceService

| ID | Obszar | Priorytet | Status |
|---|---|---|---|
| PS-03 | `get_quotes` fallback po błędzie bulk | Wysoki | Otwarte |
| PS-04 | `get_quotes` zwraca `price: 0.0` przy braku danych | Wysoki | Otwarte |
| PS-06 | Thread safety cache | Średni | Otwarte |
| PS-07 | `datetime.utcnow()` | Średni | Otwarte |
| PS-08 | `datetime.fromtimestamp()` bez `tz` | Średni | Otwarte |
| PS-09 | `_latest_expected_market_day` i święta | Niski | Otwarte |
| PS-10 | `change_1y` i długość historii | Średni | Otwarte |

### B. Transactions / History

| ID | Obszar | Priorytet | Status |
|---|---|---|---|
| TR-01 | `_legacy_cash_seed_for_child_scope` i `sub_portfolio_id = 0` | Średni | Otwarte |
| TR-03 | Brak walidacji `sub_portfolio_id` w GET query-string | Wysoki | Otwarte |
| TR-06 | `validate_assign_payload` zwraca różne typy | Średni | Otwarte |
| TR-07 | Złożoność `O(days × transactions)` w daily/monthly history | Średni | Otwarte |

### C. PortfolioValuationService

| ID | Obszar | Priorytet | Status |
|---|---|---|---|
| PV-01 | `DIVIDEND` pominięty w `tx_delta` | Wysoki | Zrobione |
| PV-02 | `legacy_row` w `get_cash_balance_on_date` | Wysoki | Otwarte |
| PV-03 | `get_holdings` i aktualizacja metadanych tylko po `MAX(id)` | Średni | Otwarte |
| PV-04 | Legacy warunki `sub_portfolio_id = 0` | Niski | Otwarte |
| PV-05 | `_compute_cash_negative_days` iteracja dzień-po-dniu | Średni | Otwarte |
| PV-06 | N+1 zapytania w wycenie i audycie | Średni | Otwarte |
| PV-07 | `datetime.utcnow()` w audycie | Niski | Otwarte |
| PV-08 | `print()` zamiast loggera (XIRR) | Niski | Otwarte |
| PV-09 | Komentarz/TODO jako pseudo-docstring | Niski | Otwarte |

### D. Core / Trade / Audit / Import

| ID | Obszar | Priorytet | Status |
|---|---|---|---|
| CT-01 | `get_tax_limits`: IKE query łapie IKZE | Krytyczny | Zrobione |
| CT-02 | `assign_transactions_bulk`: commit per transakcja | Wysoki | Zrobione |
| CT-03 | `rebuild_holdings_from_transactions`: `ValueError` dla nowego typu | Średni | Otwarte |
| CT-04 | `unconfirmed_conflicts` w imporcie | Wysoki | Otwarte |
| CT-05 | `repair_portfolio_state(sub_portfolio_id)` w routes (nieczytelny call-site) | Średni | Otwarte |
| CT-06 | `create_portfolio` dead-branch w `interest_date` | Niski | Otwarte |
| CT-07 | `archive_portfolio`: `datetime.utcnow()` | Niski | Otwarte |
| CT-08 | `list_portfolios`: `print()` zamiast loggera | Niski | Otwarte |
| CT-09 | `get_tax_limits`: hardcoded fallback 2026 | Niski | Otwarte |
| CT-10 | `resolve_symbol_mapping`: ładuje całą tabelę | Niski | Otwarte |
| CT-11 | `import_xtb_csv`: check `tx_total < 0` po `abs()` | Niski | Otwarte |
| CT-12 | Dev-komentarz w kodzie produkcyjnym | Niski | Otwarte |

---

## 3) Gotowe prompty (tylko dla tematów otwartych)

### PS-03 — `get_quotes` fallback po błędzie bulk
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

### PS-04 — `price=None` zamiast `0.0` przy no-data
```text
Popraw backend/price_service.py::get_quotes, aby brak danych cenowych nie był reprezentowany jako 0.0.
Wymagania:
1) We wszystkich gałęziach no-data/error ustaw price=None (zamiast 0.0).
2) Zachowaj None dla change_1d/change_7d/change_1m/change_1y.
3) Dodaj/zmień testy, aby rozróżniały brak danych od prawidłowej liczby.
4) Sprawdź, czy serializacja/API kontrakt nadal działa poprawnie.
Uruchom testy i przedstaw ewentualne miejsca zależne od starej semantyki 0.0.
```

### PS-06 — thread safety cache
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

### PS-07 — `datetime.utcnow()`
```text
Zastąp użycie datetime.utcnow() w backend/price_service.py wersją timezone-aware.
Wymagania:
1) Użyj datetime.now(timezone.utc).
2) Dodaj brakujący import timezone.
3) Zachowaj dotychczasowy format zapisu daty (jeśli wymagany przez DB/API).
4) Przejrzyj plik pod kątem podobnych użyć i popraw spójnie.
Uruchom testy modułu.
```

### PS-08 — `fromtimestamp` z timezone
```text
Popraw backend/price_service.py::fetch_market_events, aby fromtimestamp był jawnie w UTC.
Wymagania:
1) Użyj datetime.fromtimestamp(ts, tz=timezone.utc) dla earningsTimestamp i exDividendDate.
2) Zachowaj format końcowy YYYY-MM-DD.
3) Dodaj test regresyjny potwierdzający stabilność względem lokalnej strefy serwera.
Uruchom testy związane z fetch_market_events.
```

### PS-09 — market day i święta
```text
Rozszerz backend/price_service.py::_latest_expected_market_day o obsługę dni wolnych rynku.
Wymagania:
1) Zachowaj obecną logikę weekendową jako fallback.
2) Dodaj warstwę kalendarza sesyjnego (np. exchange_calendars) albo adapter konfigurowalny per rynek.
3) Jeśli zależność zewnętrzna jest zbyt ciężka, przygotuj prosty interfejs i implementację minimalną z możliwością podmiany.
4) Dodaj testy dla weekendu i przykładowego święta (np. 25 grudnia).
Opisz kompromisy i wpływ na częstotliwość sync.
```

### PS-10 — poprawna definicja `change_1y`
```text
Popraw backend/price_service.py::get_quotes w liczeniu change_1y.
Wymagania:
1) Nie licz change_1y, jeśli historia jest krótsza niż sensowny próg (np. ~250 sesji) — wtedy ustaw None.
2) Alternatywnie: licz względem punktu najbliższego dacie today-365d; jeśli brak takiego zakresu, zwróć None.
3) Dodaj testy dla pełnego roku danych, krótkiej historii i przypadku granicznego.
4) Zachowaj kompatybilność reszty pól odpowiedzi.
Uruchom testy modułu PriceService.
```

### TR-01 — usunięcie/udokumentowanie legacy cash seed
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

### TR-03 — walidacja `sub_portfolio_id` w GET
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

### TR-06 — stabilny kontrakt `validate_assign_payload`
```text
Refaktoruj backend/routes_transactions.py::validate_assign_payload tak, aby zawsze zwracał jeden typ danych.
Wymagania:
1) Zwracaj zawsze dict:
   {
     "sub_portfolio_id": int|None,
     "transaction_ids": list[int]|None
   }
2) Dostosuj call sites: assign_transaction i assign_transactions_bulk.
3) Zachowaj dotychczasowe reguły walidacji biznesowej i kody błędów.
4) Dodaj testy regresyjne dla obu ścieżek (single/bulk).
5) Nie zmieniaj kontraktu HTTP endpointów.
Uruchom testy routes_transactions.
```

### TR-07 — optymalizacja daily/monthly history do rolling state
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

### PV-01 — `DIVIDEND` w `tx_delta`
```text
Napraw backend/portfolio_valuation_service.py::_compute_cash_negative_days tak, aby dywidendy były liczone jako wpływ gotówki.
Wymagania:
1) W tx_delta dodaj 'DIVIDEND' do bucketu credit.
2) Nie zmieniaj innych reguł znaków dla BUY/SELL/DEPOSIT/WITHDRAW/INTEREST.
3) Dodaj test regresyjny: scenariusz, gdzie dywidenda zapobiega wejściu poniżej zera.
4) Uruchom testy audytu parent-child consistency.
```

### PV-02 — usunięcie/poprawa `legacy_row` w `get_cash_balance_on_date`
```text
Popraw backend/portfolio_valuation_service.py::get_cash_balance_on_date (gałąź sub_portfolio_id != None).
Wymagania:
1) Zweryfikuj czy legacy_row jest nadal potrzebny przy modelu transactions.portfolio_id=parent.
2) Jeśli niepotrzebny: usuń legacy query i zwracaj tylko cash_balance dla (portfolio_id, sub_portfolio_id).
3) Jeśli potrzebny tymczasowo: popraw parametr query (parent_id zamiast sub_portfolio_id jako portfolio_id) i dodaj guard wykonywany tylko gdy istnieją rekordy legacy (=0/null mapping).
4) Dodaj testy dla child scope oraz case bez danych legacy.
```

### PV-03 — poprawa update metadata w `get_holdings` (agregacja)
```text
Napraw backend/portfolio_valuation_service.py::get_holdings dla aggregate=True, aby aktualizacja metadata nie dotyczyła tylko MAX(id).
Wymagania:
1) Nie opieraj UPDATE o pojedyncze id z agregatu.
2) Aktualizuj wszystkie rekordy holdings należące do danej grupy (portfolio_id + ticker + currency), albo zastosuj dedykowany mechanizm upsert metadata.
3) Ogranicz liczbę wywołań fetch_metadata (cache per ticker w ramach requestu).
4) Dodaj test potwierdzający, że przy wielu rekordach tego samego tickera metadata trafia do wszystkich rekordów grupy.
```

### PV-04 — cleanup `sub_portfolio_id = 0` warunków
```text
Przeprowadź cleanup legacy SQL w backend/portfolio_valuation_service.py dla warunków `(sub_portfolio_id IS NULL OR sub_portfolio_id = 0)`.
Wymagania:
1) Najpierw dodaj check/migracyjny guard potwierdzający brak rekordów z sub_portfolio_id = 0.
2) Jeśli brak rekordów: uprość zapytania do `sub_portfolio_id IS NULL`.
3) Jeśli rekordy istnieją: zostaw kompatybilność, ale dodaj komentarz z planem usunięcia i telemetryczny licznik użyć.
4) Dodaj testy dla parent/child scope.
```

### PV-05 — optymalizacja `_compute_cash_negative_days`
```text
Zoptymalizuj backend/portfolio_valuation_service.py::_compute_cash_negative_days.
Wymagania:
1) Usuń pełną iterację dzień-po-dniu i przejdź na event/range-based computation.
2) Incidenty mają dalej raportować datę, saldo i triggering transaction metadata.
3) Zachowaj semantykę carrying_trigger dla ciągłych okresów ujemnego salda.
4) Dodaj benchmark/regresję porównującą stare i nowe wyniki na tym samym zbiorze danych.
5) Jeśli zostaje pętla dzienna, użyj `current_day += timedelta(days=1)` zamiast fromordinal/toordinal.
```

### PV-06 — redukcja N+1 w wycenie i audycie
```text
Zredukuj N+1 zapytania w backend/portfolio_valuation_service.py dla:
- get_portfolio_value
- get_parent_child_consistency_audit
Wymagania:
1) Prefetchuj parent+children jednym/małą liczbą zapytań.
2) Uniknij wielokrotnego get_portfolio(child_id) w pętlach.
3) Przy audycie nie wywołuj get_portfolio_value(parent_id), jeśli te same dane i tak są liczone lokalnie — użyj wspólnego kontekstu wyceny.
4) Dodaj test/licznik zapytań (lub mock DB execute count) pokazujący spadek liczby query.
```

### PV-07/PV-08/PV-09 — deprecacja UTC + logger + docstring hygiene
```text
W backend/portfolio_valuation_service.py wykonaj porządki techniczne:
1) Zamień datetime.utcnow() na datetime.now(timezone.utc) (+ import timezone).
2) Zamień print(...) dla błędów XIRR na logger.exception/logger.error z kontekstem portfolio_id.
3) Zastąp komentarz "Move the existing logic..." przy _calculate_single_portfolio_value właściwym docstringiem opisującym działanie helpera.
4) Dodaj test(y) lub asercje logowania tam, gdzie infrastruktura to umożliwia.
```

### CT-01 — poprawka IKE/IKZE w `get_tax_limits` (HOTFIX)
```text
Napraw backend/portfolio_core_service.py::get_tax_limits, aby IKE nie obejmowało IKZE.
Wymagania:
1) Zmień query IKE na:
   WHERE upper(name) LIKE '%IKE%' AND upper(name) NOT LIKE '%IKZE%'
2) Zachowaj istniejące wyliczenia i format odpowiedzi.
3) Dodaj test regresyjny: portfel o nazwie zawierającej IKZE nie może zwiększać IKE.
4) Uruchom testy endpointu /tax-limits.
```

### CT-02 — atomowość `assign_transactions_bulk`
```text
Zapewnij atomowość bulk assign w backend/portfolio_trade_service.py.
Wymagania:
1) assign_transactions_bulk ma działać w jednej transakcji DB (all-or-nothing).
2) assign_transaction_to_subportfolio nie może wymuszać commit przy użyciu z bulk (dodaj flagę autocommit=False albo wydziel wersję internal).
3) Przy błędzie rollback ma cofnąć wszystkie przypisania z tej paczki.
4) Dodaj test: błąd na N-tej transakcji nie zostawia częściowo przypisanych rekordów.
```

### CT-03 — odporność rebuild na nowe typy transakcji
```text
Popraw backend/portfolio_audit_service.py::rebuild_holdings_from_transactions.
Wymagania:
1) Zastąp `raise ValueError("Unsupported transaction type...")` logowaniem warning i `continue`.
2) Dodaj licznik/składnik wyniku informujący o pominiętych nieobsługiwanych typach.
3) Zachowaj deterministykę dla wspieranych typów.
4) Dodaj test z nieznanym typem (np. TRANSFER), który nie przerywa rebuild.
```

### CT-04 — poprawny filtr `unconfirmed_conflicts`
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

### CT-05 — czytelność call-site `repair_portfolio_state`
```text
Uczyść call-site w backend/routes_transactions.py dla wywołań repair_portfolio_state po assign.
Wymagania:
1) Zastąp wywołania `repair_portfolio_state(sub_portfolio_id)` i analogiczne wersją jawnie semantyczną:
   repair_portfolio_state(portfolio_id, subportfolio_id=sub_portfolio_id)
2) Zachowaj aktualne zachowanie runtime.
3) Dodaj test/mocked assertion na argumenty wywołania.
```

### CT-06..CT-12 — pakiet low-priority cleanup
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

---

## 4) Rekomendowana kolejność wdrożeń (globalna)

1. CT-01 (IKE/IKZE — poprawność biznesowa)
2. CT-02 (atomowość bulk assign)
3. PS-03 + PS-04 (kompletność i semantyka danych cenowych)
4. TR-03 (walidacja wejścia GET)
5. PV-01 + PV-02 (gotówka i legacy gałąź)
6. CT-04 (import: potwierdzenia konfliktów)
7. PS-10, TR-07, PV-05, PV-06 (poprawność + wydajność)
8. Pozostałe cleanupy techniczne (PS-07/08/09, PV-04/07/08/09, CT-05..12)

Taka kolejność najpierw eliminuje ryzyka biznesowe i integralność danych, a następnie porządkuje wydajność i dług techniczny.

---

## 5) Nowe krytyczne znaleziska (dodane 2026-04-04)

### 🔴 Wysoki priorytet — nowe

| ID | Źródło | Problem | Priorytet | Status |
|---|---|---|---|---|
| NEW-39 | audit_data_consistency | `get_cash_balance_on_date` ignoruje `BUY`/`SELL`/`DIVIDEND` — inny model cash niż reszta systemu, transfer validation działa na błędnych danych | Wysoki | Otwarte |
| NEW-40 | audit_edge_cases | Import `SELL` bez istniejącego holdingu — cash rośnie, holding nie maleje, cicha inflacja gotówki | Wysoki | Otwarte |
| NEW-41 | audit_edge_cases | `assert` w `_assert_holding_consistency` — wyłączane przez Python `-O`, brak ochrony w produkcji | Wysoki | Otwarte |
| NEW-42 | financial_calculations | `get_holdings` — SQL agreguje `company_name`, `sector`, `industry` bez `MAX()`; SQLite może zwrócić losowy wiersz | Wysoki | Otwarte |
| NEW-43 | fx_audit | `/buy` i `/sell` przyjmują `price` bez waluty — cena USD traktowana jako PLN, contamination całego ledgera | Wysoki | Otwarte |

### 🟡 Średni priorytet — nowe

| ID | Źródło | Problem | Priorytet | Status |
|---|---|---|---|---|
| NEW-44 | audit_data_consistency | `INTEREST` w imporcie może mieć `sub_portfolio_id` — łamie regułę „INTEREST tylko parent” | Średni | Otwarte |
| NEW-45 | audit_data_consistency | Assignment bez atomowego rebuild — okno desync `transactions` vs `holdings`/`cash` | Średni | Otwarte |
| NEW-46 | error_handling | `raise e` w wielu miejscach — utrata oryginalnego traceback, utrudniony debugging | Średni | Otwarte |
| NEW-47 | error_handling | Bare `except:` w kilku miejscach (`database.py`, `routes_imports.py`, `price_service.py`) | Średni | Otwarte |
| NEW-48 | audit_edge_cases | `sub_portfolio_id=abc` w query → cicha zamiana na `None` zamiast 422 | Średni | Otwarte |
| NEW-49 | financial_calculations | `FX_FEE_RATE` jako stała vs hardcoded `0.005` w `portfolio_valuation_service.py` — desync przy zmianie stawki | Średni | Otwarte |
| NEW-50 | financial_calculations | XIRR — Newton-Raphson bez bracketing fallback, ryzyko braku zbieżności dla nieregularnych cash flow | Średni | Otwarte |
| NEW-51 | performance | Symbol resolution w imporcie — `O(N_import × N_map)` per wiersz CSV | Średni | Otwarte |
| NEW-52 | performance | PPK weekly chart — `O(W×T)` zamiast rolling | Średni | Otwarte |
| NEW-53 | performance | Budget envelope × loan — `O(E×L)` nested loop zamiast dict lookup | Średni | Otwarte |
| NEW-54 | performance | Parent valuation — `PPK fetch_current_price()` wołane per portfolio w pętli | Średni | Otwarte |
| NEW-55 | fx_audit | FX fallback na `1.0` przy braku kursu — cicha błędna wycena bez logu/ostrzeżenia | Średni | Otwarte |

### 🟢 Niski priorytet — nowe

| ID | Źródło | Problem | Priorytet | Status |
|---|---|---|---|---|
| NEW-56 | audit_data_consistency | Brak współdzielonego helpera `cash_delta(tx)` — wiele niezależnych implementacji logiki cash | Niski | Otwarte |
| NEW-57 | audit_edge_cases | Pola dat nie są walidowane jako ISO — np. `2026-99-99` przechodzi do DB | Niski | Otwarte |
| NEW-58 | error_handling | Migracje w `database.py` — `except: pass` nie rozróżnia „kolumna już istnieje” od realnego błędu | Niski | Otwarte |
| NEW-59 | error_handling | Async recalculation może paść po udanym commicie — brak retry, stan może dryfować | Niski | Otwarte |
| NEW-60 | financial_calculations | Modified Dietz z fixed mid-period assumption — błąd dla dużych przepływów na początku/końcu miesiąca | Niski | Otwarte |
| NEW-61 | fx_audit | Brak FX snapshot w transakcjach — rebuild domyślnie zakłada PLN | Niski | Otwarte |
| NEW-62 | fx_audit | `avg_buy_fx_rate = 1.0` dla non-PLN instrumentów w imporcie | Niski | Otwarte |

---

## 6) Gotowe prompty dla nowych pozycji (NEW-39..NEW-43)

### NEW-39 — spójny model cash w `get_cash_balance_on_date`
```text
Napraw backend/portfolio_valuation_service.py::get_cash_balance_on_date tak, aby model cash był spójny z resztą systemu.
Wymagania:
1) Uwzględnij wpływ typów BUY/SELL/DIVIDEND (oraz zachowaj istniejące DEPOSIT/WITHDRAW/INTEREST/TRANSFER wg obecnej semantyki).
2) Wyeliminuj rozjazd między wynikiem get_cash_balance_on_date a saldem wykorzystywanym w transfer validation.
3) Dodaj wspólny helper cash_delta(tx) albo wspólną ścieżkę obliczeń używaną przez oba miejsca.
4) Dodaj testy regresyjne:
   - BUY obniża cash,
   - SELL podnosi cash,
   - DIVIDEND podnosi cash,
   - transfer validation używa tych samych reguł i nie bazuje na błędnym saldzie.
5) Nie zmieniaj kontraktu API endpointów.
Uruchom testy portfolio valuation + transfer validation.
```

### NEW-40 — blokada SELL bez holdingu (brak inflacji gotówki)
```text
Popraw import/księgowanie SELL, aby nie zwiększać gotówki, gdy brak wystarczającego holdingu.
Wymagania:
1) W ścieżce importu i/lub rebuild_holdings wykryj SELL dla tickera bez pozycji (lub z qty < ilość SELL).
2) Zamiast cichej akceptacji:
   - zwróć błąd walidacji (preferowane) LUB
   - oznacz rekord jako conflict do ręcznego potwierdzenia, bez wpływu na cash/holdings do czasu rozwiązania.
3) Zapewnij, że cash nie rośnie, jeśli holding nie może zostać poprawnie zmniejszony.
4) Dodaj testy regresyjne:
   - SELL bez holdingu,
   - SELL większy niż holding,
   - poprawny SELL przy wystarczającym holdingu.
5) Dodaj log ostrzegawczy z portfolio_id, ticker i tx_id/hash.
Uruchom testy importu i audytu holdings/cash.
```

### NEW-41 — usunięcie krytycznych `assert` z logiki produkcyjnej
```text
Zastąp `assert` w backend (szczególnie `_assert_holding_consistency`) jawnie egzekwowaną walidacją runtime.
Wymagania:
1) Usuń zależność od `assert` dla reguł biznesowych (Python -O nie może wyłączyć ochrony).
2) Zastąp je:
   - dedykowanym wyjątkiem domenowym (np. ValidationError/ConsistencyError),
   - albo zwracanym wynikiem błędu + logger.error.
3) Zachowaj czytelny komunikat diagnostyczny (portfolio_id, ticker, expected vs actual).
4) Dodaj test potwierdzający, że ochrona działa niezależnie od optymalizacji interpretera.
5) Upewnij się, że endpoint/API zwraca spójny kod błędu (bez 500 jeśli to błąd danych wejściowych).
Uruchom testy modułu audytu i endpointów, które używają tej walidacji.
```

### NEW-42 — deterministyczna agregacja metadata w `get_holdings`
```text
Napraw zapytanie aggregate w backend/portfolio_valuation_service.py::get_holdings, aby uniknąć niedeterministycznych pól tekstowych.
Wymagania:
1) W SQL agregującym holdings nie zwracaj `company_name`, `sector`, `industry` jako „luźnych” kolumn bez agregacji.
2) Zastosuj jedną strategię:
   - CTE/subquery wybierające rekord referencyjny (np. MAX(updated_at) lub MAX(id)) i join,
   - albo jawne agregaty (np. MAX()) z uzasadnieniem semantyki.
3) Wynik ma być deterministyczny i stabilny między uruchomieniami SQLite.
4) Dodaj test regresyjny: wiele rekordów tego samego tickera z różnymi metadata nie daje losowych wyników.
5) Sprawdź, czy poprawka nie psuje istniejących endpointów holdings.
Uruchom testy portfolio valuation/holdings.
```

### NEW-43 — waluta ceny w `/buy` i `/sell` (FX safety)
```text
Uszczelnij endpointy `/buy` i `/sell`, aby cena była interpretowana z poprawną walutą instrumentu.
Wymagania:
1) Rozszerz payload o jawne pole waluty ceny (np. `price_currency`) lub jednoznacznie wyprowadź je z instrumentu/tickera.
2) Jeśli waluta ceny ≠ waluta portfela, przelicz przez FX rate (z daty transakcji) przed zapisaniem cash impact.
3) Gdy brakuje kursu FX:
   - nie stosuj cichego fallbacku 1.0,
   - zwróć błąd walidacji albo oznacz transakcję jako wymagającą interwencji.
4) Dodaj testy regresyjne:
   - zakup/sprzedaż instrumentu USD w portfelu PLN,
   - poprawne księgowanie cash i avg_buy_fx_rate,
   - brak kursu FX => jawny błąd/flag.
5) Zachowaj kompatybilność istniejących klientów przez bezpieczny default/migrację kontraktu (opisz w changelogu API).
Uruchom testy trade routes + portfolio valuation + FX audit.
```
