# Szablon notatki GO/NO-GO przed wdrożeniem produkcyjnym

> Dokument do ręcznego wypełnienia po obserwacji stagingowej.

## 1) Dane podstawowe
- Data obserwacji (od): ____________________
- Data obserwacji (do): ____________________
- Środowisko: ____________________
- Osoba odpowiedzialna: ____________________
- Wersja / commit: ____________________

## 2) Zmierzone wartości kluczowych metryk (wpisać liczby)

### Z `/monitoring/stats`
- Średni `error_rate_percent`: __________ %
- Maksymalny `error_rate_percent`: __________ %
- Średnie `requests_per_minute`: __________
- Minimalne `requests_per_minute`: __________
- Maksymalne `requests_per_minute`: __________
- Dominujący typ w `errors_by_type` (nazwa + udział %): ____________________
- Liczba nowych/nieznanych błędów w `last_errors`: __________

### Z logów backendu
- Rozmiar `backend/logs/backend.log` na początku obserwacji: __________ MB
- Rozmiar `backend/logs/backend.log` na końcu obserwacji: __________ MB
- Obliczony przyrost na dobę: __________ MB/dobę

### Stabilność aplikacji
- Liczba crashy aplikacji: __________
- Subiektywna ocena wydajności (krótko): ____________________
- Czy wykryto spowolnienia API/UI? (TAK/NIE + opis): ____________________

## 3) Kryteria akceptacji (TAK/NIE)

1. Brak nowych crashy aplikacji: [ ] TAK  [ ] NIE  
   Uwagi: ____________________

2. `error_rate_percent < 10%` w normalnym użyciu: [ ] TAK  [ ] NIE  
   Wartość/e: ____________________

3. `backend.log` rośnie poniżej `50 MB/dobę`: [ ] TAK  [ ] NIE  
   Wartość: ____________________

4. Wszystkie testy z zadań 3–8 nadal przechodzą: [ ] TAK  [ ] NIE  
   Lista testów + wynik: ____________________

## 4) Decyzja
- **Decyzja:** [ ] GO   [ ] NO-GO
- **Powód / uwagi:**

____________________________________________________________

____________________________________________________________

## 5) Plan działań po decyzji (opcjonalnie)
- Jeśli GO: plan wdrożenia produkcyjnego (okno czasowe + owner): ____________________
- Jeśli NO-GO: lista poprawek i termin ponownej oceny: ____________________
