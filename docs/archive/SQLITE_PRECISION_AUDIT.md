# SQLite Financial Precision Audit (Portfolio-Manager-PLN)

## 1) Schema analysis: numeric columns with float-risk

SQLite does not enforce fixed-point decimal semantics for `DECIMAL(p,s)` declarations.
In this project, declared `DECIMAL` columns have NUMERIC affinity, and arithmetic/aggregations can be evaluated with IEEE-754 floating point internally.
This creates drift risk for financial values when values are repeatedly updated, multiplied, divided, or summed.

### Problematic columns (from `backend/database.py`)

| Table | Column | Declared type | Financial meaning | Risk |
|---|---|---:|---|---|
| portfolios | current_cash | DECIMAL(10,2) | cash balance | HIGH |
| portfolios | total_deposits | DECIMAL(10,2) | principal tracking | HIGH |
| portfolios | savings_rate | DECIMAL(5,2) | rate used in interest calc | MEDIUM |
| ppk_transactions | employee_units | DECIMAL(14,6) | units | MEDIUM |
| ppk_transactions | employer_units | DECIMAL(14,6) | units | MEDIUM |
| ppk_transactions | price_per_unit | DECIMAL(14,6) | unit price | HIGH |
| transactions | quantity | DECIMAL(10,4) | position size | HIGH |
| transactions | price | DECIMAL(10,2) | trade price | HIGH |
| transactions | total_value | DECIMAL(10,2) | cash movement per tx | HIGH |
| transactions | realized_profit | DECIMAL(10,2) | realized PnL | HIGH |
| transactions | commission | DECIMAL(10,2) | fee | HIGH |
| holdings | quantity | DECIMAL(10,4) | open quantity | HIGH |
| holdings | average_buy_price | DECIMAL(10,2) | average cost | HIGH |
| holdings | total_cost | DECIMAL(10,2) | basis value | HIGH |
| holdings | avg_buy_price_native | REAL | native currency average cost | HIGH |
| holdings | avg_buy_fx_rate | REAL | FX conversion factor | HIGH |
| stock_prices | close_price | DECIMAL(10,2) | EOD price | MEDIUM |
| price_cache | price | DECIMAL(12,4) | live-ish price cache | MEDIUM |
| radar_cache | price | DECIMAL(10,2) | snapshot price | MEDIUM |
| radar_cache | change_1d / 7d / 1m / 1y | DECIMAL(10,2) | percent/amount changes | MEDIUM |
| radar_cache | dividend_yield | DECIMAL(10,6) | yield metric | LOW |
| dividends | amount | DECIMAL(10,2) | cash income | HIGH |
| bonds | principal | DECIMAL(15,2) | invested amount | HIGH |
| bonds | interest_rate | DECIMAL(5,2) | coupon/rate | MEDIUM |
| loans | original_amount | DECIMAL(15,2) | loan principal | HIGH |
| loan_rates | interest_rate | DECIMAL(5,2) | variable rate | MEDIUM |
| loan_overpayments | amount | DECIMAL(15,2) | extra payments | HIGH |
| budget_accounts | balance | DECIMAL(15,2) | account cash | HIGH |
| envelopes | target_amount | DECIMAL(10,2) | budget target | MEDIUM |
| envelopes | balance | DECIMAL(10,2) | envelope balance | HIGH |
| budget_transactions | amount | DECIMAL(15,2) | budget movement | HIGH |
| envelope_loans | amount | DECIMAL(15,2) | borrowed amount | HIGH |
| envelope_loans | repaid_amount | DECIMAL(15,2) | repaid amount | HIGH |
| inflation_data | index_value | REAL | reference index | LOW |

## 2) Code-level risk detection (where drift accumulates)

### High-risk calculation paths

1. **Repeated float conversion from DB + arithmetic in Python**
   - `float(...)` conversion appears throughout valuation and history flows.
   - This can reintroduce binary fraction artifacts after every read.

2. **Multiplication hot spots (`price * quantity`)**
   - Portfolio valuation multiplies quantity, market price, and FX rate, then applies fee factors.
   - Multi-factor products are the highest drift source.

3. **Currency conversion (`amount * fx_rate`)**
   - FX paths rely on float quotes and float multiplication; small errors amplify when recomputed daily.

4. **Aggregation (`SUM`, derived averages)**
   - SQL `SUM(total_value)`, `SUM(amount)`, and derived averages (`SUM(total_cost)/SUM(quantity)`) can diverge from per-row rounded expectations.

### Concrete code hotspots

- `portfolio_valuation_service.py`:
  - float conversion and accumulation of transaction amounts.
  - weighted aggregation and average cost via SQL `SUM` and division.
  - FX-based valuation: `qty * p_now * fx_now * (1 - fee_rate)` and related day/week deltas.
