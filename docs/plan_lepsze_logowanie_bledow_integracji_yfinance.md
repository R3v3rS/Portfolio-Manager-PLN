# Plan: Lepsze logowanie błędów integracji z zewnętrznymi dostawcami (yfinance)

## Cel
Ustandaryzować i pogłębić logowanie błędów związanych z integracją `yfinance`, tak aby:
- szybciej diagnozować awarie,
- odróżniać błędy chwilowe od trwałych,
- mieć pełny kontekst techniczny i biznesowy błędu,
- ograniczyć „nieme” fallbacki oraz rozproszone komunikaty `print`.

---

## Krok 1: Inwentaryzacja obecnych punktów integracji i logowania
1. Przejrzeć miejsca wywołań `yfinance` w `backend/price_service.py`.
2. Oznaczyć, które ścieżki:
   - używają `logging`/`logger`,
   - używają `print`,
   - łapią wyjątki bez pełnego kontekstu.
3. Zmapować krytyczne operacje:
   - bulk download,
   - per-ticker fallback,
   - `Ticker().history`,
   - `Ticker().info` (metadata).
4. Udokumentować wynik jako lista: *operacja → aktualny poziom logowania → luki*.

**Efekt:** jasna mapa miejsc wymagających poprawy.

---

## Krok 2: Zdefiniowanie standardu logów dla integracji zewnętrznych
1. Ustalić standard pól logowania (minimum):
   - `provider` (np. `yfinance`),
   - `operation` (np. `download_bulk`, `history`, `metadata`),
   - `ticker` lub `tickers_count`,
   - `attempt`, `max_attempts`,
   - `duration_ms`,
   - `status` (`success`, `retry`, `failed`, `partial`),
   - `error_type`, `error_message`,
   - `trace_id` / `request_id` (jeśli dostępne).
2. Ustalić poziomy logowania:
   - `DEBUG`: szczegóły techniczne, payload-size, parametry pomocnicze,
   - `INFO`: start i sukces operacji,
   - `WARNING`: retry / degradacja / częściowy sukces,
   - `ERROR`: twarda porażka operacji,
   - `EXCEPTION`: tylko tam, gdzie potrzebny pełny stack trace.
3. Opisać kiedy log ma być pojedynczy, a kiedy agregowany (np. 1 log dla 100 tickerów + logi tylko dla błędnych).

**Efekt:** jeden spójny kontrakt logowania dla całej integracji.

---

## Krok 3: Refaktoryzacja techniczna warstwy logowania
1. Zamienić `print(...)` w `backend/price_service.py` na `logger`.
2. Dodać helper do logów integracyjnych, np. `_log_provider_event(...)`, który:
   - przyjmuje ustandaryzowane pola,
   - wymusza spójny format,
   - zmniejsza duplikację kodu.
3. Rozdzielić wyjątki na klasy (jeśli możliwe), np.:
   - timeout/network,
   - throttling/rate-limit,
   - brak danych,
   - błędny ticker,
   - błędy parsowania DataFrame.
4. W retry (`_download_with_retry`) logować każdą próbę z numerem podejścia i czasem trwania.
5. Przy końcowej porażce dodawać podsumowanie wszystkich prób.

**Efekt:** mniej chaosu w kodzie i bardziej użyteczne logi.

---

## Krok 4: Lepszy kontekst biznesowy i operacyjny
1. Przy operacjach zbiorczych logować:
   - liczbę tickerów wejściowych,
   - liczbę sukcesów,
   - liczbę porażek,
   - listę porażek skróconą (np. top 10).
2. Dla fallbacku bulk → pojedyncze tickery:
   - log `WARNING` o aktywacji fallbacku,
   - log `INFO` o wyniku fallbacku (ile odzyskano danych).
3. Dla metadata (`info`) doprecyzować komunikaty:
   - cache hit / cache miss,
   - świeży fetch,
   - brak kluczowych pól (np. `sector`, `industry`).
4. Dodać metrykę czasu każdej ścieżki integracji (latency).

**Efekt:** logi przydatne nie tylko developerom, ale też w analizie jakości danych.

---

## Krok 5: Ochrona przed zalewem logów (noise control)
1. Wprowadzić ograniczenia liczby podobnych logów (rate limiting/log sampling) dla masowych błędów.
2. Grupować powtarzalne błędy w podsumowania okresowe (np. co N minut).
3. Ustawić sensowne poziomy domyślne dla środowisk:
   - local/dev: więcej `DEBUG`,
   - prod: domyślnie `INFO`, szczegóły przez feature flag.
4. Dodać przełącznik konfiguracyjny „verbose provider logs”.

**Efekt:** czytelne logi bez utraty sygnału diagnostycznego.

---

## Krok 6: Obsługa bezpieczeństwa i danych wrażliwych
1. Zweryfikować, czy logi nie zawierają danych wrażliwych ani nadmiarowych payloadów.
2. Maskować potencjalnie ryzykowne dane (gdyby pojawiły się w wyjątkach/response).
3. Ograniczyć długość logowanego `error_message` i surowych obiektów.

**Efekt:** zgodność operacyjna i mniejsze ryzyko wycieku danych.

---

## Krok 7: Testy i walidacja
1. Dodać testy jednostkowe dla helpera logowania:
   - poprawność pól,
   - poprawny poziom loga,
   - zachowanie przy brakujących opcjonalnych polach.
2. Dodać testy scenariuszowe (mock `yfinance`):
   - sukces bulk,
   - timeout + retry + sukces,
   - timeout + retry + porażka,
   - puste dane i fallback,
   - częściowy sukces dla wielu tickerów.
3. Wykonać test ręczny i przejrzeć logi pod kątem:
   - kompletności,
   - jednoznaczności,
   - szumu.

**Efekt:** pewność, że nowy standard działa i nie psuje istniejących ścieżek.

---

## Krok 8: Monitoring i alertowanie (opcjonalnie etap 2)
1. Jeśli jest stack observability (np. ELK/Grafana), dodać dashboard:
   - error rate per operation,
   - retry rate,
   - latency.
2. Dodać alerty:
   - wzrost `ERROR` dla `provider=yfinance`,
   - wysoki odsetek fallbacków,
   - brak danych cenowych > ustalony próg.
3. Ustalić runbook: co sprawdzić najpierw przy konkretnych alertach.

**Efekt:** szybsze reagowanie na problemy produkcyjne.

---

## Krok 9: Rollout i wdrożenie
1. Wdrożyć zmianę etapami (najpierw środowisko testowe/staging).
2. Przez 3–7 dni monitorować wolumen logów i jakość diagnostyki.
3. Skorygować poziomy logowania i sampling.
4. Po stabilizacji zaktualizować dokumentację techniczną.

**Efekt:** kontrolowane wdrożenie bez ryzyka przeciążenia logami.

---

## Definition of Done
- Brak `print` w krytycznych ścieżkach integracji `yfinance`.
- Każdy błąd integracji zawiera minimalny zestaw pól kontekstowych.
- Retry i fallback są jednoznacznie widoczne w logach.
- Istnieją testy dla głównych scenariuszy błędowych.
- Zespół potrafi na podstawie logów odtworzyć: co padło, gdzie, dlaczego i z jakim skutkiem biznesowym.
