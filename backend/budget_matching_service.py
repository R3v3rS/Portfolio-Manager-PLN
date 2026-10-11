"""Suggestions only: matching never creates a second payment automatically."""
def suggestions(db,month):
    from budget_bill_schedule import due_in_month
    from budget_bills_service import candidates
    from budget_import_parser import normalized
    result=[]
    for bill in db.execute('SELECT * FROM budget_bills_v2 WHERE active=1'):
        if not due_in_month(bill,month) or db.execute('SELECT 1 FROM budget_bill_payments_v2 WHERE bill_id=? AND month=?',(bill['id'],month)).fetchone():continue
        found=candidates(db,bill,month)
        if found:result.append(dict(kind='BILL',id=bill['id'],title=bill['title'],candidates=found))
    for reserve in db.execute('''SELECT r.* FROM budget_reserves r WHERE is_archived=0 AND completed_at IS NULL
        AND NOT EXISTS(SELECT 1 FROM budget_bills_v2 b WHERE b.reserve_id=r.id AND b.active=1)'''):
        words={w for w in normalized(reserve['name']).split() if len(w)>2}
        found=[]
        for entry in db.execute('''SELECT e.* FROM budget_entries_v2 e WHERE e.kind='EXPENSE' AND e.account_id=? AND substr(e.date,1,7)=?
            AND NOT EXISTS(SELECT 1 FROM budget_bill_payments_v2 p WHERE p.entry_id=e.id)
            AND NOT EXISTS(SELECT 1 FROM budget_reserve_movements m WHERE m.budget_entry_id=e.id)
            AND NOT EXISTS(SELECT 1 FROM loan_installment_payments p WHERE p.budget_entry_id=e.id)
            AND NOT EXISTS(SELECT 1 FROM loan_overpayments p WHERE p.budget_entry_id=e.id)
            AND NOT EXISTS(SELECT 1 FROM budget_purchase_refunds p WHERE p.purchase_entry_id=e.id)
            ORDER BY e.date DESC,e.id DESC''',(reserve['account_id'],month)):
            same_category=reserve['category_id'] and db.execute('SELECT 1 FROM budget_entry_lines_v2 WHERE entry_id=? AND category_id=?',(entry['id'],reserve['category_id'])).fetchone()
            same_name=words.intersection(normalized((entry['merchant'] or '')+' '+entry['description']).split())
            if same_category or same_name:found.append(dict(id=entry['id'],date=entry['date'],amount=entry['amount_cents']/100,description=entry['description'],version=entry['version'],account_id=entry['account_id']))
        if found:result.append(dict(kind='RESERVE',id=reserve['id'],title=reserve['name'],candidates=found[:20]))
    return result
