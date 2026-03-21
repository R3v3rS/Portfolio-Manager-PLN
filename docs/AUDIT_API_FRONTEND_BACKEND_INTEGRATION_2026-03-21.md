# Audit – API / Frontend / Backend Integration

Data audytu: 2026-03-21  
Data aktualizacji po ponownej weryfikacji repo: 2026-03-21  
Zakres: kontrakt API, warstwa HTTP frontendu, compatibility unwrap/error parsing, krytyczne ekrany UI, quality gate, lint i smoke testy backendu.

## Status końcowy

- **Stan jest wyraźnie lepszy niż w pierwotnej wersji audytu.**
- **Najważniejsze elementy warstwy integracyjnej po stronie frontendu zostały już wdrożone.**
- **Projekt nie ma dziś czerwonego, oczywistego blokera builda ani podstawowych smoke testów**, a backend ma już **wprowadzony globalny kontrakt odpowiedzi dla helperów i centralnego exception handlingu**; nadal pozostają **otwarte ryzyka kontraktowe endpoint-by-endpoint**, bo odpowiedzi success/error nie są jeszcze w pełni ujednolicone na każdym route.
- **Pełny quality gate nadal nie jest zielony**, ponieważ osobno uruchomiony lint frontendu kończy się błędami `@typescript-eslint/no-explicit-any` i `@typescript-eslint/no-unused-vars` oraz ostrzeżeniami `react-hooks/exhaustive-deps`.

Najważniejsza zmiana względem wcześniejszej wersji audytu:
- frontend ma już wspólny klient HTTP,
- istnieją wspólne helpery `extractPayload`, `extractErrorMessage`, `parseJsonApiResponse`,
- najważniejsze ekrany zostały przepięte na wspólną warstwę,
- quality gate został potwierdzony komendami,
- backend ma smoke test krytycznych endpointów.

---

## 1. Frontend – parsowanie odpowiedzi

### 1.1 HTTP layer

**Wynik: PASS z pozostałym zakresem do obserwacji**

Frontend ma już jedną wspólną warstwę HTTP:
- `frontend/src/http.ts` – wspólny klient requestów,
- `frontend/src/http/response.ts` – wspólny parser odpowiedzi i błędów,
- `frontend/src/apiConfig.ts` – wspólna konfiguracja ścieżek `/api/...`.

Dodatkowo w samym kodzie obowiązuje komentarz architektoniczny, że komponenty nie powinny wykonywać bezpośrednich requestów HTTP, tylko korzystać z modułów API.

W aktualnym przeglądzie nie znaleziono już bezpośrednich `fetch(...)`, `axios.create(...)` ani inline `axios.get(...)` w kodzie aplikacji poza implementacją wspólnego klienta HTTP.

### 1.2 unwrap payload

**Wynik: PASS**

Istnieje centralny unwrap odpowiedzi:
- `extractPayload(responseBody)`

Obsługiwane warianty:
- `{ payload: ... }`,
- `{ data: ... }`,
- surowy JSON jako fallback,
- `undefined` i `null` bez crasha parsera.

To zamyka jeden z głównych problemów wskazanych wcześniej w audycie.

### 1.3 undefined / null crash

**Wynik: POPRAWA / RYZYKO OGRANICZONE, ALE NIEZEROWE**

Sytuacja jest już istotnie lepsza niż wcześniej, bo krytyczne ekrany nie bazują na „gołym” `res.data` czy `response.json()` bez normalizacji.

Najważniejsze poprawy:
- `MainDashboard` korzysta z `dashboardApi.getGlobalSummary()` i fallbacku `EMPTY_GLOBAL_SUMMARY`,
- `InvestmentRadar` korzysta z `radarApi` oraz ustawia bezpieczne fallbacki (`[]`, komunikat błędu),
- `BudgetDashboard` i `StockProfilerModal` korzystają ze wspólnego parsera błędów,
- moduły API normalizują odpowiedzi do przewidywalnych kształtów obiektów/tablic.

Ryzyko nadal istnieje, ale jest już bardziej związane z:
- niepełną standaryzacją backendu,
- lokalnymi typami `any` w części ekranów,
- pojedynczymi miejscami, gdzie backend zwraca legacy shape zamiast jednego envelope.

