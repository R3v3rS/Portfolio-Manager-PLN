# Architektura aplikacji – jak działa backend, frontend i połączenia między plikami

Ten dokument opisuje **praktyczny przepływ działania aplikacji**: od uruchomienia frontendu i backendu, przez routing, aż po zapis i odczyt danych z bazy.

---

## 1. Obraz całości

Projekt jest podzielony na dwa główne obszary:

- `frontend/` – interfejs użytkownika napisany w **React + TypeScript + Vite**,
- `backend/` – API napisane w **Flask + SQLite**.

Przepływ wygląda tak:

1. Użytkownik otwiera widok w przeglądarce.
2. Router React wybiera odpowiednią stronę.
3. Komponent strony wywołuje funkcję z warstwy API (`api.ts`, `api_budget.ts`, `api_loans.ts`, `api_symbol_map.ts`) albo bezpośrednio `fetch`/`axios`.
4. Żądanie trafia do odpowiedniego endpointu Flask, np. `/api/portfolio/list` albo `/api/dashboard/global-summary`.
5. Plik `routes*.py` przyjmuje request HTTP i deleguje logikę do serwisu domenowego (`*_service.py`).
6. Serwis wykonuje obliczenia, odczytuje/zapisuje dane przez `database.py`, a czasem pobiera ceny rynkowe przez `price_service.py`.
7. Backend zwraca JSON.
8. Frontend zapisuje dane w stanie komponentu (`useState`) i renderuje UI.

---

## 2. Backend – punkt wejścia i rejestracja modułów

### 2.1 `backend/app.py`

To jest główny punkt startowy backendu.

Plik robi kilka kluczowych rzeczy:

- tworzy aplikację Flask,
- włącza globalne CORS,
- ustawia ścieżkę do pliku SQLite `portfolio.db`,
- uruchamia inicjalizację bazy przez `init_db(app)`,
- wykonuje warmup cache cen przez `PriceService.warmup_cache()`,
- rejestruje blueprinty API,
- dodaje globalny handler wyjątków,
- wystawia prosty health check pod `/`.

### 2.2 Jakie blueprinty są podpinane

W `app.py` backend rejestruje następujące grupy endpointów:

- `portfolio_bp` pod `/api/portfolio`,
- `loans_bp` pod `/api/loans`,
- `budget_bp` pod `/api/budget`,
- `dashboard_bp` pod `/api/dashboard`,
- `radar_bp` pod `/api/radar`,
- `symbol_map_bp` pod `/api/symbol-map`.

To oznacza, że pliki `routes*.py` nie są samodzielnym serwerem – są modułami HTTP podpinanymi do jednej aplikacji Flask.

---

## 3. Backend – warstwy odpowiedzialności

Backend ma prosty, czytelny podział odpowiedzialności:

### 3.1 Warstwa HTTP – `routes*.py`

Pliki routingu odpowiadają za:

- przyjęcie parametrów z URL, query string i JSON body,
- walidację podstawowych pól,
- wywołanie właściwego serwisu,
- zwrócenie odpowiedzi JSON i kodu HTTP.

Ta warstwa **nie powinna zawierać ciężkiej logiki biznesowej** – i w większości projektu faktycznie deleguje ją do serwisów.

### 3.2 Warstwa biznesowa – `*_service.py`

To tutaj dzieją się właściwe operacje domenowe:

- obliczanie wartości portfela,
- kupno i sprzedaż aktywów,
- import CSV z XTB,
- wyliczanie harmonogramu kredytu,
- operacje budżetowe na kontach i kopertach,
- obsługa watchlisty i cen rynkowych,
- logika PPK.

### 3.3 Warstwa danych – `database.py`

Ten plik odpowiada za:

- otwieranie połączenia SQLite w kontekście requestu,
- ustawienie `row_factory`, żeby rekordy były czytelne jak słowniki,
- zamykanie połączenia po zakończeniu requestu,
- tworzenie tabel i indeksów przy starcie aplikacji.

---

## 4. Backend – baza danych i relacje między tabelami

`backend/database.py` tworzy większość schematu aplikacji. Najważniejsze obszary danych to:

### 4.1 Inwestycje

- `portfolios` – portfele inwestycyjne,
- `transactions` – historia operacji (BUY, SELL, DEPOSIT, WITHDRAW, DIVIDEND, INTEREST),
- `holdings` – aktualne pozycje w portfelu,
- `dividends` – dywidendy,
- `bonds` – obligacje,
- `stock_prices` – historia cen,
- `price_cache` – cache bieżących cen,
- `asset_metadata` – dane opisowe spółek/instrumentów,
- `symbol_mappings` – mapowanie symboli importowanych z CSV na tickery aplikacyjne.

