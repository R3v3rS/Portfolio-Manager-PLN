# 📈 Portfolio Manager (PLN)

Aplikacja webowa do zarządzania finansami osobistymi oparta o **React + Flask**. Projekt łączy w jednym miejscu:
- portfel inwestycyjny,
- budżet domowy,
- symulator kredytowy,
- dashboard analityczny.

Repozytorium jest podzielone na frontend (Vite + React + TypeScript) i backend (Flask + SQLite).

---

## ✨ Najważniejsze funkcje

### 💼 Portfel inwestycyjny
- Tworzenie wielu portfeli (np. emerytalny, akcyjny, krypto).
- Rejestrowanie operacji: wpłata, wypłata, kupno, sprzedaż, dywidendy.
- Obsługa różnych klas aktywów: akcje, ETF-y, kryptowaluty, obligacje.
- Historia wartości portfela i historia zysków.
- Import transakcji (CSV XTB).

### 🏠 Budżet domowy
- Konta budżetowe i historia transakcji.
- Kategoryzacja wydatków i przychodów.
- Limity miesięczne per kategoria.
- Integracja przepływów pomiędzy budżetem i portfelem inwestycyjnym.

### 🏦 Kredyty
- Tworzenie kredytów i harmonogram spłat.
- Obsługa zmian oprocentowania w czasie.
- Nadpłaty i analiza wpływu na koszt całkowity oraz okres kredytowania.

### 📊 Dashboard i analityka
- Widok majątku netto (Net Worth).
- Zestawienie aktywów, gotówki i zobowiązań.
- Wizualizacje danych finansowych na wykresach.

---

## 🧱 Stos technologiczny

### Frontend
- React 18 + TypeScript
- Vite
- Tailwind CSS
- Recharts + Chart.js
- React Router
- Zustand

### Backend
- Flask
- SQLite
- Pandas
- yfinance

---

## 📁 Struktura projektu

```text
.
├── backend/
│   ├── app.py                  # Uruchomienie aplikacji Flask
│   ├── database.py             # Inicjalizacja i dostęp do SQLite
│   ├── portfolio_service.py    # Logika domenowa portfela inwestycyjnego
│   ├── budget_service.py       # Logika budżetu domowego
│   ├── loan_service.py         # Logika kredytów
│   ├── bond_service.py         # Obsługa obligacji
│   ├── price_service.py        # Pobieranie i synchronizacja cen
│   ├── watchlist_service.py    # Obsługa watchlisty
│   ├── routes.py               # Endpointy portfela
│   ├── routes_budget.py        # Endpointy budżetu
│   ├── routes_loans.py         # Endpointy kredytów
│   ├── routes_dashboard.py     # Endpointy dashboardu
│   └── routes_radar.py         # Endpointy radaru inwestycyjnego
├── frontend/
│   ├── src/
│   │   ├── components/         # Komponenty UI
│   │   ├── pages/              # Widoki aplikacji
│   │   ├── hooks/              # Własne hooki React
│   │   ├── lib/                # Utilsy
│   │   └── *.ts                # Typy i warstwa API
│   └── package.json
└── README.md
```

---

## ⚙️ Wymagania

- **Python** 3.11+
- **Node.js** 18+
- **npm** 9+

---

## 🚀 Szybki start (lokalnie)

### 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows PowerShell

pip install -r requirements.txt
python app.py
```

Backend uruchomi się domyślnie na: `http://127.0.0.1:5000`

### 2) Frontend

W osobnym terminalu:

```bash
cd frontend
npm install
npm run dev
```

Frontend uruchomi się domyślnie na: `http://localhost:5173`

---

## 🧪 Przydatne komendy developerskie

### Frontend

```bash
cd frontend
npm run dev      # tryb developerski
npm run build    # build produkcyjny
npm run check    # TypeScript type-check
npm run lint     # lint (ESLint)
```

### Backend

```bash
cd backend
python app.py
```

> Uwaga: projekt nie zawiera jeszcze pełnego zestawu testów automatycznych backendu.

---

## 🔌 Główne endpointy API (przykłady)

### Portfolio
- `GET /api/portfolio/list`
- `POST /api/portfolio/create`
- `POST /api/portfolio/buy`
- `POST /api/portfolio/sell`
- `GET /api/portfolio/value/<portfolio_id>`

### Budżet
- `GET /api/budget/accounts`
- `POST /api/budget/transactions`
- `POST /api/budget/transfer`

### Kredyty
- `GET /api/loans`
- `POST /api/loans`
- `POST /api/loans/<loan_id>/overpayments`

Dokładne payloady i odpowiedzi najlepiej sprawdzić bezpośrednio w plikach `routes_*.py`.

---

## 🧠 Notatki implementacyjne

- Część danych rynkowych jest pobierana przez `yfinance`.
- Backend korzysta z SQLite i warstwy usług (`*_service.py`) oddzielonej od warstwy endpointów (`routes*.py`).
- Frontend komunikuje się z backendem przez moduły API i typy TypeScript.

---

## 📝 Licencja

MIT.
