# 📈 Portfolio Manager (PLN)

Profesjonalna aplikacja webowa do kompleksowego zarządzania finansami osobistymi, zbudowana w nowoczesnym stosie technologicznym **React + Flask**. System integruje zarządzanie portfelem inwestycyjnym, budżetem domowym oraz zobowiązaniami kredytowymi, oferując zaawansowaną analitykę i wizualizację danych.

## 🚀 Główne Funkcje

### 💼 Portfel Inwestycyjny
- **Zarządzanie Portfelami**: Tworzenie wielu niezależnych portfeli (np. Emerytalny, Akcyjny, Krypto, Obligacje).
- **Inteligentne Pobieranie Cen**: Integracja z Yahoo Finance (`yfinance`) z obsługą GPW (`.WA`), rynków zagranicznych i kryptowalut.
- **Pamięć Podręczna (Price Caching)**: Lokalna baza danych historycznych cen zamknięcia, eliminująca luki w danych i przyspieszająca działanie.
- **System Dywidendowy**: Rejestrowanie wpływów z dywidend, automatyczna aktualizacja salda gotówkowego i wykresy dochodu pasywnego.
- **Obsługa Różnych Aktywów**: Akcje, ETF-y, Kryptowaluty, Obligacje Skarbowe/Korporacyjne.

### 🏠 Budżet Domowy
- **Śledzenie Wydatków**: Kategoryzacja transakcji (Jedzenie, Transport, Mieszkanie, itp.).
- **Planowanie Budżetu**: Ustawianie miesięcznych limitów dla kategorii.
- **Analiza Wydatków**: Wykresy struktury wydatków i trendów miesięcznych.
- **Historia Transakcji**: Szczegółowy rejestr wpływów i wydatków.

### 🏦 Symulator Kredytowy
- **Kalkulator Rat**: Symulacja harmonogramu spłat kredytu hipotecznego/gotówkowego.
- **Nadpłaty**: Analiza wpływu nadpłat na koszt całkowity i okres kredytowania.
- **Wizualizacja**: Wykresy spłaty kapitału vs odsetek w czasie.

### 📊 Analityka Wizualna
- Interaktywne wykresy wydajności portfela (Recharts, Chart.js).
- Wykresy kołowe alokacji aktywów i dywersyfikacji.
- Statystyki Profit/Loss (Zysk/Strata) w czasie rzeczywistym.
- Dashboard podsumowujący majątek netto (Net Worth).

## 🛠 Stos Technologiczny

- **Frontend**: 
  - React 18, TypeScript, Vite
  - Tailwind CSS (stylowanie)
  - Recharts, Chart.js (wizualizacja danych)
  - Zustand (zarządzanie stanem)
  - React Router (nawigacja)
  - Lucide Icons (ikony)
- **Backend**: 
  - Flask (Python 3.11+)
  - SQLite (baza danych)
  - Pandas (analiza danych finansowych)
  - yfinance (dane giełdowe)
- **Architektura**: Clean Code, separacja logiki biznesowej (Services) od warstwy prezentacji (Routes).

## 📁 Struktura Projektu

```
.
├── backend/            # Serwer Flask API
│   ├── app.py          # Punkt wejścia aplikacji
│   ├── database.py     # Definicje schematów SQLite
│   ├── routes*.py      # Endpointy API (podział na moduły)
│   ├── services.py     # Logika biznesowa portfela
│   ├── budget_service.py # Logika budżetu domowego
│   ├── loan_service.py   # Logika symulatora kredytowego
│   └── bond_service.py   # Obsługa obligacji
├── frontend/           # Aplikacja React (Vite)
│   ├── src/
│   │   ├── components/ # Komponenty UI
│   │   │   ├── budget/ # Komponenty budżetu
│   │   │   ├── loans/  # Komponenty kredytowe
│   │   │   └── ...
│   │   ├── pages/      # Widoki (Dashboard, Portfele, Budżet)
│   │   ├── lib/        # Narzędzia pomocnicze (utils)
│   │   ├── hooks/      # Własne hooki React
│   │   └── api*.ts     # Klienty API (Axios)
│   └── package.json
└── README.md
```

## ⚙️ Instalacja i Uruchomienie

### 1. Backend (Python)
Wymagany Python 3.11+.

```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```
API będzie dostępne pod adresem: `http://127.0.0.1:5000`

### 2. Frontend (Node.js)
Wymagany Node.js 18+.

```bash
cd frontend
npm install
npm run dev
```
Aplikacja będzie dostępna pod adresem: `http://localhost:5173`

## 📊 Zaawansowana Logika
Aplikacja wykorzystuje algorytm **Incremental Sync** dla danych historycznych. Przy każdym zakupie lub wyświetleniu szczegółów, system sprawdza ostatnią datę zapisaną w lokalnej bazie i pobiera z Yahoo Finance tylko brakujący zakres dat. Chroni to przed limitami API i zapewnia błyskawiczne ładowanie wykresów.

## 📝 Licencja
Projekt udostępniany na licencji MIT.