### 4.2 Radar i obserwowane instrumenty

- `watchlist` – lista obserwowanych tickerów,
- `radar_cache` – snapshot danych radaru, żeby nie pobierać wszystkiego za każdym razem.

### 4.3 Kredyty

- `loans` – kredyty,
- `loan_rates` – historia zmian oprocentowania,
- `loan_overpayments` – nadpłaty.

### 4.4 Budżet

W dalszej części `database.py` są też tabele budżetowe, np.:

- `budget_accounts`,
- `envelopes`,
- `envelope_categories`,
- tabele transakcyjne i pomocnicze dla logiki kopert.

### 4.5 PPK

- `ppk_portfolios`,
- `ppk_transactions`.

Ważna obserwacja: projekt nie ma osobnej warstwy ORM. Zamiast tego serwisy wykonują bezpośrednie zapytania SQL przez `sqlite3` i `get_db()`.

---

## 5. Główne moduły backendu

## 5.1 Moduł inwestycyjny

### Pliki

- `backend/routes.py`
- `backend/portfolio_service.py`
- `backend/bond_service.py`
- `backend/price_service.py`
- `backend/watchlist_service.py`
- `backend/math_utils.py`
- `backend/modules/ppk/*`

### Za co odpowiada `routes.py`

To największy plik endpointów inwestycyjnych. Obsługuje m.in.:

- tworzenie portfeli,
- listowanie portfeli,
- wpłaty i wypłaty gotówki,
- kupno i sprzedaż aktywów,
- pobieranie holdings,
- historię wartości i zysku,
- obligacje,
- oszczędności i ręczne odsetki,
- PPK,
- czyszczenie i usuwanie portfela.

### Co robi `portfolio_service.py`

To centralny serwis domenowy inwestycji. Najważniejsze grupy funkcji:

- **operacje symbol mappingu** – `_normalize_symbol_input`, `resolve_symbol_mapping`, `resolve_symbol`,
- **import danych** – `import_xtb_csv`,
- **limity podatkowe** – `get_tax_limits`,
- **CRUD i operacje portfelowe** – tworzenie portfela, depozyty, wypłaty,
- **transakcje giełdowe** – kupno/sprzedaż, aktualizacja holdings,
- **agregacje** – lista portfeli, wartość portfela, historia, wyniki,
- **integracja z cenami** – pobieranie wycen przez `PriceService`,
- **obliczenia finansowe** – m.in. XIRR przez `math_utils.py`.

### Jak wyglądają zależności

Typowy flow w module inwestycyjnym:

- `routes.py` odbiera request,
- wywołuje `PortfolioService`, `BondService`, `PriceService` albo `PPKService`,
- te serwisy korzystają z `get_db()` z `database.py`,
- część obliczeń pomocniczych bierze z `math_utils.py`.

### Przykład przepływu: kupno akcji

1. Frontend wysyła `POST /api/portfolio/buy`.
2. Endpoint `buy()` w `routes.py` odczytuje JSON z polami typu `portfolio_id`, `ticker`, `quantity`, `price`.
3. Endpoint wywołuje `PortfolioService.buy_stock(...)`.
4. Serwis:
   - aktualizuje gotówkę w tabeli `portfolios`,
   - aktualizuje lub tworzy rekord w `holdings`,
   - zapisuje operację do `transactions`.
5. Backend zwraca komunikat sukcesu.
6. Frontend odświeża dane widoku.

### Przykład przepływu: import XTB CSV

1. Frontend lub użytkownik inicjuje import danych.
2. `PortfolioService.import_xtb_csv(...)` iteruje po DataFrame.
3. Dla operacji giełdowych próbuje rozwiązać symbol przez `resolve_symbol_mapping(...)`.
4. Jeśli mapowania brakuje, zwraca listę `missing_symbols`.
5. Jeśli wszystko jest poprawne, dane trafiają do `transactions` i `holdings`.

To właśnie dlatego istnieje osobny panel `Symbol Mapping` – użytkownik może uzupełniać brakujące mapowania symboli z eksportów brokera.

---

## 5.2 Moduł dashboardu globalnego

### Plik

- `backend/routes_dashboard.py`

Ten moduł agreguje dane z kilku obszarów jednocześnie.

Endpoint `/api/dashboard/global-summary`:

- pobiera wolne środki z budżetu przez `BudgetService.get_free_pool(...)`,
- pobiera listę portfeli przez `PortfolioService.list_portfolios()`,
- dla każdego portfela pobiera wycenę przez `PortfolioService.get_portfolio_value(...)`,
- pobiera listę kredytów z bazy,
- dla każdego kredytu generuje harmonogram przez `LoanService.generate_amortization_schedule(...)`,
- liczy aktywa, zobowiązania, majątek netto i najbliższą ratę.

To ważny plik architektonicznie, bo pokazuje, że dashboard jest **warstwą agregacyjną** łączącą budżet, inwestycje i kredyty.

---

## 5.3 Moduł kredytów

### Pliki

- `backend/routes_loans.py`
- `backend/loan_service.py`

### Co robi warstwa HTTP

`routes_loans.py` obsługuje m.in.:

- tworzenie kredytu,
- listowanie kredytów,
- usuwanie kredytu,
- dodawanie stóp procentowych,
- dodawanie nadpłat,
- pobieranie harmonogramu,
- symulacje nadpłaty przez query params.

### Co robi `loan_service.py`

Choć nie był tu w całości otwierany, z użycia w routach widać, że odpowiada za:

- pobranie szczegółów kredytu,
- generowanie harmonogramu amortyzacji,
- uwzględnianie zmian oprocentowania,
- uwzględnianie nadpłat,
- symulacje typu `REDUCE_TERM` i `REDUCE_INSTALLMENT`.

### Przykład przepływu: harmonogram kredytu

1. Frontend wywołuje `GET /api/loans/:id/schedule`.
2. Query string może zawierać np. `sim_amount`, `sim_date`, `monthly_overpayment`, `simulated_action`.
3. Endpoint przekazuje te wartości do `LoanService.generate_amortization_schedule(...)`.
4. Serwis generuje pełny harmonogram i dane symulacyjne.
5. Frontend renderuje wynik w dashboardzie kredytowym i symulatorze.

---

## 5.4 Moduł budżetu

### Pliki

- `backend/routes_budget.py`
- `backend/budget_service.py`

### Zakres endpointów

Budżet obsługuje:

- reset danych budżetowych,
- podsumowanie konta i kopert,
- analitykę miesięczną,
- listę transakcji,
- przychody,
- alokacje do kopert,
- wydatki,
- przelewy między kontami,
- transfer budżet → portfel inwestycyjny,
- wypłatę portfel → budżet,
- pożyczki między kopertami,
- spłaty pożyczek,
- kategorie,
- koperty,
- konta.

### Kluczowa rola `BudgetService`

To serwis, który pilnuje spójności między:

- saldami kont,
- wolną pulą środków,
- stanem kopert,
- historią wydatków i dochodów,
- transferami do inwestycji.

### Ciekawa zależność między modułami

Budżet nie działa w izolacji. W `routes_budget.py` są endpointy:

- `/transfer-to-portfolio`
- `/withdraw-from-portfolio`

To oznacza, że budżet integruje się z modułem inwestycyjnym i pozwala przesuwać środki między `budget_accounts` a `portfolios`.

---

## 5.5 Moduł radaru

### Pliki

- `backend/routes_radar.py`
- `backend/watchlist_service.py`
- `backend/price_service.py`

### Co robi radar

Radar scala dwa źródła informacji:

- tickery obserwowane przez użytkownika (`watchlist`),
- tickery aktualnie posiadane w portfelach (`holdings`).

Endpoint `GET /api/radar`:

1. pobiera zestaw tickerów przez `WatchlistService.get_radar_tickers()`,
2. decyduje, czy czytać dane z cache czy robić refresh (`refresh=1`),
3. pobiera ilości posiadanych instrumentów z tabeli `holdings`,
4. buduje wynik JSON z ceną, zmianami %, terminami earnings i dywidend.

Dzięki temu frontend radaru może pokazać jednocześnie:

- co użytkownik obserwuje,
- co faktycznie posiada,
- kiedy dane były ostatnio aktualizowane.

---

## 5.6 Moduł mapowania symboli

### Pliki

- `backend/routes_symbol_map.py`
- `backend/portfolio_service.py`
- `frontend/src/pages/SymbolMappingPanel.tsx`
- `frontend/src/api_symbol_map.ts`

To moduł pomocniczy, ale ważny dla importów CSV.

### Po co istnieje

Eksport z brokera może zawierać symbol, który nie jest gotowym tickerem używanym w aplikacji. Dlatego aplikacja przechowuje tabelę `symbol_mappings`, gdzie:

- `symbol_input` = symbol z importu,
- `ticker` = docelowy ticker w systemie,
- `currency` = waluta instrumentu.

