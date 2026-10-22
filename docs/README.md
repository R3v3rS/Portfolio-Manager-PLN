# Dokumentacja Portfolio Manager (PLN)

Stan opisanej funkcjonalności: 22 października 2026. Opisy dotyczą aktualnego interfejsu i kodu w tej wersji. Kwoty i nazwy kont w przykładach są fikcyjne.

## Od czego zacząć

| Potrzeba | Dokument |
|---|---|
| Chcę szybko zapisać zakup, rachunek, odłożenie lub zamknąć miesiąc | [Budżet na co dzień](BUDZET_NA_CO_DZIEN_PL.md) |
| Chcę nauczyć się obsługi całej aplikacji | [Instrukcja obsługi](INSTRUKCJA_OBSLUGI_PL.md) |
| Chcę ustawić i prowadzić budżet domowy | [Dokładna instrukcja budżetu](BUDZET_INSTRUKCJA_PL.md) |
| Chcę uruchomić, zaktualizować lub odzyskać aplikację | [Uruchamianie i kopie danych](URUCHAMIANIE_I_KOPIE_PL.md) |
| Chcę zrozumieć obliczenia, model danych i API | [Architektura i zasady obliczeń](ARCHITEKTURA_I_MODEL_DANYCH_PL.md) |
| Chcę zobaczyć zmiany tej wersji | [Najnowsza wersja](LATEST_VERSION.md) |
| Chcę analizować inwestycje, planować udziały i sprawdzać materiały | [Asystent, plan udziałów, ETF i materiały](AI_PORTFOLIO_ANALYSIS_MODULE_PL.md) |

Najkrótsza kolejność wdrożenia: uruchom aplikację, wprowadź salda kont, dodaj dochody i zobowiązania, ustaw limity oraz rezerwy, następnie sprawdź prognozę. Nie zaczynaj od kopiowania wszystkich dawnych płatności, jeśli podałeś już aktualne salda — najpierw wybierz właściwy sposób wpływu importu na saldo.

## Ważne rozróżnienia

- Aplikacja zapisuje ewidencję i wykonuje obliczenia. Przycisk zapisania płatności nie zleca przelewu w banku.
- Saldo konta, limit kategorii i odłożenie na rezerwę to różne informacje. Ich dokładne znaczenie opisuje instrukcja budżetu.
- Prognoza używa zapisanych dochodów, zobowiązań i założeń wydatków. Nie pobiera automatycznie rzeczywistego salda bankowego.
- Baza i zdjęcia paragonów są przechowywane lokalnie. Wybranie analizy AI wysyła wskazane dane do Google Gemini; podgląd i zasady opisuje [instrukcja analiz](AI_PORTFOLIO_ANALYSIS_MODULE_PL.md). Repozytorium zawiera kod i instrukcje z fikcyjnymi przykładami.

## Dokumentacja uzupełniająca

[PROJECT_GUIDE_PL.md](PROJECT_GUIDE_PL.md) opisuje szczegóły własności i księgowania portfeli. [ANALYTICS_SUMMARY_API_PL.md](ANALYTICS_SUMMARY_API_PL.md) opisuje podsumowania analiz. [TEST_CATALOG_PL.md](TEST_CATALOG_PL.md) jest katalogiem wybranych testów, a nie instrukcją użytkownika.

Starsze audyty i notatki wdrożeniowe są w [archiwum dokumentacji](archive/README.md). Mogą opisywać wcześniejsze ekrany, wykryte już poprawione błędy lub historyczne założenia. Punktem wejścia do obecnej obsługi są dokumenty z tabeli powyżej. [Zakres dokumentacji API](API_ZAKRES_PL.md) wyjaśnia częściowy opis OpenAPI, referencje domenowe i rolę testu kontraktu koperty.
