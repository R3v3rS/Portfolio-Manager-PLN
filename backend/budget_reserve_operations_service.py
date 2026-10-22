"""Receipts, exact previews and atomic funding of several reserve envelopes."""
import hashlib
import json
from uuid import UUID, uuid4, uuid5

from api.exceptions import ApiError, ValidationError
from database import get_db


def state(db):
    # Include every envelope: another reservation can consume the same account.
    values = [list(db.execute(sql).fetchall()) for sql in (
        'SELECT id,balance,account_type FROM budget_accounts ORDER BY id',
        'SELECT id,version FROM budget_reserves ORDER BY id',
        'SELECT id,version FROM budget_entries_v2 ORDER BY id',
        'SELECT reserve_id,month,version FROM budget_reserve_month_plans ORDER BY reserve_id,month',
    )]
    return hashlib.sha256(json.dumps([[list(r) for r in rows] for rows in values]).encode()).hexdigest()


def check_state(db, expected):
    if expected is not None and expected != state(db):
        raise ApiError('reserve_preview_changed', 'Salda lub rezerwy zmieniły się. Sprawdź nowy podgląd przed zapisem.', status=409)


def accounts_snapshot(db):
    from budget_reserves_service import reserved_cents
    return {r['id']: dict(id=r['id'], name=r['name'], balance=round(r['balance']*100),
                         reserved=reserved_cents(db, r['id'])) for r in db.execute('SELECT * FROM budget_accounts')}


def account_changes(db, before, include_ids=()):
    after = accounts_snapshot(db)
    return [dict(account_id=i, account_name=a['name'], balance_before=a['balance']/100,
                 balance_after=after[i]['balance']/100, reserved_before=a['reserved']/100,
                 reserved_after=after[i]['reserved']/100,
                 available_before=(a['balance']-a['reserved'])/100,
                 available_after=(after[i]['balance']-after[i]['reserved'])/100)
            for i, a in before.items() if i in include_ids or (a['balance'], a['reserved']) != (after[i]['balance'], after[i]['reserved'])]


def receipt(db, token, reserve_id, entry_id, kind, fingerprint, result):
    from budget_reserves_service import _now
    db.execute('''INSERT INTO budget_reserve_operation_receipts
        (request_id,reserve_id,entry_id,kind,request_payload,result_json,created_at) VALUES(?,?,?,?,?,?,?)''',
        (token, reserve_id, entry_id, kind, fingerprint, json.dumps(result, ensure_ascii=False), _now()))


def preview(reserve_id, data):
    from budget_reserves_service import move
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        current = state(db)
        payload = {k: v for k, v in data.items() if k not in ('expected_state', 'request_id')}
        result = move(reserve_id, dict(payload, request_id=str(uuid4())), within_transaction=True)
        return dict(**result['summary'], expected_state=current)
    finally:
        db.rollback()


def funding_plan():
    from budget_reserves_service import date, reserved_cents, _row
    from budget_planning_service import reserve_plans
    db = get_db()
    month = date.today().strftime('%Y-%m')
    available = {a['id']: max(0, round(a['balance']*100)-reserved_cents(db,a['id']))
                 for a in db.execute("SELECT * FROM budget_accounts WHERE account_type='BANK' AND UPPER(currency)='PLN'")}
    rows = []
    for p in reserve_plans(db, month):
        if not p['active'] or p['remaining'] <= 0:
            continue
        row = _row(db, p['reserve_id'])
        need = round(p['remaining']*100)
        proposed = min(need, available.get(p['account_id'], 0))
        available[p['account_id']] = available.get(p['account_id'], 0)-proposed
        rows.append(dict(reserve_id=row['id'], name=row['name'], account_id=p['account_id'],
                         priority=p['priority'], remaining=need/100, proposed=proposed/100, version=row['version']))
    return dict(month=month, date=date.today().isoformat(), rows=rows,
                remaining=round(sum(r['remaining'] for r in rows),2), proposed=round(sum(r['proposed'] for r in rows),2))