### 1.4 Dashboard (najważniejsze)

**Wynik: PASS funkcjonalny / kontrakt nadal legacy**

Dashboard nie konsumuje już odpowiedzi inline przez `axios.get(...)`.

Aktualny stan:
- `MainDashboard.tsx` używa `dashboardApi.getGlobalSummary()`,
- odpowiedź jest normalizowana przez `normalizeGlobalSummary(...)`,
- ekran ma bezpieczny stan pusty `EMPTY_GLOBAL_SUMMARY`,
- błędy są mapowane przez `extractErrorMessageFromUnknown(...)`.

Uwaga:
- backend nadal zwraca realny kontrakt oparty o pola `net_worth`, `total_assets`, `total_liabilities`, `liabilities_breakdown`, `assets_breakdown`, `quick_stats`,
- nie ma dowodu, że docelowy kontrakt typu `total_value` / `portfolio_value` / `budget_summary` został wdrożony globalnie.

Wniosek: dashboard jest już zabezpieczony integracyjnie, a endpoint `global-summary` został przepięty na envelope `{ payload: ... }` bez zmiany wewnętrznego shape danych. Formalny docelowy kontrakt backendowy nadal wymaga jednak dalszego ujednolicania poza tym endpointem.

---

## 2. Frontend – obsługa błędów

### 2.1 error envelope

**Wynik: PASS dla warstwy frontendowej / MIXED dla całego systemu**

Frontend ma już wspólną obsługę błędów w parserze odpowiedzi.

Parser wykrywa m.in.:
- `error.message`,
- `error.details`,
- `error.code`,
- legacy `{ error: "..." }`,
- `success === false` i `ok === false`,
- pustą lub niejednoznaczną odpowiedź z fallbackiem komunikatu.

Nadal otwarte pozostaje to, że backend nie zwraca jeszcze wszędzie jednego, identycznego envelope błędu.

### 2.2 extractErrorMessage

**Wynik: PASS**

Istnieje wspólny helper:
- `extractErrorMessage(errorBody)`

oraz dodatkowo:
- `extractErrorMessageFromUnknown(error)`.

To domyka brak wskazany w pierwotnym audycie.

### 2.3 XTB import

**Wynik: PASS kompatybilnościowy po stronie frontendu / backend nadal legacy**

Frontend obsługuje scenariusz `missing_symbols` zarówno dla starego, jak i nowszego kształtu danych:
- legacy: `missing_symbols` na root obiektu,
- nowszy wariant: `error.details.missing_symbols`.

Backendowy serwis importu nadal zwraca legacy shape:
- `{ success: False, missing_symbols: [...] }`.

Wniosek: flow importu jest lepiej zabezpieczony niż wcześniej, ale pełna standaryzacja backendowego error envelope nadal pozostaje do wykonania.

---

## 3. Backend – kontrakt API

### 3.1 Success response

**Wynik: POPRAWA / nadal MIXED jako pełny standard systemowy**

Backend ma już centralny helper docelowego kontraktu sukcesu `success_response(payload, status=...)`, ale nie ma jeszcze dowodu, że wszystkie endpointy backendu używają go konsekwentnie.

Backend nadal zwraca mieszankę odpowiedzi, ale zakres legacy został zawężony. Portfolio i dashboard mają już wdrożony canonical envelope dla odpowiedzi sukcesu, natomiast inne moduły nadal zawierają miks shape'ów, np.:
- surowe listy,
- surowe obiekty,
- obiekty z `message`,
- obiekty domenowe typu `baseline`, `simulation`, `tickers`.

To oznacza, że **frontend jest dziś przygotowany kompatybilnościowo**, ale **backend nie jest jeszcze formalnie ujednolicony kontraktowo**.

### 3.2 Spójność payload

**Wynik: FAIL jako pełna standaryzacja**

Wciąż istnieją endpointy zwracające różne shape’y bez jednego envelope. Dotyczy to m.in. list, obiektów summary oraz odpowiedzi akcyjnych z `message`.

Najważniejsza zmiana względem starego audytu brzmi jednak tak:
- to już nie jest krytyczny problem „bo frontend się wywróci”,
- to jest teraz przede wszystkim problem architektoniczny i utrzymaniowy backendu.

