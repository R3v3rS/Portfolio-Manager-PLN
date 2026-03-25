# Project Guide — architektura, zależności i mapa projektu

Ten dokument ma pełnić dwie role jednocześnie:

1. **onboarding dla nowej osoby**, która ma rozwijać aplikację,
2. **mapę operacyjną dla AI**, żeby szybko rozumieć zależności, przepływy danych i miejsca zmian.

## 1. Cel projektu

Portfolio Manager (PLN) scala kilka obszarów finansów osobistych w jednej aplikacji:

- inwestycje,
- budżet domowy,
- kredyty,
- dashboard majątku netto,
- radar / watchlistę,
- moduł PPK.

To nie jest zestaw niezależnych mikroserwisów. To jeden projekt, w którym moduły biznesowe są połączone wspólną bazą danych SQLite i wspólnym API Flask.

## 2. Stack technologiczny

### Frontend
- React 18,
- TypeScript,
- Vite,
- React Router,
- Axios,
- Recharts,
- Chart.js,
- Tailwind CSS,
- Zustand.

### Backend
- Flask,
- Flask-CORS,
- SQLite (`sqlite3`),
- Pandas,
- yfinance,
- Requests,
- python-dotenv.

## 3. Jak uruchamia się aplikacja

### Backend
1. `backend/app.py` tworzy instancję Flask.
2. CORS jest włączony globalnie.
3. Konfigurowana jest ścieżka do `backend/portfolio.db`.
4. `init_db(app)` przygotowuje schemat oraz połączenia z bazą.
5. `PriceService.warmup_cache()` próbuje odświeżyć cache cen przy starcie.
6. Rejestrowane są blueprinty API.
7. Aplikacja wystawia health-check pod `/`.

### Frontend
1. `frontend/src/main.tsx` bootstrappuje React.
2. `frontend/src/App.tsx` buduje routing aplikacji.
3. Część ekranów jest ładowana leniwie przez `React.lazy`.
4. Layout wspólny dla wszystkich stron znajduje się w `frontend/src/components/Layout.tsx`.

## 4. Moduły backendu

### 4.1 `backend/app.py`
Punkt wejścia backendu. Tu zaczyna się cały request lifecycle po stronie serwera.

### 4.2 `backend/database.py`
Najważniejszy plik infrastrukturalny backendu. Odpowiada za:

- połączenie z SQLite,
- obsługę `g.db` w kontekście requestu,
- inicjalizację tabel,
- część pomocniczych operacji administracyjnych, np. reset danych budżetu.

### 4.3 Podział routerów (routes_*.py)
Logika HTTP została podzielona na mniejsze, tematyczne blueprinty:

- **`routes_portfolios.py`** – CRUD portfeli i lista portfeli.
- **`routes_transactions.py`** – operacje na transakcjach (BUY, SELL, DEPOSIT, WITHDRAW, DIVIDEND).
- **`routes_history.py`** – endpointy dla wykresów i danych historycznych.
- **`routes_imports.py`** – importy danych (np. XTB CSV).
- **`routes_ppk.py`** – operacje i podsumowania dla portfeli PPK.
- **`routes_budget.py`** – pełna obsługa budżetu domowego (koperty, konta, transfery).
- **`routes_dashboard.py`** – agregacja danych dla głównego dashboardu (net worth).
- **`routes_loans.py`** – obsługa kredytów, harmonogramów i nadpłat.
- **`routes_radar.py`** – watchlisty, ceny rynkowe i radar inwestycyjny.
- **`routes_symbol_map.py`** – mapowanie symboli zewnętrznych na tickery.
- **`routes_admin.py`** – operacje administracyjne (czyszczenie, audyt, przebudowa).

### 4.4 Infrastruktura API (`backend/api/`)
Wprowadzono ustandaryzowaną warstwę komunikacji i obsługi błędów:

- **`backend/api/response.py`** – zawiera helpery `success_response` i `error_response`, które pilnują struktury envelope `{ payload, error }`.
- **`backend/api/exceptions.py`** – definiuje hierarchię wyjątków biznesowych:
    - `ApiError`: bazowy wyjątek dla błędów API z kodem i statusem HTTP.
    - `ValidationError`: rzucany przy błędach walidacji wejścia (status 400).
    - `NotFoundError`: rzucany, gdy zasób nie istnieje (status 404).

Wszystkie te wyjątki są automatycznie przechwytywane przez globalne handlery w `app.py` i zamieniane na poprawne odpowiedzi JSON.

## 5. Moduły serwisowe backendu

Logika biznesowa została wydzielona z routerów do dedykowanych serwisów:

