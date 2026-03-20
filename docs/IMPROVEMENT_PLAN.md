# Plan usprawnień aplikacji Portfolio Manager (PLN)

Ten dokument jest praktycznym planem rozwoju aplikacji opartym na aktualnej architekturze, logice modułów oraz zidentyfikowanych ograniczeniach opisanych w `docs/PROJECT_GUIDE.md`.

Celem planu nie jest „przepisać wszystko”, tylko:

- poprawić stabilność i bezpieczeństwo zmian,
- przyspieszyć rozwój nowych funkcji,
- uprościć pracę developera i AI,
- ograniczyć ryzyko regresji w najbardziej złożonych miejscach aplikacji.

---

## 1. Najważniejsze problemy do rozwiązania

Na podstawie obecnego stanu projektu najwyższy wpływ na jakość mają następujące obszary:

1. **Brak testów regresji dla kluczowych flowów**.
2. **Niespójna warstwa API na frontendzie** (`axios` + `fetch` + requesty inline).
3. **Zbyt szeroki moduł inwestycyjny w backendzie** (`backend/routes.py` i część `portfolio_service.py`).
4. **Kosztowne obliczeniowo endpointy historyczne i dashboardowe**.
5. **Duża zależność od danych zewnętrznych** przy radarze i cenach.
6. **Brak formalnego kontraktu danych między backendem a frontendem**.
7. **Rosnąca złożoność logiki budżetu, kredytów i importów bez warstwy ochronnej testów / walidacji**.

---

## 2. Priorytety strategiczne

### Priorytet P1 — Stabilność i bezpieczeństwo zmian
Najpierw trzeba obniżyć ryzyko psucia działających funkcji.

### Priorytet P2 — Uporządkowanie architektury aplikacyjnej
Potem warto ujednolicić sposób pracy kodu, szczególnie na styku frontend ↔ backend.

### Priorytet P3 — Wydajność i obserwowalność
Kiedy aplikacja będzie bezpieczniejsza w utrzymaniu, można poprawiać czas odpowiedzi i debugowalność.

### Priorytet P4 — Skalowalność dalszego rozwoju
Na końcu należy przygotować repo na większą liczbę zmian, ludzi i funkcji.

---

## 3. Plan etapami

## Etap 1 — Stabilizacja podstaw

### Cel
Zbudować minimalne zabezpieczenie przed regresjami i ustalić „co musi działać zawsze”.

### Zadania

#### 1.1 Dodać testy smoke backendu dla krytycznych endpointów
Na start warto pokryć przynajmniej:

- `GET /api/dashboard/global-summary`,
- `GET /api/portfolio/list`,
- `POST /api/portfolio/create`,
- `POST /api/portfolio/buy`,
- `GET /api/portfolio/value/<id>`,
- `POST /api/budget/transfer-to-portfolio`,
- `POST /api/budget/withdraw-from-portfolio`,
- `GET /api/loans/<id>/schedule`,
- `GET /api/radar`,
- `POST /api/radar/refresh`,
- `GET /api/symbol-map`.

#### 1.2 Dodać testy logiki biznesowej dla obszarów wysokiego ryzyka
Najwyższy priorytet mają:

- rekonstrukcja historii portfela,
- liczenie zysku portfela,
- import XTB CSV,
- transfery budżet ↔ inwestycje,
- harmonogramy kredytów,
- dashboard globalny.

#### 1.3 Dodać testowe zestawy danych referencyjnych
Warto przygotować małe fixture’y dla:

- prostego portfela z kilkoma transakcjami,
- portfela walutowego z FX,
- przykładowego importu XTB,
- jednego kredytu z nadpłatami,
- jednego konta budżetowego z kopertami i transferem do inwestycji.

#### 1.4 Ustalić minimalny quality gate dla repo
Na początek wystarczy:

- `npm run check`,
- `npm run build`,
- `python -m compileall .`,
- testy smoke backendu.

### Efekt etapu
- mniejsze ryzyko przypadkowego zepsucia najważniejszych funkcji,
- łatwiejsza refaktoryzacja kolejnych etapów,
- szybsza diagnoza, co dokładnie przestało działać.

---

## Etap 2 — Ujednolicenie komunikacji frontend ↔ backend

### Cel
Uprościć warstwę komunikacji i ograniczyć rozjazdy między modułami.

### Zadania

#### 2.1 Ujednolicić klienta HTTP na frontendzie
Docelowo wszystkie requesty powinny iść przez jeden wspólny mechanizm, np.:

- wspólny klient Axios,
- albo wspólny `http.ts` z helperami i obsługą błędów.

Do uporządkowania są szczególnie:

- `api.ts`,
- `api_loans.ts`,
- `api_budget.ts`,
- `api_symbol_map.ts`,
- requesty inline w `MainDashboard.tsx`, `InvestmentRadar.tsx` i częściach `PortfolioDetails.tsx`.

