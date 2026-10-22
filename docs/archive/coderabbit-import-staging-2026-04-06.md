# CodeRabbit Review — ImportStagingService (2026-04-06)

Zakres: nowy moduł `backend/import_staging_service.py`, `backend/routes_imports.py`,
`frontend/src/components/modals/ImportStagingModal.tsx`.

Wszystkie znaleziska z review oznaczone ⚠️ Główne lub ⚠️ Poboczne — przetworzone
na gotowe prompty wdrożeniowe.

---

## Tabela znalezisk

| ID | Plik | Linie | Priorytet | Problem | Status |
|---|---|---|---|---|---|
| IS-01 | import_staging_service.py | 330–337 (+354–369, +397–412) | Wysoki | Mutacja `booked` wiersza bez blokady | Otwarte |
| IS-02 | import_staging_service.py | 343–353 | Wysoki | Recompute SELL conflict przy reassign — `insufficient_qty` nie obsługiwany | Otwarte |
| IS-03 | import_staging_service.py | 375–390 | Wysoki | `assign_all()` łapie wszystkie wyjątki — błędy walidacji ukryte jako `skipped` | Otwarte |
| IS-04 | import_staging_service.py | 454–480 | Wysoki | BUY INSERT nie wypełnia pól FX — non-PLN holding zapisany jako PLN | Otwarte |
| IS-05 | import_staging_service.py | 543–553 | Wysoki | Sell-side conflict przy booking nie persistuje `conflict_type`/`conflict_details` | Otwarte |
| IS-06 | import_staging_service.py | 567–571 | Wysoki | `ValueError` dla błędów booking → 404 w routes (błędny mapping) | Otwarte |
| IS-07 | import_staging_service.py | 508–510 | Poboczny | `confirmed_row_ids` mogą być stringami — membership check `row['id']` (int) zawsze False | Otwarte |
| IS-08 | routes_imports.py | 97–119 | Wysoki | `ValueError` z `create_session()` / `import_xtb_csv()` → 500 zamiast 4xx | Otwarte |
| IS-09 | routes_imports.py | 138–154 (+164–179) | Wysoki | `int(target_sub_portfolio_id)` wewnątrz `try` — błąd JSON traktowany jak błąd serwisu | Otwarte |
| IS-10 | ImportStagingModal.tsx | 162–185 | Poboczny | Przycisk „Zamknij" po booking wywołuje `onCancel` → `deleteSession` na zarezerwowanej sesji | Otwarte |
| IS-11 | ImportStagingModal.tsx | 77–87 | Wysoki | `assignAll` — stan wiersza fabrykowany lokalnie, konflikty ukryte | Otwarte |

---

## Gotowe prompty

### IS-01 — Zablokuj mutację wierszy o statusie `booked`

```text
Verify each finding against the current code and only fix it if needed.

W backend/import_staging_service.py zabezpiecz wszystkie miejsca, gdzie wiersz
staging jest pobierany przed mutacją (SELECT + _validate_subportfolio) przed
modyfikacją wierszy już zarezerwowanych.

Wymagania:
1) We wszystkich 3 lokalizacjach (linie ~354, ~397) bezpośrednio po sprawdzeniu
   `if not row: raise ValueError(...)` dodaj:
     if row['status'] == 'booked':
         raise ValueError('Cannot modify booked row')
2) Nie zmieniaj żadnej innej logiki — wyłącznie guard na początku każdej mutacji.
3) Dodaj testy:
   - próba assign_row na wierszu z status='booked' → ValueError,
   - próba reject_row na wierszu z status='booked' → ValueError,
   - próba assign_all na sesji, gdzie część wierszy ma status='booked' → booked pominięte
     (increment skipped), reszta przypisana normalnie.
Uruchom testy import_staging_service.
```

---

### IS-02 — Recompute SELL conflict przy reassign (obsługa `insufficient_qty`)

