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

## Dodatkowa analiza architektury – możliwe usprawnienia i naprawy

Poniższe punkty wynikają z aktualnej architektury opisanej w `docs/ARCHITECTURE_FLOW.md` i z obecnego podziału projektu na React + Flask + SQLite.

### 1) Ujednolicenie warstwy API po stronie frontendu

#### Problem
Frontend komunikuje się z backendem w kilku stylach jednocześnie:
- przez wspólne klienty Axios (`api.ts`, `api_loans.ts`),
- przez własne moduły z `fetch` (`api_budget.ts`, `api_symbol_map.ts`),
- przez bezpośrednie wywołania `fetch`/`axios` wewnątrz komponentów.

#### Ryzyko
- niespójna obsługa błędów,
- powielanie logiki requestów,
- trudniejsze dodanie wspólnych interceptorów, timeoutów i loggera,
- wyższy koszt utrzymania i refaktoryzacji.

#### Rekomendacja
- ustandaryzować komunikację do jednego wzorca:
  - albo wszystko przez Axios,
  - albo wszystko przez lekką wspólną warstwę `fetch` + helpery.
- dodać wspólny moduł np. `frontend/src/lib/http.ts`, który odpowiada za:
  - base URL,
  - parsowanie błędów,
  - timeouty,
  - obsługę statusów 4xx/5xx,
  - ewentualne logowanie developerskie.

#### Priorytet
Wysoki.

---

### 2) Rozdzielenie odpowiedzialności w `backend/routes.py`

#### Problem
Moduł inwestycyjny ma dużo endpointów z różnych podobszarów:
- portfele,
- transakcje,
- obligacje,
- oszczędności,
- historia,
- PPK,
- importy.

#### Ryzyko
- plik staje się trudny do nawigacji,
- większe ryzyko konfliktów przy równoległej pracy kilku osób,
- trudniej znaleźć odpowiedzialny endpoint,
- większa szansa na regresje przy zmianach w pozornie odległych obszarach.

#### Rekomendacja
Rozbić `routes.py` na mniejsze blueprinty lub moduły, np.:
- `routes_portfolios.py`,
- `routes_transactions.py`,
- `routes_holdings.py`,
- `routes_ppk.py`,
- `routes_imports.py`.

Nie trzeba zmieniać publicznych URL-i – wystarczy zachować ten sam prefiks `/api/portfolio`, a wewnątrz rozdzielić odpowiedzialność plików.

#### Priorytet
Wysoki.

---

### 3) Brak wyraźnego kontraktu DTO między backendem a frontendem

#### Problem
Typy po stronie frontendu są ręcznie utrzymywane i mogą się rozjechać z odpowiedziami JSON backendu.

#### Ryzyko
- frontend może zakładać pola, których backend nie zwraca,
- backend może zmienić nazwę pola bez natychmiastowego błędu kompilacji w całym systemie,
- większe koszty onboardingu i testowania regresji.

#### Rekomendacja
- zdefiniować kontrakt API w jednym miejscu, najlepiej przez:
  - OpenAPI,
  - albo wspólne schema/DTO,
  - albo przynajmniej zestaw udokumentowanych odpowiedzi per endpoint.
- rozważyć generowanie typów dla frontendu z definicji API.

#### Priorytet
Wysoki.

---

### 4) Zbyt duża ilość logiki obliczeniowej w runtime requestów dashboardowych

#### Problem
Dashboard globalny agreguje dane z kilku modułów i dla kredytów wylicza harmonogramy, a dla inwestycji pobiera wyceny i agregacje.

#### Ryzyko
- dłuższy czas odpowiedzi dla `/api/dashboard/global-summary`,
- spadek responsywności przy większej liczbie portfeli i kredytów,
- trudniejsza diagnostyka, który fragment spowalnia odpowiedź.

#### Rekomendacja
- dodać pomiar czasu wykonania kluczowych operacji,
- wydzielić cięższe agregacje do warstwy cache lub precomputingu,
- rozważyć osobne endpointy dla części dashboardu, jeśli ekran stanie się jeszcze cięższy.

#### Priorytet
Średnio-wysoki.

---

### 5) SQLite jako wspólna baza dla wielu obszarów domenowych

#### Problem
SQLite jest prosta i wygodna lokalnie, ale przy rosnącej liczbie danych i jednoczesnych operacjach może stać się wąskim gardłem.

