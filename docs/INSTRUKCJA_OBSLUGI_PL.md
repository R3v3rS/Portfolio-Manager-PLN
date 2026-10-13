# Instrukcja obsługi całej aplikacji

Stan funkcjonalności: 13 października 2026. [Spis dokumentacji](README.md) · [Dokładna instrukcja budżetu](BUDZET_INSTRUKCJA_PL.md) · [Uruchamianie i kopie](URUCHAMIANIE_I_KOPIE_PL.md)

## 1. Jak zacząć

Aplikacja łączy ewidencję kont i wydatków, inwestycje, kredyty oraz analizę majątku. Nie wykonuje operacji w banku ani u brokera. Dodanie płatności, przelewu lub transakcji oznacza zapis do własnej ewidencji.

Zacznij od kont budżetowych z aktualnym saldem. Następnie dodaj dochody, rachunki i kredyty. Portfele inwestycyjne uzupełnij historią wpłat oraz transakcji. Na końcu ustaw rezerwy, cele i limity. Analizy będą tak kompletne, jak wprowadzona historia i dostępne wyceny.

Nawigacja po lewej prowadzi do głównych modułów. W budżecie jest dodatkowy wspólny pasek zakładek i wybór miesiąca. Archiwalne obiekty mogą wymagać włączenia filtra archiwum. Filtry oraz wybór okresu mogą zmienić widoczne sumy bez zmiany danych.

| Moduł | Adres | Główne zastosowanie |
|---|---|---|
| Centrum finansów | `/` | Majątek, płynność i sprawy wymagające działania |
| Portfele | `/portfolios` | Przegląd inwestycji i strategii |
| Szczegóły portfela | `/portfolio/:id` | Pozycje, transakcje, wyniki i analizy |
| Cele inwestycyjne | `/goals` | Postęp do celu i plan wpłat |
| Dziennik inwestora | `/journal` | Tezy, decyzje i terminy przeglądu |
| Radar | `/radar` | Obserwowanie instrumentów i alertów |
| Pomysły inwestycyjne | `/ideas` | Publiczne publikacje i własna selekcja pomysłów |
| Historia transakcji | `/transactions` | Operacje inwestycyjne w wybranym zakresie |
| Raport miesięczny | `/reports/monthly` | Wynik miesiąca i zmiana majątku |
| Budżet | `/budget` | Plan, wydatki, płatności i zamknięcie |
| Kredyty | `/loans` | Harmonogramy i rozliczenie spłat |
| Centrum narzędzi | `/admin` | Kopie, diagnostyka i narzędzia administracyjne |

## 2. Centrum finansów

Na górze znajdują się najważniejsze kwoty: majątek netto, środki płynne, kwota do zaplanowania oraz najbliższa nierozliczona rata. Dalej są konkretne sprawy, np. brak rozliczenia rachunku, potrzebne odłożenie czy dane wymagające sprawdzenia. Wybór sprawy prowadzi do miejsca jej obsługi.

**Majątek netto** to aktywa minus kredyty uwzględniane w tej miarze. Kredyt oznaczony jako pomijany nadal istnieje w module kredytów i planie spłat, lecz jest wymieniany osobno przy majątku. Rezerwa na budżetowym koncie nie jest dodatkowym aktywem obok tego konta.

Wykres majątku pozwala wybrać krótszy lub dłuższy zakres. Zapisy bieżące powstają podczas otwierania pulpitu; wcześniejsze punkty mogą pochodzić z odtworzonej historii. Brak punktu nie oznacza zerowego majątku. Wczesna historia może być niepełna, jeśli brakuje operacji lub wycen.

Saldo dostępnych kont oraz szacunkowa wartość inwestycji opisują różne rodzaje pieniędzy. Kwota „Do zaplanowania” uwzględnia również oczekiwane dochody i przeznaczenia budżetowe; nie jest równoznaczna z dzisiejszą bankową gotówką.

## 3. Portfele i rodzaje kont inwestycyjnych

### Utworzenie portfela

W **Portfelach** dodaj konto, nadaj nazwę i wybierz rzeczywisty typ: rachunek inwestycyjny, IKE, IKZE, obligacje, oszczędności albo PPK. Typ wpływa na widok i obliczenia. Nazwa może być dowolna — zmiana IKE na „Emerytura” nie zmienia typu konta ani sama nie zeruje licznika wpłat.

Portfel główny może mieć podkonta/strategie. Przegląd pokazuje drzewo i pozwala rozwinąć strategie. Podsumowanie głównego portfela uwzględnia jego aktywne zakresy, więc nie dodawaj ponownie wyświetlonej wartości strategii do wartości rodzica.

### Trzy różne miary

