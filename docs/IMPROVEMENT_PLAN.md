# Audyt aplikacji i plan usprawnień

Data przeglądu: 2026-09-06

## Zakres i stan jakości

Przegląd objął pełny zestaw testów backendu i frontendu, TypeScript, ESLint,
produkcję paczki Vite oraz kompilację modułów Pythona. Quality gate został
rozszerzony tak, aby lokalnie i w CI uruchamiał wszystkie te kontrole, zamiast
jedynie pojedynczego smoke testu backendu.

### Wynik powtórnego audytu

| Obszar | Wynik | Wnioski |
| --- | --- | --- |
| TypeScript | zaliczony | `tsc -b --noEmit` bez błędów |
| ESLint | zaliczony | brak naruszeń reguł |
| Frontend | 103 zaliczone, 2 pominięte | 20 zestawów testowych; pominięte scenariusze trzeba przenieść do E2E |
| Build Vite | zaliczony z ostrzeżeniem | główny chunk ma 591,37 kB (183,43 kB gzip) |
| Backend | 178 zaliczonych + 99 subtestów | 2 ostrzeżenia zależności, brak błędów |
| Bezpieczeństwo npm | zaliczone | aktualizacja zależności usunęła 19 zgłoszonych podatności (`npm audit`: 0) |

Test backendu został wykonany na wspieranym Pythonie 3.11. Próba instalacji na
Pythonie 3.14 ujawniła, że przypięty `pandas==2.2.0` nie ma zgodnego koła i próbuje
budować się ze źródeł. Quality gate sprawdza teraz wersję interpretera przed
uruchomieniem długich kontroli i pozwala wskazać go przez `PYTHON_BIN`.

W trakcie audytu wykryto i poprawiono:

- brak nowego endpointu dywidend w teście kompletności kontraktu API,
- mocki testów historii nieuwzględniające warstwy cache,
- brak odporności odczytu historii na uszkodzony wpis cache,
- nieaktualne selektory testów po rozbudowaniu responsywnego widoku pozycji,
- martwe akcje diagnostyczne portfela oraz błędy lintowania,
- brak testów backendu i lintowania w CI.

## Priorytety usprawnień

### P0 — bezpieczeństwo i integralność danych

1. **Uwierzytelnianie i role.** Zastąpić token administratora przechowywany w
   `localStorage` sesją po stronie serwera, dodać role użytkownik/admin i ochronę
   CSRF dla operacji modyfikujących.
2. **Migracje bazy danych.** Zastąpić ewolucję schematu wykonywaną podczas startu
   wersjonowanymi migracjami oraz automatycznie testować migrację kopii bazy i
   możliwość rollbacku.
3. **Kopie zapasowe.** Usunąć binarne backupy z repozytorium, szyfrować backupy
   operacyjne i wdrożyć cykliczny test odtworzenia danych.
4. **Precyzja finansowa.** Stopniowo zastąpić `float` typem dziesiętnym lub
   wartościami w najmniejszych jednostkach waluty; objąć testami zaokrąglenia,
   prowizje, podatki i kursy walut.
5. **Automatyczny audyt zależności.** Dodać `npm audit --omit=dev` oraz skaner
   zależności Pythona do CI i Dependabot/Renovate. Blokować wydanie dla nowych
   podatności high/critical, ale aktualizacje major sprawdzać osobnym PR-em.

### P1 — niezawodność i obserwowalność

1. **Kontrolowane zależności zewnętrzne.** Dodać timeout, retry z backoffem,
   circuit breaker i jawne oznaczenie wieku danych z yfinance oraz usług AI.
2. **Monitoring.** Wprowadzić identyfikator żądania, logi strukturalne, metryki
   czasu odpowiedzi i błędów oraz alerty dla nieudanych importów i wycen.
3. **Cache.** Wersjonować klucze, mierzyć hit-rate oraz automatycznie usuwać
   uszkodzone i przeterminowane wpisy zamiast pozostawiać je w bazie.
4. **Testy E2E.** Dodać Playwright dla krytycznych ścieżek: import CSV,
   kupno/sprzedaż, transfer, zamknięcie miesiąca i nadpłata kredytu.

### P2 — wydajność i utrzymanie

