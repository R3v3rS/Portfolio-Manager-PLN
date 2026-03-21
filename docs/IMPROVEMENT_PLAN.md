# Plan usprawnień aplikacji Portfolio Manager (PLN)

Ten dokument jest aktualnym planem działania dla projektu po wykonanych refaktorach i po ponownej weryfikacji repo w dniu 2026-03-21.

Łączy dwie perspektywy:
- **co jest już faktycznie wykonane i potwierdzone w repo**, 
- **co nadal wymaga domknięcia**, żeby projekt był spójny, przewidywalny i bezpieczny przy kolejnych zmianach.

Dokument został zaktualizowany po przeglądzie repo oraz wnioskach z:
- `docs/PROJECT_GUIDE.md`,
- `docs/AUDIT_API_FRONTEND_BACKEND_INTEGRATION_2026-03-21.md`.

---

## 0. Snapshot stanu projektu

### Co jest już potwierdzone jako wykonane

#### Etap 1 — Stabilizacja podstaw
Stan: **w dużej mierze wykonany, ale nie w pełni zielony jakościowo**.

Potwierdzone w repo i komendami:
- frontend przechodzi `npm --prefix frontend run check`,
- frontend przechodzi `npm --prefix frontend run build`,
- backend przechodzi `python -m compileall backend`,
- istnieje smoke test krytycznych endpointów `python backend/test_smoke_endpoints.py`,
- istnieje także test kontraktu API `python -m unittest backend.test_api_contract`,
- najważniejsze flowy backendowe mają przynajmniej podstawową automatyczną weryfikację integracyjną i kontraktową.

Dodatkowa weryfikacja wykazała też, że:
- skrypt `npm --prefix frontend run lint` istnieje, ale obecnie **nie przechodzi**,
- główne problemy lintu to `no-explicit-any`, `no-unused-vars` i ostrzeżenia hook dependencies.

Wniosek: Etap 1 nie jest już „tylko częściowo zaczęty” — jego fundament został realnie domknięty. Nadal jednak nie można go uznać za całkowicie zamknięty, dopóki lint frontendu pozostaje czerwony i testy biznesowe są wciąż ograniczone.

#### Etap 2 — Ujednolicenie komunikacji frontend ↔ backend
Stan: **w dużej mierze wykonany, ale nie domknięty po stronie backendowego standardu odpowiedzi**.

Potwierdzone wykonanie:
- istnieje wspólny klient HTTP `frontend/src/http.ts`,
- istnieje wspólny parser odpowiedzi `frontend/src/http/response.ts`,
- istnieją helpery `extractPayload`, `extractErrorMessage`, `parseJsonApiResponse`,
- najważniejsze requesty zostały przepięte przez wspólne moduły API,
- dashboard, radar, budżet i część importów korzystają już z ujednoliconej warstwy integracyjnej,
- frontend ma compatibility layer dla `payload / data / raw JSON` oraz dla legacy error shape.

Wniosek: największy historyczny problem po stronie frontendu został już w praktyce rozwiązany. Otwarty pozostaje głównie brak pełnej standaryzacji backendowych odpowiedzi.

#### Etap 3 — Porządki w backendzie i podziale odpowiedzialności
Stan: **w dużej mierze wykonany strukturalnie i istotnie domknięty kontraktowo dla głównych route'ów**.

Potwierdzone wykonanie:
- backend jest podzielony na mniejsze moduły route’ów,
- logika portfolio została rozbita na mniejsze serwisy,
- krytyczne endpointy są objęte smoke testem,
- istnieją canonical helpers `success_response` / `error_response`,
- działa globalny exception handling,
- istnieje test kontraktu API dla głównych endpointów.

Otwarte elementy Etapu 3:
- rozszerzanie coverage kontraktu na wszystkie mniej krytyczne endpointy,
- dalsze porządkowanie semantyki payloadów i DTO,
- ograniczenie lokalnego łapania `Exception`.

### Najważniejszy wniosek po aktualizacji planu

Największy bieżący problem projektu nie leży już w braku wspólnej warstwy frontendowej, bo ta została wdrożona.

Największe otwarte ryzyko to dziś:
- **niepełne pokrycie wszystkich endpointów testem kontraktu API i dalszym egzekwowaniem standardu**, 
- **dług typowania i DTO w części ekranów**,
- **czerwony lint frontendu**,
- **brak pełnego manualnego E2E UI oraz szerszych testów regresji biznesowej**.

---

## 1. Najważniejsze problemy do rozwiązania teraz

Na podstawie aktualnego stanu repo najwyższy wpływ na jakość mają dziś następujące obszary:

