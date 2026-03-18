# 📈 Portfolio Manager (PLN)

Portfolio Manager (PLN) to aplikacja webowa do zarządzania finansami osobistymi i inwestycjami.
Projekt łączy w jednym miejscu:

- portfele inwestycyjne,
- budżet domowy,
- kredyty i symulacje nadpłat,
- dashboard majątku netto,
- radar inwestycyjny,
- moduł PPK.

Aplikacja działa w architekturze **frontend + backend**:

- **Frontend**: React + TypeScript (Vite),
- **Backend**: Flask + SQLite.

---

## 🎯 Co potrafi aplikacja

### 💼 Portfel inwestycyjny
- Tworzenie wielu portfeli (np. emerytalny, akcyjny, krypto).
- Operacje gotówkowe i transakcyjne: wpłata, wypłata, kupno, sprzedaż, dywidendy.
- Obsługa różnych klas aktywów (akcje, ETF-y, krypto, obligacje, oszczędności).
- Historia wartości portfela i historii zysku.
- Watchlista oraz aktualizacja cen rynkowych.
- Import transakcji z plików CSV (XTB).

### 👷 PPK
- Rejestracja transakcji PPK,
- Podsumowanie wartości jednostek,
- Obliczenia podatkowe i kalkulacyjne w module dedykowanym (`backend/modules/ppk`).

### 🏠 Budżet domowy
- Zarządzanie kontami i historią transakcji.
- Kategorie przychodów i wydatków.
- Limity miesięczne per kategoria.
- Transfery pomiędzy budżetem a portfelem inwestycyjnym.

### 🏦 Kredyty
- Tworzenie i zarządzanie kredytami.
- Harmonogramy spłat.
- Obsługa zmian oprocentowania i nadpłat.
- Analiza kosztu całkowitego i skrócenia okresu kredytowania.

### 📊 Dashboard i radar
- Przegląd majątku netto (aktywa, gotówka, zobowiązania).
- Przekrojowe wykresy wartości i zysków.
- Radar inwestycyjny i porównania instrumentów.

---

## ⚙️ Jak działa aplikacja (w skrócie)

1. Użytkownik korzysta z interfejsu React (`frontend/src`).
2. Frontend wysyła żądania HTTP do API Flask (`/api/...`).
3. Endpointy (`routes_*.py`) delegują logikę do warstwy serwisowej (`*_service.py`).
4. Serwisy zapisują/odczytują dane z bazy SQLite (`backend/portfolio.db`).
5. Część danych rynkowych (np. ceny) jest pobierana z zewnętrznych źródeł (m.in. `yfinance`) i cache’owana.

---

## 🧱 Stos technologiczny

### Frontend
- React 18
- TypeScript
- Vite
- Tailwind CSS
- Recharts + Chart.js
- React Router
- Zustand
- Axios

### Backend
- Flask
- Flask-CORS
- SQLite
- Pandas
- yfinance
- python-dotenv

---

## 🗂️ Struktura projektu

