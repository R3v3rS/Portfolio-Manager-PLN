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
| NEW-39 | audit_data_consistency | `get_cash_balance_on_date` ignoruje `BUY`/`SELL`/`DIVIDEND` — inny model cash niż reszta systemu, transfer validation działa na błędnych danych | Wysoki | Zamknięte (2026-04-04) |
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
| NEW-56 | audit_data_consistency | Brak współdzielonego helpera `cash_delta(tx)` — wiele niezależnych implementacji logiki cash | Niski | Zamknięte (2026-04-04) |
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

NEW-44 — INTEREST z sub_portfolio_id w imporcie łamie regułę „tylko parent"
textWymuś regułę „INTEREST musi należeć do parent" w ścieżce importu.
Zakres: backend/portfolio_import_service.py (ścieżka INTEREST przy imporcie).

Wymagania:
1) Przed zapisem transakcji INTEREST sprawdź, czy sub_portfolio_id jest None/null.
2) Jeśli import dostarcza sub_portfolio_id dla INTEREST, zignoruj go (ustaw NULL) i zaloguj warning z hash/row_id.
3) Dodaj analogiczną walidację w warstwie serwisu (portfolio_trade_service.py), aby inne callerzy
   nie mogli ominąć reguły.
4) Dodaj testy:
   - import INTEREST z sub_portfolio_id => sub_portfolio_id ignorowane, log warning,
   - ręczny zapis INTEREST z sub_portfolio_id => błąd lub sanityzacja,
   - spójność: INTEREST w DB po imporcie zawsze ma sub_portfolio_id IS NULL.
5) Dodaj migrację danych: zaktualizuj istniejące rekordy INTEREST z sub_portfolio_id != NULL
   na NULL i zaloguj listę zmienionych ID.
Uruchom testy importu i audytu parent-child.

NEW-45 — Assignment bez atomowego rebuild (okno desync)
textUczyń assign_transaction_to_subportfolio atomowym względem rebuild holdings/cash.
Zakres: backend/portfolio_trade_service.py (assign + rebuild), backend/routes_transactions.py (call-site).

Wymagania:
1) Operacja assign + rebuild musi być objęta jedną transakcją DB (begin → assign update →
   rebuild holdings/cash → commit / rollback on any error).
2) Żaden caller zewnętrzny nie powinien móc wykonać assign bez rebuild w tej samej transakcji.
3) Jeśli rebuild jest asynchroniczny z przyczyn wydajnościowych, dodaj mechanizm kompensacyjny:
   - ustaw flagę `needs_repair=1` na portfolio przed commitem,
   - przy odpowiedzi API zwróć status `repair_scheduled`,
   - async job: potwierdź repair i ustaw flagę na 0.
4) Dodaj testy:
   - błąd w rebuild rollbackuje również assign,
   - stan holdings/cash po assign jest spójny z przypisanymi transakcjami (bez okna desync),
   - GET portfolio value bezpośrednio po assign zwraca poprawne wartości.
Uruchom testy portfolio_trade_service i routes_transactions.

NEW-46 — raise e zamiast raise (utrata traceback)
textZastąp pattern `raise e` gołym `raise` we wszystkich service wrapperach transakcji DB.
Zakres: backend/portfolio_core_service.py, backend/portfolio_trade_service.py,
        backend/budget_service.py, backend/watchlist_service.py, backend/bond_service.py.

Wymagania:
1) Wyszukaj wszystkie wystąpienia `except Exception as e: ... raise e` (lub `raise e` bez re-wrap).
2) Zamień na `raise` (bare re-raise) po bloku cleanup/rollback, aby zachować oryginalny traceback.
3) Nie zmieniaj logiki rollbacku ani logowania — tylko składnię re-raise.
4) Dodaj test lub assert potwierdzający, że po re-raise traceback wskazuje na oryginalne miejsce
   wyjątku, a nie na wrapper (np. przez sprawdzenie `__traceback__.tb_frame`).
5) Przejrzyj plik pod kątem `raise SomeException(str(e))` — te przypadki wymagają osobnej decyzji:
   jeśli wrapping jest intencjonalny, dodaj `from e`; jeśli nie — użyj `raise`.
Uruchom pełny zestaw testów backendu i potwierdź brak regresji.

NEW-47 — Bare except: w kilku miejscach
textUsuń wszystkie bare `except:` (bez typu wyjątku) z kodu produkcyjnego backendu.
Zakres: backend/database.py, backend/routes_imports.py, backend/price_service.py.

Wymagania:
1) Wyszukaj `except:` (bare) i `except BaseException`.
2) Dla każdego wystąpienia zdecyduj:
   a) Jeśli guard dla "kolumna już istnieje" / "tabela już istnieje" → zmień na
      `except sqlite3.OperationalError as e: if "already exists" not in str(e): raise`.
   b) Jeśli catch-all na granicach workera/pętli → zmień na `except Exception as e:` z logowaniem.
   c) Jeśli blok jest nieosiągalny lub niepotrzebny → usuń.
