# Float Precision Audit (Backend Financial Calculations)

## Scope
Reviewed backend financial paths with focus on:
- float usage in money calculations
- rounding behavior and consistency
- accumulation/loop drift
- multiplication/division paths (`price * quantity`, FX, interest)

---

## Executive summary

The codebase mixes **three numeric models**:
1. `float` arithmetic in core trading, transfers, budgeting, and loans.
2. `Decimal` arithmetic in selected audit/rebuild and PPK modules.
3. SQLite `DECIMAL(...)` declarations (which SQLite does not enforce as exact decimal arithmetic by itself).

This creates a material risk of drift between runtime state (`current_cash`, holdings cost basis) and recomputed state over time, especially in repeated buy/sell/transfer/interest operations.

---

## High-risk findings

### 1) Core request parsing converts numeric inputs to `float`
**Location**: `backend/routes_portfolio_base.py` (`require_number`, `optional_number`).

**Problem**
- All incoming amounts/prices/quantities are parsed via `float(...)` before being passed deeper.
- This introduces binary floating representation error at the system boundary.

**Risk**: **High** (cross-cutting entry point for almost all financial writes).

**Concrete fix**
- Replace `require_number` with a decimal parser returning `Decimal` (e.g. from string input only), plus validation on that decimal value.
- Add helper variants:
  - `require_money(...) -> Decimal` quantized to `0.01`
  - `require_quantity(...) -> Decimal` quantized to `0.00000001` (or business-specific precision)
- Keep API responses as floats/strings if needed, but internal write path should remain Decimal until persistence.

---

### 2) Buy/sell path uses float math for cost basis and cash mutations
**Location**: `backend/portfolio_trade_service.py` (`buy_stock`, `sell_stock`, `_assert_holding_consistency`).

**Problem**
- Uses `float` for `unit_price_pln`, commission, `gross_cost`, `total_cost`, `new_avg_price`, `cost_basis`, `realized_profit`.
- Repeated operations accumulate rounding residue in holdings and cash.
- Consistency checks use epsilon tolerances (`0.001`, `0.000001`) instead of deterministic quantized arithmetic.

**Risk**: **High** (directly impacts P&L, average price, and available cash).

**Concrete fix**
- Convert entire buy/sell path to `Decimal`:
  - `quantity = q8(Decimal(...))`
  - `price = q4/q6` (instrument precision) and totals quantized to `0.01` for cash ledger.
- Explicitly quantize at domain boundaries:
  - transaction cash fields (`price`, `total_value`, `commission`, `realized_profit`) => `0.01`
  - holdings quantity/cost => higher precision (e.g. `0.00000001`).
- Remove float epsilon assertions; compare quantized Decimal values.

---

### 3) Transfer delete validation relies on float tolerance
**Location**: `backend/routes_transactions.py` (`delete_cash_transfer`).

**Problem**
- `abs(float(deposit_tx['total_value']) - amount) > 0.0001` used to match transfer pair values.
- Tolerance-based matching can hide malformed rows and makes behavior non-deterministic at precision boundaries.

**Risk**: **High** (money movement integrity).

**Concrete fix**
- Compare quantized Decimals instead:
  - `q2(withdraw_total) == q2(deposit_total)`
- Reject if exact cent-level mismatch.
- Prefer storing transfer amount once and validating both legs against that canonical value.

---

### 4) Savings interest capitalization uses float and deferred threshold
**Location**: `backend/portfolio_trade_service.py` (`_capitalize_savings`, `withdraw_cash` live-interest estimate).

**Problem**
- Interest computed as float: `cash * (rate / 100) * (days / 365.0)`.
- Posting only when `interest > 0.01` causes stepwise, threshold-sensitive behavior.
- Repeated daily calculations can drift and produce inconsistent cents.

**Risk**: **High** (cash balance drift over long horizons).

**Concrete fix**
- Compute interest in Decimal with explicit day-count and quantization policy.
- Maintain an unposted accrued-interest Decimal field (high precision), then post rounded cents deterministically.
- Define rounding mode (`ROUND_HALF_UP`) globally for money postings.

---

## Medium-risk findings

### 5) Portfolio history rolling engine uses float + ad hoc rounding
**Location**: `backend/portfolio_history_service.py` (`_apply_tx_to_rolling`, valuation loops, benchmark/inflation shares).

**Problem**
- Cash/invested capital and share counters updated repeatedly with float operations.
- Periodic `round(..., 10)` in loop is an anti-drift patch, not a true financial model.
- FX valuation path multiplies `qty * native_price * fx_rate` with float then subtracts fee.

**Risk**: **Medium** (analytics/visual drift, reconciliation noise vs ledger).

**Concrete fix**
- Use Decimal in rolling state.
- Quantize cash outputs to `0.01`, keep intermediate share counters at higher precision (`0.00000001`+).
- Define separate precision classes:
  - money: 2 dp
  - quantity/shares: 8 dp
  - rates/fx: 6–8 dp

