from dataclasses import dataclass
from decimal import Decimal
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
    currentValueEmployee: float | None
    profitEmployee: float | None
    taxEmployee: float | None
    netValueEmployee: float | None

    purchaseValueEmployer: float
    currentValueEmployer: float | None
    profitEmployer: float | None
    taxEmployer: float | None
    netValueEmployer: float | None

    totalPurchaseValue: float
    totalCurrentValue: float | None
    totalNetValue: float | None
    totalTax: float | None
    totalProfit: float | None

    withdrawalTax: float | None
    employerToZUS: float | None
    withdrawalResult: float | None