Wartość aktywów, wynik inwestowania i kwota możliwa do wypłaty nie zawsze są takie same. Szczególnie w PPK lub obligacjach wynik może zależeć od potrąceń, opłat i rodzaju rozliczenia. Nie odejmuj wpłat od kwoty możliwego zwrotu tak, jakby była pełną wartością jednostek funduszu.

Przy niepełnej wycenie sprawdź oznaczenia, datę ceny, walutę i kurs przeliczenia. Brak liczby nie powinien być interpretowany jako wynik 0 zł.

## 4. Akcje i ETF-y

### Wpłata, zakup, sprzedaż i wypłata

Wpłata zwiększa gotówkę portfela. Kupno zużywa gotówkę i tworzy pozycję. Sprzedaż zamyka odpowiednią ilość pozycji, zwiększa gotówkę i rozlicza zrealizowany wynik. Wypłata wyprowadza gotówkę z portfela. Dywidendy i odsetki są osobnymi operacjami.

Przy wpisie sprawdź datę, symbol, ilość, cenę, walutę, opłaty oraz strategię. Kwota jednostkowa i łączna wartość nie są zamienne. Przy aktywach zagranicznych wynik w PLN zależy również od kursu waluty. Korekta wcześniejszej transakcji może przeliczyć późniejsze pozycje, gotówkę i historię.

### Import brokera

W szczegółach portfela otwórz import. Możesz użyć oryginalnego pliku XTB XLSX lub CSV. Z Excela odczytywany jest arkusz **Cash Operations** — nie trzeba osobno scalać go z historią zamkniętych i otwartych pozycji.

Najpierw przejrzyj podgląd/sesję: rozpoznane typy operacji, symbol brokerowy i rynkowy, duplikaty, błędy oraz przypisanie do strategii. Brakujący symbol powiąż przez mapowanie, zamiast zgadywać ticker. Istniejące sesje można wznowić. Bezpośredni import jest dostępny, ale podgląd jest wygodniejszy przy nieznanym formacie i mapowaniu.

Import zapisuje księgowanie; nie wykonuje transakcji u brokera. Nie importuj tej samej operacji równolegle jako własnej ręcznej transakcji bez kontroli duplikatu. Jeśli import przerwie się komunikatem, sprawdź stan sesji i historię przed ponownym plikiem.

### Instrument bez bieżących notowań

Pozycja może nie mieć dostawcy notowań. Oznaczenia wskazują brak aktualnej ceny lub użycie ceny ręcznej/orientacyjnej. Ręczną cenę wpiszesz przy instrumencie; kontroluj datę i walutę. Cena zakupu użyta do orientacji nie dowodzi, że aktualny wynik wynosi zero.

Sprzedaż rozlicza wynik z faktycznej zapisanej ceny sprzedaży. Ręczny punkt cenowy nie odtwarza całej dawnej historii, dlatego część analiz ryzyka i wyników nadal może mieć luki.

## 5. Strategie, przenoszenie i archiwizacja

Strategia jest wydzielonym zakresem głównego portfela. Możesz przenosić istniejącą gotówkę lub akcje, zamiast tworzyć fikcyjne kupno i sprzedaż. Przeniesienie jest przepływem dla wyników strategii, ale nie nową wpłatą ani zyskiem dla całego głównego portfela.

Przy nowej strategii sprawdź moment rozpoczęcia oraz wartość przenoszonych aktywów. Wynik od przeniesienia różni się od wyniku całej pozycji od jej pierwotnego zakupu; historyczny koszt pozycji i kapitał startowy strategii służą innym celom analizy.

**Archiwizacja strategii** przenosi jej gotówkę i pozycje do zakresu głównego, zachowuje historię strategii i zatrzymuje jej archiwalny wynik oraz wykresy. Kwoty archiwum są zapisem stanu przy zamknięciu, a nie dodatkowym aktywnym majątkiem. Archiwizacja nie jest usunięciem historii.

Scalanie historii strategii z głównym portfelem jest inną operacją niż archiwizacja. Przed scalaniem, zmianą zakresów i naprawą historii wykonaj kopię. Nie trzeba scalać starej historii, aby utworzyć nową strategię i od tego momentu analizować jej wynik.

## 6. Jak czytać wyniki i ryzyko

### Rzeczywiste wyniki

Widok wyników oddziela wpłaty/wypłaty od tego, co wypracowały aktywa. Wybierz 3 miesiące, 6 miesięcy, rok lub całą historię. Sprawdź kapitał, zmianę wartości, wynik oraz miesięczne okresy. Analiza celu obejmuje historię aktualnie przypisanych portfeli, także sprzed utworzenia celu.

