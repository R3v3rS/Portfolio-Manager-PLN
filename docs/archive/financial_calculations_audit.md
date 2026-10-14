# Financial Calculations Audit

Date: 2026-04-04  
Scope reviewed:
- `backend/math_utils.py`
- `backend/portfolio_valuation_service.py`
- `backend/portfolio_history_service.py`
- `backend/portfolio_trade_service.py`
- `backend/portfolio_import_service.py`
- `backend/portfolio_audit_service.py`

## Executive summary

The calculation layer has good coverage of core portfolio metrics, but there are **material consistency and precision risks** in four areas:

1. **Floating-point accumulation** in cash/cost basis math (`float` + repeated `round`), with potential drift in long transaction histories.
2. **Inconsistent aggregation semantics** for parent/child portfolios in cash-flow and contribution computations.
3. **Duplicated financial formulas** (realized PnL, FX fee application, external flow normalization) implemented in multiple modules.
4. **XIRR robustness limitations** (Newton-only solver, convergence sensitivity, weak fallback strategy).

---

## Findings

## 1) PnL (realized/unrealized)

### 1.1 `PortfolioTradeService.sell_stock` + `PortfolioImportService` + `PortfolioAuditService.rebuild_holdings_from_transactions`
**Problematic functions**
- `backend/portfolio_trade_service.py::sell_stock`
- `backend/portfolio_import_service.py` (SELL import path)
- `backend/portfolio_audit_service.py::rebuild_holdings_from_transactions`

**Bug / risk**
- Realized PnL and cost-basis formulas are duplicated in at least 3 places.
- Each implementation uses slightly different precision handling (plain float arithmetic vs Decimal quantization).
- This can produce audit mismatches over time (especially after many partial sells).

**Code-level fix**
- Introduce a single shared helper in core service, e.g.:
  - `compute_sell_allocation(quantity, avg_price, total_value) -> {cost_basis, realized_profit}`
  - `compute_remaining_cost(total_cost, sold_qty, avg_price)`
- Implement helper using `Decimal`, quantize once at accounting precision.
- Replace all ad-hoc formulas in trade/import/audit paths with this helper.

---

### 1.2 `PortfolioValuationService.get_holdings`
**Problematic function**
- `backend/portfolio_valuation_service.py::get_holdings`

**Bug / risk**
- Unrealized PnL uses `profit_loss = current_value - total_cost` with `current_value` reduced by estimated FX sell fee.
- This is valid *if intentional*, but it is mixed with other endpoints that present values without harmonized fee treatment (historical series and change metrics may not always match exact assumptions).
- Potential user-visible inconsistency between “live PnL” and “history PnL”.

**Code-level fix**
- Define explicit valuation conventions in one module:
  - gross market value
  - net-of-estimated-exit-fee market value
  - unrealized gross PnL
  - unrealized net PnL
- Return both gross and net variants (or document and enforce one globally).

---

### 1.3 `PortfolioHistoryService._apply_tx_to_rolling`
**Problematic function**
- `backend/portfolio_history_service.py::_apply_tx_to_rolling`

**Bug / risk**
- `state['cash']` and `state['invested_capital']` are rounded to 10 dp on every transaction mutation.
- Repeated rounding in a rolling engine is path-dependent and introduces cumulative drift.

**Code-level fix**
- Keep full precision internally (`Decimal` preferred).
- Round only at serialization/output boundaries.
- If storage requires float, convert only at final response composition.

---

## 2) XIRR / returns

### 2.1 `math_utils.xirr`
**Problematic function**
- `backend/math_utils.py::xirr`

**Bug / risk**
- Newton-Raphson only, no bracketing fallback (e.g., bisection/brent).
- Convergence criterion uses `abs(new_rate-rate)` only; does not require small residual `abs(NPV)`.
- Guard `if rate <= -1: rate = -0.99` is a heuristic that can hide unstable iterates.
- Susceptible to non-convergence / wrong root in irregular cash-flow profiles.

**Code-level fix**
- Use hybrid solver:
  1. bracket root over configurable range (e.g., `[-0.9999, 10]`) by scanning,
  2. run Brent/Bisection within bracket,
  3. optionally accelerate with Newton when safe.
- Convergence should require both:
  - `abs(npv) < npv_tolerance`
  - `abs(delta_rate) < rate_tolerance`
- Return structured error codes (e.g., `NO_BRACKET`, `NO_CONVERGENCE`, `MULTIPLE_ROOTS_POSSIBLE`) for observability.

---

### 2.2 `PortfolioValuationService._calculate_single_portfolio_value` and parent aggregate path
**Problematic functions**
- `backend/portfolio_valuation_service.py::_calculate_single_portfolio_value`
- `backend/portfolio_valuation_service.py::get_portfolio_value`

