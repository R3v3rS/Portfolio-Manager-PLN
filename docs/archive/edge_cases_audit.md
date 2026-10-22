# Edge Cases & Validation Audit (Backend)

## Scope
Audit focused on backend validation gaps and unsafe assumptions related to:
- invalid inputs,
- boundary conditions,
- unexpected states,
- potential crashes.

---

## Missing validations, risks, and recommended fixes

### 1) Service layer accepts negative/zero money values when called outside HTTP routes
- **Where**: `PortfolioTradeService.deposit_cash`, `withdraw_cash`, `record_dividend`, `add_manual_interest`, `update_savings_rate` in `backend/portfolio_trade_service.py`.
- **Missing validation**:
  - No service-level guard for `amount > 0` in several write methods.
  - No guard for `new_rate >= 0` in `update_savings_rate`.
- **Risk**:
  - If service methods are called by internal jobs/tests/scripts (bypassing route validators), negative deposits can behave like withdrawals, negative withdrawals can mint cash, and negative interest/rate can silently corrupt balances.
- **Recommended fix**:
  - Add defensive checks in service methods (not only at route layer):
    - `if amount <= 0: raise ValueError(...)`
    - `if new_rate < 0: raise ValueError(...)`
  - Keep route validation, but treat service layer as trust boundary too.

### 2) Date fields are often only “non-empty strings”, not validated as ISO dates
- **Where**:
  - Portfolio endpoints pass raw strings into DB/service: buy/sell/deposit/withdraw/dividend/manual-interest (`backend/routes_transactions.py`, `backend/routes_portfolios.py`).
  - Budget routes pass `date`, `due_date`, `from_month`, `to_month` as unvalidated strings (`backend/routes_budget.py`).
- **Missing validation**:
  - No consistent `YYYY-MM-DD` (or `YYYY-MM`) parsing on many write paths.
- **Risk**:
  - Invalid date text reaches DB (`"2026-99-99"`, `"abc"`), and downstream logic that parses dates can crash (history, bonds, reporting).
  - Lexicographic date sorting in SQL can become semantically incorrect with malformed strings.
- **Recommended fix**:
  - Introduce shared helpers (`require_iso_date`, `require_year_month`) and use them on every write path.
  - Optionally enforce DB-level `CHECK` constraints for date formats where feasible.

### 3) `PPK` transactions accept invalid dates and non-sensical unit combinations
- **Where**: `PPKService.add_transaction` in `backend/modules/ppk/ppk_service.py`, route in `backend/routes_ppk.py`.
- **Missing validation**:
  - `tx_date` is accepted as any string.
  - `employeeUnits` and `employerUnits` can both be `0` (allowed by non-negative checks), producing no-op transactions.
- **Risk**:
  - Invalid `tx_date` may break weekly aggregation/parsing paths later.
  - Zero-unit transactions pollute data and can skew analytics/event counts.
- **Recommended fix**:
  - Validate `tx_date` as `YYYY-MM-DD` and reject future dates if business rules require.
  - Require at least one of `employeeUnits`, `employerUnits` to be strictly `> 0`.

### 4) Query param `current_price` can raise unhandled `ValueError` (500)
- **Where**: `get_ppk_transactions` in `backend/routes_ppk.py`.
- **Missing validation**:
  - `current_price = float(current_price_raw)` has no error handling.
- **Risk**:
  - Request like `?current_price=abc` triggers unhandled exception and returns 500 instead of 422.
- **Recommended fix**:
  - Parse with guarded conversion and return `ValidationError` (422) on bad numeric input.
  - Optionally require `current_price > 0`.

### 5) Bond purchase date is not validated on write and can crash on read
- **Where**:
  - Write path: `add_bond` in `backend/routes_portfolios.py` + `backend/bond_service.py`.
  - Read path: `BondService.get_bonds` parses with `datetime.strptime(..., '%Y-%m-%d')`.
- **Missing validation**:
  - `purchase_date` only checked as non-empty string when inserted.
- **Risk**:
  - Invalid `purchase_date` persists, then `get_bonds` can throw `ValueError` when parsing, causing endpoint failure.
- **Recommended fix**:
  - Validate `purchase_date` as ISO date at write time.
  - Add read-side fallback handling (skip/flag invalid records instead of hard crash).

### 6) Loan schedule engine trusts DB shape too much (unsafe assumptions)
- **Where**: `LoanService.calculate_schedule` in `backend/loan_service.py`.
- **Missing validation / unsafe assumption**:
  - Assumes `loan['duration_months'] > 0`, `loan['original_amount'] > 0`, valid `start_date`, and known `installment_type`.
  - Assumes every `rate['valid_from_date']` / `op['date']` parses correctly.
- **Risk**:
  - Corrupted/manual DB records can trigger crashes (`datetime.strptime`), nonsensical loops, or unstable schedule outputs.
- **Recommended fix**:
  - Normalize and validate loan/rate/overpayment records in service before calculation.
  - Fail fast with domain errors (`ValidationError`-style) instead of raw parsing exceptions.

### 7) Budget service methods rely on route validation; direct calls can violate invariants
- **Where**: `BudgetService` write methods (`add_income`, `allocate_money`, `spend`, `transfer_between_accounts`, `transfer_to_investment`, `withdraw_from_investment`, `borrow_from_envelope`, `repay_envelope_loan`) in `backend/budget_service.py`.
- **Missing validation**:
  - Service methods do not consistently enforce `amount > 0` or date format.
  - Some flows allow operations between same source/destination account without explicit no-op validation.
- **Risk**:
  - Internal callers can create negative transfers/spends or malformed dates, causing data corruption and misleading transaction history.
- **Recommended fix**:
  - Centralize service-level guards:
    - `assert_positive_amount(amount, field='amount')`
    - `parse_iso_date_or_raise(date)`
    - `if from_account_id == to_account_id: raise ValueError(...)` (if no-op transfers are disallowed).

### 8) Portfolio history pipeline can crash on malformed transaction dates
- **Where**: `PortfolioHistoryService._to_date` and `_calculate_historical_metrics` in `backend/portfolio_history_service.py`.
- **Missing validation**:
  - Assumes transaction dates are parseable `%Y-%m-%d` strings.
- **Risk**:
  - One malformed transaction date can fail historical metrics generation for an entire portfolio.
- **Recommended fix**:
  - Enforce date validation at transaction write time.
  - Add defensive parsing fallback in history layer (skip malformed rows + emit warning) to avoid total endpoint failure.

---

## High-priority remediation order
1. **Standardize date validation on all write endpoints** (portfolio, budget, ppk, bonds).
2. **Add service-layer amount/rate guards** so non-HTTP callers cannot bypass invariants.
3. **Harden parsing points** (`PPK current_price`, bonds/history date parsing) to return controlled 4xx or partial-safe responses.
4. **Add regression tests** for:
   - negative/zero amounts,
   - malformed dates,
   - invalid query numeric inputs,
   - corrupted DB row resilience in schedule/history computations.

## Suggested test cases to add
- POST buy/sell/deposit/withdraw/dividend with invalid date strings => 422.
- POST PPK transaction with both unit fields `0` => 422.
- GET PPK transactions with `current_price=abc` => 422 (not 500).
- Create bond with invalid `purchase_date` => 422.
- Seed malformed transaction date in DB, call history endpoint => endpoint stays up and reports/ignores bad row safely.
