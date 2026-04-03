# Weryfikacja zgłoszonych problemów i plan poprawek (2026-04-03)

Zakres: **tylko weryfikacja** i przygotowanie materiału wdrożeniowego.
Nie zmieniano kodu aplikacji produkcyjnej.

## Podsumowanie statusu

| # | Obszar | Status weryfikacji | Wniosek |
|---|---|---|---|
| 1 | RSI i dzielenie przez zero | ✅ Potwierdzone | Komentarz nie odpowiada implementacji; `loss == 0` daje RSI=100 zamiast `NaN/None`. |
| 2 | `warmup_cache` i ticker `CASH` | ✅ Potwierdzone | `warmup_cache` pobiera także `CASH`. |
| 3 | `get_quotes` fallback po błędzie bulk | ✅ Potwierdzone | Gałąź fallback jest placeholderem (`pass`) i nie uzupełnia braków. |
| 4 | `get_quotes` zwraca `price: 0.0` przy braku danych | ✅ Potwierdzone | W kilku miejscach brak danych oznaczany jest jako `0.0` zamiast `None`. |
| 5 | `inserted_rows` zawiera także UPDATE | ✅ Potwierdzone | Log „Inserted ... new history rows” jest semantycznie nieprecyzyjny przy UPSERT. |
| 6 | Thread safety cache | ✅ Potwierdzone | Cache class-level modyfikowany bez dedykowanego locka. |
| 7 | `datetime.utcnow()` | ✅ Potwierdzone | Występuje użycie `utcnow`; zalecana wersja timezone-aware. |
| 8 | `datetime.fromtimestamp()` bez `tz` | ✅ Potwierdzone | Konwersja zależna od lokalnej strefy serwera. |
| 9 | `_latest_expected_market_day` i święta | ✅ Potwierdzone (niski priorytet) | Funkcja pomija tylko weekendy, nie kalendarz świąt giełdowych. |
|10| `change_1y` i długość historii | ✅ Potwierdzone | Liczenie 1Y używa pierwszej dostępnej ceny nawet przy krótszym oknie niż 1 rok. |

---

## Szczegóły weryfikacji i rekomendacja

### 1) RSI: obsługa dzielenia przez zero
- W kodzie jest:
  - `rs = gain / loss`
  - `hist['RSI'] = 100 - (100 / (1 + rs))`
  - komentarz: „Handle division by zero or NaN if loss is 0”.
- Przy `loss == 0`, `rs` staje się `inf`, co daje RSI=100. To nie realizuje semantyki „brak danych”, tylko „skrajnie wykupiony”.

**Rekomendacja:**
- Zastąpić dzielenie przez `loss.replace(0, float('nan'))`, a wynikowe `NaN` mapować na `None` dla API.

### 2) `warmup_cache` wysyła `CASH` do providerów
- `warmup_cache` pobiera tickery z `SELECT DISTINCT ticker FROM holdings` bez filtra `CASH`.
- W tym samym module istnieje już poprawny filtr w audycie jakości historii (`ticker != 'CASH'`).

**Rekomendacja:**
- Ujednolicić zapytanie w `warmup_cache` do wersji wykluczającej `NULL` i `CASH`.

### 3) `get_quotes`: pusty fallback po awarii bulk
- W `except` dla bulk download jest pętla po tickerach i `pass`.
- Efekt: część lub wszystkie tickery mogą nie trafić do wyniku wcale.

**Rekomendacja:**
- Wdrożyć realny fallback per ticker **albo** co najmniej gwarantować wpis z `price: None` i zmianami `None` dla każdego brakującego tickera.

### 4) `get_quotes`: `price: 0.0` jako sygnał braku danych
- W kilku miejscach na ścieżkach błędu/no-data zwracane jest `price: 0.0`.
- To miesza semantykę „realna cena 0” i „brak kwotowania”.

**Rekomendacja:**
- Dla „brak danych” zwracać `price: None`.
- Utrzymać spójność z innymi polami (`change_*`), które już są `None`.

### 5) `inserted_rows` i log UPSERT
- W sync historii stosowane jest `INSERT ... ON CONFLICT ... DO UPDATE`.
- `cursor.rowcount` inkrementuje się także dla UPDATE.
- Komunikat „Inserted X new history rows” jest mylący przy odświeżaniu istniejących rekordów.

**Rekomendacja:**
- Zmienić komunikat logu na „Upserted X history rows (new + refreshed)”.