#### 2.2 Ustandaryzować obsługę błędów w UI
Każdy moduł powinien korzystać z tego samego podejścia do:

- błędów sieciowych,
- błędów walidacji,
- błędów biznesowych backendu,
- komunikatów użytkownika.

#### 2.3 Ograniczyć duplikację mapowania odpowiedzi API
Warto wprowadzić:

- wspólne typy DTO po stronie frontendu,
- helpery do transformacji odpowiedzi,
- jeden standard odpowiedzi błędów z backendu.

#### 2.4 Uporządkować ładowanie danych w dużych ekranach
Największy kandydat do rozbicia to `PortfolioDetails.tsx`, bo miesza:

- dane portfela,
- historię,
- radary / ceny,
- import,
- budżet,
- PPK,
- audyt.

Warto rozdzielić to na:

- hooki ładowania danych,
- osobne sekcje logiki per tab,
- mniejsze komponenty kontenerowe.

### Efekt etapu
- mniej chaosu w requestach,
- łatwiejsza zmiana kontraktów API,
- prostszy onboarding dla nowych osób.

---

## Etap 3 — Porządki w backendzie i podziale odpowiedzialności

### Cel
Zmniejszyć złożoność backendu bez przepisywania całego systemu.

### Zadania

#### 3.1 Rozbić `backend/routes.py` na mniejsze moduły
Proponowany podział:

- `routes_portfolios.py`,
- `routes_transactions.py`,
- `routes_history.py`,
- `routes_imports.py`,
- `routes_ppk.py`,
- `routes_admin.py`.

Publiczne URL-e mogą pozostać bez zmian.

#### 3.2 Wydzielić z `portfolio_service.py` logikę do mniejszych serwisów
Przykładowy podział:

- `portfolio_history_service.py`,
- `portfolio_import_service.py`,
- `portfolio_valuation_service.py`,
- `portfolio_trade_service.py`,
- `portfolio_audit_service.py`.

#### 3.3 Wydzielić walidację requestów
Obecnie wiele walidacji jest ręcznych. Warto wprowadzić np.:

- Pydantic,
- Marshmallow,
- albo własną lekką warstwę walidatorów requestów.

Najpierw dla endpointów:

- tworzenia portfela,
- kupna/sprzedaży,
- importów,
- transferów budżetowych,
- kredytów i nadpłat.

#### 3.4 Ograniczyć bezpośrednie „business decisions” w routach
Routy powinny tylko:

- przyjąć dane,
- zwalidować je,
- wywołać serwis,
- zwrócić spójną odpowiedź.

### Efekt etapu
- czytelniejszy backend,
- mniej konfliktów przy równoległej pracy,
- łatwiejsze testowanie logiki domenowej.

---

## Etap 4 — Wydajność historii, dashboardu i radaru

### Cel
Zmniejszyć koszt obliczeń wykonywanych przy każdym wejściu użytkownika na ekran.

### Zadania

#### 4.1 Zoptymalizować historię portfela
Obecnie historia jest rekonstruowana dynamicznie z transakcji. To daje poprawność, ale jest kosztowne.

Możliwe kierunki:

- snapshoty miesięczne / dzienne,
- cache dla ostatnio liczonych zakresów,
- prekomputacja historii po zapisaniu transakcji,
- osobna tabela agregatów historycznych.

#### 4.2 Zoptymalizować `global-summary`
Aktualnie dashboard:

- iteruje po portfelach,
- dociąga ich wyceny,
- iteruje po kredytach,
- dla każdego liczy harmonogram.

To warto rozbić na:

- cache summary,
- cache sald kredytów,
- preliczone agregaty majątku netto,
- osobne endpointy dla cięższych sekcji, jeśli ekran urośnie.

#### 4.3 Ulepszyć cache cen i radaru
Warto dopracować:

- czas życia cache,
- strategię refreshu,
- fallbacki przy błędzie zewnętrznego źródła,
- rozróżnienie danych świeżych i danych ostatnio poprawnych.

#### 4.4 Ograniczyć koszt wykresów i ciężkich ekranów na frontendzie
Do rozważenia:

- dalszy code splitting,
- rozdzielenie ciężkich bibliotek wykresowych,
- ładowanie części kart i wykresów „na żądanie”,
- odświeżanie tylko aktywnej zakładki zamiast całego widoku.

### Efekt etapu
- szybsze otwieranie głównych ekranów,
- mniejsze obciążenie backendu,
- mniej problemów przy większej liczbie danych.

---

## Etap 5 — Kontrakt danych i przewidywalność zmian

### Cel
Zmniejszyć ryzyko rozjazdu frontendu i backendu.

### Zadania

#### 5.1 Zdefiniować kontrakt API
Najlepiej przez:

- OpenAPI,
- albo przynajmniej jawne DTO per endpoint.

Najpierw dla obszarów:

- portfolio,
- budżet,
- kredyty,
- radar,
- symbol mapping.

