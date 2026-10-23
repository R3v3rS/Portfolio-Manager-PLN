# Najnowsza wersja aplikacji

Stan: 23 października 2026.

## Zmiany z 23 października

- Dokumentacja skrócona z 31 do 15 plików Markdown w repozytorium. Szesnaście dawnych raportów i planów zastępuje jeden indeks z trwałymi odnośnikami do ich pełnej treści w historii Git.
- Instrukcja budżetu używa aktualnych nazw „Zarządzaj” / „Edytuj” i jednej listy „Do zrobienia”. Opisy płatności i rezerw są w odpowiednich rozdziałach, bez powtarzania ich we wstępie.
- Spis dokumentacji rozdziela instrukcje użytkownika i referencje techniczne. Mapa testów uwzględnia nowe podsumowania, miary pasków, tryby pracy oraz wspólne zestawienie rachunków i rat.

## Zmiany z 22 października

- Budżet ma wspólny tryb przeglądania i zarządzania. Codzienna ewidencja pozostaje dostępna; limity, harmonogramy i ustawienia odsłaniane są osobno. Ostrzeżenia chronią zmodyfikowane formularze i limity.
- Plan kategorii: cztery kolumny, paski wykonania i zobowiązań, rozpisane części wspólnego limitu oraz kwota nieprzypisana. Podkategoria bez kwoty nie sugeruje dodatkowych pieniędzy poza przydziałami rodzeństwa.
- Zestawienie wydatków według kategorii prowadzi do filtrowanych transakcji. Sumy wybranej kategorii uwzględniają pasujące pozycje zakupów mieszanych i zwroty.
- Paski w „Na co wydano?” mają osobne miary wykorzystania planu i udziału w wydatkach. Długość odpowiada podpisowi; przekroczenia mają kwotę i kolor, a zwinięte kategorie wyjaśniają różnicę do sumy całego miesiąca.
- Czytelniejszy budżet: zwarty nagłówek, tylko zakładki pozostające u góry, trzy główne kwoty z rozwijanym objaśnieniem oraz większe opisy pomocnicze.
- Na telefonie plan kategorii ma karty bez przewijania w bok i rozwijane filtry. Karty rezerw są krótsze; historia, miejsca środków i dodatkowe operacje są w szczegółach.
- Jedna lista „Do zrobienia” zamiast dwóch powtarzających się sekcji: trzy pilne sprawy na start, pełna lista i filtr rodzaju. Dopasowania płatności zastępują powtarzające się przypomnienia.
- Rachunki i raty kredytów mają wspólne podsumowanie kwot, najbliższego terminu i opłaconych pozycji. Rezerwy oddzielają zgromadzone środki od wykonania miesięcznej wpłaty.

- Nowe i nieużywane kategorie są dostępne przy edycji limitów, a ustawienia pokazują je domyślnie. Dodanie kategorii otwiera edycję planu i nie zapisuje samoczynnie kwoty limitu.

- Podsumowanie budżetu rozdziela bilans dochodów miesiąca, zakupy i prognozę środków poza rezerwami. Dzisiejsze pieniądze są osobno; objaśnienie przyszłego miesiąca pokazuje koszty wcześniejszego okresu i różnicę założeń prognozy.

- Przegląd dokumentacji: poprawione zasady kopii i przywracania, jakość wyceny, identyfikatory importu XTB oraz jednostki analiz. Krótka instrukcja budżetu, mapa testów i konfiguracja AI z opisem wysyłanych danych. OpenAPI jawnie częściowe, uzupełnione o trzy odczyty; archiwizacja ma jedną główną instrukcję.

- Wspólna wycena i rzeczywiste wyniki w asystencie, poprawny zakres podportfeli, obsługa PPK, obligacji i oszczędności oraz jawne braki cen/FX.
- Zapisane rozmowy ze stanem danych, dopytania, źródła, porównanie przeglądów i zapis do dziennika. Lokalne podsumowanie bez klucza AI.
- Założenia strategii, udziały i symulacja nowej wpłaty. Częściowy skład ETF ze źródłem i datą, wspólna ekspozycja i jawnie nieznany udział.
- Pięć głównych sekcji portfela i do trzech spraw do sprawdzenia. HHI opisuje rozproszenie instrumentów, nie spółek wewnątrz ETF.
- Artykuły Inwestomatu i Comparic jako domyślne materiały, z pobieraniem treści do podglądu. Filmy pozostają dodatkowym źródłem; analiza używa filmu lub transkrypcji, nie samego opisu.
- Szkice opinii wymagają potwierdzenia. Konfigurowalny Gemini i wspólny szacowany dzienny limit kosztów. [Instrukcja analiz i asystenta](AI_PORTFOLIO_ANALYSIS_MODULE_PL.md).