Modified Dietz przybliża stopę zwrotu z uwzględnieniem terminu obecności kapitału. Nie jest dokładnym dziennym TWR. XIRR jest stopą roczną; obecna analiza wymaga co najmniej roku historii i odpowiednich przepływów. Jeśli nie da się uzyskać wiarygodnego wyniku, pole pozostaje puste, zamiast prezentować 0%.

Historia używa dostępnych zapisanych cen i kursów z danego dnia lub ostatnich wcześniejszych punktów. Przy niepełnych danych czytaj objaśnienia i ostrzeżenia. Zmiana cen ręcznych, brak FX albo krótka historia może ograniczyć porównywalność.

### Struktura i ryzyko

Analiza struktury pomaga sprawdzić koncentrację pozycji oraz rozkład aktywów. Analiza ryzyka pokazuje m.in. zmienność, Sharpe, obsunięcie i VaR. Sprawdź faktyczne daty i liczbę wspólnych obserwacji — wybór „rok” nie gwarantuje pełnego roku danych dla każdego instrumentu.

Ryzyko dotyczy obecnego koszyka części akcyjnej, bez gotówki i pełnej rekonstrukcji dawnych zmian składu. Maksymalne obsunięcie tego koszyka nie musi odpowiadać całej historii Twojego konta. VaR jest oszacowaniem dla modelu i danych, a nie maksymalną możliwą stratą. Brakujące lub niewystarczające dane mogą uniemożliwić obliczenie.

## 7. Obligacje

Portfel typu **Obligacje** ma dedykowany widok. Przy dodaniu serii sprawdź rodzaj, datę nabycia, ilość/wartość nominalną, okresy oprocentowania, parametry kolejnych okresów oraz termin wykupu. Przy oprocentowaniu zależnym od indeksu brak przyszłych danych jest założeniem, nie znaną stawką.

Odróżniaj odsetki szacowane narastająco od już wypłaconego dochodu. Obligacja rozliczana raz w roku może mieć widoczne obecnie narosłe odsetki, chociaż nie wpłynęły jeszcze na konto. Kapitalizacja nie jest wypłatą budżetową.

Kalendarz zdarzeń pokazuje odsetki, kapitalizację i wykup. Do prognozy budżetowej wypłata trafia tylko przy wskazanym planie transferu na konto budżetowe. Sprawdź model netto, ewentualne opłaty oraz ostrzeżenia o niepotwierdzonej stawce. Zapis rzeczywistej wypłaty powinien odpowiadać operacji w banku.

## 8. PPK i oszczędności

### PPK

Uzupełnij fundusz, ilość jednostek oraz wpłaty uczestnika, pracodawcy i państwa zgodnie z dokumentacją dostawcy. Widok oddziela wartość jednostek od szacowanej kwoty zwrotu. Podział źródeł i kompletność dopłat wpływają na model rozliczenia; sama łączna suma wpłat nie zastępuje poprawnej historii jednostek.

Sprawdź datę notowania i użyj odświeżenia. Brak nowego notowania nie oznacza, że aplikacja może podpisać dawną cenę dzisiejszą datą. Jeżeli kwota u dostawcy się różni, porównaj datę wyceny, jednostki i rozbicie wpłat. Szacunek aplikacji nie jest potwierdzoną kwotą wypłaty od instytucji.

### Oszczędności

Konto inwestycyjne typu **Oszczędności** opisuje kapitał, historię wpłat/wypłat i odsetki. Ma inny model prezentacji niż portfel akcji. Jeżeli to samo fizyczne konto pokazujesz także w budżecie, sprawdź transfery i sposób ewidencji, aby nie wpisać tego samego salda jako dwóch niezależnych aktywów.

## 9. Cele inwestycyjne

Dodaj nazwę celu, kwotę, termin, plan miesięcznej wpłaty i przypisane portfele. Zobaczysz postęp i scenariusz realizacji. Planowany zwrot w scenariuszu jest założeniem — nie dopisuje zysku do portfela ani nie zasila budżetu.

Plan wpłat wpływa na prognozę budżetu. Faktyczne transfery pomniejszają brakującą wpłatę. Cele korzystające ze wspólnych portfeli są rozpatrywane jako wspólny plan, aby nie powielać tych samych wpłat. Zmiana przypisania portfeli zmienia zakres analizy celu.

## 10. Dziennik inwestora

Zapisuj tezę, powód decyzji, ryzyka, warunki unieważnienia tezy, datę i termin ponownego przeglądu. Powiąż wpis z instrumentem lub portfelem, gdy to przydatne. Korzystaj ze stanów i filtrów przeglądu, aby wracać do decyzji.

