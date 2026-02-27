from datetime import date
import math

def xirr(transactions, guess=0.1):
    """
    Calculates the Extended Internal Rate of Return (XIRR).

    Args:
        transactions: A list of tuples (date, amount), where date is a datetime.date object
                      and amount is a float.
                      - Negative amounts represent investments (outflows).
                      - Positive amounts represent returns/withdrawals (inflows).
        guess: Initial guess for the rate of return (default 0.1 for 10%).

    Returns:
        The annualized rate of return as a percentage (e.g., 12.5 for 12.5%).
        Returns 0.0 if calculation fails or is not applicable.
    """
    if not transactions or len(transactions) < 2:
        return 0.0

    # Sort transactions by date
    # Make a copy to avoid modifying the original list
    txns = sorted(transactions, key=lambda x: x[0])

    dates = [t[0] for t in txns]
    amounts = [t[1] for t in txns]

    # Check if we have at least one positive and one negative cash flow
    if not (any(a > 0 for a in amounts) and any(a < 0 for a in amounts)):
        return 0.0

    min_date = dates[0]
    
    # Pre-calculate years for each transaction to speed up
    years = [(d - min_date).days / 365.0 for d in dates]

    def xnpv(rate):
        if rate <= -1.0:
            # If rate is -100% or less, the value is undefined or infinite for fractional powers
            return float('inf')
        
        return sum(amount / ((1.0 + rate) ** y) for amount, y in zip(amounts, years))

    def xnpv_prime(rate):
        if rate <= -1.0:
            return float('inf')
        
        # Derivative of amount * (1+rate)^(-y) is amount * (-y) * (1+rate)^(-y-1)
        return sum(-y * amount / ((1.0 + rate) ** (y + 1.0)) for amount, y in zip(amounts, years))

    rate = guess
    max_iterations = 100
    tolerance = 1e-6

    for _ in range(max_iterations):
        try:
            f_val = xnpv(rate)
            f_prime = xnpv_prime(rate)

            if abs(f_prime) < 1e-10:
                # Derivative too small, try to perturb or just stop
                return 0.0

            new_rate = rate - f_val / f_prime
            
            if abs(new_rate - rate) < tolerance:
                return new_rate * 100.0
            
            rate = new_rate
            
            # Safety check for rate going too low
            if rate <= -1.0:
                rate = -0.99
                
        except (OverflowError, ZeroDivisionError):
            return 0.0

    # If no convergence, return 0.0
    return 0.0
