# Plan walidacji duplikowania importowanych transakcji (ZAKTUALIZOWANY)

Niniejszy dokument opisuje plan wprowadzenia mechanizmu wykrywania potencjalnie zduplikowanych transakcji podczas importu danych (np. z plików CSV brokera XTB).

## 1. Cel
Zapewnienie spójności danych poprzez uniemożliwienie przypadkowego zaimportowania tej samej transakcji wielokrotnie. System powinien wykrywać podejrzenie duplikatu i prosić użytkownika o potwierdzenie przed zapisaniem danych.

## 2. Kryteria wykrywania duplikatów
Transakcja zostanie uznana za **potencjalny duplikat**, jeśli:
1.  **W bazie danych** istnieje już transakcja dla tego samego portfela, która spełnia warunki:
    -   **Data i godzina**: Dokładnie taka sama jak w importowanym wierszu.
    -   **Wartość całkowita (total_value)**: Taka sama kwota.
    -   **Ilość (quantity)**: Taka sama liczba jednostek/akcji.
    -   **Ticker**: Ten sam instrument (jeśli dotyczy).
    -   **Typ operacji**: Ten sam typ (np. BUY, SELL, DEPOSIT).
2.  **Wewnątrz importowanego pliku** znajdują się identyczne wiersze (ta sama data, kwota, ilość, ticker, typ).

## 3. Zmiany w Backendzie

### 3.1. Identyfikacja wierszy (Hashe)
Zamiast polegać na numerach linii (indeksach), backend będzie generował dla każdego wiersza unikalny, tymczasowy **hash** (np. SHA-256 z połączonych pól: `date + ticker + amount + type + quantity`). Pozwoli to na bezpieczną komunikację między frontendem a backendem bez ryzyka przesunięcia indeksów.

### 3.2. Rozszerzenie logiki importu (`PortfolioImportService.import_xtb_csv`)
Import zostaje podzielony na dwa etapy:
1.  **Etap Walidacji (Dry Run)**: 
    -   Backend parsuje plik CSV.
    -   Sprawdza duplikaty wewnątrz pliku.
    -   Sprawdza duplikaty względem bazy danych.
    -   Zwraca status `warning` (200 OK) wraz z listą `potential_conflicts` zawierającą hashe wierszy i szczegóły konfliktów.
2.  **Etap Zapisu**: 
    -   Backend otrzymuje listę `confirmed_hashes` (hashe transakcji, które użytkownik świadomie chce zaimportować).
    -   **Wszystkie operacje zapisu odbywają się w ramach jednej transakcji DB (Atomic)**. Jeśli jakikolwiek zapis się nie powiedzie, następuje pełny rollback.

### 3.3. Struktura odpowiedzi API
W przypadku wykrycia konfliktów, API zwróci status 200 OK z następującą strukturą:
```json
{
  "status": "warning",
  "potential_conflicts": [
    {
      "row_hash": "a1b2c3d4...",
      "conflict_type": "database_duplicate" | "file_internal_duplicate",
      "import_data": { "date": "2024-03-20 10:00", "ticker": "AAPL", "amount": 1500.00, "type": "BUY" },
      "existing_match": { 
        "id": 123, 
        "date": "2024-03-20 10:00", 
        "amount": 1500.00, 
        "type": "BUY",
        "source": "database" | "file_row_X" 
      }
    }
  ],
  "missing_symbols": []
}
```
*Uwaga: Dla `file_internal_duplicate` pole `id` będzie puste/null, a pole `source` wskaże na numer wiersza w pliku.*

## 4. Zmiany we Frontendzie

### 4.1. Interfejs użytkownika (Popup)
- Wyświetlenie modala `DuplicateConfirmationModal` w przypadku otrzymania statusu `warning`.
- Prezentacja "Side-by-side": Importowana transakcja vs. Istniejąca w bazie lub inny wiersz z pliku (z pełnymi detalami: ID/wiersz, typ, data, kwota).
- Możliwość selektywnego wyboru, które z "podejrzanych" transakcji mają zostać zaimportowane.

### 4.2. Przepływ użytkownika
1.  Upload pliku -> Backend (Dry Run).
2.  Jeśli `status === "warning"`:
    -   Pokaż modal z listą konfliktów.
    -   Użytkownik zaznacza wybrane transakcje.
3.  Zatwierdzenie -> Ponowny POST do backendu z listą `confirmed_hashes`.
4.  Zakończenie importu.

## 5. Harmonogram prac
1.  **Backend**: Implementacja generatora hashy dla wierszy CSV.
2.  **Backend**: Dodanie logiki wykrywania duplikatów wewnątrz pliku (internal duplicates).
3.  **Backend**: Dodanie logiki sprawdzania duplikatów w bazie danych (external duplicates).
4.  **Backend**: Zapewnienie pełnej transakcyjności (rollback przy błędzie) w procesie zapisu.
5.  **Frontend**: Stworzenie `DuplicateConfirmationModal` z widokiem porównawczym.
6.  **Frontend**: Integracja modala w `PortfolioDetails.tsx` i obsługa nowego przepływu importu.
7.  **Frontend**: Obsługa przesyłania `confirmed_hashes` w ostatecznym żądaniu zapisu.
8.  **Testy**: Weryfikacja scenariuszy: duplikaty w pliku, duplikaty w bazie, mieszane przypadki.
