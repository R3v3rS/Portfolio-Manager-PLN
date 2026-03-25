# Audit & Plan Usprawnień – API / Frontend / Backend Integration

**Data aktualizacji:** 2026-03-25  
**Status:** W trakcie realizacji (Etap 4)

Ten dokument łączy wcześniejszy audyt integracji oraz plan usprawnień, stanowiąc jedyne źródło prawdy o stanie technicznym i kierunkach rozwoju projektu.

---

## 1. Snapshot Stanu Projektu (Audit 2026-03-25)

### 1.1 Status Końcowy
- **Quality Gate:** Zielony. `npm run lint`, `npm run build`, `npm run check` przechodzą poprawnie.
- **Backend:** Pełny podział na serwisy domenowe i routery tematyczne zakończony. Dodano dedykowany moduł PPK.
- **Integracja:** Frontend korzysta z ujednoliconej warstwy API (`api.ts`, `api_budget.ts`, itd.) z normalizacją typów.
- **Obsługa Błędów:** Wprowadzono ujednolicony system wyjątków (`ApiError`, `ValidationError`, `NotFoundError`) z globalnym handlerem.
- **Testy:** Istnieją smoke testy krytycznych endpointów oraz testy kontraktu API (envelope `payload/error`).

### 1.2 Wyniki Quality Gate
- **Lint (Frontend):** PASS (0 błędów).
- **Build (Frontend):** PASS.
- **Check (TypeScript):** PASS.
- **Smoke Tests (Backend):** PASS.
- **API Contract Tests:** PASS.

---

## 2. Architektura Integracji (Zrealizowane)

### 2.1 Warstwa HTTP & API
- **Frontend:** Centralny klient `http.ts` z obsługą błędów i unwrapem payloadu. Normalizacja DTO (`unknown -> T`) w `api.ts`.
- **Backend:** Canonical helpers `success_response` i `error_response` w `backend/api/response.py`.
- **Obsługa Błędów:** Globalny exception handling w `app.py` mapujący wyjątki na ustandaryzowany format JSON.
- **Kontrakt:** Standard `{ payload: T, error: { code, message, details } }`.

### 2.2 Podział Odpowiedzialności (Backend)
- **Routery:** Modułowe podejście (`routes_portfolios.py`, `routes_ppk.py`, itd.).
- **Serwisy:** Rozbite na serwisy domenowe (Core, Trade, Valuation, History, Audit, PPK).
- **Fasada:** `portfolio_service.py` jako punkt wejścia.

---

## 3. Plan Usprawnień (Roadmap)

### Etap 1 — Stabilizacja Podstaw (ZAKOŃCZONY)
- [x] Minimalny Quality Gate (check, build, compileall).
- [x] Smoke testy krytycznych endpointów.
- [x] Testy kontraktu API.
- [x] Zielony lint na frontendzie.

### Etap 2 — Ujednolicenie Komunikacji (ZAKOŃCZONY)
- [x] Wspólny klient HTTP i parser odpowiedzi.
- [x] Przepięcie głównych ekranów na moduły API.
- [x] **ZREALIZOWANE:** Rozszerzenie normalizacji danych (mapping `unknown -> DTO`) na wszystkie główne moduły API.
- [x] **ZREALIZOWANE:** Ujednolicona obsługa błędów na poziomie API (canonical response helpers).

### Etap 3 — Porządki w Backendzie (ZAKOŃCZONY)
- [x] Rozbicie `routes.py` na mniejsze moduły.
- [x] Rozbicie `portfolio_service.py` na serwisy domenowe.
- [x] Ustandaryzowanie formatu odpowiedzi (envelope).
- [x] **ZREALIZOWANE:** Globalny mechanizm exception handling w Flask (app.py).

### Etap 4 — Wydajność i Nowe Funkcjonalności (W TRAKCIE)
- [x] **Moduł PPK:** Pełna implementacja (backend/frontend) obsługi transakcji, wyników i wyceny PPK.
- [x] **Optymalizacja Historii:** Wprowadzenie cache'owania metryk historycznych (`_metrics_cache` w `PortfolioHistoryService`).
- [x] **Walidacja Requestów:** Wprowadzenie `ValidationError` i wstępna walidacja schematów wejściowych w routerach.
- [ ] **Testy Regresji:** Rozszerzenie testów o scenariusze biznesowe (np. skomplikowane cykle kupna/sprzedaży, nadpłaty kredytów).
- [ ] **E2E Smoke Test:** Automatyczny test przejścia przez główne ścieżki użytkownika.

### Etap 5 — Kontrakt Danych i OpenAPI (PLANOWANE)
- [ ] Formalna dokumentacja API (OpenAPI/Swagger) — obecnie istnieje zalążek w `docs/openapi.yaml`.
- [ ] Współdzielenie typów między backendem a frontendem (np. generowanie typów TS z DTO Pythona).

---

## 4. Priorytety (P1 - P3)

### P1: Jakość Danych i Walidacja
- Pełna migracja walidacji wejścia na backendzie na dedykowane schematy lub pomocniki rzucające `ValidationError`.
- Rozszerzenie testów kontraktu na 100% endpointów API.

### P2: Typowanie i DTO
- Usunięcie `any` z modułów API na frontendzie (pozostały nieliczne wystąpienia).
- Wprowadzenie jawnych interfejsów dla każdej odpowiedzi z backendu.

### P3: Optymalizacja i Monitoring
- Przyspieszenie generowania historii dziennej (30D/N dni) — dalsza optymalizacja cache'owania.
- Lepsze logowanie błędów integracji z zewnętrznymi dostawcami (yfinance).

---

## 5. Pozostałe Red Flagi (Do Obserwacji)
- **Wielkość Chunków:** Build frontendu ostrzega o dużych plikach (potrzebny code splitting).
- **Zależność od yfinance:** Ryzyko zmian w nieoficjalnym API, wymagany solidny fallback na dane historyczne z bazy.
- **Brak ORM:** Bezpośrednie zapytania SQL wymagają dużej dyscypliny przy zmianach schematu bazy.
