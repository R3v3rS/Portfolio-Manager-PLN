# Performance Audit (Backend)

Date: 2026-04-04
Scope: `backend/` Python services and route handlers.

## Executive summary

The codebase already contains some good performance practices (batch SQL, price cache in `PriceService`, rolling state in history calculation). The largest remaining bottlenecks are concentrated in a few hotspots where loops repeatedly scan growing collections or re-run heavy work.

Most impactful findings:

1. **PPK weekly chart generation does repeated full-prefix recalculation** (`O(W*T)` + repeated metric loops).
2. **Loan amortization schedule scans full rates/overpayments lists each month** (`O(M*(R+O))`).
3. **Budget envelope assembly recalculates outstanding loans with nested loops** (`O(E*L)`).
4. **Symbol mapping resolution performs full-table rebuild + fuzzy matching per row during import** (amplifies to near `O(N_import * N_map)`).
5. **Parent portfolio valuation repeats DB/service calls inside loops (including PPK current price fetch)** (avoidable repeated I/O).

---

## 1) PPK chart: repeated prefix filtering + full metric recomputation

**Problematic section**
- File: `backend/modules/ppk/ppk_service.py`
- In `get_chart_data_extended`, for every week point, transactions are filtered again (`tx['date'] <= week_date`) and passed to `PPKCalculation.calculate_metrics(...)`.

```python
for week_point in weekly_data:
    tx_up_to_week = [tx for tx in tx_list if tx['date'] <= week_date]
    week_metrics = PPKCalculation.calculate_metrics(tx_up_to_week, Decimal(str(week_price)))
```

`calculate_metrics` itself loops over all provided transactions each call.

**Why this is expensive**
- If there are `W` week points and `T` transactions, this pattern behaves like **`O(W*T)`** just for filtering, plus another **`O(W*T)`** for metric recomputation.
- In practice (e.g., 260 weeks × 2,000 transactions), this can become one of the slowest endpoints.

**Optimization suggestions**
- Use a **single-pass rolling accumulator**:
  - Keep transactions sorted by date.
  - Move a transaction pointer forward as week advances.
  - Maintain cumulative units/purchase totals incrementally.
- Compute weekly value from cumulative state instead of recalculating from scratch.
- If tax logic requires aggregate recomputation, cache intermediate components (employee/employer totals) and compute only final tax deltas.

**Expected impact**
- Reduce from repeated `O(W*T)` work toward roughly **`O(W + T)`**.
- Noticeably faster chart generation for long-lived portfolios.

---

## 2) Loan schedule: repeated scans of rates and overpayments each month

**Problematic section**
- File: `backend/loan_service.py`
- In monthly loop:
  - scans all `sorted_rates` to find active rate,
  - scans all `sorted_overpayments` to collect current month operations.

**Why this is expensive**
- Complexity approximates **`O(M*(R+O))`** where:
  - `M` = simulated months,
  - `R` = rate changes count,
  - `O` = one-off overpayments count.
- For long loans and many overpayments, runtime grows quickly.

**Optimization suggestions**
- Replace repeated scans with **cursor/index traversal** (two pointers):
  - one pointer for rates,
  - one pointer for overpayments.
- Pre-group overpayments by month key (`YYYY-MM`) once, then direct lookup each iteration.
- Parse dates once up front (currently `datetime.strptime` happens repeatedly inside loops).

**Expected impact**
- Reduce schedule generation to roughly **`O(M + R + O)`**.
- Lower CPU usage for dashboard endpoints that call schedule generation.

---

## 3) Budget envelopes: nested envelope×loan summation

**Problematic section**
- File: `backend/budget_service.py`
- For each envelope, outstanding loans are recomputed by filtering all loan rows:

```python
for env in envelopes_rows:
    outstanding_loans = sum(l['remaining'] for l in loans_rows if l['source_envelope_id'] == env['id'])
```

**Why this is expensive**
- This is a classic **`O(E*L)`** nested pattern.
- As envelope count and open loan count grow, endpoint latency scales poorly.

**Optimization suggestions**
- Pre-aggregate once into a dict:
  - `remaining_by_envelope[source_envelope_id] += remaining`
- Then each envelope lookup becomes `O(1)`.
- Alternative: push aggregation to SQL with `GROUP BY source_envelope_id`.

**Expected impact**
- Complexity drops to **`O(E + L)`**.
- Faster budget summary response and less Python-level iteration.

---

## 4) Import symbol resolution: repeated full mapping rebuild + fuzzy lookup

**Problematic section**
- File: `backend/portfolio_import_service.py`
- `resolve_symbol_mapping`:
  - performs exact query,
  - if missing, loads **all** symbol mappings,
  - rebuilds normalized map,
  - runs fuzzy matching.
- In `import_xtb_csv`, this function is called per stock-operation row.

**Why this is expensive**
- In import loop, this can become effectively **`O(N_import * N_map)`** (or worse with fuzzy matching overhead).
- Also causes repeated DB reads of the same table within one import run.

**Optimization suggestions**
- Build normalized mapping cache **once per import** (or process-level cache with invalidation).
- Add request-local memoization: `symbol_input -> resolved mapping`.
- Move fuzzy matching candidate set precomputation outside row loop.
- Consider DB index strategy for exact symbol normalization path.

**Expected impact**
- Major improvement for large CSV imports with repeated symbols.
- Significantly lower DB I/O and CPU for text normalization/fuzzy search.

---

## 5) Parent valuation: repeated per-portfolio DB/service fetches

**Problematic section**
- File: `backend/portfolio_valuation_service.py`
- In a loop over `portfolio_ids`, code repeatedly:
  - calls `get_portfolio(p_id)`,
  - for PPK branches, may call `PPKService.fetch_current_price()` per iteration,
  - performs separate flow queries per portfolio.

**Why this is expensive**
- Introduces repeated DB round trips and potentially repeated external data fetches.
- Latency accumulates linearly with number of child portfolios (and can spike if network call repeats).

**Optimization suggestions**
- Batch preload portfolio metadata for all IDs in one SQL query.
- Fetch PPK current price once and reuse across loop.
- Aggregate deposits/withdrawals for all portfolio IDs in one grouped SQL query.

**Expected impact**
- Lower query count and less I/O jitter.
- Better tail latency for parent portfolio valuation endpoints.

---

## Additional notes

- `PriceService` already has cache structures (`_price_cache`, stale checks), which is good. Focus improvements first on the loop-heavy hotspots above.
- After refactors, validate with micro-benchmarks and route-level timing (p50/p95), not only unit tests.

## Suggested implementation order

1. **Budget envelope loan pre-aggregation** (small change, quick win).
2. **Loan schedule pointer-based traversal** (medium change, high impact).
3. **PPK rolling weekly metrics** (larger change, highest computational win).
4. **Import symbol mapping request-local cache** (high impact for bulk imports).
5. **Parent valuation batching** (I/O reduction and stability improvement).

