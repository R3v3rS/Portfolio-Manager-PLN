# Analiza aktualnego działania importu CSV (XTB)

Ten dokument opisuje **jak obecnie działa import CSV XTB** w aplikacji oraz **jak system obsługuje instrumenty w walutach obcych**. To jest opis stanu aktualnej implementacji, a nie docelowego zachowania biznesowego.

---

## 1. Gdzie zaczyna się import

Import uruchamia użytkownik z widoku szczegółów portfela.

1. Użytkownik klika przycisk **Import XTB CSV**.
2. Frontend otwiera ukryty input `type="file"` z filtrem `.csv`.
3. Po wyborze pliku frontend buduje `FormData` i wysyła `POST` na endpoint:
   - `/{portfolioId}/import/xtb`
4. Backend odbiera plik w `request.files['file']`.
5. Plik jest wczytywany przez `pandas.read_csv(file)`.
6. Następnie dataframe trafia do `PortfolioService.import_xtb_csv(portfolio_id, df)`.

W praktyce cały import biznesowy dzieje się więc w `backend/portfolio_service.py`, a warstwa HTTP tylko przekazuje plik dalej.

---

## 2. Co robi frontend przed i po wysłaniu pliku

### 2.1. Scenariusz podstawowy

Jeżeli backend zwróci sukces:

1. Frontend pokazuje alert `Import successful!`.
2. Wywoływany jest callback `onSuccess()`.
3. Widok portfela odświeża dane.

### 2.2. Scenariusz brakujących mapowań symboli

Jeżeli backend zwróci:

- `success: false`
- `missing_symbols: [...]`

frontend nie traktuje tego jako zwykłego błędu technicznego, tylko uruchamia dodatkowy workflow:

1. Zapamiętuje listę brakujących symboli.
2. Zapamiętuje wybrany plik jako `pendingFile`.
3. Dla każdego brakującego symbolu tworzy roboczy formularz z polami:
   - `ticker`
   - `currency`
4. Domyślna waluta w formularzu to `PLN`.
5. Użytkownik wpisuje ticker i wybiera walutę instrumentu.
6. Frontend zapisuje każde mapowanie przez API `symbolMapApi.create(...)`.
7. Po zapisaniu mapowań frontend zamyka modal.
8. Następnie ponawia import tego samego pliku.

To oznacza, że aplikacja nie próbuje automatycznie zgadywać tickerów z CSV XTB – użytkownik najpierw musi zdefiniować mapowanie `symbol_input -> ticker + currency`.

---

## 3. Jak backend przygotowuje dane do importu

Po wejściu do `PortfolioService.import_xtb_csv(...)` wykonywane są następujące kroki:

1. DataFrame jest sortowany rosnąco po kolumnie `Time`.
   - Dzięki temu import odtwarza historię w kolejności chronologicznej.
2. Otwierana jest transakcja bazy danych przez `db.execute('BEGIN')`.
3. Tworzona jest lista `missing_symbols`, początkowo pusta.
4. Budowana jest mapa nazw kolumn w wersji znormalizowanej do lowercase.
5. Backend próbuje wykryć kolumnę z symbolem instrumentu:
   - najpierw `Symbol`
   - jeżeli jej nie ma, to `Instrument`

Dzięki temu import działa z plikami CSV, które mogą używać jednej z dwóch nazw kolumn.

---

## 4. Jak działa pętla po wierszach CSV

Backend iteruje po wszystkich wierszach dataframe.

Dla każdego wiersza pobierane są podstawowe dane:

1. `Type`
2. `Time`
3. `Amount`
4. `Comment`

Dodatkowo:

- `Type` jest normalizowany do małych liter,
- `Amount` jest zamieniany na `float` po podmianie przecinka na kropkę,
- `Comment` jest zamieniany na pusty string, jeśli jest `NaN`.

Dla każdego wiersza inicjalizowane są także:

- `ticker = None`
- `ticker_currency = 'PLN'`
- `is_stock_operation = typ_lower in {'stock purchase', 'stock sell'}`

To ważne: **waluta instrumentu jest ustawiana domyślnie na PLN**, dopóki import nie znajdzie mapowania symbolu.

---

## 5. Jak rozpoznawany jest ticker instrumentu

Dla operacji giełdowych (`stock purchase`, `stock sell`) backend próbuje rozwiązać symbol z CSV na ticker aplikacji.

