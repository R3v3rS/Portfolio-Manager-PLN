# PROJECT GUIDE (Source of Truth)

## 1. Purpose
This document is the authoritative technical reference for portfolio behavior in the current backend implementation.

Scope covered here:
- portfolio and sub-portfolio ownership model,
- transaction semantics,
- holdings and cost basis rules,
- parent/child aggregation,
- valuation and FX behavior,
- key edge cases and known technical risks.

---

## 2. Data Model and Ownership Rules

### 2.1 Portfolio hierarchy
- `portfolios.parent_portfolio_id IS NULL` => **parent portfolio**.
- `portfolios.parent_portfolio_id = <id>` => **child (sub-portfolio)**.

### 2.2 Canonical ownership fields
For investment write paths (`BUY`, `SELL`, `DEPOSIT`, `WITHDRAW`, `DIVIDEND`, `INTEREST`) the backend stores transactions as:
- `transactions.portfolio_id` = **parent portfolio id** (always tree owner),
- `transactions.sub_portfolio_id` = **child scope** or `NULL` for parent-own scope.

Equivalent scope rule for `holdings` and `dividends`:
- `portfolio_id` = parent owner,
- `sub_portfolio_id` = child scope or `NULL` for parent-own scope.

### 2.3 Scope interpretation
- Parent-own scope: `sub_portfolio_id IS NULL`.
- Child scope: `sub_portfolio_id = <child_id>`.
- Parent aggregate scope: union of parent-own + all children.

---

## 3. Transaction Semantics (Deterministic)

## 3.1 Cash-flow sign convention
`transactions.total_value` is stored as non-negative amount. Transaction type defines direction.

Cash delta by type:
- `DEPOSIT` -> `+total_value`
- `INTEREST` -> `+total_value`
- `DIVIDEND` -> `+total_value`
- `SELL` -> `+total_value`
- `WITHDRAW` -> `-total_value`
- `BUY` -> `-total_value`

For XTB import this is normalized explicitly as:
- `tx_total = abs(amount)`

## 3.2 BUY rule
Given `quantity`, `price`, `commission`:
- `total_value = quantity * price + commission`
- cash is decreased in target scope (parent-own or child)
- holding update:
  - `new_quantity = old_quantity + buy_qty`
  - `new_total_cost = old_total_cost + buy_total`
  - `average_buy_price = new_total_cost / new_quantity`

## 3.3 SELL rule (average-cost basis)
Given `sell_qty`, `sell_price`:
- `sell_total = sell_qty * sell_price`
- `cost_basis = sell_qty * average_buy_price`
- `realized_profit = sell_total - cost_basis`
- cash is increased in target scope
- holding update:
  - `quantity -= sell_qty`
  - `total_cost -= sell_qty * average_buy_price`

**Required cost basis rule:**
`total_cost -= sold_qty * avg_price`

When remaining quantity is effectively zero (`<= 1e-6`), holding row is removed (or rebuilt as zero in audit pipeline).

## 3.4 DEPOSIT / WITHDRAW / DIVIDEND / INTEREST
- `DEPOSIT`: increases `current_cash`, and increases `total_deposits` on target scope.
- `WITHDRAW`: decreases `current_cash` on target scope (validated against available funds).
- `DIVIDEND`: inserts dividend record and increases cash.
- `INTEREST`: parent-only by contract for manual interest API path.

---

## 4. Holdings Model and Cost Basis

Each open position in scope stores:
- `quantity`
- `total_cost` (PLN book cost after buys/sells)
- `average_buy_price = total_cost / quantity`

### 4.1 Holdings are derived state
Backend contains repair/audit routines that rebuild holdings from transactions deterministically. Therefore transactions are primary ledger; holdings are materialized state.

### 4.2 Rebuild engine behavior
During rebuild:
- processes transactions ordered by date/id,
- applies BUY/SELL to `quantity` and `total_cost`,
- SELL uses average-cost basis,
- raises error on oversell in deterministic rebuild,
- compares rebuilt vs stored with tolerances:
  - quantity epsilon `1e-6`,
  - total_cost/cash tolerance `0.01 PLN`.

