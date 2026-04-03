from datetime import date

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

    Raises:
        TypeError: If input structure or types are invalid.
        ValueError: If XIRR cannot be computed or does not converge.
    """
    # Validate top-level input is iterable cash-flow data.
    if isinstance(transactions, (str, bytes)):
        raise TypeError("transactions must be an iterable of (date, amount) tuples")
    try:
        txns_input = list(transactions)
    except TypeError as exc:
        raise TypeError("transactions must be an iterable of (date, amount) tuples") from exc

    if len(txns_input) < 2:
        raise ValueError("xirr requires at least two transactions")

    # Validate each transaction tuple and its element types.
    for idx, txn in enumerate(txns_input):
        if not isinstance(txn, tuple) or len(txn) != 2:
            raise TypeError(f"transaction at index {idx} must be a tuple of (date, amount)")
        txn_date, amount = txn
        if not isinstance(txn_date, date):
            raise TypeError(f"transaction date at index {idx} must be datetime.date")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise TypeError(f"transaction amount at index {idx} must be int or float")

    # Sort transactions by date
    # Make a copy to avoid modifying the original list
    txns = sorted(txns_input, key=lambda x: x[0])

    dates = [t[0] for t in txns]
    amounts = [t[1] for t in txns]

    # Check if we have at least one positive and one negative cash flow
    if not (any(a > 0 for a in amounts) and any(a < 0 for a in amounts)):
        raise ValueError("xirr requires at least one positive and one negative cash flow")

    min_date = dates[0]
    
    # Pre-calculate years for each transaction to speed up
    years = [(d - min_date).days / 365.0 for d in dates]

    def xnpv(rate):
        if rate <= -1.0:
            # Reject invalid rates explicitly instead of propagating infinity/NaN.
            raise ValueError("xirr failed: rate below -100% is invalid")
        
        return sum(amount / ((1.0 + rate) ** y) for amount, y in zip(amounts, years))

    def xnpv_prime(rate):
        if rate <= -1.0:
            # Reject invalid rates explicitly instead of propagating infinity/NaN.
            raise ValueError("xirr failed: rate below -100% is invalid")
        
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
                # Stop with explicit failure instead of returning a sentinel value.
                raise ValueError("xirr failed to converge: derivative too close to zero")

            new_rate = rate - f_val / f_prime
            
            if abs(new_rate - rate) < tolerance:
                return new_rate * 100.0
            
            rate = new_rate
            
            # Safety check for rate going too low
            if rate <= -1.0:
                rate = -0.99
                
        except (OverflowError, ZeroDivisionError) as exc:
            # Propagate numerical failure as an explicit convergence error.
            raise ValueError("xirr failed due to numerical instability") from exc

    # Explicitly report non-convergence after the iteration budget is exhausted.
    raise ValueError("xirr did not converge within the maximum number of iterations")
