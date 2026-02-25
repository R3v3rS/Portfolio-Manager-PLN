# 📈 Portfolio Manager (PLN)

Profesjonalna aplikacja webowa do zarządzania portfelem inwestycyjnym, zbudowana w nowoczesnym stosie technologicznym **React + Flask**. System został zaprojektowany z myślą o inwestorach operujących w walucie PLN, oferując zaawansowaną analitykę, śledzenie dywidend oraz inteligentne buforowanie danych giełdowych.

## 🚀 Główne Funkcje

- **Zarządzanie Portfelami**: Tworzenie wielu niezależnych portfeli (np. Emerytalny, Akcyjny, Krypto).
- **Inteligentne Pobieranie Cen**: Integracja z Yahoo Finance (`yfinance`) z obsługą GPW (`.WA`), Frankfurtu (`.F`) i rynków światowych.
- **Pamięć Podręczna (Price Caching)**: Lokalna baza danych historycznych cen zamknięcia, eliminująca luki w danych (weekendy, święta) i drastycznie przyspieszająca działanie.
- **System Dywidendowy**: Rejestrowanie wpływów z dywidend, automatyczna aktualizacja salda gotówkowego i wykresy miesięcznego dochodu pasywnego.
- **Analityka Wizualna**:
  - Interaktywne wykresy wydajności dla każdej pozycji.
  - Wykresy kołowe alokacji aktywów (akcje vs gotówka).
  - Statystyki Profit/Loss (Zysk/Strata) w czasie rzeczywistym.
- **Historia Transakcji**: Pełny log operacji Kupna, Sprzedaży, Depozytów i Dywidend.

## 🛠 Stos Technologiczny

- **Frontend**: React 18, TypeScript, Tailwind CSS, Chart.js, Lucide Icons, Vite.
- **Backend**: Flask (Python 3.11+), SQLite, Pandas, yfinance.
- **Architektura**: Clean Code, separacja logiki biznesowej (Services) od warstwy prezentacji (Routes).

## 📁 Struktura Projektu

```
.
├── backend/            # Serwer Flask API
│   ├── app.py          # Punkt wejścia aplikacji
│   ├── database.py     # Definicje schematów SQLite
│   ├── routes.py       # Endpointy API
│   ├── services.py     # Logika biznesowa i analityka finansowa
│   └── requirements.txt
├── frontend/           # Aplikacja React (Vite)
│   ├── src/
│   │   ├── components/ # Reaktywne komponenty UI (Wykresy, Formularze)
│   │   ├── pages/      # Widoki (Dashboard, Szczegóły Portfela)
│   │   ├── api.ts      # Konfiguracja Axios
│   │   └── types.ts    # Interfejsy TypeScript
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
