# Audyt funkcjonalny portfolio (2026-03-28)

## Zakres
- Backend: operacje portfela, sub-portfeli, transferów/assign transakcji, dywidend i historii.
- Frontend: przepływy UI związane z transferami i filtrowaniem sub-portfeli.
- Testy: pokrycie krytycznych ścieżek parent/child/transfer.

---

## Podsumowanie ryzyk (Executive Summary)

Najważniejsze obserwacje po audycie kodu:

1. **Krytyczne ryzyko integralności przy wypłatach z sub-portfeli** – brak walidacji parent-child w `withdraw_cash` pozwala wskazać dowolne `sub_portfolio_id` jako źródło środków.  
2. **Błędny odczyt dywidend dla childów** – endpointy dywidend bazują tylko na `portfolio_id`, a dane childów są zapisywane pod parentem + `sub_portfolio_id`.  
3. **Niespójna semantyka „clear portfolio” dla childów** – czyszczenie childa nie czyści transakcji childa (bo zapisane są pod parentem).  
4. **Ryzyko niespójności kontraktu** – `/config` zwraca lokalną, zdublowaną listę dozwolonych typów kont, niezależną od stałej backendowej.  
5. **Niskie pokrycie testami scenariuszy sub-portfeli i transferów** – brak testów regresyjnych dla assign parent↔child i child↔child.

---

## Re-audyt status (2026-03-28, ponowna weryfikacja)

- [x] **1) [CRITICAL] Walidacja parent-child przy `withdraw_cash` naprawiona**.
- [x] **2) [HIGH] Odczyt dywidend childów naprawiony** (`get_dividends`, `get_monthly_dividends`).
- [x] **3) [HIGH] `clear_portfolio_data` dla childów zabezpieczone** (blokada clear dla childa + kontrola aktywnych childów parenta).
- [x] **4) [MEDIUM] `/config` korzysta ze stałej backendowej** (`SUBPORTFOLIOS_ALLOWED_TYPES`).
- [x] **5) [MEDIUM] Walidacja wejścia w assign endpointach wdrożona**.
- [x] **6) [MEDIUM] Frontend Transactions: filtr sub-portfeli dla drzewa naprawiony** (spłaszczanie).
- [x] **7) [MEDIUM] Testy regresyjne parent/child/assign/dividends/clear znacząco rozszerzone**.
- [ ] **8) [P2] Automatyczne checki spójności parent/child po transferach w dashboardzie audytowym** – nadal otwarte.

---

## Szczegółowe ustalenia

## 1) [CRITICAL] Brak walidacji parent-child przy `withdraw_cash`

**Dowód w kodzie**
- `deposit_cash`, `buy_stock`, `record_dividend` walidują czy `sub_portfolio_id` należy do parenta i czy child nie jest zarchiwizowany.  
- `withdraw_cash` tego nie robi – używa bezpośrednio `target_id = sub_portfolio_id if sub_portfolio_id else portfolio_id`.  

**Wpływ**
- Możliwe logiczne „pobranie” środków z niewłaściwego portfela przy ręcznym wywołaniu API (integralność i bezpieczeństwo danych finansowych).

**Rekomendacja**
- Ujednolicić walidację write-path: przed wypłatą zawsze walidować zgodność parent-child i status `is_archived`.
- Dodać test negatywny: wypłata z childa należącego do innego parenta → `422`.

---

## 2) [HIGH] Dywidendy childów nie są poprawnie odczytywane

**Dowód w kodzie**
- Zapis dywidendy childa: `record_dividend(...)` zapisuje rekord z `portfolio_id=parent` i `sub_portfolio_id=child`.  
- Odczyt dywidend: `get_dividends(portfolio_id)` filtruje wyłącznie `WHERE portfolio_id = ?` (brak logiki child/parent).  
- Odczyt miesięczny ma analogiczny problem (`get_monthly_dividends`).

**Wpływ**
- Dla childa (`/dividends/<child_id>`) API może zwracać pusto mimo istniejących dywidend przypisanych do childa.
- Raportowanie i wykresy dywidend mogą być niezgodne z rzeczywistością.

**Rekomendacja**
- Dla endpointu dywidend zastosować tę samą semantykę co w historii/holdings: 
  - child: filtrować po `portfolio_id=parent` i `sub_portfolio_id=child`, 
  - parent: zwracać parent own + children (albo tryb parametryzowany).
- Dodać testy dla parent i child.

---

## 3) [HIGH] `clear_portfolio_data` jest niespójne dla childów

**Dowód w kodzie**
- `clear_portfolio_data(portfolio_id)` usuwa `transactions/holdings/dividends` tylko po `portfolio_id = ?`.  
- W modelu child transakcje/holdings/dywidendy są przechowywane pod parentem i oznaczane przez `sub_portfolio_id`.

**Wpływ**
- „Wyczyszczenie” childa nie usuwa jego historycznych rekordów; może jedynie wyzerować `current_cash` childa.
- Możliwe trudne do wykrycia niespójności po operacjach administracyjnych.

