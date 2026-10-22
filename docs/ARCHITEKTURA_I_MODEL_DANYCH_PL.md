# Architektura i zasady obliczeń

Stan funkcjonalności: 22 października 2026. Ten dokument opisuje implementację; praktyczne kroki znajdują się w [instrukcji budżetu](BUDZET_INSTRUKCJA_PL.md) i [instrukcji całej aplikacji](INSTRUKCJA_OBSLUGI_PL.md).

## 1. Warstwy

Frontend React/TypeScript/Vite definiuje trasy w `frontend/src/App.tsx`. Widoki używają modułów `api*.ts`, które korzystają ze wspólnego klienta `http.ts` i konfiguracji `apiConfig.ts`. Backend Flask rejestruje blueprinty w `backend/app.py`. Serwisy domenowe obsługują walidację, księgowanie i obliczenia przez połączenie SQLite z `database.py`.

Standardowe odpowiedzi API mają kopertę `payload` albo `error`. Komunikaty konfliktu chronią m.in. przed zapisem na nieaktualnej wersji obiektu. Sam błąd połączenia nie dowodzi, że poprzedni zapis nie dotarł do serwera; identyfikatory żądania zabezpieczają obsługiwane operacje przed ponowieniem.

Kwoty operacji budżetowych są przechowywane jako całkowite grosze. Salda `budget_accounts.balance` oraz część starszych/inwestycyjnych pól korzystają z liczb zmiennoprzecinkowych i zaokrąglania. Nie należy zakładać, że każda kwota w całej bazie ma identyczny typ i semantykę.

## 2. Główne tabele budżetu

| Tabela | Odpowiedzialność |
|---|---|
| `budget_accounts` | Konta, waluta, aktualne saldo i `account_type`: `BANK` lub `CREDIT_CARD` |
| `budget_account_reconciliations` | Dane otwarcia i potwierdzenia/korekty salda |
| `budget_entries_v2` | Nagłówki wpływów i wydatków, data, konto i wpływ na saldo |
| `budget_entry_lines_v2` | Podział wydatku na kategorie i pozycje |
| `budget_categories_v2` | Kategorie, rodzic, wersja i ustawienie tempa |
| `budget_plans_v2` | Własny limit kategorii w konkretnym miesiącu, także 0 |
| `budget_default_plans` | Wersje domyślnych limitów od wskazanego miesiąca |
| `budget_plan_transfer_requests` | Idempotentne żądania przesuwania limitów wraz z zatwierdzonym podglądem |
| `budget_plan_copy_requests` | Wyniki zatwierdzonych żądań kopiowania zakresu |
| `budget_bills_v2` | Definicje rachunków i harmonogramów |
| `budget_bill_payments_v2` | Rozliczenia wystąpienia rachunku z istniejącym wydatkiem |
| `budget_expected_incomes` / `budget_expected_income_receipts` | Plan wpływu i jego otrzymanie/powiązanie |
| `budget_reserves` / `budget_reserve_movements` | Rezerwy i ruchy odłożenia, zwolnienia oraz płatności |
| `budget_reserve_operation_receipts` | Trwałe podsumowania operacji rezerwy i wyników zbiorczego odkładania; to nie są nowe przepływy pieniężne |
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

## 11. Przegląd planu i przesuwanie limitów

`GET /api/budget/workspace/plans/year?start=YYYY-MM` odczytuje dwanaście workspace od wskazanego miesiąca. Nie zapisuje planów. Wynik miesiąca jest miarą `monthly_income_to_plan`; obciążenie to wykonane koszty finansowane z przychodów plus pozostały plan. Kategorie nadrzędne i podrzędne nie są dodawane po raz drugi. Przyszłe przeniesienia są jawnie oznaczone jako orientacyjne; nie jest to symulacja przyszłych sald ani cykli rezerw.

`POST /api/budget/workspace/plans/transfer-preview` przyjmuje `month`, `source_id`, `target_id`, `amount`. Serwis sprawdza pozostałą zwykłą część planu, wspólne limity, obowiązkowe płatności i zakres edytowalnych miesięcy. Podgląd zawiera token aktualnych kategorii oraz obie kwoty przed i po zmianie. Kwoty powiązane z mediami nie uczestniczą w tej operacji.

`POST /api/budget/workspace/plans/transfer` przyjmuje te same dane, `token` i unikalne `request_id`. `BEGIN IMMEDIATE` obejmuje ponowną walidację, limity miesiąca źródła i celu oraz wymaganych rodziców, kontrolę zgodności wyniku i zapamiętanie żądania. Błąd wycofuje wszystkie zmiany limitów. Przeniesienie między grupami koryguje wspólne limity rodziców; przeniesienie między dwojgiem dzieci tego samego rodzica zachowuje jego całkowitą kwotę. Ponowienie tego samego żądania zwraca zapamiętany wynik; zmiana treści przy tym samym identyfikatorze jest konfliktem. Domyślne limity, salda i transakcje nie są modyfikowane.

