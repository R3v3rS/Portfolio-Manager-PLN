"""Stable loan budget settings and explicit links to already booked expenses."""
import json
from datetime import date, timedelta
from api.exceptions import ValidationError, NotFoundError


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS loan_budget_settings (
        loan_id INTEGER PRIMARY KEY REFERENCES loans(id) ON DELETE CASCADE,
        account_id INTEGER REFERENCES budget_accounts(id), category_id INTEGER REFERENCES budget_categories_v2(id),
        version INTEGER NOT NULL DEFAULT 1)''')
    for table in ('loan_installment_payments','loan_overpayments'):
        columns={r['name'] for r in db.execute(f'PRAGMA table_info({table})')}
        for column,definition in [('budget_entry_created','INTEGER NOT NULL DEFAULT 1'),('linked_entry_before','TEXT')]:
            if column not in columns: db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
    for loan in db.execute('SELECT id FROM loans').fetchall(): ensure_settings(db,loan['id'])


def ensure_settings(db,loan_id):
    if db.execute('SELECT 1 FROM loan_budget_settings WHERE loan_id=?',(loan_id,)).fetchone():return
    last=db.execute('''SELECT e.id,e.account_id FROM loan_installment_payments p JOIN budget_entries_v2 e ON e.id=p.budget_entry_id
        WHERE p.loan_id=? ORDER BY p.paid_on DESC,p.id DESC LIMIT 1''',(loan_id,)).fetchone()
    category=db.execute('SELECT category_id FROM budget_entry_lines_v2 WHERE entry_id=? ORDER BY id LIMIT 1',(last['id'],)).fetchone() if last else None
    if not category:
        category=db.execute('SELECT category_id FROM loan_budget_settings WHERE category_id IS NOT NULL ORDER BY loan_id LIMIT 1').fetchone()
    if not category:
        category=db.execute("SELECT id FROM budget_categories_v2 WHERE (parent_id IS NULL AND icon='ReceiptText') OR name='Rachunki' COLLATE NOCASE ORDER BY CASE WHEN parent_id IS NULL THEN 0 ELSE 1 END,sort_order,id LIMIT 1").fetchone()
    if not category:
        order=db.execute('SELECT COALESCE(MAX(sort_order),-1)+1 FROM budget_categories_v2').fetchone()[0]
        category_id=db.execute("INSERT INTO budget_categories_v2(name,icon,sort_order) VALUES('Rachunki','ReceiptText',?)",(order,)).lastrowid
    else:category_id=category[0]
    db.execute('INSERT INTO loan_budget_settings(loan_id,account_id,category_id) VALUES(?,?,?)',(loan_id,last['account_id'] if last else None,category_id))


def settings(db,loan_id):
    from budget_planning_service import settings as planning_settings
    row=db.execute('SELECT * FROM loan_budget_settings WHERE loan_id=?',(loan_id,)).fetchone()
    # Directly inserted legacy/test loans can be read before the next migration.
    fallback=db.execute('SELECT category_id FROM loan_budget_settings WHERE category_id IS NOT NULL ORDER BY loan_id LIMIT 1').fetchone()
    if not fallback:fallback=db.execute("SELECT id FROM budget_categories_v2 WHERE (parent_id IS NULL AND icon='ReceiptText') OR name='Rachunki' COLLATE NOCASE ORDER BY CASE WHEN parent_id IS NULL THEN 0 ELSE 1 END,sort_order,id LIMIT 1").fetchone()
    result=dict(row) if row else dict(loan_id=loan_id,account_id=None,category_id=fallback[0] if fallback else None,version=0)
    result['resolved_account_id']=result['account_id'] or planning_settings(db)['resolved_loan_account_id']
    return result


def candidates(db,account_id,paid_on,amount_cents):
    if not account_id:return []
    day=date.fromisoformat(paid_on)
    return [dict(r,amount=r['amount_cents']/100) for r in db.execute('''SELECT e.id,e.date,e.description,e.amount_cents,e.version,e.account_id,e.cash_effect
        FROM budget_entries_v2 e JOIN budget_accounts a ON a.id=e.account_id
        WHERE e.kind='EXPENSE' AND e.account_id=? AND e.amount_cents=? AND e.date BETWEEN ? AND ?
        AND UPPER(COALESCE(a.currency,'PLN'))='PLN'
        AND NOT EXISTS(SELECT 1 FROM budget_bill_payments_v2 p WHERE p.entry_id=e.id)
        AND NOT EXISTS(SELECT 1 FROM loan_installment_payments p WHERE p.budget_entry_id=e.id)
        AND NOT EXISTS(SELECT 1 FROM loan_overpayments p WHERE p.budget_entry_id=e.id)
        AND NOT EXISTS(SELECT 1 FROM budget_reserve_movements p WHERE p.budget_entry_id=e.id)
        AND NOT EXISTS(SELECT 1 FROM budget_purchase_refunds p WHERE p.purchase_entry_id=e.id OR p.entry_id=e.id)
        ORDER BY ABS(julianday(e.date)-julianday(?)),e.id DESC LIMIT 20''',
        (account_id,amount_cents,(day-timedelta(days=3)).isoformat(),(day+timedelta(days=3)).isoformat(),paid_on))]


def link_expense(db,loan_id,data,account_id,paid_on,amount_cents):
    from routes_budget_workspace import positive_id
    from budget_category_service import require_version
    entry_id=positive_id(data.get('existing_entry_id'),'istniejący wydatek')
    entry=db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry_id,)).fetchone()
    if not entry:raise NotFoundError('Nie znaleziono wybranego wydatku.')
    require_version(entry,data.get('entry_version'),'Wydatek')
    if entry_id not in {r['id'] for r in candidates(db,account_id,paid_on,amount_cents)}:
        raise ValidationError('Wydatek musi mieć tę samą kwotę i konto, datę w pobliżu płatności oraz nie może rozliczać innego zobowiązania.')
    before=dict(classification_status=entry['classification_status'],lines=[dict(r) for r in db.execute('SELECT category_id,label,amount_cents FROM budget_entry_lines_v2 WHERE entry_id=? ORDER BY id',(entry_id,))])
    category_id=settings(db,loan_id)['category_id']
    if category_id:
        db.execute('DELETE FROM budget_entry_lines_v2 WHERE entry_id=?',(entry_id,))
        db.execute('INSERT INTO budget_entry_lines_v2(entry_id,category_id,label,amount_cents) VALUES(?,?,?,?)',(entry_id,category_id,'',amount_cents))
        db.execute("UPDATE budget_entries_v2 SET classification_status='GENERAL',version=version+1 WHERE id=?",(entry_id,))
    return entry_id,json.dumps(before,ensure_ascii=False)


def restore_expense(db,payment):
    if payment['linked_entry_before']:
        old=json.loads(payment['linked_entry_before'])
        db.execute('DELETE FROM budget_entry_lines_v2 WHERE entry_id=?',(payment['budget_entry_id'],))
        for line in old['lines']:
            db.execute('INSERT INTO budget_entry_lines_v2(entry_id,category_id,label,amount_cents) VALUES(?,?,?,?)',(payment['budget_entry_id'],line['category_id'],line['label'],line['amount_cents']))
        db.execute('UPDATE budget_entries_v2 SET classification_status=?,version=version+1 WHERE id=?',(old['classification_status'],payment['budget_entry_id']))