3) Żaden catch nie może cicho połykać wyjątku bez logu (minimum `logger.warning`).
4) Dodaj test dla każdej naprawionej lokalizacji, gdzie nieoczekiwany wyjątek (np. PermissionError)
   powinien teraz propagować się lub być zalogowany.
Uruchom testy modułów database, routes_imports, price_service.

NEW-48 — sub_portfolio_id=abc → 422 zamiast cichego None
textNapraw walidację query param `sub_portfolio_id` w routes transakcji (TR-03 rozszerzony).
Zakres: backend/routes_transactions.py (get_transactions, get_all_transactions).

Wymagania:
1) Wartości akceptowane: brak parametru, "none" (case-insensitive), dodatni integer string.
2) Wszelkie inne wartości (0, ujemne, nieliczbowe, bool-like) → zwróć 422 z body:
   {"code": "INVALID_QUERY_PARAM", "field": "sub_portfolio_id", "message": "..."}
3) Usuń obecny `except ValueError: ... = None`.
4) Wynieś logikę parsowania do shared helpera `parse_optional_positive_int(value, field_name)`,
   który rzuca ApiError(422) zamiast ValueError.
5) Dodaj testy: "none" → None, "5" → 5, "0" → 422, "-3" → 422, "abc" → 422, "" → 422.
Uruchom testy routes_transactions.

NEW-49 — FX_FEE_RATE vs hardcoded 0.005
textUjednolić użycie stałej FX_FEE_RATE w całym backendzie.
Zakres: backend/portfolio_valuation_service.py, backend/portfolio_trade_service.py.

Wymagania:
1) Zdefiniuj stałą `FX_FEE_RATE` w jednym miejscu (np. backend/constants.py lub
   PortfolioTradeService jako class-level constant).
2) Zastąp wszystkie inline literale `0.005` / `0.0050` referencją do tej stałej.
3) Upewnij się, że fee jest stosowane identycznie w: live holdings valuation, 1D/7D change path,
   historical valuation, trade service sell fee calculation.
4) Dodaj test spójności: ta sama transakcja wyceniana przez live endpoint i historical endpoint
   daje identyczny net_value po uwzględnieniu fee.
5) Dodaj komentarz dokumentujący, skąd pochodzi wartość stawki i gdzie ją zmienić.
Uruchom testy portfolio_valuation_service i portfolio_trade_service.

NEW-50 — XIRR: Newton-only bez bracketing fallback
textUodpornij backend/math_utils.py::xirr na niezbieżność Newton-Raphson.

Wymagania:
1) Przed NR: znajdź bracket [lo, hi] przez skanowanie zakresu [-0.9999, 10.0] w kilkunastu krokach.
2) Jeśli bracket nie znaleziony → zwróć None (lub strukturalny błąd "NO_BRACKET") zamiast
   wyjątku/błędnej wartości.
3) Jeśli bracket znaleziony → uruchom solver Brent/Bisection w tym przedziale jako fallback.
4) Opcjonalnie: przyspiesz NR (warm-start z wynikiem bisection) dla szybszych typowych przypadków.
5) Zmień kryterium zbieżności: wymagaj jednocześnie abs(delta_rate) < 1e-7 ORAZ abs(NPV) < 1e-6.
6) Usuń heurystykę `if rate <= -1: rate = -0.99` — zamiast niej użyj bracket clamp.
7) Dodaj testy:
   - nieregularne przepływy (wiele zmian znaku) → solver nie zwraca błędnego korzenia,
   - wszystkie przepływy tego samego znaku → NO_BRACKET (brak XIRR),
   - scenariusz bliski -100% → poprawna zbieżność lub jawny błąd.
Uruchom testy math_utils i portfolio_valuation_service (XIRR integration).

NEW-51 — Symbol resolution: O(N_import × N_map) per wiersz
textZoptymalizuj backend/portfolio_import_service.py::resolve_symbol_mapping dla bulk importu.

Wymagania:
1) Przed pętlą po wierszach CSV: pobierz całą tabelę symbol_mappings jednym zapytaniem SQL
   i zbuduj słownik (znormalizowany_symbol → mapping).
2) W trakcie pętli używaj wyłącznie tego słownika (O(1) lookup) — bez dodatkowych zapytań DB.
3) Fuzzy matching: prekomputuj listę kandydatów raz (poza pętlą), wewnątrz pętli tylko szukaj
   w prekomputowanej strukturze.
4) Dodaj request-level memoization: jeśli ten sam symbol pojawia się wielokrotnie w jednym imporcie,
   nie obliczaj go drugi raz.
5) Zachowaj logikę fallback (exact → normalized → fuzzy) — zmień tylko strukturę danych/kolejność
   wywołań.
6) Dodaj test wydajnościowy: import 500 wierszy z 200 unikalnymi symbolami nie wykonuje więcej
   niż N+const zapytań DB (N = unikalnych symboli, nie wierszy).
Uruchom testy portfolio_import_service.