**Bug / risk**
- XIRR inputs include only `DEPOSIT`/`WITHDRAW` + terminal value, which is conceptually okay for external-flow MWR, but parent/child query semantics differ across code paths and are easy to break.
- Parent aggregate logic computes net contributions by looping over `portfolio_ids` and querying by `portfolio_id = ?`, while transactions are parent-scoped with `sub_portfolio_id`. This design is fragile and risks future regression (double counting or omissions if legacy child-scoped rows exist).

**Code-level fix**
- Centralize cash-flow extraction in one function:
  - `build_external_cash_flows(scope)`, where scope can be `parent_own`, `child`, `parent_aggregate`.
- Make `scope` explicit in SQL predicates (`sub_portfolio_id IS NULL`, `= child_id`, or all under parent).
- Unit-test parent aggregate XIRR with mixed parent-own + child flows + legacy rows.

---

### 2.3 `PortfolioHistoryService.get_performance_matrix`
**Problematic function**
- `backend/portfolio_history_service.py::get_performance_matrix`

**Bug / risk**
- Monthly return formula uses Modified Dietz-like denominator: `start_value + net_flows/2`.
- This assumes flows occur mid-period, which can materially bias return for large/early/late flows.

**Code-level fix**
- Either:
  - switch to true daily time-weighted return chain-linking (preferred), or
  - compute Dietz with actual time weights per flow date within month.
- Document chosen methodology in API docs and UI labels.

---

## 3) Aggregation logic

### 3.1 `PortfolioValuationService.get_holdings` (aggregate SQL)
**Problematic function**
- `backend/portfolio_valuation_service.py::get_holdings`

**Bug / risk**
- Aggregation query groups by `ticker, currency` but selects `company_name, sector, industry` without deterministic aggregation.
- In SQLite this returns arbitrary row values for non-grouped columns.

**Code-level fix**
- Use deterministic aggregators:
  - `MAX(company_name)`, `MAX(sector)`, `MAX(industry)`
  - or join to a canonical metadata source after aggregation.

---

### 3.2 `PortfolioValuationService.get_cash_balance_on_date` vs `_compute_cash_negative_days`
**Problematic functions**
- `backend/portfolio_valuation_service.py::get_cash_balance_on_date`
- `backend/portfolio_valuation_service.py::_compute_cash_negative_days`

**Bug / risk**
- Cash delta mapping is inconsistent:
  - `get_cash_balance_on_date` counts only `DEPOSIT/INTEREST/WITHDRAW`.
  - `_compute_cash_negative_days` includes `SELL` and `DIVIDEND` too.
- Same concept (“cash movement”) is implemented differently.

**Code-level fix**
- Introduce single transaction-to-cash-delta mapper, reused everywhere.
- Add a regression test asserting both functions produce identical cash transitions for same transaction stream.

---

## 4) Rounding strategy

### 4.1 Global inconsistency (float + round + Decimal mix)
**Problematic areas**
- Multiple modules in scope.

**Bug / risk**
- Mixed precision model:
  - raw float operations,
  - per-step `round(...)`,
  - occasional `Decimal` in audit only.
- This can create “false inconsistencies” between live calculations and audit rebuilds.

**Code-level fix**
- Establish numeric policy:
  - store and compute monetary amounts as `Decimal` (or integer minor units),
  - quantize only at business boundaries,
  - keep one central rounding mode (`ROUND_HALF_UP`) and per-field precision map.
- Add utility methods (e.g., `money()`, `qty()`, `rate()`) and ban direct `round` in service layer.

---

### 4.2 Hard-coded fee rate duplication
**Problematic functions**
- `backend/portfolio_valuation_service.py::_calculate_single_portfolio_value` (1D/7D block)
- `backend/portfolio_trade_service.py::_calculate_fx_fee`

**Bug / risk**
- Fee rate appears as both constant (`FX_FEE_RATE`) and inline literal (`0.005`).
- Any future fee policy change may desynchronize endpoints.

**Code-level fix**
- Replace inline `0.005` with `PortfolioCoreService.FX_FEE_RATE` (or `PortfolioTradeService._calculate_fx_fee`).
- Add test asserting consistency between historical and live fee-adjusted valuation.

---

## Priority remediation plan

1. **P0**: Unify numeric type policy (`Decimal`) for transaction math and PnL/cost-basis updates.
2. **P0**: Extract shared formulas for sell allocation, cash delta mapping, and external cash-flow extraction.
3. **P1**: Upgrade XIRR solver to hybrid bracketing + residual-based convergence.
4. **P1**: Fix aggregate SQL nondeterministic grouped columns.
5. **P2**: Replace hardcoded fee literals and document return methodologies.

---

## Suggested tests to add

- Partial-sell stress test with 1,000 buys/sells validates:
  - no negative residual cost,
  - realized PnL consistency across trade/import/audit paths.
- Parent/child aggregation matrix test (parent-own + multiple children + archived child + legacy rows).
- XIRR robustness tests:
  - hard non-converging case,
  - multi-sign-change cash flows,
  - near `-100%` scenarios.
- Rounding invariance tests:
  - same transaction set in different chunking orders gives identical final PnL/cash.