1. **Rozszerzenie egzekwowania kontraktu backendowych odpowiedzi na wszystkie endpointy**.
2. **Dalsze porządkowanie semantyki błędów backendu** (`error.code`, `error.message`, `error.details`) i coverage testowego.
3. **Nadal obecny dług typowania i lokalnych założeń DTO w części UI**.
4. **Brak rozszerzonych testów regresji dla logiki biznesowej wysokiego ryzyka**.
5. **Brak pełnego manualnego E2E smoke testu frontendu po głównych ekranach**.
6. **Lint frontendu jest czerwony i ujawnia zaległości typowania oraz porządku kodu**.
7. **Ostrzeżenia o dużych chunkach frontendu przy buildzie**.

---

## 2. Priorytety strategiczne po aktualizacji planu

### Priorytet P1 — Rozszerzenie i utrzymanie standardu backendowego API
To jest obecnie priorytet absolutny.

Trzeba doprowadzić do tego, żeby wdrożony już standard backendu był pokryty testem i konsekwentnie utrzymany dla wszystkich endpointów.

### Priorytet P2 — Rozszerzenie jakości i testów regresji
Drugi priorytet to zwiększyć pewność zmian przez lepsze testy biznesowe oraz manualny smoke test UI.

### Priorytet P3 — Dalsze porządki typów i DTO na frontendzie
Wspólna warstwa HTTP już istnieje; teraz trzeba ograniczyć resztki `any` i doprecyzować modele danych.

### Priorytet P4 — Wydajność i obserwowalność
Po ustabilizowaniu kontraktu warto szerzej optymalizować i poprawiać monitoring.

---

## 3. Plan etapami — status + dalsze działania

## Etap 1 — Stabilizacja podstaw

### Status
**W dużej mierze wykonany i dobrze potwierdzony automatycznie.**

### Co zostało zrobione / potwierdzone
- istnieje działający minimalny quality gate dla repo,
- frontend przechodzi check i build,
- backend przechodzi kompilację modułów,
- istnieje smoke test krytycznych endpointów backendu,
- istnieje test kontraktu API dla głównych route'ów,
- smoke test obejmuje dashboard, portfolio, budżet, kredyty, radar i symbol map.

### Co zostało do zrobienia

#### 1.1 Rozszerzyć smoke testy backendu o kolejne edge case’y
Na start warto dodać scenariusze:
- błędny payload dla buy / sell,
- błędny payload dla transferów budżetowych,
- puste i częściowe dane dla krytycznych summary endpointów,
- błędy importu i mapowania symboli.

#### 1.2 Domknąć testy logiki biznesowej dla obszarów wysokiego ryzyka
Najwyższy priorytet mają:
- rekonstrukcja historii portfela,
- liczenie wartości i zysku portfela,
- import XTB CSV,
- transfery budżet ↔ inwestycje,
- harmonogramy kredytów,
- dashboard globalny.

#### 1.3 Domknąć quality gate o zielony lint i kolejne testy
Obecne minimum już działa, ale nadal wymaga domknięcia:
- naprawić bieżące błędy `npm --prefix frontend run lint`,
- dodać bardziej granularne testy backendowe,
- rozważyć testy UI dla kluczowych flowów.

### Efekt końcowy etapu
- zmiany będą bezpieczniejsze,
- regresje będą szybciej wykrywane,
- repo będzie gotowe do dalszego porządkowania kontraktu API.

---

## Etap 2 — Ujednolicenie komunikacji frontend ↔ backend

### Status
**W dużej mierze wykonany po stronie frontendu i w dużej mierze domknięty na granicy API.**

### Co zostało już zrobione
- istnieje wspólny HTTP layer,
- istnieje centralny `unwrap payload`,
- istnieje centralny parser błędów,
- istnieje `parseJsonApiResponse`,
- najważniejsze ekrany zostały przepięte na moduły API,
- frontend obsługuje stary i nowszy kształt odpowiedzi.

### Co trzeba zrobić teraz priorytetowo

#### 2.1 Rozszerzyć zgodność backendu ze wspólnym kontraktem na pełne API
Dla głównych route'ów standard już działa, ale trzeba go jeszcze konsekwentnie utrzymać i objąć nim mniej krytyczne endpointy, tak aby frontend nie musiał długoterminowo utrzymywać szerokiej warstwy kompatybilności.

#### 2.2 Kontynuować normalizację DTO na granicy API
Dla każdego istotnego modułu warto utrzymywać:
- wejście jako `unknown`,
- normalizację do jawnego modelu,
- bezpieczne fallbacki dla pól opcjonalnych.

#### 2.3 Dokończyć przegląd mniej krytycznych ekranów
W pierwszej kolejności warto jeszcze przejrzeć:
- mniej używane modale i flowy specjalne,
- ekrany z pozostałym `any`,
- miejsca, gdzie shape odpowiedzi nie jest jeszcze wyraźnie normalizowany.

