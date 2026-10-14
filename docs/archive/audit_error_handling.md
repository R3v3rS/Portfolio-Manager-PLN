# Error Handling Audit

## Scope

This audit reviewed backend Python modules with focus on:

- silent failures
- broad `except` blocks
- inconsistent error types
- swallowed exceptions
- unclear error messages
- missing validation

Primary scan commands used:

- `rg -n "except\s*:\s*$|except\s+Exception|except\s+BaseException|pass\s*(#.*)?$|return\s+None\s*$" backend tests`
- `python` pattern scan (summary):
  - `broad_except`: **65**
  - `swallowed_pass`: **22**
  - `raise e`: **18**
  - `return None`: **34**

---

## Problematic patterns

### 1) Silent failures and swallowed exceptions

#### Findings

1. **Schema migration errors are frequently swallowed with `pass`**, which can hide real migration drift or partial failures.
   - `backend/database.py` has many `except sqlite3.OperationalError: pass` migration blocks (e.g. around lines 430-535).
   - `backend/database.py` also has a bare `except: pass` when adding `radar_cache.score` (lines 185-189).
   - Holdings unique-constraint migration catches all exceptions, prints, then `pass`es (lines 605-607).

2. **Import parsing fallback hides malformed JSON silently.**
   - `backend/routes_imports.py` converts `confirmed_hashes_raw`; on any exception it silently sets `confirmed_hashes = []` (lines 23-28).

3. **PPK and valuation flows degrade silently when upstream fetches fail.**
   - `backend/routes_ppk.py` swallows all exceptions while fetching current price and silently returns `currentPrice: null` (lines 23-27).
   - `backend/portfolio_valuation_service.py` swallows exceptions for PPK current price and continues with `None` (lines 663-666).

4. **Inner-loop parse failures are swallowed with `continue`**, dropping records without trace.
   - `backend/portfolio_valuation_service.py` XIRR flow parsing uses `except Exception: continue` (lines 433-441 and 793-801).

#### Impact

- Data correctness issues become hard to detect (migrations and valuation).
- Users receive partial/incorrect results without actionable warnings.
- Production incidents may be discovered late due to missing observability.

#### Suggested improvements

- Replace silent `pass` in migrations with a helper that:
  - recognizes expected cases (`duplicate column`, etc.),
  - logs at `INFO` for expected idempotent cases,
  - raises for unexpected errors.
- For request parsing (`confirmed_hashes`), return `ValidationError` with field-level details when malformed JSON is provided.
- Where business flow continues with fallback values, include structured warning metadata in API response (or at minimum log with request context).
- In loop-level `continue` handlers, increment a counter and log a summary (`N records skipped`) to avoid invisible data loss.

---

### 2) Broad exception handling (`except Exception` / bare `except`)

#### Findings

1. **Bare except still exists.**
   - `backend/database.py` line 187 (`except:`).
   - `backend/routes_imports.py` line 27 (`except:`).
   - `backend/price_service.py` line 1356 (`except:`).

2. **High-frequency `except Exception` appears in services and background jobs.**
   - `backend/price_service.py` (multiple areas).
   - `backend/portfolio_trade_service.py` transaction methods wrap DB calls with `except Exception as e` then re-raise.
   - `backend/routes_transactions.py` async recalculation wrappers catch all exceptions and only set job status.

3. **Broad exception usage often conflates expected operational errors with programmer bugs.**
   - Example: parsing, network errors, and DB/logic errors are all caught under the same handler in several places.

#### Impact

- Masked programmer errors (e.g., `TypeError`, logic bugs) can be treated like transient runtime issues.
- Harder to triage true root causes.
- Inconsistent behavior between endpoints depending on where the broad catch occurs.

#### Suggested improvements

- Replace broad catches with explicit exception tuples:
  - network/provider layer: (`TimeoutError`, provider-specific HTTP errors, parsing errors),
  - DB layer: (`sqlite3.OperationalError`, `sqlite3.IntegrityError`),
  - input parsing: (`ValueError`, `TypeError`, `JSONDecodeError`).
- Reserve `except Exception` only at clear boundaries (top-level worker loop, Flask global error handler), and always include structured logging.
- Remove bare `except` entirely.

