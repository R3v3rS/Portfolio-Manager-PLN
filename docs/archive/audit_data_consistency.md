# Data Consistency Audit – Financial Logic

## Scope
Audit focused on:
- mismatches between derived values (`total_value`, holdings, cash, portfolio value),
- duplicated calculations across modules,
- consistency of holdings/transactions/portfolio rollups.

---

## 1) Cash balance logic drift (`get_cash_balance_on_date` ignores BUY/SELL/DIVIDEND)

**Reference**
- `backend/portfolio_valuation_service.py:114-189`
- `backend/portfolio_valuation_service.py:126-128,143-145,160-162,176-178`
- Compared with canonical cash delta logic in:
  - `backend/portfolio_history_service.py:82-85`
  - `backend/portfolio_audit_service.py:94-102,119`

**Issue**
`get_cash_balance_on_date` only includes `DEPOSIT`, `INTEREST`, and `WITHDRAW`, while other modules treat `BUY`, `SELL`, and `DIVIDEND` as cash movements. This creates a second, incompatible cash model.

**Risk**
- Transfer validation can approve or reject transfers on incorrect historical cash.
- Parent/child cash checks drift from audit and history outputs.
- Hard-to-debug inconsistencies where UI history and transfer validation disagree for the same date.

**Suggested fix**
Create one shared cash-delta helper (e.g., `cash_delta_for_tx_type`) and use it in:
- `get_cash_balance_on_date`,
- `_compute_cash_negative_days`,
- history rolling logic,
- rebuild/audit logic.

Also add regression tests with mixed flows (`DEPOSIT`, `BUY`, `SELL`, `DIVIDEND`, `WITHDRAW`) on the same day.

---

## 2) Parent-vs-child scope inconsistency in historical cash reconstruction

**Reference**
- `backend/portfolio_history_service.py:203-207` (parent uses all transactions for `portfolio_id`)
- `backend/portfolio_valuation_service.py:30-40` (parent cash-negative-days uses only `sub_portfolio_id IS NULL`)
- `backend/portfolio_valuation_service.py:120-136` (parent `get_cash_balance_on_date` uses all transactions)

**Issue**
Different endpoints apply different scope rules for parent portfolios:
- history for parent aggregates all child+parent transactions,
- negative-days audit for parent excludes child transactions,
- cash balance on date for parent includes all.

This is logic drift in “what parent scope means”.

**Risk**
- One endpoint can report “cash healthy” while another reports negative cash for same portfolio/date.
- Operational actions (transfers, audits, dashboards) can disagree and trigger false alarms or missed anomalies.

**Suggested fix**
Define explicit scope semantics once:
- `PARENT_OWN_ONLY` vs `PARENT_AGGREGATED`.
Implement shared query builders/helpers and enforce per endpoint deliberately (with explicit naming in function parameters and tests).

---

## 3) Assignment flow can temporarily desynchronize transactions vs holdings/cash

**Reference**
- `backend/portfolio_trade_service.py:374-376` (transaction sub-portfolio reassignment)
- `backend/portfolio_trade_service.py:382-390` (cash/holdings are not updated there by design)

**Issue**
`assign_transaction_to_subportfolio` updates transaction ownership, but intentionally does not update cash/holdings immediately. It assumes a later repair process will reconcile state.

**Risk**
- If any caller skips repair (or crashes between assign and repair), persisted state can be partially moved:
  - transactions show new assignment,
  - holdings/cash still reflect old assignment.
- Subsequent reads in that window can produce inconsistent portfolio values.

**Suggested fix**
Wrap assignment + reconciliation in a single service-level transaction boundary for all call paths, or make assignment API always execute deterministic rebuild before commit.

At minimum, add an invariant check right after assignment and fail hard if post-state is inconsistent.

---

## 4) INTEREST sub-portfolio rule is inconsistent between write paths

**Reference**
- `backend/portfolio_trade_service.py:367-368` (explicitly forbids assigning `INTEREST` to child)
- `backend/portfolio_trade_service.py:437-451` (manual interest writes parent-only)
- `backend/portfolio_import_service.py:407-416` (import writes `INTEREST` with provided `sub_portfolio_id`)

**Issue**
Core trade service enforces “INTEREST must stay in parent”, but import path can create child-assigned INTEREST transactions.

**Risk**
- Audit checks can flag imported data as inconsistent.
- Parent/child totals and interest reporting become source-dependent (manual vs import).
- Downstream logic relying on the invariant may break silently.

**Suggested fix**
Unify rule enforcement by reusing one validation function for all write paths (manual routes, import, bulk tools). If legacy data must be supported, migrate old records and explicitly mark transitional behavior.

---

## 5) Duplicate cash-flow business logic across modules (high drift surface)

**Reference**
- `backend/portfolio_history_service.py:82-85`
- `backend/portfolio_audit_service.py:94-102,119`
- `backend/portfolio_valuation_service.py:45-50`
- `backend/portfolio_valuation_service.py:124-129,141-146,158-163,174-179`

**Issue**
Cash-flow sign rules are reimplemented in multiple places with slight differences and different SQL CASE expressions.

**Risk**
- Every new transaction type (or rule change) requires synchronized edits across modules.
- Partial updates introduce silent accounting drift.
- Audit/repair may “fix” to a different model than valuation/history uses.

**Suggested fix**
Introduce one canonical domain layer for transaction effects:
- `cash_delta(tx)`
- `invested_capital_delta(tx)`
- `position_delta(tx)`
Then use this in both SQL-backed and Python-backed computations (or generate SQL CASE from one mapping constant).

---

## Recommended hardening plan

1. **Canonicalize transaction semantics** in one shared module and replace duplicated CASE logic.
2. **Codify scope model** (`parent own`, `parent aggregated`, `child`) with explicit APIs.
3. **Make assignment atomic with rebuild** so desync windows are impossible.
4. **Normalize interest rule across import and manual writes**; migrate legacy outliers.
5. **Add consistency tests** that compare outputs of valuation/history/audit for the same fixture dataset.
