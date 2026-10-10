# Analizy inwestycji, plan miesiąca i kopie bazy

## Inwestycje

Przeniesienie akcji jest przepływem kapitału między strategiami. Wkład instrumentu i miesięczne stopy uwzględniają ASSET_IN / ASSET_OUT. W obrębie głównego portfela sparowane przeniesienia znoszą się i nie tworzą zysku.

W zakładce „Wyniki” jeden okres steruje podsumowaniem, wykresami, tabelą miesięcy, wkładem instrumentów i osią wydarzeń. Można podać własne daty. Zysk na wykresie narasta od początku wybranego okresu, a nie od początku rachunku. Miesiące mają przełącznik wykres / mapa / tabela.

Procentowy benchmark pokazuje zmianę ceny w PLN w tym samym okresie; uwzględnia historyczne kursy walut. Nie doliczamy ponownie dywidend do zapisanych cen. Miesięczny Modified Dietz portfela pozostaje przybliżeniem, nie dokładnym TWR. Porównanie inflacji jest dostępne na wykresie wartości wpłat.

Oś wydarzeń obejmuje operacje i wpisy dziennika. Znaczniki grupują wydarzenia miesięcznie. Kliknięcie instrumentu otwiera całą historię zakupów, sprzedaży, dywidend i transferów oraz wynik i pozostałą liczbę jednostek. Dotyczy również sprzedanych instrumentów.

„Sprzedaże i cykle” łączy widok według spółki i według cyklu posiadania. „Strategie i archiwum” porównuje kapitał startowy, późniejsze wpłaty, okres działania i wynik. Zamrożone archiwalne kwoty nie są ponownie doliczane do majątku. Dawne archiwa bez zapisanego raportu pokazują brak wyceny zamiast pozornego zera.

## Budżet

W „Planie miesiąca” można rozwinąć grupę zobowiązań i rozliczyć rachunek bez przechodzenia do osobnego katalogu. Podgląd rozdziela rachunki, raty, limity kategorii i odłożenia. Płatność wyjaśnia, że rozlicza istniejący plan, oraz czy tworzy nowy wydatek czy wiąże istniejącą transakcję. Finansowanie rezerwą pozostaje oznaczone.

Nadwyżka wykonania w jednej rezerwie lub kategorii nie pokrywa automatycznie braku w innej. Dlatego „Pozostało” jest sumą braków poszczególnych pozycji, a nie zawsze różnicą dwóch zbiorczych kolumn.

## Kopie i przywracanie

Panel: Centrum narzędzi → Kopie bezpieczeństwa.

- Kopia przed uruchomieniem zmienionej wersji kodu, również przed migracją schematu.
- Codzienna kopia przy pierwszym użyciu aplikacji danego dnia; aplikacja musi być uruchomiona.
- Rotacja: 14 kopii codziennych i 10 kopii aktualizacji. Kopie ręczne i ratunkowe pozostają.
- Kopie tworzy mechanizm SQLite, również gdy baza pracuje w trybie WAL.
- Przywracanie wymaga wyboru pliku i wpisania „PRZYWRÓĆ”. Przed nadpisaniem powstaje kopia bieżącego stanu.
- Sprawdzamy integralność, klucze obce i wymagany schemat. Uszkodzone i obce bazy są odrzucane.
- Jeśli migracja przywróconej bazy nie powiedzie się, poprzedni stan jest odtwarzany z kopii ratunkowej.

Kopie obejmują bazę SQLite. Zdjęcia paragonów pozostają w lokalnym folderze uploads i nie są przywracane z pliku bazy. Kopie, zdjęcia i prywatne raporty nie trafiają do repozytorium.

Weryfikacja: pełne testy backendu i frontendu, dodatkowe scenariusze transferów i przywracania oraz porównanie wpisów finansowych i sald z kopią sprzed zmian. Podczas sprawdzania interfejsu nie przywracano ani nie księgowano operacji w bazie użytkownika.
