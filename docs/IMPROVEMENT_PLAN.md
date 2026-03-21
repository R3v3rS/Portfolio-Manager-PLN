# Plan usprawnień aplikacji Portfolio Manager (PLN)

Ten dokument jest aktualnym planem działania dla projektu po wykonanych refaktorach i ostatnim audycie integracji API / frontend / backend.

Łączy on dwie perspektywy:
- **co już zostało zrobione lub jest w dużej mierze wdrożone**, 
- **co nadal wymaga domknięcia**, żeby projekt był spójny, przewidywalny i bezpieczny przy kolejnych zmianach.

Dokument został zaktualizowany po przeglądzie repo oraz wnioskach z:
- `docs/PROJECT_GUIDE.md`,
- `docs/AUDIT_API_FRONTEND_BACKEND_INTEGRATION_2026-03-21.md`.

---

## 0. Snapshot stanu projektu

### Co wygląda na zrobione / mocno posunięte

#### Etap 1 — Stabilizacja podstaw
Stan: **częściowo zrobione, ale niezamknięte formalnie**.

W praktyce projekt przeszedł już kilka ważnych usprawnień organizacyjnych i refaktorów, ale w repo nadal nie widać jeszcze pełnego, jednoznacznego domknięcia etapu testowego w skali całej aplikacji.

To znaczy:
- architektura i podział odpowiedzialności poprawiły się względem wcześniejszego stanu,
- aplikacja przechodzi build frontendu,
- część krytycznych flowów została już przerobiona,
- ale nadal brakuje czytelnego dowodu, że wszystkie najważniejsze smoke testy i quality gate są domknięte dla całego repo.

#### Etap 2 — Ujednolicenie komunikacji frontend ↔ backend
Stan: **częściowo zrobione, ale wymaga domknięcia priorytetowego**.

Zrobione / rozpoczęte:
- istnieją dedykowane moduły API po stronie frontendu (`api.ts`, `api_loans.ts`, `api_budget.ts`, `api_symbol_map.ts`),
- część requestów została już wyciągnięta poza komponenty,
- widać kierunek porządkowania integracji.

Niezamknięte problemy:
- frontend nadal używa miksu `axios`, `fetch` i requestów inline,
- nie ma jednej wspólnej warstwy HTTP,
- nie ma centralnego `unwrap payload` / `extract error`,
- nie ma pełnej warstwy compatibility dla starego i nowego kontraktu API.

#### Etap 3 — Porządki w backendzie i podziale odpowiedzialności
Stan: **w dużej mierze zrobione**.

To jest obszar, w którym faktycznie widać największy postęp.

Już wykonane:
- `backend/routes.py` został rozbity na mniejsze moduły (`routes_portfolios.py`, `routes_transactions.py`, `routes_history.py`, `routes_imports.py`, `routes_ppk.py`, `routes_admin.py`),
- logika portfela została rozdzielona na mniejsze serwisy (`portfolio_history_service.py`, `portfolio_import_service.py`, `portfolio_valuation_service.py`, `portfolio_trade_service.py`, `portfolio_audit_service.py`, `portfolio_core_service.py`),
- poprawił się podział odpowiedzialności po stronie backendu.

Nadal do domknięcia w Etapie 3:
- spójna walidacja requestów,
- spójny kontrakt success/error,
- redukcja ręcznego łapania `Exception` bez ustandaryzowanych odpowiedzi.

### Najważniejszy wniosek po audycie

Największy bieżący problem projektu nie leży już w samym podziale backendu, tylko na styku:
- **HTTP layer frontendu**,
- **unwrap payload / compatibility layer**,
- **spójność odpowiedzi backendowych success/error**.

To właśnie ten obszar jest teraz głównym priorytetem technicznym.

---

## 1. Najważniejsze problemy do rozwiązania teraz

Na podstawie aktualnego stanu repo najwyższy wpływ na jakość mają dziś następujące obszary:

1. **Brak jednej wspólnej warstwy HTTP na frontendzie** (`axios` + `fetch` + requesty inline).
2. **Brak wspólnego parsera odpowiedzi API** dla wariantów `payload` / `data` / goły JSON.
3. **Brak wspólnego parsera błędów** (`error.message`, `error.details`, fallback string).
4. **Niespójny backendowy kontrakt odpowiedzi** — mieszanka surowych list, surowych obiektów, `{ message: ... }`, `{ error: ... }`.
5. **Brak pełnej warstwy compatibility backend ↔ frontend** po refaktorze envelope.
6. **Brak formalnego domknięcia quality gate / smoke testów dla najważniejszych flowów**.
7. **Dalsze użycie `any` i lokalnych założeń o shape JSON**, co zwiększa ryzyko crashy runtime.