#### 5.2 Generować lub współdzielić typy
Dzięki temu frontend nie będzie ręcznie zgadywał pól odpowiedzi.

#### 5.3 Ujednolicić nazewnictwo pól i struktur odpowiedzi
Szczególnie przy:

- listach,
- obiektach summary,
- błędach,
- danych historycznych,
- odpowiedziach POST / PATCH / DELETE.

### Efekt etapu
- mniej błędów integracyjnych,
- szybsza praca przy refaktorach,
- prostsze wykorzystanie repo przez AI.

---

## Etap 6 — Obserwowalność, diagnostyka i utrzymanie

### Cel
Skrócić czas szukania błędów i poprawić zrozumienie zachowania systemu.

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

#### 6.3 Uporządkować logi błędów z integracji zewnętrznych
Szczególnie dla:

- yfinance,
- synchronizacji historii cen,
- wydarzeń rynkowych,
- fetchu analizy tickera.

#### 6.4 Dodać checklisty developerskie do dokumentacji
Np.:

- „co sprawdzić po zmianie w `portfolio_service.py`”,
- „jak testować import XTB”,
- „jak sprawdzić czy radar pokazuje cache czy świeże dane”.

### Efekt etapu
- szybszy debugging,
- mniej „niewidzialnych” problemów środowiskowych,
- łatwiejsza praca dla osób wracających do projektu po czasie.

---

## 4. Proponowana kolejność wdrożenia

### Kolejność rekomendowana
1. **Etap 1 — Stabilizacja podstaw**.
2. **Etap 2 — Ujednolicenie komunikacji frontend ↔ backend**.
3. **Etap 3 — Porządki w backendzie**.
4. **Etap 4 — Wydajność**.
5. **Etap 5 — Kontrakt danych**.
6. **Etap 6 — Obserwowalność i utrzymanie**.

Taka kolejność daje najlepszy stosunek efektu do ryzyka, bo najpierw zabezpiecza zmiany, a dopiero potem wchodzi w większe refaktory.

---

## 5. Quick wins — rzeczy do zrobienia od razu

Jeśli trzeba zacząć od kilku małych zadań o wysokim zwrocie, to najlepsze są:

1. dodać smoke test dla `global-summary`,
2. dodać smoke test dla kupna/sprzedaży portfela,
3. dodać smoke test dla transferu budżet → inwestycje,
4. przenieść inline requesty z `InvestmentRadar.tsx` i `MainDashboard.tsx` do wspólnej warstwy API,
5. wydzielić osobny moduł dla importu XTB,
6. dodać prosty pomiar czasu dla historii portfela i radaru,
7. ustalić jednolity format błędów backendu.

---

## 6. Plan produktowo-techniczny per moduł

### Inwestycje
- rozbić logikę historii, wyceny i importu,
- dodać testy dla FX, historii i importów,
- zoptymalizować liczenie serii historycznych,
- uprościć `PortfolioDetails.tsx`.

### Budżet
- dodać testy dla free pool, kopert i pożyczek,
- uprościć logikę transferów między domenami,
- lepiej udokumentować reguły biznesowe dla kopert miesięcznych i długoterminowych.

### Kredyty
- pokryć testami harmonogramy i nadpłaty,
- rozdzielić logikę bazową od symulacyjnej,
- dodać czytelniejsze DTO dla harmonogramów.

### Radar i ceny
- ustalić politykę cache,
- dodać fallback na ostatnie poprawne dane,
- dopracować widoczność stanu „dane nieświeże / odświeżone / błąd źródła”.

### Dashboard globalny
- odseparować warstwę agregacji,
- dodać cache,
- mieć testy pilnujące poprawności aktywów / zobowiązań.

---

## 7. Definicja sukcesu

Plan można uznać za skutecznie wdrażany, jeśli po kilku iteracjach projekt osiągnie następujący stan:

- kluczowe flowy są zabezpieczone testami,
- frontend korzysta ze wspólnej warstwy API,
- backend ma mniejszą złożoność modułów inwestycyjnych,
- historia portfela i dashboard działają szybciej,
- radar jest stabilniejszy przy błędach zewnętrznego źródła,
- developer i AI mogą szybciej znaleźć właściwe miejsce zmiany,
- dokumentacja rośnie przez dopisywanie do istniejących plików, a nie przez mnożenie nowych niespójnych opisów.

---

## 8. Rekomendacja końcowa

Gdybym miał wskazać **pierwsze 3 rzeczy do zrobienia od zaraz**, byłyby to:

1. **testy smoke + testy logiki dla historii portfela, dashboardu i transferów budżet ↔ inwestycje**,  
2. **ujednolicenie warstwy HTTP na frontendzie**,  
3. **rozdzielenie `routes.py` i `portfolio_service.py` na mniejsze odpowiedzialności**.

To zestaw, który da największy realny zwrot: mniej regresji, szybszą pracę i lepszą bazę pod dalsze usprawnienia.