```text
Verify each finding against the current code and only fix it if needed.

W backend/import_staging_service.py napraw logikę recompute konfliktu SELL
przy reassign (linie ~343–353).

Problem: kod czyści conflict_type gdy available_qty > 0, ale nie sprawdza czy
available_qty >= wymagana ilość z wiersza. SELL 10 przy holding=1 błędnie
kasuje konflikt.

Wymagania:
1) Rozszerz warunek wejścia — obsługuj oba typy konfliktu sprzedażowego:
     if row['type'] == 'SELL' and conflict_type in {'missing_holding', 'insufficient_qty'}:
2) Pobierz required_qty z wiersza:
     required_qty = float(row['quantity'] or 0.0)
3) Trzy gałęzie decyzji:
   a) available_qty <= 0:
        conflict_type = 'missing_holding'
        conflict_details = json.dumps({'required_qty': required_qty, 'available_qty': 0})
   b) required_qty > available_qty:
        conflict_type = 'insufficient_qty'
        conflict_details = json.dumps({'required_qty': required_qty, 'available_qty': available_qty})
   c) available_qty >= required_qty:
        conflict_type = None
        conflict_details = None
4) Dodaj testy:
   - reassign SELL 10 przy holding=1 → conflict_type='insufficient_qty',
     conflict_details zawiera {required_qty:10, available_qty:1},
   - reassign SELL 10 przy holding=0 → conflict_type='missing_holding',
   - reassign SELL 10 przy holding=15 → conflict_type=None (konflikt wyczyszczony),
   - reassign SELL przy original conflict_type='insufficient_qty' → poprawnie recomputed.
Uruchom testy import_staging_service.
```

---

### IS-03 — `assign_all()`: nie spłaszczaj błędów walidacji do `skipped`

```text
Verify each finding against the current code and only fix it if needed.

W backend/import_staging_service.py napraw assign_all() (linie ~375–390) tak,
aby błędy walidacji propagowały się zamiast być ukryte jako skipped.

Wymagania:
1) Przed pętlą: sprawdź czy sesja istnieje (query import_session WHERE session_id = ?).
   Jeśli brak → raise ValueError('Session not found') (lub NotFoundError).
2) Zdefiniuj dedykowany wyjątek do celowego pomijania wierszy:
     class ImportRowSkipError(Exception): pass
3) Zamień broad `except Exception:` na:
     except ImportRowSkipError:
         skipped += 1
   — tylko ten wyjątek inkrementuje skipped. Wszystkie inne propagują się.
4) W assign_row: rzuć ImportRowSkipError gdy wiersz ma status 'booked' lub jest
   celowo pomijany (nie błąd walidacji). Błędy walidacyjne (np. invalid sub-portfolio)
   nadal jako ValueError/ApiError.
5) Zwracaj też strukturę błędów per-wiersz jeśli potrzeba diagnozy:
     return {'assigned': assigned, 'skipped': skipped}
   (bez zmiany kontrayu API — błędy propagują się jako wyjątek do routes).
6) Dodaj testy:
   - assign_all z nieprawidłowym session_id → ValueError/NotFoundError (nie {assigned:0, skipped:0}),
   - assign_all gdzie jeden wiersz ma invalid sub_portfolio → wyjątek propaguje się do route,
   - assign_all gdzie jeden wiersz jest booked → skipped++, reszta przypisana.
Uruchom testy import_staging_service i routes_imports.
```

---

### IS-04 — BUY INSERT: wypełnij pola FX przy tworzeniu nowego holdingu

```text
Verify each finding against the current code and only fix it if needed.

W backend/import_staging_service.py w gałęzi BUY (linie ~454–480), przy INSERT
nowego holdingu wypełnij kolumny FX zamiast polegać na domyślnych wartościach
schematu (instrument_currency='PLN', avg_buy_fx_rate=1.0).

Wymagania:
1) Przed INSERT: resolve instrument_currency — użyj tej samej logiki co
   backend/portfolio_trade_service.py (linie ~143–243):
   - sprawdź symbol_mappings dla tickera,
   - fallback do metadata z PriceService,
   - fallback 'PLN'.
2) Przed INSERT: resolve avg_buy_fx_rate dla daty transakcji:
   - jeśli instrument_currency == 'PLN' → fx_rate = 1.0, fx_source = 'pln_native',
   - jeśli non-PLN → pobierz kurs {CCY}PLN=X dla daty transakcji,
   - jeśli brak kursu → fx_rate = NULL, fx_source = 'missing' (NIE 1.0).
3) Rozszerz INSERT INTO holdings o kolumny:
   (instrument_currency, avg_buy_fx_rate, avg_buy_price_native, fx_source)
   i uzupełnij VALUES odpowiednimi wartościami.
4) Dla gałęzi UPDATE (istniejący holding): nie nadpisuj FX fields jeśli już są ustawione
   (zachowaj avg_buy_fx_rate z pierwszego zakupu).
5) Dodaj testy:
   - import BUY dla USD tickera → instrument_currency='USD', avg_buy_fx_rate != 1.0,
   - import BUY dla USD tickera bez dostępnego kursu FX → fx_rate=NULL, fx_source='missing',
   - import BUY dla PLN tickera → instrument_currency='PLN', avg_buy_fx_rate=1.0.
Uruchom testy import_staging_service.
```