### Inwestycje (Portfolio services)
- **`portfolio_core_service.py`** – podstawowe operacje na portfelach (CRUD).
- **`portfolio_trade_service.py`** – logika kupna/sprzedaży i transakcji.
- **`portfolio_valuation_service.py`** – wycena portfeli i instrumentów.
- **`portfolio_history_service.py`** – rekonstrukcja danych historycznych i wykresów.
- **`portfolio_import_service.py`** – parsowanie i przetwarzanie importów CSV (XTB).
- **`portfolio_audit_service.py`** – weryfikacja integralności danych i **deterministyczna rekonstrukcja stanu** (holdings/cash) na podstawie historii transakcji. Służy do audytu i naprawy niespójności.
- **`portfolio_service.py`** – fasada łącząca powyższe serwisy dla prostszego dostępu.

### Pozostałe serwisy
- **`price_service.py`** – zarządzanie cenami rynkowymi, cachem i radarem.
- **`watchlist_service.py`** – logika watchlisty.
- **`bond_service.py`** – logika związana z obligacjami.
- **`budget_service.py`** – serwis budżetowy odpowiedzialny za wolne środki, koperty i analitykę.
- **`loan_service.py`** – silnik harmonogramów kredytów i nadpłat.
- **`inflation_service.py`** – pobieranie i serwowanie danych o inflacji.

### `modules/ppk/*`
Wydzielony moduł domenowy PPK:
- DTO, kalkulacje, podatki, serwis.

## 6. Frontend — mapa katalogów

### `frontend/src/App.tsx`
Najważniejsza mapa ekranów. To najkrótsza droga do zrozumienia, jakie widoki naprawdę istnieją.

### `frontend/src/pages/`
Strony wysokiego poziomu, np.:

- `MainDashboard.tsx`,
- `PortfolioDashboard.tsx`,
- `PortfolioDetails.tsx`,
- `InvestmentRadar.tsx`,
- `Transactions.tsx`,
- `SymbolMappingPanel.tsx`.

### `frontend/src/components/`
Komponenty współdzielone i modułowe. Znajdują się tu m.in.:

- wykresy inwestycyjne,
- layout,
- komponenty kredytów,
- komponenty budżetu,
- modale transakcyjne.

### `frontend/src/api*.ts`
Spójna warstwa komunikacji z backendem oparta o wspólny klient HTTP z `frontend/src/http.ts` oraz wspólną konfigurację endpointów z `frontend/src/apiConfig.ts`.

Zasada architektoniczna dla frontendu: komponenty i strony nie wykonują bezpośrednich requestów HTTP — każde wywołanie backendu powinno przejść przez moduł API. Helpery infrastrukturalne także powinny opierać się o wspólny klient HTTP, chyba że istnieje dobrze udokumentowany wyjątek techniczny.

### `frontend/src/services/`
Pomocnicze usługi po stronie klienta, np. kalkulatory PPK i provider cen.

### `frontend/src/types.ts`
Zbiorczy punkt z częścią typów współdzielonych po stronie UI.

## 7. Główne ścieżki użytkownika i przepływy danych

### 7.1 Dashboard główny
Flow:
1. użytkownik wchodzi na `/`,
2. ładuje się `MainDashboard.tsx`,
3. komponent pobiera `/api/dashboard/global-summary`,
4. backend agreguje budżet, portfele i kredyty,
5. frontend renderuje majątek netto, aktywa, zobowiązania i statystyki szybkie.

#### Co dokładnie liczy backend
`routes_dashboard.py` nie zwraca surowych tabel, tylko gotowe agregaty do UI:

- iteruje po wszystkich kontach budżetowych i sumuje **free pool**, a nie pełne saldo kont,
- iteruje po wszystkich portfelach i pobiera ich aktualną wartość przez `PortfolioService.get_portfolio_value(...)`,
- rozbija aktywa na kubełki: gotówka budżetowa, gotówka inwestycyjna, oszczędności, obligacje, akcje/ETF i PPK,
- pobiera wszystkie kredyty i dla każdego generuje harmonogram przez `LoanService.generate_amortization_schedule(...)`,
- z harmonogramu wyciąga aktualne saldo kredytu oraz najbliższą ratę,
- klasyfikuje zobowiązania na krótkoterminowe i długoterminowe według kategorii kredytu.

#### Co renderuje frontend
`MainDashboard.tsx` robi z gotowych danych trzy rzeczy:

- pokazuje karty KPI: aktywa, zobowiązania i majątek netto,
- wylicza dwa warianty majątku netto: tylko z krótkoterminowymi zobowiązaniami oraz ze wszystkimi,
- buduje wykres kołowy struktury aktywów w oparciu o `assets_breakdown`.

