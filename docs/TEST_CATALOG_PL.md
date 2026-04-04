# Katalog testów (frontend + backend)

## Frontend

### `frontend/src/http.response.test.ts`
- `extractPayload returns payload and throws for invalid envelope` — waliduje rozpakowanie envelope `payload` i fallback dla błędnego kontraktu.
- `extractErrorMessage prefers message, then details and code` — sprawdza priorytet mapowania `error.message`/`error.details`/`error.code`.
- `extractErrorMessageFromUnknown handles body and plain errors` — normalizacja błędu z nieznanego źródła.
- `parseJsonApiResponse unwraps payload on success` — mapowanie odpowiedzi sukcesu.
- `parseJsonApiResponse sets error.body for non-2xx API errors` — zachowanie szczegółów envelope błędu.

### `frontend/src/http.test.ts`
- `serializes query params and skips undefined/null values` — serializacja query params i pomijanie pustych wartości.
- `sends JSON body by default and keeps explicit body for text requests` — poprawna struktura request body i nagłówków.
- `wraps parser errors into HttpError for status 400/401/403/404/409/422/500` — tabelaryczne pokrycie kodów błędów HTTP (`it.each`).
- `keeps AbortError for cancellation and does not remap into HttpError` — rozróżnienie anulowania requestu.
- `keeps network errors as-is when fetch rejects` — rozróżnienie błędu sieciowego.

### `frontend/src/api.test.ts`
- `normalizes list response with safe defaults` — bezpieczna normalizacja typów i fallbacków dla `portfolioApi.list`.
- `maps getPriceHistory with null->[] and nullable last_updated` — normalizacja `null → []` i pól opcjonalnych.
- `serializes optional benchmark query only when provided` — mapowanie opcjonalnego query parametru.
- `normalizeXtbImportError keeps error envelope shape for status 400/401/403/404/409/422/500` — tabelaryczne pokrycie propagacji `code/message/details` z `HttpError`.
- `sends importXtbCsv form data with optional fields only when provided` — struktura `FormData` i pomijanie nieustawionych pól opcjonalnych.

### `frontend/src/api_budget.test.ts`
- `maps budget summary and normalizes null arrays to []` — normalizacja typów, null-safe i fallback biznesowy.
- `omits optional query params when null/undefined for getTransactions` — mapowanie query i pomijanie pól opcjonalnych.
- `keeps HttpError shape for status 400/401/403/404/409/422/500` — tabelaryczne testy statusów błędów i spójny kształt obiektu błędu.

### `frontend/src/api_dashboard.test.ts`
- `maps numeric/string fields and falls back to zero/null defaults` — normalizacja dashboardu i fallback dla brakujących pól.

### `frontend/src/api_loans.test.ts`
- `maps getLoans response and falls back to empty array` — normalizacja listy kredytów.
- `serializes schedule query params and normalizes nested schedule shape` — mapowanie query i zagnieżdżonych struktur odpowiedzi.
- `sends createLoan body unchanged` — mapowanie payloadu requestu mutacyjnego.

### `frontend/src/api_radar.test.ts`
- `maps getAll with null-safe conversions and filters empty tickers` — normalizacja odpowiedzi i filtrowanie rekordów niepoprawnych.
- `maps action response with fallback message and ticker normalization` — fallback komunikatu i bezpieczne mapowanie tablicy tickerów.
- `maps analysis object safely when nested blocks are missing` — odporność na brak sekcji analitycznych.

### `frontend/src/api_symbol_map.test.ts`
- `normalizes list/create/update payloads` — mapowanie request/response dla CRUD mapowania symboli.

### `frontend/src/components/DuplicateConfirmationModal.test.tsx`
- `toggles selected conflicts and confirms selected hashes` — interakcja użytkownika (checkbox + potwierdzenie) i walidacja przekazywanych danych.
- `calls onCancel and allows skipping all duplicates` — scenariusz anulowania i potwierdzenia bez zaznaczeń.

### `frontend/src/components/Empty.test.tsx`
- `renders fallback empty state label` — smoke test renderowania komponentu UI.

