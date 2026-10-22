# Edge Case Audit – Portfolio Manager

Date: 2026-04-04  
Role: Senior QA Engineer

## Scope
Focused review areas:
- empty data
- zero / negative values
- division by zero
- invalid states (e.g., sell without holdings)

Files reviewed included transaction write paths, valuation/history math, import flows, and API parsing.

---

## Risky code paths

### 1) `deposit_cash` allows negative deposits and can silently act like a withdrawal
**Code path**: `PortfolioTradeService.deposit_cash()` (`backend/portfolio_trade_service.py`)  
**Why risky**:
- Service method has no local guard for `amount > 0`.
- API route validates positivity, but service can be called from non-route paths (tests, scripts, future jobs).
- Negative input would reduce `current_cash` and `total_deposits` while writing a `DEPOSIT` transaction.

**Example failing scenario**:
1. Internal script calls `deposit_cash(portfolio_id=1, amount=-500)`.
2. Portfolio cash and total deposits both decrease by 500.
3. Transaction history now says `DEPOSIT` with negative value, corrupting financial semantics.

**Suggested fix**:
- Add service-level invariant checks:
  - `if amount <= 0: raise ValueError("Deposit amount must be greater than 0")`
- Consider DB `CHECK(total_value > 0)` for cash transaction types where applicable.

---

### 2) `withdraw_cash` allows negative values in service layer (silent logical inversion)
**Code path**: `PortfolioTradeService.withdraw_cash()` (`backend/portfolio_trade_service.py`)  
**Why risky**:
- No local `amount > 0` guard.
- With negative amount, insufficient-funds check is bypassed (`cash < negative` is false), and update `current_cash = current_cash - amount` increases cash.
- Writes `WITHDRAW` transaction with negative value.

**Example failing scenario**:
1. Direct call: `withdraw_cash(1, -100)`.  
2. Cash increases by 100.  
3. Transaction type is `WITHDRAW`, but amount is negative, breaking downstream analytics.

**Suggested fix**:
- Add `if amount <= 0: raise ValueError("Withdrawal amount must be greater than 0")` inside service.
- Add reconciliation test for direct service invocation (not only API).

---

### 3) `buy_stock` can divide by zero or create negative holdings if called with invalid quantity
**Code path**: `PortfolioTradeService.buy_stock()` (`backend/portfolio_trade_service.py`)  
**Why risky**:
- No internal guard for `quantity > 0` and `price > 0`.
- `avg_price = total_cost / quantity` for new holdings can raise `ZeroDivisionError` when `quantity == 0`.
- For existing holdings, `new_quantity = holding['quantity'] + quantity`; negative quantity can reduce/flip holding state unexpectedly.

**Example failing scenario**:
- Internal integration calls `buy_stock(..., quantity=0, price=100)` -> runtime crash (division by zero).  
- Internal integration calls `buy_stock(..., quantity=-2, price=100)` -> cash may be increased/decreased inconsistently and holding math corrupted.

**Suggested fix**:
- Add strict service-layer checks:
  - `quantity > 0`, `price > 0`, `commission >= 0`.
- Keep API validation, but treat service as trust boundary too.

---

### 4) `sell_stock` lacks local positivity guards; negative quantity can produce invalid-state side effects
**Code path**: `PortfolioTradeService.sell_stock()` (`backend/portfolio_trade_service.py`)  
**Why risky**:
- Guard only checks `holding['quantity'] < quantity`; with negative `quantity`, condition is typically false.
- Negative quantity causes `total_value = quantity * price` negative, then `current_cash += total_value` decreases cash.
- `new_quantity = holding['quantity'] - quantity` increases holdings (effectively a buy) while transaction type is `SELL`.

**Example failing scenario**:
1. Holding has 10 shares.
2. Call `sell_stock(..., quantity=-3, price=50)`.
3. Cash decreases by 150; holdings increase to 13; realized profit sign is nonsensical.

**Suggested fix**:
- Add invariant checks in service: `quantity > 0`, `price > 0`.
- Optional: reject sell when resulting `new_total_cost < -epsilon`.

---

