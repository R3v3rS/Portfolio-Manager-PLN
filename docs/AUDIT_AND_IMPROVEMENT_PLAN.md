# Documentation Audit and Improvement Plan

**Date:** 2026-04-02  
**Status:** Completed documentation audit + remediation plan aligned to current backend behavior.

This document records: (1) detected documentation defects, (2) root causes, (3) prioritized corrective actions, and (4) technical recommendations.

---

## 1. Audit Scope
Files audited:
- `docs/AUDIT_AND_IMPROVEMENT_PLAN.md` (previous version)
- `docs/PROJECT_GUIDE.md` (previous version)

Reference logic used for alignment:
- transaction write paths (`deposit/withdraw/buy/sell/dividend/import`)
- holdings and deterministic rebuild rules
- parent/child aggregation behavior
- valuation and FX conversion flows

---

## 2. Detected Issues

## A) Logical errors

1. **Ownership model under-specified and partially misleading**  
   Prior docs did not consistently enforce that transaction ownership is parent-based with child scope in `sub_portfolio_id`.

2. **Aggregation rules were descriptive but not deterministic**  
   Parent aggregation of holdings was not expressed as an explicit formula (`SUM(total_cost)/SUM(quantity)`).

3. **Holdings vs transactions source-of-truth ambiguity**  
   Prior text did not clearly separate transactions as primary ledger and holdings as derived/materialized state.

4. **SELL cost basis rule not explicit**  
   Documentation lacked an explicit mandatory equation for average-cost reduction during partial sells.

5. **Import quantity parsing edge case undocumented**  
   XTB fraction parsing behavior (`"1/5" -> 1`) was not documented as a contract.

6. **Cash-flow normalization not stated as hard rule**  
   Import normalization `tx_total = abs(amount)` was present in code paths but not specified as canonical behavior.

## B) Inconsistencies between documents

1. **Mixed terminology** (`subportfolio`, `sub-portfolio`, parent/main/main scope) without dictionary-level normalization.
2. **Narrative mismatch**: one doc acted as roadmap/status log, the other as architecture guide, but neither was authoritative for deterministic accounting rules.
3. **Different granularity**: behavioral formulas appeared in fragments and were absent in corresponding sections in the other document.

## C) Missing critical information

1. Explicit SELL reduction rule:
   - `total_cost -= sold_qty * avg_price`
2. Explicit parent aggregated avg formula:
   - `SUM(total_cost) / SUM(quantity)`
3. Explicit transaction ownership rule:
   - `portfolio_id = parent`, `sub_portfolio_id = child scope`
4. Explicit XTB quantity fraction handling:
   - `"1/5" -> qty = 1`
5. Explicit normalization rule:
   - `tx_total = abs(amount)`
6. Explicit statement that holdings are rebuildable derived state from ledger transactions.
7. Risk notes around mixed float/decimal precision boundaries.

## D) Duplications

1. Repeated architecture summaries without deterministic behavioral rules.
2. Repeated high-level route/service descriptions that did not add operational semantics.
3. Overlap in history/value narratives that were not linked to precise invariants.

## E) Technical debt / risk areas highlighted by audit

1. **Precision debt (HIGH):** mixed `float` runtime logic and decimal-based audit/rebuild can diverge.
2. **FX interpretation ambiguity (MEDIUM):** valuation and fee application are deterministic but historical broker-consistent FX mapping is not fully documented end-to-end.
3. **Aggregation drift risk (MEDIUM):** parent totals assembled in multiple services.
4. **Rounding accumulation (MEDIUM):** repeated partial sells may create cent-level drift.
5. **History compute cost (LOW/MEDIUM):** dynamic daily reconstruction can become expensive at scale.

---

## 3. Root Cause Analysis

1. **Documentation intent drift**  
   Existing docs mixed changelog, roadmap, onboarding, and specification roles in the same pages.

2. **Spec-by-narrative, not spec-by-rules**  
   Critical accounting behavior was described narratively rather than as formulas/invariants.

3. **Insufficient cross-file governance**  
   No explicit “source of truth” hierarchy between docs caused inconsistent wording and omitted hard constraints.

4. **Backend evolution outpaced docs**  
   Parent/child and repair/rebuild behavior evolved faster than final documentation cleanup.

---

## 4. Prioritized Fix Plan

## HIGH priority (must hold for correctness)
1. Define canonical ownership model (`portfolio_id` parent + `sub_portfolio_id` child scope).
2. Define deterministic BUY/SELL formulas including mandatory SELL cost-basis equation.
3. Define parent aggregation formula for weighted average cost.
4. Define import normalization and XTB quantity parsing contract.
5. Establish one authoritative guide as source of truth.

## MEDIUM priority (stability and maintainability)
1. Normalize terminology across all docs.
2. Add explicit derived-state statement for holdings and repair/audit behavior.
3. Document critical edge cases (partial sell, archived child, parent-own + child same ticker).
4. Record precision/FX/rounding risks and expected mitigation direction.

## LOW priority (future quality improvements)
1. Add operational examples for API request/response payloads in dedicated API docs.
2. Add “invariant checklist” section for regression test authors.
3. Add traceability table mapping each rule to tests.

---

## 5. Implemented Documentation Improvements (this pass)

1. Rewrote `docs/PROJECT_GUIDE.md` into an authoritative specification-oriented guide.
2. Added deterministic formulas for BUY/SELL/aggregation/cash-flow semantics.
3. Added explicit ownership and scope model for parent/child behavior.
4. Added explicit XTB quantity and amount normalization rules.
5. Added consolidated edge cases and risk register.
6. Reframed this file into an actionable audit document with root causes and prioritized actions.

---

## 6. Technical Recommendations

1. **Adopt decimal-first accounting policy** (target: eliminate float in book-cost/cash mutation paths).
2. **Centralize aggregation primitives** (single helper for parent aggregate formulas).
3. **Introduce invariant-based test suite** for:
   - parent/child ownership constraints,
   - partial sell cost basis,
   - aggregate weighted average,
   - import quantity and abs-amount normalization.
4. **Document FX accounting policy explicitly** (transaction-time vs valuation-time conversion fields and rounding).
5. **Add a doc QA gate** requiring terminology checks and cross-file rule consistency before merge.

---

## 7. Acceptance Criteria for Documentation Quality

Documentation is acceptable when:
1. All critical accounting behaviors are expressed as explicit formulas/rules.
2. No contradiction exists between `PROJECT_GUIDE` and audit plan.
3. Ownership and aggregation semantics are deterministic and testable from text alone.
4. Critical risks are listed with mitigation direction.
5. A new maintainer can implement or validate behavior without reading source code first.