#### Ryzyko
- ograniczona współbieżność zapisów,
- trudniejsza migracja schematu przy większym zespole,
- ryzyko rosnących zależności ukrytych w SQL-ach rozproszonych po serwisach.

#### Rekomendacja
- krótkoterminowo: uporządkować migracje i dodać jawny changelog schematu,
- średnioterminowo: przygotować kod do ewentualnej migracji na PostgreSQL,
- ograniczyć powielanie surowych zapytań przez helpery/repository dla najbardziej krytycznych tabel.

#### Priorytet
Średni.

---

### 6) Brak pełnej warstwy testów regresji

#### Problem
Architektura ma kilka miejsc o wysokim ryzyku regresji:
- wyceny portfeli,
- harmonogramy kredytów,
- transfery budżet ↔ inwestycje,
- importy CSV i mapowanie symboli,
- agregacje dashboardu globalnego.

#### Ryzyko
- zmiana w jednym module psuje inny moduł,
- trudniej bezpiecznie refaktoryzować,
- ręczne testowanie staje się zbyt kosztowne.

#### Rekomendacja
Zbudować minimalny pakiet testów smoke i testów biznesowych:
- backend:
  - test create/list portfolio,
  - test transfer budżet → portfel,
  - test amortization schedule,
  - test symbol mapping dla importu,
  - test global-summary.
- frontend:
  - test renderu dashboardu,
  - test formularza tworzenia portfela,
  - test radaru z mockiem API.

#### Priorytet
Bardzo wysoki.

---

### 7) Brak wspólnej strategii obserwowalności i debugowania

#### Problem
W systemie są logi, ale nie ma jeszcze jednej spójnej strategii typu:
- request id,
- correlation id,
- metryki czasu odpowiedzi,
- jasny podział logów aplikacyjnych i błędów biznesowych.

#### Ryzyko
- trudniej analizować problemy środowiskowe,
- ciężko odtworzyć pełny przebieg requestu przez kilka modułów,
- większy koszt debugowania błędów „sporadycznych”.

#### Rekomendacja
- dodać middleware/request hook nadający `request_id`,
- logować początek i koniec requestu oraz czas wykonania,
- ujednolicić strukturę logów JSON lub przynajmniej wspólny format.

#### Priorytet
Średni.

---

### 8) Brak warstwy walidacji payloadów w backendzie

#### Problem
Walidacja requestów w wielu endpointach opiera się głównie na ręcznym sprawdzaniu pól w `routes*.py`.

#### Ryzyko
- niespójne komunikaty błędów,
- większa ilość duplikacji,
- większe ryzyko przepuszczenia niepełnych lub źle sformatowanych danych.

#### Rekomendacja
- dodać warstwę walidacji DTO/schematów, np. przez:
  - Marshmallow,
  - Pydantic,
  - albo własny, prosty zestaw walidatorów requestów.

#### Priorytet
Średnio-wysoki.

---

### 9) Code splitting frontendu i wydajność ekranów z wykresami

#### Problem
Aplikacja używa kilku bibliotek do wykresów i ma cięższe moduły (dashboard, radar, kredyty, analityka).

#### Ryzyko
- duży bundle startowy,
- wolniejszy pierwszy render,
- dłuższy czas interakcji na słabszych urządzeniach.

#### Rekomendacja
- utrzymać i rozszerzać lazy loading ekranów,
- wydzielić wspólne chunky dla bibliotek wykresowych,
- sprawdzić, czy wszystkie wykresy muszą ładować się od razu.

#### Priorytet
Średni.

---

### 10) Jawne zależności krzyżowe między modułami domenowymi

#### Problem
To cecha biznesowa, ale wymaga kontroli:
- budżet wpływa na inwestycje,
- kredyty wpływają na dashboard globalny,
- radar korzysta z holdings,
- import inwestycji zależy od symbol mapping.

#### Ryzyko
- pozornie lokalna zmiana psuje zewnętrzny moduł,
- trudniej przewidzieć wpływ refaktoryzacji,
- potrzeba większej liczby testów integracyjnych niż sugeruje podział plików.

#### Rekomendacja
- jawnie utrzymywać mapę zależności w dokumentacji,
- przy zmianach w modułach wspólnych robić checklistę „co jeszcze może się zepsuć?”,
- dodać testy przekrojowe między modułami.