To ważne: sam frontend nie przelicza biznesowej logiki majątku netto — on tylko formatuje odpowiedź API.

### 7.2 Lista portfeli i szczegóły portfela
Flow:
1. użytkownik przechodzi na `/portfolios` albo `/portfolio/:id`,
2. frontend pobiera dane portfela, pozycji, transakcji, dywidend i historii,
3. backend korzysta głównie z `routes.py` oraz `portfolio_service.py`,
4. ceny i historia mogą wykorzystywać `PriceService` i zapisany cache.

#### Jak działa `fetchData()` w `PortfolioDetails.tsx`
To centralna funkcja ładowania widoku szczegółów portfela. Równolegle pobiera:

- listę wszystkich portfeli,
- holdings dla danego portfela,
- aktualną wartość portfela,
- miesięczne dywidendy,
- historię transakcji,
- zamknięte pozycje i cykle zamkniętych pozycji,
- summary budżetu, żeby mieć listę kont do transferów.

Potem, zależnie od typu portfela:

- dla `BONDS` pobiera osobno listę obligacji,
- dla `SAVINGS` pobiera miesięczną historię wartości,
- dla `PPK` pobiera transakcje PPK, podsumowanie i bieżącą cenę jednostki,
- dla zwykłych portfeli pobiera historię miesięczną, historię zysku oraz dwa krótkoterminowe szeregi 30D: zysk i wartość.

#### Jak działa aktualna wycena portfela
`PortfolioService.get_portfolio_value(...)` rozgałęzia logikę według typu konta:

- `SAVINGS` — liczy odsetki narosłe od `last_interest_date` do dziś i dodaje je do gotówki,
- `BONDS` — pobiera obligacje z `BondService`, sumuje ich `total_value` i dodaje gotówkę,
- `PPK` — pobiera aktualną cenę jednostki, buduje podsumowanie PPK i używa netto-wartości możliwej do wypłaty,
- `STANDARD` / `IKE` — pobiera holdings, sumuje bieżące wartości pozycji i wynik otwartych pozycji.

Na końcu niezależnie od typu dokłada jeszcze:

- zaksięgowane dywidendy,
- zaksięgowane odsetki gotówkowe,
- procentowy wynik całkowity,
- XIRR tam, gdzie ma sens,
- dodatkowe pola wykorzystywane przez zakładki w szczegółach portfela.

### 7.3 Historia portfela, zysku i wykresy
To obszar, o który najłatwiej pytać przy rozwoju aplikacji, bo łączy rekonstrukcję danych historycznych z prezentacją na frontendzie.

#### Historia miesięczna portfela
`PortfolioService.get_portfolio_history(...)` bazuje na wewnętrznej rekonstrukcji danych miesięcznych. Wynik końcowy to lista punktów:

- `date` w formacie `YYYY-MM`,
- `label` do osi X,
- `value` jako wartość portfela na koniec miesiąca,
- opcjonalnie `benchmark_value` gdy użytkownik wybrał benchmark.

Ta funkcja nie czyta gotowej tabeli historii portfela. Ona **odtwarza stan na podstawie transakcji**, a potem grupuje wynik miesiącami.

#### Historia zysku miesięczna
`PortfolioService.get_portfolio_profit_history(...)` używa tego samego mechanizmu bazowego, ale zamiast wartości portfela zwraca pole `profit`.

W praktyce zysk jest rozumiany jako:

`wartość portfela - kapitał netto wpłacony`

czyli uwzględnia:

- depozyty,
- wypłaty,
- bieżącą wartość holdings,
- gotówkę,
- efekty wcześniejszych operacji.

#### Historia dzienna 30D / N dni
`PortfolioService.get_portfolio_profit_history_daily(...)` działa inaczej niż wariant miesięczny:

1. pobiera wszystkie transakcje portfela rosnąco po dacie,
2. wyznacza zakres od `today - (days - 1)` do dziś,
3. dla każdego dnia z tego zakresu odtwarza stan portfela „jakby dzień kończył się właśnie wtedy”,
4. osobno liczy gotówkę, kapitał zainwestowany i ilości poszczególnych tickerów,
5. dla instrumentów nie-PLN pobiera lub odtwarza kursy FX,
6. wylicza wartość pozycji według najbliższej dostępnej historycznej ceny,
7. dla aktywów walutowych odejmuje szacunkową opłatę FX,
8. zwraca albo zysk (`metric='profit'`), albo samą wartość (`metric='value'`).

#### Co ta rekonstrukcja uwzględnia
Mechanizm dzienny uwzględnia m.in.:

- daty wszystkich transakcji,
- buy / sell wpływające na liczbę sztuk,
- depozyty i wypłaty wpływające na kapitał netto,
- dywidendy i odsetki wpływające na gotówkę,
- historyczne ceny instrumentów,
- kursy FX dla walut innych niż PLN,
- brak dokładnej ceny w danym dniu poprzez użycie ostatniej dostępnej historycznej ceny.

#### Ograniczenia, które warto znać
- historia dzienna jest odtwarzana dynamicznie i może być kosztowna dla dużej liczby transakcji,
- jeśli brakuje historii cen dla danego tickera, wartość może chwilowo spaść do zera dla tej pozycji,
- dla `SAVINGS` i `BONDS` logika historii różni się od klasycznych akcji, bo te portfele nie opierają się na standardowym mechanizmie cen rynkowych.

#### Jak rysowany jest wykres wartości miesięcznej
`PortfolioHistoryChart.tsx` używa Recharts i oczekuje danych już policzonych przez backend.

Frontend robi tu tylko:

- render osi X na podstawie `label`,
- render serii `value`,
- opcjonalny render serii `benchmark_value`,
- tooltip z formatowaniem do PLN,
- legendę i styl wizualny.

Czyli cały ciężar liczenia historii jest po stronie backendu, a komponent jest warstwą prezentacji.

#### Jak rysowany jest wykres zysku
`PortfolioProfitChart.tsx` używa Chart.js i dostaje listę punktów `label + value`.

Logika komponentu:

- rysuje jedną linię skumulowanego wyniku w PLN,
- kolor segmentu zmienia się w zależności od tego, czy punkt startowy segmentu jest nad zerem czy pod zerem,
- obszar nad osią zero jest wypełniany na zielono,
- obszar poniżej osi zero jest wypełniany na czerwono,
- sama oś zero jest dodatkowo pogrubiona, żeby łatwo było zobaczyć przejścia między stratą a zyskiem.

To oznacza, że „zielony/czerwony wykres zysku” nie jest liczony przez frontend matematycznie poza prostą oceną znaku — wszystkie wartości wejściowe dostarcza backend.

#### Jak działa wykres historii pojedynczego tickera
`PriceHistoryChart.tsx` pokazuje prostą serię `date -> close_price`.

Dane pochodzą z endpointu historii pojedynczego instrumentu i są używane głównie do szybkiego podglądu notowań zaznaczonej pozycji w portfelu.

### 7.4 Operacje portfelowe: wpłata, wypłata, kupno, sprzedaż
To podstawowa logika, która buduje później całą historię i wycenę.

#### Wpłata i wypłata
`deposit_cash(...)` i `withdraw_cash(...)` aktualizują gotówkę portfela oraz zapisują odpowiednie transakcje typu `DEPOSIT` lub `WITHDRAW`.

To ważne, bo historia i wyniki nie bazują wyłącznie na stanie końcowym — bazują na pełnym dzienniku transakcji.

#### Kupno akcji
`buy_stock(...)` aktualizuje kilka rzeczy jednocześnie:

- zmniejsza gotówkę portfela,
- tworzy lub aktualizuje `holding`,
- przelicza średnią cenę zakupu,
- zapisuje koszt całkowity,
- zapisuje transakcję typu `BUY`.

Jeśli aktywo jest walutowe, logika może uwzględnić automatyczne opłaty FX.

#### Sprzedaż akcji
`sell_stock(...)`:

- zwiększa gotówkę portfela,
- zmniejsza ilość w `holdings` albo usuwa pozycję przy pełnym zamknięciu,
- liczy `realized_profit`,
- zapisuje transakcję typu `SELL`.

Ta informacja później zasila:

- historię transakcji,
- zamknięte pozycje,
- historyczny wynik,
- audyt portfela.

### 7.5 Import XTB CSV
To jedna z ważniejszych ścieżek specjalnych projektu.

#### Wejście z frontendu
W `PortfolioDetails.tsx` użytkownik wybiera plik, a frontend wysyła go jako `multipart/form-data` pod endpoint `/{portfolioId}/import/xtb`.

Jeżeli backend zwróci brakujące symbole, frontend:

- pokazuje listę braków,
- pozwala dopisać ticker i walutę dla każdego symbolu,
- zapisuje mapowania przez `symbolMapApi`,
- umożliwia ponowienie importu na tym samym pliku.

#### Co robi backend podczas importu
`PortfolioService.import_xtb_csv(...)`:

1. sortuje DataFrame po kolumnie `Time`,
2. rozpoznaje nazwy kolumn niezależnie od wielkości liter,
3. znajduje kolumnę `symbol` albo `instrument`,
4. otwiera transakcję DB (`BEGIN`),
5. iteruje po każdym wierszu eksportu,
6. rozpoznaje typ operacji,
7. dla operacji giełdowych próbuje rozwiązać symbol przez `resolve_symbol_mapping(...)`.

#### Jak rozwiązywane są symbole
`resolve_symbol_mapping(...)` działa wielostopniowo:

- najpierw normalizuje wejście (`trim`, `upper`, usuwanie nadmiarowych spacji),
- szuka dokładnego dopasowania w `symbol_mappings`,
- jeśli nie znajdzie, buduje znormalizowany lookup z całej tabeli,
- na końcu próbuje znaleźć bardzo bliskie dopasowanie przez `get_close_matches(...)`.

To pozwala obsłużyć drobne różnice w zapisie symbolu z eksportu brokera.

#### Jakie typy operacji import uwzględnia
Na podstawie obecnej logiki import obsługuje m.in.:

- `deposit` i `ike deposit`,
- `free funds interest`,
- `withdrawal`,
- `stock purchase`,
- `stock sell`.

#### Co dokładnie robi dla poszczególnych wierszy
- **deposit / ike deposit** — zwiększa gotówkę i zapisuje transakcję `DEPOSIT`,
- **free funds interest** — zwiększa gotówkę i zapisuje `INTEREST`,
- **withdrawal** — zmniejsza gotówkę i zapisuje `WITHDRAW`,
- **stock purchase** — parsuje komentarz XTB, wylicza ilość i cenę jednostkową z realnego przepływu gotówki, aktualizuje holdings oraz zapisuje `BUY`,
- **stock sell** — parsuje komentarz, zwiększa gotówkę, zmniejsza holdings, liczy zrealizowany wynik i zapisuje `SELL`.

#### Co import świadomie uwzględnia
- rzeczywisty przepływ gotówki z pliku XTB jako źródło prawdy dla transakcji,
- walutę instrumentu z mapowania symboli,
- sytuację, w której tego samego tickera nie ma jeszcze w holdings,
- aktualizację średniego kosztu zakupu przy kolejnych dokupieniach,
- rollback całego importu, jeśli wystąpi błąd.

#### Co się dzieje przy brakujących symbolach
Jeżeli choć jeden symbol nie ma mapowania:

- import nie jest częściowo zapisywany,
- backend robi rollback,
- zwracana jest lista `missing_symbols`,
- użytkownik może dopisać mapowania i spróbować ponownie.

To bardzo ważne: import jest traktowany jako operacja atomowa, żeby nie zostawić portfela w stanie „zaimportowane połowicznie”.

### 7.6 Radar inwestycyjny
Radar nie jest tylko watchlistą. To ekran łączący obserwowane tickery z realnie posiadanymi pozycjami i cachem danych rynkowych.

#### Jak działa pobranie listy radaru
`routes_radar.py` w `GET /api/radar`:

1. pobiera tickery przez `WatchlistService.get_radar_tickers()`,
2. jeśli `refresh=1`, odświeża dane przez `PriceService.refresh_radar_data(...)`,
3. w przeciwnym razie czyta dane z `PriceService.get_cached_radar_data(...)`,
4. dociąga z bazy sumaryczne ilości tickerów z `holdings`,
5. dociąga daty dodania do watchlisty,
6. buduje wynik zawierający jednocześnie dane rynkowe i status portfelowy.

#### Jak działa cache radaru
`PriceService.get_cached_radar_data(...)` czyta z tabeli `radar_cache` gotowe rekordy zawierające m.in.:

- cenę,
- zmianę 1D,
- zmianę 7D,
- zmianę 1M,
- zmianę 1Y,
- najbliższy earnings date,
- ex-dividend date,
- dividend yield,
- timestamp ostatniego odświeżenia.

`PriceService.refresh_radar_data(...)`:

- pobiera świeże kwotowania przez `get_quotes(...)`,
- pobiera dane wydarzeń rynkowych przez `fetch_market_events(...)`,
- robi `INSERT ... ON CONFLICT DO UPDATE` do `radar_cache`,
- zwraca finalnie odczyt z cache.

#### Jak liczone są zmiany procentowe
Źródłem jest `get_quotes(...)` w `price_service.py`, które na podstawie danych z yfinance buduje:

- bieżącą cenę,
- zmianę 1D,
- zmianę 7D,
- zmianę 1M,
- zmianę 1Y.

Frontend nie liczy tych procentów sam — tylko koloruje je i formatuje do `+/-xx.xx%`.

#### Jak działa UI radaru
`InvestmentRadar.tsx`:

- ładuje tabelę przez `fetch('/api/radar')`,
- może wymusić pełne odświeżenie wszystkich tickerów albo pojedynczego tickera,
- pozwala dodawać ticker do obserwowanych,
- pozwala usuwać ticker z watchlisty,
- pozwala kliknąć ticker i otworzyć modal analityczny.

#### Co oznacza auto-refresh w obecnej implementacji
Przełącznik `autoRefreshEnabled` nie ustawia interwału czasowego. Zmienia tylko to, czy przy pobraniu listy frontend woła wariant z `?refresh=1`, czyli czy odczyt ma być z cache czy z wymuszonego odświeżenia źródła danych.

#### Jak działa analiza pojedynczego tickera
`PriceService.get_stock_analysis(...)` zwraca trzy grupy danych:

- **fundamentals** — np. trailing PE, price-to-book, ROE, payout ratio,
- **analyst** — target mean price, recommendation key i potencjalny upside,
- **technicals** — SMA50, SMA200 i RSI14 liczone z historii ~1 roku.

Technikalia są liczone lokalnie na podstawie danych OHLC z yfinance:

- SMA50 = średnia krocząca z 50 sesji,
- SMA200 = średnia krocząca z 200 sesji,
- RSI14 = RSI na podstawie 14-okresowych średnich wzrostów i spadków.

### 7.7 Budżet domowy
Budżet to nie tylko księga przychodów/wydatków. To system sald kont, kopert, wolnej puli i pożyczek wewnętrznych.

#### Kluczowe pojęcia
- **account balance** — realne saldo konta,
- **free pool** — środki nieprzypisane do kopert,
- **envelope balance** — środki zarezerwowane na konkretny cel,
- **loan between envelopes** — czasowe pożyczenie środków z jednej koperty.

#### Jak działa `get_free_pool(...)`
To jedna z podstaw budżetu. Wolna pula jest liczona jako:

`saldo konta - suma aktywnych alokacji / stanów kopert`

Dzięki temu dashboard i transfery do inwestycji mogą korzystać z realnie wolnych środków, a nie z pełnego salda rachunku.

#### Jak działa `get_summary(...)`
Ta funkcja przygotowuje praktycznie cały ekran budżetu:

- wybiera miesiąc docelowy,
- pobiera listę wszystkich kont,
- dla każdego konta liczy `free_pool`,
- dla wybranego konta liczy `total_allocated` i `total_borrowed`,
- pobiera koperty miesięczne i długoterminowe,
- dociąga otwarte pożyczki między kopertami,
- liczy wydatki bieżącego miesiąca per koperta,
- liczy wartości lifetime per koperta,
- buduje `flow_analysis` dla miesiąca.

#### Co zawiera `flow_analysis`
- miesięczny przychód,
- suma transferów do inwestycji,
- savings rate według formuły:

`(transfery do inwestycji + free_pool) / income`

To jest mieszanka przepływu i stanu końcowego, ale taki model jest obecnie zaimplementowany i wykorzystywany w UI.

#### Jak działają podstawowe operacje budżetowe
- `add_income(...)` — podnosi saldo konta i zapisuje przychód,
- `allocate_money(...)` — przesuwa środki z free pool do koperty,
- `spend(...)` — zapisuje wydatek i zmniejsza odpowiednie saldo,
- `transfer_between_accounts(...)` — przenosi środki między kontami z opcjonalnymi kopertami źródłowymi/docelowymi.

#### Transfery budżet ↔ inwestycje
To bardzo ważna integracja między domenami.

`transfer_to_investment(...)`:
- sprawdza konto i portfel,
- opcjonalnie zabiera środki z koperty lub z free pool,
- obniża saldo budżetowe,
- zapisuje transakcję budżetową typu `EXPENSE`,
- zwiększa `current_cash` w portfelu,
- zwiększa `total_deposits` portfela,
- zapisuje inwestycyjną transakcję `DEPOSIT`,
- robi to atomowo w jednej transakcji DB.

`withdraw_from_investment(...)`:
- sprawdza dostępność gotówki w portfelu,
- odejmuje gotówkę z portfela,
- zapisuje `WITHDRAW` po stronie inwestycji,
- zwiększa saldo konta budżetowego,
- zapisuje `INCOME` po stronie budżetu,
- również działa atomowo.

#### Pożyczki między kopertami
`borrow_from_envelope(...)`:
- obniża saldo koperty źródłowej,
- nie rusza salda całego konta,
- zapisuje otwartą pożyczkę i transakcję typu `BORROW`,
- efekt biznesowy: rośnie wolna pula na koncie.