NEW-52 — PPK weekly chart: O(W×T) zamiast rolling
textZoptymalizuj backend/modules/ppk/ppk_service.py::get_chart_data_extended.

Wymagania:
1) Posortuj transakcje raz po dacie przed pętlą tygodniową.
2) Zastosuj rolling pointer (index i): przesuń i do przodu wraz z kolejnym week_date,
   akumulując jednostki i kwoty inkrementalnie.
3) PPKCalculation.calculate_metrics wywołaj z bieżącym stanem skumulowanym (nie z listą
   filtrowaną od zera).
4) Jeśli calculate_metrics wymaga pełnej listy z przyczyn logiki podatkowej: przeróbka
   calculate_metrics na wersję inkrementalną z przekazaniem delta (nowe transakcje od
   ostatniego tygodnia).
5) Zachowaj identyczny format odpowiedzi i wartości numeryczne.
6) Dodaj test porównawczy (stara vs nowa implementacja) dla 260 tygodni × 500 transakcji.
Uruchom testy PPK service.

NEW-53 — Budget envelope × loan: O(E×L) nested loop
textZoptymalizuj backend/budget_service.py — obliczanie outstanding_loans per envelope.

Wymagania:
1) Przed pętlą po kopertach: załaduj wszystkie loans_rows jednym zapytaniem.
2) Zbuduj dict `remaining_by_envelope: {source_envelope_id: total_remaining}` jednym przejściem
   po loans_rows (lub przez SQL GROUP BY source_envelope_id + SUM(remaining)).
3) W pętli per-envelope: użyj remaining_by_envelope.get(env['id'], 0) — O(1).
4) Opcjonalnie: przenieś agregację do SQL:
   SELECT source_envelope_id, SUM(remaining) FROM budget_loans WHERE ... GROUP BY 1
5) Zachowaj semantykę: tylko aktywne (niespłacone) pożyczki w sumie.
6) Dodaj test z 100 kopertami i 1000 pożyczkami — wynik identyczny, czas < obecny.
Uruchom testy budget_service.

NEW-54 — Parent valuation: PPK fetch_current_price() per portfolio w pętli
textWyeliminuj powtarzane I/O w backend/portfolio_valuation_service.py przy wycenie parent portfolio.

Wymagania:
1) Przed pętlą po portfolio_ids: ustal które z nich to PPK i pobierz PPK current price raz
   (jeden call PPKService.fetch_current_price()).
2) Przekaż cenę jako parametr do iteracji (nie wywołuj w środku pętli).
3) Analogicznie: batch-pobierz metadane portfolio dla wszystkich IDs jednym zapytaniem SQL
   zamiast get_portfolio(p_id) per iteracja.
4) Batch-pobierz DEPOSIT/WITHDRAW flows dla wszystkich portfolio_ids jednym zapytaniem z GROUP BY.
5) Zachowaj identyczne wartości wynikowe.
6) Dodaj test (mock DB + mock PPK) potwierdzający, że fetch_current_price wywołany ≤ 1 raz
   niezależnie od liczby PPK subportfolio.
Uruchom testy portfolio_valuation_service (parent aggregate path).

NEW-55 — FX fallback na 1.0 bez logu/ostrzeżenia
textZastąp cichy FX fallback `1.0` jawnym statusem w backend/portfolio_trade_service.py,
backend/portfolio_valuation_service.py, backend/portfolio_history_service.py.

Wymagania:
1) Wszędzie gdzie brak kursu FX skutkuje `rate = 1.0`:
   a) Zaloguj warning z: ticker, currency, date, portfolio_id.
   b) Ustaw fx_status = "MISSING" (lub "STALE") na zwracanym obiekcie wyceny.
2) Dla endpointów live valuation i history: dodaj pole `fx_warnings: []` do odpowiedzi,
   które zawiera listę tickerów z brakującym kursem w danym obliczeniu.
3) Opcjonalnie: zamiast 1.0 użyj ostatniego dostępnego kursu (last-known) z datą i flagą "STALE".
4) Nie przerywaj wyceny — degradacja graceful, ale zawsze z widocznym sygnałem.
5) Dodaj testy:
   - wycena bez dostępnego kursu FX → fx_warnings zawiera ticker,
   - log zawiera wymagane pola kontekstu,
   - wartość wyceny z 1.0 jest poprawnie oznaczona jako niedokładna.
Uruchom testy portfolio_valuation_service, portfolio_history_service.

NEW-57 — Pola dat nie walidowane jako ISO (2026-99-99 przechodzi do DB)
textWprowadź spójną walidację dat ISO 8601 na wszystkich write endpoint'ach backendu.
Zakres: backend/routes_transactions.py, backend/routes_portfolios.py, backend/routes_budget.py,
        backend/routes_ppk.py, backend/bond_service.py.

Wymagania:
1) Stwórz shared helper `parse_iso_date(value: str, field: str) -> date`:
   - próbuje datetime.strptime(value, '%Y-%m-%d'),
   - przy błędzie rzuca ApiError(422, code="INVALID_DATE", field=field, message="...").
