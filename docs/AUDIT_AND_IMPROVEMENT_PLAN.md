# Audit & Plan Usprawnień – API / Frontend / Backend Integration

**Data aktualizacji:** 2026-03-22  
**Status:** W trakcie realizacji (Etap 3/4)

Ten dokument łączy wcześniejszy audyt integracji oraz plan usprawnień, stanowiąc jedyne źródło prawdy o stanie technicznym i kierunkach rozwoju projektu.

---

## 1. Snapshot Stanu Projektu (Audit 2026-03-22)

### 1.1 Status Końcowy
- **Quality Gate:** Zielony. `npm run lint`, `npm run build`, `npm run check` przechodzą poprawnie.
- **Backend:** Pełny podział na serwisy domenowe i routery tematyczne został zakończony.
- **Integracja:** Frontend korzysta z ujednoliconej warstwy API (`api.ts`, `api_budget.ts`, itd.). Bezpośrednie wywołania HTTP w komponentach zostały wyeliminowane.
- **Testy:** Istnieją smoke testy krytycznych endpointów oraz testy kontraktu API (envelope `payload/error`).

### 1.2 Wyniki Quality Gate
- **Lint (Frontend):** PASS (0 błędów).
- **Build (Frontend):** PASS.
- **Check (TypeScript):** PASS.
- **Smoke Tests (Backend):** PASS (pokrywają dashboard, portfolio, budżet, kredyty, radar).
- **API Contract Tests:** PASS (weryfikacja envelope `payload/error` dla głównych route'ów).

---

## 2. Architektura Integracji (Zrealizowane)

### 2.1 Warstwa HTTP & API
- **Frontend:** Centralny klient `http.ts` z obsługą błędów i unwrapem payloadu.
- **Backend:** Canonical helpers `success_response` i `error_response`. Globalny exception handling mapujący wyjątki na odpowiednie statusy HTTP i formaty błędu.
- **Kontrakt:** Standard `{ payload: T, error: { code, message, details } }` jest stosowany w większości endpointów.

### 2.2 Podział Odpowiedzialności (Backend)
- **Routery:** Rozbite na `routes_portfolios.py`, `routes_transactions.py`, `routes_history.py`, itd.
- **Serwisy:** Rozbite na `portfolio_core_service.py`, `portfolio_trade_service.py`, `portfolio_valuation_service.py`, itd.
- **Fasada:** `portfolio_service.py` stanowi punkt wejścia dla logiki inwestycyjnej.

---

## 3. Plan Usprawnień (Roadmap)

### Etap 1 — Stabilizacja Podstaw (ZAKOŃCZONY)
- [x] Minimalny Quality Gate (check, build, compileall).
- [x] Smoke testy krytycznych endpointów.
- [x] Testy kontraktu API.
- [x] Zielony lint na frontendzie.

### Etap 2 — Ujednolicenie Komunikacji (W TRAKCIE)
- [x] Wspólny klient HTTP i parser odpowiedzi.
- [x] Przepięcie głównych ekranów na moduły API.
- [ ] **DO ZROBIENIA:** Wyeliminowanie resztek `any` w typowaniu DTO na frontendzie.
- [ ] **DO ZROBIENIA:** Rozszerzenie normalizacji danych (mapping `unknown -> DTO`) na wszystkie moduły API.

### Etap 3 — Porządki w Backendzie (ZAKOŃCZONY)
- [x] Rozbicie `routes.py` na mniejsze moduły.
- [x] Rozbicie `portfolio_service.py` na serwisy domenowe.
- [x] Ustandaryzowanie formatu odpowiedzi (envelope).

### Etap 4 — Wydajność i Rozszerzone Testy (NASTĘPNY KROK)
- [ ] **Optymalizacja Historii:** Wprowadzenie snapshotów lub cache dla rekonstrukcji historii portfela.
- [ ] **Testy Regresji:** Rozszerzenie testów o scenariusze biznesowe (np. skomplikowane cykle kupna/sprzedaży, nadpłaty kredytów).
- [ ] **E2E Smoke Test:** Manualny lub automatyczny test przejścia przez główne ścieżki użytkownika (Dashboard -> Portfel -> Transakcja -> Budżet).
- [ ] **Walidacja Requestów:** Wprowadzenie ścisłej walidacji schematów wejściowych (np. pydantic lub marshmallow na backendzie).

### Etap 5 — Kontrakt Danych i OpenAPI (PLANOWANE)
- [ ] Formalna dokumentacja API (OpenAPI/Swagger).
- [ ] Współdzielenie typów między backendem a frontendem (np. generowanie typów TS z DTO Pythona).

---

## 4. Priorytety (P1 - P3)

### P1: Jakość Danych i Walidacja
- Wprowadzenie walidacji wejścia na backendzie dla operacji zapisu (buy/sell/transfer).
- Rozszerzenie testów kontraktu na 100% endpointów API.

### P2: Typowanie i DTO
- Usunięcie `any` z modułów API na frontendzie.
- Wprowadzenie jawnych interfejsów dla każdej odpowiedzi z backendu.

### P3: Optymalizacja i Monitoring
- Przyspieszenie generowania historii dziennej (30D/N dni).
- Lepsze logowanie błędów integracji z zewnętrznymi dostawcami (yfinance).

---

## 5. Pozostałe Red Flagi (Do Obserwacji)
- **Wielkość Chunków:** Build frontendu ostrzega o dużych plikach (potrzebny code splitting).
- **Zależność od yfinance:** Ryzyko zmian w nieoficjalnym API, wymagany solidny fallback na dane historyczne z bazy.
- **Brak ORM:** Bezpośrednie zapytania SQL wymagają dużej dyscypliny przy zmianach schematu bazy.