```text
.
├── backend/
│   ├── app.py                    # Punkt startowy API Flask i rejestracja blueprintów
│   ├── database.py               # Inicjalizacja połączeń i schematu SQLite
│   ├── routes.py                 # Endpointy portfela i operacji inwestycyjnych
│   ├── routes_budget.py          # Endpointy budżetu domowego
│   ├── routes_loans.py           # Endpointy kredytów
│   ├── routes_dashboard.py       # Endpointy dashboardu majątku
│   ├── routes_radar.py           # Endpointy radaru inwestycyjnego
│   ├── portfolio_service.py      # Logika portfeli i transakcji inwestycyjnych
│   ├── budget_service.py         # Logika budżetowa
│   ├── loan_service.py           # Logika kredytowa
│   ├── bond_service.py           # Logika obligacji
│   ├── watchlist_service.py      # Logika watchlisty
│   ├── price_service.py          # Pobieranie i synchronizacja cen
│   ├── math_utils.py             # Funkcje pomocnicze obliczeń
│   └── modules/ppk/              # Moduł domenowy PPK
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Routing aplikacji
│   │   ├── pages/                # Główne widoki (dashboardy, portfele, radar itp.)
│   │   ├── components/           # Komponenty UI (w tym moduły budget/ i loans/)
│   │   ├── services/             # Usługi po stronie frontendu
│   │   ├── api*.ts               # Warstwa komunikacji z backendem
│   │   ├── hooks/                # Własne hooki React
│   │   ├── types.ts              # Typy danych
│   │   └── lib/                  # Narzędzia pomocnicze
│   └── package.json
│
├── docs/
│   ├── ARCHITECTURE_FLOW.md      # Szczegółowy opis przepływów, zależności i onboardingu
│   └── ARCHITECTURE_REVIEW.md    # Notatki o jakości i spójności architektury
│
└── README.md
```

---

## ✅ Wymagania

- **Python** 3.11+
- **Node.js** 18+
- **npm** 9+

---

## 🚀 Uruchomienie lokalne

### 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows PowerShell

pip install -r requirements.txt
python app.py
```

API będzie dostępne pod adresem: `http://127.0.0.1:5000`.

Przykładowy endpoint health-check:
- `GET /` → `{"status": "healthy", "message": "Portfolio Manager API is running"}`

### 2) Frontend

W drugim terminalu:

```bash
cd frontend
npm install
npm run dev
```

Aplikacja będzie dostępna pod adresem: `http://localhost:5173`.

---

## 📚 Dokumentacja dla developerów

Jeśli zaczynasz pracę z repo, poza tym README zajrzyj od razu do:

- `docs/ARCHITECTURE_FLOW.md` — szczegółowy opis działania backendu i frontendu, przepływów requestów, zależności między plikami, diagramu zależności oraz krótkiego onboardingu dla nowych developerów.
- `docs/ARCHITECTURE_REVIEW.md` — przegląd jakości architektury, najważniejszych problemów i rekomendowanych usprawnień.

Najlepsza ścieżka wejścia do projektu:

1. przeczytaj ten `README.md`,
2. otwórz `backend/app.py` i `frontend/src/App.tsx`,
3. przejdź do `docs/ARCHITECTURE_FLOW.md`,
4. wybierz jeden moduł (`portfolio`, `budget`, `loans`, `radar`) i prześledź go end-to-end.

---

## 🧪 Komendy developerskie

### Frontend

```bash
cd frontend
npm run dev      # uruchomienie w trybie developerskim
npm run build    # build produkcyjny
npm run check    # TypeScript type-check
npm run lint     # lintowanie kodu
npm run preview  # podgląd buildu
```

### Backend

```bash
cd backend
python app.py
```

> Uwaga: repozytorium nie zawiera jeszcze pełnego zestawu testów automatycznych backendu.

---

## 🔌 Główne grupy endpointów API

- `/api/portfolio/*` — portfele, transakcje, wycena, PPK, obligacje, import.
- `/api/budget/*` — konta budżetowe, transfery, transakcje i limity.
- `/api/loans/*` — kredyty, harmonogramy, symulacje i nadpłaty.
- `/api/dashboard/*` — agregacje danych do dashboardu majątku.
- `/api/radar/*` — radar inwestycyjny.

Najlepsze źródło prawdy dla payloadów i odpowiedzi: pliki `backend/routes*.py`.

---

## 🧠 Notatki implementacyjne

- CORS jest włączony globalnie po stronie backendu.
- Baza danych (`portfolio.db`) jest tworzona/inicjalizowana automatycznie.
- Przy starcie backend wykonuje warmup cache cen rynkowych.
- Architektura serwisowa (`*_service.py`) oddziela logikę biznesową od warstwy HTTP.

---

## 📝 Licencja

MIT.