2) Analogicznie `parse_year_month(value, field)` dla pól YYYY-MM.
3) Zastąp all raw string date assignments wywołaniem helpera na write path.
4) Opcjonalnie: odrzucaj daty w przyszłości, jeśli reguły biznesowe tego wymagają
   (np. data transakcji > dzisiaj + 1 dzień).
5) Dodaj testy:
   - "2026-99-99" → 422,
   - "abc" → 422,
   - "2026-04-06" → poprawnie parsowane,
   - "2026/04/06" → 422,
   - pola w routes_budget (from_month, to_month) → błąd przy złym formacie.
Uruchom testy wszystkich objętych endpointów.

NEW-58 — Migracje w database.py: except: pass nie rozróżnia przypadków
textUodpornij observability migracji schematu w backend/database.py.

Wymagania:
1) Zastąp bare `except: pass` i `except sqlite3.OperationalError: pass` w blokach migracyjnych
   dedykowanym helperem `_migration_guard(fn, description)`:
   - jeśli OperationalError.message zawiera "already exists" / "duplicate column" → log INFO, pass,
   - każdy inny błąd → log ERROR z description + full traceback, raise.
2) Po zakończeniu migracji emituj summary log: "Migrations complete: N applied, M skipped, K failed".
3) Dla błędów nieoczekiwanych: przerwij startup i nie pozwól aplikacji wystartować w niespójnym
   stanie schematu.
4) Dodaj testy dla helpera:
   - "duplicate column" → pass + log INFO,
   - inny OperationalError → raise + log ERROR,
   - ogólny Exception → raise + log ERROR.
Uruchom testy database.py i startup integration test.

NEW-59 — Async recalculation po commicie bez retry
textDodaj retry i widoczność stanu dla async recalculation jobs w backend/routes_transactions.py.

Wymagania:
1) Zdefiniuj bounded retry policy dla recalculation workerów:
   - max 3 próby, backoff: 1s, 3s, 10s,
   - po wyczerpaniu prób: ustaw job status = "failed_permanent" i zaloguj alert.
2) Job store: zastąp in-memory słownik trwałym (np. tabela SQLite `background_jobs`) z kolumnami:
   job_id, status, portfolio_id, created_at, last_attempt, attempts, error.
3) Endpoint statusu: GET /api/jobs/<job_id> zwraca aktualny status i szczegóły błędu.
4) Przy odpowiedzi na transfer/assign: zwróć job_id i status_url w body, np.:
   {"success": true, "job_id": "abc", "status_url": "/api/jobs/abc"}
5) Dodaj testy:
   - job kończy się błędem → retry do max, potem failed_permanent,
   - stan portfolio po failed_permanent jest logicznie spójny (transakcje zatwierdzone,
     holdings mogą być nieaktualne — wyraźnie udokumentowane),
   - GET /api/jobs/<id> zwraca poprawny status.
Uruchom testy routes_transactions (transfer, assign paths).

NEW-60 — Modified Dietz z fixed mid-period assumption
textPopraw metodę zwrotu miesięcznego w backend/portfolio_history_service.py::get_performance_matrix.

Wymagania:
1) Zamiast stałego `start_value + net_flows/2` zastosuj ważony Modified Dietz:
   - dla każdego przepływu w miesięcu: waga = (dni_do_końca_miesiąca / dni_w_miesiącu),
   - denominator = start_value + SUM(flow_i × weight_i).
2) Opcja B (preferowana długoterminowo): przejdź na daily time-weighted return (TWR) chain-linking.
   Jeśli TWR wymaga zbyt dużej refaktoryzacji, zaakceptuj ważony Dietz jako etap pośredni.
3) Zachowaj format odpowiedzi i zaokrąglenia.
4) Dodaj testy:
   - duży przepływ na początku miesiąca → waga ~1.0, duży wpływ na denominator,
   - duży przepływ na końcu miesiąca → waga ~0, mały wpływ,
   - brak przepływów → wynik identyczny ze starą metodą,
   - wynik dla dużych przepływów różni się od starego mid-period (potwierdzenie poprawności).
5) Dodaj komentarz z opisem metodologii (Modified Dietz weighted / TWR) dla przyszłych maintainerów.
Uruchom testy portfolio_history_service.

NEW-61 — Brak FX snapshot w transakcjach (rebuild zakłada PLN)
textWprowadź fundament pod FX snapshot per transakcja w backend/database.py i write paths.
(Zadanie architektoniczne — może być realizowane iteracyjnie.)

Etap 1 — schemat (ten prompt):
1) Dodaj migrację dodającą kolumny do tabeli `transactions`:
   - `price_currency TEXT DEFAULT 'PLN'`
   - `price_native REAL`
   - `fx_rate_at_trade REAL`
   - `fx_source TEXT`  -- 'snapshot' | 'legacy_assumed_pln' | 'manual'