`repay_envelope_loan(...)`:
- sprawdza dostępność free pool,
- pilnuje, żeby nie spłacić więcej niż pozostało,
- oddaje środki na kopertę źródłową,
- aktualizuje status pożyczki,
- zapisuje transakcję `REPAY`.

### 7.8 Kredyty i harmonogramy
To drugi obszar obliczeniowo ciężki po historii portfela.

#### Jak działa wejście do harmonogramu
`routes_loans.py` pobiera szczegóły kredytu, a następnie wywołuje `LoanService.generate_amortization_schedule(...)`.

Może przekazać:

- jednorazową symulowaną nadpłatę (`sim_amount`, `sim_date`),
- miesięczną nadpłatę (`monthly_overpayment`),
- strategię `REDUCE_TERM` lub `REDUCE_INSTALLMENT`.

#### Jak działa `calculate_schedule(...)`
To właściwy silnik harmonogramu.

Dla każdej iteracji miesiąca:

1. ustala aktywną stopę procentową na dany moment,
2. wylicza miesięczną stopę,
3. sprawdza nadpłaty jednorazowe wpadające między poprzednią a bieżącą ratą,
4. dla takich nadpłat wstrzykuje osobne punkty „mid-month” do harmonogramu,
5. wylicza ratę według typu `EQUAL` albo `DECREASING`,
6. opcjonalnie dodaje symulowaną miesięczną nadpłatę dla przyszłych okresów,
7. obcina nadpłatę, jeśli przewyższa pozostały kapitał,
8. aktualizuje saldo i sumę odsetek,
9. przy strategii `REDUCE_INSTALLMENT` przelicza przyszłą ratę na nowo.

#### Co uwzględnia harmonogram
- różne stopy procentowe w czasie,
- nadpłaty zapisane historycznie,
- nadpłaty symulowane,
- raty równe i malejące,
- osobne punkty harmonogramu dla nadpłat w środku miesiąca,
- licznik odsetek zapłaconych do dziś,
- zabezpieczenie przed pętlą nieskończoną przez limit `duration * 2`.

#### Jak używa tego frontend
`LoanSimulator.tsx`:

- ładuje harmonogram po wejściu na ekran,
- renderuje wykres liniowy oraz tabele rat,
- pozwala dodać nadpłatę,
- pozwala dodać zmianę oprocentowania,
- umożliwia analizę wpływu miesięcznych nadpłat i wybranej strategii.

## 8. Model danych — skrót po tabelach

Pełna definicja jest w `backend/database.py`, ale praktycznie najważniejsze grupy tabel to:

### Inwestycje
- `portfolios`,
- `transactions`,
- `holdings`,
- `dividends`,
- `bonds`,
- `stock_prices`,
- `price_cache`,
- `asset_metadata`,
- `symbol_mappings`.

### Radar
- `watchlist`,
- `radar_cache`.

### Kredyty
- `loans`,
- `loan_rates`,
- `loan_overpayments`.

### Budżet
- `budget_accounts`,
- `envelopes`,
- `envelope_categories`,
- `budget_transactions`,
- `envelope_loans` i tabele pomocnicze budżetu.

### PPK
- `ppk_portfolios`,
- `ppk_transactions`.

## 9. Zależności między modułami

To bardzo ważne przy wprowadzaniu zmian:

- **dashboard zależy od budżetu, inwestycji i kredytów**, więc łatwo go nieświadomie zepsuć,
- **budżet i portfele są połączone transferami**, więc zmiany w jednej domenie wpływają na drugą,
- **radar korzysta z cen i holdings**, więc zależy zarówno od watchlisty, jak i inwestycji,
- **import CSV zależy od symbol mappings**, więc problemy z importem często nie siedzą w parserze, tylko w mapowaniach,
- **PPK jest modułem specjalnym**, ale nadal korzysta ze wspólnej infrastruktury aplikacji.

## 10. Gdzie zaczynać analizę zmian

### Gdy problem dotyczy portfela inwestycyjnego
Otwórz w tej kolejności:
1. `frontend/src/pages/PortfolioDetails.tsx`,
2. `frontend/src/api.ts`,
3. `backend/routes_portfolios.py` lub `routes_transactions.py`,
4. `backend/portfolio_core_service.py` lub `portfolio_trade_service.py`,
5. `backend/database.py`.

### Gdy problem dotyczy budżetu
1. `frontend/src/components/budget/BudgetDashboard.tsx`,
2. `frontend/src/api_budget.ts`,
3. `backend/routes_budget.py`,
4. `backend/budget_service.py`,
5. `backend/database.py`.

