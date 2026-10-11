"""Shared return calculations; missing or ambiguous results stay unavailable."""
import math
from collections import defaultdict

def modified_dietz(opening, closing, flows, start, end):
    """End-of-day flow convention; no invented rate for a nonpositive base."""
    if opening is None or closing is None:
        return None
    days = (end - start).days + 1
    base = opening + sum(amount * (end - day).days / days for day, amount in flows)
    if base <= 1e-9:
        return None
    value = (closing - opening - sum(amount for _, amount in flows)) / base * 100
    return round(value, 4) if math.isfinite(value) else None


def money_weighted(flows):
    """Solve conventional cash flows with a guaranteed unique root."""
    grouped = defaultdict(float)
    for day, amount in flows:
        grouped[day] += amount
    points = sorted((day, amount) for day, amount in grouped.items() if abs(amount) > 1e-9)
    if len(points) < 2 or (points[-1][0] - points[0][0]).days < 365:
        return None
    if not any(amount < 0 for _, amount in points) or not any(amount > 0 for _, amount in points):
        return None
    signs = [amount > 0 for _, amount in points]
    if sum(left != right for left, right in zip(signs, signs[1:])) != 1:
        return None
    scale = sum(abs(amount) for _, amount in points)
    years = [((day - points[0][0]).days / 365, amount / scale) for day, amount in points]

    def npv(log_rate):
        # Positive normalization preserves the zero and prevents overflow.
        exponents = [-period * log_rate for period, _ in years]
        shift = max(exponents)
        return sum(amount * math.exp(exponent - shift) for exponent, (_, amount) in zip(exponents, years))

    brackets = []
    previous, previous_value = -16.0, npv(-16.0)
    for i in range(1, 129):
        current = -16 + i * .25
        value = npv(current)
        if value == 0:
            brackets.append((current, current))
        elif previous_value != 0 and value * previous_value < 0:
            brackets.append((previous, current))
        previous, previous_value = current, value
    if len(brackets) != 1:
        return None
    low, high = brackets[0]
    for _ in range(80):
        middle = (low + high) / 2
        if npv(low) * npv(middle) <= 0:
            high = middle
        else:
            low = middle
    return round(math.expm1((low + high) / 2) * 100, 4)
