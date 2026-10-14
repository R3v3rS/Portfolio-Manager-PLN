# FX / Multi-Currency Audit

Date: 2026-04-04  
Scope: backend currency model, transaction write paths, valuation, history, import, and repair flows.

## Executive summary

The codebase is **PLN-centric at storage level** (`transactions.total_value`, `holdings.total_cost`, `portfolios.current_cash`) and performs FX conversion mostly at valuation/runtime. This model can work, but the current implementation has several consistency gaps:

1. **Foreign-currency transaction inputs are accepted without explicit conversion context**, while write paths treat them as PLN.
2. **Historical and live valuation use current/ad-hoc FX lookups instead of persisted trade-date FX snapshots.**
3. **FX fallback behavior silently uses `1.0` on missing rates**, masking data quality issues and potentially understating/overstating values.
4. **Currency inference and conversion logic are duplicated** across services with different heuristics.
5. **Repair/rebuild logic is currency-agnostic**, so integrity repairs can preserve wrong PLN totals for non-PLN flows.

Overall risk: **High** for correctness in real multi-currency usage, **Medium** for single-currency (PLN-only) portfolios.

---

## Current currency architecture (observed)

### Storage model

- `holdings` stores:
  - display/holding `currency`
  - `instrument_currency`
  - `avg_buy_price_native`
  - `avg_buy_fx_rate`
- `transactions` stores `price` and `total_value` but **no transaction currency nor FX rate snapshot**.
- `portfolios.current_cash` is effectively treated as PLN across services.

### Runtime conversion model

- Runtime valuation converts non-PLN holdings with market FX tickers like `{CCY}PLN=X`.
- Historical valuation uses historical FX close prices where available.
- FX fee is modeled as flat `0.5%` for non-PLN positions.

---

## Findings

## 1) Potential mixing of currencies at transaction write points

**Risk: High**

### What happens
- `/buy` and `/sell` APIs accept `price` only (no currency argument) and pass directly to service methods.
- `buy_stock` and `sell_stock` treat incoming `price` as PLN (`unit_price_pln`), then store totals/cash movements in PLN.
- Yet instrument currency can be non-PLN via `symbol_mappings`/metadata, creating a semantic mismatch when callers send native price (e.g., USD).

### Affected code areas
- `backend/routes_transactions.py` (`/buy`, `/sell` request contracts)
- `backend/portfolio_trade_service.py` (`buy_stock`, `sell_stock`)

### Why this is risky
If client sends native price for USD stock (e.g., 100 USD), system may store as 100 PLN unless client pre-converted. This contaminates `transactions.total_value`, holdings `total_cost`, P/L, and cash balances.

### Suggested improvements
- Make API contract explicit:
  - Option A: require `price_pln` only (strict).
  - Option B: accept `price`, `price_currency`, and optional `fx_rate`; convert server-side.
- Persist on each BUY/SELL:
  - `transaction_currency`
  - `price_native`
  - `fx_rate_at_trade`
  - `total_value_native`
- Reject ambiguous payloads (e.g., missing currency for non-PLN tickers).

---

## 2) Missing FX snapshots at transaction level

**Risk: High**

### What happens
- Holdings table includes `avg_buy_fx_rate`, but BUY/IMPORT paths often default this to `1.0`.
- No reliable per-transaction FX snapshot in `transactions`.
- Runtime/historical recomputation relies on market data lookups at read time.

### Affected code areas
- `backend/database.py` (`transactions` schema lacks FX fields)
- `backend/portfolio_trade_service.py` (BUY write path defaults for native/FX fields)
- `backend/portfolio_import_service.py` (import path sets `avg_buy_fx_rate` to `1.0` or carries old value)

### Why this is risky
Without immutable trade-date FX snapshots, cost basis and reconstructed performance can drift depending on data availability and retrospective FX retrieval behavior.

### Suggested improvements
- Add transaction FX snapshot columns and backfill strategy.
- Compute holdings averages from transaction snapshots, not inferred defaults.
- Introduce migration path: legacy rows marked `fx_source='legacy_assumed_pln'` for transparent confidence levels.

---

## 3) Inconsistent FX source and fallback behavior (`1.0` fallback)

**Risk: High**

### What happens
- `_get_fx_rates_to_pln` returns `1.0` when FX quote unavailable.
- Historical valuation also falls back to `1.0` when historical FX price <= 0.
- This can silently convert USD/EUR assets as PLN.

### Affected code areas
- `backend/portfolio_trade_service.py` (`_get_fx_rates_to_pln`)
- `backend/portfolio_valuation_service.py` (holdings valuation + change calculations)
- `backend/portfolio_history_service.py` (monthly/daily historical loops)

### Why this is risky
Silent fallback hides outages/data gaps and produces materially incorrect valuation/profit metrics without alerting users.

### Suggested improvements
- Replace silent fallback with explicit status:
  - `fx_status = OK | MISSING | STALE`
- For missing FX:
  - return partial valuation + warning, or
  - use last known FX with timestamp and confidence flag.
- Emit structured logs/metrics when fallback path triggers.

---

## 4) Duplicated conversion logic across services

**Risk: Medium**