### `frontend/src/pages/MainDashboard.test.tsx`
- `renders loading state before data is loaded` — weryfikuje stan ładowania dashboardu globalnego.
- `renders KPI cards, chart section and formatted values after successful load` — sprawdza render KPI, sekcji wykresu i formatowania kwot/dat po załadowaniu danych.
- `renders empty-style quick stat message when there is no upcoming installment` — scenariusz pustego stanu dla raty kredytu.
- `renders error state when API request fails` — scenariusz błędu API.

### `frontend/src/pages/PortfolioDashboard.test.tsx`
- `renders loading state before data fetch resolves` — stan ładowania przed resolve zapytań list/limits/config.
- `renders KPI cards, tax limits and table rows after loading` — render dashboardu portfeli, limitów podatkowych i tabeli.
- `renders empty state when no portfolios exist` — komunikat pustego stanu dla listy portfeli.
- `renders error state when dashboard fetch fails` — komunikat błędu pobierania danych.
- `submits create portfolio form and sends payload` — interakcja formularza tworzenia portfela i poprawny payload.

### `frontend/src/pages/PortfolioFlows.integration.test.tsx`
- `creates portfolio and refreshes list with new row` — integracyjny flow tworzenia portfela (request `POST /portfolio/create` + odświeżenie listy `GET /portfolio/list` i render nowego kafla).
- `shows create error feedback and keeps UI responsive` — obsługa błędu API przy tworzeniu portfela bez utraty interaktywności formularza.
- `sends BUY payload and updates holdings + summary cards` — flow BUY przez `PortfolioDetails` + modal transakcji, walidacja payloadu requestu i aktualizacji UI (holdings + gotówka).
- `displays API buy errors without crashing screen` — błąd BUY pokazany użytkownikowi i zachowanie stabilności widoku.
- `sends SELL payload and updates positions/profit in UI` — flow SELL z tabeli holdings, poprawny request i aktualizacja pozycji/summary.
- `shows SELL errors and keeps details page mounted` — obsługa błędu SELL bez wywrócenia widoku portfela.
- `posts transfer payload and updates both balances from API refresh` — transfer `Sub→Sub` z walidacją payloadu i poprawnym odświeżeniem danych.
- `shows transfer API errors and does not crash modal` — feedback błędu transferu oraz zachowanie modala.
- `handles successful CSV import flow` — import XTB CSV (scenariusz sukcesu) i feedback użytkownika.
- `renders partial import failure modal and allows user feedback` — częściowy sukces importu (konflikty/duplikaty) i render modalu konfliktów.
- `calls API with date/type/ticker filters and updates table rows` — filtrowanie historii transakcji po dacie/typie/tickerze z walidacją query params i wyników UI.
- `shows API errors during filtering but page remains usable` — obsługa błędu endpointu filtrowania bez utraty dostępności widoku.

### `frontend/src/components/modals/TransactionModal.test.tsx`
- `renders buy form fields for STANDARD portfolio and submits BUY transaction` — weryfikuje flow BUY, auto-prowizję FX i payload.
- `switches to dividend mode and submits dividend transaction` — przełączenie trybu oraz poprawny payload dla dywidendy.
- `handles API error with user feedback and reenables submit button` — obsługa błędu serwera i powrót przycisku do stanu aktywnego.

### `frontend/src/components/modals/SellModal.test.tsx`
- `renders prefilled sell form and submits SELL request` — prefill pól sprzedaży i poprawny payload SELL.
- `shows disabled state during request and handles server error` — blokada submita w trakcie requestu + feedback błędu.
- `returns null when modal is closed` — brak renderu przy `isOpen=false`.

### `frontend/src/components/modals/TransferModal.test.tsx`
- `submits DEPOSIT transaction` — poprawny payload wpłaty.
- `submits WITHDRAW to selected budget account` — wypłata na konto budżetowe z poprawnym wywołaniem API.
- `shows validation error for invalid internal transfer amount and does not call API` — walidacja kwoty dla przelewu wewnętrznego i brak requestu.
- `shows processing status for successful internal transfer job` — status przeliczania historii po transferze `Sub→Sub`.