def fund_batch(data, *, dry_run=False):
    from budget_reserves_service import _request_id, _fingerprint, move
    from routes_budget_workspace import positive_id, cents
    db = get_db()
    token = str(uuid4()) if dry_run else _request_id(data)
    fingerprint = _fingerprint(data)
    try:
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT * FROM budget_reserve_operation_receipts WHERE request_id=?',(token,)).fetchone()
        if previous:
            if previous['kind']!='BATCH' or previous['request_payload']!=fingerprint:
                raise ApiError('reserve_batch_conflict','Ten zestaw zapisano z innymi kwotami.',status=409)
            return json.loads(previous['result_json'])
        check_state(db, data.get('expected_state'))
        if not dry_run and not data.get('expected_state'):
            raise ValidationError('Najpierw sprawdź podgląd odłożeń.')
        current = state(db)
        raw = data.get('rows')
        if not isinstance(raw,list) or not 1<=len(raw)<=100:
            raise ValidationError('Wybierz od 1 do 100 odłożeń.')
        ids = set()
        before = accounts_snapshot(db)
        results = []
        for r in raw:
            if not isinstance(r,dict):
                raise ValidationError('Nieprawidłowe odłożenie.')
            reserve_id = positive_id(r.get('reserve_id'),'rezerwa')
            if reserve_id in ids:
                raise ValidationError('Rezerwa może wystąpić w zestawie tylko raz.')
            ids.add(reserve_id)
            cents(r.get('amount'))
            result = move(reserve_id, dict(kind='ADD', amount=r['amount'], date=data.get('date'),
                account_id=r.get('account_id'), version=r.get('version'), notes='Zbiorcze odłożenie według planu',
                request_id=str(uuid5(UUID(token),str(reserve_id)))), within_transaction=True)
            results.append(result)
        result = dict(expected_state=current, rows=results, accounts=account_changes(db,before),
                      total=round(sum(r['summary']['amount'] for r in results),2))
        if not dry_run:
            receipt(db,token,None,None,'BATCH',fingerprint,result)
            db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction:
            db.rollback()


def surplus_options(row, data, saved, amount, day):
    """The remaining cash stays at its existing bank location."""
    from budget_reserves_service import _date
    default = 'FREE' if row['monthly_amount_cents'] is None and row['frequency']=='ONCE' else 'KEEP'
    mode = data.get('surplus_mode', default)
    if mode not in ('FREE','KEEP','RESERVE'):
        raise ValidationError('Wybierz przeznaczenie nadwyżki.')
    if row['monthly_amount_cents'] is not None and mode!='KEEP':
        raise ValidationError('Nadwyżkę miesięcznej puli zwolnij osobno; pula pozostaje aktywna.')
    next_due = None
    if row['monthly_amount_cents'] is None and row['frequency']=='ONCE' and mode=='KEEP':
        next_due = _date(data.get('next_due_date'),'Termin kolejnego cyklu')
        if next_due<=day:
            raise ValidationError('Kolejny cykl wymaga terminu późniejszego niż płatność.')
    return mode, max(0,saved-amount), next_due


def transfer_surplus(db, source, data, amount, releases, covered, budget_cost, token, day, now):
    from budget_reserves_service import _row, _version, last_reserve_day
    from budget_plan_history import freeze
    from routes_budget_workspace import positive_id
    target_id = positive_id(data.get('surplus_reserve_id'),'rezerwa nadwyżki')
    if target_id==source['id']:
        raise ValidationError('Wybierz inną rezerwę dla nadwyżki.')
    target = _row(db,target_id,_version(dict(version=data.get('surplus_reserve_version'))))
    last = last_reserve_day(db,target_id)
    if target['is_archived'] or target['completed_at'] or day<target['start_date'] or (last and day<last):
        raise ValidationError('Wybierz aktywną rezerwę bez późniejszych operacji.')
    freeze(db,target_id,include_current=True)
    ids=[]
    budget_left=max(0,-budget_cost-covered)
    for account_id, released in releases:
        spent=min(covered,released); covered-=spent
        extra=released-spent
        if not extra:
            continue
        share=min(budget_left,extra); budget_left-=share
        ids.append(db.execute('''INSERT INTO budget_reserve_movements
            (reserve_id,account_id,cycle,kind,amount_cents,budget_cost_cents,date,notes,request_id,request_payload,created_at)
            VALUES(?,?,?,'ADD',?,?,?,?,?,?,?)''', (target_id,account_id,target['cycle'],extra,share,day,
                f'Nadwyżka z rezerwy: {source["name"]}',str(uuid5(UUID(token),f'surplus-{account_id}')),'{}',now)).lastrowid)
    db.execute('UPDATE budget_reserves SET version=version+1,updated_at=? WHERE id=?',(now,target_id))
    return dict(before=dict(target),movement_ids=ids,amount=amount/100)
