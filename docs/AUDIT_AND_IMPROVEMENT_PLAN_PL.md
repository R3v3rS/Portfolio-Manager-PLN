# Audyt Dokumentacji i Plan Usprawnień

**Data:** 2026-04-02  
**Status:** Audyt dokumentacji + plan remediacji wykonany i wyrównany do aktualnego backendu.

Dokument zawiera: (1) wykryte defekty dokumentacji, (2) analizę przyczyn źródłowych, (3) priorytety poprawek, (4) rekomendacje techniczne.

---

## 1. Zakres audytu
Pliki objęte audytem:
- `docs/AUDIT_AND_IMPROVEMENT_PLAN.md` (poprzednia wersja)
- `docs/PROJECT_GUIDE.md` (poprzednia wersja)

Logika referencyjna użyta do wyrównania:
- ścieżki zapisu transakcji (`deposit/withdraw/buy/sell/dividend/import`),
- reguły holdings i deterministycznej odbudowy,
- agregacja parent/child,
- wycena i konwersja FX.

---

## 2. Wykryte problemy

## A) Błędy logiczne

1. **Model własności był niedookreślony i miejscami mylący**  
   Poprzednie dokumenty nie wymuszały konsekwentnie reguły: właścicielem transakcji jest parent (`portfolio_id`), a child to zakres (`sub_portfolio_id`).

2. **Reguły agregacji były opisowe, nie deterministyczne**  
   Brak jawnej formuły agregacji średniego kosztu parenta (`SUM(total_cost)/SUM(quantity)`).

3. **Niejednoznaczność „holdings vs transactions”**  
   Dokumentacja nie rozdzielała jasno transakcji jako ledgera źródłowego i holdings jako stanu pochodnego.

4. **Reguła SELL cost basis nie była jawna**  
   Brak obowiązkowego wzoru redukcji `total_cost` przy partial sell.

5. **Brak udokumentowania edge-case parsera ilości XTB**  
   Zachowanie `"1/5" -> 1` nie było opisane jako kontrakt.

6. **Brak twardej reguły normalizacji przepływu**  
   `tx_total = abs(amount)` było w implementacji, ale nie jako jawna reguła dokumentacyjna.

## B) Niespójności między dokumentami

1. **Mieszana terminologia** (`subportfolio`, `sub-portfolio`, parent/main scope) bez słownika pojęć.
2. **Rozjazd roli dokumentów**: jeden plik był roadmapą/statusem, drugi mapą architektury, ale żaden nie był jednoznaczną specyfikacją reguł księgowych.
3. **Różna granularność**: wzory i zasady pojawiały się fragmentarycznie.

## C) Brakujące informacje krytyczne

1. Jawna reguła redukcji SELL:
   - `total_cost -= sold_qty * avg_price`
2. Jawna reguła średniej agregowanej parenta:
   - `SUM(total_cost) / SUM(quantity)`
3. Jawna reguła własności transakcji:
   - `portfolio_id = parent`, `sub_portfolio_id = child scope`
4. Jawna obsługa ułamka ilości XTB:
   - `"1/5" -> qty = 1`
5. Jawna reguła normalizacji:
   - `tx_total = abs(amount)`
6. Jawne wskazanie, że holdings są stanem odbudowywalnym z ledgera transakcji.
7. Sekcja ryzyk dla mixed float/decimal precision.

## D) Duplikacje

1. Powtórzone opisy architektury bez deterministycznych reguł.
2. Powtórzone opisy routerów/serwisów bez nowych informacji operacyjnych.
3. Nakładające się fragmenty historii/wyceny bez mapowania na konkretne inwarianty.

## E) Dług techniczny / ryzyka

