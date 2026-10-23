# Budżet domowy — szczegółowa instrukcja

Stan funkcjonalności: 23 października 2026. Wszystkie kwoty poniżej są przykładami. [Spis dokumentacji](README.md) · [Pozostałe moduły](INSTRUKCJA_OBSLUGI_PL.md)

Do codziennej pracy zacznij od [krótkiej instrukcji budżetu](BUDZET_NA_CO_DZIEN_PL.md). Poniżej znajdziesz szczegółowe zasady i przypadki szczególne.

## Spis treści

1. [Podstawowe pojęcia i zakładki](#1-podstawowe-pojęcia-i-zakładki)
2. [Pierwsze ustawienie budżetu](#2-pierwsze-ustawienie-budżetu)
3. [Konta, saldo początkowe i korekty](#3-konta-saldo-początkowe-i-korekty)
4. [Kategorie, podkategorie i limity](#4-kategorie-podkategorie-i-limity)
5. [Plan domyślny, wyjątki i kopiowanie](#5-plan-domyślny-wyjątki-i-kopiowanie)
6. [Dochody i zwykłe wydatki](#6-dochody-i-zwykłe-wydatki)
7. [Rachunki i raty kredytów](#7-rachunki-i-raty-kredytów)
8. [Rezerwy na przyszłe wydatki](#8-rezerwy-na-przyszłe-wydatki)
9. [Miesięczne pule na prąd i wodę](#9-miesięczne-pule-na-prąd-i-wodę)
10. [Przelewy między kontami i inwestycjami](#10-przelewy-między-kontami-i-inwestycjami)
11. [Import bankowy, reguły i paragony](#11-import-bankowy-reguły-i-paragony)
12. [Zwroty zakupów](#12-zwroty-zakupów)
13. [Podsumowanie i tempo wydatków](#13-podsumowanie-i-tempo-wydatków)
14. [Prognoza pieniędzy](#14-prognoza-pieniędzy)
15. [Zamknięcie miesiąca](#15-zamknięcie-miesiąca)
16. [Codzienna i miesięczna rutyna](#16-codzienna-i-miesięczna-rutyna)
17. [Najczęstsze pytania i pomyłki](#17-najczęstsze-pytania-i-pomyłki)

## 1. Podstawowe pojęcia i zakładki

### Przeglądanie i zarządzanie

Budżet otwiera się w **Przeglądaniu**. Widzisz kwoty, wykonanie limitów, rachunki i historię. Nadal możesz dodawać wydatki, wpływy i paragony, przypisywać importy, zapisywać opłacenie rachunku, przelew lub odłożenie na rezerwę. To codzienna ewidencja.

**Zarządzaj** (na telefonie **Edytuj**) w pasku nad zakładkami odsłania zmianę limitów, struktury kategorii, harmonogramów rachunków i dochodów, ustawień oraz archiwizację i usuwanie zapisanych pozycji. Wybrany tryb pozostaje podczas przechodzenia pomiędzy zakładkami budżetu. Odświeżenie lub ponowne otwarcie aplikacji rozpoczyna przeglądanie; tryb nie jest zapisywany w bazie.

W zarządzaniu pola limitów i odłożeń otwierasz przy **konkretnej pozycji**. Samo włączenie trybu nie otwiera wszystkich edytorów. Zmodyfikowany limit lub formularz ustawień wywołuje ostrzeżenie przy wyjściu z edycji, przejściu linkiem, zmianie miesiąca lub zamykaniu strony. Zapisz zmiany albo potwierdź ich odrzucenie. **Zakończ** (na telefonie **Gotowe**) chowa ustawienia. Przełącznik upraszcza widok; nie jest blokadą dostępu ani systemem uprawnień.

Budżet odpowiada na trzy osobne pytania: ile pieniędzy jest na kontach, na co je przeznaczono oraz jakie operacje faktycznie wykonano. Plan nie jest przelewem, a odłożenie pieniędzy nie musi oznaczać opuszczenia konta.

| Pojęcie | Co oznacza |
|---|---|
| Saldo konta | Kwota własnych pieniędzy na koncie; na kredytówce saldo ujemne oznacza zadłużenie, a dodatnie nadpłatę |
| Saldo początkowe | Pieniądze, które już miałeś przy rozpoczęciu ewidencji; nie są dochodem miesiąca |
| Limit kategorii | Kwota przeznaczona na kategorię w miesiącu, nie dodatkowe pieniądze na koncie |
| Rachunek | Plan konkretnej płatności z terminem, kontem i kategorią |
| Wydatek | Zapis wykonanego zakupu lub płatności, także historycznej |
| Rezerwa | Część istniejących pieniędzy wydzielona na wskazany cel |
| Odłożenie | Przypisanie pieniędzy do rezerwy; zmniejsza wolne środki, ale samo nie zmienia salda bankowego |
| Przelew własny | Zmiana miejsca pieniędzy między własnymi kontami; nie jest nowym dochodem ani zakupem |
| Prognoza | Symulacja przyszłych sald i wolnych środków na podstawie planów |

| Zakładka | Do czego służy |
|---|---|
| Podsumowanie | Wydatki miesiąca, zobowiązania, wolne kwoty, pilne sprawy i tempo |
| Plan miesiąca | Limity kategorii, ich wykonanie, przypisane płatności, odłożenia i zamknięcie |
| Transakcje | Historia podzielona na dni, wyszukiwarka, filtry, edycja, paragony i zwroty |
| Rachunki i raty | Rachunki jednorazowe i powtarzalne oraz raty kredytów |
| Rezerwy | Rezerwy terminowe, miesięczne pule mediów i odkładanie bez terminu |
| Konta | Salda, otwarcie ewidencji, porównanie z bankiem i przelewy |
| Prognoza | Saldo na 30, 90 i 365 dni, kalendarz oraz założenia miesięczne |
| Ustawienia | Kategorie, domyślne limity, osobne sekcje kategorii, planu domyślnego, reguł, kont i okresu oraz końca miesiąca |
| Dodaj / Importuj | Skróty do wpływu, wydatku, CSV, paragonu i wpisów do sprawdzenia |

Przy przewijaniu pozostaje widoczny tylko pasek zakładek. Miesiąc i narzędzia przewijają się razem z treścią. Opisy obliczeń na trzech głównych kafelkach są rozwijane; informacja o oczekiwanych wpływach pozostaje widoczna.

Na telefonie tabela planu zmienia się w karty **Plan / Wydano / Pozostało**. Rozwinięcie kategorii pokazuje te same podkategorie i płatności co na komputerze. Wyszukiwarka oraz zakres kategorii są pod przyciskiem **Filtry kategorii**. Edycja używa tego samego limitu na obu ekranach.

Wybrany miesiąc jest zachowywany przy przechodzeniu między zakładkami. **Konta i rezerwy pokazują aktualny stan, a prognoza zaczyna się od dzisiaj.** Wybranie dawnego miesiąca nie cofa sald tych ekranów. Plan, transakcje i rozliczenie miesiąca dotyczą wybranego okresu.

## 2. Pierwsze ustawienie budżetu

1. Wejdź w **Konta** i dodaj wszystkie używane konta z aktualnym saldem, np. Konto główne, Konto oszczędnościowe i Gotówka.
2. W **Ustawieniach** uporządkuj kategorie i podkategorie. Nie trzeba tworzyć kategorii dla każdego sklepu.
3. W **Prognozie → Dochody** dodaj spodziewane wynagrodzenie i inne wpływy wraz z kontem oraz terminem.
4. W **Rachunkach i ratach** dodaj rachunki, wybierając ich rodzaj, kategorię i konto płatności.
5. W szczegółach każdego kredytu ustaw jego konto budżetowe i kategorię raty.
6. W **Planie miesiąca** ustaw limity zwykłych wydatków. Zobacz, jaka część wspólnego limitu jest już przeznaczona na rachunki lub raty.
7. Dodaj rezerwy, wskaż istniejące odłożone pieniądze i ustaw plan kolejnych wpłat.
8. Ustaw **Domyślny plan miesięczny** dla powtarzalnych limitów i sprawdź prognozę przyszłych miesięcy.

Jeśli saldo startowe zawiera już dawne zakupy, import tych zakupów wykonaj w trybie historii bez ponownego zmniejszania salda. Nowe zakupy, których saldo jeszcze nie uwzględnia, zapisuj z pomniejszeniem salda.

## 3. Konta, saldo początkowe i korekty

### Dodanie pieniędzy, które już masz

W **Kontach** dodaj konto z saldem początkowym. Jeśli masz 1500 zł w banku, podaj 1500 zł jako początek ewidencji. Nie dodawaj sztucznego wpływu „Moje dotychczasowe pieniądze” — zawyżyłby dochód miesiąca.

Jeśli konto już istnieje, rozwiń **Więcej opcji** na jego karcie i wybierz obsługę salda początkowego. Wpis otwarcia jest przechowywany osobno od dochodów i zwykłych korekt. Istniejącą korektę można oznaczyć jako dane otwarcia; ta operacja zachowuje bieżące saldo. Ustawienie lub zmiana salda otwarcia nie zastępuje sprawdzenia bieżącego salda z bankiem.

### Różnica między aplikacją a bankiem

Najpierw porównaj transakcje, zwroty, raty oraz przelewy. Jeżeli faktyczne saldo bankowe nadal się różni, użyj sprawdzenia/korekty salda w **Kontach**. Podaj rzeczywistą kwotę i opis różnicy. Korekta jest osobnym zapisem, a nie zwykłym dochodem. Widać ją w kontroli miesiąca.

Nie zapisuj korekty wyłącznie po to, aby ukryć podwójnie zaksięgowany rachunek. Usuń przyczynę duplikatu lub cofnij błędne rozliczenie.

### Gdzie są odłożone pieniądze

Konto pokazuje saldo, przypisane rezerwy i kwotę poza rezerwami. Przykład: saldo 2000 zł, rezerwy 700 zł — poza rezerwami zostaje 1300 zł. To nie są dwa salda do dodania: rezerwa już mieści się w tych 2000 zł.

### Karta kredytowa — zakup w tym miesiącu, spłata w następnym

1. Otwórz **Konta → Dodaj konto → Rodzaj konta → Karta kredytowa**. Podaj nazwę i obecne zadłużenie jako dodatnią kwotę. Jeśli karta jest spłacona, wpisz **0**. Nie wpisuj limitu przyznanego przez bank.
2. Każdy zakup dodawaj jako **wydatek**, wskazując kartę, faktyczną datę zakupu i kategorię. Możesz również dodać paragon albo importować transakcje z CSV karty. Dług karty wzrośnie, a wydatek obciąży kategorię miesiąca zakupu.
3. Po wykonaniu spłaty otwórz **Konta → karta → Zapisz spłatę**. Wybierz konto bankowe, rzeczywistą datę i kwotę. Formularz podpowiada pełne aktualne zadłużenie; możesz spłacić część. Przed zapisem zobaczysz nowe saldo banku i pozostały dług.
4. **Spłata jest przelewem własnym, nie kolejnym wydatkiem ani dochodem.** Nie dodawaj rachunku z drugą kwotą zakupu. Spłata nie zużywa limitu kategorii w następnym miesiącu.

Przykład: na koncie bankowym jest 3000 zł, karta jest spłacona. Kupujesz 20 października paliwo za 300 zł. Październik ma 300 zł wydatku w Paliwie; w banku nadal jest 3000 zł, a dług karty wynosi 300 zł. Łączne saldo po uwzględnieniu karty to 2700 zł. Spłata 5 listopada zmienia bank na 2700 zł, kartę na 0 zł i nie tworzy listopadowego wydatku. Wolne środki nie zmieniają się od samej spłaty.

Początkowy dług pomniejsza wolne środki bez sztucznego wydatku lub dochodu w miesiącu zakładania konta. Jeśli uzupełniasz dawne zakupy już uwzględnione w zadłużeniu, wybierz import **historii bez zmiany salda**. Przy sprawdzaniu salda i edycji salda początkowego karty wpisuj saldo ze znakiem: **−300 zł to dług**, +50 zł to nadpłata.

**Zwrot zakupu:** użyj funkcji zwrotu przy pierwotnej transakcji i wskaż kartę jako konto zwrotu. Zwrot zmniejszy wydatki oraz dług; po pełnej spłacie może utworzyć nadpłatę. Nie jest zwykłym dochodem.

**Import spłaty:** wiersz spłaty oznacz jako **Przelew własny** i wskaż drugie konto. Jeżeli spłata jest już zapisana, wybierz **Połącz z istniejącym**, zamiast tworzyć nowy przelew. Tak samo postąp po imporcie drugiej strony tej samej spłaty z wyciągu banku lub karty. Nierozpoznane dodatnie wpływy na kartę są domyślnie pomijane do wyjaśnienia; zwrot najpierw zapisz przy zakupie i połącz z nim wiersz wyciągu.

**Plan i prognoza:** zadłużenie jest już odjęte od łącznego salda i „Do rozdysponowania”. Nie twórz dodatkowej rezerwy na spłatę tego samego długu. Prognoza sumuje salda po uwzględnieniu kart, ale nie zgaduje terminu przyszłej spłaty ani zmiany konta, z którego ją wykonasz. Zapisz faktyczny przelew po wykonaniu. Dla pojedynczej karty minus oznacza dług, a nie niedobór rezerw. Kart nie używamy do przechowywania rezerw ani jako źródła własnych przelewów lub wpłat do inwestycji. Ręczna spłata jest ograniczona aktualnym długiem i środkami banku poza rezerwami.

## 4. Kategorie, podkategorie i limity

Nazwę, podział oraz uwzględnianie kategorii w tempie zmienisz w **Ustawieniach → Kategorie i podkategorie**. Kwoty miesięczne edytujesz w **Planie miesiąca → Zarządzaj → Zmień limit** (na telefonie przycisk **Edytuj**). W ustawieniach opisy i podkategorie są zwijane; wyszukiwanie odsłania pasujące wpisy. Dla podkategorii rozwiń ich listę.

W edycji kategorii możesz zapisać **Opis i przykłady**. Opis jest widoczny w ustawieniach, planie i przy wyborze kategorii nowego wydatku. Warto opisać cel zakupu: posiłek kupiony z konieczności może należeć do Jedzenia, a celowe wyjście do Przyjemności. Sama nazwa restauracji nie rozstrzyga tej decyzji.

Podgląd planu domyślnie ukrywa kategorie bez historii, planów, rachunków, rezerw oraz reguł. Włączenie **zarządzania** pokazuje także nieużywane kategorie, aby można było nadać im pierwszy limit. Ustawienia kategorii domyślnie pokazują wszystkie; opcjonalnie możesz wyłączyć nieużywane. Przełącznik **Pokaż nieużywane kategorie** odsłania je bez usuwania danych; wyszukiwanie również je pokazuje. Kategorie z zaplanowanym wydatkiem lub jawnym limitem 0 zł pozostają widoczne. Nowo dodana kategoria otwiera edycję planu; jej utworzenie nie ustala kwoty. Kategorie są wspólne dla miesięcy, a limit zapisujesz osobno dla wybranego miesiąca. Przy podkategorii bez własnej kwoty aplikacja wyjaśnia, czy korzysta ona ze wspólnego limitu rodzica, ma plan z rachunku, czy nie ma planu.

Aplikacja obsługuje dwa poziomy, np. **Transport → Paliwo / Bilety / Utrzymanie auta**. Zmiana nazwy zachowuje powiązania. Przeniesienie kategorii zmienia grupowanie jej dotychczasowych wpisów, dlatego może też zmienić prezentację wcześniejszych miesięcy.

**Limit kategorii głównej jest wspólny. Nie dodajemy go ponownie do sumy podkategorii.**

Przykład: Transport ma 800 zł, Paliwo 600 zł, Bilety 100 zł. Łączny plan Transportu wynosi 800 zł, a nie 1500 zł. Pozostałe 100 zł jest częścią wspólnej puli. Jeśli suma wymaganych planów podkategorii i rachunków ogólnych przekroczy wspólny limit, aplikacja podwyższy całkowity plan do tej sumy i pokaże wyjaśnienie.

Przykład z rachunkiem: Mieszkanie ma wspólny limit 1000 zł, a przypisany czynsz wynosi 700 zł. Na pozostałe wydatki zostaje 300 zł. Czynsz mieści się już w tych 1000 zł.

Kliknij nazwę kategorii, aby rozwinąć opis, podkategorie oraz przypisane płatności i pule. Lista płatności pokazuje termin, konto, status i podkategorię; opłacone pozycje można rozwinąć. W zarządzaniu nowy rachunek dodany stąd ma wstępnie wybraną kategorię, którą możesz zmienić na podkategorię.

Kategoria bez własnego limitu nie oznacza, że jej zakupy są bezkosztowe. Zapisany zakup pomniejsza saldo, a przekroczenie nie zwraca automatycznie pieniędzy do puli „Do rozdysponowania w planie”. Niezapłacone zobowiązanie również pozostaje do pokrycia.

### Czytanie planu i pasków wykorzystania

Tabela ma kolumny **Kategoria / Plan / Wydano / Pozostało**. Plan kategorii głównej zawiera podkategorie i przypisane płatności. Rozwiń kategorię, aby zobaczyć jej części: kwoty przypisane podkategoriom, płatności przypisane bezpośrednio do kategorii oraz **nieprzypisaną część planu**. Nie dodawaj wiersza rodzica ponownie do jego dzieci.

Przykład: Dom ma plan 300 zł, a Wyposażenie własny limit 300 zł. Nieprzypisana część planu Domu wynosi 0 zł. Podkategoria Inne zakupy bez własnej kwoty nie dostaje dodatkowych 300 zł. Zakup nadal obciąży wspólny plan Domu.

**Wydano** to faktyczne zakupy po zwrotach. **Pozostało** wynika z wykonania planu. Przy mediach wykonanie obejmuje również odłożenia, a płatności sfinansowane wcześniejszą rezerwą nie obciążają limitu ponownie. Jeżeli te miary się różnią, obok zakupów widzisz osobne wykonanie planu. Pozostało nie oznacza wolnego salda: w tej kwocie mogą nadal mieścić się oczekujące rachunki i plan mediów.

Pasek rozróżnia koszty obciążające ten plan (turkus), nieopłacone zobowiązania (złoty), wykonane i oczekujące odłożenia mediów (fiolet) oraz resztę planu (tło). Tekst podaje wykonanie i kwoty zobowiązań, a przekroczenie ma osobną kwotę i kolor. Brak planu jest oznaczony słownie, bez wyliczania procentu z zera. Sumy odłożeń na pozostałe rezerwy są pokazane oddzielnie poniżej tabeli, żeby nie zwiększać drugi raz limitów kategorii.

W podsumowaniu **Na co wydano?** pokazuje zakupy po zwrotach według kategorii głównych. Kliknięcie otwiera transakcje z filtrem obejmującym także podkategorie. Przy mieszanym paragonie podsumowanie filtra sumuje tylko jego pasujące pozycje; wiersz transakcji nadal pokazuje całą płatność. Przelewy i nowe odłożenia nie są zakupami w tym zestawieniu.

W tym zestawieniu przełącznik **Wykorzystanie planu** odnosi każdy pasek do planu jego kategorii: 80% wypełnia 80% szerokości, a przekroczenie ma pełny czerwony pasek i kwotę ponad plan. Wykonanie planu może różnić się od zakupów z powodu odłożeń mediów lub wykorzystania wcześniejszych rezerw; wtedy pokazujemy je osobno. Brak planu nie otrzymuje sztucznego procentu. **Udział w wydatkach** pokazuje natomiast udział kategorii w sumie wydatków; pasek i podpis korzystają z tej samej miary. Gdy zwroty przewyższają zakupy w którejś kategorii, udział liczymy tylko w dodatnich kwotach kategorii i podajemy podstawę obliczenia. Suma u góry nadal uwzględnia wszystkie zwroty. Przy zwiniętej liście podajemy kwotę pominiętych kategorii.

## 5. Plan domyślny, wyjątki i kopiowanie

### Stała podstawa kolejnych miesięcy

1. Otwórz **Ustawienia → Plan domyślny**.
2. Wybierz miesiąc obowiązywania: bieżący lub przyszły, po ostatnim zamkniętym miesiącu.
3. Wpisz kwoty albo kliknij **Użyj limitów z …**, aby wypełnić formularz zapisanymi limitami wybranego miesiąca.
4. Sprawdź podkategorie i jednorazowe wyjątki. Nie każdy wysoki limit z bieżącego miesiąca powinien obowiązywać przez cały rok.
5. Kliknij **Zapisz plan domyślny**.

Domyślny plan nie jest automatycznie aktywowany samym wypełnieniem formularza. Puste pole pozostawia dotychczasową zasadę. **0 zł zeruje własny limit**, lecz nie usuwa rachunków, rat ani osobnych limitów podkategorii. Miesięczne pule mediów mają własne ustawienia i nie otrzymują dodatkowego limitu z tego formularza.

Późniejsza zmiana obowiązuje od wskazanego miesiąca. Wcześniejsze wersje pozostają w historii, a już zaplanowana późniejsza zmiana jest widoczna przy kategorii.

### Wyjątek na jeden miesiąc

Wybierz miesiąc, włącz **zarządzanie**, kliknij **Zmień limit** przy wybranej kategorii, wpisz kwotę i zapisz kategorię. Ten zapis ma pierwszeństwo przed domyślnym limitem. Przykład: domyślnie Jedzenie 1000 zł, grudzień 1300 zł, styczeń znów 1000 zł, o ile nie ma własnego styczniowego zapisu.

Miesięczny wpis 0 zł jest decyzją, nie brakiem danych. Gdy istnieje domyślny limit, przy zapisanym wyjątku dostępne jest **Wróć do domyślnego**. Usuwa to wyjątek dla wybranej kategorii i miesiąca, zachowując historię wydatków.

### Kopiowanie kilku miesięcy

W **Planie miesiąca** kliknij **Kopiuj na 3, 6 lub 12 miesięcy**. Wybierz miesiąc źródłowy, pierwszy miesiąc docelowy, długość zakresu i kategorie. Źródło nie może należeć do zakresu docelowego.

Domyślna opcja **Zachowaj — uzupełnij tylko brakujące** chroni istniejące miesięczne limity, także 0 zł. Opcja **Zastąp** zmienia wybrane zapisane limity w zakresie. Najpierw kliknij **Pokaż podgląd**, sprawdź własne limity przed i po oraz dopiero potem **Zapisz pokazane limity**.

Kopiowane są własne zapisane lub domyślne limity, bez wykonanych płatności, historii zakupów, odłożeń ani przeniesionych nadwyżek. Brak limitu źródłowego jest oznaczony i pomijany. Końcowy wspólny plan nadal uwzględnia podkategorie oraz zobowiązania. Jeśli dane zmieniły się po podglądzie, trzeba sprawdzić nowy podgląd.

**Kopiowanie tworzy miesięczne wpisy, które mają pierwszeństwo przed domyślnym planem.** Do stałego planowania wygodniejszy jest plan domyślny; kopiowanie przydaje się do świadomego ustalenia konkretnego okresu. Jest też prosty przycisk uzupełnienia brakujących limitów z poprzedniego miesiąca.

### Przeniesienie wolnego limitu

W **Planie miesiąca** kliknij **Przenieś limit**. Wybierz kategorię źródłową, docelową i kwotę, następnie **Sprawdź podgląd**. Dopiero **Zatwierdź przeniesienie** zapisuje zmiany miesięcznych limitów.

Przykład: Jedzenie 1000 zł, Transport 500 zł. Przeniesienie 100 zł daje 900 zł i 600 zł, razem nadal 1500 zł. Domyślne limity, salda i historia zakupów pozostają zachowane. To zmiana przeznaczenia istniejącego planu, nie przelew ani dochód.

Możesz przenosić tylko pozostały limit zwykłych wydatków. Wykorzystane kwoty, rachunki, raty i odłożenia zachowują pokrycie. Nie przeniesiesz planu miesięcznej puli mediów ani kategorii do przypisania. Przy przenoszeniu między podkategoriami różnych grup podgląd pokaże także zmianę ich wspólnych limitów. Między dwiema podkategoriami tej samej grupy wspólna kwota pozostaje taka sama. Jeśli wolny limit kategorii głównej jest już rozdzielony między podkategorie, wskaż konkretną podkategorię źródłową. Nie można przenosić kwoty między rodzicem a jego dzieckiem, bo są częściami tej samej puli. Operacja dotyczy bieżącego lub przyszłego, niezamkniętego miesiąca. Po zmianie wydatków lub planu od czasu podglądu trzeba sprawdzić go ponownie. Ponowienie tego samego zapisu po utracie odpowiedzi nie przenosi limitu drugi raz. Jeśli zapis się udał, ale odczyt planu zawiedzie, aplikacja pokaże to wprost. **Odśwież plan** ponawia tylko pobranie danych.

### Przegląd na 12 miesięcy

W **Planie miesiąca** wybierz **12 miesięcy**. Zakres zaczyna się od wybranego miesiąca. Tabela pokazuje wpływy, zwykłe wydatki, opłaty i raty, odłożenia, obciążenie planu oraz wynik finansowany przychodami tego miesiąca. Kliknięcie miesiąca otwiera jego plan do edycji.

To odczyt zapisanych limitów i ich domyślnej podstawy. Nie tworzy przyszłych wpisów ani wydatków. Wynik miesiąca nie jest saldem konta; wcześniejsze oszczędności sprawdzisz w prognozie. Kategorie z aktywnością, ale bez własnego ani wspólnego planu, są oznaczone do sprawdzenia. Jawny limit 0 zł pozostaje zapisaną decyzją.

Rozwiń **Jakość planu**, aby zobaczyć źródła kwot i przeniesione limity. Przyszłe przeniesienie z niezamkniętych miesięcy jest orientacyjne: może się zmienić wraz z zakupami i decyzjami zamknięcia. Przyszłe cykle rezerw oraz szacunkowe wydatki pokazuje **Prognoza → Założenia**; nie uznawaj pustego przyszłego planu za brak kosztów.

## 6. Dochody i zwykłe wydatki

### Plan dochodu i otrzymanie pieniędzy

W **Prognozie → Dochody** podaj nazwę, konto, kwotę netto, pierwszy termin wpływu i powtarzalność: jednorazowo albo co miesiąc. Planowany dochód poprawia plan i prognozę, ale nie dopisuje pieniędzy do salda.

Po wpływie wybierz otrzymanie dochodu. Możesz zapisać rzeczywistą kwotę i datę albo powiązać plan z wpływem już zapisanym/importowanym. Powiązanie nie dodaje pieniędzy ponownie. Termin, który minął bez potwierdzenia wpływu, wymaga sprawdzenia — prognoza nie zakłada, że pieniądze na pewno wpłynęły.

### Wydatek i jego kategoria

Wybierz **Wydatek**, konto, datę, opis, kwotę i kategorię lub podział na pozycje. Suma podziału musi dokładnie odpowiadać wartości zakupu. Transakcje można wyszukiwać po opisie, sklepie i pozycjach paragonu oraz filtrować po koncie, kategorii, rodzaju i powiązaniu. Kliknij nazwę wpisu lub przycisk **Więcej działań**, aby zobaczyć cały podział, stan salda i działania: zwrot, paragon, powiązane rozliczenie oraz usunięcie. Edycja dostępnych do zmiany wpisów pozostaje także bezpośrednio w wierszu.

Wyszukiwarka i wybór konta są widoczne od razu. Rozwiń **Więcej filtrów i zapisane widoki**, aby wybrać kategorię, rodzaj lub stan. Ustaw filtry, wpisz ich nazwę i kliknij **Zapisz filtr**. Kliknięcie zapisanej nazwy przywraca wyszukiwanie, konto, kategorię, rodzaj i stan. Możesz zachować do 12 filtrów, np. „Bez paragonów”. Filtry są zapisane tylko w tej przeglądarce; nie są częścią bazy ani jej kopii. Przycisk przy nazwie usuwa filtr, nie transakcje.

Zwykły nowy wydatek zmniejsza saldo. Przy uzupełnianiu dawnej historii sprawdź, czy saldo już go obejmuje. Niektóre rozliczenia mają własne przyciski zamiast zwykłego ołówka; błędne powiązanie z rachunkiem, ratą lub rezerwą poprawiasz przez cofnięcie rozliczenia.

### „Historia — saldo już uwzględnia zakup”

Taki zapis trafia do historii i miesięcznych wydatków, ale nie zmniejsza ponownie salda. Przykład: podałeś aktualne saldo 1000 zł po wczorajszym zakupie 50 zł. Dodanie zakupu jako historii zostawi 1000 zł na koncie; zapisanie go jako nowego wydatku zmniejszyłoby saldo do 950 zł.

Jeśli omyłkowo wybrałeś historię dla naprawdę nowego zakupu, użyj dostępnej przy wpisie operacji uwzględnienia w saldzie. Sprawdź pokazane saldo przed i po. Zadziała tylko dla wpisu, którego wpływ na saldo nie był jeszcze zastosowany.

## 7. Rachunki i raty kredytów

W **Rachunkach i ratach** kwoty opłacone, pozostałe i najbliższy termin obejmują obie grupy. Filtr pozwala wybrać rachunki jednorazowe, powtarzalne lub raty kredytów. Komunikat o rozliczeniu wszystkich płatności wymaga rozliczenia również rat. Zapłacone pozycje obu rodzajów znajdziesz w **Opłaconych płatnościach**.

### Dodanie rachunku

W **Rachunkach i ratach → Dodaj zobowiązanie** podaj nazwę, kwotę, konto oraz kategorię. Wybierz:

- **Jednorazowy** — jedna data, np. konkretny zakup lub pojedyncza opłata.
- **Powtarzalny** — płatność miesięczna, kwartalna albo roczna, z miesiącem rozpoczęcia i opcjonalnym zakończeniem.

Można zaznaczyć szacunkową kwotę, wybrać finansowanie z rezerwy oraz wpisać promocję, kwotę po promocji i termin wypowiedzenia. Wstrzymany rachunek pozostaje w katalogu; sprawdź filtr wstrzymanych zobowiązań, jeśli go nie widzisz.

### Opłacenie bez duplikatu

Jeśli płatność nie jest jeszcze w historii, wybierz **Zapisz opłacenie**, podaj faktyczną datę i kwotę, sprawdź saldo i zatwierdź. To zapis ewidencyjny po płatności w banku.

Jeśli płatność już pochodzi z CSV lub ręcznego wpisu, wybierz znalezioną transakcję / **Powiąż płatność**. Aplikacja oznaczy rachunek jako rozliczony, zachowując jedną płatność i jedno obciążenie salda. Przykład: importowane ENEA 180 zł oraz plan ENEA 250 zł — powiąż istniejące 180 zł, zamiast dodawać drugie 180 zł.

Rachunek opłacony za mniej niż wspólny limit może zostawić nadwyżkę kategorii. Jeśli ta nadwyżka ma być odłożona na przyszłe faktury, zastosuj miesięczną pulę mediów, a nie drugi niezależny limit.

Gdy znaleziony wydatek ma inną kategorię, formularz może wymagać jej poprawienia przed powiązaniem. Gdy podobny wydatek nie dotyczy tego rachunku, osobną płatność trzeba świadomie potwierdzić.

### Raty

W szczegółach kredytu ustaw **konto i kategorię budżetową**. Każdy kredyt może korzystać z innego konta. Wspólne konto rat w ustawieniach jest domyślne tylko dla kredytów bez własnego przypisania.

Wybierz właściwy numer raty, datę i kwotę. Jeżeli ratę już importowano, powiąż istniejącą transakcję. Sprawdź konto także przy zapisywaniu raty z historii — potwierdzenie spłaty bez księgowania w budżecie nie jest obciążeniem bankowego konta w aplikacji. Jeśli już zapisano spłatę bez konta, skorzystaj z operacji jej zaksięgowania, zamiast potwierdzać ratę drugi raz.

Plan rat jest przypisany do identyfikatora kategorii, nie do samej nazwy „Rachunki”. Zmiana jej nazwy nie tworzy drugiego planu rat. Nie dodawaj równolegle tej samej raty jako osobnego cyklicznego rachunku.

### Błędne rozliczenie

Przy płatności wybierz **Cofnij rozliczenie** i przeczytaj podgląd skutków. Jeśli rozliczenie utworzyło nowy wydatek, cofnięcie usuwa jego obciążenie. Jeśli tylko powiązało wcześniej istniejący zakup, ten zakup pozostaje w historii i saldzie, a zwalniane jest powiązanie. To nie jest zapis zwrotu pieniędzy od sprzedawcy.

## 8. Rezerwy na przyszłe wydatki

Na karcie rezerwy od razu widać zgromadzoną kwotę, wykonanie planu miesiąca i kwotę jeszcze do odłożenia. **Odłóż środki** oraz **Zapisz płatność** pozostają na wierzchu. W **Szczegółach rezerwy** są opis, miejsca pieniędzy, zwolnienie środków, przeniesienie, historia i — w zarządzaniu — archiwizacja. Plan miesięczny i kwota brakująca do całego celu to osobne miary.

### Rezerwa z terminem, np. OC w lutym

W **Rezerwach i celach → Nowa rezerwa** podaj nazwę, przewidywany koszt, termin, konto i rodzaj: jednorazowo albo corocznie. Ubezpieczenie może mieć kategorię Transport → Ubezpieczenie/utrzymanie auta, a mieszkanie swoją podkategorię.

Rezerwa pokazuje odłożoną sumę, miejsca pieniędzy, brak do celu oraz potrzebne kolejne odłożenia. Jeśli do zebrania zostało 1200 zł i 6 odłożeń, średnia wynosi 200 zł. Mniejsza wpłata lub pominięty miesiąc zwiększa późniejszą potrzebną kwotę; większa wpłata ją zmniejsza. Dokładna liczba odłożeń wynika z dat cyklu, terminu i zapisanych wpłat, a nie wyłącznie z różnicy numerów miesięcy.

W **Planie miesiąca → Odłożenia i miesięczne pule** widoczny jest plan automatyczny lub zapisany własny plan oraz kwota jeszcze do odłożenia. Samo pojawienie się planu nie oznacza, że pieniądze już wydzielono. Własną kwotę odłożenia możesz zapisać dla bieżącego lub przyszłego miesiąca.

### „Odłóż”, „Przelej i odłóż” oraz „Zwolnij”

- **Odłóż środki** — wydziel pieniądze już znajdujące się na wskazanym koncie. Saldo zostaje, wolne środki maleją.
- **Przelej i odłóż** — zapisz wykonany przelew między własnymi kontami oraz zasilenie rezerwy. Zmieniają się salda dwóch kont i kwota przypisana do celu.
- **Zwolnij** — usuń przypisanie pieniędzy do celu. Stają się wolne; samo zwolnienie nie jest dochodem i nie przenosi pieniędzy w banku.
- **Zapisz płatność** — rozlicz faktyczny koszt z rezerwy, tworząc wydatek albo łącząc już istniejącą płatność.

Odłożenie obciąża budżet miesiąca jako przeznaczenie pieniędzy. Późniejsza płatność zużywa rezerwę, aby tej samej odłożonej części nie obciążyć ponownie jako nowego finansowania miesiąca. Nadal widać faktyczny wydatek bankowy.

Po płatności corocznej zaczyna się następny cykl. Domyślnie pozostałe środki zostają na cel, a przy rezerwie jednorazowej wracają do wolnych środków. Przed zapisem możesz zmienić przeznaczenie nadwyżki. Archiwizacja i rozliczenie są różnymi stanami — sprawdzaj zakładkę archiwum oraz kwoty rezerw przed uznaniem pieniędzy za wolne.

### Podgląd i potwierdzenie operacji

W formularzu odłożenia, zwolnienia lub płatności wybierz **Sprawdź podgląd**. Serwer sprawdza całą operację bez jej zapisywania. Podgląd pokazuje stan rezerwy, saldo każdego konta dotkniętego operacją oraz kwotę poza rezerwami przed i po. Drugi przycisk zatwierdza zapis. Zmiana kwoty, konta, daty lub przeznaczenia nadwyżki wymaga nowego podglądu. Gdy od czasu podglądu zmienią się salda albo rezerwy, odśwież go i sprawdź ponownie.

Po płatności pozostaje podsumowanie z przyciskiem **Pokaż transakcję**. Ten sam wynik można sprawdzić w historii rezerwy. Przykład: odłożono 382 zł, zapłacono 374,20 zł, zakończono jednorazowy cel — **7,80 zł wraca do wolnych środków**. Ta nadwyżka pozostaje na kontach i nie jest nowym dochodem. W transakcjach jest jeden wydatek 374,20 zł.

### Co zrobić z nadwyżką

Dla kosztu z terminem, gdy zapłacona kwota jest mniejsza od odłożonej, wybierz:

- **Zwolnij do wolnych środków** — usuwa przypisanie nadwyżki do celu, bez tworzenia wpływu bankowego.
- **Przenieś do innej rezerwy** — wybierz aktywny cel. Pieniądze pozostają na dotychczasowych kontach; nie powstaje kolejny koszt ani przelew. Przenoszona jest także odpowiadająca tej części podstawa budżetowa, żeby przyszła płatność nie obciążyła jej ponownie.
- **Zachowaj na kolejny cykl** — rezerwa coroczna otwiera następny cykl; jednorazowa wymaga wskazania nowego terminu. Niewykorzystane środki zostają w tej rezerwie.

Miesięczne pule mediów i rezerwy bez terminu pozostają aktywne i zachowują resztę środków. Możesz je zwolnić osobną operacją. Cofnięcie rozliczenia odwraca także przekazanie nadwyżki. Jeżeli od tego czasu zmieniono docelową rezerwę, najpierw rozlicz jej późniejsze operacje — aplikacja nie zabierze pieniędzy użytych już do innego celu.

### Jedna historia i zestawienie miesiąca

**Historia rezerwy** łączy odłożenia, płatności, zwolnienia, zmiany miejsca oraz cofnięcia rozliczeń. Przelew z odłożeniem jest jednym wpisem. Możesz filtrować rodzaj operacji i wybrany miesiąc albo pokazać całą historię. Link do rozliczonej rezerwy automatycznie otwiera właściwą kartę w **Rozliczonych i archiwum**.

Rozwiń **Zestawienie miesięczne rezerw** i wybierz miesiąc. Równanie jest następujące:

**Stan początkowy + odłożono/otrzymano − pokryto z rezerwy − zwolniono/przekazano = stan końcowy.**

Kwota faktycznie zapłaconych wydatków jest osobno, ponieważ faktura może przekraczać odłożoną sumę. Widać również plan, wykonanie i brakujące odłożenie dla wybranego miesiąca. Karty rezerw nadal pokazują aktualny stan. W pulach mediów osobno widać wpłaty i faktyczne płatności; finansowanie faktury z wcześniej odłożonych środków nie jest nową wpłatą.

### Zbiorcze odkładanie

Wybierz **Odłóż według planu** albo skrót w planie miesiąca. Propozycja obejmuje brakujące odłożenia bieżącego miesiąca według ustawionej ważności, osobno dla każdego konta. Przyszłe pule przed miesiącem startu nie są proponowane. Kwota jest ograniczona środkami poza rezerwami na danym koncie, ale te pieniądze mogą być potrzebne również na inne rachunki i limity — sprawdź je przed zatwierdzeniem.

Możesz zmienić konto i każdą kwotę; **0 zł pomija daną rezerwę**. Najpierw sprawdź podgląd, następnie wybierz **Zatwierdź odłożenia**. Nie powstaną przelewy bankowe ani zakupy. Cały zestaw zapisuje się razem; błąd dowolnej pozycji wycofuje wszystkie odłożenia. Ponowienie tego samego zapisu po problemie z połączeniem nie tworzy kolejnych wpłat.

### Rezerwa bez terminu

Wybierz **Bez terminu** i stałą miesięczną kwotę, także 0 zł. Nie ma obowiązkowego celu ani automatycznego zwiększania wpłaty po pominiętym miesiącu. Kwotę domyślną zmieniasz w edycji rezerwy. Możesz ręcznie odkładać dowolne kwoty; przy 0 zł brak odłożenia nie jest zaległą obowiązkową wpłatą.

Na karcie rezerwy oddzielone są **odłożone środki na cały cel** oraz **wykonanie planu miesiąca**. Cel z kwotą ma postęp zgromadzonej rezerwy; drugi pasek odnosi się wyłącznie do miesięcznego planu. Rezerwa bez celu nie dostaje sztucznego procentu oszczędności. Przy miesięcznej kwocie 0 zł pojawia się informacja o odkładaniu ręcznym. Wpłata ponad plan jest opisana kwotą; pasek nie wychodzi poza kartę. Dla mediów wykonanie miesięczne obejmuje płatności i odłożenia zgodnie z zasadą jednej puli.

## 9. Miesięczne pule na prąd i wodę

Miesięczna pula mediów służy kosztom, które chcesz finansować regularnie, choć faktury przychodzą później lub mają różną wysokość. Ma dedykowaną kategorię, domyślną miesięczną kwotę i możliwość ręcznej korekty konkretnego miesiąca.

### Początek odkładania — np. dopiero od listopada

W tworzeniu lub edycji miesięcznej puli wybierz **Początek odkładania**. Jest to miesiąc rozpoczęcia planu, również dla stałego odkładania bez terminu. Przykład: „Woda Listopad – Styczeń”, 140 zł miesięcznie, start **listopad 2026**. W październiku plan tej puli wynosi 0 zł, od listopada 140 zł. Prognoza zaczyna planować odłożenia w tym samym miesiącu.

Na karcie pojawia się miesiąc startu i skrót do korekty pierwszego miesiąca. Październikowy rachunek za wodę pozostaje październikowym wydatkiem, ale nie jest wykonaniem listopadowej puli. Sama zmiana początku nie przenosi pieniędzy i nie tworzy wpłaty. Istniejące rachunki i osobne limity nadal obowiązują.

Miesiąc początku można zmienić, dopóki pula nie ma własnych odłożeń, płatności ani transferów. Po zapisaniu takich operacji początek jest chroniony, aby nie zmieniać ich rozliczenia; dla nowego okresu utwórz osobną pulę. Kwotę domyślną nadal można zmieniać, a korektę miesiąca zapisać od miesiąca rozpoczęcia. Nazwa puli nie wyznacza automatycznie daty zakończenia.

### Prąd: pula 250 zł, faktura 180 zł

1. Utwórz pulę na prąd z kwotą domyślną 250 zł i osobną kategorią Prąd.
2. Rozlicz fakturę 180 zł w tej puli lub przez przypisany do niej rachunek; importowaną płatność powiąż.
3. Odłóż brakujące 70 zł na przyszłe rozliczenie.

Miesiąc wykorzysta pulę 250 zł: 180 zł płatności i 70 zł odłożenia. **Nie zapisuj dodatkowo 250 zł zwykłego limitu i 250 zł odłożenia jako dwóch niezależnych planów.**

Jeśli w miesiącu faktura wynosi 0 zł, nie zapisuj fikcyjnej płatności. Odłóż 250 zł. Pieniądze pozostaną na przyszłą fakturę. Jeśli ustalisz rzeczywisty koszt 230 zł, skoryguj pulę miesiąca do 230 zł; kolejne miesiące zachowają domyślne 250 zł.

### Woda: odkładanie według licznika, faktura kwartalna

Utwórz osobną pulę Woda. Domyślna kwota, np. 140 zł, służy planowaniu do przodu. Po odczycie licznika ręcznie popraw kwotę w aktualnym miesiącu. Aplikacja nie oblicza sama zużycia z licznika i nie przenosi kosztu na poprzedni okres zużycia.

Fakturę kwartalną rozlicz z tej samej puli/rezerwy. Już odłożone środki są jej finansowaniem. Faktura pozostaje faktycznym wydatkiem, a wykorzystanie rezerwy nie jest nowym dochodem. Sprawdź podgląd, ile pokryje rezerwa, a ile wymaga bieżących wolnych środków.

Dedykowana kategoria puli jest zarządzana przez plan rezerwy. Jej zwykły ręczny limit nie powinien nadpisywać korekty puli.

## 10. Przelewy między kontami i inwestycjami

W **Kontach** wybierz konto źródłowe, docelowe, kwotę, datę i opis. Zwykły własny przelew nie zmienia sumy pieniędzy ani miesięcznego dochodu i wydatków. Przykład: 300 zł z Konta głównego na Oszczędności — na pierwszym jest o 300 zł mniej, na drugim o 300 zł więcej.

Jeżeli przelew ma zasilić rezerwę, wskaż ją i operację odłożenia. Wtedy 300 zł jest przypisaniem pieniędzy do celu, a nie zakupem za 300 zł. Nie dodawaj dodatkowego wpływu na konto docelowe i wydatku na źródłowe.

**Przenieś na inne konto** może oznaczać także zmianę miejsca istniejącej rezerwy bez kolejnego przelewu. Jeśli pieniądze już fizycznie przeniosłeś i salda to uwzględniają, wybierz zmianę przypisania; jeśli dopiero księgujesz przelew w aplikacji, wybierz także zmianę sald.

Transfer budżet ↔ inwestycje łączy konto budżetowe z gotówką portfela. Wpłata do inwestycji opuszcza budżetowe konto, ale nie jest zakupem konsumpcyjnym. Zakup akcji to kolejna operacja wewnątrz portfela. Nie księguj tej samej wpłaty niezależnie po obu stronach.

## 11. Import bankowy, reguły i paragony

### Wyciąg bankowy CSV

1. Otwórz **Dodaj / Importuj → Wyciąg bankowy**.
2. Wskaż konto z wyciągu, wybierz CSV i sprawdź mapowanie daty, opisu, odbiorcy i kwoty.
3. Odpowiedz na pytanie **Czy saldo konta już uwzględnia te operacje?** Nie ma domyślnej odpowiedzi. **Tak** uzupełnia historię bez zmiany salda, **Nie** aktualizuje saldo nowymi operacjami. Przygotowanie importu wymaga tego wyboru.
4. Przygotuj podgląd. Sprawdź kategorie, duplikaty, przelewy własne, połączenia i błędy wierszy.
5. Popraw lub pomiń problematyczne pozycje i dopiero zatwierdź zapis.

Obsługiwane są CSV do 8 MB i maksymalnie 3000 operacji. Parser rozpoznaje typowe separatory oraz UTF-8, UTF-16 z oznaczeniem i Windows-1250. Różne banki mają różne kolumny — automatyczne mapowanie wymaga sprawdzenia.

Zapisany import można otworzyć z historii i sprawdzić wynik. Identyfikatory źródłowe i podobieństwo transakcji pomagają ograniczać duplikaty, ale nie zastępują przeglądu: dwie rzeczywiste płatności mogą mieć taką samą datę i kwotę.

Importowana płatność nie oznacza zawsze automatycznego rozliczenia każdego pasującego planu. Po imporcie przejrzyj proponowane powiązania rachunków i rat. Rozlicz istniejący wydatek, zamiast tworzyć następny.

### Reguły kategorii

W **Importach → Reguły** dodaj np. `ENEA → Rachunki › Prąd`. Wybierz pole dopasowania, sposób dopasowania, kategorię, ewentualne konto i priorytet. Możesz też przyjąć podpowiedź reguły po ręcznym przypisaniu wydatku.

Reguła kategorii mówi, jak klasyfikować płatność. Nie jest zleceniem bankowym i nie oznacza sama, że konkretny rachunek lub rata została już rozliczona. Zmiana reguły nie służy do automatycznego przepisywania całej dawnej historii; sprawdź i odśwież podgląd niezapisanego importu.

Reguły dla sklepu mogą przypisać cały zakup do Jedzenia. Gdy później dołączysz paragon, możesz zastąpić ogólną kategorię podziałem pozycji bez drugiego obciążenia konta.

### Reguły przelewów na rezerwy

Wybierz własne konto źródłowe, docelowe, rezerwę i jednoznaczną frazę z opisu, np. `rezerwa OC auta`. Sama fraza `BLIK` nie mówi, do jakiego celu odłożono pieniądze. Reguła ignoruje wielkość liter i polskie znaki przy szukaniu frazy.

Podgląd pokaże przelew własny oraz odłożenie. Jeśli importujesz obie strony przelewu, powiąż drugą stronę z już rozpoznanym transferem, zamiast tworzyć drugi przelew. Sprawdź też, czy na docelowym koncie są pieniądze pokrywające przypisanie do rezerwy.

### Paragon do już istniejącego zakupu

1. W **Transakcjach** otwórz szczegóły zakupu i wybierz **Dołącz lub rozlicz paragon**, albo otwórz **Importy i paragony → Paragony**.
2. Wgraj zdjęcie lub PDF. Dostępne są JPG, PNG, WebP i PDF do 8 MB; PDF do 3 stron.
3. Porównaj oryginał z odczytanymi nazwami, datą, sumą, rabatami i kaucją. Lokalny OCR na Windows przygotowuje propozycję, nie zatwierdzone dane.
4. Kliknij **Znajdź zakup** i wybierz istniejącą płatność na właściwym koncie. Jeśli otworzyłeś paragon z konkretnego zakupu, sprawdź to powiązanie.
5. Zachowaj kategorie, przypisz cały zakup do jednej albo podziel pozycje. Suma podziału musi odpowiadać całej płatności, włącznie z płatną kaucją.
6. Zapisz. Dołączenie zdjęcia i podziału do istniejącej płatności nie tworzą drugiego wydatku ani kolejnego obciążenia salda.

### Paragon jako nowy zakup

Wybierz **Nowy, odrębny wydatek** i odpowiedz na **Czy saldo konta już uwzględnia ten zakup?** Nie ma domyślnej odpowiedzi. **Tak** uzupełnia historię bez zmiany salda, **Nie** pomniejsza saldo o zakup. Podgląd pokazuje kwotę przed zapisem i po nim. Powiązanie z istniejącą transakcją zachowuje jedno obciążenie bez dodatkowego wyboru. Gdy znaleziono podobne zakupy, osobny zakup wymaga potwierdzenia.

Przy słabym odczycie popraw dane ręcznie lub odczytaj ponownie. Powtórny odczyt może zastąpić poprawiony formularz — sprawdź komunikat. Bez działającego OCR nadal można uzupełnić paragon ręcznie.

### Usunięcie paragonu

W edytorze wybierz **Usuń paragon** i przeczytaj potwierdzenie. Usuwane są dane/załącznik paragonu; zapisany zakup i jego saldo nie są automatycznie usuwane. Jeżeli błędny jest sam zakup, popraw lub usuń go osobno w historii, uwzględniając jego powiązania.

## 12. Zwroty zakupów

Otwórz szczegóły pierwotnego wydatku i wybierz **Zapisz zwrot**. Wskaż kwotę, datę, konto otrzymania i kategorię lub pozycje. Możesz rozliczyć zwrot częściowy. Jeżeli zwrot jest już w historii, użyj dostępnego powiązania zamiast ponownego dopisywania pieniędzy.

Zwrot zmniejsza wydatki, a nie udaje nowej pensji. Zakup 200 zł i zwrot 50 zł daje 150 zł wydatków po zwrotach. Jeśli zakup był w poprzednim miesiącu, zwrot pomniejsza wydatki miesiąca otrzymania, z zachowaniem powiązania z zakupem.

Dodatnia płatność z banku nie zawsze jest rozpoznana jako zwrot sama z siebie. Sprawdź jej rodzaj i połączenie z zakupem, zanim uznasz ją za dochód. Przy rozliczeniu zakupu finansowanego rachunkiem, ratą lub rezerwą zachowaj istniejące powiązania i sprawdź podgląd.

## 13. Podsumowanie i tempo wydatków

### Co znaczą główne kwoty

Podsumowanie wyróżnia **Wolne z dochodów miesiąca**, **Wydano w miesiącu** i **Poza rezerwami na koniec miesiąca**. Nagłówek planu pokazuje ten sam bilans dochodów miesiąca. Dzisiejsze saldo, rezerwy i kwota poza rezerwami są w osobnym pasku „Stan dzisiaj”, niezależnym od wybranego miesiąca.

| Kwota | Interpretacja |
|---|---|
| Wydano w miesiącu | Faktycznie zapisane zakupy i płatności od początku wybranego miesiąca do dziś, po zwrotach |
| Pozostałe zobowiązania | Rachunki i raty jeszcze do opłacenia/rozliczenia |
| Przewidywane saldo na koniec miesiąca | Symulacja salda wszystkich kont na ostatni dzień wybranego miesiąca; osobno widać kwotę poza rezerwami. Dla miesiąca poza zakresem prognozy nie pokazujemy zmyślonego salda |
| Do rozdysponowania w planie | Pieniądze pozostałe po uwzględnieniu sald, oczekiwanych wpływów miesiąca, pozostałych limitów i zobowiązań oraz rezerw i brakujących odłożeń |
| Wolne z dochodów miesiąca | Nadwyżka wyłącznie otrzymanych i oczekiwanych dochodów miesiąca ponad jego finansowane koszty i pozostały plan; bez wcześniejszych sald |
| Do następnej wypłaty | Wynik symulacji do następnego planowanego wpływu; sprawdź też najniższy punkt po drodze |

Przykład „Do rozdysponowania w planie”: bieżące saldo 3000 zł + oczekiwane wpływy 1000 zł − rezerwy 500 zł − pozostały plan i zobowiązania 1500 zł − dodatkowe brakujące odłożenia 200 zł = 1800 zł. Wykonane płatności są już w saldzie; nie odejmujemy ich ponownie.

Przykład „Wolne z przychodów”: dochody miesiąca 6000 zł, finansowane koszty miesiąca 2000 zł, plan pozostały 3000 zł — wolne z tych dochodów 1000 zł, niezależnie od oszczędności z poprzednich miesięcy. Finansowane koszty uwzględniają również nowe przeznaczenie pieniędzy na rezerwy i transfery do inwestycji, z rozliczeniem wykorzystanych rezerw.

Dla przyszłego miesiąca pomocniczy bilans na dzisiejszych saldach może zawyżać wrażenie dostępnej kwoty: nie odejmuje niewykonanego planu miesięcy przed nim. Jest dostępny w objaśnieniu, a nie jako główna wolna kwota. „Dlaczego plan i prognoza pokazują różne kwoty?” rozdziela dzisiejsze środki poza rezerwami, zmianę przed początkiem miesiąca, jego bilans dochodów i różnicę założeń prognozy. Ta ostatnia może obejmować szacunkowe limity i inny harmonogram finansowania rezerw; sprawdź założenia zamiast traktować wynik jako gwarantowane pieniądze.

**Saldo na koniec miesiąca nie musi równać się wolnej kwocie do zaplanowania.** Saldo zawiera rezerwy, a wolna kwota odejmuje także pozostałe przeznaczenia pieniędzy. Dodatnia suma wszystkich kont nie gwarantuje środków na koncie konkretnej płatności.

Plan nie traktuje dodatkowego odłożenia na rezerwę z limitem 0 zł jako wykonania innej rezerwy. Wykonanie do wysokości planu, brakujące odłożenia i dodatkowe kwoty pokazuje oddzielnie.

### Tempo wybranych kategorii

Wskaźnik porównuje zwykłe zakupy po zwrotach z równomiernie rozłożonym planem dni miesiąca. Jeśli w 10. dniu wydałeś kwotę odpowiadającą 15. dniowi planu, pokazuje około 5 dni przed planem. To orientacyjny wskaźnik, a nie informacja o pięciu konkretnych przyszłych dniach bez pieniędzy.

Powiązane rachunki, raty, płatności z rezerw i miesięczne pule mediów nie przyspieszają tego wskaźnika. Czynsz opłacony wcześniej jest wykonaniem stałego zobowiązania. Przy niepowiązanym imporcie najpierw prawidłowo rozlicz płatność.

W edycji kategorii wyłącz z tempa np. Paliwo, jeśli tankujesz jednorazowo za cały miesięczny limit. Z tempa wypadają jej wydatki i limit, lecz nadal pozostają w pełnym budżecie, saldzie i prognozie. Wyłączenie rodzica obejmuje podkategorie. Dla wyłączanej podkategorii ustaw osobny limit, aby jego część dało się odjąć od wspólnego planu.

Wykres można przełączyć między codziennymi wydatkami, faktycznymi płatnościami i obciążeniem budżetu z odłożeniami. Nazwy serii w legendzie pozwalają je ukrywać; tabela danych pokazuje kwoty. Nie porównuj sum z różnych miar jak identycznych wartości.

### Kolejka spraw i wykonanie odłożeń

W **Podsumowaniu** jest jedna lista **Do zrobienia**, domyślnie z trzema najpilniejszymi sprawami. Rozwiń wszystkie albo wybierz rodzaj spraw. Dopasowanie istniejącej płatności zastępuje zwykłe przypomnienie o tym samym rachunku lub rezerwie. Lista łączy płatności i plan wybranego miesiąca z dokumentami oczekującymi na sprawdzenie także z innych miesięcy; szczegóły zakresu są rozwijane pod listą. Link otwiera odpowiednią sekcję lub dokument. Kolejka sama nie księguje żadnej operacji.

W planie rezerw **Wykonano plan** jest sumą pokrycia każdego celu do wysokości jego miesięcznej kwoty. **Dodatkowe wpłaty** pokazują nadwyżki oddzielnie. Przykład: plan OC 100 zł i serwis 100 zł, wpłata na OC 150 zł i serwis 0 zł. Wykonano 100 zł z 200 zł, dodatkowo odłożono 50 zł, a na serwis nadal brakuje 100 zł. Nadwyżka jednego celu nie wypełnia automatycznie innego.

## 14. Prognoza pieniędzy

Prognoza zaczyna się od aktualnego salda kont w PLN i pokazuje kolejne 365 dni, w tym podsumowania 30/90/365 dni. Uwzględnia spodziewane dochody, rachunki, raty, zwykłe wydatki, odłożenia, planowane koszty rezerw i wpłaty na cele inwestycyjne. Nie zakłada wzrostu cen inwestycji. Ewentualne wypłaty obligacji są przepływem budżetowym tylko przy zaplanowanym transferze na wskazane konto.

### Skąd bierze limity

Każda kategoria ma następującą kolejność: **własny limit miesiąca → obowiązujący limit domyślny → oznaczony szacunek z bieżącego miesiąca**. 0 zł jest zapisanym limitem i nie zostaje zastąpione inną kwotą.

Brak przyszłego planu jednej kategorii nie usuwa planów innych. Jednocześnie dawny szacunkowy limit podkategorii nie podwyższa świadomie ustawionego wspólnego limitu jej rodzica. Prawdziwie zapisane limity podkategorii nadal są uwzględniane według zasad wspólnej puli.

Przyszłe szacunki nie tworzą zapisanych planów w bazie. Dlatego prognoza może zakładać wydatek, którego przyszły plan miesiąca jeszcze nie ma. Żeby oba widoki miały stałą wspólną podstawę, ustaw plan domyślny albo zapisz/kopiuj limity miesiąca.

### Jak czytać wynik

Prognoza ma cztery widoki: **Wykres i saldo**, **Kalendarz**, **Założenia** oraz **Dochody**. Przełączenie widoku zachowuje wybrany zakres i wariant. Nie dopisuje operacji do historii. W Założeniach zobaczysz źródła planów i ewentualne szacunki, a w Dochodach rozliczysz oczekiwany wpływ.

Bezpośrednio nad wykresem wybierz **Zakres prognozy**: 30 dni, 3 miesiące (90 dni) albo 12 miesięcy (365 dni). Ten sam zakres można wybrać kafelkiem salda u góry. Oba wybory są zsynchronizowane i aktualizują wykres, najniższe saldo, przepływy, tabelę kont oraz kalendarz. Daty początku i końca widać przy wykresie. Przełączenie zakresu zachowuje wybrane konto i wariant symulacji.

W **Planie użytym w prognozie** rozwiń miesiąc. Zobaczysz źródło każdego limitu i kwoty pozostałych przepływów. Pierwszy oraz ostatni miesiąc mogą obejmować tylko część dni; pełny limit miesiąca i część w zakresie prognozy są osobno wyjaśnione.

Zwykłe wydatki są rozkładane na pozostałe dni. W bieżącym miesiącu pomniejszają je już zapisane zakupy, liczone w ramach odpowiedniej kategorii. Rachunki i raty mają konkretne daty i są wyłączane z codziennej części limitu. Dzisiaj wymagalne oraz zaległe zobowiązania bieżącego miesiąca są symulowane od jutra. Starsze nierozliczone raty wymagają sprawdzenia historii.

Odłożenie na rezerwę zmniejsza prognozowane wolne środki, a płatność z rezerwy zmniejsza saldo i zużywa odłożenie. Z tego powodu linia salda oraz linia pieniędzy poza rezerwami mogą się różnić.

Sprawdź nie tylko saldo końcowe, lecz również **najniższe saldo, okresy niedoboru oraz każde konto osobno**. Dodatni wynik końcowy może poprzedzać kilkudniowy niedobór. Kafelki podają pierwsze dwa przedziały braku i liczbę pozostałych; daty przepływów sprawdzisz w kalendarzu. Rozwiń salda poszczególnych kont — suma środków może wystarczać, mimo braku na konkretnym koncie płatności. Sugestia przelewu nie wykonuje go. Codzienne wydatki trafiają w symulacji na skonfigurowane konto codziennych wydatków, a raty na konta przypisane kredytom.

### Własny wariant

Wybierz **Założenia**. Możesz zmienić procent planowanych dochodów, miesięczną kwotę codziennych wydatków, bufor lub wyłączyć wybrane źródła. Scenariusz nie zmienia zapisanych planów ani sald. Własna kwota codziennych wydatków nie powinna ponownie zawierać osobno liczonych rachunków, rat i rezerw.

Wariant ostrożny zmniejsza planowane dochody o 20% i zwiększa codzienny limit o 20%; nie podwyższa automatycznie rat ani rachunków. Nie zakładamy z góry nieznanych przyszłych nadwyżek limitów jako dodatkowych pieniędzy.

## 15. Zamknięcie miesiąca

Zasady niewykorzystanych limitów ustaw w **Ustawieniach → Koniec miesiąca** dla kategorii głównej razem z podkategoriami:

- zacznij następny miesiąc od nowa;
- przenieś niewykorzystany limit;
- zdecyduj przy zamknięciu;
- zawsze odłóż na wskazaną rezerwę.

Przeniesienie limitu jest zmianą planu, nie dochodem i nie przelewem. Przekroczenie nie tworzy dodatniej nadwyżki. Zasada „Zdecyduję” nie przenosi pieniędzy automatycznie przed zatwierdzeniem.

Po zakończeniu miesiąca wybierz go w **Planie miesiąca** i kliknij **Rozlicz miesiąc**. Przejrzyj salda porównane z bankiem, różnice, nierozliczone rachunki i raty, brakujące odłożenia oraz zakupy bez kategorii. Zamknąć można miesiąc wcześniejszy od aktualnego.

Dla wymagających decyzji dodatnich nadwyżek wybierz: limit kolejnego miesiąca, oszczędności, środki na inwestycje, konkretną rezerwę albo pozostawienie wolnych środków. Wskazanie oszczędności/inwestycji wydziela rezerwę bez terminu na wybranym koncie. Nie wykonuje bankowego przelewu ani zakupu instrumentów.

Zatwierdzenie sprawdza aktualność kwot i dostępność pieniędzy. Zapisane decyzje są zachowywane. Późniejsza zmiana polityki kategorii nie dokłada drugi raz tej samej nadwyżki do kolejnego miesiąca. Jeśli później poprawisz transakcje, widok kontroli pokaże różnice wobec zamknięcia; nie przepisze po cichu zatwierdzonej decyzji.

Zamknięcie nie opłaca automatycznie brakujących rachunków i nie zastępuje bankowej kontroli sald.

## 16. Codzienna i miesięczna rutyna

### Po zakupie lub płatności

1. Sprawdź, czy płatność już jest w historii.
2. Dodaj albo powiąż ją raz, wybierając właściwe konto i wpływ na saldo.
3. Przypisz kategorię; jeśli masz paragon, dołącz go do tego samego zakupu.
4. Rozlicz powiązany rachunek, ratę lub rezerwę.

### Raz w tygodniu

Porównaj salda kont, przejrzyj wpisy bez kategorii i proponowane powiązania. Sprawdź najbliższe płatności, brakujące odłożenia i prognozę każdego konta. Dopiero potem oceń tempo codziennych wydatków.

### Na początku miesiąca

Sprawdź domyślne limity, ustaw wyjątkowe wydatki, popraw dochody i terminy oraz skoryguj miesięczne pule prądu/wody. Nie trzeba kopiować płatności wykonanych w poprzednim miesiącu.

### Po zakończeniu miesiąca

Uzupełnij transakcje i zwroty, porównaj salda, rozlicz zobowiązania, zdecyduj o niewykorzystanych limitach i zapisz zamknięcie. Przejrzyj raport miesięczny oraz przyszły plan.

## 17. Najczęstsze pytania i pomyłki

| Objaw lub pytanie | Co sprawdzić |
|---|---|
| Dodałem paragon, ale saldo nie spadło | Czy dołączono go do istniejącej płatności albo wybrano tryb Historii? Nie twórz od razu następnego zakupu |
| Rachunek opłacony w banku nadal jest oczekujący | Powiąż istniejącą płatność z właściwym miesiącem rachunku |
| Rata nie zmieniła salda | Sprawdź konto i sposób księgowania w szczegółach zapisanej raty |
| Wydatek nie ma zwykłego ołówka | Może być rozliczeniem rachunku, kredytu lub rezerwy. Sprawdź operację cofnięcia rozliczenia |
| Wszystkie konta razem mają pieniądze, a prognoza ostrzega | Na koncie konkretnej płatności może być za mało pieniędzy |
| Rezerwa pokazuje plan, ale nie ma odłożonych środków | Plan nie jest wykonaniem. Zapisz rzeczywiste odłożenie |
| Przelew na oszczędności podwoił wydatki | Sprawdź, czy zapisano transfer i dodatkowy zwykły wydatek dla tej samej operacji |
| Tempo wygląda źle po tankowaniu | Wyłącz Paliwo z tempa i przypisz mu osobny limit; pełny budżet nadal je uwzględni |
| Prognoza ma inne założenia niż pusty przyszły plan | Rozwiń źródła limitów; szacunek nie jest zapisanym limitem. Ustaw plan domyślny |
| Zmiana planu domyślnego nie zmienia danego miesiąca | Miesiąc ma własny wpis, także z kopiowania. Wyjątek ma pierwszeństwo |
| Wpisane 0 zł nie usuwa wszystkich kosztów kategorii | Nie kasuje przypisanych rachunków, rat ani osobnych planów podkategorii |
| Po korekcie danych zmieniły się sumy zamkniętego miesiąca | Kontrola pokazuje różnicę, a zatwierdzone decyzje zamknięcia pozostają zachowane |
| Komunikat o nieaktualnych danych lub konflikcie | Odśwież podgląd. Przed ponowieniem sprawdź historię; poprzedni zapis mógł już się udać |

Jeśli kwota nadal się nie zgadza, zanotuj miesiąc, konto, nazwę operacji, oczekiwaną kwotę i sposób jej zapisu. [Instrukcja kopii i diagnostyki](URUCHAMIANIE_I_KOPIE_PL.md) opisuje, gdzie sprawdzić logi i jak zachować bazę przed naprawą.