---

## 2. Priorytety strategiczne po aktualizacji planu

### Priorytet P1 — Domknięcie integracji API / frontend / backend
To jest obecnie priorytet absolutny.

Najpierw trzeba zapewnić, że:
- frontend umie odczytać nowy i stary format odpowiedzi,
- backend zwraca przewidywalne success/error,
- UI nie wywraca się na pustych danych albo envelope bez unwrap.

### Priorytet P2 — Formalne domknięcie jakości i testów regresji
Drugi priorytet to potwierdzić automatycznie, że najważniejsze flowy nadal działają.

### Priorytet P3 — Dalsze porządki architektoniczne
Tutaj wchodzą dalsze refaktory i wygładzanie granic modułów.

### Priorytet P4 — Wydajność i obserwowalność
Dopiero po ustabilizowaniu kontraktu i testów warto szerzej optymalizować koszt obliczeń.

---

## 3. Plan etapami — status + dalsze działania

## Etap 1 — Stabilizacja podstaw

### Status
**Częściowo wykonany, wymaga formalnego domknięcia.**

Etap 1 traktuję jako „już przerabiany”, ale nadal nie jest w pełni zakończony w sensie repozytoryjnym i procesowym.

### Co zostało zrobione / poprawione
- projekt przeszedł już istotne refaktory zmniejszające chaos w kodzie,
- istnieją rozdzielone moduły backendowe, co ułatwia testowanie,
- frontend buduje się poprawnie,
- część ryzykownych flowów została uporządkowana funkcjonalnie.

### Co zostało do zrobienia

#### 1.1 Domknąć smoke testy backendu dla krytycznych endpointów
Na start powinny być objęte przynajmniej:
- `GET /api/dashboard/global-summary`,
- `GET /api/portfolio/list`,
- `POST /api/portfolio/create`,
- `POST /api/portfolio/buy`,
- `POST /api/portfolio/sell`,
- `GET /api/portfolio/value/<id>`,
- `POST /api/budget/transfer-to-portfolio`,
- `POST /api/budget/withdraw-from-portfolio`,
- `GET /api/loans/<id>/schedule`,
- `GET /api/radar`,
- `POST /api/radar/refresh`,
- `GET /api/symbol-map`.

#### 1.2 Domknąć testy logiki biznesowej dla obszarów wysokiego ryzyka
Najwyższy priorytet mają:
- rekonstrukcja historii portfela,
- liczenie wartości i zysku portfela,
- import XTB CSV,
- transfery budżet ↔ inwestycje,
- harmonogramy kredytów,
- dashboard globalny.

#### 1.3 Ustalić i egzekwować minimalny quality gate
Na początek wystarczy:
- `npm --prefix frontend run check`,
- `npm --prefix frontend run build`,
- `python -m compileall backend`,
- smoke testy backendu.

### Efekt końcowy etapu
- zmiany będą bezpieczniejsze,
- łatwiej będzie refaktoryzować HTTP layer i kontrakt API,
- mniej regresji przejdzie niezauważenie.

---

## Etap 2 — Ujednolicenie komunikacji frontend ↔ backend

### Status
**Rozpoczęty, ale jeszcze niezamknięty. To obecnie najważniejszy etap do domknięcia.**

### Co zostało już zrobione
- część komunikacji została przeniesiona do plików API,
- projekt ma już wydzielone moduły typu `api_budget.ts`, `api_loans.ts`, `api_symbol_map.ts`,
- kierunek architektoniczny został wyznaczony.

### Co trzeba zrobić teraz priorytetowo

#### 2.1 Wprowadzić jeden wspólny HTTP layer
Docelowo wszystkie requesty powinny przechodzić przez jeden mechanizm, np. wspólny `http.ts`.

Ta warstwa powinna obsługiwać:
- `GET / POST / PATCH / DELETE`,
- spójne nagłówki i serializację,
- wspólną obsługę błędów,
- wspólne unwrapowanie odpowiedzi,
- kompatybilność dla starego i nowego kontraktu.

Do przepięcia w pierwszej kolejności:
- `api.ts`,
- `api_loans.ts`,
- `api_budget.ts`,
- `api_symbol_map.ts`,
- requesty inline w `MainDashboard.tsx`,
- requesty inline w `InvestmentRadar.tsx`,
- requesty inline / specyficzne flowy w `PortfolioDetails.tsx`,
- requesty inline w `BudgetDashboard.tsx`.