### 3.3 Null payload

**Wynik: NISKIE RYZYKO PO STRONIE FRONTENDU**

Nie znaleziono dowodu, by backend systemowo zwracał `{ payload: null }` jako problematyczny wzorzec.

Dzięki wspólnemu parserowi i normalizacji po stronie frontendu, `null` / `undefined` nie jest już tak groźne jak w pierwotnej wersji audytu.

---

## 4. Backend – błędy

### 4.1 Typy błędów

**Wynik: POPRAWA / CZĘŚCIOWO PASS**

Backend ma już globalny exception handler w inicjalizacji aplikacji, z mapowaniem:
- `ValidationError` → 400,
- `ValueError` → 400 (tymczasowy fallback),
- `NotFoundError` → 404,
- `HTTPException` → zachowanie oryginalnego statusu HTTP,
- nieobsłużone błędy → 500 bez ujawniania surowego komunikatu wyjątku.

To istotnie poprawia spójność odpowiedzi błędów dla wyjątków nieprzechwyconych przez route. Nadal jednak pozostaje miks lokalnych `except Exception` i ręcznego zwracania legacy shape'ów, więc pełna standaryzacja backendu nie jest jeszcze zakończona.

### 4.2 error.details

**Wynik: FAIL jako standard backendowy**

Frontend potrafi już odczytywać `error.details`, ale backend nie gwarantuje jeszcze wszędzie:
- obecności `details`,
- słownikowego shape,
- jednolitego formatu.

### 4.3 logowanie błędów

**Wynik: CZĘŚCIOWO OK**

Globalne logowanie wyjątków istnieje, ale nadal część route’ów łapie `Exception` lokalnie i zwraca odpowiedź bez pełnego, centralnie ujednoliconego logowania i formatu błędu.

---

## 5. Backend ↔ Frontend compatibility

### 5.1 Compatibility layer

**Wynik: PASS po stronie frontendu**

Warstwa kompatybilności faktycznie istnieje i działa dla:
- `payload`,
- `data`,
- legacy raw JSON,
- legacy error string,
- nowszego `error.message` / `error.details`.

To jest jedna z najważniejszych pozytywnych zmian w repo.

### 5.2 Edge cases

**Wynik: PASS / częściowo do dalszego utwardzania**

Centralny parser obsługuje dziś:
- puste body,
- 204 / 205,
- nieprawidłowy JSON,
- nie-JSON z próbą rozsądnego fallbacku,
- błędy biznesowe w ciele odpowiedzi.

Pozostaje sensowne dalsze utwardzanie ekranów i DTO, ale najgroźniejszy brak centralnej obsługi edge case’ów został zamknięty.

---

## 6. Build / runtime

### 6.1 Build

**Wynik: PASS**

Potwierdzone komendą:
- `npm --prefix frontend run build`

Build przechodzi poprawnie. Jedyna uwaga to ostrzeżenie Vite o dużych chunkach, ale nie blokuje ono buildu.

### 6.2 Runtime

**Wynik: PASS dla smoke poziomu backend + NIEZWERYFIKOWANE pełne E2E UI**

Potwierdzone komendami:
- `npm --prefix frontend run check`,
- `python -m compileall backend`,
- `python backend/test_smoke_endpoints.py`.

Smoke test backendu pokrywa krytyczne endpointy:
- dashboard global summary,
- portfolio list/create/buy/sell/value,
- transfery budżet ↔ portfolio,
- harmonogram pożyczki,
- radar,
- symbol map.

Nie wykonywano pełnego manualnego E2E UI w przeglądarce w ramach tej aktualizacji audytu.

---

## 7. Lint / typowanie

### 7.1 TypeScript

**Wynik: POPRAWA, ALE NADAL JEST DŁUG TECHNICZNY**

Najważniejszy postęp:
- warstwa HTTP i parser odpowiedzi są już typowane,
- krytyczne moduły API normalizują `unknown` do przewidywalnych modeli,
- najbardziej wrażliwe ekrany nie działają już na surowym `response.json()`.

Nadal do poprawy:
- część ekranów nadal używa `any`,
- nie ma pełnej walidacji runtime DTO dla wszystkich endpointów.