## Backend — testy API, serwisów i regresji

Poniżej pełna lista aktualnych plików testowych backendu wraz z krótką adnotacją.

### `backend/test_api_contract.py`
- `test_all_registered_endpoints_follow_the_api_contract` — sprawdza kontrakt odpowiedzi dla zarejestrowanych endpointów (envelope `payload`/`error`, spójność pól błędu i typów odpowiedzi).

### `backend/test_monitoring_dashboard.py`
- `test_empty_log_file_returns_zeroed_metrics` — weryfikuje, że pusty log daje zerowe metryki.
- `test_mixed_entries_compute_expected_metrics` — sprawdza poprawność agregacji metryk dla mieszanych wpisów (błędy, wolne operacje, error rate).
- `test_old_entries_do_not_affect_last_hour_metrics` — potwierdza, że stare wpisy nie wpływają na metryki „ostatniej godziny”.
- `test_identical_durations_do_not_crash_heap_sorting` — regresja: sortowanie wolnych operacji działa stabilnie przy identycznych czasach.

### `backend/test_portfolio_import_service.py`
- `test_try_parse_float_supports_common_import_formats` — test parsera liczb dla formatów importowych (np. przecinki/spacje).
- `test_select_column_prefers_numeric_candidate_for_amount` — wybór kolumny preferuje dane numeryczne dla pól kwot.
- `test_parse_xtb_quantity_standard_format` — parsowanie ilości z komentarza XTB (format standardowy).
- `test_parse_xtb_quantity_fractional_close_uses_numerator_only` — parsowanie pozycji częściowo zamykanej (ułamek).
- `test_parse_xtb_quantity_handles_spaces_and_commas` — odporność parsera na niestandardowe odstępy i separatory.
- `test_parse_xtb_quantity_raises_for_invalid_comment` — walidacja błędu dla niepoprawnego komentarza XTB.

### `backend/test_price_service_logging.py`
- `test_verbose_provider_logs_flag_parsing` — parsowanie flagi środowiskowej `VERBOSE_PROVIDER_LOGS`.
- `test_log_verbose_provider_event_respects_flag` — logi verbose są emitowane tylko przy aktywnej fladze.
- `test_error_aggregation_reduces_log_flood_when_not_verbose` — agregacja błędów ogranicza „flood” logów.
- `test_log_provider_event_includes_contract_fields_for_error` — sprawdza kompletność i strukturę pól logu błędu.
- `test_log_provider_event_accepts_optional_none_fields` — logowanie toleruje opcjonalne pola `None`.
- `test_log_provider_event_respects_explicit_log_levels` — poziom logowania respektuje przekazany level.
- `test_warmup_cache_excludes_cash_and_null_tickers_from_query` — warmup cache pomija tickery `CASH`/`NULL`.
- `test_classify_error_known_and_unknown_paths` — klasyfikacja znanych i nieznanych błędów providera.

### `backend/test_price_service_scenarios.py`
- `test_scenario_success_bulk_download` — scenariusz pełnego sukcesu pobierania cen.
- `test_scenario_retry_then_success` — retry kończy się sukcesem.
- `test_scenario_retry_then_final_failure` — retry kończy się finalnym błędem.
- `test_scenario_fallback_activation` — uruchomienie fallbacku po awarii ścieżki głównej.
- `test_scenario_partial_success_in_fallback` — fallback zwraca częściowy sukces.
- `test_get_stock_analysis_sets_rsi14_to_none_when_loss_is_zero` — poprawna obsługa RSI przy zerowej stracie.
- `test_sync_stock_history_logs_upserted_rows_message` — logowanie komunikatu o upsertowanych wierszach historii.

