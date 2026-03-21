# Audit – API / Frontend / Backend Integration

Data audytu: 2026-03-21
Zakres: kontrakt API po refaktorze envelope, warstwa kompatybilności frontend, walidacja, error handling, build.

## Status końcowy

- **Nie jest wszystko OK.**
- **Są edge case’y do poprawy.**
- **Brak jednego oczywistego krytycznego crasha blokującego build, ale są wysokie ryzyka integracyjne**, szczególnie wokół niespójnego kontraktu API i braku wspólnej warstwy unwrap/error parsing.

---

## 1. Frontend – parsowanie odpowiedzi

### 1.1 HTTP layer

**Wynik: FAIL**

Nie wszystkie requesty przechodzą przez jedną warstwę.

Zidentyfikowane wzorce:
- `axios.create(...)` w `frontend/src/api.ts` i `frontend/src/api_loans.ts`.
- wiele bezpośrednich `fetch(...)` w `frontend/src/api_budget.ts`, `frontend/src/api_symbol_map.ts`, `frontend/src/pages/InvestmentRadar.tsx`, `frontend/src/components/budget/BudgetDashboard.tsx`, `frontend/src/components/StockProfilerModal.tsx`.
- `MainDashboard.tsx` używa inline `axios.get('/api/dashboard/global-summary')`.

**Nie znaleziono implementacji ani użycia:**
- `extractPayload`
- `extractErrorMessage`
- `parseJsonApiResponse`

Wniosek: frontend nie ma jednej, spójnej warstwy HTTP po refaktorze kontraktu API.

### 1.2 unwrap payload

**Wynik: FAIL**

Nie znaleziono centralnego unwrap dla wariantów:
- `payload`
- `data`
- goły JSON fallback

Aktualny frontend zwykle zakłada jeden konkretny kształt odpowiedzi:
- `setData(res.data)`
- `return res.json()`
- `setRadarItems(data)`
- `setSummary(data)`

To oznacza, że przejście backendu na envelope typu `{ payload: ... }` lub `{ data: ... }` złamie część UI bez warstwy kompatybilności.

### 1.3 undefined / null crash

**Wynik: MIXED / RYZYKO**

Dobre praktyki są obecne miejscami (`data?.field`, `??`, warunkowe renderowanie), ale nie są konsekwentne.

Najważniejsze ryzyka:
- `MainDashboard.tsx` po `if (!data) return null;` zakłada pełną obecność zagnieżdżonych pól (`data.assets_breakdown.budget_cash`, `data.quick_stats.free_pool` itd.). Jeśli backend zwróci envelope lub niepełny obiekt, komponent padnie.
- `BudgetDashboard.tsx` po `setSummary(data)` zakłada `data.accounts.length`, `summary.accounts.map(...)`, `summary.loans.map(...)` i liczne inne `.map(...)` bez normalizacji odpowiedzi.
- `InvestmentRadar.tsx` zakłada, że `response.json()` zwraca tablicę i robi później `radarItems.map(...)`.

Nie znalazłem jednego globalnego guard layer, który zabezpieczałby UI przed `null`, pustym body albo envelope bez payload.

### 1.4 Dashboard (najważniejsze)

**Wynik: FAIL względem nowego kontraktu**

Endpoint `/api/dashboard/global-summary` jest obecnie konsumowany jako surowy obiekt (`setData(res.data)`), a nie unwrapowany.

Dodatkowo endpoint backendowy zwraca pola:
- `net_worth`
- `total_assets`
- `total_liabilities`
- `liabilities_breakdown`
- `assets_breakdown`
- `quick_stats`

**Nie zwraca** pól oczekiwanych z checklisty:
- `total_value`
- `portfolio_value`
- `budget_summary`

Wniosek: jeśli checklista odzwierciedla nowy oczekiwany kontrakt, to dashboard jest obecnie z nim niespójny.

---

## 2. Frontend – obsługa błędów

### 2.1 error envelope

**Wynik: FAIL**

