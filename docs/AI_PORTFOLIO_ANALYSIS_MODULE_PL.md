# Dokumentacja modułu AI: analiza portfela (`/api/ai/portfolio-analysis`)

## 1) Cel modułu i zakres odpowiedzialności
Moduł AI odpowiada za **opisową analizę portfela inwestycyjnego** na podstawie realnych danych użytkownika zapisanych w bazie. Funkcja działa jako warstwa interpretacyjna nad danymi transakcyjnymi i cenowymi — nie składa zleceń, nie podejmuje decyzji automatycznie i nie modyfikuje portfela.

Główna rola modułu:
- zebrać stan aktualnych pozycji,
- policzyć najważniejsze wskaźniki kontekstowe (wartość pozycji, PnL, udział w portfelu),
- przekazać je do modelu LLM w uporządkowanym promptcie,
- zwrócić użytkownikowi zwięzłą rekomendacyjną odpowiedź po polsku.

To rozwiązanie jest podpięte pod UI „🤖 Zapytaj AI o portfel”.

---

## 2) Endpoint API
- **Metoda:** `POST`
- **URL:** `/api/ai/portfolio-analysis`
- **Content-Type:** `application/json`

### 2.1 Wejście (request body)
```json
{
  "portfolio_id": 1,
  "question": "Gdzie są największe ryzyka w moim portfelu?"
}
```

### 2.2 Wymagania wejściowe
- `portfolio_id`:
  - wymagane,
  - liczba całkowita,
  - wartość dodatnia (`> 0`).
- `question`:
  - wymagane,
  - niepusty string,
  - po `trim()` nie może być pusty.

### 2.3 Walidacja backendowa
Endpoint korzysta z helperów:
- `require_json_body()` — wymusza poprawne JSON body,
- `require_positive_int(..., 'portfolio_id')` — waliduje `portfolio_id`,
- `require_non_empty_string(..., 'question')` — waliduje pytanie.

Jeśli walidacja nie przejdzie, zwracany jest kontrolowany błąd API (status 4xx/5xx zależnie od scenariusza).

---

## 3) Dane wejściowe do analizy: skąd pochodzą
Dane są pobierane z SQLite zapytaniem łączącym:
- `holdings h` (pozycje portfela),
- `price_cache pc` (ostatnia znana cena po tickerze).

Wybierane kolumny:
- `ticker`,
- `quantity`,
- `total_cost`,
- `sector`,
- `currency`,
- `current_price` (`pc.price`).

Filtry:
- tylko wskazany `portfolio_id`,
- tylko pozycje otwarte: `h.quantity > 0`.

Sortowanie:
- malejąco po `h.total_cost` (największa ekspozycja kosztowa na początku).

Jeżeli zapytanie nie zwróci żadnych pozycji, endpoint odpowiada błędem `portfolio_empty` (HTTP 404).

---

## 4) Co dokładnie moduł wylicza i jak
Po pobraniu rekordów backend przelicza każdą pozycję do wspólnego zestawu metryk.

### 4.1 Normalizacja danych liczbowych
Dla każdego wiersza:
- `quantity = float(row['quantity'] or 0)`
- `total_cost = float(row['total_cost'] or 0)`
- `current_price`:
  - jeśli `pc.price` jest `NULL` → `0.0`,
  - jeśli parsowanie się nie powiedzie (`ValueError`/`TypeError`) → `0.0`.

To zabezpiecza endpoint przed przerwaniem analizy przez pojedynczy wadliwy rekord ceny.

### 4.2 Metryki pozycji
Dla każdej pozycji liczone są:

1. **Aktualna wartość pozycji**
   - `current_value = quantity * current_price`

2. **Niezrealizowany wynik kwotowo**
   - `unrealized_pnl = current_value - total_cost`

3. **Niezrealizowany wynik procentowo**
   - `unrealized_pnl_pct = (unrealized_pnl / total_cost) * 100`, gdy `total_cost > 0`
   - w przeciwnym razie `0.0` (ochrona przed dzieleniem przez zero)

4. **Udział pozycji w portfelu (`weight_pct`)**
   - najpierw liczona jest suma `total_portfolio_value = Σ current_value`,
   - potem:
     - `weight_pct = (current_value / total_portfolio_value) * 100`, gdy `total_portfolio_value > 0`,
     - w przeciwnym razie `0.0`.

