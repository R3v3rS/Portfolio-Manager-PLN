# Projekt wielowalutowości (IKE + konto akcyjne)

## Cel
Wprowadzić obsługę transakcji w walutach obcych (EUR, USD) przy zachowaniu **waluty bazowej PLN** do raportowania, limitów IKE/IKZE, wykresów i zyskowności.

## Założenia biznesowe
- Portfel ma jedną walutę bazową: `PLN`.
- Instrument (ticker) ma walutę notowania: np. `USD`, `EUR`, `PLN`.
- Transakcja ma walutę wykonania (`trade_currency`) i kurs FX (`fx_rate`) użyty do przeliczenia na PLN.
- Prowizja 0.5% jest już wspierana i powinna być księgowana dla każdego BUY/SELL.
- W IKE/IKZE limit wpłat liczony jest wyłącznie po `PLN` (czyli po przeliczeniu wpłat i transferów gotówki do PLN, jeśli kiedyś pojawią się walutowe wpłaty).

## Model danych – minimalne rozszerzenie

### 1) `portfolios`
Dodać kolumny:
- `base_currency TEXT NOT NULL DEFAULT 'PLN'`

### 2) `holdings`
Dodać kolumny:
- `instrument_currency TEXT NOT NULL DEFAULT 'PLN'`
- `avg_buy_price_native REAL NOT NULL DEFAULT 0` (średnia cena w walucie instrumentu)
- `avg_buy_fx_rate REAL NOT NULL DEFAULT 1` (średni kurs PLN za 1 jednostkę waluty instrumentu)

### 3) `transactions`
Dodać kolumny:
- `trade_currency TEXT NOT NULL DEFAULT 'PLN'`
- `price_native REAL` (cena jednostkowa w walucie instrumentu)
- `gross_value_native REAL` (wartość bez prowizji w walucie transakcji)
- `commission_native REAL NOT NULL DEFAULT 0`
- `commission_pln REAL NOT NULL DEFAULT 0`
- `fx_rate REAL NOT NULL DEFAULT 1` (PLN za 1 walutę transakcji)
- `total_value_pln REAL NOT NULL DEFAULT 0` (wartość księgowa transakcji po FX)
- `realized_profit_pln REAL` (zrealizowany wynik tylko w PLN)

### 4) (Opcjonalnie, etap 2) `cash_ledger`
Aby mieć prawdziwe subkonta walutowe:
- `portfolio_id`, `currency`, `balance`

Na start można zostać przy gotówce w PLN i księgowaniu wszystkich ruchów gotówki po przeliczeniu FX.

## Logika księgowa

### BUY (np. akcja w USD)
Wejście:
- `qty`, `price_native`, `trade_currency=USD`, `fx_rate`

Wzory:
- `gross_native = qty * price_native`
- `commission_native = gross_native * 0.005`
- `total_native = gross_native + commission_native`
- `total_pln = total_native * fx_rate`

Księgowanie:
- `current_cash_pln -= total_pln`
- holding:
  - `quantity += qty`
  - `total_cost_pln += total_pln`
  - `avg_buy_price_pln = total_cost_pln / quantity`
  - aktualizuj pomocniczo `avg_buy_price_native` i `avg_buy_fx_rate`
- transakcja zapisuje wszystkie pola native + PLN.

### SELL (np. akcja w EUR)
Wejście:
- `qty`, `price_native`, `trade_currency=EUR`, `fx_rate`

Wzory:
- `gross_native = qty * price_native`
- `commission_native = gross_native * 0.005`
- `net_native = gross_native - commission_native`
- `net_pln = net_native * fx_rate`
- `cost_basis_pln = qty * avg_buy_price_pln`
- `realized_profit_pln = net_pln - cost_basis_pln`

Księgowanie:
- `current_cash_pln += net_pln`
- redukcja `holding.quantity`
- redukcja `holding.total_cost_pln` o koszt sprzedanego pakietu
- zapis `realized_profit_pln` w transakcji.

## Wycena bieżąca
Dla każdego holdingu:
- pobierz cenę rynkową w walucie instrumentu (`market_price_native`)
- pobierz kurs FX (`fx_rate_current`) dla pary waluta->PLN
- `current_value_pln = quantity * market_price_native * fx_rate_current`
- `unrealized_pln = current_value_pln - total_cost_pln`

Dzięki temu dashboard i wszystkie metryki pozostają spójne (100% w PLN).

## Źródło kursów FX
- Dodać prosty serwis `FxRateService`:
  - cache dzienny kursów NBP (EUR/PLN, USD/PLN) albo fallback do dostawcy rynkowego,
  - API: `get_rate(currency: str, date: Optional[str]) -> float`.
- Dla transakcji historycznej:
  - preferuj kurs z daty transakcji,
  - jeśli brak (weekend/święto) użyj ostatniego dostępnego dnia roboczego.

## API kontrakt (propozycja)

### POST `/api/portfolio/transaction`
Dodać pola wejściowe:
- `trade_currency`
- `price_native`
- `fx_rate` (opcjonalny: jeśli brak, backend wylicza sam)

Backend zawsze zwraca i zapisuje:
- `total_value_pln`
- `commission_pln`
- `realized_profit_pln` (dla SELL)

## UI/UX
- Formularz BUY/SELL:
  - ticker
  - ilość
  - cena w walucie instrumentu
  - waluta transakcji (auto z instrumentu, ale edytowalna)
  - kurs FX (auto, z możliwością ręcznej korekty)
  - podgląd: prowizja, wartość native, wartość PLN
- Lista transakcji:
  - pokazywać obie waluty (`native` i `PLN`).
- Widok portfela:
  - główne sumy i wykresy w PLN,
  - detal holdingu: cena native + przeliczenie PLN.

## Migracja istniejących danych
1. Dodać nowe kolumny z bezpiecznymi `DEFAULT`.
2. Dla starych rekordów:
   - `trade_currency='PLN'`
   - `fx_rate=1`
   - `total_value_pln = total_value` (dotychczasowa kolumna)
3. Backfill dla holdingów:
   - `instrument_currency='PLN'` jeśli brak mapowania symbolu.
4. Stopniowo przełączyć backend na nowe pola i zostawić kompatybilność wsteczną przez 1-2 wersje.

## Plan wdrożenia (iteracyjny)

### Etap 1 (najmniejsze ryzyko)
- Dodać kolumny DB + migrację kompatybilną.
- Rozszerzyć BUY/SELL o `trade_currency`, `price_native`, `fx_rate`.
- Księgować wszystko finalnie do PLN.

### Etap 2
- Wycena bieżąca z aktualnym FX.
- Widoki UI z dualnym formatem kwot.

### Etap 3
- (Opcjonalnie) prawdziwe subkonta walutowe i walutowe wpłaty/wypłaty.

## Ryzyka i jak ograniczyć
- **Niespójność kursów historycznych**: zapisywać kurs bezpośrednio w transakcji (nie liczyć „w locie”).
- **Błędy zaokrągleń**: stosować `Decimal` do obliczeń księgowych i zaokrąglenie bankowe na końcu operacji.
- **Wydajność wyceny**: cache kursów FX per dzień.

## Kryteria akceptacji
- BUY/SELL dla EUR/USD zapisuje wartości native i PLN.
- Prowizja 0.5% liczona przy każdej transakcji i poprawnie wpływa na wynik.
- Zysk zrealizowany i niezrealizowany raportowany w PLN.
- Limity IKE/IKZE nie zmieniają logiki i pozostają liczone w PLN.
