# Error Handling Audit (Backend Reliability)

Date: 2026-04-04  
Scope: `backend/` application layer, service layer, async jobs, and data/migration paths.

## Executive summary

The codebase has a solid **global API error envelope** and catches unhandled exceptions centrally, but several areas still reduce diagnosability and reliability:

- multiple broad `except Exception` blocks that either suppress context or convert invalid input into silent fallback behavior,
- inconsistent logging (`print`, `traceback.print_exc`, and `logging` mixed together),
- async/background failure handling that marks jobs failed but can leave business operations partially successful,
- migration and valuation paths where exceptions are swallowed without structured telemetry.

---

## Risky areas

## 1) Swallowed exceptions and silent degradation

### A. PPK price fetch silently ignored in API route
- `routes_ppk.get_ppk_transactions` suppresses all exceptions from `fetch_current_price()` and continues with `current_price_data = None`.
- Risk: upstream outages/data parse failures become invisible to operators and clients; response shape does not explain degraded calculation mode.

**Code location:** `backend/routes_ppk.py` (`except Exception: current_price_data = None`).

### B. Query parameter parse errors converted to `None`
- `routes_transactions.get_transactions` and `get_all_transactions` catch `ValueError` for numeric query parsing and silently set values to `None`.
- Risk: user sends invalid filter value and gets broad/unexpected dataset instead of actionable 4xx feedback.

**Code location:** `backend/routes_transactions.py` (`except ValueError: ... = None`).

### C. Metadata/price context fallbacks hide external dependency failures
- `portfolio_history_service._build_price_context` catches metadata fetch failures and defaults to PLN (or ignores) for currency decisions.
- Risk: valuation may be wrong with no explicit signal in API response; only one branch logs an exception (`sync_stock_history`) while metadata failures are mostly suppressed.

**Code location:** `backend/portfolio_history_service.py` (`except Exception: pass` / fallback currency assignment).

### D. XIRR processing drops records on parse errors
- In valuation flows, transaction parsing failures inside loops are silently skipped (`except Exception: continue`).
- Risk: XIRR may be materially inaccurate for malformed historical records, without visibility.

**Code location:** `backend/portfolio_valuation_service.py` (`except Exception: continue` in cashflow assembly).

### E. Migration steps suppress operational errors broadly
- Many schema migration steps do `except sqlite3.OperationalError: pass` or bare `except: pass`.
- Risk: real migration breakages can be indistinguishable from expected “column exists” cases; startup may continue in inconsistent schema state.

**Code location:** `backend/database.py` (multiple migration sections).

---

## 2) Failure propagation gaps

### A. Async recalculation failures after successful write commit
- Transfer/assignment endpoints commit DB transaction first, then launch recalculation async job.
- If recalculation fails, API still returns success for mutation, and correctness relies on later manual/system repair.
- Jobs are marked `failed`, but there is no explicit compensating transaction or retry strategy in these flows.

**Code location:** `backend/routes_transactions.py` (`_run_cash_transfer_recalculation`, `run_recalculation`, `run_bulk_recalculation`).

### B. Global handler hides 500 details by design, but route-level logs are inconsistent
- `app.py` correctly returns generic `internal_error` for uncaught exceptions.
- However, because some paths only use `print`/`traceback.print_exc`, production log pipelines may miss critical context.

**Code location:** `backend/app.py`, `backend/routes_transactions.py`, `backend/portfolio_core_service.py`, `backend/modules/ppk/ppk_service.py`.

### C. Re-raising with `raise e` resets traceback origin
- Several service methods use `except Exception as e: ... raise e`.
- Risk: traceback points to re-raise location rather than original exception site, reducing root-cause clarity.

**Code location:** `backend/portfolio_core_service.py`, `backend/portfolio_trade_service.py`, `backend/budget_service.py`, `backend/watchlist_service.py`.

---

## 3) Logging quality issues

### A. Mixed logging mechanisms
- Uses `logging` in many modules (good), but also `print(...)` and `traceback.print_exc()` in runtime code.
- Risk: fragmented observability, log parsing inconsistencies, and missing correlation fields.

### B. Missing structured context in some failure logs
- Some logs report only error string; missing `portfolio_id`, `transaction_id`, `job_id`, operation name, and retry state.
- Risk: hard to triage incident blast radius quickly.

### C. Partial standardization success
- `app.py` sets JSON-line file logging and central exception logging (strong baseline).
- `price_service` demonstrates structured provider-event logging and error classification (good practice worth extending).

---

## Failure scenarios

1. **External PPK provider down**  
   `GET /api/portfolio/ppk/transactions/<id>` still returns 200, but valuation can be stale/degraded with no explicit warning in payload.

2. **Client typo in filter** (`sub_portfolio_id=abc`)  
   Endpoint silently treats it as `None`, returning broader data than intended; user may trust incorrect query scope.

3. **Cash transfer recalculation fails in background**  
   Transfer rows and cash delta are committed, API returns success, async repair fails later; job has failed status but portfolio state may drift until manual intervention.

4. **Historical data row malformed**  
   XIRR loop skips bad row silently, producing incomplete return metric with no user-facing or operator-facing signal.

5. **Migration failure beyond expected duplicate-column case**  
   Broad catches (`pass`) may hide startup schema issues, leading to latent runtime errors later.

---

## Improvements

## High priority

1. **Replace silent catches with explicit typed handling + logging**
- Convert `except Exception: ...` to narrower exceptions where possible.
- For intentionally tolerated failures, log at least `warning` with operation and identifiers.
- In API responses, add degradation metadata for non-fatal dependency failures (e.g., `warnings: [...]`).

2. **Standardize logging backend-wide**
- Ban `print` and `traceback.print_exc()` in application runtime paths.
- Use `logging` consistently with structured JSON payloads (same contract as `price_service`).
- Always include correlation fields (`job_id`, `portfolio_id`, `transfer_id`, route, op).

3. **Fix traceback preservation**
- Replace `raise e` with bare `raise` after rollback.

4. **Strengthen async failure strategy**
- Add retry policy (bounded retries + backoff) for recalculation jobs.
- Track idempotent repair tasks with durable queue/store instead of in-memory-only registry.
- Surface async failure state to clients in a machine-readable way (e.g., `status_url`, `repair_required`).

## Medium priority

5. **Make invalid query params fail fast (422)**
- For endpoints currently coercing invalid ints to `None`, return validation error with field name and expected format.

6. **Harden migration observability**
- For each migration, explicitly detect “already exists” vs unexpected `OperationalError` and log unexpected failures as errors.
- Emit a migration summary at startup (applied/skipped/failed counts).

7. **Expose metric integrity warnings**
- Where valuation skips rows, collect skipped-count and include in logs + optional response diagnostics for admin endpoints.

## Low priority

8. **Define error taxonomy and message guidelines**
- Introduce normalized error codes for dependency failures, parse failures, and degraded mode.
- Standardize user-safe vs operator-detailed messages.

9. **Add targeted tests for degradation and async failures**
- Tests should assert not only HTTP status/shape, but also emitted log events and job failure semantics.

---

## Quick win checklist

- [ ] Replace all `raise e` with `raise`.
- [ ] Replace runtime `print(...)` / `traceback.print_exc()` with structured logger calls.
- [ ] Convert silent query-param coercion into validation errors.
- [ ] Add warning payload when fallback path is used (PPK, metadata, XIRR row skip).
- [ ] Add retry wrapper for async recalculation jobs.