#### 2.4 Utrzymać ujednolicony flow XTB import i ograniczyć warstwę legacy
Frontend zachowuje kompatybilność przejściową, ale aktualny route XTB zwraca już standard błędu z `error.details.missing_symbols`; kolejne zmiany nie powinny wracać do legacy shape.

### Efekt końcowy etapu
- frontend pozostanie odporny na zmiany,
- kompatybilność przestanie być głównym źródłem ryzyka,
- utrzymanie modułów API będzie prostsze.

---

## Etap 3 — Porządki w backendzie i podziale odpowiedzialności

### Status
**W dużej mierze wykonany strukturalnie, z wdrożonym kontraktem dla głównych route'ów; wymaga dalszego rozszerzania coverage i walidacji.**

### Co już zostało zrobione

#### 3.1 Rozbicie `backend/routes.py`
To jest wykonane.

Aktualny podział obejmuje m.in.:
- `routes_portfolios.py`,
- `routes_transactions.py`,
- `routes_history.py`,
- `routes_imports.py`,
- `routes_ppk.py`,
- `routes_admin.py`,
- `routes_budget.py`,
- `routes_dashboard.py`,
- `routes_loans.py`,
- `routes_radar.py`,
- `routes_symbol_map.py`.

#### 3.2 Rozbicie logiki portfela na mniejsze serwisy
To również jest wykonane.

W repo są już m.in.:
- `portfolio_history_service.py`,
- `portfolio_import_service.py`,
- `portfolio_valuation_service.py`,
- `portfolio_trade_service.py`,
- `portfolio_audit_service.py`,
- `portfolio_core_service.py`.

#### 3.3 Smoke test krytycznych endpointów
To również należy uznać za wykonany krok porządkujący backend.

#### 3.4 Test kontraktu API
To jest już wykonane dla głównych endpointów i realnie podnosi poziom bezpieczeństwa zmian kontraktowych.

### Co zostało do zrobienia

#### 3.5 Ustandaryzować walidację requestów
Najpierw trzeba objąć walidacją endpointy:
- tworzenia portfela,
- buy / sell,
- importów,
- transferów budżetowych,
- kredytów i nadpłat.

#### 3.6 Rozszerzać i egzekwować kontrakt success / error
Kierunek jest już wdrożony dla głównych route'ów:
- sukces: envelope `{ payload: ... }`,
- błąd: `{ error: { code, message, details } }`.

Teraz trzeba przede wszystkim:
- utrzymać ten standard przy nowych zmianach,
- rozszerzać coverage testów kontraktowych,
- dopinać mniej krytyczne endpointy i obrzeża API.

#### 3.7 Ograniczyć lokalne `except Exception`
Mapowanie wyjątków powinno być centralne i przewidywalne.

### Efekt końcowy etapu
- backend będzie naprawdę spójny kontraktowo,
- frontendowa compatibility layer będzie mogła zostać uproszczona,
- kolejne refaktory będą bezpieczniejsze.

---

## Etap 4 — Wydajność historii, dashboardu i radaru

### Status
**Do zrobienia po pełnym domknięciu kontraktu backendowego.**

### Zadania

#### 4.1 Zoptymalizować historię portfela
Możliwe kierunki:
- snapshoty miesięczne / dzienne,
- cache dla liczonych zakresów,
- prekomputacja po zapisaniu transakcji,
- osobna tabela agregatów historycznych.

#### 4.2 Zoptymalizować `global-summary`
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
**Do zrobienia równolegle z końcówką Etapu 3.**

### Zadania

#### 5.1 Zdefiniować formalny kontrakt API
Najlepiej przez:
- OpenAPI,
- albo przynajmniej jawne DTO per endpoint.

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
**Wciąż ważne, ale wtórne wobec kontraktu backendowego i testów.**

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

1. **Rozszerzać Etap 3** — coverage kontraktu API, walidacja requestów i dalsze uproszczenie obsługi błędów.
2. **Rozszerzać Etap 1** — więcej testów regresji i pełniejszy quality gate.
3. **Równolegle rozpocząć Etap 5** — formalizacja DTO / OpenAPI.
4. **Dalej porządkować Etap 2 na obrzeżach** — usuwać pozostałe legacy assumptions i `any`.
5. **Dopiero potem szerzej robić Etap 4 i 6** — wydajność i obserwowalność.

To jest najbardziej sensowna kolejność po obecnym stanie projektu: wspólna warstwa frontendowa już działa, a największe ryzyko siedzi dziś po stronie kontraktu backendowego i jakości walidacji.

---

## 5. Quick wins — rzeczy do zrobienia od razu

