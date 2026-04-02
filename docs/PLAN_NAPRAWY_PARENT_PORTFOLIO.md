# Plan naprawy agregacji danych dla portfela nadrzędnego (Parent)

Data: 2026-04-02
Status: **Do wdrożenia**

## 1. Zidentyfikowane problemy

1.  **Brak aktywnych pozycji w widoku Parent**: Obecnie widok portfela nadrzędnego filtruje pozycje (`holdings`) tak, aby pokazywać tylko te, które są przypisane bezpośrednio do niego (`sub_portfolio_id IS NULL`), pomijając wszystkie pozycje z sub-portfeli.
2.  **Brak historii zysku i wartości w widoku Parent**: Podobnie jak w przypadku pozycji, funkcje historyczne filtrują transakcje tak, aby uwzględniać tylko te przypisane bezpośrednio do Parenta. Powoduje to, że wykresy i tabele wyników nie odzwierciedlają agregacji całego drzewa portfela.

## 2. Planowane poprawki

### A. Naprawa widoku pozycji (Active Holdings)
W klasie `PortfolioValuationService.get_holdings` (backend):
- Usunięcie filtra `sub_portfolio_id IS NULL` dla portfeli nadrzędnych.
- Zmiana logiki na agregację po tickerze: jeśli ten sam instrument znajduje się w wielu sub-portfelach, zostanie on zsumowany w widoku nadrzędnym (średnia cena zakupu, łączna ilość).
- Dzięki temu w głównym widoku Parenta zobaczymy pełen obraz aktywów.

### B. Naprawa historii (History & Profit Charts)
W klasie `PortfolioHistoryService` (backend):
- Metody `_calculate_historical_metrics`, `get_portfolio_profit_history_daily` oraz `get_performance_matrix` zostaną zaktualizowane.
- Dla portfeli nadrzędnych filtr `sub_portfolio_id IS NULL` zostanie usunięty z zapytań SQL do tabeli `transactions`.
- Ponieważ reguła biznesowa mówi, że `portfolio_id` na transakcji zawsze wskazuje na Parenta, pobranie wszystkich transakcji dla danego `portfolio_id` automatycznie zsumuje historię całego drzewa.

### C. Naprawa salda gotówki (Cash Balance)
W klasie `PortfolioValuationService.get_cash_balance_on_date`:
- Aktualizacja zapytania dla Parenta, aby suma gotówki uwzględniała wszystkie transakcje z całego drzewa, a nie tylko te przypisane bezpośrednio.

## 3. Kolejność wdrożenia

1.  [ ] **Modyfikacja `portfolio_valuation_service.py`**: Naprawa `get_holdings` oraz `get_cash_balance_on_date`.
2.  [ ] **Modyfikacja `portfolio_history_service.py`**: Naprawa agregacji transakcji w historii.
3.  [ ] **Weryfikacja**: Sprawdzenie czy dane na froncie (pozycje i wykresy) odświeżają się poprawnie dla portfela Parent.
4.  [ ] **Testy regresyjne**: Uruchomienie istniejących testów sub-portfeli, aby upewnić się, że widoki pojedynczych sub-portfeli (Child) nadal działają poprawnie.

## 4. Przewidywany efekt
Po wdrożeniu poprawek, użytkownik otwierając portfel nadrzędny zobaczy:
- Wszystkie akcje/instrumenty posiadane we wszystkich sub-portfelach (zsumowane).
- Poprawny wykres wartości całego portfela (suma wszystkich sub-portfeli w czasie).
- Pełną macierz wyników miesięcznych oraz XIRR dla całego drzewa inwestycyjnego.