---

### 6) Loan amortization engine uses float and rounds only for output rows
**Location**: `backend/loan_service.py` (`calculate_schedule`).

**Problem**
- Core calculations (`remaining_balance`, rates, installment formula, interest accumulation) use float.
- Rounding mostly occurs when appending schedule rows; internal state keeps float artifacts.
- Long schedules can accumulate cents error and produce end-of-loan residue behavior.

**Risk**: **Medium** (schedule accuracy and interest totals).

**Concrete fix**
- Migrate schedule engine to Decimal with explicit per-step quantization rules:
  - interest per period rounded to cents (if matching bank statements), or
  - high-precision internal calc + cent rounding on posting (must be documented).
- Add reconciliation assertions: sum(principal parts) == original amount (± 0.01 per policy).

---

### 7) Budget free-pool and account arithmetic uses floats
**Location**: `backend/budget_service.py` (`get_free_pool` and multiple balance updates).

**Problem**
- Free pool computed with `float(account['balance']) - float(sum_positive) - float(sum_negative)`.
- Frequent increment/decrement balance updates can drift by fractions over many operations.

**Risk**: **Medium** (budget integrity, less severe than trading P&L but user-visible).

**Concrete fix**
- Convert budget money math to integer cents or Decimal.
- If SQLite remains, store integer cents (`BIGINT`) for account/envelope balances and transaction amounts.

---

## Low-risk / structural findings

### 8) Mixed precision strategy across modules
**Location**: `backend/portfolio_core_service.py` vs float-heavy services.

**Problem**
- Core utilities provide Decimal helpers (`_to_decimal`, `_quantize_accounting`), but many critical services bypass them and use float.

**Risk**: **Low-to-Medium** (architectural inconsistency; enables future regressions).

**Concrete fix**
- Define a mandatory money math contract:
  - all write paths use Decimal helper APIs
  - lint/check rule or code review checklist disallowing raw `float` in financial write logic.

---

### 9) SQLite `DECIMAL` declarations may still behave as floating numeric affinity
**Location**: `backend/database.py` schema definitions.

**Problem**
- Columns are declared as `DECIMAL(...)`, but SQLite does not enforce fixed-point decimal semantics automatically.
- Without adapter/converter or integer-cents storage, values may be stored/processed with floating behavior.

**Risk**: **Low-to-Medium** (depends on insert/read patterns, but important long-term).

**Concrete fix**
- Preferred: migrate money columns to integer cents.
- Alternative: register sqlite adapters/converters for Decimal and serialize to TEXT for exact decimal storage.

---

## Inconsistent rounding strategy inventory

Current patterns observed:
- `round(x, 2)` in many output/price paths.
- `round(x, 10)` anti-drift in rolling history state.
- epsilon comparisons (`0.0001`, `0.001`, `0.000001`) for integrity checks.
- Decimal quantization in selected modules with `ROUND_HALF_UP`.

This is inconsistent and can produce different answers for mathematically equivalent flows.

**Recommended unification**
1. Adopt Decimal for all financial writes and ledger calculations.
2. Standardize quantizers:
   - `MONEY = Decimal('0.01')`
   - `QTY = Decimal('0.00000001')`
   - `RATE = Decimal('0.00000001')`
3. One rounding mode for finance (`ROUND_HALF_UP`) unless regulated otherwise.
4. Replace tolerance comparisons with quantized equality on domain precision.

---

## Prioritized remediation plan

1. **Boundary layer first (High impact)**
   - Replace `require_number` parsing strategy.
   - Introduce typed decimal input helpers (money/quantity/rate).

2. **Trading ledger write paths (High impact)**
   - Refactor `buy_stock`, `sell_stock`, transfer creation/deletion, savings interest.
   - Ensure cash and holdings are derived from quantized Decimal calculations.

3. **History and loans (Medium impact)**
   - Move rolling performance and amortization engines to Decimal.

4. **Storage hardening (Strategic)**
   - Plan migration to integer cents for money fields (or strict Decimal TEXT+adapters).

5. **Safety net**
   - Add regression tests for repeated micro-transactions (e.g., 10k small buys/sells) to detect drift.
   - Add invariants: `portfolio cash == recomputed cash` within cent precision only.

---

## Suggested implementation patterns

### A) Decimal helper module
- `to_dec(value) -> Decimal`
- `q_money(x)`, `q_qty(x)`, `q_rate(x)`
- `mul_money(a, b)` wrapper that quantizes deterministically.

### B) Integer-cents model (optional but robust)
- API accepts decimal strings.
- Convert to cents at boundary.
- Store/process as ints.
- Convert back only at response serialization.

### C) Testing scenarios to add
- Repeated buy/sell at fractional quantities.
- FX conversion round-trip (buy foreign asset, sell, compare expected vs actual cash).
- Savings interest accrual over long date ranges.
- Loan schedule sum checks for principal and interest reconciliation.