#### Priorytet
Wysoki.

## Szybkie naprawy o największym zwrocie

Poniżej lista działań, które dają dobry efekt przy relatywnie małym koszcie wdrożenia.

### Quick wins (1–3 dni)
1. Ujednolicić obsługę błędów HTTP po stronie frontendu.
2. Dodać wspólny helper HTTP dla wszystkich modułów.
3. Uporządkować lint debt: nieużywane importy, podstawowe `any`, drobne warningi React.
4. Dodać smoke test dla `/api/dashboard/global-summary`.
5. Dodać smoke test dla przepływu tworzenia portfela.

### Krótki termin (1 sprint)
1. Rozbić `backend/routes.py` na mniejsze moduły.
2. Dodać schemat walidacji requestów backendowych.
3. Dodać pomiar czasu dla najcięższych endpointów.
4. Ograniczyć największe źródła bundla po stronie frontendu.

### Średni termin (2–3 sprinty)
1. Wprowadzić kontrakt DTO / OpenAPI.
2. Rozbudować testy integracyjne przekrojowe.
3. Uporządkować logowanie i correlation id.
4. Przygotować ścieżkę migracji z SQLite na mocniejszą bazę, jeśli projekt będzie rósł.

## Proponowany plan poprawy – etapami

## Etap 1 – Stabilizacja podstaw (najwyższy priorytet)

### Cel
Zmniejszyć ryzyko regresji i ujednolicić najbardziej newralgiczne elementy.

### Zakres
- frontend lint cleanup,
- wspólna obsługa błędów HTTP,
- podstawowe smoke testy backendu,
- podstawowe testy UI dla kluczowych ekranów.

### Efekt
- szybsze i bezpieczniejsze drobne zmiany,
- mniej losowych błędów po refaktorach,
- łatwiejszy onboarding.

---

## Etap 2 – Porządkowanie architektury aplikacyjnej

### Cel
Zmniejszyć złożoność plików i ujednolicić kontrakty danych.

### Zakres
- podział `routes.py`,
- walidacja requestów DTO/schema,
- uporządkowanie warstwy API frontendu,
- wspólne typy odpowiedzi lub OpenAPI.

### Efekt
- czytelniejsza architektura,
- mniej duplikacji,
- niższy koszt utrzymania.

---

## Etap 3 – Wydajność i obserwowalność

### Cel
Zidentyfikować oraz ograniczyć koszt ciężkich endpointów i ekranów.

### Zakres
- profilowanie dashboardu,
- pomiary czasu requestów,
- dalszy code splitting,
- logowanie request id i czasu wykonania,
- analiza cache dla danych agregacyjnych.

### Efekt
- lepsza responsywność,
- prostsza diagnostyka problemów produkcyjnych,
- większa gotowość projektu na dalszy wzrost.

---

## Etap 4 – Skalowanie i dojrzałość procesu

### Cel
Przygotować projekt na większy zespół i większy wolumen zmian.

### Zakres
- pełniejszy zestaw testów integracyjnych,
- pipeline jakościowy z obowiązkowym lint/test/build,
- migracje schematu danych,
- analiza przejścia na silniejszą bazę danych, jeśli zajdzie potrzeba.

### Efekt
- lepsza przewidywalność wdrożeń,
- większa odporność na regresje,
- prostsze skalowanie repo i zespołu.

## Rekomendowana kolejność wdrożenia

1. **Najpierw bezpieczeństwo zmian:** testy smoke + cleanup lint + wspólny helper HTTP.
2. **Potem porządek architektoniczny:** podział `routes.py`, walidacja requestów, kontrakt DTO.
3. **Następnie wydajność:** bundle, dashboard, cache, profiling.
4. **Na końcu skalowanie procesu:** logging, CI gates, migracje danych, strategia DB.

## Finalna rekomendacja

Gdybym miał wskazać tylko 5 rzeczy do zrobienia w pierwszej kolejności, wybrałbym:

1. dodać testy smoke dla krytycznych endpointów,
2. ujednolicić warstwę HTTP w frontendzie,
3. rozbić `backend/routes.py` na mniejsze moduły,
4. wdrożyć walidację payloadów backendowych,
5. ograniczyć lint debt i `any` w frontendzie.