### Krok po kroku

1. Z wiersza pobierany jest `symbol_input`:
   - z kolumny `Symbol`, albo
   - z kolumny `Instrument`.
2. `symbol_input` trafia do `PortfolioService.resolve_symbol_mapping(symbol_input)`.
3. Funkcja normalizuje tekst:
   - trim,
   - upper-case,
   - redukcja wielokrotnych spacji.
4. Najpierw wykonywane jest dokładne wyszukanie w tabeli `symbol_mappings`.
5. Jeśli nie ma dokładnego trafienia, backend ładuje wszystkie mapowania i buduje lookup po znormalizowanych symbolach.
6. Jeśli dalej nie ma trafienia, używane jest `difflib.get_close_matches(..., cutoff=0.92)`.
7. Jeśli nadal nie znaleziono mapowania:
   - symbol trafia do `missing_symbols`,
   - import **pomija ten wiersz tymczasowo** i przechodzi dalej.

### Co zawiera mapowanie

Mapowanie zawiera:

- `symbol_input` – symbol z CSV XTB,
- `ticker` – ticker używany przez aplikację i źródła cen,
- `currency` – waluta instrumentu.

Ta waluta nie jest wyliczana automatycznie z rynku podczas importu. Jest brana z tabeli `symbol_mappings`, czyli z wcześniej zapisanego mapowania.

---

## 6. Kiedy import kończy się rollbackiem

Po przejściu całego CSV backend sprawdza, czy lista `missing_symbols` jest pusta.

### Jeśli są brakujące symbole:

1. Backend wykonuje `db.rollback()`.
2. Żadna część importu nie zostaje zapisana.
3. Zwracana jest odpowiedź:
   - `success: false`
   - `missing_symbols: [...]`

To oznacza, że import ma charakter **atomowy**:

- albo zapisuje się cały poprawnie zmapowany plik,
- albo nie zapisuje się nic.

Nawet jeśli część wierszy była już technicznie przetworzona w pętli, końcowy rollback usuwa te zmiany z bieżącej transakcji.

---

## 7. Jak obsługiwane są poszczególne typy operacji z CSV

### 7.1. Deposit / IKE Deposit

Dla typów `deposit` i `ike deposit`:

1. Kwota jest zamieniana na wartość dodatnią przez `abs(amount)`.
2. `portfolios.current_cash` zwiększa się o tę kwotę.
3. Do `transactions` dopisywany jest rekord:
   - `ticker = 'CASH'`
   - `type = 'DEPOSIT'`
   - `quantity = 1`
   - `price = deposit_amount`
   - `total_value = deposit_amount`
   - `date = time`

### 7.2. Free Funds Interest

Dla `free funds interest`:

1. Kwota jest traktowana jako dodatnia wartość wpływu gotówki.
2. `current_cash` rośnie o tę wartość.
3. Do `transactions` trafia rekord typu `INTEREST` z tickerem `CASH`.

### 7.3. Withdrawal

Dla `withdrawal`:

1. Z `current_cash` odejmowane jest `abs(amount)`.
2. Do `transactions` trafia rekord typu `WITHDRAW` z tickerem `CASH`.

### 7.4. Stock Purchase

Dla `stock purchase`:

1. Backend wymaga, aby ticker był już rozwiązany z mapowania.
2. Z pola `Comment` parsowany jest regex:
   - ilość (`qty`)
   - cena jednostkowa z komentarza (`unit_price_from_comment`)
3. `total_cost` jest liczone jako `abs(amount)`.
4. Z `portfolios.current_cash` odejmowany jest `total_cost`.
5. Backend szuka istniejącego `holding` dla `(portfolio_id, ticker)`.
6. Jeżeli pozycja już istnieje:
   - zwiększa ilość,
   - zwiększa koszt całkowity,
   - przelicza średnią cenę zakupu.
7. Jeżeli pozycja nie istnieje:
   - tworzy nowy rekord w `holdings`.
8. Niezależnie od tego dopisywany jest rekord `BUY` do `transactions`.

### 7.5. Stock Sell

Dla `stock sell`:

