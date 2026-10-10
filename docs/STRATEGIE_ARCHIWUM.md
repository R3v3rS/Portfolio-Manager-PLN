# Archiwizacja strategii

W widoku aktywnego podkonta wybierz „Archiwizuj i przenieś środki”. Po potwierdzeniu wszystkie akcje i gotówka zostają przesunięte do części głównej tego samego portfela.

Historia transakcji pozostaje przypisana do strategii. Dopisywane są tylko powiązane wpisy przesunięcia akcji i gotówki. Nie powstaje sprzedaż u brokera, nowy dochód ani nowa wpłata na IKE. Pierwotne koszty zakupu są zachowane.

Archiwum przechowuje końcowe podsumowanie, historię miesięczną, dzienną oraz raport wyników. Zmiana późniejszych notowań nie zmienia zapisanego wyniku archiwalnego. Kwoty w archiwum oznaczają stan przy zamknięciu, a nie dodatkowe aktywa. Główne IKE uwzględnia historyczne operacje zamkniętej strategii przy liczeniu całego wyniku, ale środki są już w części głównej.

Archiwalne strategie można wyświetlić przez opcję archiwum na liście portfeli. Nie można ponownie przesunąć ich środków ani zmienić przypisania ich transakcji.

Przy braku ceny jednej z pozycji należy wpisać cenę ręcznie przed archiwizacją. Ujemną gotówkę trzeba wcześniej rozliczyć. Operacja jest atomowa: błąd wycofuje przesunięcia i zapis archiwum. Ponowne wywołanie nie powtarza transferu.

Kopia bazy przed wprowadzeniem tej funkcji: `backend/backups/before-strategy-archive-20261010-182106.db`.

Sprawdzono 26 testów backendu oraz 12 testów frontendu; dwa wcześniejsze testy frontendu są oznaczone jako pomijane. Kontrola TypeScript i budowanie frontendu zakończone poprawnie. W obecnej bazie nie zamykano żadnej nowej strategii w ramach sprawdzania funkcji.