### `backend/test_smoke_endpoints.py`
- `test_critical_backend_smoke_endpoints` — smoke test kluczowych endpointów backendu.
- `test_invalid_buy_payload_returns_validation_error` — walidacja błędnego payloadu dla BUY.
- `test_invalid_sell_payload_returns_validation_error` — walidacja błędnego payloadu dla SELL.
- `test_avg_price_stability_after_sell` — regresja stabilności `average_buy_price` po częściowym SELL (BUY 5 @ 100, SELL 1, oczekiwane avg=100).
- `test_tax_limits_does_not_count_ikze_portfolios_as_ike` — poprawna logika limitów podatkowych IKE/IKZE.
- `test_invalid_budget_transfer_payload_returns_validation_error` — walidacja niepoprawnego transferu budżetowego.
- `test_missing_budget_transfer_field_returns_validation_error` — brak wymaganych pól zwraca błąd walidacji.
- `test_loan_schedule_rejects_invalid_simulation_inputs` — odrzucanie niepoprawnych danych symulacji kredytu.
- `test_loan_mutations_validate_positive_amounts_and_missing_loans` — walidacja kwot i brakujących rekordów kredytu.
- `test_xtb_import_missing_symbols_returns_consistent_error_details` — spójny format błędów importu XTB (brak symboli).
- `test_xtb_import_invalid_csv_returns_consistent_error_details` — spójny format błędów dla wadliwego CSV.
- `test_global_error_handlers_preserve_contract_and_status_codes` — globalne handlery błędów zachowują kontrakt i statusy.

### `tests/test_assign_integration.py`
- `test_assign_parent_to_child_changes_only_sub_portfolio` — przypisanie parent→child zmienia wyłącznie `sub_portfolio_id`.
- `test_assign_child_to_parent_changes_only_sub_portfolio` — przypisanie child→parent aktualizuje tylko pole przypisania.
- `test_assign_child_a_to_child_b_changes_only_sub_portfolio` — przepięcie child A→child B nie modyfikuje innych danych transakcji.
- `test_assign_to_child_of_different_parent_returns_422` — blokada przypisania do dziecka innego parenta.
- `test_assign_to_archived_child_returns_422` — blokada przypisania do archiwalnego sub-portfela.
- `test_assign_interest_to_child_returns_422` — walidacja: `INTEREST` nie może być przypisany do child.
- `test_bulk_assign_with_interest_in_set_returns_422_and_is_atomic` — bulk z niedozwoloną transakcją kończy się 422 i rollbackiem.
- `test_bulk_assign_cross_parent_returns_422` — bulk przypisania cross-parent jest odrzucany.
- `test_assign_single_rebuilds_parent_and_children_with_correct_argument_order` — po assign single odświeżanie struktur parent/children wywoływane poprawnie.
- `test_assign_bulk_rebuilds_parent_and_children_with_correct_argument_order` — analogiczna weryfikacja dla assign bulk.

### `tests/test_assign_validation.py`
- `test_assign_transaction_rejects_invalid_sub_portfolio_id` — endpoint assign odrzuca nieprawidłowe ID sub-portfela.
- `test_assign_transactions_bulk_rejects_invalid_sub_portfolio_id` — bulk assign odrzuca niepoprawny sub-portfolio.
- `test_assign_transactions_bulk_rejects_invalid_transaction_ids` — bulk assign waliduje listę ID transakcji.

### `tests/test_audit_cash_negative.py`
- `test_portfolio_without_incidents_returns_ok_true_and_empty_incidents` — brak incydentów przy poprawnym cashflow.
- `test_withdraw_above_balance_creates_incident_with_correct_date_and_amount` — wykrywanie dnia z ujemną gotówką po nadmiernej wypłacie.
- `test_buy_can_trigger_negative_balance` — zakup może wygenerować incydent ujemnego salda.
- `test_later_deposit_repairs_balance_but_incident_day_remains_visible` — późniejszy depozyt naprawia saldo, ale historia incydentu pozostaje.
- `test_child_is_checked_separately_and_parent_stays_clean` — niezależne audytowanie child i parent.
- `test_dividend_counts_as_credit_and_prevents_negative_balance` — dywidenda jako wpływ zapobiega zejściu poniżej zera.