1. Backend również wymaga poprawnie rozwiązanego tickera.
2. Z pola `Comment` parsowana jest ilość sprzedanych sztuk.
3. `sell_total = abs(amount)`.
4. Cena w transakcji sprzedaży jest liczona jako `sell_total / qty`.
5. `current_cash` zwiększa się o `amount`.
6. Jeżeli istnieje holding:
   - liczony jest `realized_profit = sell_total - (holding['average_buy_price'] * qty)`
   - ilość w holdingu jest zmniejszana,
   - koszt całkowity jest redukowany proporcjonalnie do sprzedanej części.
7. Jeżeli po sprzedaży ilość spadnie do zera lub poniżej, holding jest usuwany.
8. Do `transactions` trafia rekord `SELL`.

---

## 8. Dokładna analiza obsługi walut obcych w imporcie

To jest najważniejsza część z perspektywy CSV i instrumentów zagranicznych.

## 8.1. Źródło prawdy o walucie podczas importu

W aktualnej implementacji waluta instrumentu podczas importu **nie jest pobierana bezpośrednio z pliku CSV** i **nie jest ustalana przez metadata z yfinance w momencie importu**.

Źródłem prawdy jest:

- `symbol_mappings.currency`

Czyli:

1. CSV dostarcza symbol wejściowy (`Symbol` lub `Instrument`).
2. System szuka tego symbolu w `symbol_mappings`.
3. Jeśli znajdzie mapowanie, pobiera z niego:
   - ticker,
   - walutę instrumentu.
4. Jeśli nie znajdzie mapowania, cały import finalnie jest cofany.

Wniosek: **dla instrumentów zagranicznych poprawność waluty zależy od tego, co użytkownik zapisze w mapowaniu symbolu**.

---

## 8.2. Co oznacza `Amount` w imporcie

Kod zakłada, że:

- `Amount` w CSV XTB jest przepływem gotówki w walucie konta aplikacji,
- w tej aplikacji import zakłada konto rozliczane w `PLN`.

Komentarz w kodzie mówi wprost:

- `Amount` to cash movement w walucie konta,
- cena jednostkowa w `Comment` może być w walucie instrumentu, np. EUR.

To rozróżnienie jest kluczowe.

### Przykład logiczny

Jeśli kupujesz ETF notowany w EUR:

- `Comment` może podawać cenę np. `100 EUR`,
- ale `Amount` może wynosić np. `430 PLN`.

To są dwa różne poziomy walutowe:

- waluta rynku instrumentu,
- waluta przepływu gotówkowego w portfelu.

---

## 8.3. Jak import liczy cenę zakupu dla PLN vs waluty obcej

W `stock purchase` występują dwa warianty.

### Wariant A – instrument w PLN

Jeżeli `ticker_currency == 'PLN'`:

1. Import ufa cenie z komentarza.
2. `price = unit_price_from_comment`
3. Do `holdings.average_buy_price` trafia cena jednostkowa z komentarza.

To ma sens, bo zarówno cena instrumentu, jak i przepływ gotówki są w tej samej walucie.

### Wariant B – instrument w walucie obcej

Jeżeli `ticker_currency != 'PLN'`:

1. Import **nie używa bezpośrednio ceny z komentarza jako ceny zapisywanej w holdingu**.
2. Zamiast tego liczy:
   - `price = total_cost / qty`
3. Ponieważ `total_cost = abs(amount)`, a `amount` jest traktowany jako przepływ w PLN, zapisane `price` staje się de facto:
   - **średnim kosztem jednostki wyrażonym w PLN**.

To oznacza, że dla aktywów zagranicznych pole `average_buy_price` w tabeli `holdings` nie przechowuje ceny natywnej (np. w EUR lub USD), tylko koszt jednostkowy już przeliczony na PLN.

### Konsekwencja praktyczna

Dla zagranicznego aktywa:

- `currency` może być np. `EUR`,
- ale `average_buy_price` może być zapisane w PLN na jednostkę.

To jest świadome zachowanie opisane w komentarzu kodu: system chce uniknąć mieszania matematyki między walutą instrumentu i walutą przepływu gotówkowego.

---

## 8.4. Jak oznaczane są zagraniczne holdingi

Podczas importu `stock purchase` system zapisuje do `holdings`:

- `currency = ticker_currency`
- `auto_fx_fees = 1`, jeśli waluta nie jest `PLN`