### 6) Thread safety cache
- `_price_cache`, `_price_cache_updated_at`, `_metadata_cache`, `_metadata_cache_updated_at` są słownikami class-level.
- W module jest lock agregacji błędów, ale nie ma dedykowanego locka wokół odczytu/zapisu cache.

**Rekomendacja:**
- Dodać lock dla operacji cache (najlepiej jeden wspólny lub osobne dla price/meta).
- Objąć lockiem modyfikacje i krytyczne sekwencje read-modify-write.

### 7) `datetime.utcnow()`
- Występuje użycie `datetime.utcnow().strftime(...)`.

**Rekomendacja:**
- Przejść na timezone-aware UTC, np. `datetime.now(timezone.utc)`.

### 8) `datetime.fromtimestamp()` bez timezone
- Daty eventów rynkowych są liczone `datetime.fromtimestamp(ts)` bez `tz`.
- To zależy od strefy serwera i może powodować przesunięcia dat.

**Rekomendacja:**
- Użyć `datetime.fromtimestamp(ts, tz=timezone.utc)`.

### 9) `_latest_expected_market_day` ignoruje święta
- Funkcja cofa się tylko po weekendach.
- W dni wolne od sesji (np. święta) może błędnie uznać, że dane są „stare”.

**Rekomendacja (niski priorytet):**
- Rozważyć kalendarz giełdowy (np. `exchange_calendars`) albo prosty adapter per rynek.

### 10) `change_1y` liczy „od początku danych”, niekoniecznie 1 rok
- Warunek `if len(hist) > 0` jest zbyt słaby dla metryki 1Y.
- `hist['Close'].iloc[0]` to najstarszy punkt z dostępnego okna, które bywa krótsze niż rok.

**Rekomendacja:**
- Dodać minimalny próg długości historii (np. ~250 sesji) lub liczyć od daty `today - 365d` z najbliższym punktem.

---

## Gotowe prompty do wdrożenia poprawek (po kolei)

Poniższe prompty są przygotowane tak, aby można je wykonywać sekwencyjnie jako osobne taski.

### Prompt 1 — RSI division by zero
```text
Napraw backend/price_service.py w logice RSI (sekcja technicals), aby loss=0 nie dawał RSI=100 przez inf.
Wymagania:
1) Użyj dzielenia przez loss.replace(0, float('nan')).
2) Zachowaj aktualny interfejs wyjściowy technicals (rsi14/sma50/sma200).
3) Upewnij się, że wynik NaN jest mapowany do None dla technicals["rsi14"].
4) Dodaj/uzupełnij test jednostkowy pokrywający przypadek loss=0.
5) Nie zmieniaj innych zachowań biznesowych.
Po zmianach uruchom testy związane z PriceService i pokaż diff.
```

### Prompt 2 — warmup_cache bez CASH
```text
Popraw backend/price_service.py: warmup_cache ma ignorować CASH i puste tickery.
Wymagania:
1) Zmień SQL w warmup_cache na wersję filtrującą ticker IS NOT NULL oraz ticker != 'CASH'.
2) Zachowaj dotychczasowe logowanie.
3) Dodaj test (lub zaktualizuj istniejący), który potwierdza, że get_prices nie dostaje CASH z warmup_cache.
4) Nie wprowadzaj zmian poza tym zakresem.
Uruchom odpowiednie testy i pokaż wynik.
```

### Prompt 3 — get_quotes fallback po błędzie bulk
```text
Uzupełnij fallback w backend/price_service.py::get_quotes na wypadek wyjątku w bulk download.
Wymagania:
1) Każdy ticker z wejścia ma być obecny w słowniku wynikowym (nawet po totalnej awarii bulk).
2) W fallbacku zaimplementuj per-ticker próbę pobrania danych LUB minimum bezpieczny placeholder.
3) Jeśli brak danych, zwracaj price=None i wszystkie change_* jako None.
4) Dodaj test, który wymusza wyjątek w bulk i sprawdza kompletność odpowiedzi.
5) Nie zmieniaj publicznego formatu odpowiedzi.
Uruchom testy PriceService.
```

### Prompt 4 — price None zamiast 0.0 przy no-data
```text
Popraw backend/price_service.py::get_quotes, aby brak danych cenowych nie był reprezentowany jako 0.0.
Wymagania:
1) We wszystkich gałęziach no-data/error ustaw price=None (zamiast 0.0).
2) Zachowaj None dla change_1d/change_7d/change_1m/change_1y.
3) Dodaj/zmień testy, aby rozróżniały brak danych od prawidłowej liczby.
4) Sprawdź, czy serializacja/API kontrakt nadal działa poprawnie.
Uruchom testy i przedstaw ewentualne miejsca zależne od starej semantyki 0.0.
```