### 4.3 Jakie pola trafiają dalej do promptu
Dla każdej pozycji budowany jest obiekt zawierający co najmniej:
- `ticker`,
- `sector` (fallback: `Nieznany`),
- `currency` (fallback: `PLN`),
- `quantity`,
- `total_cost`,
- `current_price`,
- `current_value`,
- `unrealized_pnl`,
- `unrealized_pnl_pct`,
- `weight_pct`.

---

## 5) Budowa promptu: na jakiej podstawie AI odpowiada
Model dostaje 3 główne bloki informacji:
1. **Rola i kontekst** (doradca finansowy analizujący portfel).
2. **Stan portfela** (łączna wartość + lista pozycji z wagą, sektorem i PnL%).
3. **Pytanie użytkownika** (`question`).

Do tego dokładane są instrukcje formatu odpowiedzi:
- odpowiedź po polsku,
- fokus na ryzyku koncentracji/sektora/strat,
- wskazanie pozycji relatywnie mocnych,
- propozycje „dokupić/sprzedać” z uzasadnieniem,
- limit długości do ~300 słów.

### Ważne
AI **nie dostaje pełnej historii transakcji** ani makroekonomii; bazuje głównie na:
- bieżącym przekroju pozycji,
- wagach,
- niezrealizowanych wynikach,
- treści pytania użytkownika.

---

## 6) Wymagania techniczne i środowiskowe
Aby endpoint działał poprawnie, środowisko musi mieć:

1. **Pakiet Python**
   - `google-generativeai` (importowany jako `google.generativeai`).

2. **Zmienną środowiskową**
   - `GEMINI_API_KEY` (klucz API).

3. **Dostęp do bazy danych**
   - tabele `holdings` i `price_cache` z danymi portfela/cen.

### Konfiguracja modelu
- `genai.configure(api_key=..., transport='rest')`
- model: `gemini-3.1-flash-lite-preview`

---

## 7) Kontrakt odpowiedzi
### 7.1 Sukces
```json
{
  "payload": {
    "answer": "...odpowiedź AI..."
  }
}
```

Pole `answer` to tekst gotowy do wyświetlenia w UI.

### 7.2 Błędy kontrolowane
- `portfolio_empty` (404) — brak otwartych pozycji,
- `gemini_unavailable` (500) — brak pakietu `google-generativeai`,
- `gemini_config_error` (500) — brak `GEMINI_API_KEY`,
- `gemini_empty_response` (502) — pusta odpowiedź od modelu,
- `debug_error` (500) — nieobsłużony wyjątek runtime.

---

## 8) Integracja frontendowa
Komponent: `frontend/src/components/ai/PortfolioAIChat.tsx`.

UI zapewnia:
- gotowe szybkie pytania (quick actions),
- ręczne pytanie w `textarea`,
- stan ładowania (`Analizuję portfel...`),
- prezentację błędu po stronie klienta,
- render odpowiedzi zwróconej w `payload.answer`.

Wywołanie:
```ts
http.post('/api/ai/portfolio-analysis', {
  portfolio_id: portfolioId,
  question: trimmed,
})
```

---

## 9) Ograniczenia interpretacyjne i jakość danych
Najważniejsze ograniczenia tej analizy:
- jeżeli ceny w `price_cache` są nieaktualne lub puste, wnioski AI mogą być zaniżone/zaburzone,
- `current_price = 0.0` dla braków danych obniża `current_value`, a więc także `weight_pct`,
- analiza jest punktowa (snapshot), nie uwzględnia pełnej dynamiki historycznej,
- odpowiedź ma charakter informacyjny i edukacyjny (nie jest poradą inwestycyjną).

---

## 10) Przykład użycia (curl)
```bash
curl -X POST "http://localhost:5000/api/ai/portfolio-analysis" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": 1,
    "question": "Jak oceniasz ryzyko koncentracji i co mógłbym zdywersyfikować?"
  }'
```

---

## 11) Powiązane pliki
- Backend endpoint i logika promptu: `backend/routes_ai.py`
- Frontend UI i obsługa odpowiedzi: `frontend/src/components/ai/PortfolioAIChat.tsx`
