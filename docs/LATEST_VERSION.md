# Najnowsza wersja aplikacji

Stan: 14 października 2026.

## Zmiany z 14 października

- Zakres prognozy 30 dni, 3 lub 12 miesięcy wybierany bezpośrednio przy wykresie. Zakres dat, konto, scenariusz, tabela i kalendarz pozostają zsynchronizowane.
- Opisy i przykłady kategorii, widoczne w ustawieniach, planie i przy wyborze kategorii wydatku.
- Nieużywane kategorie domyślnie ukryte w planie i ustawieniach; można je pokazać przełącznikiem lub wyszukiwarką. Historia i kategorie dostępne przy dodawaniu wydatków są zachowane.
- Czytelne odróżnienie wspólnego limitu od kwot przeznaczonych na rachunki; jawnie zapisany limit 0 zł nie jest przedstawiany jako brak planu.
- Nadpłatę kredytu można powiązać z istniejącym wydatkiem, bez drugiego obciążenia konta. Cofnięcie powiązania przywraca poprzednią kategorię i zachowuje płatność.
- Domyślna kategoria rachunków i rat rozpoznawana także po zmianie jej nazwy.
- Starsze audyty przeniesione do [archiwum](archive/README.md), usunięte nieużywane skrypty diagnostyczne, robocze prompty i grafika startowa Reacta.
- Pomocnicze scenariusze testowe przeniesione z lokalnych skryptów audytu do `backend/tests/`. Testy nie wymagają już prywatnych plików, a konfiguracja pytest ustawia ścieżki importu dla uruchomienia z repozytorium.
- Logi, próbne bazy, pliki testowe i stare obrazy diagnostyczne uporządkowane lokalnie. Kopie bazy o nazwach `*.db.*` wyłączone z aktualnej publikowanej wersji i z przyszłych commitów; istniejące lokalne kopie pozostają zachowane. Starsza historia Git nadal zawiera wcześniej opublikowane pliki.

## Główne zmiany

- Szczegółowe instrukcje całej aplikacji, budżetu, uruchamiania i kopii oraz dokumentacja modelu danych: [spis dokumentacji](README.md).
- Wspólna nawigacja budżetu z zachowaniem miesiąca, osobne ustawienia, filtry transakcji i podział historii na dni.
- Plan kategorii rozdzielający wspólny limit, rachunki/raty i zwykłe wydatki; płatności widoczne także pod kategoriami.
- Domyślny plan miesięczny od wybranej daty, miesięczne wyjątki z pierwszeństwem dla 0 zł i powrót do domyślnego limitu.
- Kopiowanie limitów na 3, 6 lub 12 miesięcy z podglądem, zachowaniem istniejących wyjątków i kontrolą nieaktualnych danych.
- Miesięczne założenia prognozy z oznaczeniami limitów miesięcznych, domyślnych i szacunkowych; szacunek podkategorii nie podwyższa zapisanego wspólnego limitu.
- Konto i kategoria rat zapamiętywane per kredyt, powiązanie istniejącej płatności oraz bezpieczne cofnięcie rozliczenia.
- Zatwierdzone decyzje zamknięcia zachowane niezależnie od późniejszej zmiany polityki kategorii.
- Wyłączenie wybranych kategorii z tempa bez usuwania ich z pełnego planu oraz zakresy wykresu majątku.

- Spójny interfejs Centrum finansów, inwestycji, kredytów i budżetu.
- Konta budżetowe, salda początkowe, przelewy, hierarchia kategorii, rachunki jednorazowe i cykliczne.
- Plan miesiąca, prognoza pieniędzy, rezerwy terminowe i bezterminowe oraz miesięczne rozliczenie.
- Tempo codziennych wydatków wyrażone w dniach względem planu, bez wcześniejszych płatności stałych zobowiązań.
- Decyzja o niewykorzystanym limicie przy zamknięciu miesiąca: następny miesiąc, oszczędności, przyszłe inwestycje, wybrana rezerwa lub pozostawienie wolnych środków. Odłożenia nie tworzą fikcyjnych przelewów ani zakupów inwestycji.
- Import bankowych CSV, reguły kategorii, paragony z odczytem i przeglądem przed zapisem, powiązania z istniejącymi płatnościami.
- Cele inwestycyjne, dziennik inwestora, raport miesięczny i widok pomysłów inwestycyjnych.
- Analiza rzeczywistych wyników, osobne modele obligacji i PPK oraz oznaczanie niepełnych wycen.
- Ręczne ceny instrumentów bez notowań, przenoszenie akcji pomiędzy strategiami i archiwizacja z zachowaniem historii.
- Lokalny start i bezpieczne zatrzymanie backendu oraz frontendu.

## Dane lokalne

Baza SQLite, kopie bezpieczeństwa, przesłane paragony, prywatne raporty i zrzuty ekranów nie są publikowane. Zachowaj swoją bazę przed aktualizacją i migracją schematu. Lokalny serwer uruchamia się przez `backend/run_local.py`; frontend przez standardowy skrypt `dev`.

## Znane ograniczenia analiz

Wkład instrumentów i miesięczne stopy uwzględniają przeniesienia akcji. Wskaźniki ryzyka nadal opisują obecny koszyk części akcyjnej, bez gotówki i historycznych zmian składu. Łączona miesięczna stopa Modified Dietz jest przybliżeniem, nie dokładną dzienną stopą TWR.