### Prompt 5 — precyzyjny log UPSERT
```text
Popraw komunikat logowania w backend/price_service.py::sync_stock_history.
Wymagania:
1) Ponieważ używany jest UPSERT (INSERT + UPDATE), komunikat nie może mówić "Inserted ... new history rows".
2) Zmień tekst na "Upserted {n} history rows (new + refreshed)" albo równoważny.
3) Nie zmieniaj logiki liczenia rowcount.
4) Dodaj test/asercję logu jeśli istnieje infrastruktura testów logowania.
Uruchom testy związane z sync_stock_history.
```

### Prompt 6 — thread safety cache
```text
Wprowadź thread-safety dla cache w backend/price_service.py.
Wymagania:
1) Dodaj dedykowany lock (lub locki) dla _price_cache/_price_cache_updated_at oraz _metadata_cache/_metadata_cache_updated_at.
2) Obejmij lockiem wszystkie zapisy i kluczowe sekwencje read-modify-write.
3) Zminimalizuj czas trzymania locka (bez ciężkich wywołań sieciowych pod lockiem).
4) Dodaj test(y) konkurencyjne lub przynajmniej deterministyczny test regresji dla spójności cache.
5) Nie zmieniaj zewnętrznego API klasy PriceService.
Uruchom testy PriceService.
```

### Prompt 7 — datetime.utcnow deprecacja
```text
Zastąp użycie datetime.utcnow() w backend/price_service.py wersją timezone-aware.
Wymagania:
1) Użyj datetime.now(timezone.utc).
2) Dodaj brakujący import timezone.
3) Zachowaj dotychczasowy format zapisu daty (jeśli wymagany przez DB/API).
4) Przejrzyj plik pod kątem podobnych użyć i popraw spójnie.
Uruchom testy modułu.
```

### Prompt 8 — fromtimestamp z timezone
```text
Popraw backend/price_service.py::fetch_market_events, aby fromtimestamp był jawnie w UTC.
Wymagania:
1) Użyj datetime.fromtimestamp(ts, tz=timezone.utc) dla earningsTimestamp i exDividendDate.
2) Zachowaj format końcowy YYYY-MM-DD.
3) Dodaj test regresyjny potwierdzający stabilność względem lokalnej strefy serwera.
Uruchom testy związane z fetch_market_events.
```

### Prompt 9 — market day i święta
```text
Rozszerz backend/price_service.py::_latest_expected_market_day o obsługę dni wolnych rynku.
Wymagania:
1) Zachowaj obecną logikę weekendową jako fallback.
2) Dodaj warstwę kalendarza sesyjnego (np. exchange_calendars) albo adapter konfigurowalny per rynek.
3) Jeśli zależność zewnętrzna jest zbyt ciężka, przygotuj prosty interfejs i implementację minimalną z możliwością podmiany.
4) Dodaj testy dla weekendu i przykładowego święta (np. 25 grudnia).
Opisz kompromisy i wpływ na częstotliwość sync.
```

### Prompt 10 — poprawna definicja change_1y
```text
Popraw backend/price_service.py::get_quotes w liczeniu change_1y.
Wymagania:
1) Nie licz change_1y, jeśli historia jest krótsza niż sensowny próg (np. ~250 sesji) — wtedy ustaw None.
2) Alternatywnie: licz względem punktu najbliższego dacie today-365d; jeśli brak takiego zakresu, zwróć None.
3) Dodaj testy dla:
   - pełnego roku danych,
   - krótkiej historii (np. 60 sesji),
   - granicznego przypadku.
4) Zachowaj kompatybilność reszty pól odpowiedzi.
Uruchom testy modułu PriceService.
```

---

## Sugerowana kolejność wdrożenia
1. #3 fallback bulk (ryzyko brakujących danych w odpowiedzi)
2. #4 `price=None` (semantyka braków danych)
3. #1 RSI dzielenie przez zero
4. #10 `change_1y`
5. #2 `warmup_cache` bez `CASH`
6. #7 i #8 (strefy czasowe)
7. #5 (precyzja logów)
8. #6 (thread safety)
9. #9 (kalendarz świąt — ulepszenie)

Taka kolejność najpierw zabezpiecza poprawność danych zwracanych przez API, potem porządkuje stabilność i utrzymanie.
