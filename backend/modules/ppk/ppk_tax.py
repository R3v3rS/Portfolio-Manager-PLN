from decimal import Decimal

class PPKTaxCalculator:
    TAX_RATE = Decimal('0.19')
    EMPLOYER_TAXABLE_WEIGHT = Decimal('1.0')
    EMPLOYEE_TAXABLE_WEIGHT = Decimal('1.0')

    @staticmethod
    def calculate_tax(profit: Decimal, is_employer: bool = False) -> Decimal:
        """
        Calculates tax based on profit and source (employee vs employer).
        Tax applies only to positive profit.
        """
        if profit <= 0:
            return Decimal('0')
        
        weight = PPKTaxCalculator.EMPLOYER_TAXABLE_WEIGHT if is_employer else PPKTaxCalculator.EMPLOYEE_TAXABLE_WEIGHT
        # Tax = Profit * Weight * Rate
        tax = profit * weight * PPKTaxCalculator.TAX_RATE
        return tax
