# Uruchamianie, aktualizacja i kopie danych

[Spis dokumentacji](README.md) · [Instrukcja obsługi](INSTRUKCJA_OBSLUGI_PL.md)

## 1. Co musi działać

Aplikacja ma dwa lokalne serwery: backend Flask pod `http://127.0.0.1:5000` i frontend Vite pod `http://127.0.0.1:5173`. W przeglądarce otwierasz frontend. Backend obsługuje dane i bazę SQLite.

Backend w `app.py` wybiera `backend/portfolio.db` względem własnego pliku. Dwie kopie repozytorium mogą mieć dwie różne bazy o tej samej nazwie. Uruchomienie innego folderu może więc pokazać pustą lub starszą historię, choć poprzednia baza nadal istnieje.

Przed pracą sprawdź folder wypisany przy uruchomieniu oraz wskazaną bazę. Nie zamieniaj plików bazy w trakcie działania serwera.

## 2. Dotychczasowe skróty na Windows

Jeżeli masz przygotowane skróty na pulpicie, skrót włączania uruchamia backend i frontend, a skrót wyłączania zatrzymuje ich rozpoznane procesy. Wyłączenie nie usuwa bazy. Zamknięcie samej karty przeglądarki nie zatrzymuje serwerów.

Skróty są lokalne i wskazują konkretny folder projektu. Po przeniesieniu repozytorium trzeba poprawić ich ścieżki. Nie są uniwersalnym instalatorem aplikacji z GitHuba.

Skrypty w repozytorium:

```powershell
# Z katalogu głównego projektu
.\scripts\start-local.ps1
.\scripts\start-local.ps1 -NoBrowser
.\scripts\start-local.ps1 -CheckOnly
.\scripts\stop-local.ps1 -CheckOnly
.\scripts\stop-local.ps1
```

Obecny `start-local.ps1` używa przygotowanego runtime Pythona w profilu użytkownika Codex, Node z `Program Files`, istniejących zależności frontendu i istniejącej bazy. Nie instaluje ich sam. Na innym komputerze dostosuj ścieżki lub skorzystaj z uruchomienia ręcznego poniżej.

Skrypt startu sprawdza zajętość portów i stan usług; nie uruchamia ponownie gotowego serwera na tym samym porcie. Nie weryfikuje jednak przez sam adres HTTP, że już działająca aplikacja korzysta z oczekiwanego folderu — przy kilku kopiach najpierw sprawdź proces/folder.

Skrypt zatrzymywania używa lokalnego pliku `.local-servers.json`, sprawdza tożsamość procesu, jego czas rozpoczęcia, program i argumenty. Nie zatrzymuje wszystkich procesów Python/Node na komputerze. Serwery uruchomione ręcznie zatrzymaj w ich terminalach przez `Ctrl+C`.

## 3. Pierwsze uruchomienie na nowym komputerze

Backend wymaga zgodnego Pythona 3.11 lub 3.12 ze względu na przypięty `pandas==2.2.0`. Node i npm muszą spełniać wymagania zależności w `frontend/package.json` i pliku blokady. Zainstaluj je przed poniższymi krokami.

### Windows — backend

W terminalu PowerShell, w katalogu repozytorium:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_local.py
```

Użyj instalacji Pythona dostępnej na swoim komputerze, jeśli polecenie `py -3.12` nie jest dostępne. `run_local.py` wiąże serwer z lokalnym adresem i wyłącza tryb automatycznego ponownego uruchamiania. Pierwszy start tworzy brakujące tabele; nie tworzy Twojej osobistej historii.

### Windows — frontend

W drugim terminalu, zaczynając z katalogu repozytorium:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Otwórz `http://127.0.0.1:5173`. Przy standardowej konfiguracji Vite przekazuje lokalne żądania `/api` do backendu. `VITE_API_BASE_URL` pozwala wskazać inną bazę API; po zmianie konfiguracji uruchom frontend ponownie.

