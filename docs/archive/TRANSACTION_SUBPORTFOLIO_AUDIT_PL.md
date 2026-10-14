# Audit: dodawanie transakcji vs sub-portfel

Data: 2026-04-03

## Kontekst problemu
W tym projekcie **poprawny model danych** dla sub-portfeli jest następujący:
- `transactions.portfolio_id` wskazuje **parent portfolio**,
- `transactions.sub_portfolio_id` wskazuje **child portfolio** (albo `NULL` dla parent scope).

To jest zgodne z logiką odczytu, np. dla widoku child w `get_transactions()` backend filtruje po `portfolio_id = parent_id` i `sub_portfolio_id = child_id`.

## Wynik audytu (najważniejsze problemy)

### 1) Krytyczny: endpointy dodawania transakcji nie normalizują `portfolio_id`, gdy przychodzi ID child
**Objawy:**
- Gdy frontend wyśle `portfolio_id = child_id` i `sub_portfolio_id = NULL`, wpis trafia do `transactions` jako child w `portfolio_id`, bez sub-id.
- Odczyt child-portfolio filtruje po `(portfolio_id=parent, sub_portfolio_id=child)`, więc taka transakcja „znika” z widoku child.

**Dowód w kodzie:**
- Odczyt child zakłada `(portfolio_id = parent, sub_portfolio_id = child)`: `backend/portfolio_service.py` (`get_transactions`).
- Zapisy (`deposit`, `withdraw`, `buy`, `sell`, `dividend`) przekazują `portfolio_id` bez normalizacji do parent i opcjonalne `sub_portfolio_id` wprost z payloadu: `backend/routes_transactions.py` + `backend/portfolio_trade_service.py`.

**Wpływ:** bardzo wysoki (znikające transakcje, niespójne saldo i historia).

---

### 2) Krytyczny UX/API flow: w widoku child nie da się wskazać `sub_portfolio_id`, więc requesty lecą z `sub_portfolio_id = null`
**Objawy:**
- UI pozwala otworzyć `PortfolioDetails` dla child (`/portfolio/:id`),
- ale selektor sub-portfela pokazuje się tylko gdy `subPortfolios.length > 0`.
- Dla child zazwyczaj `subPortfolios` jest puste, więc formularze wysyłają `sub_portfolio_id = null`.

**Dowód w kodzie:**
- Nawigacja do child details: `frontend/src/pages/PortfolioList.tsx`.
- Modale transakcji/transferu pokazują selector tylko przy `subPortfolios.length > 0`: `TransactionModal.tsx`, `TransferModal.tsx`.

**Wpływ:** bardzo wysoki (łatwo reprodukowalny scenariusz powodujący błąd z pkt 1).

---

### 3) Wysoki: szybkie „Zamknij pozycję” sprzedaje bez `sub_portfolio_id`
**Objawy:**
- `closePositionAtLastPrice()` wywołuje `portfolioApi.sell(...)` bez `sub_portfolio_id`.
- Dla pozycji należących do child może to prowadzić do błędów (brak holdingu w parent scope) lub sprzedaży w złym scope, jeśli istnieje identyczny ticker w parent.

**Dowód w kodzie:**
- `closePositionAtLastPrice` nie przekazuje `holding.sub_portfolio_id`: `frontend/src/pages/PortfolioDetails.tsx`.
- Dla porównania `SellModal` przekazuje `sub_portfolio_id: holding.sub_portfolio_id` poprawnie: `frontend/src/components/modals/SellModal.tsx`.

**Wpływ:** wysoki (ryzyko niepoprawnej sprzedaży / błędów użytkownika).

---

### 4) Wysoki: wypłata do Budżetu ignoruje wybrany sub-portfel
**Objawy:**
- W `TransferModal` przy `WITHDRAW` + wybrane konto budżetowe wykonywane jest `budgetApi.withdrawFromPortfolio(...)` bez informacji o `sub_portfolio_id`.
- Backend `budget_service.withdraw_from_investment(...)` operuje tylko na `portfolio_id` (brak wsparcia sub-scope), więc transakcja i cash lecą po parent.

**Dowód w kodzie:**
- `TransferModal` gałąź `WITHDRAW` z budżetem nie przekazuje sub-id.
- `backend/budget_service.py` wstawia `transactions` bez kolumny `sub_portfolio_id` i modyfikuje `portfolios.current_cash` tylko po `portfolio_id`.

**Wpływ:** wysoki (niespójność sald parent/sub przy integracji budżetowej).

---

### 5) Wysoki: import XTB z widoku child może zapisać transakcje do złego scope
**Objawy:**
- Endpoint importu jest parametryzowany przez `/<portfolio_id>/import/xtb`.
- Jeśli import uruchamiany z child details i bez wybranego `sub_portfolio_id`, payload użyje `portfolio_id = child_id`.
- Import zapisuje transakcje z `portfolio_id` dokładnie takim, jaki dostał endpoint.

**Dowód w kodzie:**
- `ImportXtbCsvButton` wysyła `portfolioId` z widoku i opcjonalny sub-id tylko z selektora widocznego przy `subPortfolios.length > 0`: `frontend/src/pages/PortfolioDetails.tsx`.
- `routes_imports.py` przekazuje `portfolio_id` i `sub_portfolio_id` dalej 1:1 do `PortfolioService.import_xtb_csv`.
- `portfolio_import_service.py` zapisuje `transactions.portfolio_id = portfolio_id` przekazany na wejściu.

**Wpływ:** wysoki (masowe „znikające” transakcje po imporcie w child context).

---

## Dodatkowe obserwacje
- Część testów pokrywa parent/child odczyt i assign transakcji, ale brakuje testów E2E „dodanie z kontekstu child view” (UI + API payload semantics).
- Obecny kontrakt API dopuszcza `portfolio_id` będące child, ale logika odczytu i agregacji w wielu miejscach zakłada model parent+sub_id.

## Rekomendowany plan naprawczy (priorytety)
1. **Backend hardening (P0):**
   - Dodać normalizację scope na wejściu dla endpointów write (`deposit/withdraw/buy/sell/dividend/import/manual interest`).
   - Jeśli `portfolio_id` wskazuje child:
     - przepisać wewnętrznie na `parent_id`,
     - wymusić `sub_portfolio_id = child_id` (o ile caller nie podał konfliktowego sub-id).

2. **Frontend guardrails (P0):**
   - W `PortfolioDetails` dla child wymusić hidden scope (`portfolio_id=parent`, `sub_portfolio_id=child`) albo zablokować operacje bez jawnego scope.
   - W `closePositionAtLastPrice` zawsze przekazywać `holding.sub_portfolio_id`.

3. **Integracja budżetu (P1):**
   - Rozszerzyć API budżetowe o `sub_portfolio_id` lub jawnie wyłączyć opcję sub przy tej operacji z komunikatem dla użytkownika.

4. **Import XTB (P1):**
   - Taki sam resolver scope jak w write endpoints; nie ufać surowemu `portfolio_id` z URL.

5. **Testy regresyjne (P0/P1):**
   - Scenariusze child-context dla każdej operacji write.
   - Test dla `closePositionAtLastPrice`.
   - Test dla `withdrawFromPortfolio` z/bez sub-scope.

