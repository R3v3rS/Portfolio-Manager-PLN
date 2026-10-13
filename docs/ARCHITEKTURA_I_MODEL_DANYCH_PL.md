# Architektura i zasady obliczeń

Stan funkcjonalności: 13 października 2026. Ten dokument opisuje implementację; praktyczne kroki znajdują się w [instrukcji budżetu](BUDZET_INSTRUKCJA_PL.md) i [instrukcji całej aplikacji](INSTRUKCJA_OBSLUGI_PL.md).

## 1. Warstwy

Frontend React/TypeScript/Vite definiuje trasy w `frontend/src/App.tsx`. Widoki używają modułów `api*.ts`, które korzystają ze wspólnego klienta `http.ts` i konfiguracji `apiConfig.ts`. Backend Flask rejestruje blueprinty w `backend/app.py`. Serwisy domenowe obsługują walidację, księgowanie i obliczenia przez połączenie SQLite z `database.py`.

Standardowe odpowiedzi API mają kopertę `payload` albo `error`. Komunikaty konfliktu chronią m.in. przed zapisem na nieaktualnej wersji obiektu. Sam błąd połączenia nie dowodzi, że poprzedni zapis nie dotarł do serwera; identyfikatory żądania zabezpieczają obsługiwane operacje przed ponowieniem.

Kwoty operacji budżetowych są przechowywane jako całkowite grosze. Salda `budget_accounts.balance` oraz część starszych/inwestycyjnych pól korzystają z liczb zmiennoprzecinkowych i zaokrąglania. Nie należy zakładać, że każda kwota w całej bazie ma identyczny typ i semantykę.

## 2. Główne tabele budżetu

| Tabela | Odpowiedzialność |
|---|---|
| `budget_accounts` | Konta, waluta i aktualne saldo |
| `budget_account_reconciliations` | Dane otwarcia i potwierdzenia/korekty salda |
| `budget_entries_v2` | Nagłówki wpływów i wydatków, data, konto i wpływ na saldo |
| `budget_entry_lines_v2` | Podział wydatku na kategorie i pozycje |
| `budget_categories_v2` | Kategorie, rodzic, wersja i ustawienie tempa |
| `budget_plans_v2` | Własny limit kategorii w konkretnym miesiącu, także 0 |
| `budget_default_plans` | Wersje domyślnych limitów od wskazanego miesiąca |
| `budget_plan_copy_requests` | Wyniki zatwierdzonych żądań kopiowania zakresu |
| `budget_bills_v2` | Definicje rachunków i harmonogramów |
| `budget_bill_payments_v2` | Rozliczenia wystąpienia rachunku z istniejącym wydatkiem |
| `budget_expected_incomes` / `budget_expected_income_receipts` | Plan wpływu i jego otrzymanie/powiązanie |
| `budget_reserves` / `budget_reserve_movements` | Rezerwy i ruchy odłożenia, zwolnienia oraz płatności |
| `budget_reserve_month_plans` / `budget_reserve_plan_history` | Wyjątki i historyczne podstawy planu odłożeń |
| `budget_account_transfers` | Przelewy własne, przeniesienie miejsca rezerwy lub jej zasilenie |
| `budget_investment_transfers` | Powiązane przepływy między budżetem a inwestycjami |
| `budget_purchase_refunds` | Powiązanie zwrotu z pierwotnym zakupem |
| `budget_settlements` / `budget_settlement_reversals` | Podstawa cofnięcia rozliczenia |
| `budget_category_policies` | Zasada niewykorzystanego limitu |
| `budget_month_closings` / `budget_month_closing_items` | Zatwierdzone zamknięcia i konkretne decyzje |
| `budget_month_snapshots` | Podstawa zamknięcia i porównanie późniejszych zmian |
| `loan_budget_settings` / `loan_installment_payments` | Konto i kategoria kredytu oraz potwierdzone spłaty |

Tabele dawnych kopert nadal istnieją dla starszej kompatybilności. Obecny główny interfejs budżetu korzysta z modelu workspace `v2`; nie należy mieszać zapisów starego modelu kopert z nową historią bez jawnej migracji.

## 3. Zasady salda i wydatków

Wpis nowego wpływu zwiększa saldo, a wydatku je zmniejsza. `cash_effect=0` oznacza historię już uwzględnioną w saldzie: wpis nadal uczestniczy w miesięcznych wydatkach. Zastosowanie wpływu takiego wpisu na saldo jest osobną chronioną operacją.

Przelew własny zmienia dwa salda, bez tworzenia dochodu konsumpcyjnego i wydatku. Odłożenie na rezerwę zmienia przeznaczenie kwoty, nie saldo fizyczne. Zwrot jest powiązany z zakupem i odejmowany od wydatków, mimo że techniczny zapis wpływu środków zwiększa konto.