#### 2.2 Dodać centralny `unwrap payload`
Potrzebna jest jedna funkcja kompatybilności, np.:
- `extractPayload(response)`

która obsłuży:
- `{ payload: ... }`,
- `{ data: ... }`,
- stary surowy JSON jako fallback.

To jest krytyczne szczególnie dla:
- dashboardu,
- radaru,
- budżetu,
- importów,
- symbol mapping.

#### 2.3 Dodać centralny parser błędów
Potrzebna jest jedna funkcja, np.:
- `extractErrorMessage(errorBody)`

Powinna ona obsługiwać:
- `error.message`,
- `error.details`,
- stare `{ error: "..." }`,
- fallback string,
- sytuację, gdy odpowiedź jest pusta albo błędna.

#### 2.4 Dodać `parseJsonApiResponse`
Wspólny parser powinien:
- bezpiecznie parsować JSON,
- działać dla pustego body,
- odróżniać success/error,
- zwracać czytelny błąd dla UI,
- delegować unwrap i extract error do helperów wspólnych.

#### 2.5 Zaktualizować najbardziej wrażliwe ekrany
Najpierw:
- `MainDashboard.tsx`,
- `InvestmentRadar.tsx`,
- `PortfolioDetails.tsx`,
- `BudgetDashboard.tsx`.

Tu trzeba dopilnować:
- guardów dla `undefined` / `null`,
- sensownych fallbacków dla pustych tablic i pustych obiektów,
- braku bezpośredniego zakładania shape odpowiedzi bez normalizacji.

#### 2.6 Domknąć XTB import pod nowy kontrakt błędów
Scenariusz `missing_symbols` powinien działać zarówno dla starego formatu, jak i nowego:
- stary: `{ success: false, missing_symbols: [...] }`,
- nowy: `{ error: { message, details: { missing_symbols: [...] } } }`.

### Efekt końcowy etapu
- frontend przestanie być kruchy na zmianę formatu odpowiedzi,
- backend będzie można migrować bez rozwalania UI ekran po ekranie,
- zniknie duża część ryzyka „białego ekranu” i `undefined` w runtime.

---

## Etap 3 — Porządki w backendzie i podziale odpowiedzialności

### Status
**W dużej mierze wykonany, ale wymaga domknięcia kontraktu i walidacji.**

### Co już zostało zrobione

#### 3.1 Rozbicie `backend/routes.py`
To wygląda na wykonane.

Aktualny podział obejmuje m.in.:
- `routes_portfolios.py`,
- `routes_transactions.py`,
- `routes_history.py`,
- `routes_imports.py`,
- `routes_ppk.py`,
- `routes_admin.py`.

#### 3.2 Rozbicie logiki portfela na mniejsze serwisy
To również wygląda na wykonane.

W repo są już m.in.:
- `portfolio_history_service.py`,
- `portfolio_import_service.py`,
- `portfolio_valuation_service.py`,
- `portfolio_trade_service.py`,
- `portfolio_audit_service.py`,
- `portfolio_core_service.py`.

### Co zostało do zrobienia

#### 3.3 Ustandaryzować walidację requestów
Obecnie nadal wiele endpointów:
- czyta `request.json[...]` bez warstwy walidacji,
- łapie `Exception` szeroko,
- zwraca różne shape’y błędów.

Najpierw trzeba objąć walidacją endpointy:
- tworzenia portfela,
- buy / sell,
- importów,
- transferów budżetowych,
- kredytów i nadpłat,
- dashboardowych summary requestów, jeśli pojawią się parametry wejściowe.

#### 3.4 Ustandaryzować kontrakt success / error
Backend powinien przejść na jeden format odpowiedzi.

Rekomendowany kierunek:
- sukces: `{ payload: ... }` albo inny jeden ustalony envelope,
- błąd: `{ error: { code, message, details } }`.

Najważniejsze zasady:
- brak surowych list i surowych dictów bez envelope,
- `details` zawsze jako obiekt,
- brak mieszania `{ message: ... }`, `{ error: ... }`, `{ success: false }` bez wspólnego standardu.

#### 3.5 Ograniczyć lokalne `except Exception`
Routy powinny docelowo:
- przyjąć dane,
- zwalidować je,
- wywołać serwis,
- zwrócić ustandaryzowaną odpowiedź.

A mapowanie wyjątków powinno być centralne i przewidywalne.

### Efekt końcowy etapu
- backend będzie naprawdę spójny kontraktowo,
- łatwiej będzie utrzymać frontendową compatibility layer,
- mniej kodu będzie trzeba „zgadywać” przy kolejnych zmianach.

