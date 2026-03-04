# Przegląd spójności i jakości kodu

## Zakres
- Backend: Flask + SQLite (`backend/`)
- Frontend: React + TypeScript + Vite (`frontend/`)

## Co sprawdziłem
1. Statyczna poprawność TypeScript (`npm run check`) – **PASS**.
2. Build produkcyjny frontendu (`npm run build`) – **PASS**, ale z ostrzeżeniem o dużym bundlu.
3. Lint frontendu (`npm run lint`) – **FAIL**: 51 błędów i 4 ostrzeżenia.
4. Walidacja składni backendu (`python -m compileall`) – **PASS**.

## Najważniejsze problemy

### 1) Niska spójność typów w frontendzie
- Wiele wystąpień `any` i nieużywanych importów powoduje brak spójności i większe ryzyko regresji.
- Priorytet: wysoki (utrzymanie i niezawodność).

### 2) Potencjalny wyciek szczegółów błędów z backendu
- Globalny handler wyjątków zwracał szczegółową treść błędu klientowi.
- To zwiększa ryzyko ujawnienia informacji o implementacji.

### 3) Wydajność frontendu (rozmiar bundla)
- Build wskazuje główny plik JS > 1 MB przed gzip.
- Może pogarszać TTI/LCP na wolniejszych urządzeniach.

### 4) Dynamic + static import tego samego modułu
- `api_loans.ts` jest importowany mieszanie (statycznie i dynamicznie), co ogranicza code splitting.

## Wprowadzone poprawki
1. Uszczelnienie obsługi wyjątków backendu:
   - w trybie produkcyjnym zwracany jest generyczny komunikat błędu,
   - szczegóły zostają w logach.
2. Spójniejsze logowanie warmup cache zamiast `print`.
3. Uporządkowanie `App.tsx` (usunięty nieużywany import).
4. Utypowanie warstwy `api_loans.ts` (payloady i query), usunięcie `any`.

## Rekomendowany plan usprawnień (następne kroki)
1. **Frontend lint debt (1–2 sprinty):**
   - usunięcie `any`,
   - domknięcie zależności `useEffect`,
   - cleanup nieużywanych importów/zmiennych.
2. **Podział bundla:**
   - lazy-load dużych ekranów (`LoansDashboard`, `BudgetDashboard`, wykresy),
   - konfiguracja `manualChunks` dla bibliotek wykresowych.
3. **API contract-first:**
   - wspólne typy DTO dla frontend/backend (np. OpenAPI + generator).
4. **Obserwowalność:**
   - ujednolicony logger i correlation id w requestach.
5. **Testy regresji:**
   - smoke testy endpointów Flask,
   - 2–3 testy komponentów krytycznych w frontendzie.