### Jak działa w praktyce

- Panel frontendowy pobiera listę mapowań przez `GET /api/symbol-map`.
- Użytkownik może dodać, zmienić lub usunąć mapowanie.
- `PortfolioService.import_xtb_csv(...)` używa `resolve_symbol_mapping(...)`, żeby zamienić symbol z CSV na ticker systemowy.

---

## 6. Frontend – punkt wejścia i routing

## 6.1 `frontend/src/main.tsx`

To najprostszy punkt wejścia frontendu:

- importuje `App`,
- importuje style globalne `index.css`,
- renderuje całość do elementu `#root`.

## 6.2 `frontend/src/App.tsx`

To centralny router aplikacji.

Plik:

- opakowuje aplikację w `BrowserRouter`,
- używa `Layout` jako wspólnego szkieletu,
- lazy-loaduje główne widoki przez `React.lazy`,
- definiuje mapowanie ścieżek URL na strony.

### Najważniejsze trasy

- `/` → `MainDashboard`
- `/portfolios` → `PortfolioDashboard`
- `/portfolio/:id` → `PortfolioDetails`
- `/radar` → `InvestmentRadar`
- `/transactions` → `Transactions`
- `/loans` → `LoansDashboard`
- `/loans/:id` → `LoanSimulator`
- `/budget` → `BudgetDashboard`
- `/settings/symbol-mapping` → `SymbolMappingPanel`

To oznacza, że **strony (`pages`) są punktami wejścia funkcjonalnego**, a komponenty podrzędne zwykle renderują szczegóły, wykresy, modale i formularze.

---

## 7. Frontend – wspólny layout i nawigacja

### `frontend/src/components/Layout.tsx`

`Layout` zapewnia:

- górny pasek nawigacji,
- wspólny kontener strony,
- przełączanie motywu przez `useTheme()`,
- aktywne podświetlenie bieżącej trasy dzięki `useLocation()`.

To jest wspólna rama dla wszystkich widoków. Każda strona renderowana przez router trafia do `{children}` wewnątrz `Layout`.

---

## 8. Frontend – warstwa komunikacji z backendem

Frontend nie komunikuje się z backendem w jednym stylu – w projekcie są dwa podejścia:

- wydzielone moduły API,
- bezpośrednie wywołania `fetch` lub `axios` w komponentach.

## 8.1 `frontend/src/api.ts`

To klient Axios dla modułu inwestycyjnego:

- ma `baseURL: '/api/portfolio'`,
- jest używany przez widoki inwestycyjne.

Dzięki temu w komponentach można pisać krócej, np. `api.get('/list')` zamiast pełnej ścieżki.

## 8.2 `frontend/src/api_budget.ts`

To osobna, jawnie opisana warstwa API dla budżetu.

Zawiera:

- typy odpowiedzi (`BudgetSummary`, `Envelope`, `BudgetAccount` itd.),
- pomocniczy `buildUrl(...)`,
- komplet funkcji do komunikacji z `/api/budget/...`.

To dobry przykład modułu, w którym logika komunikacji jest odseparowana od komponentów UI.

## 8.3 `frontend/src/api_loans.ts`

Analogicznie dla kredytów:

- tworzy klient Axios z `baseURL: '/api/loans'`,
- eksportuje funkcje `getLoans`, `createLoan`, `addRate`, `addOverpayment`, `deleteLoan`, `getSchedule`.

## 8.4 `frontend/src/api_symbol_map.ts`

Ten plik obsługuje panel mapowania symboli i udostępnia:

- `getAll()`,
- `create()`,
- `update()`,
- `delete()`.

Dodatkowo ma wspólne `parseJsonResponse<T>()`, które normalizuje obsługę błędów z backendu.

---

## 9. Frontend – strony i ich odpowiedzialność

## 9.1 `MainDashboard.tsx`

To globalny pulpit aplikacji.

### Co robi

- przy starcie wykonuje `GET /api/dashboard/global-summary`,
- trzyma wynik w stanie lokalnym `data`,
- renderuje:
  - aktywa,
  - zobowiązania,
  - majątek netto,
  - wykres struktury aktywów,
  - szybkie przejścia do modułów.

### Połączenie z backendem

Frontend pobiera **jedną agregowaną odpowiedź**, a backend sam łączy budżet, inwestycje i kredyty.

To ważne, bo frontend nie musi ręcznie sklejać wielu requestów.

## 9.2 `PortfolioDashboard.tsx`

To główny dashboard inwestycji.

### Co robi