2) Dla istniejących rekordów: ustaw fx_source='legacy_assumed_pln', fx_rate_at_trade=1.0,
   price_currency='PLN'.
3) Nie zmieniaj jeszcze logiki write paths — tylko schemat i backfill.
4) Dodaj endpoint diagnostyczny (admin only): GET /api/admin/fx-coverage zwraca:
   - total transactions, transactions z fx_source='legacy_assumed_pln', z 'snapshot'.
5) Dodaj test migracji: po backfill wszystkie starsze rekordy mają fx_source='legacy_assumed_pln'.
Uruchom testy database.py.

NEW-62 — avg_buy_fx_rate = 1.0 dla non-PLN instrumentów w imporcie
textZapobiegaj domyślnemu avg_buy_fx_rate=1.0 dla instrumentów non-PLN w import path.
Zakres: backend/portfolio_import_service.py (holding upsert path).

Wymagania:
1) Przy upsert holdingu: jeśli instrument_currency != 'PLN' i nie mamy rzeczywistego fx_rate:
   a) Spróbuj pobrać fx_rate dla daty transakcji z PriceService/YahooFinance ({CCY}PLN=X).
   b) Jeśli pobranie się nie uda → nie zapisuj 1.0; zamiast tego:
      - ustaw fx_rate = NULL,
      - ustaw fx_source = 'missing',
      - zaloguj warning z ticker, portfolio_id, tx_date.
2) Nigdy nie zapisuj fx_rate=1.0 dla instrumentu z walutą != PLN (chyba że rzeczywiście
   instrument ma kurs 1:1 z PLN — np. EUR/PLN w momencie odchylenia 0, co jest nierealistyczne).
3) Dodaj endpoint lub raport: GET /api/admin/holdings-fx-audit → lista holdingów z
   avg_buy_fx_rate=1.0 i instrument_currency != PLN (potencjalnie błędne dane).
4) Dodaj testy:
   - import USD tickera z dostępnym kursem → avg_buy_fx_rate != 1.0,
   - import USD tickera bez dostępnego kursu → fx_rate=NULL, fx_source='missing', log warning,
   - import PLN tickera → fx_rate=1.0 akceptowane.
Uruchom testy portfolio_import_service.

Sekcja B — Nowe pozycje (NEW-63..NEW-71)
Poniższe problemy wynikają z audytów, ale nie zostały ujęte w poprzedniej liście NEW-39..NEW-62.
Tabela nowych pozycji
IDŹródłoProblemPriorytetStatusNEW-63audit_performanceLoan schedule: O(M×(R+O)) — pętla miesięczna skanuje całą listę rat/nadpłat per iteracjaŚredniOtwarteNEW-64audit_edge_cases / edge_cases_auditBond purchase_date — brak walidacji na write, crash strptime na readWysokiOtwarteNEW-65audit_edge_casesLoan schedule — unsafe DB assumptions (brak walidacji przed kalkulacją)ŚredniOtwarteNEW-66audit_edge_casesBudget service write methods — brak amount > 0 i walidacji dat na poziomie serwisuŚredniOtwarteNEW-67audit_edge_casesPPK — transakcja z employeeUnits=0 i employerUnits=0 przechodzi walidacjęNiskiOtwarteNEW-68financial_calculations_auditPnL — wzory zduplikowane w 3 miejscach (sell_stock, import, audit rebuild) z różną precyzjąWysokiOtwarteNEW-69financial_calculations_auditPolityka numeryczna — mieszanie float + round + Decimal bez regułyŚredniOtwarteNEW-70fx_auditLogika FX conversion zduplikowana w 4 serwisach (brak centralnego modułu FX)ŚredniOtwarteNEW-71audit_data_consistencyParent/child scope — brak jednolitej definicji PARENT_OWN vs PARENT_AGGREGATED w historii, wycenie i audycieWysokiOtwarte

NEW-63 — Loan schedule: O(M×(R+O)) per miesiąc
textZoptymalizuj backend/loan_service.py::calculate_schedule.

Wymagania:
1) Przed pętlą miesięczną: sparsuj i posortuj wszystkie `sorted_rates` i `sorted_overpayments`
   raz (datetime.strptime poza pętlą).
2) Zastosuj dual-pointer traversal:
   - pointer `rate_idx` przesuwa się do przodu gdy current_month >= rates[rate_idx+1].valid_from,
   - aktywna stopa = rates[rate_idx].rate (O(1) lookup per miesiąc).
3) Dla overpayments: pre-grupuj do dict `ops_by_month: {YYYY-MM: [ops]}` jednym przejściem
   przed pętlą. Wewnątrz pętli: ops_by_month.get(current_month_key, []).
4) Zachowaj identyczną semantykę (decreasing installment, fixed installment, early payoff logic).
5) Dodaj testy:
   - wyniki identyczne ze starą implementacją dla fixture z 360 miesiącami, 5 zmianami stopy,
     20 nadpłatami,
   - brak wywołań strptime wewnątrz pętli (mock/assert).
Uruchom testy loan_service.