Wpis w dzienniku nie jest transakcją i nie zmienia salda. Jeżeli po analizie wykonasz kupno lub sprzedaż, zapisz ją w historii inwestycji osobno. Dzięki temu opis decyzji i rzeczywiste wykonanie można porównać.

## 11. Radar i pomysły inwestycyjne

Radar służy własnej obserwacji instrumentów, cen i warunków alertów. Sprawdź źródło, datę i dostępność ceny. Alert nie zleca kupna ani sprzedaży.

**Pomysły inwestycyjne** zbierają dostępne publiczne publikacje źródeł, w tym wskazanych twórców. Odśwież publikacje, wybierz materiał, sprawdź link i datę oraz zapisz własny pomysł lub obserwację. Powiąż instrument, jeśli został prawidłowo rozpoznany.

Lista nie jest automatycznym rankingiem najlepszych spółek miesiąca. Publiczny tytuł lub wzmianka nie dowodzi, że autor aktualnie rekomenduje zakup. Treści płatne, niepubliczne materiały, brak transkrypcji i błędy źródła mogą ograniczać odczyt. Sprawdź oryginalną publikację przed przypisaniem autorowi konkretnej tezy.

## 12. Kredyty

Dodaj parametry kredytu, datę rozpoczęcia, typ rat, czas spłaty i oprocentowanie. Wprowadź kolejne zmiany oprocentowania oraz nadpłaty. Harmonogram i symulator pomagają sprawdzić skutki skrócenia okresu lub obniżenia rat; wynik zależy od zapisanych parametrów i modelu.

W szczegółach ustaw konto i kategorię budżetową. Potwierdź konkretny numer raty, rzeczywistą datę i kwotę. Importowaną płatność powiąż z istniejącą transakcją. Sama data potwierdzenia nie powinna być zgadywana z numeru miesiąca.

Sprawdź rozróżnienie zapisu spłaty oraz księgowania w budżecie. Przy korekcie lub cofnięciu zapisu przeczytaj podgląd wpływu na istniejący wydatek i saldo. [Instrukcja budżetu](BUDZET_INSTRUKCJA_PL.md#7-rachunki-i-raty-kredytów) opisuje te sytuacje szczegółowo.

Opcja **nie uwzględniaj w majątku netto** zmienia prezentację majątku. Nie usuwa kredytu, harmonogramu ani płatności z budżetu i prognozy.

## 13. Raport miesięczny

Wybierz miesiąc i sprawdź dochody, wydatki, przeznaczenie pieniędzy, wyniki inwestycji oraz zmianę majątku. Raport obejmuje dedykowane modele PPK i obligacji. Narosły wynik inwestycji i wypłacony dochód są różnymi zdarzeniami.

Przy zmianie majątku rozdziel nowe wpłaty, wyniki aktywów i zmianę długu. Korekty sald są prezentowane odrębnie. Sprawdź informacje o niepełnej historii i wycenie, zanim porównasz miesiące. Raport nie jest dodatkowym księgowaniem i nie dopisuje operacji do kont.

## 14. Centrum narzędzi

- **Kopie bazy** — utworzenie, pobranie i przywrócenie lokalnej kopii SQLite.
- **Spójność danych** — wykryte błędy i ostrzeżenia. Otwórz szczegóły flagi; ostrzeżenie samo nie przesądza o błędnym saldzie.
- **Historia cen** — sprawdzenie dat i braków wyceny.
- **Mapowanie symboli** — powiązanie symbolu brokera z instrumentem rynkowym.
- **Narzędzia portfela** — przeliczenie/diagnostyka zależności transakcji, pozycji i gotówki.
- **Administracja budżetem** — narzędzia danych budżetowych; nie zastępują codziennej obsługi zakładek.

Naprawa, przeliczenie, scalanie, reset i przywrócenie bazy mogą mieć szerokie skutki. Najpierw zachowaj kopię i sprawdź zakres operacji. Przywrócenie kopii dotyczy całej bazy, a nie jednego widoku.

## 15. Gdy coś się nie zgadza

Sprawdź właściwy miesiąc/okres, konto lub strategię, aktywne filtry, typ operacji, powiązania i datę wyceny. Rozdziel brak danych od wartości zero. Po błędzie połączenia sprawdź, czy zapis już pojawił się w historii, zanim utworzysz go ponownie.

Do zgłoszenia problemu wystarczą: moduł, kolejne wykonane kroki, data, oczekiwany wynik, faktyczny wynik i komunikat. Zrzut ekranu lub plik diagnostyczny może zawierać prywatne kwoty; publikując zgłoszenie, użyj danych przykładowych. [Uruchamianie i kopie](URUCHAMIANIE_I_KOPIE_PL.md) opisują kontrolę lokalnej instancji i zachowanie danych.
