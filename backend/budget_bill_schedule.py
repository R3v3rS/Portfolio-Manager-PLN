"""Shared bill occurrences for the monthly plan, forecast and reminders."""
import calendar
from datetime import date


def due_in_month(row, month):
    if row['end_month'] and month > row['end_month']:
        return False
    if row['frequency'] == 'ONCE':
        return row['due_month'] == month
    start = row['start_month']
    if start and month < start:
        return False
    if row['interval_months'] == 1:
        return True
    if not start:
        return False
    y, m = map(int, month.split('-')); sy, sm = map(int, start.split('-'))
    return ((y-sy)*12+m-sm) % row['interval_months'] == 0


def due_date(row, month):
    y, m = map(int, month.split('-'))
    return date(y, m, min(row['due_day'], calendar.monthrange(y,m)[1])).isoformat()


def amount_cents(row, month):
    if row['promotion_end'] and row['regular_amount_cents'] is not None and due_date(row,month) > row['promotion_end']:
        return row['regular_amount_cents']
    return row['amount_cents']


def category_bill_cents(db, month, pln_only=False):
    from collections import defaultdict
    from budget_bill_funding import occurrence
    result = defaultdict(int)
    currency = " AND UPPER(COALESCE(a.currency,'PLN'))='PLN'" if pln_only else ''
    for row in db.execute('SELECT b.* FROM budget_bills_v2 b JOIN budget_accounts a ON a.id=b.account_id WHERE 1=1'+currency):
        if due_in_month(row,month):
            value = occurrence(db,row,month)
            if value['media'] or (not row['active'] and not value['paid']): continue
            result[row['category_id']] += value['unfunded_cents']
    return dict(result)
