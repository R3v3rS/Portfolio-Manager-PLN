"""Read-only allocation of shared category limits; no money is moved here."""
from collections import defaultdict


def category_details(db, month, categories, bills, loans, reserves):
    daily = defaultdict(int)
    media_ids = {r['category_id'] for r in reserves
                 if r.get('monthly_amount') is not None and not r.get('open_ended')}
    # Refunds inherit the original payment's role, also when it was in an older month.
    for row in db.execute('''SELECT l.category_id,l.amount_cents,e.kind,r.purchase_entry_id,
            EXISTS(SELECT 1 FROM budget_bill_payments_v2 p WHERE p.entry_id=COALESCE(r.purchase_entry_id,e.id)) bill,
            EXISTS(SELECT 1 FROM loan_installment_payments p WHERE p.budget_entry_id=COALESCE(r.purchase_entry_id,e.id)
                UNION ALL SELECT 1 FROM loan_overpayments p WHERE p.budget_entry_id=COALESCE(r.purchase_entry_id,e.id)) loan,
            EXISTS(SELECT 1 FROM budget_reserve_movements p WHERE p.budget_entry_id=COALESCE(r.purchase_entry_id,e.id)) reserve
        FROM budget_entry_lines_v2 l JOIN budget_entries_v2 e ON e.id=l.entry_id
        LEFT JOIN budget_purchase_refunds r ON r.entry_id=e.id
        WHERE substr(e.date,1,7)=? AND (e.kind='EXPENSE' OR r.entry_id IS NOT NULL)''', (month,)):
        if row['bill'] or row['loan'] or row['reserve'] or row['category_id'] in media_ids:
            continue
        daily[row['category_id']] += row['amount_cents'] * (-1 if row['purchase_entry_id'] else 1)
    pending = defaultdict(int)
    media_left = defaultdict(int)
    for bill in bills:
        if bill['status'] != 'PAID' and bill['reserve_id'] not in {
                r['reserve_id'] for r in reserves if r['category_id'] in media_ids}:
            pending[bill['category_id']] += round(bill.get('unfunded', bill['amount']) * 100)
    for loan in loans:
        if not loan['paid']:
            pending[loan['category_id']] += round(loan['amount'] * 100)
    for reserve in reserves:
        if reserve['category_id'] in media_ids:
            media_left[reserve['category_id']] += round(reserve['remaining'] * 100)
    result = {}
    for category in categories:
        ids = [category['id'], *[c['id'] for c in categories if c['parent_id'] == category['id']]]
        planned = max(0, round((category['planned'] - category['planned_bills']) * 100))
        spent = sum(daily[i] for i in ids)
        left = max(0, round(category['remaining'] * 100)
                   - sum(pending[i] + media_left[i] for i in ids))
        result[category['id']] = dict(
            ordinary_planned=planned/100, ordinary_spent=spent/100, ordinary_remaining=left/100,
            payments_planned=category['planned_bills'], payments_pending=sum(pending[i] for i in ids)/100,
            media_remaining=sum(media_left[i] for i in ids)/100,
            ordinary_over=max(0, spent-planned)/100,
        )
    return result