1. **Precyzja (HIGH):** współistnienie `float` i decimal-based audit/rebuild może dawać rozjazdy.
2. **FX (MEDIUM):** reguły wyceny są deterministyczne, ale end-to-end policy dla historycznego FX nie jest pełna.
3. **Agregacja (MEDIUM):** parent totals są składane w wielu miejscach.
4. **Zaokrąglenia (MEDIUM):** repeated partial sells mogą kumulować dryf centowy.
5. **Wydajność historii (LOW/MEDIUM):** rekonstrukcja dzienna jest kosztowna przy dużej liczbie transakcji.

---

## 3. Analiza przyczyn źródłowych

1. **Drift celu dokumentacji**  
   Dokumenty mieszały changelog, roadmapę, onboarding i specyfikację.

2. **Opis narracyjny zamiast specyfikacji reguł**  
   Krytyczne zachowania księgowe nie były zapisane jako wzory/inwarianty.

3. **Brak hierarchii „source of truth” między plikami**  
   Powodowało to niespójność i luki w zasadach.

4. **Ewolucja backendu szybsza niż porządki dokumentacji**  
   Szczególnie w obszarze parent/child i repair/rebuild.

---

## 4. Priorytety poprawek

## HIGH (krytyczne dla poprawności)
1. Jednoznacznie zdefiniować model własności (`portfolio_id` parent + `sub_portfolio_id` child scope).
2. Zdefiniować deterministyczne wzory BUY/SELL wraz z obowiązkową regułą SELL cost basis.
3. Zdefiniować formułę agregacji średniej ważonej parenta.
4. Zdefiniować kontrakt normalizacji importu i parsowania ilości XTB.
5. Utrzymać jeden dokument jako autorytatywne źródło prawdy.

## MEDIUM (stabilność i utrzymanie)
1. Ujednolicić terminologię.
2. Dopisać jawnie, że holdings to stan pochodny.
3. Udokumentować krytyczne edge-case’y (partial sell, archived child, parent-own + child na tym samym tickerze).
4. Zmapować ryzyka precision/FX/rounding na kierunki mitigacji.

## LOW (dalsze podniesienie jakości)
1. Rozszerzyć API docs o przykłady request/response.
2. Dodać checklistę inwariantów dla autorów testów regresyjnych.
3. Dodać tabelę traceability: reguła -> test.

---

## 5. Wdrożone usprawnienia dokumentacji (ten pass)

1. Przepisano `docs/PROJECT_GUIDE.md` na specyfikację source-of-truth.
2. Dodano jawne wzory BUY/SELL/agregacji/normalizacji cash flow.
3. Dodano jednoznaczny model własności i zakresów parent/child.
4. Dodano jawne reguły XTB quantity + abs(amount).
5. Dodano sekcję edge-case’ów i rejestr ryzyk.
6. Przekształcono ten dokument w audyt z RCA i planem priorytetowym.

---

## 6. Rekomendacje techniczne

1. **Przejść na decimal-first accounting** (eliminować `float` z mutacji cash/book-cost).
2. **Scentralizować prymitywy agregacji** (jeden helper dla reguł parent aggregate).
3. **Wprowadzić testy inwariantów** dla:
   - własności parent/child,
   - SELL cost basis,
   - weighted average parenta,
   - parsowania ilości i normalizacji `abs(amount)` w imporcie.
4. **Doprecyzować politykę FX accounting** (moment kursu, pola, zaokrąglenia).
5. **Dodać doc QA gate** sprawdzający spójność terminologii i reguł.

---

## 7. Kryteria akceptacji jakości dokumentacji

Dokumentacja jest akceptowalna, gdy:
1. Krytyczne zachowania księgowe są zapisane jawnie jako reguły/wzory.
2. Nie ma sprzeczności między `PROJECT_GUIDE` i planem audytu.
3. Semantyka ownership i agregacji jest deterministyczna i testowalna z samego tekstu.
4. Krytyczne ryzyka są wskazane z kierunkiem mitigacji.
5. Nowy maintainer może poprawnie wdrażać i walidować zachowanie bez czytania kodu źródłowego.

