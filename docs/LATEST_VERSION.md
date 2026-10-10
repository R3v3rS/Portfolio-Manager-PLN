# Najnowsza wersja aplikacji

## Główne zmiany

- Spójny interfejs Centrum finansów, inwestycji, kredytów i budżetu.
- Konta budżetowe, salda początkowe, przelewy, hierarchia kategorii, rachunki jednorazowe i cykliczne.
- Plan miesiąca, prognoza pieniędzy, rezerwy terminowe i bezterminowe oraz miesięczne rozliczenie.
- Import bankowych CSV, reguły kategorii, paragony z odczytem i przeglądem przed zapisem, powiązania z istniejącymi płatnościami.
- Cele inwestycyjne, dziennik inwestora, raport miesięczny i widok pomysłów inwestycyjnych.
- Analiza rzeczywistych wyników, osobne modele obligacji i PPK oraz oznaczanie niepełnych wycen.
- Ręczne ceny instrumentów bez notowań, przenoszenie akcji pomiędzy strategiami i archiwizacja z zachowaniem historii.
- Lokalny start i bezpieczne zatrzymanie backendu oraz frontendu.

## Dane lokalne

Baza SQLite, kopie bezpieczeństwa, przesłane paragony, prywatne raporty i zrzuty ekranów nie są publikowane. Zachowaj swoją bazę przed aktualizacją i migracją schematu. Lokalny serwer uruchamia się przez `backend/run_local.py`; frontend przez standardowy skrypt `dev`.

## Znane ograniczenia analiz

Wkład instrumentów i miesięczne stopy uwzględniają przeniesienia akcji. Wskaźniki ryzyka nadal opisują obecny koszyk części akcyjnej, bez gotówki i historycznych zmian składu. Łączona miesięczna stopa Modified Dietz jest przybliżeniem, nie dokładną dzienną stopą TWR.