- pobiera listę portfeli przez `api.get('/list')`,
- pobiera limity podatkowe przez `api.get('/limits')`,
- liczy sumy globalne po stronie UI,
- umożliwia utworzenie nowego portfela przez `api.post('/create', ...)`.

### Jak działa przepływ tworzenia portfela

1. Użytkownik wypełnia formularz.
2. `handleCreate()` wysyła `POST /api/portfolio/create`.
3. Po sukcesie komponent resetuje formularz.
4. `fetchData()` odświeża listę portfeli.

## 9.3 `InvestmentRadar.tsx`

To ekran radaru inwestycyjnego.

### Co robi

- pobiera radar przez `GET /api/radar`,
- może wymusić refresh przez `GET /api/radar?refresh=1`,
- odświeża konkretne tickery przez `POST /api/radar/refresh`,
- dodaje ticker do watchlisty przez `POST /api/radar/watchlist`,
- usuwa z watchlisty przez `DELETE /api/radar/watchlist/:ticker`,
- otwiera modal profilera spółki.

To dobry przykład widoku, który mocno bazuje na danych rynkowych i cache po stronie backendu.

## 9.4 `BudgetDashboard.tsx`

Choć nie był tu otwierany linia po linii, po strukturze projektu i API wiadomo, że jest głównym widokiem budżetowym. Korzysta z komponentów w `components/budget/` i funkcji z `api_budget.ts`.

## 9.5 `LoansDashboard.tsx` i `LoanSimulator.tsx`

To odpowiednio:

- lista i podsumowanie kredytów,
- szczegół/symulator pojedynczego kredytu.

Ich backendowym odpowiednikiem jest `routes_loans.py` + `loan_service.py`, a frontendowym klientem `api_loans.ts`.

## 9.6 `PortfolioDetails.tsx`, `Transactions.tsx`, `PortfolioList.tsx`

Te widoki rozwijają moduł inwestycyjny:

- szczegóły pojedynczego portfela,
- historia transakcji,
- listy i agregaty pozycji.

W praktyce te strony opierają się głównie o `frontend/src/api.ts` i endpointy z `backend/routes.py`.

---

## 10. Frontend – komponenty wspólne i domenowe

W `frontend/src/components/` są dwa główne typy komponentów:

### 10.1 Komponenty ogólne

Np.:

- `Layout.tsx`,
- wykresy portfela,
- komponenty pustych stanów,
- modale transakcyjne.

### 10.2 Komponenty domenowe

Pogrupowane folderami:

- `components/budget/` – UI budżetu,
- `components/loans/` – UI kredytów,
- `components/modals/` – modale wspólne,
- komponenty wykresów inwestycyjnych.

To oznacza, że architektura frontendu jest **mieszana: page-driven + feature folders**.

---

## 11. Typy i kontrakty danych

### `frontend/src/types.ts`

Ten plik jest centralnym miejscem dla typów inwestycyjnych i części danych wspólnych:

- `Portfolio`,
- `Transaction`,
- `Bond`,
- `Dividend`,
- `Holding`,
- `PortfolioValue`,
- `ClosedPosition`,
- `RadarItem`,
- `StockAnalysisData`.

Dzięki temu komponenty mają spójniejsze typowanie, a dane z backendu są łatwiejsze do renderowania bez zgadywania kształtu JSON.

Osobne moduły, jak budżet czy symbol mapping, definiują własne typy we własnych plikach API.

---

## 12. Jak pliki są ze sobą połączone – najważniejsze mapowanie

## 12.1 Inwestycje

### Frontend

- `App.tsx` → route `/portfolios`
- `pages/PortfolioDashboard.tsx`
- `pages/PortfolioDetails.tsx`
- `pages/Transactions.tsx`
- `api.ts`
- `types.ts`

### Backend

- `app.py` → rejestruje `/api/portfolio`
- `routes.py`
- `portfolio_service.py`
- `bond_service.py`
- `price_service.py`
- `database.py`

### Relacja

`PortfolioDashboard.tsx` / `PortfolioDetails.tsx` → `api.ts` → `routes.py` → `PortfolioService` → `database.py` / `PriceService`

---

## 12.2 Budżet

### Frontend

- `App.tsx` → route `/budget`
- `components/budget/BudgetDashboard.tsx`
- `components/budget/BudgetAnalytics.tsx`
- `components/budget/TransactionHistory.tsx`
- `api_budget.ts`

### Backend

- `app.py` → rejestruje `/api/budget`
- `routes_budget.py`
- `budget_service.py`
- `database.py`

### Relacja