- `routes_history.py`:
  - transaction state machine does repeated float accumulation (`open_qty`, `cost_basis_open`, `realized_profit`) across historical rows.
- `budget_service.py`:
  - balances are repeatedly incremented/decremented through SQL updates and then aggregated with `SUM` and `float` conversions.

## 3) SQL queries to detect precision inconsistencies

> Run these against a production snapshot first (read-only), then compare frequencies and max error bands.

### A. Trade total mismatch (`quantity * price` vs stored `total_value`)

```sql
SELECT
  id,
  portfolio_id,
  ticker,
  quantity,
  price,
  total_value,
  ROUND(quantity * price, 2) AS recomputed_total,
  ROUND(total_value - ROUND(quantity * price, 2), 6) AS delta
FROM transactions
WHERE ABS(total_value - ROUND(quantity * price, 2)) > 0.009
ORDER BY ABS(delta) DESC;
```

### B. Holdings consistency (`quantity * average_buy_price` vs `total_cost`)

```sql
SELECT
  id,
  portfolio_id,
  ticker,
  quantity,
  average_buy_price,
  total_cost,
  ROUND(quantity * average_buy_price, 2) AS recomputed_cost,
  ROUND(total_cost - ROUND(quantity * average_buy_price, 2), 6) AS delta
FROM holdings
WHERE ABS(total_cost - ROUND(quantity * average_buy_price, 2)) > 0.009
ORDER BY ABS(delta) DESC;
```

### C. Portfolio cash consistency (flow-derived vs stored `current_cash`)

```sql
WITH tx AS (
  SELECT
    portfolio_id,
    COALESCE(SUM(CASE WHEN type IN ('DEPOSIT','INTEREST') THEN total_value ELSE 0 END), 0)
    - COALESCE(SUM(CASE WHEN type = 'WITHDRAW' THEN total_value ELSE 0 END), 0) AS flow_cash
  FROM transactions
  GROUP BY portfolio_id
)
SELECT
  p.id,
  p.name,
  p.current_cash,
  ROUND(tx.flow_cash, 2) AS flow_cash_rounded,
  ROUND(p.current_cash - ROUND(tx.flow_cash, 2), 6) AS delta
FROM portfolios p
LEFT JOIN tx ON tx.portfolio_id = p.id
WHERE ABS(p.current_cash - ROUND(COALESCE(tx.flow_cash, 0), 2)) > 0.009
ORDER BY ABS(delta) DESC;
```

### D. Budget account reconciliation drift

```sql
WITH tx AS (
  SELECT
    account_id,
    COALESCE(SUM(CASE WHEN type IN ('INCOME','TRANSFER','REPAY') THEN amount ELSE 0 END), 0)
    - COALESCE(SUM(CASE WHEN type IN ('EXPENSE','ALLOCATE','BORROW') THEN amount ELSE 0 END), 0) AS ledger_balance
  FROM budget_transactions
  WHERE account_id IS NOT NULL
  GROUP BY account_id
)
SELECT
  a.id,
  a.name,
  a.balance,
  ROUND(COALESCE(tx.ledger_balance, 0), 2) AS ledger_balance_rounded,
  ROUND(a.balance - ROUND(COALESCE(tx.ledger_balance, 0), 2), 6) AS delta
FROM budget_accounts a
LEFT JOIN tx ON tx.account_id = a.id
WHERE ABS(a.balance - ROUND(COALESCE(tx.ledger_balance, 0), 2)) > 0.009
ORDER BY ABS(delta) DESC;
```

### E. Detect latent float artifacts (more than 2 decimal places in money fields)

```sql
SELECT 'transactions.total_value' AS field, COUNT(*) AS bad_rows
FROM transactions
WHERE ABS(total_value * 100 - ROUND(total_value * 100)) > 1e-8
UNION ALL
SELECT 'transactions.realized_profit', COUNT(*)
FROM transactions
WHERE ABS(realized_profit * 100 - ROUND(realized_profit * 100)) > 1e-8
UNION ALL
SELECT 'holdings.total_cost', COUNT(*)
FROM holdings
WHERE ABS(total_cost * 100 - ROUND(total_cost * 100)) > 1e-8
UNION ALL
SELECT 'budget_accounts.balance', COUNT(*)
FROM budget_accounts
WHERE ABS(balance * 100 - ROUND(balance * 100)) > 1e-8;
```

### F. PPK precision check (unit-price-value consistency)

```sql
SELECT
  id,
  portfolio_id,
  employee_units,
  employer_units,
  price_per_unit,
  ROUND((employee_units + employer_units) * price_per_unit, 2) AS recomputed_value
FROM ppk_transactions
WHERE ABS(((employee_units + employer_units) * price_per_unit) - ROUND(((employee_units + employer_units) * price_per_unit), 2)) > 1e-8
ORDER BY id DESC;
```