---

### IS-05 — Booking: persistuj `conflict_type` przy sell-side shortfall

```text
Verify each finding against the current code and only fix it if needed.

W backend/import_staging_service.py w book_session (linie ~543–553), gdy wykryto
sell-side conflict (available_qty niewystarczające), przed `continue` zapisz
zaktualizowane metadane konfliktu do DB.

Problem: obecnie tylko `skipped_conflicts` rośnie, ale wiersz staging zachowuje
stare conflict_type/conflict_details. Późniejszy get_session() nie może pokazać
UI dlaczego wiersz został pominięty.

Wymagania:
1) Przy available_qty <= 0:
     UPDATE import_staging SET conflict_type='missing_holding',
     conflict_details=json.dumps({...}), updated_at=now()
     WHERE id = row['id']
2) Przy needed_qty > available_qty:
     UPDATE import_staging SET conflict_type='insufficient_qty',
     conflict_details=json.dumps({'required_qty': needed_qty, 'available_qty': available_qty}),
     updated_at=now()
     WHERE id = row['id']
3) Użyj istniejącego helpera UPDATE jeśli istnieje, lub wykonaj bezpośrednie zapytanie.
4) Dopiero po UPDATE: increment result['skipped_conflicts'] i continue.
5) Dodaj testy:
   - book_session z SELL bez holdingu → skipped_conflicts++, get_session() zwraca
     conflict_type='missing_holding' dla tego wiersza,
   - book_session z SELL za dużo → conflict_type='insufficient_qty' w DB,
   - book_session z SELL OK → wiersz zarezerwowany, conflict_type=None.
Uruchom testy import_staging_service.
```

---

### IS-06 — Booking errors: użyj dedykowanego wyjątku zamiast `ValueError`

```text
Verify each finding against the current code and only fix it if needed.

W backend/import_staging_service.py zastąp `ValueError('Errors while booking rows')`
dedykowanym wyjątkiem, aby routes_imports.py nie mapował błędów booking na 404.

Wymagania:
1) Zdefiniuj nowy wyjątek w import_staging_service.py:
     class ImportBookingError(Exception):
         def __init__(self, message: str, row_errors: list[str]):
             super().__init__(message)
             self.row_errors = row_errors
2) Zastąp:
     raise ValueError('Errors while booking rows')
   na:
     raise ImportBookingError('Booking failed', result['errors'])
3) Zachowaj `ValueError` wyłącznie dla brakującej sesji (sesja not found).
4) W routes_imports.book_import_staging_session() dodaj obsługę ImportBookingError:
     except ImportBookingError as e:
         raise ApiError('BOOKING_ERROR', str(e),
                        details={'row_errors': e.row_errors}, status=422)
5) Dodaj testy:
   - booking z błędem DB na jednym wierszu → ApiError 422 z listą row_errors,
   - booking nieistniejącej sesji → 404 (ValueError mapowane do NotFoundError),
   - poprawne booking → 200 z wynikiem.
Uruchom testy import_staging_service i routes_imports.
```

---

### IS-07 — `confirmed_row_ids`: normalizuj do `int` przed membership check

```text
Verify each finding against the current code and only fix it if needed.

W backend/import_staging_service.py::book_session (linia ~510) znormalizuj
confirmed_row_ids do zbioru integerów przed sprawdzeniem membership.

Problem: JSON może dostarczyć IDs jako stringi. `row['id']` jest int. 
`"123" in {123}` → False → potwierdzone konflikty są błędnie pomijane.

Wymagania:
1) Zamień:
     confirmed = set(confirmed_row_ids or [])
   na:
     confirmed = set()
     for rid in (confirmed_row_ids or []):
         try:
             confirmed.add(int(rid))
         except (TypeError, ValueError):
             logger.warning(f"Invalid confirmed_row_id ignored: {rid!r}")
2) Upewnij się, że wszystkie miejsca sprawdzające `row['id'] in confirmed` (linia ~537-538)
   korzystają z tego znormalizowanego zbioru.
3) Dodaj testy:
   - confirmed_row_ids=['1', '2', 3] (mix stringów i intów) → wszystkie 3 traktowane jako potwierdzone,
   - confirmed_row_ids=['abc'] → warning, zbiór pusty, konflikt nie potwierdzony,
   - confirmed_row_ids=None → pusty zbiór (obecne zachowanie zachowane).
Uruchom testy book_session.
```