`BudgetDashboard.tsx` → `api_budget.ts` → `routes_budget.py` → `BudgetService` → `database.py`

---

## 12.3 Kredyty

### Frontend

- `App.tsx` → `/loans`, `/loans/:id`
- `components/loans/LoansDashboard.tsx`
- `components/loans/LoanSimulator.tsx`
- `api_loans.ts`

### Backend

- `app.py` → rejestruje `/api/loans`
- `routes_loans.py`
- `loan_service.py`
- `database.py`

### Relacja

`LoansDashboard.tsx` / `LoanSimulator.tsx` → `api_loans.ts` → `routes_loans.py` → `LoanService` → `database.py`

---

## 12.4 Dashboard globalny

### Frontend

- `App.tsx` → `/`
- `pages/MainDashboard.tsx`

### Backend

- `routes_dashboard.py`
- `BudgetService`
- `PortfolioService`
- `LoanService`

### Relacja

`MainDashboard.tsx` → `GET /api/dashboard/global-summary` → `routes_dashboard.py` → agregacja trzech modułów

---

## 12.5 Radar

### Frontend

- `App.tsx` → `/radar`
- `pages/InvestmentRadar.tsx`
- `components/StockProfilerModal.tsx`

### Backend

- `routes_radar.py`
- `watchlist_service.py`
- `price_service.py`
- `database.py`

### Relacja

`InvestmentRadar.tsx` → `/api/radar*` → `routes_radar.py` → `WatchlistService` + `PriceService` + `database.py`

---

## 12.6 Symbol mapping

### Frontend

- `App.tsx` → `/settings/symbol-mapping`
- `pages/SymbolMappingPanel.tsx`
- `api_symbol_map.ts`

### Backend

- `routes_symbol_map.py`
- `portfolio_service.py`
- `database.py`

### Relacja

`SymbolMappingPanel.tsx` → `api_symbol_map.ts` → `routes_symbol_map.py` → tabela `symbol_mappings` → użycie pośrednie w `PortfolioService.import_xtb_csv(...)`

---

## 13. Funkcje referencyjne / pomocnicze i ich znaczenie

U Ciebie „odniesienia” najpewniej oznaczają funkcje pomocnicze, które są używane przez inne moduły i spinają całość. Najważniejsze z nich to:

### Backend

- `create_app()` – tworzy i składa całą aplikację backendową,
- `init_db(app)` – inicjalizuje schemat bazy,
- `get_db()` – daje połączenie do SQLite w ramach requestu,
- `PriceService.warmup_cache()` – przygotowuje cache cen po starcie,
- `PortfolioService.resolve_symbol_mapping()` – tłumaczy symbole importowe na tickery systemowe,
- `PortfolioService.get_portfolio_value()` – kluczowa funkcja wyceny portfela,
- `LoanService.generate_amortization_schedule()` – serce modułu kredytów,
- `BudgetService.get_free_pool()` – ważna funkcja dla dashboardu globalnego.

### Frontend

- `App()` – mapuje ścieżki na widoki,
- `Layout` – wspólna rama aplikacji,
- `fetchData()` w wielu stronach – schemat pobierania danych z backendu,
- funkcje z `api_budget.ts`, `api_loans.ts`, `api_symbol_map.ts` – cienka warstwa pośrednia między UI a backendem,
- typy z `types.ts` – referencja kształtu danych dla wielu komponentów.

---

## 14. Typowy cykl requestu – przykład end-to-end

## 14.1 Przykład: wejście na dashboard inwestycji

1. Użytkownik przechodzi na `/portfolios`.
2. `App.tsx` wybiera `PortfolioDashboard`.
3. `PortfolioDashboard.tsx` w `useEffect()` uruchamia `fetchData()`.
4. `fetchData()` wykonuje równolegle:
   - `GET /api/portfolio/list`,
   - `GET /api/portfolio/limits`.
5. `routes.py` odbiera requesty.
6. `PortfolioService` liczy dane i pobiera rekordy z bazy.
7. Backend odsyła JSON.
8. Frontend ustawia stan przez `setPortfolios(...)` i `setTaxLimits(...)`.
9. React renderuje karty, tabelę i limity podatkowe.

## 14.2 Przykład: wejście na dashboard globalny

1. Użytkownik wchodzi na `/`.
2. `MainDashboard.tsx` robi `GET /api/dashboard/global-summary`.
3. `routes_dashboard.py` pobiera dane z budżetu, inwestycji i kredytów.
4. Backend zwraca jeden obiekt z podsumowaniem.
5. Frontend renderuje karty KPI i wykres struktury aktywów.