Powiązanie rachunku, raty lub rezerwy z istniejącym wydatkiem zachowuje jedną operację gotówkową. Dane rozliczenia pamiętają, czy wydatek utworzono w trakcie rozliczenia, czy tylko dołączono istniejący. Cofnięcie odtwarza właściwy poprzedni stan, zamiast bezwarunkowo usuwać cudzy wpis.

## 4. Limity i domyślny plan

`budget_default_plan_service.resolve` wybiera najnowszy domyślny wpis kategorii z `start_month <= miesiąc`, następnie zastępuje go własnym wpisem miesiąca. O wyborze decyduje obecność rekordu, nie prawdziwość kwoty: zero nie jest traktowane jak brak danych.

`budget_category_hierarchy_service.plan_amounts` liczy dziecko jako maksimum jego własnego limitu i przypisanych zobowiązań. Rodzic jest maksimum własnego wspólnego limitu oraz jego zobowiązań ogólnych z sumą planów dzieci. Sumy globalne obejmują rodziców, bez ponownego dodawania dzieci. Część pokryta odłożoną rezerwą jest odłączana od zapotrzebowania na nowe wolne środki.

Miesięczne pule mediów są źródłem własnego planu dedykowanych kategorii i wyłączają konkurencyjny dawny ręczny limit. Zwykłe rezerwy i brakujące odłożenia są rozliczane dodatkowo tylko w części, która nie jest już tym samym finansowaniem rachunku.

`budget_plan_read_service` dostarcza rozbicie dla interfejsu: zwykły plan/wydatki, część płatności, brakujące płatności i media. Nie księguje finansowych operacji podczas odczytu.

Zapis domyślnego planu jest atomowy, porównuje rewizję historii każdej wybranej kategorii i nie zmienia miesięcy przed wskazanym startem. Nie pozwala rozpocząć przed bieżącym ani ostatnim zamkniętym miesiącem. Wcześniejsze domyślne wersje oraz później zaplanowane zmiany pozostają zachowane.

Kopiowanie zakresu najpierw wylicza podgląd i jego sygnaturę. Przy zatwierdzeniu serwer ponownie sprawdza podgląd w transakcji. Nieaktualna sygnatura blokuje zapis. Domyślnie istniejące rekordy miesięczne są zachowywane, a ponowienie tego samego żądania zwraca zapamiętany wynik. Kopiowany jest własny limit, bez nadwyżek zamknięcia i bez płatności.

## 5. Główne podsumowania budżetu

Implementacja w `budget_summary_service.py` rozdziela:

```text
wydatki po zwrotach = zakupy i płatności − powiązane zwroty
obciążenie budżetu = wydatki po zwrotach + korekty przeznaczenia rezerw
dostępne teraz = aktualne saldo − aktualnie wydzielone rezerwy
do zaplanowania = saldo dla końca wybranego okresu + oczekiwane wpływy
                 − pozostały plan i zobowiązania − rezerwy − dodatkowe odłożenia
wolne z przychodów = otrzymane i oczekiwane dochody miesiąca
                    − finansowane koszty miesiąca − pozostały plan miesiąca
```

Saldo okresu jest odtwarzane z bieżącego salda przez odjęcie późniejszych zapisanych efektów gotówkowych. „Do zaplanowania” nie jest samym bankowym saldem na koniec miesiąca. Przy wyliczeniu pozostałego planu każda główna kategoria zachowuje co najmniej potrzebne nieopłacone zobowiązania; przekroczenie jednej kategorii nie zwraca pozornie pieniędzy na inną.

Finansowane koszty dochodów miesiąca obejmują zwykłe wydatki po zwrotach, nowe przeznaczenie na rezerwy oraz wyjścia do inwestycji, z korektą rozliczenia wykorzystanych rezerw. Różne miary nie powinny być porównywane bez ich zakresu.

## 6. Prognoza i tempo

`cash_forecast_service` symuluje 365 dni od aktualnego dnia. Generuje oczekiwane wpływy, rachunki, raty, płatności i odłożenia rezerw oraz cele. Saldo i rezerwy są prowadzone osobno, również per konto. Symulacja jest odczytem i nie zleca operacji.

Zwykłe limity otrzymują per kategorię pierwszeństwo miesięczny/domyślny. Dla braków tylko prognoza może przyjąć bieżący zapis jako `ESTIMATE`. Taki szacunek nie tworzy miesięcznego rekordu. Szacunkowy limit dziecka nie podwyższa rzeczywiście zapisanego wspólnego limitu rodzica.

Codzienna część limitu jest wyznaczana po odjęciu przypisanych stałych płatności i mediów. Bieżące zwykłe zakupy i ich zwroty redukują pozostałe wydatki w swoich grupach. Własny scenariusz `variable_monthly` zastępuje codzienną część planu, bez zmiany zapisanych limitów. `month_plans` opisuje źródła i przepływy w zakresie prognozy, nie potwierdzone przyszłe wydatki.