### What happens
- FX conversion and fee application are implemented in several places:
  - live holdings valuation
  - portfolio 1D/7D change path
  - historical valuation loops
- Currency determination also appears in multiple places (holdings currency, metadata fallback, mapping fallback).

### Affected code areas
- `backend/portfolio_valuation_service.py`
- `backend/portfolio_history_service.py`
- `backend/portfolio_import_service.py`
- `backend/portfolio_trade_service.py`

### Why this is risky
Duplicated logic diverges over time (different fallback rules, different inferred currency sources), causing endpoint-to-endpoint inconsistencies.

### Suggested improvements
- Introduce centralized FX module/service (single source of truth):
  - `resolve_instrument_currency(ticker)`
  - `convert_to_pln(amount, currency, as_of_date, mode)`
  - `estimate_sell_fee(amount_pln, currency)`
- Reuse identical pipeline in live valuation, history, and import normalization.

---

## 5) Storage-vs-runtime mismatch in holdings FX fields

**Risk: Medium**

### What happens
- `avg_buy_price_native` and `avg_buy_fx_rate` exist, but in practice are often placeholders (`price` as PLN, FX=1.0).
- Current valuation primarily uses current quote + current FX, while profit compares against stored PLN `total_cost`.

### Affected code areas
- `backend/portfolio_trade_service.py` (holding insert/update defaults)
- `backend/portfolio_import_service.py` (holding upsert path)
- `backend/database.py` (schema indicates intent, but write paths underfill semantics)

### Why this is risky
Columns imply native-currency fidelity, but data may not be trustworthy. Consumers may overestimate precision of FX-aware fields.

### Suggested improvements
- Enforce invariant on write:
  - if `instrument_currency != PLN`, require non-default native + FX values.
- Add DB/application constraints or validation hooks.
- Introduce data-quality audit endpoint listing rows with suspicious `fx_rate=1.0` on non-PLN instruments.

---

## 6) Currency-agnostic repair/rebuild can perpetuate wrong PLN totals

**Risk: Medium**

### What happens
- Rebuild/audit recomputes holdings from `transactions.total_value` and quantity only.
- No FX-aware recomputation from native prices or transaction-currency snapshots (which are absent).

### Affected code areas
- `backend/portfolio_audit_service.py` (`rebuild_holdings_from_transactions`, `repair_portfolio_state`)

### Why this is risky
If historic BUY/SELL amounts were stored with wrong currency assumption, repair tooling will “confirm” and preserve those errors.

### Suggested improvements
- Once transaction FX snapshots exist, update rebuild logic to use canonical native+FX decomposition.
- Report “confidence level” for rebuilt holdings (high when snapshot complete, low for legacy inferred rows).

---

## 7) Cash transfer and cash messaging are PLN-hardcoded

**Risk: Low/Medium**

### What happens
- Cash transfer validation/error text is explicitly PLN.
- No portfolio base-currency abstraction exists; cash appears universally treated as PLN.

### Affected code areas
- `backend/routes_transactions.py` (transfer validation message and semantics)
- broader cash model in `portfolios.current_cash`

### Suggested improvements
- If product should stay PLN-only cash ledger: enforce and document clearly.
- If multi-currency cash is desired: add cash ledger per currency and transfer conversion policy.

---

## Conversion points map (where FX is applied now)

1. **Live holdings valuation**: native quote × runtime FX `{CCY}PLN=X` → PLN; fee deducted for non-PLN.
2. **Portfolio change metrics (1D/7D)**: quote deltas and FX deltas both applied at runtime.
3. **Historical monthly/daily value**: historical security price × historical FX (if available) with fallback behavior.
4. **Trade/import write paths**: generally no explicit FX conversion step; values assumed as already PLN.

---

## Prioritized remediation plan

1. **Define canonical transaction money model (highest priority).**
   - Add transaction currency + FX snapshot fields.
   - Make BUY/SELL/IMPORT contracts explicit and validated.
2. **Centralize FX conversion logic.**
   - Single module for currency resolution, conversion, fallback policy, and diagnostics.
3. **Eliminate silent `1.0` FX fallback.**
   - Replace with explicit warning/error/last-known strategy.
4. **Backfill & classify legacy data.**
   - Mark confidence of legacy rows; avoid pretending precise FX history where absent.
5. **Add regression tests for multi-currency invariants.**
   - Examples: USD buy with native price, missing FX day, import of mixed PLN/USD statements, historical valuation consistency.

---

## Suggested test scenarios to add

- BUY USD ticker with `price_currency=USD`, verify PLN cash decrement equals native×FX+fees.
- SELL USD ticker with historical FX snapshot, verify realized P/L in PLN stable even if current FX changes.
- Missing FX quote on valuation day should surface warning/status, not silently use 1.0.
- Import mixed-currency CSV where amount is native currency: confirm explicit conversion path or validation failure.
- Repair flow on legacy records should report low-confidence FX assumptions.

---

## Final risk assessment

- **Data correctness risk:** High (multi-currency portfolios).
- **Operational risk:** Medium (silent fallback masks FX data outages).
- **Auditability risk:** High (missing immutable FX snapshots at transaction granularity).

