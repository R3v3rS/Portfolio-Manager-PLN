# PROJECT GUIDE (Źródło Prawdy)

## 1. Cel
Ten dokument jest autorytatywną referencją techniczną zachowania modułu portfeli w aktualnej implementacji backendu.

Zakres:
- model własności portfel / sub-portfel,
- semantyka transakcji,
- logika holdings i cost basis,
- agregacja parent/child,
- wycena i FX,
- kluczowe edge-case’y i ryzyka techniczne.

---

## 2. Model Danych i Zasady Własności

### 2.1 Hierarchia portfeli
- `portfolios.parent_portfolio_id IS NULL` => **portfel rodzic (parent)**.
- `portfolios.parent_portfolio_id = <id>` => **portfel dziecko (sub-portfolio)**.

### 2.2 Kanoniczne pola własności
Dla zapisów inwestycyjnych (`BUY`, `SELL`, `DEPOSIT`, `WITHDRAW`, `DIVIDEND`, `INTEREST`) backend zapisuje:
- `transactions.portfolio_id` = **id portfela rodzica** (właściciel drzewa),
- `transactions.sub_portfolio_id` = **zakres dziecka** lub `NULL` dla zakresu własnego parenta.

Analogicznie dla `holdings` i `dividends`:
- `portfolio_id` = właściciel rodzic,
- `sub_portfolio_id` = zakres dziecka lub `NULL` dla zakresu parent-own.

### 2.3 Interpretacja zakresu
- Zakres własny parenta: `sub_portfolio_id IS NULL`.
- Zakres dziecka: `sub_portfolio_id = <child_id>`.
- Zakres zagregowany parenta: suma zakresu własnego + wszystkich dzieci.

---

## 3. Semantyka Transakcji (Deterministyczna)

## 3.1 Konwencja znaku przepływu gotówki
`transactions.total_value` jest zapisywane jako wartość nieujemna. Kierunek wynika z typu transakcji.

Delta gotówki po typie:
- `DEPOSIT` -> `+total_value`
- `INTEREST` -> `+total_value`
- `DIVIDEND` -> `+total_value`
- `SELL` -> `+total_value`
- `WITHDRAW` -> `-total_value`
- `BUY` -> `-total_value`

Dla importu XTB normalizacja jest jawna:
- `tx_total = abs(amount)`

## 3.2 Reguła BUY
Dla `quantity`, `price`, `commission`:
- `total_value = quantity * price + commission`
- gotówka jest zmniejszana w docelowym zakresie (parent-own lub child)
- aktualizacja holdingu:
  - `new_quantity = old_quantity + buy_qty`
  - `new_total_cost = old_total_cost + buy_total`
  - `average_buy_price = new_total_cost / new_quantity`

## 3.3 Reguła SELL (average-cost basis)
Dla `sell_qty`, `sell_price`:
- `sell_total = sell_qty * sell_price`
- `cost_basis = sell_qty * average_buy_price`
- `realized_profit = sell_total - cost_basis`
- gotówka jest zwiększana w docelowym zakresie
- aktualizacja holdingu:
  - `quantity -= sell_qty`
  - `total_cost -= sell_qty * average_buy_price`

**Wymagana reguła cost basis:**
`total_cost -= sold_qty * avg_price`

Gdy pozostała ilość jest efektywnie zerowa (`<= 1e-6`), holding jest usuwany (lub odbudowywany jako zero w ścieżce audytu).

## 3.4 DEPOSIT / WITHDRAW / DIVIDEND / INTEREST
- `DEPOSIT`: zwiększa `current_cash` i `total_deposits` w docelowym zakresie.
- `WITHDRAW`: zmniejsza `current_cash` w docelowym zakresie (po walidacji środków).
- `DIVIDEND`: zapisuje rekord dywidendy i zwiększa gotówkę.
- `INTEREST`: zgodnie z kontraktem API ścieżki manualnej jest parent-only.

---

## 4. Model Holdings i Cost Basis

Każda otwarta pozycja w zakresie przechowuje:
- `quantity`
- `total_cost` (PLN book cost po BUY/SELL)
- `average_buy_price = total_cost / quantity`

### 4.1 Holdings jako stan pochodny
Backend zawiera mechanizmy repair/audit, które deterministycznie odbudowują holdings z transakcji. Oznacza to, że transakcje są ledgerem źródłowym, a holdings stanem materializowanym.

### 4.2 Zachowanie silnika odbudowy
W trakcie odbudowy:
- transakcje przetwarzane są po `date/id`,
- BUY/SELL aktualizują `quantity` i `total_cost`,
- SELL używa average-cost basis,
- oversell w odbudowie deterministycznej zgłasza błąd,
- porównanie rebuilt vs stored używa tolerancji:
  - ilość: epsilon `1e-6`,
  - total_cost / cash: `0.01 PLN`.