---

## 5. Aggregation Rules (Parent vs Child)

## 5.1 Holdings aggregation for parent view
For parent aggregate holdings, backend groups by `(ticker, currency)` and computes:
- `sum_quantity = SUM(quantity)`
- `sum_total_cost = SUM(total_cost)`
- `avg_price = SUM(total_cost) / SUM(quantity)` (when quantity > 0)

**Required aggregation rule:**
`parent_avg_price = SUM(total_cost) / SUM(quantity)`

## 5.2 Portfolio value aggregation
For a parent with active children:
- parent total value = own parent scope value + sum(children values)
- breakdown returns parent-own and each child contribution.

## 5.3 Transaction listing behavior
- Requesting a child portfolio id returns only that child scope.
- Requesting a parent portfolio id returns aggregate history (parent-own + children).

---

## 6. Price, FX, and Valuation Rules

## 6.1 Price units
- Current market price is fetched in instrument native currency.
- Valuation converts to PLN with FX rate map (`currency -> currencyPLN`).

## 6.2 Value formula per holding
- `gross_current_value = quantity * current_price_pln`
- if currency != PLN, estimated FX sell fee may be applied
- `current_value = gross_current_value - estimated_sell_fee`
- `profit_loss = current_value - total_cost`

## 6.3 Missing live price fallback
If live price is unavailable, backend falls back to an implied price derived from stored average buy price and FX rate context.

## 6.4 FX flags
- Non-PLN instruments are marked for FX fee behavior (`auto_fx_fees` path).
- FX treatment is deterministic but still float-based in several runtime paths (see Risks).

---

## 7. Import (XTB) Rules

## 7.1 Quantity extraction from comment
For stock operations imported from XTB comments:
- fraction syntax is parsed by taking numerator.
- example: `"1/5" -> qty = 1`.

## 7.2 Duplicate detection model
Import detects duplicates in two stages:
- duplicate inside file (`file_internal_duplicate`),
- duplicate against DB (`database_duplicate`).

Conflict acceptance requires explicit row-hash confirmation (`confirmed_hashes`).

## 7.3 Amount normalization
All imported transaction totals are normalized to non-negative amount:
- `tx_total = abs(amount)`

Type controls direction afterward.

---

## 8. Edge Cases to Know
- Partial sell uses average-cost reduction (not FIFO/LIFO).
- Parent can hold own positions (`sub_portfolio_id IS NULL`) and children can hold separate positions in same ticker/currency.
- Parent aggregate holdings can include multiple rows merged into one weighted result per `(ticker, currency)`.
- Child cash calculations include legacy compatibility path in selected flows.
- Archived child cannot be target of new trade/deposit/withdraw/dividend assignment.

---

## 9. Known Technical Risks
- **Float precision debt:** many runtime calculations still use `float`; audit/rebuild uses decimal quantization, creating mixed-precision boundaries.
- **Rounding drift risk:** repeated partial sells and recomputed averages can accumulate cent-level drift.
- **FX ambiguity risk:** buy/sell book-cost in PLN may rely on imported/assumed rates; historical FX parity assumptions can diverge from broker statements.
- **Aggregation regressions risk:** parent aggregate logic appears in multiple services; future schema/query edits can desynchronize totals.
- **History performance risk:** dynamic daily reconstruction can be expensive on large ledgers.

---

## 10. Terminology (Normalized)
- **Parent portfolio**: portfolio with `parent_portfolio_id IS NULL`.
- **Child / sub-portfolio**: portfolio with `parent_portfolio_id = parent.id`.
- **Scope**: `(portfolio_id parent_owner, sub_portfolio_id nullable child selector)`.
- **Parent-own scope**: `sub_portfolio_id IS NULL` under a parent owner.
- **Aggregate parent scope**: parent-own scope + all child scopes.

