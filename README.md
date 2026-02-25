# Portfolio Manager (PLN)

A production-ready web application for managing investment portfolios, built with React (Frontend) and Flask (Backend).

## Features

- **Portfolio Management**: Create multiple portfolios, track cash and holdings.
- **Transaction Tracking**: Buy/Sell stocks, Deposit/Withdraw cash.
- **Real-time Valuation**: Fetches latest stock prices (PLN) from Yahoo Finance (cached daily).
- **Analytics**: Profit/Loss calculation, Allocation charts, Performance metrics.
- **Clean Architecture**: Separation of concerns, type-safe frontend, modular backend.

## Tech Stack

- **Frontend**: React, TypeScript, Tailwind CSS, Chart.js, Axios, Vite.
- **Backend**: Flask, SQLite, yfinance, Pandas.
- **Database**: SQLite (local file).

## Project Structure

```
.
├── backend/            # Flask Backend
│   ├── app.py          # Application Factory & Startup
│   ├── database.py     # Database Connection & Schema
│   ├── routes.py       # API Endpoints
│   ├── services.py     # Business Logic & Price Fetching
│   ├── portfolio.db    # SQLite Database (generated on run)
│   └── requirements.txt
├── frontend/           # React Frontend
│   ├── src/
│   │   ├── components/ # Reusable UI Components
│   │   ├── pages/      # Page Views
│   │   ├── api.ts      # API Client
│   │   └── types.ts    # TypeScript Interfaces
│   └── package.json
└── README.md
```

## Prerequisites

- Node.js (v18+)
- Python (v3.11+)

## Setup & Run

### 1. Backend Setup

Open a terminal in the root directory:

```bash
cd backend
# Create virtual environment (optional but recommended)
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

The backend will start at `http://127.0.0.1:5000`.

### 2. Frontend Setup

Open a **new terminal** in the root directory:

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will start at `http://localhost:5173`.

## Usage

1. Open `http://localhost:5173` in your browser.
2. **Create a Portfolio**: Click "Create Portfolio" and enter a name (e.g., "Retirement").
3. **Deposit Cash**: Go to Portfolio Details -> "Deposit" tab.
4. **Buy Stocks**: Go to "Buy" tab, enter Ticker (e.g., "AAPL", "GOOGL", "CDR.WA" for Polish stocks), Quantity, and Price (in PLN).
   - Note: Since the app forces PLN, ensure you enter the PLN equivalent price if buying foreign stocks, or use Polish tickers (e.g., "PKO.WA").
5. **View Analytics**: Check the Dashboard for total value and the Details page for allocation charts.

## License

MIT