Czyli każdy holding z mapowaniem np. `USD`, `EUR`, `GBP` automatycznie dostaje znacznik, że należy uwzględniać opłaty FX.

Jeżeli holding już istniał i kolejny import również wskazuje walutę nie-PLN, rekord jest aktualizowany tak, aby:

- zachować poprawną walutę,
- ustawić `auto_fx_fees = 1`.

---

## 8.5. Jak wygląda sprzedaż aktywa zagranicznego

Przy `stock sell` kod działa inaczej niż przy zakupie:

1. `sell_total = abs(amount)` – czyli znowu przepływ gotówki w PLN.
2. `price = sell_total / qty` – cena jednostkowa transakcji sprzedaży także staje się ceną efektywną w PLN/szt.
3. `realized_profit` liczone jest jako:
   - wpływ ze sprzedaży w PLN
   - minus średni koszt zakupu w PLN

Czyli cały realized P/L dla aktywów zagranicznych jest liczony w PLN, a nie w walucie natywnej instrumentu.

To jest spójne z tym, jak zapisuje się koszt zakupu przy imporcie.

---

## 8.6. Gdzie waluta obca zaczyna mieć znaczenie po imporcie

Po imporcie waluta z holdingu jest używana dalej do wyceny bieżącej.

### W `get_holdings(...)`

1. System pobiera aktualną cenę rynkową instrumentu jako `price_native`.
   - Dla np. akcji amerykańskiej będzie to zwykle cena w USD.
2. Następnie pobiera kursy FX do PLN przez `_get_fx_rates_to_pln(...)`.
3. Kurs pobierany jest jako ticker w stylu:
   - `USDPLN=X`
   - `EURPLN=X`
   - `GBPPLN=X`
4. `price_native` jest mnożone przez `fx_rate`, aby policzyć `price_pln`.
5. Wartość pozycji liczona jest w PLN.
6. Dodatkowo dla walut nie-PLN od razu odejmowana jest estymowana opłata FX:
   - `FX_FEE_RATE = 0.005`
   - czyli 0,5% wartości brutto.

### Ważny detal

Jeżeli nie uda się pobrać bieżącej ceny instrumentu, system robi fallback:

1. Bierze `average_buy_price` z holdingu.
2. Dzieli ją przez `fx_rate`, aby oszacować `price_native` do wyświetlenia.

Ponieważ dla aktywów zagranicznych `average_buy_price` jest przechowywane w PLN, to cofnięcie przez kurs FX daje przybliżoną cenę natywną do prezentacji.

---

## 8.7. Jak liczone są kursy FX

Mechanizm jest prosty:

1. System zbiera zestaw walut z holdingów.
2. Usuwa `PLN`.
3. Dla każdej waluty buduje ticker `waluta + PLN + =X`.
   - np. `EURPLN=X`
4. Pobiera ceny tych tickerów przez `PriceService.get_prices(...)`.
5. Jeśli kurs nie zostanie znaleziony, system stosuje fallback `1.0`.

To oznacza, że brak kursu FX nie blokuje działania – ale może zafałszować wycenę, bo waluta obca zostanie wtedy potraktowana jak PLN 1:1.

---

## 8.8. Jak waluta wpływa na historię wartości portfela

W metodach liczących historię portfela i punktowe wyceny historyczne backend robi analogiczny mechanizm:

1. Buduje mapę `ticker -> currency`.
2. Dla walut innych niż PLN dociąga historię tickerów FX typu `EURPLN=X`.
3. Dla każdej daty historycznej liczy:
   - cenę natywną aktywa,
   - kurs FX z tej daty,
   - wartość brutto w PLN,
   - wartość netto po szacowanej opłacie FX.

Czyli waluta obca ma wpływ nie tylko na widok bieżący, ale również na historyczne wykresy portfela.

---

## 9. Najważniejsze konsekwencje obecnej implementacji dla walut obcych

### 9.1. Import jest zależny od ręcznego mapowania

Bez mapowania symbolu import nie zna:

- tickera,
- waluty instrumentu.

Dlatego aktywa zagraniczne muszą mieć poprawnie zapisane mapowanie przed finalnym importem.

### 9.2. Koszt zakupu zagranicznych aktywów jest księgowany w PLN

To najważniejsza właściwość obecnego kodu.

Dla aktywów nie-PLN:

- `average_buy_price` i `total_cost` są de facto prowadzone w PLN,
- mimo że samo pole `currency` nadal przechowuje walutę instrumentu.

### 9.3. Realized profit dla importowanych aktywów zagranicznych też wychodzi w PLN

Zysk zrealizowany po sprzedaży jest liczony na podstawie przepływów pieniężnych w PLN i kosztu historycznego w PLN.

### 9.4. Wycena bieżąca używa ceny rynkowej w walucie natywnej + kursu FX

To oznacza, że po imporcie system przechodzi na model:

- koszt historyczny trzymany w PLN,
- cena bieżąca pobierana w walucie rynku,
- wycena końcowa liczona z przeliczeniem po kursie FX.

### 9.5. System automatycznie dolicza koszt FX dla aktywów nie-PLN

Zarówno w widoku holdings, jak i w części historycznej, dla aktywów zagranicznych stosowane jest domyślne obciążenie 0,5%.

---

## 10. Ryzyka i ograniczenia obecnego podejścia

Poniżej nie opisuję błędów krytycznych, tylko realne konsekwencje aktualnego designu.

### 10.1. Waluta pochodzi z mapowania, nie z rynku ani z CSV

Jeśli użytkownik zapisze złe `currency` w `symbol_mappings`, cały dalszy model wyceny i opłat FX będzie niepoprawny.

### 10.2. Regex parsujący komentarz jest kruchy formatowo

Zakup i sprzedaż opierają się na parsowaniu `Comment` regexem. Jeśli format komentarza w eksporcie XTB się zmieni, import może przestać działać.

### 10.3. Dla `stock sell` używany jest regex z frazą `BUY`

Aktualny kod dla sprzedaży również używa regexu zaczynającego się od `OPEN|CLOSE BUY ...`. Jeżeli komentarz sprzedaży w CSV ma inny wzorzec tekstowy, import sprzedaży może się wyłożyć.

### 10.4. Fallback kursu FX do `1.0`

Jeżeli źródło cen nie odda kursu walutowego, wycena zagranicznego aktywa będzie liczona tak, jakby 1 EUR/USD/GBP = 1 PLN.

### 10.5. Model mieszany: koszt historyczny w PLN, bieżąca cena w walucie natywnej

To działa praktycznie i pozwala liczyć P/L w PLN, ale trzeba pamiętać, że:

- `currency` w holdingu nie oznacza, że `average_buy_price` jest zapisane w tej walucie,
- dla zagranicznych aktywów `average_buy_price` jest w praktyce kosztem PLN per jednostka.

---

## 11. Podsumowanie w skrócie

### Jak działa import CSV dziś

1. Frontend wysyła plik CSV do endpointu importu.
2. Backend wczytuje CSV do Pandas.
3. Import idzie w kolejności po `Time`.
4. Operacje gotówkowe aktualizują `current_cash` i `transactions`.
5. Operacje giełdowe wymagają mapowania symbolu na ticker i walutę.
6. Brak mapowania powoduje rollback całego importu.
7. Po poprawnym mapowaniu import zapisuje holdings i transactions.

### Jak działa waluta obca dziś

1. Waluta jest pobierana z `symbol_mappings.currency`.
2. Dla zakupu aktywa nie-PLN koszt jednostki jest zapisywany w PLN/szt.
3. Dla sprzedaży aktywa nie-PLN wpływ i zysk realizowany też są liczone w PLN.
4. Przy wycenie bieżącej system pobiera cenę rynkową w walucie natywnej i przelicza ją kursem FX do PLN.
5. Dla aktywów nie-PLN system automatycznie uwzględnia szacowaną opłatę FX 0,5%.

---

## 12. Pliki źródłowe, które definiują to zachowanie

Najważniejsze miejsca w kodzie:

- `frontend/src/pages/PortfolioDetails.tsx`
  - UI importu pliku,
  - obsługa brakujących mapowań,
  - zapis mapowań i retry importu.
- `backend/routes.py`
  - endpoint uploadu CSV.
- `backend/portfolio_service.py`
  - główna logika importu,
  - rozwiązywanie mapowań symboli,
  - obsługa kursów FX,
  - wycena holdings i historii portfela.
- `backend/routes_symbol_map.py`
  - CRUD mapowań symboli.
- `backend/database.py`
  - definicja tabeli `symbol_mappings`.

