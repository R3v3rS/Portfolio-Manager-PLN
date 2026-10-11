"""Shared quote freshness policy, including weekly PPK and foreign currency quotes."""
from datetime import date
import math


def quote_status(price, stamp, as_of=None):
    as_of = as_of or date.today()
    if price is None or not math.isfinite(float(price)) or float(price) <= 0:
        return 'incomplete'
    try:
        quoted_on = date.fromisoformat(str(stamp)[:10])
    except (ValueError, TypeError):
        return 'stale'
    if quoted_on > as_of or (as_of - quoted_on).days > 7:
        return 'stale'
    return 'ok'


def combined_status(statuses):
    statuses = set(statuses)
    return 'incomplete' if 'incomplete' in statuses else 'stale' if 'stale' in statuses else 'ok'
