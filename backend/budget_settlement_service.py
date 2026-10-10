"""Atomic reversal of a settlement; linked bank expenses retain their cash effect."""
import json
from api.exceptions import ApiError, NotFoundError, ValidationError
from database import get_db


def preview(db, entry_id):
    entry=db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry_id,)).fetchone()
    if not entry: raise NotFoundError('Wydatek nie istnieje.')
    settlement=db.execute('SELECT * FROM budget_settlements WHERE entry_id=?',(entry_id,)).fetchone()
    bill=db.execute('SELECT * FROM budget_bill_payments_v2 WHERE entry_id=?',(entry_id,)).fetchone()
    if not settlement and not bill: raise ValidationError('Ten wpis nie rozlicza rachunku ani rezerwy.')
    # Old records lack provenance: do not guess whether an expense was created.
    if not settlement and db.execute('SELECT 1 FROM budget_reserve_movements WHERE budget_entry_id=?',(entry_id,)).fetchone():
        raise ValidationError('Starsze rozliczenie rezerwy nie ma danych potrzebnych do bezpiecznego cofnięcia.')
    delete=bool(settlement and settlement['created_entry'])
    if db.execute('SELECT 1 FROM budget_purchase_refunds WHERE entry_id=? OR purchase_entry_id=?',(entry_id,entry_id)).fetchone():
        raise ValidationError('Najpierw cofnij zwroty powiązane z tym zakupem.')
    if delete and (entry['receipt_filename'] or db.execute('SELECT 1 FROM budget_import_sources WHERE entry_id=?',(entry_id,)).fetchone()):
        raise ValidationError('Do wydatku dołączono dokument. Usuń jego powiązanie przed cofnięciem całej płatności.')
    reserve=None;restore=0
    if settlement and settlement['reserve_id']:
        before=json.loads(settlement['before_json']);ids=json.loads(settlement['movement_ids'])
        reserve=db.execute('SELECT * FROM budget_reserves WHERE id=?',(settlement['reserve_id'],)).fetchone()
        later=db.execute('SELECT 1 FROM budget_reserve_movements WHERE reserve_id=? AND id>?',(reserve['id'],max(ids))).fetchone()
        immutable=('name','notes','account_id','target_cents','category_id','monthly_amount_cents','open_ended','is_archived','frequency','anniversary')
        if later or any(reserve[k]!=before[k] for k in immutable):
            raise ApiError('settlement_reserve_changed','Po płatności zmieniono rezerwę. Najpierw rozlicz jej późniejsze operacje.',status=409)
        restore=sum(db.execute('SELECT amount_cents FROM budget_reserve_movements WHERE id=?',(i,)).fetchone()[0] for i in ids)
        if db.execute('SELECT 1 FROM budget_account_transfers WHERE reserve_id=? AND created_at>?',(reserve['id'],settlement['recorded_at'])).fetchone():
            raise ValidationError('Po rozliczeniu przeniesiono rezerwę między kontami. Najpierw rozlicz ten przelew.')
    account=db.execute('SELECT * FROM budget_accounts WHERE id=?',(entry['account_id'],)).fetchone()
    prior_entry=json.loads(settlement['before_json'] or '{}').get('entry_before') if settlement else None
    return dict(entry_id=entry_id,entry_version=entry['version'],account_id=account['id'],account_name=account['name'],
        balance_before=round(account['balance'],2),balance_after=round(account['balance']+(entry['amount_cents']/100 if delete and entry['cash_effect'] else 0),2),
        delete_expense=delete,reserve_id=reserve['id'] if reserve else None,reserve_version=reserve['version'] if reserve else None,
        restored_reserve=restore/100,bill_id=bill['bill_id'] if bill else None,
        message='Wydatek zostanie cofnięty wraz z wpływem na saldo.' if delete else 'Istniejący wydatek pozostanie w historii i saldzie. Cofniemy wyłącznie jego rozliczenie.'+(' Przywrócimy też kategorię sprzed powiązania.' if prior_entry else ''))


