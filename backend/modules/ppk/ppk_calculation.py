from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional
from .ppk_tax import PPKTaxCalculator
from .ppk_dto import PPKSummaryDTO

class PPKCalculation:
    @staticmethod
    def _to_decimal(value) -> Decimal:
        return Decimal(str(value or 0))

    @staticmethod
    def _q(value: Decimal, places: str = '0.01') -> float:
        return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))

    @staticmethod
    def calculate_metrics(transactions: List[Dict[str, Any]], current_price: Optional[Decimal] = None) -> PPKSummaryDTO:
        # Initialize aggregators
        emp_units = Decimal('0')
        empr_units = Decimal('0')
        
        emp_purchase_val = Decimal('0')
        empr_purchase_val = Decimal('0')
        
        emp_current_val = Decimal('0')
        empr_current_val = Decimal('0')
        
        # 1. Aggregation
        for t in transactions:
            u_emp = PPKCalculation._to_decimal(t['employee_units'])
            u_empr = PPKCalculation._to_decimal(t['employer_units'])
            price = PPKCalculation._to_decimal(t['price_per_unit'])
            
            # Purchase Value
            emp_units += u_emp
            empr_units += u_empr
            
            emp_purchase_val += u_emp * price
            empr_purchase_val += u_empr * price
            
            # Current Value
            # If current_price is provided, use it. Else fallback to purchase price.
            c_price = current_price if current_price is not None else price
            
            emp_current_val += u_emp * c_price
            empr_current_val += u_empr * c_price

        # 2. Profit (Profit = Current - Purchase)
        emp_profit = emp_current_val - emp_purchase_val
        empr_profit = empr_current_val - empr_purchase_val
        
        # 3. Tax
        emp_tax = PPKTaxCalculator.calculate_tax(emp_profit, is_employer=False)
        empr_tax = PPKTaxCalculator.calculate_tax(empr_profit, is_employer=True)
        
        # 4. Net Profit
        emp_net_profit = emp_profit - emp_tax
        empr_net_profit = empr_profit - empr_tax
        
        # 5. Net Value (Purchase + Net Profit)
        emp_net_val = emp_purchase_val + emp_net_profit
        empr_net_val = empr_purchase_val + empr_net_profit
        
        # Totals
        total_purchase_val = emp_purchase_val + empr_purchase_val
        total_current_val = emp_current_val + empr_current_val
        total_net_val = emp_net_val + empr_net_val
        total_tax = emp_tax + empr_tax
        total_profit = emp_profit + empr_profit
        
        # Legacy / Extra fields for compatibility
        total_units = emp_units + empr_units
        avg_price = (total_purchase_val / total_units) if total_units > 0 else Decimal('0')
        net_profit_amount = total_profit - total_tax

        return {
            "purchaseValueEmployee": PPKCalculation._q(emp_purchase_val),
            "currentValueEmployee": PPKCalculation._q(emp_current_val),
            "profitEmployee": PPKCalculation._q(emp_profit),
            "taxEmployee": PPKCalculation._q(emp_tax),
            "netValueEmployee": PPKCalculation._q(emp_net_val),
            
            "purchaseValueEmployer": PPKCalculation._q(empr_purchase_val),
            "currentValueEmployer": PPKCalculation._q(empr_current_val),
            "profitEmployer": PPKCalculation._q(empr_profit),
            "taxEmployer": PPKCalculation._q(empr_tax),
            "netValueEmployer": PPKCalculation._q(empr_net_val),
            
            "totalPurchaseValue": PPKCalculation._q(total_purchase_val),
            "totalCurrentValue": PPKCalculation._q(total_current_val),
            "totalNetValue": PPKCalculation._q(total_net_val),
            "totalTax": PPKCalculation._q(total_tax),
            "totalProfit": PPKCalculation._q(total_profit),

            # Legacy fields
            "totalUnits": PPKCalculation._q(total_units, '0.0001'),
            "averagePrice": PPKCalculation._q(avg_price),
            "totalContribution": PPKCalculation._q(total_purchase_val),
            # For PPK UI we expose withdrawable value (after PPK withdrawal weights and 19% tax).
            "currentValue": PPKCalculation._q(total_net_val),
            "profit": PPKCalculation._q(net_profit_amount),
            "tax": PPKCalculation._q(total_tax),
            "netProfit": PPKCalculation._q(net_profit_amount)
        }
