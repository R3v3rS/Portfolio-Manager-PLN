"""One definition of a bill's amount and earmarked funding for a month."""
import calendar


def occurrence(db, bill, month):
    from budget_bill_schedule import amount_cents
    end = f"{month}-{calendar.monthrange(*map(int, month.split('-')))[1]:02d}"
    payment = db.execute('''SELECT p.entry_id,e.amount_cents FROM budget_bill_payments_v2 p
        JOIN budget_entries_v2 e ON e.id=p.entry_id WHERE p.bill_id=? AND p.month=?''',
        (bill['id'], month)).fetchone()
    amount = payment['amount_cents'] if payment else amount_cents(bill, month)
    cover = 0
    media = False
    if bill['reserve_id']:
        reserve = db.execute('SELECT * FROM budget_reserves WHERE id=?', (bill['reserve_id'],)).fetchone()
        media = bool(reserve and reserve['monthly_amount_cents'] is not None and not reserve['open_ended']
                     and month >= (reserve['monthly_start_month'] or reserve['start_date'][:7]))
        if payment:
            cover = -db.execute('''SELECT COALESCE(SUM(budget_cost_cents),0) FROM budget_reserve_movements
                WHERE reserve_id=? AND budget_entry_id=? AND kind='SPEND' ''',
                (bill['reserve_id'], payment['entry_id'])).fetchone()[0]
        else:
            cover = db.execute('''SELECT COALESCE(SUM(budget_cost_cents),0) FROM budget_reserve_movements
                WHERE reserve_id=? AND date<=?''', (bill['reserve_id'], end)).fetchone()[0]
    cover = min(amount, max(0, cover))
    return dict(amount_cents=amount, covered_cents=cover, unfunded_cents=amount-cover,
                paid=bool(payment), media=media, entry_id=payment['entry_id'] if payment else None)


def category_coverage(db, month):
    from collections import defaultdict
    from budget_bill_schedule import due_in_month
    covered, settled = defaultdict(int), defaultdict(int)
    for bill in db.execute('SELECT * FROM budget_bills_v2'):
        if not due_in_month(bill, month): continue
        value = occurrence(db, bill, month)
        if (not bill['active'] and not value['paid']) or value['media']: continue
        covered[bill['category_id']] += value['covered_cents']
        if value['paid']: settled[bill['category_id']] += value['covered_cents']
    return covered, settled