---

### IS-08 — `routes_imports.py`: `ValueError` z serwisu → 500 zamiast 4xx

```text
Verify each finding against the current code and only fix it if needed.

W backend/routes_imports.py (linie ~97–119) obsłuż ValueError rzucany przez
ImportStagingService.create_session() i PortfolioService.import_xtb_csv()
jako błąd klienta (4xx), nie błąd serwera (500).

Wymagania:
1) Otoczy oba wywołania w try/except:
   Dla staging path (create_session):
     try:
         result = ImportStagingService.create_session(...)
     except ValueError as e:
         raise ApiError('IMPORT_VALIDATION_ERROR', str(e), status=400)
   Dla direct path (import_xtb_csv) — uzupełnij istniejący blok błędu o catch ValueError:
     try:
         result = PortfolioService.import_xtb_csv(...)
     except ValueError as e:
         raise ApiError('IMPORT_VALIDATION_ERROR', str(e), status=400)
2) Zachowaj istniejącą logikę `if not result.get('success')` dla missing_symbols.
3) Nie zmieniaj kontrayu odpowiedzi dla poprawnych wywołań.
4) Dodaj testy:
   - import z brakującymi kolumnami CSV → 400 z IMPORT_VALIDATION_ERROR,
   - import z nieprawidłowym sub_portfolio_id → 400 (nie 500),
   - import z zarchiwizowanym portfolio → 400.
Uruchom testy routes_imports.
```

---

### IS-09 — `routes_imports.py`: waliduj `target_sub_portfolio_id` przed `try`

```text
Verify each finding against the current code and only fix it if needed.

W backend/routes_imports.py (linie ~138–154 i ~164–179) przenieś parsowanie
`int(target_sub_portfolio_id)` poza blok try/except, aby błędy JSON (np. "1.5", "abc")
nie były traktowane jak błędy serwisu.

Wymagania:
1) Przed wywołaniem serwisu wyodrębnij i zwaliduj wartość:
     raw = request.json.get('target_sub_portfolio_id')
     if raw is None:
         target_sub_portfolio_id = None
     else:
         try:
             val = int(raw)
             if val != float(raw):  # odrzuć 1.5
                 raise ValueError()
             if val <= 0:
                 raise ValueError()
             target_sub_portfolio_id = val
         except (TypeError, ValueError):
             raise ApiError('invalid_sub_portfolio',
                            'target_sub_portfolio_id must be a positive integer',
                            status=422, details={'field': 'target_sub_portfolio_id'})
2) Dopiero po tej walidacji uruchom blok try/except dla wywołania serwisu.
3) W except ValueError po serwisie: obsługuj tylko błędy serwisu (sub-portfolio
   validation, not-found), nie błędy parsowania (bo te już wyrzuciliśmy wcześniej).
4) Zastosuj tę samą zmianę w obu lokalizacjach (~138 i ~164).
5) Dodaj testy:
   - payload {"target_sub_portfolio_id": "abc"} → 422,
   - payload {"target_sub_portfolio_id": 1.5} → 422,
   - payload {"target_sub_portfolio_id": -1} → 422,
   - payload {"target_sub_portfolio_id": 5} → przechodzi do serwisu,
   - payload {"target_sub_portfolio_id": null} → przechodzi jako None.
Uruchom testy routes_imports.
```

---

### IS-10 — `ImportStagingModal`: przycisk „Zamknij" po booking wywołuje `deleteSession`