---

## Etap 4 — Wydajność historii, dashboardu i radaru

### Status
**Do zrobienia po ustabilizowaniu integracji.**

### Zadania

#### 4.1 Zoptymalizować historię portfela
Możliwe kierunki:
- snapshoty miesięczne / dzienne,
- cache dla liczonych zakresów,
- prekomputacja po zapisaniu transakcji,
- osobna tabela agregatów historycznych.

#### 4.2 Zoptymalizować `global-summary`
Aktualny dashboard nadal może być kosztowny, bo:
- iteruje po portfelach,
- dociąga ich wyceny,
- iteruje po kredytach,
- liczy harmonogramy.

Po ustabilizowaniu kontraktu warto dodać:
- cache summary,
- cache sald kredytów,
- preliczone agregaty majątku netto,
- ewentualnie rozdzielenie cięższych sekcji na osobne endpointy.

#### 4.3 Ulepszyć cache cen i radaru
Dopracować:
- TTL cache,
- strategię refreshu,
- fallback na ostatnie poprawne dane,
- rozróżnienie „fresh / stale / failed”.

#### 4.4 Ograniczyć koszt ciężkich ekranów frontendu
Do rozważenia:
- dalszy code splitting,
- lazy loading ciężkich sekcji,
- odświeżanie tylko aktywnej zakładki,
- unikanie pełnych reloadów dużych ekranów.

### Efekt końcowy etapu
- szybsze otwieranie głównych ekranów,
- mniejsze obciążenie backendu,
- stabilniejsze zachowanie przy większej liczbie danych.

---

## Etap 5 — Kontrakt danych i przewidywalność zmian

### Status
**Do zrobienia równolegle z końcówką Etapu 2 i 3.**

### Zadania

#### 5.1 Zdefiniować formalny kontrakt API
Najlepiej przez:
- OpenAPI,
- albo przynajmniej jawne DTO per endpoint.

Najpierw dla obszarów:
- portfolio,
- budżet,
- kredyty,
- radar,
- symbol mapping,
- dashboard.

#### 5.2 Współdzielić lub generować typy
Dzięki temu frontend nie będzie ręcznie zgadywał pól odpowiedzi.

#### 5.3 Ujednolicić nazewnictwo pól i struktur odpowiedzi
Szczególnie przy:
- summary,
- listach,
- błędach,
- historycznych payloadach,
- odpowiedziach POST / PATCH / DELETE.

### Efekt końcowy etapu
- mniej błędów integracyjnych,
- łatwiejsze refaktory po obu stronach,
- mniejsze ryzyko rozjazdu dokumentacji i implementacji.

---

## Etap 6 — Obserwowalność, diagnostyka i utrzymanie

### Status
**Wciąż ważne, ale wtórne wobec integracji i testów.**

### Zadania

#### 6.1 Dodać spójne logowanie requestów
Dla każdego requestu warto logować:
- endpoint,
- czas wykonania,
- status,
- podstawowe parametry,
- identyfikator requestu.

#### 6.2 Dodać pomiary dla najcięższych operacji
Najpierw dla:
- historii portfela,
- global summary,
- importu XTB,
- refreshu radaru,
- analizy pojedynczego tickera.

#### 6.3 Uporządkować logi błędów integracji zewnętrznych
Szczególnie dla:
- yfinance,
- synchronizacji historii cen,
- wydarzeń rynkowych,
- fetchu analizy tickera.

#### 6.4 Dodać checklisty developerskie do dokumentacji
Np.:
- co sprawdzić po zmianie w warstwie HTTP,
- jak testować import XTB po zmianie kontraktu błędów,
- jak sprawdzić kompatybilność `payload/data/raw JSON`,
- jak potwierdzić, że dashboard i radar obsługują puste odpowiedzi.

### Efekt końcowy etapu
- szybszy debugging,
- mniej problemów „ukrytych” w runtime,
- łatwiejszy powrót do projektu po czasie.

---

## 4. Rekomendowana kolejność wdrożenia po aktualizacji

1. **Domknąć Etap 2** — wspólny HTTP layer, unwrap payload, parser błędów, compatibility layer.
2. **Formalnie domknąć Etap 1** — smoke testy, testy logiki i quality gate.
3. **Domknąć Etap 3** — walidacja requestów i ujednolicenie kontraktu success/error.
4. **Równolegle rozpocząć Etap 5** — formalizacja DTO / OpenAPI.
5. **Dopiero potem szerzej robić Etap 4 i 6** — wydajność i obserwowalność.