### Linux/macOS — ręcznie

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_local.py
```

W drugim terminalu uruchom frontend tak samo przez `npm ci` i `npm run dev -- --host 127.0.0.1 --port 5173 --strictPort`. Lokalny OCR paragonów korzysta z Windows OCR; na innych systemach dane paragonu można uzupełniać ręcznie.

## 4. Co jest Twoimi danymi

| Miejsce | Zawartość |
|---|---|
| `backend/portfolio.db` | Portfele, transakcje, konta, budżet, kredyty, plany i pozostałe dane aplikacji |
| `backend/backups/` | Lokalne kopie SQLite |
| `backend/uploads/` | Przesłane pliki, w tym oryginały paragonów |
| `backend/logs/` oraz pliki `*.log` | Diagnostyka; może zawierać informacje o operacjach |
| Lokalne `.env` | Konfiguracja i ewentualne klucze usług |

Kopia samej bazy **nie zawiera zdjęć paragonów zapisanych na dysku**. Do pełnego przeniesienia lub archiwum zachowaj również `backend/uploads/`, a potrzebną konfigurację przechowuj osobno. Nie dołączaj jej do publicznego repozytorium.

## 5. Kopie automatyczne i ręczne

W **Centrum narzędzi → Kopie bazy** możesz utworzyć ręczną kopię, przejrzeć listę i pobrać wybraną. Usługa używa kopii SQLite, sprawdza integralność oraz wymagane tabele i relacje.

Przy uruchomieniu backendu sprawdzana jest kopia dzienna, najwyżej jedna dla danego dnia, oraz kopia przed aktualizacją, gdy zmieni się sygnatura kodu. Podczas zwykłej pracy kontrola kopii dziennej jest wykonywana także przed obsługą żądań: pierwsze żądanie w nowym dniu może utworzyć kopię bez restartu. Sam upływ czasu przy bezczynnym serwerze nie uruchamia kopii. Nie jest to kopia wykonywana co godzinę ani po każdej transakcji.

Automatyczna retencja pozostawia do 14 kopii dziennych i 10 kopii aktualizacji. To liczby kopii, nie gwarancja zachowania każdego kalendarzowego dnia. Warto zachować ważną kopię ręczną także poza katalogiem aplikacji.

Przed większą korektą historii, scalaniem, resetem lub przywróceniem wykonaj kopię ręczną. Nie usuwaj jedynej kopii, z której właśnie odzyskujesz dane.

## 6. Przywracanie i przeniesienie

Przywrócenie wybranej kopii w narzędziach odtwarza **całą bazę**. Zmiany późniejsze niż kopia nie będą częścią odtworzonych danych. Przed przywróceniem aplikacja zapisuje kopię ratunkową bieżącej bazy, a po przywróceniu sama inicjalizuje schemat aktualnego kodu i czyści obsługiwane pamięci podręczne. Błąd inicjalizacji powoduje odtworzenie kopii ratunkowej. Po udanej operacji odśwież widoki; restart nie jest wymagany do wykonania tej inicjalizacji. Przy ręcznej podmianie pliku bazy wykonaj procedurę zatrzymania i uruchomienia poniżej.

Przy ręcznym przeniesieniu:

1. Wykonaj i sprawdź kopię w aplikacji.
2. Zatrzymaj oba serwery.
3. Zachowaj obecną bazę docelową oraz załączniki.
4. Umieść wybraną bazę jako `backend/portfolio.db` w folderze, z którego uruchomisz aplikację. Nie kopiuj wyłącznie części tabel.
5. Przenieś potrzebne `backend/uploads/` i konfigurację.
6. Uruchom aplikację i sprawdź salda, liczbę wpisów, powiązania oraz dostępność załączników.

Podczas działania SQLite mogą występować pliki `-wal` i `-shm`. Do kopii działającej bazy używaj funkcji aplikacji; zwykłe kopiowanie samego `.db` w trakcie zapisu może nie objąć całości zmian.

## 7. Aktualizacja z GitHuba

1. Zapisz kopię i zatrzymaj serwery.
2. Sprawdź lokalne zmiany przez `git status`; nie nadpisuj ich bez zachowania.
3. Pobierz zatwierdzone zmiany na używanej gałęzi, np. `git pull --ff-only`.
4. Jeśli zmieniły się zależności, uaktualnij je: `npm ci` w `frontend/` oraz instalacja `requirements.txt` w swoim środowisku backendu.
5. Uruchom serwery i sprawdź dane oraz komunikaty migracji.

Kod wysłany na gałąź PR jest już na GitHubie, ale nie musi jeszcze być w `main`. Wybierz właściwą gałąź, jeśli chcesz sprawdzić niezłączoną wersję. Pliki bazy i załączniki są lokalne i nie pojawią się po samym pobraniu kodu.

## 8. Diagnozowanie uruchomienia

| Problem | Co sprawdzić |
|---|---|
| Strona nie otwiera się | Czy frontend działa na 5173 i czy polecenie nie zakończyło się błędem? |
| Strona jest, ale dane się nie ładują | Czy backend działa na 5000? Sprawdź komunikat żądania i log serwera |
| Pusta historia po uruchomieniu | Folder działającego backendu i jego `portfolio.db` |
| Port jest zajęty | Czy działa inna kopia aplikacji? Nie zatrzymuj przypadkowych procesów |
| Brak modułu Pythona lub paczki JS | Właściwy interpreter i instalacja zależności w tym środowisku |
| Paragon nie odczytuje tekstu | Dostępność Windows OCR i języków; wpisz dane ręcznie, gdy lokalny OCR jest niedostępny |
| Dane wyglądają na stare | Odśwież widok i sprawdź datę notowania, a nie tylko czas uruchomienia aplikacji |

Przy starcie przez skrypty czytaj `backend/local-backend.stderr.log`, `backend/local-backend.stdout.log` i analogiczne logi frontendu. Backend zapisuje także `backend/logs/backend.log`. W ręcznym uruchomieniu błędy są widoczne w terminalach.

## 9. Opcjonalne uruchomienie AI

Lokalne podsumowania inwestycji działają bez klucza. Aby włączyć generowanie odpowiedzi, zainstaluj aktualne `requirements.txt`, utwórz lub uzupełnij `backend/.env` i uruchom ponownie backend:

```dotenv
GEMINI_API_KEY=TU_WSTAW_WLASNY_KLUCZ
# Opcjonalny model domyślny, przed pierwszym zapisem ustawień:
# GEMINI_MODEL=gemini-3.1-flash-lite
```

Klucza nie wpisuj w konfigurację frontendu ani do repozytorium. W portfelu otwórz **Asystent → Ustawienia AI i limit kosztów** i sprawdź status konfiguracji, model, stawki i dzienny limit. Limit 0 wyłącza generowanie. Zapisane ustawienia mają pierwszeństwo przed domyślnym modelem ze środowiska.

Wybranie **Analizuj z AI** wysyła pytanie i wskazany kontekst finansowy do Google Gemini. **Przygotuj szkic AI** wysyła treść materiału wybraną do analizy. Odczyt zapisów i lokalne podsumowanie nie uruchamiają generowania. [Instrukcja analiz](AI_PORTFOLIO_ANALYSIS_MODULE_PL.md) opisuje podgląd danych, koszty i bezpieczne ponowienia; limit aplikacji jest szacunkiem i nie zastępuje kontroli rozliczeń u dostawcy.

## 10. Kontrola wersji przed publikacją

Frontend: `npm run check`, `npm run lint`, `npm test` i `npm run build` w `frontend/`. Backend: instalacja `requirements-dev.txt` i `python -m pytest -q` w środowisku z zależnościami, z katalogu `backend/` oraz dostępnymi jego modułami w `PYTHONPATH`.

Na systemie z Bash dostępny jest `scripts/run_quality_gate.sh`. Dla nietypowego interpretera wskaż `PYTHON_BIN`. Testy domenowe używają odrębnych baz; część testów tworzy aplikację i może uruchamiać jej standardową inicjalizację, dlatego kopia bazy pozostaje przydatna również przed szerszą kontrolą.