### Gdy problem dotyczy kredytów
1. `frontend/src/components/loans/LoansDashboard.tsx` lub `LoanSimulator.tsx`,
2. `frontend/src/api_loans.ts`,
3. `backend/routes_loans.py`,
4. `backend/loan_service.py`.

### Gdy problem dotyczy dashboardu głównego
1. `frontend/src/pages/MainDashboard.tsx`,
2. `backend/routes_dashboard.py`,
3. zależne serwisy: `BudgetService`, `PortfolioValuationService`, `LoanService`.

### Gdy problem dotyczy importów XTB lub symboli
1. `frontend/src/pages/SymbolMappingPanel.tsx`,
2. `frontend/src/api_symbol_map.ts`,
3. `backend/routes_imports.py` lub `routes_symbol_map.py`,
4. `backend/portfolio_import_service.py`,
5. `backend/database.py`.

### Gdy problem dotyczy radaru lub danych rynkowych
1. `frontend/src/pages/InvestmentRadar.tsx`,
2. `backend/routes_radar.py`,
3. `backend/watchlist_service.py`,
4. `backend/price_service.py`,
5. `backend/database.py` (`radar_cache`, `watchlist`, `stock_prices`).

## 11. Miejsca o najwyższym ryzyku regresji

Przed większymi zmianami warto pamiętać o tych miejscach:

- dashboard globalny,
- harmonogramy kredytów,
- transfery budżet ↔ inwestycje,
- import CSV i rekonstrukcja historii,
- odświeżanie cen i radar,
- operacje kupna / sprzedaży i aktualizacja holdings.

## 12. Dług techniczny, który warto znać

Najważniejsze obserwacje dla nowej osoby lub AI:

1. warstwa API na frontendzie jest ujednolicona, ale typowanie DTO wymaga dalszego dopracowania (unikanie `any`),
2. backend korzysta z bezpośrednich zapytań SQL bez ORM,
3. logika inwestycyjna jest modularna, ale dashboard agreguje wiele obszarów naraz,
4. repo posiada smoke testy i testy kontraktu API, ale brakuje pełnych testów jednostkowych logiki biznesowej,
5. historia i radar zależą od jakości danych zewnętrznych (yfinance) oraz synchronizacji cache.

## 13. Jak pracować z repo jako AI

Jeśli celem jest szybkie poruszanie się po projekcie, trzymaj się tej procedury:

1. najpierw ustal, którego modułu dotyczy zadanie,
2. znajdź odpowiadający widok React,
3. sprawdź, przez który plik `api*.ts` dochodzi do backendu,
4. otwórz odpowiedni `routes_*.py`,
5. sprawdź czy request jest walidowany i czy rzuca `ValidationError` przy błędach,
6. znajdź serwis domenowy (`portfolio_*_service.py`, `budget_service.py` itd.),
7. jeśli sprawa dotyczy danych lub błędów w zapisie, sprawdź `database.py`,
8. jeśli sprawa dotyczy historii lub wykresów portfela, sprawdź `portfolio_history_service.py`.

Minimalna ścieżka diagnostyczna to zwykle:

`widok frontendu -> moduł API -> route Flask -> service -> database.py`

A przy błędach walidacji lub wyjątkach:

`backend/api/exceptions.py -> global_handler (app.py) -> frontend/src/http.ts`

A dla wykresów inwestycyjnych najczęściej:

`PortfolioDetails.tsx -> endpoint historii -> PortfolioService -> PriceService / stock_prices`

## 14. Jak pracować z repo jako nowy developer

Najlepszy onboarding praktyczny:

1. uruchom backend i frontend lokalnie,
2. sprawdź ekran dashboardu głównego,
3. utwórz przykładowy portfel,
4. dodaj prostą transakcję kupna,
5. sprawdź zakładki historii i wyników,
6. przejdź do budżetu i wykonaj transfer do portfela,
7. utwórz przykładowy kredyt i zobacz harmonogram,
8. przejdź do radaru oraz panelu mapowania symboli,
9. wykonaj próbny import XTB na testowym portfelu.

Po takim przejściu zrozumienie zależności między modułami jest dużo szybsze niż po samym czytaniu kodu.

## 15. Utrzymanie dokumentacji

Aktualny porządek dokumentacji jest celowo prosty:

- `README.md` ma być krótkim punktem wejścia,
- ten plik ma być pełną dokumentacją operacyjną,
- stare, rozproszone opisy architektury lub audyty powinny być kasowane albo scalane, zamiast mnożyć kolejne podobne pliki.

Jeśli w przyszłości pojawi się potrzeba nowego dokumentu, warto najpierw sprawdzić, czy nie lepiej dopisać sekcji tutaj.