NEW-64 — Bond purchase_date: brak walidacji → crash na read
textZabezpiecz bond purchase_date przed persystencją błędnych wartości.
Zakres: backend/routes_portfolios.py (add_bond), backend/bond_service.py (get_bonds).

Wymagania:
1) Write path (add_bond): zwaliduj purchase_date jako ISO date (YYYY-MM-DD) przed insertem.
   Użyj shared helpera parse_iso_date() (patrz NEW-57). Zwróć 422 dla błędnych wartości.
2) Read path (get_bonds): opakuj strptime w try/except; dla invalid row:
   - zaloguj error z bond_id i raw wartością,
   - zastąp wartość None lub pomiń rekord z flagą `parse_error: true`,
   - nie crashuj całego endpointu.
3) Dodaj migrację/health-check: SELECT id, purchase_date FROM bonds WHERE
   purchase_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   i zaloguj wyniki przy starcie (ostrzeżenie admina).
4) Dodaj testy:
   - POST add_bond z "2026/01/15" → 422,
   - seed DB z błędną datą + GET bonds → endpoint żyje, rekord oznaczony jako błędny,
   - poprawna data → poprawna odpowiedź.
Uruchom testy bond_service i routes_portfolios.

NEW-65 — Loan schedule: unsafe DB assumptions
textDodaj walidację danych wejściowych do backend/loan_service.py::calculate_schedule.

Wymagania:
1) Przed uruchomieniem kalkulacji: zwaliduj i sanityzuj loan record:
   - duration_months > 0 (ApiError 422 jeśli nie),
   - original_amount > 0,
   - start_date parseable jako YYYY-MM-DD,
   - installment_type in ('decreasing', 'fixed') (lub inny enum),
   - interest_rate >= 0.
2) Dla rate records: filtruj/pomijaj nieparseable valid_from_date z logiem warning i row_id.
3) Dla overpayment records: filtruj/pomijaj nieparseable date z logiem warning i row_id.
4) Jeśli walidacja loan record failuje → rzuć ValidationError (nie raw ValueError/crashuj).
5) Dodaj testy:
   - loan z duration_months=0 → ValidationError,
   - rate z błędną datą → pominięty + warning, reszta kalkulacji działa,
   - loan z nieznanym installment_type → ValidationError z jasnym komunikatem.
Uruchom testy loan_service.

NEW-66 — Budget service: brak service-level guards dla amount > 0 i dat
textDodaj walidację na poziomie serwisu w backend/budget_service.py dla write methods.

Wymagania:
1) Dla metod: add_income, allocate_money, spend, transfer_between_accounts,
   transfer_to_investment, withdraw_from_investment, borrow_from_envelope, repay_envelope_loan:
   - dodaj na początku: `assert_positive_amount(amount)` (lub if + raise ValueError),
   - dodaj: `parse_iso_date_or_raise(date)` gdzie metoda przyjmuje datę.
2) Dla transfer_between_accounts: jeśli from_account_id == to_account_id → raise ValueError
   (transfer do siebie jest operacją no-op, potencjalnie błędem).
3) Helpers (`assert_positive_amount`, `parse_iso_date_or_raise`) wyeksportuj do shared modułu,
   aby były reużywane przez inne serwisy (patrz NEW-57).
4) Zachowaj kompatybilność z istniejącymi callersami (route layer nadal może mieć własną
   walidację — serwis stanowi drugą linię obrony).
5) Dodaj testy direct-service-call (bez HTTP):
   - spend(-100) → ValueError,
   - add_income(0) → ValueError,
   - transfer_between_accounts(from_id=1, to_id=1, ...) → ValueError,
   - add_income z datą "abc" → ValueError/ApiError.
Uruchom testy budget_service.

NEW-67 — PPK: transakcja z oboma Units=0 przechodzi walidację
textDodaj walidację logiczną dla unitów PPK transakcji.
Zakres: backend/modules/ppk/ppk_service.py, backend/routes_ppk.py.

Wymagania:
1) W routes_ppk (przy add_transaction): sprawdź, że co najmniej jedno z
   {employeeUnits, employerUnits} jest > 0. Jeśli oba == 0 → zwróć 422.
2) Analogiczna walidacja w PPKService.add_transaction (service-level guard).
3) Zwaliduj też tx_date jako ISO date YYYY-MM-DD; odrzuć daty w przyszłości (opcjonalnie
   konfigurowalne via env flag `PPK_ALLOW_FUTURE_DATES`).
4) Dodaj testy:
   - employeeUnits=0, employerUnits=0 → 422,
   - employeeUnits=0, employerUnits=5 → OK,
   - tx_date="abc" → 422,
   - tx_date w przyszłości → 422 (jeśli feature enabled).
Uruchom testy PPK service i routes.

NEW-68 — PnL: wzory zduplikowane w 3 miejscach z różną precyzją
textWynieś obliczenia PnL/cost-basis do jednego shared helpera.
Zakres: backend/portfolio_trade_service.py (sell_stock), backend/portfolio_import_service.py
        (SELL import path), backend/portfolio_audit_service.py (rebuild_holdings_from_transactions).

