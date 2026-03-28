# AUDIT + plan wdrożenia transferu transakcji i pozycji między parent portfolio a sub-portfolio

Data: 2026-03-28  
Status: **plan implementacyjny (do wykonania przez agenta krok po kroku)**

## 1) Cel i zakres

Celem jest bezpieczne wdrożenie **przenoszenia transakcji** pomiędzy:
- parent portfolio (`sub_portfolio_id = NULL`),
- child sub-portfolio (`sub_portfolio_id = <child_id>`),
- child → child (w obrębie tego samego parenta).

> Kluczowa zasada: źródłem prawdy przypisania jest wyłącznie `transactions.sub_portfolio_id`.

W tym planie „transfer pozycji” oznacza:
1. zmianę przypisania transakcji,
2. automatyczne odtworzenie holdings i historii po transferze,
3. spójną prezentację wyniku w parent i child.

## 2) Kontekst projektowy (skrót dla agenta)

Na podstawie istniejących dokumentów:
- API działa pod prefiksem `/api/portfolio/...`.
- Backend: Flask + sqlite3.
- Frontend: React + TypeScript + wspólny klient API.
- Sub-portfele mają być dostępne tylko dla `IKE` i `STANDARD`.
- Child nie może mieć dzieci (głębokość drzewa = 1).
- Parent nie może być usunięty, child ma być archiwizowany.

## 3) Decyzje domenowe (finalne dla transferu)

1. **Transfer nie edytuje ekonomii transakcji**: nie zmieniamy `price`, `quantity`, `date`, `commission`.
2. **Transfer zmienia tylko przypisanie**: aktualizujemy tylko `sub_portfolio_id`.
3. **`portfolio_id` pozostaje parentem** dla każdej transakcji.
4. **Holdings są wynikiem transakcji**, nie niezależnym bytem do „ręcznego przenoszenia”.
5. **Po transferze uruchamiamy przeliczenie historii asynchronicznie** (job idempotentny).
6. **Zarchiwizowany child nie może być celem transferu** (422).
7. **Transfer między różnymi parentami jest zabroniony** (422).

## 4) Zakres techniczny (MVP)

## 4.1 Baza danych

Wymagane pola/założenia:
- `transactions.sub_portfolio_id` (nullable, FK do `portfolios.id`).
- `holdings.sub_portfolio_id` (nullable, FK do `portfolios.id`).
- unikalność holdings: `(portfolio_id, sub_portfolio_id, ticker)`.
- `portfolios.parent_portfolio_id`, `portfolios.is_archived`.

Checklist:
- [ ] migracje idempotentne (bezpieczne wielokrotne uruchomienie),
- [ ] dane legacy ustawione na `sub_portfolio_id = NULL`,
- [ ] walidacja spójności FK po migracji.

## 4.2 Endpointy backend (MVP)

1. `PUT /api/portfolio/transactions/<transaction_id>/assign`
   - Body: `{ "target_sub_portfolio_id": number | null }`
   - Działanie: przypisanie 1 transakcji do parent (`null`) lub child (`id`).

2. `POST /api/portfolio/transactions/assign-bulk`
   - Body: `{ "transaction_ids": number[], "target_sub_portfolio_id": number | null }`
   - Działanie: przypisanie wsadowe.

3. `GET /api/portfolio/jobs/<job_id>`
   - Działanie: status przeliczenia historii.

## 4.3 Walidacje backend (konieczne)

Dla każdego transferu:
- [ ] transakcja istnieje,
- [ ] `target_sub_portfolio_id` istnieje albo `null`,
- [ ] target child należy do tego samego parenta co transakcja,
- [ ] target child nie jest zarchiwizowany,
- [ ] transakcja typu `INTEREST` może mieć wyłącznie `sub_portfolio_id = NULL`,
- [ ] operacja jest idempotentna (jeśli przypisanie już jest takie samo, zwróć 200 z no-op).

Kody odpowiedzi:
- 200: sukces/no-op,
- 202: sukces + uruchomiony job,
- 404: brak transakcji lub portfolio,
- 422: naruszenie reguł domenowych.

## 4.4 Przeliczenie po transferze

Po zatwierdzeniu transferu:
1. Zapis zmiany `sub_portfolio_id` (transakcja DB).
2. Uruchomienie joba async:
   - odtworzenie holdings parenta i childów dla dotkniętych portfeli,
   - przeliczenie historii miesięcznej dla parenta i dotkniętych childów,
   - odświeżenie KPI.
3. Zwrócenie `job_id` do frontendu.

Uwaga: jeżeli system nie ma trwałej kolejki, użyć in-memory job registry + polling.

## 5) Plan realizacji dla agenta (kolejność prac)

## Etap A — przygotowanie
- [ ] wykonać backup DB,
- [ ] dopisać/uzupełnić migracje,
- [ ] dodać testy jednostkowe walidacji transferu.

## Etap B — backend assign API
- [ ] zaimplementować endpoint single assign,
- [ ] zaimplementować endpoint bulk assign,
- [ ] dodać wspólną funkcję walidującą (`validate_transfer_target(...)`).

## Etap C — recalculation engine
- [ ] dodać job registry (`queued/running/done/failed`),
- [ ] dodać worker przeliczenia holdings + historii,
- [ ] podpiąć polling endpoint job status.

## Etap D — frontend
- [ ] dodać selector target portfolio (parent + aktywne childy),
- [ ] dodać akcję pojedynczą i wsadową,
- [ ] dodać polling joba + komunikaty stanu,
- [ ] zablokować wybór zarchiwizowanych childów.

## Etap E — testy i rollout
- [ ] testy kontraktu API (single/bulk/no-op/422/404),
- [ ] testy E2E: parent→child, child→parent, child→child,
- [ ] test regresji importu XTB,
- [ ] rollout za feature flagą.

## 6) Definition of Done (DoD)

Funkcję uznajemy za gotową gdy:
- [ ] transfer transakcji działa w 3 kierunkach (parent↔child, child↔child),
- [ ] holdings po transferze są poprawne i bez duplikatów,
- [ ] historia i KPI parent/child odświeżają się po zakończeniu joba,
- [ ] `INTEREST` nie może być przypięty do childa,
- [ ] brak regresji endpointów `/api/portfolio/...` i importu XTB,
- [ ] frontend jasno komunikuje „przeliczanie w toku”.

## 7) Ryzyka + mitigacje

1. **Niespójne holdings po błędzie w jobie**
   - Mitigacja: retry idempotentny + audyt spójności po jobie.

2. **Długi czas przeliczenia dla dużych danych**
   - Mitigacja: batchowanie oraz metryka czasu joba.

3. **Regresja importu XTB**
   - Mitigacja: osobne testy regresji i fixture z realnymi przypadkami BUY/SELL/INTEREST/DIVIDEND.

## 8) Po MVP (opcjonalnie)

- reguły automatycznego przypisywania po tickerze po imporcie,
- partial transfer pozycji (split lotów przez kreator transakcji technicznych),
- trwały job store (np. Redis/Postgres) zamiast in-memory.