### 7.2 unused vars / martwy kod

**Wynik: FAIL dla aktualnego lint frontendu**

Osobno uruchomiony `npm --prefix frontend run lint` nie przechodzi. Aktualnie potwierdzone problemy to m.in.:
- `@typescript-eslint/no-explicit-any` w kilku komponentach portfela, kredytów i modali,
- `@typescript-eslint/no-unused-vars` w części komponentów wykresów i stron,
- ostrzeżenia `react-hooks/exhaustive-deps` w dashboardzie budżetu i historii transakcji.

Wniosek praktyczny:
- minimalny quality gate (`check`, `build`, `compileall`, `smoke`) jest zielony,
- pełniejszy gate jakościowy z lintem nadal wymaga domknięcia.

Po stronie architektury pozytywna zmiana jest jednak istotna:
- wcześniejszy chaos wielu konkurencyjnych mini-warstw HTTP został w dużej mierze zastąpiony jednym klientem i wspólnymi modułami API.

---

## 8. Testy – szybki check

### 8.1 API

**Wynik: PASS dla smoke testów krytycznych endpointów**

Potwierdzony automatem smoke test backendu obejmuje najważniejsze flowy integracyjne.

To oznacza, że wcześniejszy status „niezweryfikowane automatem” jest już nieaktualny.

### 8.2 UI

**Wynik: MIXED — PASS dla check/build, FAIL dla lint, E2E manual nadal niepełne**

Potwierdzone:
- aplikacja przechodzi TypeScript check,
- aplikacja buduje się poprawnie.

Nie przechodzi:
- lint frontendu (`npm --prefix frontend run lint`).

Nadal niepotwierdzone w tej aktualizacji:
- pełny manualny smoke test wszystkich ekranów w przeglądarce.

---

## 9. Najważniejsze red flagi

### Nadal potwierdzone red flagi

- **backend nie ma jeszcze jednego, globalnie egzekwowanego kontraktu success/error**,
- **backend nie ma jeszcze pełnej standaryzacji `error.details`**,
- **część odpowiedzi nadal jest legacy i endpoint-specific**,
- **część UI nadal ma dług typowania (`any`, lokalne założenia DTO)**,
- **lint frontendu jest obecnie czerwony i potwierdza zaległości w `any`, unused vars i hook dependencies**,
- **brak pełnego manualnego E2E UI po całej aplikacji**,
- **build ostrzega o dużych chunkach frontendu**.

### Red flagi zamknięte od czasu poprzedniej wersji audytu

- brak wspólnej warstwy HTTP,
- brak `extractPayload`,
- brak `extractErrorMessage`,
- brak `parseJsonApiResponse`,
- brak compatibility layer dla `payload / data / raw JSON`,
- brak smoke testów krytycznych endpointów,
- inline dashboard request bez normalizacji odpowiedzi.

---

## Priorytet poprawek

### P1 – domknięcie standardu backendowego
1. Ustalić jeden backendowy kontrakt success/error dla wszystkich endpointów.
2. Wprowadzić spójny `error.details` jako obiekt.
3. Ograniczyć lokalne `except Exception` i przenieść mapowanie błędów do warstwy centralnej.

### P2 – dalsze utwardzenie frontendu
1. Ograniczyć `any` w krytycznych ekranach.
2. Kontynuować normalizację DTO na granicy API.
3. Dodać więcej testów regresji dla flowów biznesowych wysokiego ryzyka.

### P3 – jakość wykonawcza i wydajność
1. Dodać pełniejszy lint/quality gate.
2. Przeprowadzić manualny E2E smoke test kluczowych ekranów UI.
3. Ograniczyć zbyt duże chunki frontendu.

---

## Finalna ocena

**Wniosek:** projekt jest dziś **istotnie bardziej dojrzały integracyjnie** niż wskazywała wcześniejsza wersja audytu. Frontend ma już wspólną warstwę HTTP, centralne parsowanie success/error i compatibility layer, a build oraz smoke test backendu przechodzą poprawnie. Główne otwarte ryzyko przesunęło się z „frontend może się masowo wywracać po zmianie kontraktu” na **„backend nadal nie ma jednego, globalnie wymuszonego standardu odpowiedzi i błędów”**.