Wymagania:
1) Utwórz backend/portfolio_math.py (lub backend/core/pnl.py) z helperami:
   - `compute_sell_allocation(quantity, avg_price, total_cost)
     -> {cost_basis: Decimal, realized_profit: Decimal}`
   - `compute_remaining_cost(total_cost, sold_qty, avg_price) -> Decimal`
   - `compute_new_avg_price(old_total_cost, new_total_cost, new_quantity) -> Decimal`
2) Implementacja wyłącznie w Decimal; zaokrąglaj tylko na wyjściu do zdefiniowanej precyzji
   (np. 8 miejsc dla cen, 2 dla kwot PLN).
3) Zastąp wszystkie 3 ad-hoc implementacje wywołaniem helpera.
4) Dodaj testy:
   - 1000 naprzemiennych BUY/SELL → identyczny końcowy realized_profit niezależnie od kolejności
     (stara vs nowa implementacja),
   - partial sell 50/100 akcji → cost_basis proporcjonalny,
   - sprzedaż ostatnich akcji → remaining_cost == 0 (brak epsilon drift).
Uruchom testy trade_service, import_service, audit_service.

NEW-69 — Polityka numeryczna: float + round + Decimal bez reguły
textUstandaryzuj politykę numeryczną dla obliczeń monetarnych w backendzie.

Wymagania:
1) Zdefiniuj w backend/portfolio_math.py (lub constants.py) globalną politykę:
   - wszystkie kwoty monetarne: Decimal,
   - zaokrąglanie: ROUND_HALF_UP,
   - precyzja kwot PLN: 2 miejsca, ceny: 6-8, kursy FX: 6, ilości (qty): 8.
2) Dodaj utility functions:
   - `money(v) -> Decimal`  — konwersja + normalizacja kwoty PLN,
   - `qty(v) -> Decimal`    — ilość instrumentu,
   - `rate(v) -> Decimal`   — kurs FX lub stopa %.
3) W rolling state (portfolio_history_service._apply_tx_to_rolling):
   - usuń `round(...)` per krok — trzymaj Decimal wewnętrznie,
   - zaokrąglaj tylko przy serializacji do JSON (przez `float()` lub `str()`).
4) Zakaz: `round(x, n)` bezpośrednio na float w logice serwisu — ban na poziomie code review
   (dodaj komentarz policy + linter rule jeśli dostępny).
5) Dodaj testy:
   - 1000 kolejnych BUY po 0.001 PLN → suma dokładna (bez float drift),
   - ta sama sekwencja transakcji w różnej kolejności → identyczny wynik końcowy,
   - serial round vs single-round → brak rozbieżności.
Uruchom testy wszystkich serwisów finansowych (smoke test).

NEW-70 — FX conversion logic: zduplikowana w 4 serwisach
textScentralizuj logikę FX conversion w dedykowanym module.
Zakres: backend/portfolio_valuation_service.py, backend/portfolio_history_service.py,
        backend/portfolio_import_service.py, backend/portfolio_trade_service.py.

Wymagania:
1) Utwórz backend/fx_service.py z metodami:
   - `resolve_instrument_currency(ticker: str, holdings_currency: str = None) -> str`
     (jedyna logika inference: symbol_mappings → metadata → holdings.currency → fallback PLN)
   - `convert_to_pln(amount: Decimal, currency: str, as_of_date: date,
                     mode: Literal['live', 'historical']) -> tuple[Decimal, FxResult]`
     gdzie FxResult = {rate, source, status: OK|MISSING|STALE, timestamp}
   - `estimate_sell_fee(amount_pln: Decimal, currency: str) -> Decimal`
     (używa FX_FEE_RATE z constants — patrz NEW-49)
2) Zastąp wszystkie inline implementacje konwersji wywołaniem fx_service.
3) Fallback policy (spójna z NEW-55): jeśli rate niedostępny → status=MISSING, nie 1.0.
4) Dodaj testy jednostkowe fx_service:
   - live conversion USD → PLN,
   - historical conversion EUR → PLN z datą,
   - missing rate → FxResult.status == MISSING,
   - PLN → PLN → rate=1.0, status=OK (bez zewnętrznego lookupa).
5) Dodaj integration test: valuation_service i history_service używają tego samego fx_service
   i zwracają identyczny kurs dla tego samego tickera/daty.
Uruchom testy wszystkich 4 serwisów.

NEW-71 — Parent/child scope: brak jednolitej definicji
textSkodyfikuj semantykę scope parent/child i wymuś spójność across history, valuation i audit.
Zakres: backend/portfolio_history_service.py, backend/portfolio_valuation_service.py,
        backend/portfolio_audit_service.py.

