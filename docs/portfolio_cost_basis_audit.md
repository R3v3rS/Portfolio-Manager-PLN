# Portfolio Cost Basis Audit

## Summary
- **Is SELL logic correct?** YES ✅
- **Is average price reliable?** YES ✅

## Findings
The audit confirms that the portfolio transaction logic correctly maintains the cost basis and average buy price during SELL operations.

### Description of current SELL implementation
The system uses a **weighted average cost** (WAC) method. 
- When a **BUY** occurs, the `total_cost` is increased by the transaction total, and a new `average_buy_price` is calculated as `total_cost / quantity`.
- When a **SELL** occurs, the `total_cost` is reduced proportionally to the quantity sold, using the *current* `average_buy_price`:
  `total_cost -= sold_qty * average_buy_price`
- This ensures that the `average_buy_price` remains constant after a sell, which is the correct behavior for cost-basis accounting.

### Whether it violates cost-basis rules
No violations were found. The system correctly avoids subtracting the transaction total (sell price * quantity) from the cost basis, which would have corrupted the average buy price.

## Issues (if any)
No critical issues were found. 

### Minor Observation: Precision
The main trade services use `float` for calculations, while the audit/rebuild service uses `Decimal`. This could theoretically lead to sub-penny discrepancies over many transactions, but the audit service handles this with a 0.01 tolerance (epsilon) for cost basis comparisons, which is sufficient for practical purposes.

## Fix Recommendation
No code changes are required as the implementation already follows the correct logic.

### Recommendation for Future Robustness
While not a bug, it is recommended to eventually migrate all financial calculations in `PortfolioTradeService` and `PortfolioImportService` to use the `Decimal` type (already used in `PortfolioAuditService` and `PortfolioCoreService`) to eliminate any potential floating-point rounding issues in extreme edge cases.

## Test Cases

### 1. Standard Weighted Average
- **Scenario**: Buy 2 @ 100, Buy 2 @ 200, Sell 2.
- **Trace**:
  1. Buy 2 @ 100: `qty=2`, `total_cost=200`, `avg=100`
  2. Buy 2 @ 200: `qty=4`, `total_cost=600`, `avg=150`
  3. Sell 2: `cost_basis = 2 * 150 = 300`. `new_total_cost = 600 - 300 = 300`. `new_qty = 2`.
- **Expected result**: `average_buy_price` = 150.
- **System behavior**: Matches expected result.

### 2. Partial Sell using Fraction
- **Scenario**: Buy 5 @ 100, Sell 1 (1/5th).
- **Trace**:
  1. Buy 5 @ 100: `qty=5`, `total_cost=500`, `avg=100`
  2. Sell 1: `cost_basis = 1 * 100 = 100`. `new_total_cost = 500 - 100 = 400`. `new_qty = 4`.
- **Expected result**: `average_buy_price` = 100.
- **System behavior**: Matches expected result.

### 3. Full Close
- **Scenario**: Buy 2 @ 100, Sell 2.
- **Trace**:
  1. Buy 2 @ 100: `qty=2`, `total_cost=200`, `avg=100`
  2. Sell 2: `new_qty = 0`. System deletes the holding row.
- **Expected result**: Holding record removed.
- **System behavior**: Matches expected result.

## Final Verdict
**SAFE** ✅

The core logic for cost basis reduction and average price calculation is sound and correctly implemented across both manual trades and automated imports. Cross-portfolio aggregation also correctly uses weighted averages at the parent level.