## 14.3 Przykład: dodanie tickera do radaru

1. Użytkownik wpisuje ticker w `InvestmentRadar.tsx`.
2. `handleAddTicker()` wysyła `POST /api/radar/watchlist`.
3. `routes_radar.py` wywołuje `WatchlistService.add_to_watchlist(...)`.
4. Ticker trafia do tabeli `watchlist`.
5. Frontend odświeża radar i pobiera nową listę.

---

## 15. Najważniejsze zależności między modułami

Projekt nie jest zbiorem całkowicie niezależnych części. Są tu istotne połączenia krzyżowe:

### 15.1 Budżet ↔ inwestycje

- transfer środków z budżetu do portfela,
- wypłata środków z portfela do budżetu,
- dashboard globalny sumuje oba obszary.

### 15.2 Kredyty ↔ dashboard globalny

- harmonogramy kredytów wpływają na zobowiązania i majątek netto.

### 15.3 Radar ↔ inwestycje

- radar korzysta z holdings, żeby pokazać ilość już posiadanych instrumentów.

### 15.4 Symbol mapping ↔ import inwestycji

- poprawność importu CSV zależy od jakości mapowań symboli.

### 15.5 Price service ↔ inwestycje i radar

- wycena holdings,
- historia wyników,
- dane analityczne do radaru,
- warmup cache przy starcie aplikacji.

---

## 16. Jak czytać ten projekt jako developer

Jeśli chcesz szybko zrozumieć konkretny feature, najlepiej iść taką ścieżką:

### Dla frontendu

1. Zacznij od `frontend/src/App.tsx`.
2. Znajdź route odpowiadający ekranowi.
3. Otwórz odpowiedni plik w `pages/` albo `components/<moduł>/`.
4. Zobacz, czy używa `api*.ts`, `fetch`, czy `axios` inline.
5. Sprawdź endpoint backendowy.

### Dla backendu

1. Zacznij od `backend/app.py`.
2. Znajdź blueprint dla obszaru.
3. Otwórz odpowiedni `routes*.py`.
4. Zobacz, jaki serwis jest wywoływany.
5. Otwórz `*_service.py` i sprawdź, jakie tabele i funkcje pomocnicze są używane.
6. Jeśli potrzeba, wróć do `database.py`, żeby sprawdzić strukturę tabel.

To jest najszybszy sposób dojścia od ekranu do SQL-a.

---

## 17. Diagram zależności plików

Poniżej jest uproszczony diagram pokazujący najważniejsze połączenia między plikami i warstwami aplikacji.

```text
frontend/src/main.tsx
  -> frontend/src/App.tsx
    -> frontend/src/components/Layout.tsx
    -> frontend/src/pages/MainDashboard.tsx
      -> GET /api/dashboard/global-summary
      -> backend/routes_dashboard.py
        -> backend/budget_service.py
        -> backend/portfolio_service.py
        -> backend/loan_service.py
        -> backend/database.py

    -> frontend/src/pages/PortfolioDashboard.tsx
      -> frontend/src/api.ts
      -> backend/routes.py
        -> backend/portfolio_service.py
          -> backend/price_service.py
          -> backend/bond_service.py
          -> backend/math_utils.py
          -> backend/database.py

    -> frontend/src/pages/PortfolioDetails.tsx
      -> frontend/src/api.ts
      -> backend/routes.py
        -> backend/portfolio_service.py
        -> backend/price_service.py
        -> backend/database.py

    -> frontend/src/components/budget/BudgetDashboard.tsx
      -> frontend/src/api_budget.ts
      -> backend/routes_budget.py
        -> backend/budget_service.py
          -> backend/database.py
          -> (integracja) backend/portfolio_service.py

    -> frontend/src/components/loans/LoansDashboard.tsx
    -> frontend/src/components/loans/LoanSimulator.tsx
      -> frontend/src/api_loans.ts
      -> backend/routes_loans.py
        -> backend/loan_service.py
          -> backend/database.py

    -> frontend/src/pages/InvestmentRadar.tsx
      -> fetch('/api/radar...')
      -> backend/routes_radar.py
        -> backend/watchlist_service.py
        -> backend/price_service.py
        -> backend/database.py

    -> frontend/src/pages/SymbolMappingPanel.tsx
      -> frontend/src/api_symbol_map.ts
      -> backend/routes_symbol_map.py
        -> backend/database.py
        -> (użycie pośrednie) backend/portfolio_service.py::import_xtb_csv()

backend/app.py
  -> rejestruje wszystkie blueprinty
  -> init_db(app) z backend/database.py
  -> PriceService.warmup_cache() z backend/price_service.py
```