### `tests/test_audit_consistency.py`
- `test_portfolio_ok_returns_status_ok` — audyt spójności zwraca status OK dla poprawnych danych.
- `test_value_match_fail_when_parent_value_differs` — wykrywanie rozjazdu wartości parenta.
- `test_orphan_transaction_detected` — detekcja osieroconych transakcji.
- `test_interest_leaked_detected` — wykrywanie „wycieku” transakcji typu INTEREST.
- `test_archived_child_transaction_detected` — detekcja transakcji przypisanych do archiwalnego child.

### `tests/test_cash_transfer.py`
- `test_01_child_to_child_same_parent` — transfer child→child w obrębie jednego parenta.
- `test_02_child_to_parent` — transfer child→parent.
- `test_03_parent_to_child` — transfer parent→child.
- `test_04_child_to_child_different_parents_returns_422` — blokada transferu między różnymi parentami.
- `test_05_parent_to_other_parent_returns_422` — blokada transferu parent→inny parent.
- `test_06_archived_child_as_source_returns_422` — archiwalny child nie może być źródłem transferu.
- `test_07_archived_child_as_target_returns_422` — archiwalny child nie może być celem transferu.
- `test_08_insufficient_cash_returns_422` — walidacja niewystarczającej gotówki.
- `test_09_future_date_returns_422` — walidacja daty z przyszłości.
- `test_10_delete_transfer_restores_cash_and_deletes_transactions` — usunięcie transferu cofa wpływ na cash i usuwa transakcje.
- `test_11_delete_non_existing_transfer_returns_422` — usunięcie nieistniejącego transferu zwraca 422.
- `test_12_backdated_transfer_uses_historical_cash_balance` — transfer wsteczny używa historycznego salda.
- `test_13_backdated_transfer_repairs_cash_state_instead_of_only_applying_delta` — backdated transfer naprawia stan gotówki globalnie, nie tylko delta.

### `tests/test_clear_subportfolio.py`
- `test_clear_child_portfolio_returns_422` — blokada „clear” dla child portfolio.
- `test_clear_parent_with_active_children_returns_422` — blokada „clear” parenta z aktywnymi dziećmi.
- `test_clear_parent_without_active_children_keeps_existing_behavior` — parent bez aktywnych dzieci zachowuje obecne działanie endpointu clear.

### `tests/test_config_endpoint.py`
- `test_config_returns_allowed_subportfolio_types_from_constants` — endpoint config zwraca typy sub-portfeli zgodne ze stałymi backendu.

### `tests/test_dividends_subportfolio.py`
- `test_get_dividends_for_child_uses_parent_and_child_filter` — dywidendy child filtrowane przez parent + child.
- `test_get_dividends_for_parent_returns_own_and_children_with_subportfolio_name` — parent widzi własne i child dywidendy z nazwami sub-portfeli.
- `test_get_monthly_dividends_for_parent_and_child` — miesięczne agregacje dywidend dla parenta i child.

### `tests/test_portfolio_history_service.py`
- `test_build_price_context_logs_sync_errors_and_continues` — budowa kontekstu cen loguje błędy synchronizacji i kontynuuje.
- `test_daily_history_matches_legacy_algorithm` — zgodność dziennej historii z algorytmem legacy.
- `test_monthly_history_rolling_matches_legacy_invariants` — zgodność rolling monthly z niezmiennikami legacy.
- `test_benchmark_shows_operation_reduction` — benchmark: redukcja liczby operacji w nowym podejściu.
- `test_long_sparse_daily_history` — poprawność dla długiej i rzadkiej historii dziennej.
- `test_multi_ticker_daily_runs_and_returns_points` — wielotickerowa historia dzienna zwraca poprawne punkty.
- `test_fx_consistency_uses_latest_rate_without_future_leakage` — kurs FX bez „wycieku” danych z przyszłości.
- `test_buy_before_window_sell_inside_window` — poprawna wycena przy BUY przed oknem i SELL w oknie.
- `test_daily_accepts_row_like_transactions_without_get` — kompatybilność wejścia row-like bez metody `get`.

### `tests/test_portfolio_trade_bulk_atomicity.py`
- `test_assign_transactions_bulk_rolls_back_entire_batch_on_error` — atomowość bulk assign: błąd cofa cały batch.

