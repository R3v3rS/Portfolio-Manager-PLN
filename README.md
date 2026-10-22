# Portfolio Manager (PLN)

Aplikacja do zarządzania budżetem domowym, kontami i rezerwami, inwestycjami, kredytami oraz majątkiem netto. Backend: Flask + SQLite. Frontend: React + TypeScript + Vite.

## Dokumentacja i instrukcja obsługi

Zacznij od [spisu dokumentacji](docs/README.md).

| Dokument | Zawartość |
|---|---|
| [Budżet na co dzień](docs/BUDZET_NA_CO_DZIEN_PL.md) | Zakup, rachunek, rezerwa, import i koniec miesiąca |
| [Asystent i analizy inwestycji](docs/AI_PORTFOLIO_ANALYSIS_MODULE_PL.md) | Historia przeglądów, plan udziałów, ETF, materiały autorów i koszty AI |
| [Instrukcja całej aplikacji](docs/INSTRUKCJA_OBSLUGI_PL.md) | Centrum finansów, portfele, strategie, PPK, obligacje, kredyty, analizy, cele, radar i narzędzia |
| [Szczegółowa instrukcja budżetu](docs/BUDZET_INSTRUKCJA_PL.md) | Pierwsze ustawienie, salda, limity, rachunki, rezerwy, media, importy, paragony, zwroty, prognoza i zamknięcie miesiąca |
| [Uruchamianie i kopie](docs/URUCHAMIANIE_I_KOPIE_PL.md) | Windows i uruchomienie ręczne, aktualizacja, przeniesienie danych, kopie i diagnostyka |
| [Architektura i model danych](docs/ARCHITEKTURA_I_MODEL_DANYCH_PL.md) | Zasady księgowania i obliczeń, ważne tabele, warstwy i API |
| [Najnowsza wersja](docs/LATEST_VERSION.md) | Zakres aktualnych zmian i ograniczenia analiz |

Instrukcje są po polsku. Przykłady korzystają z fikcyjnych kwot i kont; baza, paragony i prywatne raporty nie są publikowane.

## Główne możliwości

- Centrum finansów: majątek netto, płynność i konkretne sprawy do załatwienia.
- Budżet: kategorie i podkategorie, wspólne limity, domyślny plan, miesięczne wyjątki i kopiowanie na 3/6/12 miesięcy.
- Rachunki jednorazowe i cykliczne, raty przypisane do kont oraz powiązanie z istniejącymi płatnościami.
- Rezerwy na koszt z terminem, miesięczne pule prądu/wody i stałe odkładanie bez terminu.
- Konta, saldo początkowe poza dochodem, korekty oraz przelewy własne i do inwestycji.
- Import bankowego CSV, reguły kategorii i przelewów, paragony z lokalnym OCR na Windows, podział zakupów i zwroty.
- Prognoza 30/90/365 dni, źródła limitów, scenariusze i kontrola braków na poszczególnych kontach.
- Tempo wybranych kategorii oraz zamknięcie miesiąca z decyzją o pozostałym limicie.
- Akcje, ETF-y, IKE/IKZE, obligacje, oszczędności i PPK z właściwymi podsumowaniami.
- Import XTB CSV/XLSX Cash Operations, mapowanie symboli, strategie, transfery aktywów i archiwizacja.
- Rzeczywiste wyniki, analiza struktury i ryzyka, ceny ręczne oraz oznaczenia jakości wyceny.
- Zapisane przeglądy, asystent inwestora, symulacja dopłaty, częściowy skład ETF i analiza treści artykułów.
- Cele, dziennik inwestora, radar, publiczne pomysły inwestycyjne i raport miesięczny.
- Kopie bazy oraz narzędzia spójności danych i historii cen.

## Uruchomienie lokalne

Backend wymaga Pythona 3.11 lub 3.12 zgodnego z `pandas==2.2.0`. Dla frontendu przygotuj Node i npm zgodne z zależnościami projektu.

Windows, terminal 1:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_local.py
```

Windows, terminal 2:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Otwórz `http://127.0.0.1:5173`. API działa na `http://127.0.0.1:5000`. Inicjalizacja backendu tworzy brakujący schemat w `backend/portfolio.db`; własną bazę zachowaj przed aktualizacją.

Na przygotowanym lokalnym środowisku Windows można użyć `scripts/start-local.ps1` i `scripts/stop-local.ps1`. Skrypt startu zakłada lokalny runtime Codex oraz istniejące zależności i bazę — na nowym komputerze użyj uruchomienia ręcznego lub dostosuj jego ścieżki. Szczegóły, także dla Linux/macOS, są w [instrukcji uruchamiania](docs/URUCHAMIANIE_I_KOPIE_PL.md).

AI jest opcjonalne: ustaw `GEMINI_API_KEY` w `backend/.env`, uruchom ponownie backend i sprawdź model oraz limit kosztów w Asystencie. [Konfiguracja krok po kroku](docs/URUCHAMIANIE_I_KOPIE_PL.md#9-opcjonalne-uruchomienie-ai). Lokalne podsumowanie działa bez klucza. Generowanie AI przesyła wskazany kontekst do Google Gemini.

## Kontrola jakości

Frontend, z katalogu `frontend/`:

```bash
npm run check
npm run lint
npm test
npm run build
```

Backend, z katalogu `backend/` w przygotowanym środowisku Pythona:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Na środowisku z Bash można uruchomić `scripts/run_quality_gate.sh`, opcjonalnie z `PYTHON_BIN=python3.12`. [Dokumentacja techniczna](docs/ARCHITEKTURA_I_MODEL_DANYCH_PL.md) opisuje obszary, które należy sprawdzać po zmianach wspólnych obliczeń.

## Organizacja projektu

- `frontend/src/App.tsx` — trasy aplikacji.
- `frontend/src/pages/`, `frontend/src/components/` — widoki i komponenty.
- `frontend/src/api*.ts`, `http.ts`, `apiConfig.ts` — wspólna warstwa API; komponenty nie wykonują niezależnych żądań poza nią.
- `backend/app.py`, `database.py` — konfiguracja i baza.
- `backend/routes*.py`, `*_service.py`, `modules/` — domeny, księgowanie i analizy.
- `backend/tests/`, testy `*.test.ts(x)` — weryfikacja zachowania.
- `docs/` — aktualne instrukcje i referencje uzupełniające.

## Dane i ograniczenia

Baza SQLite, backupy, załączniki, klucze, logi i prywatne zrzuty pozostają lokalne. Kopia samej bazy nie zawiera plików paragonów; zachowaj również `backend/uploads/`.

Aplikacja nie wykonuje przelewów w banku ani zleceń u brokera. Prognoza jest symulacją, a analizy zależą od kompletności historii i aktualności wyceny. Lokalna konfiguracja nie jest gotowym publicznym systemem wieloużytkownikowym.

Starsze dokumenty audytowe znajdują się w [archiwum dokumentacji](docs/archive/README.md) i mogą opisywać wcześniejsze zachowanie. Obecne instrukcje znajdują się w [spisie dokumentacji](docs/README.md); szczegóły historycznej własności portfeli uzupełnia [PROJECT_GUIDE_PL.md](docs/PROJECT_GUIDE_PL.md).
