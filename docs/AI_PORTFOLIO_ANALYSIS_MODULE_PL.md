# Inwestycje: asystent, plan udziałów i materiały

Stan: 22 października 2026. Przykłady są fikcyjne. Funkcje analityczne nie księgują transakcji i nie wysyłają zleceń do brokera.

## Nawigacja

Portfel akcyjny ma pięć głównych sekcji: **Przegląd**, **Wyniki**, **Ryzyko i struktura**, **Historia i strategie**, **Asystent**. W historii są transakcje, strategie, archiwum, sprzedaże i cykle pozycji. Ryzyko i struktura zawiera także dywidendy, plan udziałów i wnętrze ETF. PPK, obligacje i oszczędności zachowują własne podsumowania; opis założeń znajduje się przy asystencie.

Przegląd pokazuje najwyżej trzy sprawy dotyczące wyceny i założeń. Zwijana sekcja materiałów zawiera Twoje zapisane analizy oraz potwierdzone szkice do posiadanych spółek.

## Asystent krok po kroku

1. Wybierz okres wyników i czy uwzględniasz podportfele. Wyłączenie podportfeli usuwa ich pozycje, gotówkę i operacje z zakresu. Bieżące pozycje pokazują obecny stan, nawet przy analizie dawnego okresu wyników.
2. Sprawdź czas przygotowania danych, ostrzeżenia oraz **Dane i źródła przekazywane do analizy**. Pozycje zawierają daty ceny i FX, jeśli są dostępne, oraz oznaczenie podstawy wyceny.
3. **Zapisz podsumowanie danych** działa lokalnie, bez klucza AI. Pokazuje obliczone wyniki, przepływy, wkład instrumentów i ograniczenia.
4. Wpisz pytanie i kliknij **Analizuj z AI**. Dopiero ten przycisk wysyła dane z podglądu oraz pytanie do Google Gemini. Otwieranie widoku i czytanie dawnych rozmów nie wysyłają danych do AI.
5. Odpowiedź ma sekcje: co się zmieniło, dlaczego, co sprawdzić, źródła i braki. Akapity wskazują źródła w aplikacji. Nieznany identyfikator źródła jest odrzucany; prawidłowy odnośnik nie gwarantuje poprawnej interpretacji modelu.
6. Dopytania korzystają z tej samej zapisanej kopii danych. **Nowy przegląd** pobiera aktualny stan. Późniejsze importy i notowania nie przepisują dawnych rozmów.
7. **Zapisz w dzienniku** tworzy jeden wpis obserwacji. Ponowienie nie tworzy duplikatu. W dzienniku możesz dopisać wnioski i termin przeglądu.

Kontekst obejmuje wspólną wycenę, rzeczywiste wyniki okresu, wkład instrumentów, założenia, do 20 aktywnych wpisów dziennika i do 20 przypisanych materiałów. Dla ETF obejmuje również znany skład i ograniczenia. Poprzedni przegląd jest kontekstem porównawczym przy zgodnym zakresie podportfeli. Różnica wartości aktywów obejmuje przepływy i nie oznacza samego zysku.

PPK rozróżnia wartość jednostek, wynik inwestowania i szacowany zwrot. Obligacje korzystają z modelu obligacji aplikacji, a oszczędności z wartości konta i naliczanych odsetek. Brak ceny lub FX pozostaje brakiem danych. Cena zakupu nie zastępuje notowania; ręczne i stare ceny zachowują oznaczenie jakości.

## Konfiguracja, ponowienia i koszty AI

Zainstaluj `backend/requirements.txt`, ustaw `GEMINI_API_KEY` w `backend/.env` i uruchom ponownie backend. Klucz pozostaje na serwerze. Domyślny model to `gemini-3.1-flash-lite`; `GEMINI_MODEL` zmienia domyślną wartość przed pierwszym zapisem ustawień. Ustawienia zapisane w formularzu mają pierwszeństwo.