### 17.1 Jak czytać ten diagram

- Strzałka `->` oznacza bezpośrednie wywołanie albo zależność wykonawczą.
- Pliki frontendowe na górze inicjują requesty.
- Pliki `routes_*.py` są wejściem HTTP po stronie backendu.
- Serwisy (`*_service.py`) realizują logikę biznesową.
- `database.py` jest najniższą warstwą dostępu do SQLite.
- `price_service.py` jest usługą współdzieloną przez inwestycje i radar.

---

## 18. Krótka dokumentacja dla nowych developerów

Jeśli wchodzisz do projektu pierwszy raz, nie czytaj wszystkiego naraz. Najszybciej zrozumiesz repo w tej kolejności.

### 18.1 Start – 5 plików, od których warto zacząć

1. `README.md` – ogólny opis projektu i modułów.
2. `backend/app.py` – jak startuje backend i jakie są blueprinty.
3. `backend/database.py` – jakie tabele istnieją i jak przechowywane są dane.
4. `frontend/src/App.tsx` – jakie są główne ekrany aplikacji.
5. `docs/ARCHITECTURE_FLOW.md` – ten dokument, jako mapa zależności.

### 18.2 Jeśli chcesz pracować nad frontendem

Idź tą ścieżką:

1. Otwórz `frontend/src/App.tsx`.
2. Znajdź route ekranu, który chcesz zmieniać.
3. Otwórz odpowiedni plik w `pages/` lub `components/<feature>/`.
4. Sprawdź, skąd bierze dane: `api.ts`, `api_budget.ts`, `api_loans.ts`, `api_symbol_map.ts`, `fetch`, `axios`.
5. Z mapy endpointów przejdź do odpowiedniego `backend/routes*.py`.

### 18.3 Jeśli chcesz pracować nad backendem

Idź tą ścieżką:

1. Otwórz `backend/app.py`.
2. Znajdź moduł (`portfolio`, `budget`, `loans`, `dashboard`, `radar`, `symbol-map`).
3. Otwórz odpowiadający mu plik `routes*.py`.
4. Zobacz, który serwis wykonuje logikę.
5. Otwórz `*_service.py`.
6. Jeśli coś dotyczy zapisu danych, sprawdź odpowiednią tabelę w `backend/database.py`.

### 18.4 Najważniejsze skróty myślowe

- **Chcę zmienić ekran** → zacznij od `App.tsx` i pliku widoku.
- **Chcę zmienić odpowiedź API** → zacznij od `routes*.py`, potem `*_service.py`.
- **Chcę zrozumieć dane** → zacznij od `database.py`.
- **Chcę zrozumieć wyceny i dane rynkowe** → sprawdź `price_service.py`.
- **Chcę zrozumieć import CSV** → sprawdź `portfolio_service.py` + `routes_symbol_map.py`.

### 18.5 Najczęstsze miejsca, od których naprawdę zaczyna się debugging

- problem z widokiem → komponent strony + zakładka Network w przeglądarce,
- problem z API → `routes*.py`,
- problem z wynikiem biznesowym → `*_service.py`,
- problem z danymi historycznymi lub relacjami → `database.py`,
- problem z cenami / radarem → `price_service.py` i `routes_radar.py`.

### 18.6 Minimalny plan wejścia do repo w pierwsze 30 minut

- 5 min: przeczytaj `README.md`.
- 5 min: przeczytaj `backend/app.py` i zobacz blueprinty.
- 5 min: przejrzyj `frontend/src/App.tsx` i listę tras.
- 10 min: wybierz jeden flow, np. dashboard albo portfele, i prześledź go end-to-end.
- 5 min: wróć do tego dokumentu i porównaj teorię z konkretnymi plikami.

---

## 19. Podsumowanie architektury

Najkrócej:

- **Frontend** odpowiada za routing, formularze, wizualizacje i stan widoków.
- **Backend** odpowiada za logikę biznesową, agregację danych, walidację operacji i zapis do SQLite.
- **Warstwa routingu** w backendzie jest cienka i deleguje pracę do serwisów.
- **Warstwa API** w frontendzie jest częściowo wydzielona, ale miejscami requesty są robione bezpośrednio w komponentach.
- **Dashboard globalny** jest miejscem, gdzie łączą się inwestycje, budżet i kredyty.
- **PriceService** i **symbol mapping** są modułami wspólnymi, które wspierają kilka funkcji jednocześnie.