Widoki prognozy nie resetują symulacji przy zmianie zakładki. Założenia miesiąca są prezentowane według rzeczywistych dat zdarzeń prognozy do wybranego końca zakresu, z pominięciem zapisanych już operacji. Filtry transakcji są osobnym ustawieniem `localStorage` przeglądarki i nie należą do kopii SQLite.

## 12. Karty kredytowe

Migracja addytywna w `budget_import_schema.initialize` dodaje `budget_accounts.account_type` z domyślnym `BANK`. Istniejące salda i transakcje nie są przepisywane. `CREDIT_CARD` przechowuje zadłużenie jako saldo ujemne, nadpłatę jako dodatnie. Otwarcie i korekty kart obsługują obie wartości; nie tworzą dochodów ani wydatków.

Zakup i zwrot korzystają z istniejących wpisów oraz podziałów kategorii. Spłata korzysta z `budget_account_transfers`, transakcji `BEGIN IMMEDIATE`, kontroli oczekiwanych sald i identyfikatora żądania. Nie powstaje drugi `budget_entries_v2`; historia kont rozpoznaje `CARD_PAYMENT` po rodzaju konta docelowego. Ręczna spłata nie przekracza długu ani wolnej gotówki źródła. Import obu stron przelewu łączy się przez istniejący identyfikator transferu. Nierozpoznany wpływ na kartę jest domyślnie `SKIP`, a nowy zwykły dochód na kartę jest odrzucany; zwroty korzystają z `budget_purchase_refunds`.

`balance`, `available_now` oraz `to_plan` zachowują sumę sald ze znakami. Dług jest już w tej sumie i nie jest odejmowany drugi raz ani odłożony jako rezerwa. Pola `cash_balance`, `credit_card_debt`, `credit_card_overpayment` służą jawnemu przedstawieniu składowych. W globalnym majątku aktywa to saldo netto plus dług kart; ten dług jest następnie wykazywany w zobowiązaniach. Wynik netto jest identyczny z sumą sald minus pozostałe kredyty.

Prognoza zachowuje sumę sald ze znakami, dodaje typ do przebiegów kont i nie traktuje ujemnego salda karty jako niedoboru fizycznej gotówki ani celu propozycji przelewu. Nie planuje automatycznie przyszłej spłaty bez ustalonego terminu. Rezerwy i finansowanie inwestycji wymagają `BANK`, również przy dodatniej nadpłacie karty.

## 13. Podglądy i historia rezerw

`budget_reserve_operations_service` wykonuje podgląd przy użyciu tej samej ścieżki księgowania w transakcji zakończonej rollbackiem. Skrót stanu obejmuje salda kont, wersje rezerw, wpisów i planów rezerw; zatwierdzenie chroni przed zapisem na nieaktualnym podglądzie. Zbiorcze odłożenia korzystają ze wspólnej transakcji i deterministycznych identyfikatorów pozycji. `budget_reserve_operation_receipts` przechowuje wynik, aby ponowienie oddało ten sam rezultat.

Dla przekazanej nadwyżki źródłowa operacja zwalnia kwotę, a docelowa rezerwa otrzymuje ruch ADD na tych samych kontach. Część `budget_cost_cents` przenosi niewykorzystaną podstawę wcześniejszych odłożeń, zamiast naliczać ją drugi raz. Dane do cofnięcia są zapisane w `budget_settlements.before_json._surplus_transfer`; późniejsze zmiany docelowej rezerwy blokują cofnięcie. Cofnięte podsumowanie pozostaje oznaczone `cancelled`.

`budget_reserve_history_service` grupuje ruchy jednej płatności i łączy transfer FUND z odpowiadającym mu odłożeniem. Starsze rozliczenia otrzymują podsumowanie odczytane z istniejących danych, bez migracji kwot. Zestawienie miesiąca dotyczy przypisanych środków: początek + ADD − pokrycie płatności − zwolnienia = koniec. Kwota wydatku bankowego jest osobną miarą. Przeniesienia MOVE nie zmieniają łącznej kwoty rezerwy.


## 14. Analizy inwestycji i AI

[Referencja analiz](AI_PORTFOLIO_ANALYSIS_MODULE_PL.md) opisuje kontekst, tabele i trasy: `/api/ai` oraz `/api/investment-analysis`. `investment_ai_context` korzysta ze wspólnej wyceny i rzeczywistych wyników; rozmowa zachowuje niezmienny stan danych. `investment_ai_provider` obsługuje wersjonowane ustawienia, identyfikatory żądań i atomową rezerwację szacowanego kosztu. Materiały źródłowe wymagają osobnej analizy i potwierdzenia szkicu. Symulacja dopłaty i rozwinięcie częściowego składu ETF nie księgują transakcji.

Rozmowy, stany danych, teksty materiałów i rejestr kosztów są w lokalnej bazie oraz jej kopiach. Wywołanie generowania przesyła wskazane dane do Google Gemini. Konfigurację i zakres wysyłania opisuje [uruchomienie AI](URUCHAMIANIE_I_KOPIE_PL.md#9-opcjonalne-uruchomienie-ai). Tylko część tras ma opis OpenAPI; [zakres specyfikacji](API_ZAKRES_PL.md) rozróżnia katalog tras, kontrakt koperty i schematy pól.