### `tests/test_regression_subportfolio_id.py`
- `test_buy_sell_without_sub_portfolio_id_uses_null` — regresja: brak `sub_portfolio_id` zapisuje `NULL`.
- `test_buy_with_explicit_null_sub_portfolio_id_uses_null` — regresja: jawne `null` także pozostaje `NULL`.

### `tests/test_transactions_subportfolio.py`
- `test_transactions_endpoint_parent_and_child_scope` — zakres endpointu transakcji dla parent/child.
- `test_holdings_endpoint_parent_and_child_scope` — zakres endpointu holdings dla parent/child.
- `test_history_monthly_endpoint_parent_and_child_scope` — zakres endpointu historii miesięcznej dla parent/child.
- `test_closed_positions_endpoint_parent_and_child_scope` — zakres endpointu closed positions dla parent/child.

### `tests/test_withdraw_validation.py`
- `test_withdraw_without_subportfolio_happy_path` — poprawna wypłata bez wskazania child.
- `test_withdraw_with_valid_subportfolio_happy_path` — poprawna wypłata z prawidłowym child.
- `test_withdraw_with_subportfolio_from_different_parent_returns_422` — blokada wypłaty dla child z innego parenta.
- `test_withdraw_with_archived_subportfolio_returns_422` — blokada wypłaty z archiwalnego child.
- `test_withdraw_with_non_existing_subportfolio_returns_422` — walidacja dla nieistniejącego child.

### `tests/test_xirr.py`
- `XirrRegressionTests.test_mixed_date_and_datetime` — regresja: `xirr` działa dla mieszanki `date` i `datetime`.
- `test_amount_nan` — `xirr` odrzuca `NaN` w kwotach.
- `test_amount_inf` — `xirr` odrzuca `inf` w kwotach.
- `test_guess_nan` — `xirr` odrzuca `NaN` w parametrze guess.
- `test_guess_bool` — `xirr` odrzuca bool jako guess.

---

## Brakujące testy, które warto dodać

Poniżej lista rekomendowanych braków testowych (priorytetyzowana), żeby domknąć najważniejsze ryzyka.

### Frontend (największa luka)

1. **Testy jednostkowe API clientów** (`frontend/src/api*.ts`)
   - Co sprawdzać: mapowanie payloadów request/response, obsługę kodów błędów, normalizację danych i fallbacki.
2. **Testy komponentów React** (`frontend/src/**/*.tsx`)
   - Co sprawdzać: rendering sekcji dashboard/portfolio, stany loading/empty/error, formatowanie kwot/dat.
3. **Testy integracyjne UI + mock API**
   - Co sprawdzać: kluczowe flow użytkownika (dodanie portfela, BUY/SELL, transfery, import, filtrowanie historii).
4. **E2E smoke dla krytycznych ścieżek**
   - Co sprawdzać: uruchomienie aplikacji i przejście 2–3 najważniejszych scenariuszy end-to-end.

### Backend — luki funkcjonalne

1. **Idempotencja endpointów mutujących**
   - Co dodać: testy ponowienia tego samego requestu (np. retry po timeout) bez podwójnych skutków.
2. **Testy współbieżności (race conditions)**
   - Co dodać: równoległe BUY/SELL/TRANSFER na tym samym portfelu i walidacja spójności sald/holdings.
3. **Testy uprawnień i separacji danych**
   - Co dodać: scenariusze multi-user/tenant (brak odczytu i modyfikacji cudzych danych).
4. **Kontrakt błędów dla wszystkich routerów**
   - Co dodać: parametrized tests wymuszające stały format `error.code/message/details` dla pełnej mapy endpointów.
5. **Testy graniczne walidacji wejścia**
   - Co dodać: skrajne wartości `quantity/price/amount`, bardzo długie stringi, nietypowe locale/formaty dat.

### Backend — historia, wycena, import

1. **Testy wydajnościowe na większych wolumenach danych**
   - Co dodać: benchmarki historii/wyceny dla dużej liczby transakcji i tickerów.
