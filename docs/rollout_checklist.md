# Rollout checklist (staging 3–7 dni)

> Cel: codzienna, powtarzalna obserwacja jakości integracji po wdrożeniu zmian logowania yfinance.

## Zakres monitoringu
- Endpoint/metryki: `/monitoring/stats`
- Dodatkowy sygnał: rozmiar pliku `backend/logs/backend.log`
- Okres rekomendowany: minimum **3 dni**, docelowo **5–7 dni**

## Progi i interpretacja (skrót)
- `error_rate_percent` w normalnym użyciu: **< 10%**
- `backend/logs/backend.log` przyrost: **< 50 MB/dobę**
- Jedna dominująca kategoria w `errors_by_type` przez dłuższy czas: potencjalny problem systemowy
- `requests_per_minute`: bez nienaturalnych spadków/skoków względem wcześniejszego baseline

---

## Dzień 1 — baseline po wdrożeniu
1. Czy `error_rate_percent` jest **< 10%** dla typowego ruchu?
2. Czy `requests_per_minute` wygląda „normalnie” (zbliżone do wcześniejszych wartości staging)?
3. Czy w `errors_by_type` nie dominuje pojedynczy nowy typ błędu?
4. Czy `last_errors` nie pokazuje nowych, nieznanych wcześniej klas błędów?
5. Czy aplikacja (API/UI) odpowiada bez zauważalnych opóźnień?
6. Czy przyrost `backend/logs/backend.log` po 24h nie przekracza 50 MB?

## Dzień 2 — stabilność dobową
1. Czy `error_rate_percent` utrzymuje się **< 10%** przez cały dzień, a nie tylko punktowo?
2. Czy `requests_per_minute` nie ma anomalii (nagłe „dołki” lub piki bez przyczyny testowej)?
3. Czy rozkład `errors_by_type` jest zróżnicowany i zgodny z oczekiwanym profilem?
4. Czy wpisy w `last_errors` są znane i opisane (brak „nowych niespodzianek”)?
5. Czy użytkowe ścieżki aplikacji nie zwalniają w godzinach większego ruchu?
6. Czy przyrost `backend/logs/backend.log` (dzień do dnia) pozostaje < 50 MB/dobę?

## Dzień 3 — weryfikacja trendu
1. Czy średnia z 3 dni dla `error_rate_percent` pozostaje **< 10%**?
2. Czy `requests_per_minute` jest stabilne i spójne z wykorzystaniem środowiska?
3. Czy `errors_by_type` nie wskazuje utrwalonej dominacji jednego błędu (sygnał problemu systemowego)?
4. Czy `last_errors` nie zawiera nowych typów błędów krytycznych?
5. Czy obserwujemy brak regresji wydajności (czasy odpowiedzi, odczuwalna płynność pracy)?
6. Czy `backend/logs/backend.log` nadal rośnie poniżej 50 MB/dobę?

## Dzień 4–5 (zalecane) — potwierdzenie przed GO/NO-GO
1. Czy `error_rate_percent` przez kolejne dni pozostaje **< 10%** w normalnym użyciu?
2. Czy `requests_per_minute` pozostaje przewidywalne względem baseline i planowanych testów?
3. Czy w `errors_by_type` brak nowego dominującego typu błędu?
4. Czy `last_errors` nie pokazuje nowych klas błędów o nieznanej przyczynie?
5. Czy aplikacja nie zwalnia (subiektywnie + obserwacje techniczne)?
6. Czy przyrost `backend/logs/backend.log` pozostaje < 50 MB/dobę?

## Dzień 6–7 (opcjonalnie) — rozszerzona obserwacja
1. Czy utrzymuje się trend: `error_rate_percent < 10%` bez epizodów destabilizacji?
2. Czy `requests_per_minute` i liczba błędów rosną proporcjonalnie (brak nietypowej degradacji przy większym ruchu)?
3. Czy `errors_by_type` i `last_errors` są powtarzalne i zrozumiałe operacyjnie?
4. Czy brak oznak „cichego” problemu: wolniejsze odpowiedzi, większy log volume, wzrost ostrzeżeń?

---

## Rejestr obserwacji (do ręcznego wypełniania)
| Dzień | error_rate_percent | requests_per_minute (zakres) | dominujący `errors_by_type` | nowe wpisy w `last_errors` (TAK/NIE + opis) | przyrost `backend.log` MB/dobę | aplikacja zwalnia? (TAK/NIE) | Wniosek dnia |
|---|---:|---|---|---|---:|---|---|
| 1 |  |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |
| 4 |  |  |  |  |  |  |  |
| 5 |  |  |  |  |  |  |  |
| 6 (opc.) |  |  |  |  |  |  |  |
| 7 (opc.) |  |  |  |  |  |  |  |

## Warunek przejścia do decyzji GO/NO-GO
- Co najmniej 3 dni obserwacji zakończone bez czerwonych flag.
- Brak nowych crashy aplikacji.
- `error_rate_percent < 10%` w normalnym użyciu.
- Przyrost `backend.log < 50 MB/dobę`.
- Brak trwałej dominacji jednego nowego typu błędu w `errors_by_type`.
