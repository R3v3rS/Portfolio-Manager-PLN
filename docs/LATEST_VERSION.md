# Najnowsza wersja aplikacji

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
