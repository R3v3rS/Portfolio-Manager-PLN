# Plan naprawy testów API (backend)

## Kontekst problemu

Występują dwa niezależne failujące testy regresyjne:

1. `test_all_registered_endpoints_follow_the_api_contract` — asercja porównuje **pełny zbiór tras Flaska** (`app.url_map`) z mapą `contract_request_builders`, ale mapa builderów nie została uzupełniona o nowe endpointy.
2. `test_critical_backend_smoke_endpoints` — krok sprzedaży (`POST /api/portfolio/sell`) zwraca `400` z komunikatem `Insufficient shares in parent portfolio` zamiast oczekiwanego `200`.

---

## Diagnoza 1: zgodność endpointów z kontraktem

### Co wiemy

Test kontraktowy buduje `expected_routes` z pełnego `app.url_map` (z wyłączeniem tylko `static`) i porównuje go 1:1 z kluczami `contract_request_builders`.

W aktualnym stanie brakuje builderów m.in. dla:

- `/api/portfolio/config` (GET)
- `/api/portfolio/ppk/performance/<int:portfolio_id>` (GET)
- `/api/portfolio/transactions/assign-bulk` (POST)
- `/api/portfolio/audit/consistency` (GET)
- `/monitoring` (GET)
- `/monitoring/stats` (GET)
- `/api/portfolio/transfer/cash` (POST)
- `/api/portfolio/transfer/cash/<string:transfer_id>` (DELETE)
- `/api/portfolio/<int:parent_id>/children` (POST)
- `/api/portfolio/<int:portfolio_id>/archive` (POST)
- `/api/portfolio/admin/price-history-audit` (GET)
- `/api/portfolio/jobs/<string:job_id>` (GET)
- `/api/portfolio/transactions/<int:transaction_id>/assign` (PUT)
- `/api/portfolio/allocation/<int:portfolio_id>` (GET)

### Wniosek

To jest przede wszystkim **problem utrzymania testu**, nie błąd runtime aplikacji: test ma założenie „100% endpointów musi mieć builder” i to założenie nie jest spełnione po rozbudowie API.

### Plan naprawczy

1. Rozszerzyć `build_contract_request_builders()` o brakujące trasy.
2. Dla endpointów wymagających danych przygotować fixture’y pomocnicze (np. transfer ID, transaction ID, child portfolio).
3. Dla endpointów administracyjnych/monitoringowych zdecydować politykę:
   - **wariant A (zalecany):** objąć je testem kontraktowym i dodać buildery,
   - **wariant B:** jawnie wykluczyć je z `expected_routes` (lista `excluded_routes`) i udokumentować dlaczego.
4. Dodać „guard rail”: test pomocniczy lub komentarz wymuszający aktualizację `contract_request_builders` przy każdym nowym `@route`.

---

## Diagnoza 2: smoke test sprzedaży (`/api/portfolio/sell`) zwraca 400

### Co wiemy

W scenariuszu smoke:

1. wykonywany jest poprawny zakup (`buy`, status 200),
2. następnie sprzedaż 1 sztuki zwraca błąd „Insufficient shares in parent portfolio”.

Lokalna reprodukcja pokazuje, że po `buy` rekord `holdings` ma `sub_portfolio_id = 0` (a nie `NULL`).

Następnie `sell_stock()` przy sprzedaży portfela głównego szuka rekordu warunkiem `sub_portfolio_id IS NULL`, więc nie znajduje świeżo kupionych walorów i rzuca `ValueError`.

### Przyczyna źródłowa

`routes_transactions.buy()` przekazuje `sub_portfolio_id=optional_number(data, 'sub_portfolio_id')`.

`optional_number()` ma domyślny `default=0.0`, więc brak pola w request body zamienia się na `0`, co jest semantycznie sprzeczne z logiką SQL opartą o `NULL` dla „parent portfolio”.

### Wniosek

Tutaj problem jest po stronie **kodu aplikacji**, a test smoke jest poprawny (odzwierciedla oczekiwany flow: buy -> sell bez sub-portfela).

### Plan naprawczy

1. Zmienić walidację pola `sub_portfolio_id` tak, aby brak pola mapował się na `None`/`NULL` (nie `0`).
   - opcja preferowana: dodać dedykowany parser `optional_positive_int(..., default=None)` dla identyfikatorów,
   - opcja minimalna: przy wywołaniu `optional_number(..., default=None)` i typowanie pod `int | None`.
2. Ujednolicić wszystkie endpointy używające `sub_portfolio_id` (buy/sell/dividend/deposit/withdraw/transfery), aby stosowały tę samą semantykę `None => parent`.
3. Dodać test regresyjny jednostkowy/integracyjny:
   - buy bez `sub_portfolio_id` zapisuje `NULL` w `holdings`,
   - sell bez `sub_portfolio_id` po buy zwraca 200.
4. Zweryfikować, czy istnieją historyczne rekordy z `sub_portfolio_id = 0`.
   - jeśli tak: przygotować migrację danych `0 -> NULL` dla tabel (`holdings`, potencjalnie `transactions`, `dividends`).

---

## Odpowiedź na pytanie „czy test jest zły, czy aplikacja?”

- `test_all_registered_endpoints_follow_the_api_contract`: **test jest niekompletny/stary względem obecnego API** (do aktualizacji).
- `test_critical_backend_smoke_endpoints` (krok sell): **kod aplikacji jest błędny semantycznie** (`0` zamiast `NULL` dla braku `sub_portfolio_id`).

---

## Proponowana kolejność prac

1. Naprawa semantyki `sub_portfolio_id` (`None` zamiast `0`) + test regresyjny sprzedaży.
2. Uzupełnienie `contract_request_builders` lub jawne wykluczenia tras (z decyzją architektoniczną).
3. Uruchomienie pełnego pakietu testów kontraktowych i smoke.
4. (Opcjonalnie) migracja danych `0 -> NULL` i smoke po migracji.

---

## Kryteria akceptacji

1. `backend/test_smoke_endpoints.py::BackendSmokeEndpointsTestCase::test_critical_backend_smoke_endpoints` przechodzi.
2. `backend/test_api_contract.py::ApiContractEndpointsTestCase::test_all_registered_endpoints_follow_the_api_contract` przechodzi.
3. Brak nowych regresji w testach walidacyjnych dla endpointów portfolio.
4. Dokumentacja kontraktu API zawiera jasną regułę: `sub_portfolio_id` jest opcjonalny, a brak wartości oznacza kontekst parent (`NULL` w DB).
