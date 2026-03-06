# Portfolio Module Documentation

## 1) Overview

The **portfolio module** is the investment domain of the application. It manages portfolio lifecycle, cash flows, asset transactions, valuation, and analytics in both backend and frontend layers.

At a system level:

- **Backend** (`backend/routes.py`, `backend/portfolio_service.py`) exposes HTTP endpoints under `/api/portfolio/*` and implements portfolio business rules.
- **Frontend** (pages/components under `frontend/src`) renders dashboard/list/detail experiences and calls the backend API via Axios.
- The module supports multiple account types: `STANDARD`, `IKE`, `BONDS`, `SAVINGS`, and `PPK`.

Although the only folder literally named `portfolio` is `frontend/src/components/portfolio`, the functional portfolio module spans all portfolio-related files listed below.

---

## 2) Portfolio-related folder and file structure

```text
backend/
  routes.py
  portfolio_service.py

frontend/src/
  api.ts
  types.ts
  pages/
    PortfolioDashboard.tsx
    PortfolioList.tsx
    PortfolioDetails.tsx
  components/
    PortfolioAnalytics.tsx
    PortfolioChart.tsx
    PortfolioHistoryChart.tsx
    PortfolioProfitChart.tsx
    portfolio/
      PerformanceHeatmap.tsx
```

---

## 3) File-by-file responsibilities

## Backend

### `backend/routes.py`
Controller layer for portfolio endpoints.

Main responsibilities:
- Maps HTTP routes to service operations (create/list/delete/deposit/withdraw/buy/sell).
- Exposes analytics/data endpoints:
  - `/value/<id>`, `/holdings/<id>`, `/transactions/<id>`
  - `/history/monthly/<id>`, `/history/profit/<id>`
  - `/dividends/monthly/<id>`, `/<id>/performance`
- Handles special flows:
  - CSV import (`/<id>/import/xtb`)
  - PPK transactions and summary (`/ppk/transactions*`)
  - Closed positions (`/<id>/closed-positions`)
- Translates exceptions to HTTP status codes and JSON errors.

### `backend/portfolio_service.py`
Core domain/service layer for portfolio business logic.

Key responsibility groups:

1. **Portfolio lifecycle & account operations**
   - `create_portfolio`, `list_portfolios`, `get_portfolio`, `delete_portfolio`, `is_portfolio_empty`
   - `deposit_cash`, `withdraw_cash`, `update_savings_rate`, `_capitalize_savings`

2. **Trading operations**
   - `buy_stock`, `sell_stock`
   - Updates both `transactions` and `holdings`, adjusts `current_cash`, computes realized P/L.

3. **Valuation and enrichment**
   - `get_holdings` enriches holdings with market prices, metadata (company/sector/industry), FX rates, estimated FX sell fee, current value, and per-holding P/L.
   - `get_portfolio_value` computes totals (`portfolio_value`, `cash_value`, `holdings_value`, dividends, result %, XIRR), with account-type-specific rules.

4. **History and analytics**
   - `_calculate_historical_metrics`: month-end reconstruction from transaction timeline.
   - `get_portfolio_history`: monthly portfolio value (optionally benchmark).
   - `get_portfolio_profit_history`: monthly cumulative profit.
   - `get_performance_matrix`: month-over-month and YTD returns (Modified Dietz style).

5. **Dividend and tax utility**
   - `record_dividend`, `get_dividends`, `get_monthly_dividends`
   - `get_tax_limits` for IKE/IKZE limit progress.

6. **XTB CSV import + symbol mapping**
   - `import_xtb_csv` parses imported rows and applies transactions atomically.
   - `resolve_symbol_mapping` / `resolve_symbol` map broker symbols to app tickers.
   - If mappings are missing, import is aborted with `missing_symbols` so frontend can collect user mappings.

7. **FX handling**
   - `_get_fx_rates_to_pln`, `_calculate_fx_fee`
   - Non-PLN assets are converted and include configured FX fee assumptions.

