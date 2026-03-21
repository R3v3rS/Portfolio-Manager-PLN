from typing import TypedDict

class PPKTransactionDTO(TypedDict):
    id: int
    portfolio_id: int
    date: str
    employee_units: float
    employer_units: float
    price_per_unit: float

class PPKSummaryDTO(TypedDict):
    purchaseValueEmployee: float
    currentValueEmployee: float
    profitEmployee: float
    taxEmployee: float
    netValueEmployee: float

    purchaseValueEmployer: float
    currentValueEmployer: float
    profitEmployer: float
    taxEmployer: float
    netValueEmployer: float

    totalPurchaseValue: float
    totalCurrentValue: float
    totalNetValue: float
    totalTax: float
    totalProfit: float
