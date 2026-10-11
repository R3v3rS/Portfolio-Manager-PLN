"""Unpaid obligations remain committed even when a shared cap is overspent."""
from collections import defaultdict


def pending_by_root(db,month,categories,loans,include_monthly=True):
    from budget_bill_schedule import due_in_month,amount_cents
    from budget_bill_funding import occurrence
    roots={c['id']:c['parent_id'] or c['id'] for c in categories}
    pending=defaultdict(int)
    for bill in db.execute('SELECT * FROM budget_bills_v2 WHERE active=1'):
        if not due_in_month(bill,month) or db.execute('SELECT 1 FROM budget_bill_payments_v2 WHERE bill_id=? AND month=?',(bill['id'],month)).fetchone():
            continue
        amount=amount_cents(bill,month)
        if bill['reserve_id'] and not include_monthly:
            reserve=db.execute('SELECT monthly_amount_cents,monthly_start_month,start_date,open_ended FROM budget_reserves WHERE id=?',(bill['reserve_id'],)).fetchone()
            if reserve and not reserve['open_ended'] and reserve['monthly_amount_cents'] is not None and month>=(reserve['monthly_start_month'] or reserve['start_date'][:7]):continue
        amount=occurrence(db,bill,month)['unfunded_cents']
        pending[roots[bill['category_id']]]+=amount
    for loan in loans:
        if not loan['paid']:pending[roots.get(loan['category_id'])]+=round(loan['amount']*100)
    return pending
