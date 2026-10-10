"""Read-only checklist shown before closing a household month."""
import calendar
import hashlib
import json


def review(db,month):
    from budget_bill_schedule import due_in_month
    from budget_bills_service import serialize
    from budget_planning_service import reserve_plans
    from budget_loan_plan_service import items as loan_items
    from budget_reserves_service import reserved_cents
    first=month+'-01';end=f"{month}-{calendar.monthrange(*map(int,month.split('-')))[1]:02d}"
    accounts=[]
    for account in db.execute("SELECT * FROM budget_accounts WHERE UPPER(COALESCE(currency,'PLN'))='PLN'"):
        verified=db.execute("SELECT date FROM budget_account_reconciliations WHERE account_id=? AND record_type='RECONCILIATION' ORDER BY id DESC LIMIT 1",(account['id'],)).fetchone()
        accounts.append(dict(id=account['id'],name=account['name'],balance=round(account['balance'],2),reserved=reserved_cents(db,account['id'])/100,verified_on=verified[0] if verified else None))
    corrections=[dict(id=r['id'],name=r['name'],date=r['date'],amount=r['difference_cents']/100,notes=r['notes']) for r in db.execute('''SELECT r.*,a.name FROM budget_account_reconciliations r JOIN budget_accounts a ON a.id=r.account_id
        WHERE record_type='RECONCILIATION' AND date BETWEEN ? AND ? AND difference_cents!=0''',(first,end))]
    unpaid=[]
    for bill in db.execute('SELECT * FROM budget_bills_v2 WHERE active=1'):
        if due_in_month(bill,month):
            item=serialize(db,bill,month)
            if item['status']!='PAID': unpaid.append(dict(id=bill['id'],title=bill['title'],date=item['due_date'],amount=item['amount']))
    loans,warnings=loan_items(db,month)
    reserves=[r for r in reserve_plans(db,month) if r['remaining']>0]
    unassigned=db.execute("SELECT COUNT(*) FROM budget_entries_v2 WHERE classification_status='UNASSIGNED' AND kind='EXPENSE' AND date BETWEEN ? AND ?",(first,end)).fetchone()[0]
    result=dict(accounts=accounts,corrections=corrections,unpaid_bills=unpaid,unpaid_loans=[l for l in loans if not l['paid']],missing_reserves=reserves,unassigned=unassigned,warnings=warnings)
    result['token']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    from budget_month_snapshot import comparison
    result['closing_snapshot']=comparison(db,month)
    return result