1. **Podział paczki frontendu.** Wyodrębnić biblioteki wykresów do osobnych
   chunków i ładować ciężkie widoki na żądanie; obecny build sygnalizuje chunk
   przekraczający 500 kB.
2. **Warstwa repozytoriów.** Oddzielić SQL od logiki domenowej i ujednolicić
   transakcje bazodanowe, co uprości testy oraz przyszłą migrację z SQLite.
3. **Kontrakt API.** Generować typy TypeScript z `docs/openapi.yaml` i walidować
   zgodność specyfikacji z zarejestrowanymi trasami w CI.
4. **Aktualizacja AI SDK.** Zaplanować przejście z wycofanego pakietu
   `google.generativeai` na wspierany SDK i dodać testy błędów/limitów dostawcy.
5. **Macierz wspieranych środowisk.** Testować backend na Pythonie 3.11 i 3.12,
   a frontend na aktywnym Node LTS. Rozszerzenie do Pythona 3.13+ poprzedzić
   aktualizacją pandas i testem importu CSV na danych referencyjnych.

## Konkretne następne iteracje

### Iteracja A — bezpieczne wdrożenie (1–2 tygodnie)

- sesja serwerowa, role i CSRF wraz z testami operacji zapisu,
- migracje schematu i automatyczny test backup → migracja → restore,
- skan zależności w CI oraz aktualizacja `google.generativeai`,
- kryterium ukończenia: brak sekretów w przeglądarce, odtworzenie testowej bazy i
  zero podatności high/critical w zależnościach produkcyjnych.

### Iteracja B — niezawodność danych (1–2 tygodnie)

- `Decimal` na granicach wejścia/wyjścia i jawna polityka zaokrągleń,
- timeout/retry/circuit breaker dla notowań oraz znacznik „dane z godziny…”,
- request ID, log JSON i metryki błędów/importów,
- kryterium ukończenia: deterministyczne testy groszowe i brak wiszących requestów
  do dostawcy w scenariuszach awarii.

### Iteracja C — ścieżki użytkownika i wydajność (1 tydzień)

- Playwright dla pięciu krytycznych przepływów wskazanych w P1,
- lazy loading bibliotek wykresów i budżet maks. 250 kB gzip dla entry chunku,
- usunięcie lub pokrycie dwóch pominiętych testów integracyjnych,
- kryterium ukończenia: E2E działa na czystej bazie, a build nie generuje
  ostrzeżenia o chunku większym niż 500 kB.

## Możliwe dalsze funkcje

### Największa wartość dla użytkownika

- cele finansowe z prognozą daty realizacji i scenariuszami wpłat,
- automatyczny rebalancing z tolerancją odchylenia i listą proponowanych zleceń,
- kalendarz dywidend, kuponów obligacji, rat i cyklicznych wydatków z alertami,
- pełna analiza podatkowa (FIFO, podatek Belki, IKE/IKZE, eksport pomocniczy PIT),
- benchmarki portfela i porównanie TWR/XIRR po opłatach oraz inflacji,
- reguły kategoryzacji transakcji i import z kolejnych banków/brokerów.

### Funkcje zaawansowane

- scenariusze „co jeśli” dla stóp procentowych, inflacji, FX i obsunięcia rynku,
- analiza ryzyka: zmienność, drawdown, VaR/CVaR i koncentracja sektorowa/walutowa,
- gospodarstwo domowe z wieloma użytkownikami, uprawnieniami i audytem zmian,
- powiadomienia e-mail/push o limitach budżetu, cenach, terminach i anomaliach,
- eksport/import całego konta oraz raporty PDF/CSV,
- tryb prywatności i lokalne szyfrowanie wrażliwych danych.

## Proponowana kolejność realizacji

1. Zamknąć P0: auth, migracje, backup/restore i precyzja kwot.
2. Dodać obserwowalność oraz E2E dla pięciu najważniejszych przepływów.
3. Uporządkować API/SQL i budżet wydajności frontendu.
4. Dostarczyć cele, kalendarz i rebalancing jako pierwszy pakiet produktowy.
5. Dopiero potem rozszerzać analitykę ryzyka, podatki i integracje automatyczne.

Każdą większą funkcję należy wdrażać z flagą funkcjonalną, migracją danych,
metryką sukcesu i scenariuszem wycofania.