---

### 3) Inconsistent error typing and propagation

#### Findings

1. **Mixed use of `ValueError`, `ApiError`, and implicit 500 behavior for similar validation scenarios.**
   - Validation in some route layers maps to `ApiError(..., status=422)` (good).
   - Similar validation in service layers often raises generic `ValueError` (e.g., many portfolio trade flows).

2. **`raise e` anti-pattern appears repeatedly**, which discards original traceback context in Python.
   - Seen across services like `bond_service.py`, `watchlist_service.py`, `portfolio_trade_service.py`, `portfolio_core_service.py`, `budget_service.py`.

3. **String-only error messages with mixed language and format.**
   - Some messages are localized Polish, others English, some include internal phrasing not suitable for API consumers.

#### Impact

- Inconsistent API contracts and status semantics.
- Lower debugging quality (lost traceback chaining).
- Uneven user-facing experience and difficult localization.

#### Suggested improvements

- Introduce/standardize domain exceptions (`ValidationError`, `NotFoundError`, `ConflictError`, `ExternalDependencyError`) across services.
- In service DB transaction wrappers, use plain `raise` (not `raise e`) after rollback.
- Normalize message policy:
  - internal logs: rich technical context,
  - API payload: stable code + user-safe message + optional structured details,
  - one language policy or explicit i18n path.

---

### 4) Unclear error messages and observability gaps

#### Findings

1. **Print-based error reporting remains in core paths** instead of structured logging.
   - `backend/database.py` (migration error print).
   - `backend/portfolio_valuation_service.py` XIRR calculation errors use `print(...)`.

2. **Some fallback paths provide no error detail to clients**, even when client input is malformed.
   - `confirmed_hashes` malformed JSON silently coerced to empty list.
   - `current_price` query parameter in PPK endpoint is cast directly with `float(...)` and may throw unhandled `ValueError` (no explicit validation).

#### Suggested improvements

- Replace `print` with module logger calls and structured fields (`operation`, `portfolio_id`, `ticker`, `exception_type`).
- Validate query params consistently through shared validators (e.g., `require_number`-style for args).
- Use explicit error codes for parse/format failures (`INVALID_JSON`, `INVALID_QUERY_PARAM`, etc.).

---

### 5) Missing validation / weak input guards

#### Findings

1. **`current_price` in PPK GET endpoint lacks defensive parsing.**
   - `float(current_price_raw)` without try/validation can return 500 on bad input (`backend/routes_ppk.py`, line 21).

2. **`confirmed_hashes` type is not validated after JSON parse.**
   - Even if parse succeeds, type could be non-list/non-string structure, leading to downstream ambiguity (`backend/routes_imports.py`).

3. **Some fallback-to-default behaviors can hide domain data issues.**
   - Currency fallback to PLN on metadata failures in history build path (`backend/portfolio_history_service.py`, lines 155-159).

#### Suggested improvements

- Add strict schema validation for request payload/query params at route boundary.
- For fallback defaults, tag results with warning metadata and emit logs containing affected entities.
- Add tests for malformed query and malformed form-data payloads.

---

## Priority remediation plan

### P0 (high risk / high value)

1. Remove bare `except` in:
   - `backend/database.py`
   - `backend/routes_imports.py`
   - `backend/price_service.py`
2. Replace `raise e` with `raise` in all service transaction wrappers.
3. Stop swallowing migration exceptions without classification/logging.

### P1

1. Standardize exception taxonomy across service layer.
2. Add request validation for `routes_ppk` and `routes_imports` parsing edge cases.
3. Replace print statements with structured logging.

### P2

1. Add warning metadata and counters for fallback/skip flows.
2. Add regression tests covering:
   - malformed JSON in import confirmation,
   - malformed `current_price` query param,
   - migration unexpected-error behavior.

---

## Recommended target standard (short)

- No bare `except`.
- No `except Exception` unless at hard boundaries.
- No `raise e`; use `raise` to preserve traceback.
- No silent `pass` unless explicitly justified and logged.
- All client input validated at route boundary.
- Stable error envelope: `{code, message, details}` with deterministic status mapping.