def reverse(entry_id,data):
    from budget_reserves_service import _request_id,_fingerprint,_now
    db=get_db();token=_request_id(data);fingerprint=_fingerprint(dict(data,entry_id=entry_id))
    try:
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT * FROM budget_settlement_reversals WHERE request_id=?',(token,)).fetchone()
        if previous:
            if previous['request_payload']!=fingerprint: raise ApiError('reversal_request_conflict','To cofnięcie zapisano z innymi danymi.',status=409)
            return dict(entry_id=entry_id)
        view=preview(db,entry_id)
        if any(data.get(key)!=view[key] for key in ('entry_version','reserve_version','balance_before')):
            raise ApiError('settlement_preview_changed','Dane zmieniły się. Odśwież podgląd cofnięcia.',status=409)
        entry=dict(db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry_id,)).fetchone())
        settlement=db.execute('SELECT * FROM budget_settlements WHERE entry_id=?',(entry_id,)).fetchone()
        payments=[dict(r) for r in db.execute('SELECT * FROM budget_bill_payments_v2 WHERE entry_id=?',(entry_id,))]
        movements=[]
        if settlement and settlement['reserve_id']:
            ids=json.loads(settlement['movement_ids']);before=json.loads(settlement['before_json'])
            for i in ids:
                movements.append(dict(db.execute('SELECT * FROM budget_reserve_movements WHERE id=?',(i,)).fetchone()))
                if db.execute('SELECT 1 FROM budget_month_closing_items WHERE movement_id=?',(i,)).fetchone(): raise ValidationError('Ta operacja należy do zamknięcia miesiąca.')
                db.execute('DELETE FROM budget_reserve_movements WHERE id=?',(i,))
            db.execute('''UPDATE budget_reserves SET due_date=?,start_date=?,cycle=?,completed_at=?,version=version+1,updated_at=? WHERE id=?''',
                (before['due_date'],before['start_date'],before['cycle'],before['completed_at'],_now(),settlement['reserve_id']))
        for saved in [*payments,*movements]:
            if saved.get('request_id'): db.execute('INSERT OR IGNORE INTO budget_cancelled_requests VALUES(?)',(saved['request_id'],))
        for payment in payments: db.execute('UPDATE budget_bills_v2 SET version=version+1 WHERE id=?',(payment['bill_id'],))
        db.execute('DELETE FROM budget_bill_payments_v2 WHERE entry_id=?',(entry_id,))
        db.execute('DELETE FROM budget_settlements WHERE entry_id=?',(entry_id,))
        if view['delete_expense']:
            db.execute('UPDATE budget_accounts SET balance=? WHERE id=?',(view['balance_after'],view['account_id']))
            db.execute('DELETE FROM budget_entry_lines_v2 WHERE entry_id=?',(entry_id,))
            db.execute('DELETE FROM budget_entries_v2 WHERE id=?',(entry_id,))
        else:
            prior_entry=json.loads(settlement['before_json'] or '{}').get('entry_before') if settlement else None
            if prior_entry:
                db.execute('DELETE FROM budget_entry_lines_v2 WHERE entry_id=?',(entry_id,))
                for line in prior_entry['lines']:
                    db.execute('INSERT INTO budget_entry_lines_v2(entry_id,category_id,label,amount_cents) VALUES(?,?,?,?)',
                        (entry_id,line['category_id'],line['label'],line['amount_cents']))
                db.execute('UPDATE budget_entries_v2 SET classification_status=? WHERE id=?',(prior_entry['classification_status'],entry_id))
            db.execute('UPDATE budget_entries_v2 SET version=version+1 WHERE id=?',(entry_id,))
        audit=dict(preview=view,entry=entry,payments=payments,movements=movements,settlement=dict(settlement) if settlement else None)
        db.execute('INSERT INTO budget_settlement_reversals VALUES(?,?,?,?,?)',(token,fingerprint,entry_id,json.dumps(audit,ensure_ascii=False),_now()))
        db.commit();return dict(entry_id=entry_id)
    except Exception:db.rollback();raise
    finally:
        if db.in_transaction:db.rollback()