Frontend nie ma wspólnej obsługi struktury:

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {}
  }
}
```

Aktualne miejsca zwykle oczekują prostego:
- `{ error: "..." }`
- albo po prostu `response.ok === false`
- albo success/failure w stylu `{ success: false, missing_symbols: [...] }`

### 2.2 extractErrorMessage

**Wynik: FAIL**

Nie znaleziono wspólnego helpera typu `extractErrorMessage`.

Najczęstsze wzorce:
- `throw new Error('Failed to ...')`
- `const message = data.error || 'Request failed'`
- `alert(err.message)`

Brakuje obsługi:
- `error.message`
- `error.details`
- sensownego fallbacku dla zagnieżdżonego envelope error

### 2.3 XTB import

**Wynik: CZĘŚCIOWO DZIAŁA, ale nie z nowym error envelope**

Scenariusz `missing_symbols` działa tylko dla aktualnego starego kontraktu:
- backend zwraca `{ success: false, missing_symbols: [...] }` przy HTTP 400,
- frontend w `PortfolioDetails.tsx` sprawdza właśnie ten kształt.

Ryzyka:
- brak `details.missing_symbols` support,
- brak wspólnego parsera błędu,
- brak zgodności z docelowym error envelope.

Jeśli backend przejdzie na:

```json
{
  "error": {
    "message": "...",
    "details": { "missing_symbols": [...] }
  }
}
```

obecny UI nie wyświetli brakujących mapowań poprawnie.

---

## 3. Backend – kontrakt API

### 3.1 Success response

**Wynik: FAIL**

Nie ma dowodu, że wszystkie endpointy używają `success_response(...)`.

Wręcz przeciwnie: nie znalazłem helpera `success_response`, a backend zwraca mieszankę:
- surowe listy `jsonify([...])`
- surowe obiekty `jsonify({...})`
- obiekty z `message`
- obiekty z `transactions`, `history`, `limits`, itd.

### 3.2 Spójność payload

**Wynik: FAIL**

Są surowe listy i surowe dicty bez envelope, np.:
- `GET /api/loans/` → lista pożyczek,
- `GET /api/budget/categories` → lista kategorii,
- `GET /api/budget/envelopes` → lista kopert,
- `GET /api/radar` → lista lub `[]`,
- `GET /api/dashboard/global-summary` → surowy obiekt.

### 3.3 Null payload

**Wynik: NIE STWIERDZONO literalnego `{ payload: null }`, ale problem jest szerszy**

Nie znalazłem odpowiedzi z literalnym `payload: null`, ponieważ backend w ogóle nie stosuje spójnego envelope payload.

Problem praktyczny: frontend oczekuje obiektów/tablic bezpośrednio, więc migracja do envelope bez warstwy kompatybilności będzie ryzykowna nawet bez `payload: null`.

---

## 4. Backend – błędy

### 4.1 Typy błędów

**Wynik: FAIL**

Nie znalazłem wdrożonej warstwy domenowych wyjątków typu:
- `ValidationError` → 400
- `BusinessError` → 400
- `NotFoundError` → 404
- `ForbiddenError` → 403
- `Exception` → 500

Aktualnie dominuje:
- `ValueError` w serwisach,
- lokalne `except Exception as e` w route’ach,
- ręczne mapowanie statusów zależnie od stringa lub kontekstu.

### 4.2 error.details

**Wynik: FAIL**

Nie ma spójnego `error.details`.

W większości endpointów błąd ma postać:
- `{ "error": "tekst" }`

Brakuje gwarancji, że `details`:
- istnieje,
- jest słownikiem,
- nigdy nie jest `None`.

### 4.3 logowanie błędów

**Wynik: CZĘŚCIOWO OK**

Globalny handler w `backend/app.py` loguje stacktrace przez `logging.exception("Unhandled exception")`.

Ale wiele route’ów przechwytuje `Exception` lokalnie i od razu zwraca `jsonify({'error': str(e)})`, bez jawnego logowania stacktrace. To oznacza, że część błędów biznesowych/operacyjnych może nie zostawić pełnego śladu w logach.

---

## 5. Backend ↔ Frontend compatibility

### 5.1 Compatibility layer

**Wynik: FAIL**

Nie znalazłem warstwy kompatybilności działającej dla:
- `payload`
- `data`
- starego formatu

Obie strony nadal są mocno związane z „aktualnym lokalnym” formatem endpoint-by-endpoint.

### 5.2 Edge cases

**Wynik: FAIL / RYZYKO**

Brakuje centralnej obsługi dla:
- pustego response body,
- braku payload,
- błędu bez `message`.

Przykłady:
- `api_budget.ts` robi `res.json()` bez ochrony przed pustą odpowiedzią,
- `InvestmentRadar.tsx` i `BudgetDashboard.tsx` zakładają określony shape JSON,
- `api_symbol_map.ts` ma lokalny parser, ale obsługuje tylko `{ error: string }`.

---

## 6. Build / runtime

### 6.1 Build

**Wynik: PASS**

`npm --prefix frontend run build` przechodzi poprawnie.

### 6.2 Runtime

**Wynik: NIEZWERYFIKOWANE E2E, ale są realne ryzyka runtime**

Nie uruchamiałem pełnego manualnego smoke testu UI w przeglądarce w tym audycie.

Na podstawie kodu najbardziej prawdopodobne problemy runtime po zmianie kontraktu API to:
- biały ekran lub pusty widok w dashboardzie,
- `undefined`/`map is not a function` w ekranach oczekujących tablicy,
- silent crash po odpowiedzi niezgodnej z oczekiwanym shape,
- nieczytelne komunikaty błędów (`Failed to fetch ...` bez szczegółów).

---

## 7. Lint / typowanie

### 7.1 TypeScript

**Wynik: RYZYKO**

W kodzie są użycia `any`, m.in. w:
- `LoansDashboard.tsx`
- `SellModal.tsx`
- `TransferModal.tsx`
- `TransactionModal.tsx`
- `BudgetDashboard.tsx`
- `PortfolioDetails.tsx`
- `PortfolioProfitChart.tsx`
- `PerformanceHeatmap.tsx`

HTTP layer nie jest spójnie typowany; część funkcji zwraca `res.json()` bez walidacji runtime shape.

### 7.2 unused vars / martwy kod

**Wynik: NIEPEŁNA WERYFIKACJA**

Nie uruchamiałem osobno `eslint`, więc nie potwierdzam listy nieużywanych importów/zmiennych.

Natomiast już po samym przeglądzie widać martwy architektonicznie kierunek: równoległe współistnienie wielu mini-warstw API (`api.ts`, `api_loans.ts`, `api_budget.ts`, `api_symbol_map.ts`, requesty inline w komponentach).

---

## 8. Testy – szybki check

### 8.1 API

**Wynik: NIEZWERYFIKOWANE AUTOMATEM**

Nie wykonałem requestów integracyjnych dla:
- buy (zły payload)
- sell (zły payload)
- transfer (edge cases)

Natomiast z kodu wynika, że endpointy zwykle polegają na bezpośrednim dostępie do `request.json[...]`, więc zły payload może prowadzić do mało spójnych błędów 400 lub 500 zależnie od miejsca.

### 8.2 UI

**Wynik: CZĘŚCIOWO TYLKO BUILD**

Potwierdzone:
- aplikacja buduje się poprawnie.

Niepotwierdzone manualnie:
- Dashboard się ładuje end-to-end,
- PortfolioDetails działa end-to-end,
- Radar działa end-to-end.

---

## 9. Najważniejsze red flagi

### Potwierdzone red flagi

- **brak wspólnej warstwy HTTP / compatibility layer**,
- **brak spójnego envelope success/error po backendzie**,
- **frontend nie unwrapuje `payload` / `data`**,
- **XTB import nie wspiera `error.details.missing_symbols`**,
- **dashboard nie jest zgodny z checklistą pól `total_value`, `portfolio_value`, `budget_summary`**,
- **wiele miejsc zakłada konkretny shape JSON i może paść po zmianie kontraktu**.

### Niepotwierdzone, ale bardzo prawdopodobne po zmianie kontraktu

- biały ekran bez czytelnego błędu,
- `undefined` w UI,
- crash przy pustych danych lub tablicy zastąpionej envelope,
- error bez sensownego message dla użytkownika.

---

## Priorytet poprawek

### P1 – krytyczne architektonicznie
1. Dodać wspólną warstwę frontend API z:
   - `parseJsonApiResponse`,
   - `extractPayload`,
   - `extractErrorMessage`.
2. Przepiąć wszystkie requesty (`axios` i `fetch`) przez jedną warstwę.
3. Ustalić jeden backendowy kontrakt success/error dla wszystkich endpointów.

### P2 – ważne funkcjonalnie
1. Ujednolicić `/api/dashboard/global-summary` do docelowego kontraktu albo zaktualizować frontend do realnego kontraktu.
2. Przenieść `missing_symbols` do `error.details` i dodać kompatybilność frontend dla starego i nowego formatu.
3. Dodać normalizację pustych odpowiedzi i fallbacki dla list/obiektów.

### P3 – jakość i bezpieczeństwo refaktoru
1. Ograniczyć `any` w TypeScript.
2. Dodać smoke testy integracyjne dla dashboard / radar / portfolio details.
3. Dodać testy backendowe dla błędnych payloadów buy/sell/transfer.

---

## Finalna ocena

**Wniosek:** projekt po refaktorze wygląda na **częściowo działający**, ale **nie jest gotowy na pełne przejście na nowy kontrakt API envelope** bez dalszych zmian. Największy problem to niespójność obu stron integracji: backend nadal zwraca wiele różnych shape’ów, a frontend nie ma centralnego parsera success/error/compatibility.