### 5) Imported sells can create hidden invalid state: SELL transaction recorded even when holding is missing/insufficient
**Code path**: `PortfolioImportService.import_xtb_csv()` (`backend/portfolio_import_service.py`)  
**Why risky**:
- In `stock sell` branch, if `holding` is missing, code still:
  - increases cash,
  - inserts `SELL` transaction,
  - leaves holdings unchanged.
- No explicit check for `qty <= holding['quantity']` before applying sell.
- This can fabricate proceeds from non-owned shares (silent accounting inflation).

**Example failing scenario**:
- CSV includes sell of ticker never bought in this portfolio.
- Import succeeds; cash rises; no holding reduction; audit inconsistency introduced.

**Suggested fix**:
- Before processing sell rows:
  - if no holding: reject row / mark as import error.
  - if `qty > holding_qty + tolerance`: reject row.
- Return structured import errors with row numbers and reasons.

---

### 6) Date parsing can crash on invalid persisted date format
**Code paths**:
- `PortfolioTradeService._capitalize_savings()` (`backend/portfolio_trade_service.py`)
- `PortfolioValuationService._calculate_single_portfolio_value()` for savings (`backend/portfolio_valuation_service.py`)

**Why risky**:
- Both parse `last_interest_date` using strict `%Y-%m-%d` and do not handle invalid historical DB values.
- `create_portfolio()` accepts arbitrary `created_at` string and derives `last_interest_date` from it without format validation (`backend/portfolio_core_service.py`).
- Malformed value can trigger runtime `ValueError` during trade/value operations.

**Example failing scenario**:
1. Portfolio created with `created_at="2026/01/15"` or malformed migrated row.
2. Any savings capitalization/value call throws parse error.

**Suggested fix**:
- Validate `created_at` input format at API/service boundary.
- Wrap date parse with explicit error handling and fallback policy (e.g., set to `today` or reject with clear API error).
- Add migration/health-check to detect malformed date rows.

---

### 7) Invalid query param silently broadens transaction scope
**Code path**: `routes_transactions.get_transactions()` (`backend/routes_transactions.py`)  
**Why risky**:
- When `sub_portfolio_id` query param is non-numeric and not `none`, parser catches `ValueError` and sets it to `None`.
- That silently removes filter instead of returning validation error.
- This is a silent logical error: caller can think they requested one scope but receive aggregated data.

**Example failing scenario**:
- Request: `/api/portfolio/transactions/10?sub_portfolio_id=abc`
- Response returns all sub-scopes instead of rejecting bad input.

**Suggested fix**:
- Return 422 for malformed `sub_portfolio_id` instead of silently defaulting to `None`.
- Reuse `optional_positive_int` style validation for query params.

---

### 8) Assertions used for integrity checks may be skipped in optimized runtime
**Code paths**:
- `PortfolioTradeService._assert_holding_consistency()` (`backend/portfolio_trade_service.py`)
- `PortfolioImportService._assert_holding_consistency()` (`backend/portfolio_import_service.py`)

**Why risky**:
- Uses `assert` for business-critical consistency checks.
- Python run with optimization (`-O`) disables assertions, removing guards entirely.
- Could let invalid `quantity/total_cost/average_buy_price` drift persist silently.

**Example failing scenario**:
- Production container uses optimized mode; corrupted holding math no longer raises.

**Suggested fix**:
- Replace `assert` with explicit `if ...: raise ValueError(...)` (or custom `DataIntegrityError`) for non-optional checks.

---

## High-priority fixes (recommended order)
1. Add service-layer numeric invariants for `deposit_cash`, `withdraw_cash`, `buy_stock`, `sell_stock`.
2. Harden import sell path with strict holding existence/quantity checks.
3. Replace `assert` integrity checks with explicit exceptions.
4. Enforce strict date validation and parsing error handling for savings dates.
5. Make query validation strict (reject malformed IDs instead of widening scope).

## Suggested regression tests to add
- Direct service calls (bypassing routes):
  - deposit/withdraw with `amount <= 0`
  - buy/sell with `quantity <= 0`, `price <= 0`
- Import tests:
  - sell without holding
  - sell quantity larger than holding
- Savings tests:
  - malformed `last_interest_date` row handling
- API test:
  - invalid `sub_portfolio_id` query returns 422 (not broad results)
