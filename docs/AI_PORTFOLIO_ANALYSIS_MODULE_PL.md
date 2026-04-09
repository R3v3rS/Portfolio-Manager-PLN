# Dokumentacja modułu AI: analiza portfela (`/api/ai/portfolio-analysis`)

## 1. Cel modułu
Moduł AI umożliwia szybkie uzyskanie opisowej analizy portfela inwestycyjnego na podstawie aktualnych pozycji użytkownika. Funkcja jest dostępna z poziomu UI (sekcja **„🤖 Zapytaj AI o portfel”**) i odpowiada po polsku, skupiając się na ryzyku, jakości pozycji oraz potencjalnych kierunkach zmian.

W praktyce moduł:
- pobiera otwarte pozycje (`quantity > 0`) z bazy,
- wylicza metryki pomocnicze dla każdej pozycji,
- buduje prompt z kontekstem portfela,
- wysyła prompt do modelu Gemini,
- zwraca odpowiedź tekstową do frontendu.

---

## 2. Endpoint API
- **Metoda:** `POST`
- **Ścieżka:** `/api/ai/portfolio-analysis`
- **Content-Type:** `application/json`

### 2.1. Body request
```json
{
  "portfolio_id": 1,
  "question": "Gdzie są największe ryzyka w moim portfelu?"
}
```

### 2.2. Wymagane pola
- `portfolio_id` — dodatnia liczba całkowita,
- `question` — niepusty string (po przycięciu białych znaków).

Walidacja wejścia realizowana jest przez helpery backendowe:
- `require_json_body`,
- `require_positive_int`,
- `require_non_empty_string`.

---

## 3. Źródło danych i obliczenia
Endpoint wykonuje zapytanie SQL łączące:
- `holdings` (pozycje portfela),
- `price_cache` (aktualna cena po tickerze).

Filtrowane są tylko aktywne pozycje (`h.quantity > 0`) dla wskazanego `portfolio_id`.

Dla każdej pozycji backend wylicza:
- `current_value = quantity * current_price`,
- `unrealized_pnl = current_value - total_cost`,
- `unrealized_pnl_pct = (unrealized_pnl / total_cost) * 100` (gdy `total_cost > 0`),
- `weight_pct` — udział pozycji w wartości całego portfela.

Jeżeli `current_price` jest `NULL` lub nie daje się sparsować, backend przyjmuje `0.0`, aby nie przerywać analizy błędem konwersji.

---

## 4. Budowa promptu i zachowanie modelu
Prompt zawiera:
1. krótką rolę modelu („doradca finansowy analizujący portfel”),
2. listę pozycji z sektorami, wagami i niezrealizowanym PnL,
3. pytanie użytkownika,
4. instrukcje dot. formatu odpowiedzi.

### Wymuszenia w promptcie
Model dostaje jawne wytyczne, by:
- odpowiedzieć konkretnie po polsku,
- wskazać największe ryzyka (koncentracja, sektor, strata),
- wskazać pozycje wyglądające dobrze,
- zasugerować co ewentualnie dokupić/sprzedać wraz z uzasadnieniem,
- zmieścić się w limicie ~300 słów.

---

## 5. Konfiguracja integracji Gemini
Wymagania runtime:
- zainstalowany pakiet `google-generativeai`,
- ustawiona zmienna środowiskowa `GEMINI_API_KEY`.

Konfiguracja po stronie backendu:
- transport: `rest`,
- model: `gemini-3.1-flash-lite-preview`.

Jeśli konfiguracja jest niekompletna, endpoint zwraca kontrolowany błąd API (szczegóły niżej).

---

## 6. Kontrakt odpowiedzi
### 6.1. Sukces
```json
{
  "payload": {
    "answer": "...tekst odpowiedzi AI..."
  }
}
```

### 6.2. Typowe błędy
- `portfolio_empty` (404) — portfel nie ma otwartych pozycji,
- `gemini_unavailable` (500) — brak pakietu `google-generativeai`,
- `gemini_config_error` (500) — brak `GEMINI_API_KEY`,
- `gemini_empty_response` (502) — model zwrócił pustą odpowiedź,
- `debug_error` (500) — nieoczekiwany wyjątek.

---

## 7. Integracja z frontendem
Komponent UI: `frontend/src/components/ai/PortfolioAIChat.tsx`.

Funkcjonalność po stronie UI:
- szybkie akcje pytań:
  - „Gdzie są największe ryzyka?”,
  - „Co warto dokupić?”,
  - „Co rozważyć do sprzedaży?”,
- własne pytanie wpisywane w textarea,
- stan ładowania (`Analizuję portfel...`),
- obsługa błędu i fallback odpowiedzi.

Wywołanie API jest realizowane przez `http.post('/api/ai/portfolio-analysis', { portfolio_id, question })`.

---

## 8. Ograniczenia i uwagi praktyczne
- Jakość odpowiedzi zależy od jakości danych wejściowych (`holdings`, `price_cache`).
- Braki cen (`current_price`) zaniżają `current_value`, a więc także udział `weight_pct` i kontekst dla modelu.
- Odpowiedź ma charakter informacyjny; nie jest to automatyczny silnik transakcyjny.
- Logi backendowe zawierają etapy działania endpointu, co ułatwia diagnostykę problemów integracyjnych.

---

## 9. Przykład użycia (curl)
```bash
curl -X POST "http://localhost:5000/api/ai/portfolio-analysis" \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": 1,
    "question": "Jak oceniasz ryzyko koncentracji w moim portfelu?"
  }'
```

---

## 10. Powiązane pliki w repo
- Backend endpoint: `backend/routes_ai.py`
- Frontend UI: `frontend/src/components/ai/PortfolioAIChat.tsx`
