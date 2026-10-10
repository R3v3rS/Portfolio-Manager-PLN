"""Funding a reserve with an own-account transfer, within the caller's transaction."""
import re
from uuid import UUID, uuid5

from api.exceptions import ApiError, ValidationError
from database import get_db
from budget_import_parser import normalized
from budget_reserves_service import (
    _account, _fingerprint, _now, _request_id, _row, last_reserve_day, reserved_cents,
)
from routes_budget_workspace import positive_id, text_field


def budget_pool(db, reserve_id):
    return max(0, db.execute('SELECT COALESCE(SUM(budget_cost_cents),0) FROM budget_reserve_movements WHERE reserve_id=?',
                            (reserve_id,)).fetchone()[0])


def fund(db, reserve_id, target_id, amount, day, notes, token, *, history=False):
    """Cash has already moved (or is already included in the current bank balance)."""
    reserve = _row(db, reserve_id)
    if reserve['is_archived'] or reserve['completed_at']:
        raise ValidationError('Wybrana rezerwa nie jest aktywna.')
    last = last_reserve_day(db, reserve_id)
    if last and day < last:
        raise ValidationError('Wpłata nie może poprzedzać ostatniej operacji rezerwy. Importuj wyciągi od najstarszego.')
    if day < reserve['start_date']:
        if not history or last:
            raise ValidationError('Wpłata nie może poprzedzać początku cyklu rezerwy.')
        # The first historical payment can precede the date the goal was created.
        db.execute('UPDATE budget_reserves SET start_date=? WHERE id=?', (day, reserve_id))
    account = _account(db, target_id)
    if amount > max(0, round(float(account['balance'])*100)-reserved_cents(db, target_id)):
        raise ValidationError('Na koncie docelowym brakuje wolnych środków na tę rezerwę. Sprawdź saldo i tryb importu.')
    db.execute('''INSERT INTO budget_reserve_movements
        (reserve_id,account_id,cycle,kind,amount_cents,budget_cost_cents,date,notes,request_id,request_payload,created_at)
        VALUES (?,?,?,'ADD',?,?,?,?,?,?,?)''',
        (reserve_id,target_id,reserve['cycle'],amount,amount,day,notes,
         str(uuid5(UUID(token),'reserve-funding')), '{}', _now()))
    db.execute('UPDATE budget_reserves SET version=version+1,updated_at=? WHERE id=?', (_now(),reserve_id))


def rules(db):
    return [dict(r, active=bool(r['active']),reserve_active=bool(r['reserve_active'])) for r in db.execute('''SELECT t.*,s.name source_name,a.name target_name,r.name reserve_name,
        CASE WHEN r.is_archived=0 AND r.completed_at IS NULL THEN 1 ELSE 0 END reserve_active
        FROM budget_reserve_transfer_rules t JOIN budget_accounts s ON s.id=t.source_account_id
        JOIN budget_accounts a ON a.id=t.target_account_id JOIN budget_reserves r ON r.id=t.reserve_id ORDER BY t.id''')]


def match_rules(db, account_id, item):
    matches = []
    description = normalized(item['description'])
    for rule in rules(db):
        side = 'source_account_id' if item['bank_kind']=='EXPENSE' else 'target_account_id'
        pattern = normalized(rule['pattern'])
        # Whole phrases also make short purposes like OC safe from matching "BLOC".
        if rule['active'] and rule['reserve_active'] and rule[side]==account_id and re.search(r'(?<!\w)'+re.escape(pattern)+r'(?!\w)', description):
            matches.append(rule)
    if len(matches)>1:
        return None, ['Kilka reguł pasuje do przelewu na rezerwę. Wybierz cel ręcznie; automatyczne odkładanie jest wstrzymane.']
    return (matches[0] if matches else None), []


def save_rule(data, rule_id=None):
    pattern = text_field(data.get('pattern'), 'Tekst w opisie przelewu', 120)
    if not normalized(pattern):
        raise ValidationError('Opis reguły musi zawierać litery lub cyfry określające cel.')
    source, target, reserve_id = (positive_id(data.get(key), key) for key in ('source_account_id','target_account_id','reserve_id'))
    active = data.get('active', True)
    if source==target or type(active) is not bool:
        raise ValidationError('Wybierz dwa różne własne konta i stan reguły.')
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        _account(db, source); _account(db, target)
        reserve = _row(db, reserve_id)
        if active and (reserve['is_archived'] or reserve['completed_at']):
            raise ValidationError('Reguła wymaga aktywnej rezerwy.')
        payload = _fingerprint(dict(pattern=pattern,source_account_id=source,target_account_id=target,reserve_id=reserve_id,active=active))
        if rule_id is None:
            token = _request_id(data)
            prior = db.execute('SELECT * FROM budget_reserve_transfer_rules WHERE request_id=?', (token,)).fetchone()
            if prior:
                if prior['request_payload']!=payload:
                    raise ApiError('reserve_rule_conflict','Ten zapis przyjęto z innymi danymi.',status=409)
                return dict(id=prior['id'])
            rule_id = db.execute('''INSERT INTO budget_reserve_transfer_rules
                (pattern,source_account_id,target_account_id,reserve_id,active,request_id,request_payload,created_at)
                VALUES (?,?,?,?,?,?,?,?)''', (pattern,source,target,reserve_id,int(active),token,payload,_now())).lastrowid
        else:
            prior = db.execute('SELECT * FROM budget_reserve_transfer_rules WHERE id=?', (rule_id,)).fetchone()
            if not prior or type(data.get('version')) is not int or prior['version']!=data['version']:
                raise ApiError('reserve_rule_conflict','Reguła zmieniła się. Odśwież dane.',status=409)
            db.execute('''UPDATE budget_reserve_transfer_rules SET pattern=?,source_account_id=?,target_account_id=?,reserve_id=?,
                active=?,version=version+1 WHERE id=?''', (pattern,source,target,reserve_id,int(active),rule_id))
        db.commit()
        return dict(id=rule_id)
    except Exception:
        db.rollback(); raise
    finally:
        if db.in_transaction:
            db.rollback()