Najwyższy zwrot teraz dadzą:

1. rozszerzyć test kontraktu API na kolejne endpointy,
2. dodać testy błędnych payloadów buy / sell / transfer,
3. ograniczyć najbardziej ryzykowne `any` w warstwie integracyjnej UI,
4. uruchomić manualny smoke test ekranów: dashboard, radar, budżet, portfolio details,
5. naprawić aktualne błędy `npm --prefix frontend run lint`,
6. utrzymać lint jako obowiązkowy element minimalnego quality gate,
7. rozważyć podział największych chunków frontendu.

---

## 6. Plan produktowo-techniczny per moduł

### Inwestycje
Zrobione / poprawione:
- rozbita logika serwisowa,
- lepszy podział odpowiedzialności backendu,
- podstawowy smoke test flowów portfolio.

Do zrobienia:
- objąć testami błędne i graniczne payloady buy / sell / import / historię,
- przepiąć backend na wspólny envelope,
- dalej ograniczać integracyjne `any` w `PortfolioDetails.tsx` i powiązanych komponentach.

### Budżet
Zrobione / poprawione:
- istnieje wydzielona warstwa API,
- summary i akcje korzystają ze wspólnego klienta HTTP,
- flow transferów jest objęty smoke testem backendowym.

Do zrobienia:
- dodać więcej testów dla free pool, kopert i transferów,
- dopiąć finalny standard odpowiedzi backendowych,
- przejrzeć pozostałe edge case’y UI.

### Kredyty
Zrobione / poprawione:
- istnieje osobny moduł i logika harmonogramów,
- harmonogram jest objęty smoke testem backendowym.

Do zrobienia:
- dodać walidację requestów,
- pokryć harmonogramy i nadpłaty dodatkowymi testami,
- ujednolicić kontrakt odpowiedzi harmonogramów.

### Radar i ceny
Zrobione / poprawione:
- istnieje osobny moduł radarowy,
- frontend radaru korzysta ze wspólnej warstwy HTTP,
- flow odświeżania jest objęty smoke testem backendowym.

Do zrobienia:
- dopracować semantykę „dane świeże / nieświeże / błąd źródła”,
- dodać więcej fallbacków i testów regresji,
- zoptymalizować wydajność/caching po domknięciu kontraktu backendowego.

### Dashboard globalny
Zrobione / poprawione:
- istnieje osobny endpoint i ekran,
- frontend dashboardu korzysta z dedykowanego modułu API,
- odpowiedź jest normalizowana do bezpiecznego modelu,
- endpoint jest objęty smoke testem.

Do zrobienia:
- ujednolicić finalny kontrakt odpowiedzi backendu,
- przeprowadzić manualny smoke test UI,
- w kolejnym kroku dodać cache.

### Symbol mapping / importy
Zrobione / poprawione:
- istnieje osobny panel i osobny moduł API,
- import XTB ma kompatybilność frontendu dla `missing_symbols`,
- symbol map jest objęty smoke testem backendowym.

Do zrobienia:
- utrzymać backend na `error.details.missing_symbols` bez regresji do legacy shape,
- zachować zgodność przejściową tylko tam, gdzie jest jeszcze naprawdę potrzebna,
- dodać dalsze testy regresji importu i mapowania symboli.

---

## 7. Definicja sukcesu po tej aktualizacji planu

Plan będzie można uznać za skutecznie wdrażany, jeśli projekt osiągnie następujący stan:

- backend zwraca jeden spójny format success/error i ma to szeroko pokryte testem kontraktu,
- `error.details` jest wszędzie przewidywalne i słownikowe,
- frontend ogranicza compatibility hacks do minimum,
- najważniejsze flowy mają smoke testy i dodatkowe testy regresji,
- krytyczne obszary biznesowe mają lepsze pokrycie testami,
- dashboard, radar, budżet i portfolio details przejdą także manualny smoke test UI,
- dokumentacja opisuje stan faktyczny: co zrobione, co do zrobienia i w jakiej kolejności.

---

## 8. Rekomendacja końcowa

Najważniejsza zmiana względem wcześniejszej wersji planu jest taka:
- **Etap 1 nie jest już tylko planem — jego minimalny quality gate działa, choć pełny gate z lintem nadal wymaga domknięcia**,
- **Etap 2 nie jest już główną dziurą architektoniczną po stronie frontendu — wspólna warstwa HTTP została wdrożona**,
- **główny ciężar prac przesunął się teraz na rozszerzanie coverage kontraktu, walidację, lint frontendu i dalsze testy regresji**.

Krótko: fundament integracyjny jest już postawiony; teraz trzeba go uporządkować kontraktowo i testowo do poziomu przewidywalnego standardu zespołowego.