W **Ustawieniach AI i limicie kosztów** wybierasz model, dzienny limit USD, stawki za milion tokenów oraz długość odpowiedzi. Limit 0 blokuje generowanie. Limit jest wspólny dla materiałów i portfeli, a dzień rozliczany według UTC. Przed generowaniem aplikacja liczy tokeny u dostawcy i atomowo rezerwuje szacowany koszt wejścia oraz maksymalnej odpowiedzi. Po wykonaniu zapisuje zgłoszone zużycie. Jednoczesne żądania uwzględniają rezerwacje innych żądań.

To **limit szacowany tej aplikacji**, a nie blokada rachunku Google. Taryfa może zależeć od modelu i rodzaju wejścia, zwłaszcza dźwięku/wideo. Sprawdź [cennik Google](https://ai.google.dev/gemini-api/docs/pricing) i ustaw konserwatywną stawkę dla używanych mediów. Limit nie obejmuje innych aplikacji, podatków ani przeliczenia waluty rachunku.

Identyfikator żądania chroni przed powtórnym wykonaniem; zmieniona treść z tym samym identyfikatorem jest odrzucana. Niepewny błąd dostawcy zachowuje rezerwację kosztu i nie uruchamia automatycznej płatnej próby. **Przygotuj nowe żądanie** nadaje nowy identyfikator; kolejna próba może być płatna. Gdy proces przerwano w trakcie wywołania, rozpocznij nowy przegląd. Pusta rozmowa po nieudanej pierwszej odpowiedzi nadal zachowuje stan wejściowy.

## Plan udziałów i dopłata

W **Ryzyko i struktura → Plan udziałów** zapisz cel, horyzont i ograniczenia. Plan może dotyczyć instrumentów z gotówką (`CASH`) albo, na głównym koncie z aktywnymi podportfelami, strategii i części głównej (`OWN`). Udziały sumują się do 100%. Opis może istnieć bez udziałów. Plan archiwalnej strategii nie jest edytowalny.

Po zapisaniu planu wpisz kwotę i wybierz **Oblicz podział**. Symulacja ustala udziały po dopłacie, a nową wpłatę rozdziela proporcjonalnie do braków niedoważonych pozycji. Nie proponuje sprzedaży i nie wydaje obecnej gotówki. Niewykorzystana część pozostaje w gotówce/części głównej. Podział groszy zachowuje sumę wpłaty.

Wynik pokazuje kwoty, nie liczbę akcji. Nie obejmuje prowizji, podatków ani całych jednostek zakupu. Niepełna wycena blokuje obliczenia, stare dostępne ceny powodują ostrzeżenie. Samą nową wpłatą nie zawsze można osiągnąć plan.

## Wewnątrz ETF

Sekcja łączy bezpośrednie akcje i zapisany skład funduszy. Filtr pokazuje spółki występujące przez więcej niż jeden instrument. Udziały dotyczą wycenionych pozycji, bez gotówki.

Skład można pobrać z Yahoo albo wpisać z dokumentu emitenta: ticker funduszu, link HTTPS, data składu oraz wiersze `TICKER;udział procentowy`, np. `ABC;6,25`. Zapis zastępuje poprzedni skład. Suma poniżej 100% jest dozwolona; reszta pozostaje nierozpoznana. Powtórzenia i suma powyżej 100% są odrzucane.

Yahoo często podaje tylko największe pozycje. Data pobrania nie oznacza daty składu. Brak daty lub skład starszy niż 90 dni wywołują ostrzeżenie. Fundusze rozpoznajemy po nazwie, sektorze albo zapisanym składzie; nierozpoznany fundusz należy uzupełnić. Łączone są identyczne tickery, bez zgadywania odpowiedników giełdowych. Rozwijany jest jeden poziom składu. Skład nie służy do liczenia historycznych stóp zwrotu.

HHI ma nazwę **Rozproszenie instrumentów**. Jeden ETF może zawierać wiele spółek, więc ten wskaźnik nie ocenia dywersyfikacji wewnątrz ETF.

## Materiały autorów: artykuły i tekst źródłowy

**Pomysły inwestycyjne** domyślnie pokazują artykuły Inwestomatu i Comparic. Filmy Marcina Podlackiego i Zawodu Inwestor pozostają pod filtrem **Filmy**. Odświeżanie pobiera ostatnie publikacje z kanałów, nie całe archiwum. Starszy materiał można dodać linkiem z właściwym źródłem i datą.

1. Wybierz **Analizuj treść**. Dla artykułu kliknij **Pobierz treść artykułu** i sprawdź podgląd oraz datę pobrania. Odczytywany jest publiczny tekst ze wspieranych domen, bez obchodzenia logowania i płatnego dostępu. Jeśli pobranie się nie uda, wklej dostępny fragment.
2. Tekst dłuższy niż 60 000 znaków jest skracany z widocznym ostrzeżeniem. Analiza dotyczy wyłącznie przekazanej części. Tytuł i opis z RSS nie wystarczają do przypisania opinii autora.
3. **Przygotuj szkic AI** przesyła tekst z podglądu do Gemini. Film można analizować jako publiczne wideo lub wkleić transkrypcję. Dostępność filmu zależy od dostawcy. Opis wypowiedzi z filmu jest parafrazą AI z proponowanym momentem, nie zweryfikowanym cytatem.
4. Sprawdź ticker, osobę wypowiadającą się, opinię, fragment, tezę, ryzyka i horyzont. Dopasowanie fragmentu do tekstu potwierdza tylko obecność słów, nie interpretację.
5. Zaznacz **Sprawdziłem źródło, ticker i przypisanie opinii** i zapisz. Dopiero wtedy powstaje analiza spółki. Gdy analiza danej spółki w materiale już istnieje, edytuj ją zamiast tworzyć drugi wpis.

Wzmianka, obserwacja, deklaracja posiadania, zakupu i sprzedaży są osobnymi typami. Wypowiedź gościa nie jest automatycznie opinią prowadzącego. Szkice nie tworzą transakcji ani automatycznych rekomendacji. Materiały i transkrypcje są niezaufanymi danymi, a nie instrukcjami dla asystenta.

## Dane, API i testy

Nowe tabele są addytywne: `investment_ai_settings`, `investment_ai_runs`, `investment_ai_sessions`, `investment_ai_messages`, `investment_strategy_plans`, `investment_fund_compositions`, `investment_material_reviews`, `investment_material_confirmations`, `research_publication_text`. Rozmowy, stan danych, teksty i koszty pozostają w bazie i lokalnych kopiach.

- `/api/ai/context/<pid>`, `/sessions/<pid>`, `/session/<sid>`: podgląd i historia.
- `/api/ai/portfolio-analysis`: POST z `portfolio_id`, `request_id` UUID, `question`, `mode` (`data`/`ai`), `include_subportfolios`, `from`, `to`. Dopytanie dodaje `session_id` i `expected_last_id`.
- `/api/ai/messages/<mid>/journal`: idempotentny zapis do dziennika. `/api/ai/settings`: wersjonowane ustawienia GET/PUT.
- `/api/investment-analysis/plans/<pid>` i `/simulate`: plan i symulacja.
- `/api/investment-analysis/exposure/<pid>`, `/funds/<ticker>`, `/funds/<ticker>/refresh`: ekspozycja i skład.
- `/api/investment-analysis/materials/<pid>` oraz `/text`, `/analyze`: publikacje i odczyty. `/material-reviews/<rid>/<index>/confirm`: potwierdzenie. `/related/<pid>`: materiały posiadanych spółek.

Odpowiedzi używają standardowej koperty API. Integracja używa `google-genai` zamiast `google-generativeai`. Testy zastępują model atrapą; nie przesyłają danych użytkownika. Archiwum strategii zachowuje zamrożony wynik i nie jest dostępne dla nowego przeglądu AI.