## 4) Concrete drift examples

1. Binary-float primitive:
   - `0.1 + 0.2` becomes `0.30000000000000004` in IEEE-754.

2. Trade drift scenario:
   - 10,000 micro-trades where each computed value carries hidden `~1e-10` residue.
   - Periodic `SUM(total_value)` can end up off by multiple grosz/cents, causing reconciliation failures.

3. PnL mismatch scenario:
   - `profit_loss = current_value - total_cost` computed daily with float prices and FX rates.
   - Recomputed history can differ from previously persisted realized profit snapshots by 0.01–0.10 over long periods.

4. FX compounding scenario:
   - `qty * asset_price_usd * usdpln * (1-fee)` recalculated each day.
   - Three float multipliers + fee factor introduce tiny day-level errors that appear as noisy PnL changes unrelated to market movement.

## 5) Fix recommendations (specific)

## Option A — Store money as INTEGER minor units (cents/grosz)

- Add integer columns for all money amounts (`*_minor`, scale=100).
- For 4dp prices/FX derived values, use scale=10,000 where needed.
- Pros: deterministic arithmetic in SQL, exact sums, stable reconciliations.
- Cons: schema + code migration effort.

## Option B — Enforce rounding at write time

- On all write paths, quantize money to 2dp and units to defined scale before insert/update.
- Add DB constraints (CHECK) to reject over-precision values.
- Pros: low migration effort.
- Cons: still float internals in calculations/aggregates.

## Option C — Move calculations to application layer Decimal

- Keep DB storage but never compute using Python float.
- Convert DB values to `Decimal(str(value))`, compute, quantize, write.
- Pros: predictable financial math.
- Cons: SQL aggregate operations remain risk points unless replaced.

## Option D — Hybrid (recommended)

1. **Money ledger fields** (`transactions.total_value`, `realized_profit`, `commission`, `dividends.amount`, budget balances): migrate to INTEGER minor units.
2. **Rates/quotes/analytics** (`radar_cache`, `price_cache`, optional market prices): keep as DECIMAL/REAL but treat as non-ledger and round on output.
3. **Application math**: all business calculations in `Decimal`, only convert to float for API serialization.
4. **Reconciliation jobs**: nightly checks using the SQL in section 3 + alerts on threshold.

## 6) Safe migration strategy

### Step 1 — Add parallel columns (non-breaking)

Example for `transactions`:

```sql
ALTER TABLE transactions ADD COLUMN total_value_minor INTEGER;
ALTER TABLE transactions ADD COLUMN realized_profit_minor INTEGER;
ALTER TABLE transactions ADD COLUMN commission_minor INTEGER;
```

### Step 2 — Backfill with explicit rounding policy

Policy recommendation:
- money: `ROUND_HALF_UP` to 2dp, then multiply by 100 and cast to integer.
- units: keep decimal scale (e.g., 6dp) or use integer micro-units (x1_000_000) for strict determinism.

Backfill sample:

```sql
UPDATE transactions
SET total_value_minor = CAST(ROUND(total_value * 100, 0) AS INTEGER),
    realized_profit_minor = CAST(ROUND(realized_profit * 100, 0) AS INTEGER),
    commission_minor = CAST(ROUND(commission * 100, 0) AS INTEGER)
WHERE total_value_minor IS NULL;
```

### Step 3 — Dual-write in application

- For one release window, write both legacy DECIMAL and new INTEGER columns.
- Read path should prefer INTEGER columns when present.

### Step 4 — Reconciliation gate

- Compare old vs new derived outputs for each portfolio/day.
- Fail migration if `abs(old_value - new_value) > 0.01` for ledger fields (or stricter threshold you define).

### Step 5 — Switch reads + freeze legacy writes

- Read only INTEGER minor-unit columns for ledger logic.
- Keep legacy columns for backward compatibility in API payloads (computed as `minor/100.0`).

### Step 6 — Cleanup (optional)

- After 1-2 stable release cycles, deprecate legacy columns from core logic.
- Keep migration view if older reports depend on old names.

## 7) Priority rollout order

1. Transactions + holdings + portfolios cash (highest impact on PnL and reconciliation).
2. Budget module balances and transactions.
3. Loan/bond cashflow tables.
4. Optional: market cache/analytics tables.

---

## Immediate next actions for this repository

1. Add automated audit endpoint/job executing queries from section 3.
2. Convert high-risk valuation/history flows to Decimal-first arithmetic (`portfolio_valuation_service.py`, `routes_history.py`, `budget_service.py`).
3. Introduce minor-unit columns for ledger tables and run staged migration.