External backend dependencies used by service:
- `PriceService` (prices, metadata, historical sync)
- `BondService` (bond valuation)
- `PPKService` (PPK-specific summaries/price)
- `xirr` helper for annualized return
- SQLite DB via `get_db`

---

## Frontend

### `frontend/src/api.ts`
Axios client for the portfolio backend (`baseURL: /api/portfolio`).

### `frontend/src/types.ts`
Shared TypeScript contracts for portfolio domain entities (`Portfolio`, `Holding`, `Transaction`, `PortfolioValue`, `Bond`, `ClosedPosition`, etc.).

### `frontend/src/pages/PortfolioDashboard.tsx`
High-level investment dashboard.

Responsibilities:
- Loads portfolio list (`GET /list`) and tax limits (`GET /limits`) in parallel.
- Aggregates totals across all portfolios (value, deposits, dividends, result).
- Supports portfolio creation (`POST /create`).
- Displays account-wide cards + table of portfolios + IKE/IKZE progress bars.

### `frontend/src/pages/PortfolioList.tsx`
Portfolio catalog view.

Responsibilities:
- Fetches portfolio list (`GET /list`).
- Creates portfolios (`POST /create`).
- Deletes empty portfolios (`DELETE /:id`).
- Renders account-type badges and basic KPIs per portfolio card.

### `frontend/src/pages/PortfolioDetails.tsx`
Main orchestration page for a single portfolio.

Responsibilities:
- Loads full portfolio context (list lookup, holdings, value, dividends, transactions, closed positions, budget accounts).
- Handles account-type-specific tabs and fetches:
  - `BONDS`: bonds table
  - `SAVINGS`: savings-focused summary + history
  - `PPK`: PPK summary + contribution history
  - Standard/IKE: holdings, analytics, results heatmap, history, closed positions
- Contains action entry points/modals for transfers and transactions.
- Supports inline position close (sell all at current price).
- Handles ticker history fetch for selected asset.
- Includes CSV import flow with missing-symbol remediation:
  - Upload CSV
  - If backend returns `missing_symbols`, collect ticker/currency mappings
  - Save mappings via `symbolMapApi`
  - Retry import

### `frontend/src/components/PortfolioChart.tsx`
Compact pie allocation chart (cash + holdings) using `react-chartjs-2`.

### `frontend/src/components/PortfolioAnalytics.tsx`
Three pie charts (assets/sectors/industries) using `recharts`.

Features:
- Uses holding `current_value` when available.
- Includes cash as an allocation slice.

### `frontend/src/components/PortfolioHistoryChart.tsx`
Line chart of monthly portfolio value (and optional benchmark line) using `recharts`.

### `frontend/src/components/PortfolioProfitChart.tsx`
Line/area chart of cumulative profit history using `chart.js`.

Features:
- Positive/negative styling around zero line.

### `frontend/src/components/portfolio/PerformanceHeatmap.tsx`
The folder literally named `portfolio`.

Responsibilities:
- Calls `GET /<portfolioId>/performance`.
- Renders a year x month matrix with YTD column.
- Applies color semantics for positive/negative returns and loading/error/empty states.

---

## 4) Data flow inside the module

## A. Portfolio detail data load flow

1. User opens `/portfolio/:id`.
2. `PortfolioDetails` executes `fetchData()`.
3. It requests (in parallel):
   - `/list`
   - `/holdings/:id`
   - `/value/:id`
   - `/dividends/monthly/:id`
   - `/transactions/:id`
   - `/:id/closed-positions`
   - budget summary (from budget API)
4. Backend routes delegate to `PortfolioService` methods.
5. `PortfolioService` pulls DB state + price/metadata/FX data and calculates derived metrics.
6. Frontend binds returned data into tabs/cards/charts.

## B. Buy/sell transaction flow

1. User submits transaction (modal / quick close).
2. Frontend posts to `/buy` or `/sell`.
3. Backend `PortfolioService`:
   - validates funds/shares
   - converts currency to PLN
   - applies FX fee rules
   - writes transaction rows
   - updates holdings and cash
4. Frontend refreshes data (`fetchData`) so UI is consistent.