**Rekomendacja**
- Dodać rozróżnienie parent vs child i odpowiednie warunki kasowania (`portfolio_id + sub_portfolio_id`).
- Opcjonalnie zablokować `clear` dla childów do czasu pełnej implementacji.

---

## 4) [MEDIUM] Dryf kontraktu: `/config` używa lokalnej listy zamiast stałej

**Dowód w kodzie**
- W module tras importowana jest stała `SUBPORTFOLIOS_ALLOWED_TYPES`.  
- Endpoint `/config` nadpisuje ją lokalnie: `SUBPORTFOLIOS_ALLOWED_TYPES = ['IKE', 'STANDARD']`.

**Wpływ**
- Rozjazd między walidacją tworzenia childa i konfiguracją zwracaną do frontendu po zmianie stałej.

**Rekomendacja**
- Usunąć lokalne nadpisanie i zwracać wyłącznie wartość ze `constants.py`.

---

## 5) [MEDIUM] Braki walidacji wejścia w assign endpointach

**Dowód w kodzie**
- `assign_transaction` i `assign_transactions_bulk` pobierają `sub_portfolio_id` z JSON bez walidatora typu (`optional_number`/`require_positive_int`).

**Wpływ**
- Możliwe słabe komunikaty błędów i niejednoznaczna semantyka dla niepoprawnych payloadów.

**Rekomendacja**
- Użyć wspólnego walidatora wejścia + spójne kody domenowe błędów.

---

## 6) [MEDIUM] Frontend: filtr sub-portfeli na stronie Transactions nie działa poprawnie dla drzewa

**Dowód w kodzie**
- `Transactions.tsx` wylicza sub-portfele przez `portfolios.filter(p => p.parent_portfolio_id === ...)`.
- `portfolioApi.list()` domyślnie pobiera `/list` (tree=1), gdzie childy są zagnieżdżone w `children`, a niekoniecznie na poziomie root.

**Wpływ**
- Użytkownik może nie widzieć pełnej listy childów w filtrze sub-portfela.

**Rekomendacja**
- Dla tego widoku pobierać listę płaską (`tree=0`) albo spłaszczać strukturę po stronie UI.

---

## 7) [MEDIUM] Niewystarczające testy regresyjne dla sub-portfeli i transferów

**Dowód w kodzie**
- Obecne testy skupiają się głównie na smoke/API contract i transferach budżetowych.
- Brak testów dla: assign parent→child, child→parent, child→child, walidacji archived child, i odczytów dywidend childa.

**Wpływ**
- Wysokie ryzyko regresji przy kolejnych zmianach.

**Rekomendacja**
- Dodać pakiet testów integracyjnych dla transferów i agregacji parent/child.
- Dodać testy negatywne (cross-parent, INTEREST do childa, archived child).

---

## Plan naprawczy (priorytety)

### P0 (natychmiast)
1. [x] Naprawić walidację `withdraw_cash` dla `sub_portfolio_id`.
2. [x] Naprawić odczyt dywidend (`get_dividends`, `get_monthly_dividends`) z pełną semantyką parent/child.
3. [x] Dodać testy integracyjne dla transferów assign + walidacji cross-parent.

### P1 (najbliższy sprint)
4. [x] Naprawić `clear_portfolio_data` dla childów lub zablokować endpoint dla childa do czasu wdrożenia.
5. [x] Ujednolicić źródło `SUBPORTFOLIOS_ALLOWED_TYPES` w `/config`.
6. [x] Uspójnić walidację payloadów assign endpointów.

### P2 (higiena i UX)
7. [x] Naprawić filtr sub-portfeli w `Transactions.tsx`.
8. [ ] Rozszerzyć dashboard audytowy o automatyczne checki spójności parent/child po transferach.

---

## Proponowany minimalny zestaw testów regresyjnych

1. `assign_transaction`:
   - parent → child (OK),
   - child → parent (OK),
   - childA → childB (OK),
   - child innego parenta (422),
   - `INTEREST` do childa (422).
2. `withdraw_cash`:
   - poprawny child własny (OK),
   - child innego parenta (422),
   - child zarchiwizowany (422).
3. Dywidendy:
   - dodanie dywidendy do childa,
   - odczyt dywidend childa zawiera rekord,
   - odczyt parenta pokazuje agregację zgodną z decyzją domenową.
4. `clear_portfolio_data`:
   - parent: pełne czyszczenie,
   - child: zachowanie zgodne z polityką (albo poprawne kasowanie, albo kontrolowany błąd).

---

## Ocena końcowa

System ma solidną bazę dla modelu parent/child, ale obecnie ma kilka **wysokoryzykownych luk** w write-path i read-path dotyczących sub-portfeli (w szczególności wypłaty i dywidendy). Przed dalszym rozwojem funkcji transferowych rekomendowane jest wdrożenie poprawek P0 i testów regresyjnych.