## Zmiany z 19 października

- Rozliczenie rezerwy z podglądem sald i wolnych środków oraz trwałym podsumowaniem płatności, wykorzystanej rezerwy i nadwyżki. Przejście bezpośrednio do konkretnej transakcji.
- Wspólna historia odłożeń, przelewów, płatności i zwolnień; zestawienie miesiąca uzgadniające stan początkowy i końcowy, osobno plan i wykonanie.
- Wybór przeznaczenia nadwyżki celu terminowego: wolne środki, inna rezerwa lub kolejny cykl. Przekazanie zachowuje miejsca pieniędzy i nie powiela kosztów; cofnięcie rozliczenia obejmuje także nadwyżkę.
- Zbiorcze odkładanie według ważności z edycją kwot i kont, podglądem, kontrolą zmian sald i atomowym, idempotentnym zatwierdzeniem.

- Początek odkładania w miesięcznych pulach mediów i rezerwach bez terminu. Plan oraz prognoza zaczynają naliczać wpłaty od wybranego miesiąca.
- Karta przyszłej puli pokazuje miesiąc startu i nie przypisuje do niej wcześniejszej płatności z tej samej kategorii. Historia wydatków i saldo pozostają zachowane.
- Początek puli z zapisanymi odłożeniami lub rozliczeniami jest chroniony; nowy okres można prowadzić jako osobną pulę.

## Zmiany z 17 października

- Karta kredytowa jako osobny rodzaj konta: zakup obciąża miesiąc transakcji, a późniejsza spłata jest przelewem własnym bez ponownego wydatku.
- Osobno własna gotówka, dług kart i wolne środki. Ujemne saldo karty jest zobowiązaniem w majątku netto, uwzględnianym tylko raz.
- Początkowy dług, częściowe spłaty, podgląd sald i zwroty zakupów. Import dodatnich wpływów na kartę wymaga wyjaśnienia, a istniejącą spłatę można powiązać z wyciągiem.
- Rezerwy dostępne dla własnych pieniędzy; prognoza rozróżnia dług karty i niedobór gotówki. Termin przyszłej spłaty nie jest zgadywany.

## Zmiany z 14 października

- Budżet z trzema głównymi kwotami: wydano w miesiącu, do rozdysponowania w planie i przewidywane saldo końca miesiąca. Oczekiwane wpływy oraz wcześniejsze salda są wyjaśnione osobno.
- Kompaktowa tabela limitów ze zwijanymi podkategoriami, opisami i przypisanymi płatnościami. Kategorie w ustawieniach też są grupowane i zwijane.
- Przenoszenie wolnego limitu między kategoriami z podglądem, ochroną wydatków i zobowiązań, zapisem atomowym oraz bezpiecznym ponowieniem.
- Przegląd planu 12 miesięcy, źródła limitów, brakujące plany i oznaczenie orientacyjnych przeniesień. Jest to przegląd zapisów, odrębny od prognozy salda.
- Kolejka spraw do sprawdzenia i zapisane filtry transakcji w przeglądarce. Pełny podział zakupu, paragony i zwroty w szczegółach transakcji.
- Osobne sekcje ustawień i prognozy, uproszczone menu oraz skrót do rozliczenia miesiąca. Okres określony stałym dniem ma nazwę „Okres rozliczeniowy”.
- Import CSV i nowy zakup z paragonu wymagają jawnego wyboru wpływu na saldo. Powiązanie z istniejącą transakcją nadal zachowuje jedną płatność.
- Wykonanie planu rezerw jest oddzielone od dodatkowych wpłat. Nadwyżka jednego celu nie ukrywa braków innych.
- Przedziały niedoborów w prognozie i założenia ograniczone do wybranego zakresu, również dla części ostatniego miesiąca. Zmiana zakładki nie pobiera niepotrzebnie prognozy od nowa.

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