To jest najbardziej sensowna kolejność po obecnym stanie projektu: backendowy rozdział modułów już w dużej mierze jest, ale największe ryzyko siedzi dziś na granicy integracyjnej.

---

## 5. Quick wins — rzeczy do zrobienia od razu

Najwyższy zwrot teraz dadzą:

1. dodać wspólny `http.ts` dla frontendu,
2. dodać `extractPayload`,
3. dodać `extractErrorMessage`,
4. dodać `parseJsonApiResponse`,
5. przepiąć `MainDashboard.tsx` i `InvestmentRadar.tsx` na wspólną warstwę HTTP,
6. przepiąć `PortfolioDetails.tsx` i `BudgetDashboard.tsx` na wspólną warstwę HTTP,
7. ujednolicić backendowy error envelope,
8. dodać obsługę `missing_symbols` w `error.details`,
9. uruchomić smoke test dla `global-summary`, buy / sell, transfer budżet → inwestycje,
10. ograniczyć najbardziej ryzykowne `any` w warstwie integracyjnej.

---

## 6. Plan produktowo-techniczny per moduł

### Inwestycje
Zrobione / poprawione:
- rozbita logika serwisowa,
- lepszy podział odpowiedzialności backendu.

Do zrobienia:
- objąć testami buy / sell / import / historię,
- przepiąć odpowiedzi API na wspólny envelope,
- uprościć integracyjnie `PortfolioDetails.tsx`.

### Budżet
Zrobione / poprawione:
- istnieje wydzielona warstwa API i logika modułu budżetowego.

Do zrobienia:
- wyeliminować inline requesty i twarde założenia o shape JSON,
- dodać testy dla free pool, kopert i transferów,
- dopiąć kompatybilność odpowiedzi po stronie UI.

### Kredyty
Zrobione / poprawione:
- istnieje osobny moduł i logika harmonogramów.

Do zrobienia:
- dodać walidację requestów,
- pokryć harmonogramy i nadpłaty testami,
- ujednolicić kontrakt odpowiedzi harmonogramów.

### Radar i ceny
Zrobione / poprawione:
- istnieje osobny moduł radarowy i cache cen.

Do zrobienia:
- przepiąć frontend na wspólny HTTP layer,
- dodać lepsze fallbacki błędów,
- dopracować semantykę „dane świeże / nieświeże / błąd źródła”.

### Dashboard globalny
Zrobione / poprawione:
- istnieje osobny endpoint i ekran.

Do zrobienia:
- ujednolicić kontrakt odpowiedzi,
- dodać compatibility unwrap,
- dopiąć smoke testy,
- w kolejnym kroku dodać cache.

### Symbol mapping / importy
Zrobione / poprawione:
- istnieje osobny panel i osobny moduł API,
- import XTB ma już osobny flow.

Do zrobienia:
- przenieść `missing_symbols` do ustandaryzowanego `error.details`,
- zachować kompatybilność dla starego formatu,
- dodać test regresji importu i mapowania symboli.

---

## 7. Definicja sukcesu po tej aktualizacji planu

Plan będzie można uznać za skutecznie wdrażany, jeśli projekt osiągnie następujący stan:

- frontend korzysta z jednej wspólnej warstwy HTTP,
- istnieje wspólny `unwrap payload` dla `payload / data / raw JSON`,
- istnieje wspólny `extract error` dla `error.message / error.details / fallback`,
- backend zwraca jeden spójny format success/error,
- najważniejsze flowy mają smoke testy,
- krytyczne obszary biznesowe mają testy regresji,
- dashboard, radar, budżet i portfolio details nie wywracają się na pustych albo niepełnych danych,
- dokumentacja opisuje stan faktyczny: co zrobione, co do zrobienia i w jakiej kolejności.

---

## 8. Rekomendacja końcowa

Jeśli mam wskazać **3 najważniejsze rzeczy od teraz**, to są to:

1. **domknąć Etap 2: wspólny HTTP layer + unwrap payload + parser błędów + compatibility layer**,  
2. **formalnie domknąć Etap 1: smoke testy i quality gate**,  
3. **domknąć Etap 3 od strony kontraktu i walidacji: jeden format success/error + jedna strategia mapowania błędów**.

To jest dziś najkrótsza droga do realnej stabilności projektu: architektura backendu została już mocno poprawiona, ale żeby to naprawdę działało bezpiecznie, trzeba teraz domknąć warstwę integracji i przewidywalność kontraktu danych.