Ustawienia wyłączenia kategorii z tempa wpływają na `budget_chart_service` oraz model wykresu i wskaźnik dni. Nie wyłączają kategorii z salda, pełnego planu ani prognozy. Powiązane płatności stałe, raty i rezerwy nie są zwykłym tempem zakupów.

## 7. Zamknięcia i kredyty

Zamknięcie pamięta wynik decyzji kategorii, również automatycznej. `budget_rollover_service` daje zatwierdzonej decyzji pierwszeństwo przed późniejszą zmianą polityki. Późniejsze korekty są porównywane ze snapshotem, bez ponownego rozdysponowania tej samej kwoty.

`loan_budget_service` przechowuje konto i kategorię każdego kredytu. Domyślne konto ogólne jest fallbackiem. Dopasowanie raty szuka niezajętego wydatku tego samego konta i kwoty w pobliżu daty płatności. Połączenie z ratą oraz cofnięcie zachowują podstawę wcześniejszej klasyfikacji.

## 8. Najważniejsze grupy API

| Grupa | Zastosowanie |
|---|---|
| `/api/budget/workspace` | Miesięczny widok, konta, kategorie, wpisy i rachunki |
| `/api/budget/workspace/plans/defaults` | Odczyt i atomowy zapis domyślnych limitów |
| `/api/budget/workspace/plans/copy-preview` / `copy-range` | Podgląd i zatwierdzenie kopiowania |
| `/api/budget/workspace/plans/<id>` | Miesięczny limit i powrót z wyjątku |
| `/api/budget/planning` | Ustawienia, rezerwy miesięczne, polityki i zamknięcia |
| `/api/budget/forecast` | Prognoza i oczekiwane dochody |
| `/api/budget/accounts`, `/api/budget/reserves`, `/api/budget/imports` | Wyspecjalizowane operacje budżetu |
| `/api/loans` | Kredyty, harmonogramy, spłaty i nadpłaty |
| `/api/portfolio` i pozostałe blueprinty inwestycyjne | Portfele, transakcje, wycena i analizy |

Pełne kształty żądań są w odpowiednich `frontend/src/api*.ts` i trasach backendu. Test `test_api_contract.py` wymaga sprawdzenia każdego zarejestrowanego endpointu. Nie traktuj tej tabeli jako kompletnej specyfikacji wszystkich parametrów.

## 9. Inwestycje, wycena i historia

Portfel główny jest właścicielem drzewa; zakres własny i strategie są rozróżniane przez `sub_portfolio_id`. Agregacja aktywnych zakresów i stan archiwalny służą innym celom. Transfer aktywów nie jest sprzedażą w całym portfelu, lecz przepływem kapitału zakresu strategii.

Rynek i FX mają daty oraz jakość danych. Cena ręczna lub cena zakupu do orientacji musi pozostać odróżniona od aktualnego notowania. Braki wyceny nie są bezwarunkowo uzupełniane kursem 1 ani zerowym zyskiem.

PPK, obligacje i oszczędności używają modeli właściwych rodzajowi konta. Wartość aktywów oraz wartość do wypłaty są osobnymi polami. Ryzyko akcyjnego koszyka i rzeczywista stopa zwrotu inwestora z przepływami nie mierzą tego samego.

Dokładniejszą własność i księgowanie opisuje [PROJECT_GUIDE_PL.md](PROJECT_GUIDE_PL.md). Część historycznych analiz jest przybliżeniem i może być niedostępna dla brakujących wycen lub krótkich szeregów.

## 10. Utrzymanie i ograniczenia

Schemat jest inicjalizowany addytywnie przy starcie backendu. Kopia SQLite powstaje przed zmianą wersji i według zasad retencji; zdjęcia są osobnymi plikami. Przy odtworzeniu dawnej bazy uruchom inicjalizację aktualnego kodu.

Paragony są odczytywane lokalnym Windows OCR. Dane rynkowe i publiczne publikacje korzystają z usług zewnętrznych; dostępność i aktualność mogą się zmieniać. Ewentualne moduły AI mają odrębną konfigurację i nie stanowią mechanizmu rozpoznawania wszystkich paragonów.

Ta konfiguracja uruchomienia jest przeznaczona do pracy lokalnej. Nie stanowi gotowego systemu wieloużytkownikowego z izolacją kont, kontrolą dostępu i publicznym wdrożeniem. Backupy, klucze, baza, załączniki, logi i prywatne zrzuty nie należą do publikowanego kodu.

Zmiana wspólnych obliczeń wymaga testów modeli: podkategorii, zwrotów, rachunków, rat, rezerw, zamknięć i prognozy. Testy interfejsu sprawdzają m.in. rozdzielenie podglądu i zapisu oraz skutki powiązań. Daty testowe powinny być stałe albo tak dobrane, aby punkty historii nie stawały się przypadkiem przyszłe.
