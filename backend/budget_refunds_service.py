"""Refunds use incoming cash, but reduce spending rather than reported income."""
from datetime import date
from api.exceptions import ApiError, ValidationError
from database import get_db
from budget_category_service import require_version
from budget_reserves_service import _request_id, _fingerprint, _account


def flows(db, first, end, pln_only=False):
    currency = " AND UPPER(COALESCE(a.currency,'PLN'))='PLN'" if pln_only else ''
    account_join=' JOIN budget_accounts a ON a.id=e.account_id' if pln_only else ''
    return db.execute('''SELECT
        COALESCE(SUM(CASE WHEN e.kind='INCOME' AND r.entry_id IS NULL THEN e.amount_cents ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN e.kind='EXPENSE' THEN e.amount_cents WHEN r.entry_id IS NOT NULL THEN -e.amount_cents ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN r.entry_id IS NOT NULL THEN e.amount_cents ELSE 0 END),0)
        FROM budget_entries_v2 e''' + account_join + '''
        LEFT JOIN budget_purchase_refunds r ON r.entry_id=e.id
        WHERE e.date BETWEEN ? AND ?''' + currency, (first,end)).fetchone()


def create(purchase_id, data):
    from routes_budget_workspace import cents, positive_id, day_value, insert_entry, validate_lines
    token, fingerprint, db = _request_id(data), _fingerprint(dict(data,purchase_id=purchase_id)), get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT * FROM budget_purchase_refunds WHERE request_id=?',(token,)).fetchone()
        if prior:
            if prior['request_payload']!=fingerprint: raise ApiError('refund_request_conflict','Ten zwrot zapisano z innymi danymi.',status=409)
            db.rollback(); return dict(id=prior['entry_id'])
        purchase=db.execute("SELECT * FROM budget_entries_v2 WHERE id=? AND kind='EXPENSE'",(purchase_id,)).fetchone()
        if not purchase: raise ValidationError('Wybierz zakup, którego dotyczy zwrot.')
        require_version(purchase,data.get('version'),'Zakup')
        amount=cents(data.get('amount'));day=day_value(data.get('date'))
        if day<purchase['date'] or day>date.today().isoformat(): raise ValidationError('Zwrot musi być otrzymany po zakupie, najpóźniej dzisiaj.')
        refunded=db.execute('''SELECT COALESCE(SUM(e.amount_cents),0) FROM budget_purchase_refunds r
            JOIN budget_entries_v2 e ON e.id=r.entry_id WHERE purchase_entry_id=?''',(purchase_id,)).fetchone()[0]
        if refunded+amount>purchase['amount_cents']: raise ValidationError('Łączne zwroty nie mogą przekroczyć kwoty zakupu.')
        account_id=positive_id(data.get('account_id',purchase['account_id']),'konto zwrotu');account=_account(db,account_id)
        lines=validate_lines(data,'EXPENSE',amount)
        mode=data.get('balance_mode','APPLY')
        if mode not in ('APPLY','HISTORY'): raise ValidationError('Wybierz wpływ zwrotu na saldo.')
        if data.get('existing_entry_id') is not None:
            entry_id=positive_id(data['existing_entry_id'],'wpływ z banku')
            entry=db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry_id,)).fetchone()
            if not entry or (entry['kind'],entry['account_id'],entry['amount_cents'],entry['date'])!=('INCOME',account_id,amount,day):
                raise ValidationError('Wybierz wpływ z banku o tej samej kwocie, dacie i koncie.')
            require_version(entry,data.get('entry_version'),'Wpływ')
            if db.execute('SELECT 1 FROM budget_expected_income_receipts WHERE budget_entry_id=?',(entry_id,)).fetchone() or db.execute('SELECT 1 FROM budget_purchase_refunds WHERE entry_id=?',(entry_id,)).fetchone():
                raise ValidationError('Ten wpływ jest już rozliczony.')
            db.execute('DELETE FROM budget_entry_lines_v2 WHERE entry_id=?',(entry_id,))
            for line in lines: db.execute('INSERT INTO budget_entry_lines_v2(entry_id,category_id,label,amount_cents) VALUES(?,?,?,?)',(entry_id,line['category_id'],line['label'],line['amount_cents']))
            db.execute('UPDATE budget_entries_v2 SET version=version+1 WHERE id=?',(entry_id,))
        else:
            if mode=='APPLY' and data.get('expected_balance')!=round(account['balance'],2): raise ApiError('refund_balance_conflict','Saldo zmieniło się. Odśwież dane.',status=409)
            entry_id=insert_entry(db,dict(account_id=account_id,kind='INCOME',amount_cents=amount,date=day,
                description='Zwrot: '+purchase['description'][:140],merchant=purchase['merchant'],lines=lines,cash_effect=int(mode=='APPLY')))
        db.execute('INSERT INTO budget_purchase_refunds VALUES(?,?,?,?)',(entry_id,purchase_id,token,fingerprint))
        db.execute('UPDATE budget_entries_v2 SET version=version+1 WHERE id=?',(purchase_id,))
        db.commit();return dict(id=entry_id)
    except Exception: db.rollback();raise