Wymagania:
1) Zdefiniuj enum lub stałe w backend/constants.py:
   - `PortfolioScope.PARENT_OWN`         — transakcje parent z sub_portfolio_id IS NULL,
   - `PortfolioScope.CHILD`              — transakcje konkretnego child (sub_portfolio_id = X),
   - `PortfolioScope.PARENT_AGGREGATED`  — parent_own + wszystkie children.
2) Utwórz query builder `build_tx_scope_filter(scope, portfolio_id, child_id=None) -> str, params`:
   - zwraca fragment SQL + parametry odpowiedni dla każdego scope.
3) Zastąp wszystkie inline scope SQL-query fragments wywołaniem builder'a.
4) Udokumentuj per endpoint, który scope jest stosowany i dlaczego (docstring lub OpenAPI comment).
5) Dodaj testy:
   - `get_cash_balance_on_date(parent)` vs `_compute_cash_negative_days(parent)` → ten sam scope,
   - `get_performance_matrix(parent)` → PARENT_AGGREGATED (children + own),
   - te same dane z różnymi endpointami → spójne cash/invested_capital dla tego samego zakresu dat.
Uruchom testy portfolio_history_service, portfolio_valuation_service, portfolio_audit_service.

Sekcja C — Zaktualizowana tabela priorytetów (cały otwarty backlog)
Tabela obejmuje tylko otwarte pozycje. Pozycje zamknięte (CT-01, CT-02, PV-01, NEW-39, NEW-56) pominięte.
🔴 Krytyczne / Wysoki priorytet — implementuj najpierw
IDProblemPrompt gotowyNEW-40Import SELL bez holdingu — inflacja gotówki✅NEW-41assert w _assert_holding_consistency — wyłączane przez -O✅NEW-42get_holdings SQL — niedeterministyczne pola tekstowe✅NEW-43/buy//sell bez waluty ceny — contamination ledgera✅NEW-64Bond purchase_date — crash na read✅ (nowy)NEW-68PnL zduplikowany w 3 miejscach — drift precyzji✅ (nowy)NEW-71Parent/child scope — brak definicji, niespójne wyniki✅ (nowy)TR-03sub_portfolio_id w GET — cicha zamiana na None✅PS-03get_quotes fallback po błędzie bulk✅PS-04price=0.0 przy braku danych✅
🟡 Średni priorytet
IDProblemPrompt gotowyNEW-44INTEREST w imporcie z sub_portfolio_id✅ (nowy)NEW-45Assignment bez atomowego rebuild✅ (nowy)NEW-46raise e → utrata traceback✅ (nowy)NEW-47Bare except: w 3 modułach✅ (nowy)NEW-48sub_portfolio_id=abc → 422✅ (nowy)NEW-49FX_FEE_RATE vs 0.005 inline✅ (nowy)NEW-50XIRR bez bracketing fallback✅ (nowy)NEW-51Symbol resolution O(N×M)✅ (nowy)NEW-52PPK weekly chart O(W×T)✅ (nowy)NEW-53Budget envelope×loan O(E×L)✅ (nowy)NEW-54Parent valuation — PPK fetch per portfolio✅ (nowy)NEW-55FX fallback 1.0 bez logu✅ (nowy)NEW-63Loan schedule O(M×(R+O))✅ (nowy)NEW-65Loan schedule unsafe DB assumptions✅ (nowy)NEW-66Budget service — brak amount/date guards✅ (nowy)NEW-69Polityka numeryczna — float/Decimal chaos✅ (nowy)NEW-70FX conversion zduplikowana w 4 serwisach✅ (nowy)PS-06Thread safety cache✅PS-07datetime.utcnow()✅PS-08fromtimestamp bez tz✅PS-10change_1y i długość historii✅TR-01Legacy cash seed i sub_portfolio_id=0✅TR-06validate_assign_payload różne typy✅TR-07O(days×transactions) w history✅PV-02legacy_row w get_cash_balance_on_date✅PV-03Metadata update tylko po MAX(id)✅PV-05_compute_cash_negative_days dzień-po-dniu✅PV-06N+1 queries w wycenie✅CT-03rebuild_holdings: ValueError dla nowego typu✅CT-04unconfirmed_conflicts w imporcie✅CT-05repair_portfolio_state nieczytelny call-site✅CT-10resolve_symbol_mapping — full table scan✅
🟢 Niski priorytet
IDProblemPrompt gotowyNEW-57Daty nie walidowane jako ISO na write✅ (nowy)NEW-58Migracje — except: pass bez klasyfikacji✅ (nowy)NEW-59Async recalculation — brak retry✅ (nowy)NEW-60Modified Dietz mid-period bias✅ (nowy)NEW-61Brak FX snapshot w transakcjach✅ (nowy)NEW-62avg_buy_fx_rate=1.0 dla non-PLN w imporcie✅ (nowy)NEW-67PPK — transakcja z oboma Units=0✅ (nowy)PS-09_latest_expected_market_day i święta✅PV-04Legacy sub_portfolio_id=0 warunki✅PV-07/08/09UTC + logger + docstring hygiene✅CT-06..CT-12Low-priority cleanup pakiet✅
```