---

## 5. Reguły Agregacji (Parent vs Child)

## 5.1 Agregacja holdings dla widoku parenta
Dla agregatu parenta backend grupuje po `(ticker, currency)` i liczy:
- `sum_quantity = SUM(quantity)`
- `sum_total_cost = SUM(total_cost)`
- `avg_price = SUM(total_cost) / SUM(quantity)` (gdy quantity > 0)

**Wymagana reguła agregacji:**
`parent_avg_price = SUM(total_cost) / SUM(quantity)`

## 5.2 Agregacja wartości portfela
Dla parenta z aktywnymi dziećmi:
- wartość parenta = wartość zakresu własnego + suma wartości dzieci,
- breakdown zwraca wkład parent-own i każdego dziecka.

## 5.3 Zachowanie listowania transakcji
- Zapytanie child `portfolio_id` zwraca wyłącznie zakres tego dziecka.
- Zapytanie parent `portfolio_id` zwraca historię zagregowaną (parent-own + children).

---

## 6. Zasady Wyceny, Ceny i FX

## 6.1 Jednostki cen
- Cena rynkowa instrumentu jest pobierana w walucie natywnej.
- Wycena konwertuje do PLN przez mapę kursów FX (`currency -> currencyPLN`).

## 6.2 Wzór wartości holdingu
- `gross_current_value = quantity * current_price_pln`
- gdy waluta != PLN, może być zastosowana estymowana opłata FX przy sprzedaży
- `current_value = gross_current_value - estimated_sell_fee`
- `profit_loss = current_value - total_cost`

## 6.3 Fallback przy braku ceny live
Jeśli brak ceny live, backend stosuje cenę implikowaną wyliczoną ze `stored average buy price` i kontekstu FX.

## 6.4 Flagi FX
- Instrumenty nie-PLN są oznaczane pod ścieżkę opłat FX (`auto_fx_fees`).
- Obsługa FX jest deterministyczna, ale część ścieżek runtime nadal korzysta z `float` (patrz: Ryzyka).

---

## 7. Reguły Importu (XTB)

## 7.1 Ekstrakcja ilości z komentarza
Dla operacji giełdowych z komentarzy XTB:
- przy składni ułamkowej parser bierze licznik,
- przykład: `"1/5" -> qty = 1`.

## 7.2 Model wykrywania duplikatów
Import wykrywa duplikaty dwustopniowo:
- duplikat wewnątrz pliku (`file_internal_duplicate`),
- duplikat względem bazy (`database_duplicate`).

Akceptacja konfliktów wymaga jawnego potwierdzenia `row-hash` (`confirmed_hashes`).

## 7.3 Normalizacja kwot
Wszystkie total-e transakcji z importu są normalizowane do wartości nieujemnej:
- `tx_total = abs(amount)`

Kierunek przepływu wynika później z typu transakcji.

---

## 8. Edge Cases
- Partial sell używa average-cost reduction (nie FIFO/LIFO).
- Parent może mieć pozycje własne (`sub_portfolio_id IS NULL`), a dzieci mogą mieć osobne pozycje na tym samym tickerze/walucie.
- Zagregowane holdings parenta mogą scalać wiele pozycji do jednego wyniku ważonego per `(ticker, currency)`.
- Wybrane przepływy gotówki child uwzględniają ścieżkę kompatybilności legacy.
- Zarchiwizowany child nie może być celem nowego trade/deposit/withdraw/dividend assignment.

---

## 9. Znane Ryzyka Techniczne
- **Dług precyzji float:** wiele obliczeń runtime używa `float`; audyt/odbudowa używa decimal quantization -> mieszane granice precyzji.
- **Ryzyko dryfu zaokrągleń:** powtarzane partial selle i rekalkulacje średniej mogą kumulować odchylenia centowe.
- **Ryzyko niejednoznaczności FX:** book-cost w PLN może zależeć od importowanych/założonych kursów; historyczne założenia FX mogą różnić się od statementów brokera.
- **Ryzyko regresji agregacji:** logika agregatu parenta występuje w wielu serwisach; przyszłe zmiany zapytań/schematu mogą rozjechać sumy.
- **Ryzyko wydajności historii:** dynamiczna rekonstrukcja dzienna może być kosztowna dla dużych ledgerów.

---

## 10. Terminologia (Ujednolicona)
- **Parent portfolio**: portfel z `parent_portfolio_id IS NULL`.
- **Child / sub-portfolio**: portfel z `parent_portfolio_id = parent.id`.
- **Scope**: `(portfolio_id parent_owner, sub_portfolio_id nullable child selector)`.
- **Parent-own scope**: `sub_portfolio_id IS NULL` pod ownerem-parentem.
- **Aggregate parent scope**: parent-own + wszystkie child scopes.