2. **Testy jakości danych cenowych**
   - Co dodać: luki w notowaniach, duplikaty, split/reverse split, niespójne waluty.
3. **Testy importu dla większej liczby brokerów i wariantów plików**
   - Co dodać: dodatkowe formaty CSV/XLSX, uszkodzone nagłówki, kodowania, nietypowe separatory.
4. **Testy odporności na chwilową niedostępność providerów**
   - Co dodać: dłuższe serie retry/fallback + powrót do ścieżki głównej po odzyskaniu API.

### API contract / dokumentacja

1. **Snapshoty odpowiedzi OpenAPI vs runtime**
   - Co dodać: automatyczne porównanie faktycznych odpowiedzi endpointów z `docs/openapi.yaml`.
2. **Testy kompatybilności wstecznej**
   - Co dodać: ochrona przed „breaking changes” w polach payloadów używanych przez frontend.

### Priorytet wdrożenia (proponowany)

1. Frontend unit + component tests (najpierw krytyczne widoki i API clienty).
2. Backend concurrency + idempotencja dla operacji finansowych.
3. Rozszerzenie contract/error tests na pełną mapę endpointów.
4. E2E smoke (minimum) i testy wydajnościowe historii/wyceny.

## Uzupełnienie: szczegółowy plan testów frontend (do dopisania na końcu backlogu QA)

Poniżej rozpiska „co dokładnie testować” dla obszarów wskazanych jako największa luka. Sekcja może być użyta 1:1 jako checklista do implementacji testów.

### 1) Testy jednostkowe API clientów (`frontend/src/api*.ts`)

**Zakres**
- `api.ts`, `api_budget.ts`, `api_dashboard.ts`, `api_loans.ts`, `api_radar.ts`, `api_symbol_map.ts`, `api-contract.ts`, `http.ts`, `http/response.ts`.

**Scenariusze obowiązkowe**
- Mapowanie requestów:
  - poprawne nazwy pól, typy, wartości domyślne i serializacja query params/body.
  - brak wysyłki pól opcjonalnych, gdy `undefined/null` (jeśli kontrakt tego wymaga).
- Mapowanie response:
  - transformacja envelope (`payload`/`error`) do wewnętrznych typów frontendu.
  - poprawna obsługa pól opcjonalnych i wartości brakujących.
- Obsługa błędów HTTP:
  - 400/401/403/404/409/422/500 — mapowanie na spójny obiekt błędu UI.
  - poprawna propagacja `error.code`, `error.message`, `error.details`.
- Normalizacja i fallbacki:
  - normalizacja pustych list (`null -> []`), wartości liczbowych (`string -> number`, jeśli stosowane),
  - fallback dla brakujących danych (np. placeholdery, wartości 0 tylko tam, gdzie to bezpieczne biznesowo).
- Anulowanie/timeouty (jeśli wspierane):
  - poprawne odróżnienie błędu sieci od anulowania żądania.

**Narzędzia / podejście**
- Vitest/Jest + mock warstwy HTTP (`fetch`/axios).
- Testy tabelaryczne (`it.each`) dla kodów błędów i wariantów payloadu.

### 2) Testy komponentów React (`frontend/src/**/*.tsx`)

**Priorytetowe widoki/komponenty**
- Strony dashboard i portfolio: `MainDashboard.tsx`, `PortfolioDashboard.tsx`, `PortfolioDetails.tsx`, `PortfolioList.tsx`, `Home.tsx`, `Transactions.tsx`.
- Modale transakcyjne: BUY/SELL/TRANSFER (`TransactionModal.tsx`, `SellModal.tsx`, `TransferModal.tsx`).
- Kluczowe sekcje wizualne/metryki: wykresy i panele analityczne.

**Scenariusze obowiązkowe**
- Rendering danych:
  - wyświetlenie sekcji i kluczowych KPI po poprawnym fetchu.
- Stany aplikacyjne:
  - `loading` (skeleton/spinner),
  - `empty` (brak danych),
  - `error` (komunikat i/lub retry action).