## C. Monthly analytics flow

1. Frontend requests:
   - `/history/monthly/:id`
   - `/history/profit/:id`
   - `/:id/performance`
2. Backend reconstructs month-end values from transactions via `_calculate_historical_metrics`.
3. Derived datasets are transformed for chart/matrix components.

## D. XTB CSV import flow

1. User uploads file from `ImportXtbCsvButton`.
2. Frontend posts multipart file to `/:id/import/xtb`.
3. Backend parses row-by-row and tries mapping broker symbols.
4. If mappings are missing:
   - backend returns `{ success: false, missing_symbols: [...] }`
   - frontend opens mapping modal
   - user saves mappings via `symbolMapApi.create`
   - frontend retries import
5. Successful import persists transactions/holdings in one DB transaction.

---

## 5) Key functions/components summary

### High-impact backend functions

- `get_portfolio_value` – canonical valuation endpoint logic across account types.
- `get_holdings` – enriches holdings with price, FX, metadata, profitability.
- `_calculate_historical_metrics` – base engine for all historical charts.
- `get_performance_matrix` – builds monthly/YTD return grid.
- `buy_stock` / `sell_stock` – transactional integrity for trades.
- `import_xtb_csv` – broker import and symbol mapping bridge.

### High-impact frontend components/pages

- `PortfolioDetails` – orchestration hub and state container.
- `PortfolioDashboard` – aggregate view and tax-limit visibility.
- `PerformanceHeatmap` – return matrix visualization.
- `PortfolioHistoryChart` + `PortfolioProfitChart` – trend and profitability narrative.
- `PortfolioAnalytics` – allocation decomposition by asset/sector/industry.

---

## 6) Dependencies between files

## Backend dependency direction

- `routes.py` → `PortfolioService`
- `PortfolioService` → `PriceService`, `BondService`, `PPKService`, DB

This keeps HTTP handling thin and business rules centralized.

## Frontend dependency direction

- Pages (`PortfolioDashboard`, `PortfolioList`, `PortfolioDetails`) → `api.ts` and domain `types.ts`
- `PortfolioDetails` → portfolio chart/analytics components + modal components
- `PerformanceHeatmap` (in `components/portfolio/`) → `api.ts`

`PortfolioDetails` is the integration point where most portfolio sub-components are composed.

---

## 7) External APIs/services used

- **Market data / metadata** via backend `PriceService`:
  - current prices
  - historical prices
  - ticker metadata (company/sector/industry)
  - FX tickers like `USDPLN=X`
- **PPK service** via `PPKService`:
  - current unit price
  - unit-based portfolio summary
- **SQLite database** via `get_db`:
  - portfolios, holdings, transactions, dividends, bonds, ppk tables, symbol mappings

---

## 8) Example execution flow: “load and display portfolio details”

1. User navigates to details page for portfolio `42`.
2. Frontend calls:
   - `/api/portfolio/list`
   - `/api/portfolio/holdings/42`
   - `/api/portfolio/value/42`
   - `/api/portfolio/dividends/monthly/42`
   - `/api/portfolio/transactions/42`
   - `/api/portfolio/42/closed-positions`
3. Backend service computes:
   - enriched holdings with pricing + FX
   - total valuation and result metrics
   - monthly dividend aggregates
   - transactions and closed-position rollup
4. Frontend renders:
   - summary KPI cards
   - allocation pie chart
   - holdings table and transaction history
   - optional account-specific tabs (bonds/savings/PPK/results)
5. User opens “Wartość Historyczna” tab:
   - frontend requests `/history/monthly/42` and `/history/profit/42`
   - charts render portfolio value trend + cumulative profit trend.

---

## 9) Notes on module boundaries

- Literal `portfolio` folder (`frontend/src/components/portfolio`) currently contains `PerformanceHeatmap.tsx` only.
- Practical/functional portfolio module boundary is broader and includes backend service/routes and portfolio pages/components.
- This split follows common architecture: domain logic in backend service, orchestration in page components, reusable visuals in components.
