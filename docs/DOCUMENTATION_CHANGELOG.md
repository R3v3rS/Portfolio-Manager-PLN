# Documentation Changelog

**Date:** 2026-04-02

## Changed files
- `docs/AUDIT_AND_IMPROVEMENT_PLAN.md`
- `docs/PROJECT_GUIDE.md`
- `docs/DOCUMENTATION_CHANGELOG.md` (new)

---

## What was changed

1. Replaced roadmap-style audit content with a structured technical audit document.
2. Reworked project guide into a deterministic source-of-truth specification.
3. Added explicit rules and formulas for:
   - transaction ownership (`portfolio_id` parent, `sub_portfolio_id` child scope),
   - SELL cost basis (`total_cost -= sold_qty * avg_price`),
   - parent weighted aggregation (`SUM(total_cost) / SUM(quantity)`),
   - XTB fraction quantity parsing (`"1/5" -> 1`),
   - cash-flow normalization (`tx_total = abs(amount)`).
4. Added explicit section separating ledger transactions (source-of-truth) from derived holdings.
5. Added explicit edge cases and risks (precision, FX ambiguity, aggregation drift, rounding).
6. Normalized terminology across documents.

---

## Why it was changed

1. Previous documents mixed onboarding, status tracking, and architecture narrative without deterministic accounting rules.
2. Key backend behaviors existed in implementation but were not captured as explicit documentation contracts.
3. Terminology inconsistencies created risk of misinterpretation in future development and maintenance.
4. Missing formulas for SELL and aggregation could cause incorrect future implementations.

---

## Key improvements

1. Documentation now provides explicit, testable accounting invariants.
2. Parent/child scope semantics are unambiguous.
3. Import behavior for XTB quantity and absolute cash normalization is explicit.
4. Risk register is now directly tied to potential correctness failures.
5. Project guide can be used as an implementation reference, not only onboarding text.

---

## Detected risks to track

1. Mixed float + decimal precision across runtime and audit paths.
2. Potential FX interpretation mismatches between valuation and book-cost assumptions.
3. Aggregation logic distributed across multiple services (regression surface).
4. Rounding drift in repeated partial sell sequences.
5. Performance overhead of dynamic historical reconstruction for large ledgers.