- Formatowanie:
  - kwoty (waluta, separatory tysięcy, liczba miejsc po przecinku),
  - daty (lokalizacja i format spójny z wymaganiami UI).
- Interakcje:
  - submit formularzy, walidacje pól, disabled state przy żądaniu,
  - komunikaty błędów walidacyjnych i serwerowych.

**Narzędzia / podejście**
- React Testing Library + `user-event`.
- Asercje po roli i tekście (`getByRole`, `findByText`) zamiast selektorów implementacyjnych.

### 3) Testy integracyjne UI + mock API

**Cel**
Weryfikacja krytycznych flow użytkownika na poziomie kilku komponentów naraz, z mockowanym backendem.

**Flow krytyczne (minimum)**
- Dodanie portfela i jego pojawienie się na liście.
- Dodanie transakcji BUY i wpływ na widok holdings/summary.
- Dodanie transakcji SELL i aktualizacja zysku/pozycji.
- Transfer środków i poprawna zmiana sald po obu stronach.
- Import transakcji (scenariusz sukcesu + scenariusz częściowego błędu).
- Filtrowanie historii transakcji (zakres dat/typ transakcji/ticker).

**Co asercjami potwierdzać**
- Że UI wysyła poprawny request (payload + endpoint).
- Że po odpowiedzi backendu odświeżają się właściwe sekcje i liczby.
- Że błędy API są komunikowane użytkownikowi bez „rozsypania” widoku.

### 4) E2E smoke dla krytycznych ścieżek

**Zakres minimalny (2–3 scenariusze)**
1. Start aplikacji + wejście na dashboard + poprawne załadowanie danych startowych.
2. Utworzenie portfela -> BUY -> SELL (prosty pełny cykl transakcyjny).
3. Transfer / import + weryfikacja, że historia i podsumowanie się aktualizują.

**Wymagania smoke**
- Testy krótkie, stabilne i uruchamiane na każdym CI (PR + main).
- Stabilizacja przez deterministic fixtures oraz kontrolę czasu (mock daty), gdy wpływa na wyniki.

**Status wdrożenia (backend E2E smoke API)**
- Scenariusz 1: start aplikacji + dashboard + załadowanie danych startowych  
  `backend/test_smoke_endpoints.py::test_e2e_smoke_bootstrap_dashboard_and_seed_data`
- Scenariusz 2: utworzenie portfela -> BUY -> SELL  
  `backend/test_smoke_endpoints.py::test_e2e_smoke_create_portfolio_buy_sell_cycle`
- Scenariusz 3: transfer środków + weryfikacja historii i podsumowania  
  `backend/test_smoke_endpoints.py::test_e2e_smoke_transfer_updates_history_and_summary`

**Deterministyczność**
- Wszystkie scenariusze używają jawnych dat transakcji (`2026-03-02` ... `2026-03-05`).
- Dashboard smoke ma zamrożoną datę przez patch `routes_dashboard.date` (kontrola czasu w asercjach summary).

**Uruchamianie w CI (krótki pakiet smoke)**
- `python -m unittest backend.test_smoke_endpoints.BackendSmokeEndpointsTestCase.test_e2e_smoke_bootstrap_dashboard_and_seed_data`
- `python -m unittest backend.test_smoke_endpoints.BackendSmokeEndpointsTestCase.test_e2e_smoke_create_portfolio_buy_sell_cycle`
- `python -m unittest backend.test_smoke_endpoints.BackendSmokeEndpointsTestCase.test_e2e_smoke_transfer_updates_history_and_summary`
- lub cały plik: `python -m unittest backend/test_smoke_endpoints.py`

---

## Proponowana kolejność wdrożenia (frontend)

1. API client unit tests (najtańsze i najszybsze wykrywanie regresji kontraktu).
2. Testy komponentów dla ekranów portfolio/dashboard + modali transakcyjnych.
3. Integracyjne flow UI + mock API dla BUY/SELL/TRANSFER/importu.
4. Krótki pakiet E2E smoke (2–3 scenariusze) odpalany w CI.