```text
Verify each finding against the current code and only fix it if needed.

W frontend/src/components/modals/ImportStagingModal.tsx (linie ~162–185) napraw
przycisk „Zamknij" w widoku po-booking, który błędnie wywołuje onCancel
(co triggeruje deleteSession w PortfolioDetails).

Wymagania:
1) Dodaj nowy prop do ImportStagingModal:
     onCloseAfterBooking?: () => void
2) W widoku bookResult (gałąź `if (bookResult)`):
     <button onClick={onCloseAfterBooking ?? onCancel}>Zamknij</button>
3) W PortfolioDetails (rodzic modalu): przekaż handler, który tylko zamyka modal
   BEZ usuwania sesji:
     onCloseAfterBooking={() => setShowImportModal(false)}
4) Zachowaj obecne onCancel dla prawdziwego anulowania (przed booking) →
   tam deleteSession jest poprawne.
5) Prop onCloseAfterBooking jest opcjonalny — fallback do onCancel jeśli nie podany
   (zachowanie wstecznie kompatybilne).
6) Dodaj testy (unit):
   - po pomyślnym booking kliknięcie Zamknij → onCloseAfterBooking wywołane, onCancel nie,
   - bez onCloseAfterBooking prop → fallback do onCancel (nie crash).
Uruchom testy frontend ImportStagingModal.
```

---

### IS-11 — `ImportStagingModal`: `assignAll` fabrykuje stan lokalnie — konflikty ukryte

```text
Verify each finding against the current code and only fix it if needed.

W frontend/src/components/modals/ImportStagingModal.tsx (linie ~77–87) zastąp
lokalne fabrykowanie stanu wierszy po assignAll rzeczywistymi danymi z serwera.

Problem: kod force-ustawia status='assigned' i target_sub_portfolio_id lokalnie
ignorując odpowiedź backendu. Konflikty wykryte przez serwis (conflict_type,
conflict_details) są pomijane, co desynchronizuje summary.conflictRows
i wyłącza canConfirmConflict.

 prompt mówi „Jeśli endpoint zwraca zaktualizowane rows: użyj serverRows". Aktualny backend assign_all zwraca tylko {assigned, skipped} — nigdy rows. Opcja A jest więc nieosiągalna bez zmiany API. Prompt powinien jasno wskazać jedyną realną ścieżkę: refetch sesji po assignAll. Czyli dodaj wywołanie getSession(session.session_id) i zastąp nim lokalne setRows.

Wymagania:
1) Upewnij się, że assignAll() zwraca zaktualizowane wiersze lub summary sesji
   (jeśli nie zwraca — rozszerz API endpoint /assign-all o odpowiedź z rows).
2) Po await assignAll(...):
   a) Jeśli endpoint zwraca zaktualizowane rows: zastąp setRows(prev => ...) na
      setRows(serverRows) lub zmapuj server response na StagingRow[].
   b) Jeśli endpoint nie zwraca rows: wykonaj refetch sesji:
        const updated = await fetchSession(session.session_id);
        setRows(updated.rows);
        setSession(updated.session);
3) Usuń obecny `prev.map(row => { return { ...row, status: 'assigned', ... } })`.
4) Rekomputuj summary (conflictRows, canConfirmConflict) ze świeżych danych,
   nie z lokalnych założeń.
5) Dodaj testy:
   - assignAll gdzie backend oznacza część wierszy jako conflict → conflictRows > 0 po operacji,
   - assignAll sukces wszystkich → conflictRows = 0, canConfirmConflict = false,
   - assignAll z błędem serwisu → error state, rows niezmienione.
Uruchom testy frontend ImportStagingModal.
```

---

## Rekomendowana kolejność wdrożeń

### Blok 1 — Poprawność danych (wdrożyć razem)
1. **IS-02** — SELL recompute conflict przy reassign (patch dostarczony przez CodeRabbit)
2. **IS-04** — BUY INSERT FX fields (kluczowy dla poprawności wyceny)
3. **IS-05** — Persistuj conflict_type przy sell-side booking shortfall
4. **IS-07** — Normalizacja `confirmed_row_ids` do int

### Blok 2 — Poprawność błędów API (wdrożyć razem)
5. **IS-01** — Guard na booked rows
6. **IS-03** — `assign_all()` exception propagation
7. **IS-06** — `ImportBookingError` zamiast `ValueError`
8. **IS-08** — `routes_imports` ValueError → 4xx
9. **IS-09** — `target_sub_portfolio_id` walidacja przed try

### Blok 3 — Frontend
10. **IS-11** — `assignAll` refetch zamiast lokalnego fake state (kluczowe)
11. **IS-10** — Zamknij po booking (niska złożoność)

---

*Łącznie znalezisk: 11 | Wysoki priorytet: 9 | Poboczny: 2*
*Wszystkie mają gotowe prompty. Blok 1 + 2 należy wdrożyć przed merge.*
