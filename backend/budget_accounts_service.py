"""Recorded account balances, internal transfers and explicit balance reconciliation."""
from datetime import date
from decimal import Decimal, InvalidOperation

from api.exceptions import ApiError, ValidationError
from database import get_db
from routes_budget_workspace import STARTER_CATEGORIES, cents, positive_id, text_field
from budget_reserves_service import (
    _account, _date, _fingerprint, _now, _request_id, _row, _version,
    last_reserve_day, location_cents, locations, reserved_cents,
)
from budget_reserve_funding_service import fund
from budget_account_types import balance_cents, is_credit, require_cash, totals as account_totals


def _notes(data):
    value = data.get('notes','')
    if not isinstance(value,str) or len(value)>500:
        raise ValidationError('Notatka może mieć najwyżej 500 znaków.')
    return value.strip()


def _expected(data, key, current):
    value = data.get(key)
    try:
        if isinstance(value,bool):
            raise ValueError()
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError()
        expected = (-1 if number<0 else 1)*cents(abs(number),allow_zero=True)
    except (InvalidOperation,ValueError,TypeError):
        raise ValidationError('Odśwież zapisane saldo konta przed operacją.') from None
    if expected!=round(float(current)*100):
        raise ApiError('account_balance_conflict','Saldo zmieniło się od otwarcia formularza. Odśwież dane i sprawdź kwotę.',status=409)


def _retry(db,table,token,fingerprint):
    row = db.execute(f'SELECT id,request_payload FROM {table} WHERE request_id=?',(token,)).fetchone()
    if row and row['request_payload']!=fingerprint:
        raise ApiError('account_request_conflict','Ten zapis został już przyjęty z innymi danymi.',status=409)
    return dict(id=row['id']) if row else None


def _account_day(db,account_id):
    return db.execute('''SELECT MAX(date) FROM (
        SELECT date FROM budget_entries_v2 WHERE account_id=?
        UNION ALL SELECT date FROM budget_investment_transfers WHERE account_id=?
        UNION ALL SELECT date FROM budget_account_transfers WHERE source_account_id=? OR target_account_id=?
        UNION ALL SELECT date FROM budget_account_reconciliations WHERE account_id=? AND record_type='RECONCILIATION'
        UNION ALL SELECT date FROM budget_reserve_movements WHERE account_id=?)''',
        (account_id,account_id,account_id,account_id,account_id,account_id)).fetchone()[0]


def _cash_net(db, account_id):
    """Net booked cash; history-only imports and location moves have no effect."""
    return db.execute('''SELECT COALESCE(SUM(amount),0) FROM (
        SELECT cash_effect * CASE WHEN kind='INCOME' THEN amount_cents ELSE -amount_cents END amount
        FROM budget_entries_v2 WHERE account_id=?
        UNION ALL SELECT CASE WHEN direction='IN' THEN amount_cents ELSE -amount_cents END
        FROM budget_investment_transfers WHERE account_id=?
        UNION ALL SELECT cash_effect * CASE WHEN target_account_id=? THEN amount_cents ELSE -amount_cents END
        FROM budget_account_transfers WHERE move_money=1 AND (source_account_id=? OR target_account_id=?))''',
        (account_id,account_id,account_id,account_id,account_id)).fetchone()[0]


def _effective_opening(db, account):
    adjustments = db.execute("SELECT COALESCE(SUM(difference_cents),0) FROM budget_account_reconciliations WHERE account_id=? AND record_type='RECONCILIATION'",
                             (account['id'],)).fetchone()[0]
    return round(float(account['balance'])*100) - _cash_net(db,account['id']) - adjustments


def _opening_day(db, account):
    first = db.execute('''SELECT MIN(date) FROM (
        SELECT date FROM budget_entries_v2 WHERE account_id=? AND cash_effect=1
        UNION ALL SELECT date FROM budget_investment_transfers WHERE account_id=?
        UNION ALL SELECT date FROM budget_account_transfers
        WHERE move_money=1 AND cash_effect=1 AND (source_account_id=? OR target_account_id=?))''',
        (account['id'],account['id'],account['id'],account['id'])).fetchone()[0]
    return min(day for day in (date.today().isoformat(), str(account['created_at'])[:10], first) if day)


def set_opening_balance(account_id, data):
    """An opening balance is setup data, separate from income and corrections."""
    source_id = positive_id(data['from_reconciliation_id'],'korekta') if data.get('from_reconciliation_id') is not None else None
    amount = None
    token, fingerprint, db, now = _request_id(data), _fingerprint(dict(data,account_id=account_id,operation='OPENING')), get_db(), _now()
    try:
        db.execute('BEGIN IMMEDIATE')
        retry = _retry(db,'budget_account_reconciliations',token,fingerprint)
        if retry:
            return retry
        account = _account(db,account_id)
        if source_id is None:
            amount = balance_cents(data.get('balance'), account['account_type'])
        _expected(data,'expected_balance',account['balance'])
        opening = db.execute("SELECT id FROM budget_account_reconciliations WHERE account_id=? AND record_type='OPENING' ORDER BY id DESC LIMIT 1",(account_id,)).fetchone()
        expected_opening = positive_id(data['expected_opening_id'],'saldo początkowe') if data.get('expected_opening_id') is not None else None
        if expected_opening != (opening['id'] if opening else None):
            raise ApiError('opening_balance_conflict','Saldo początkowe zmieniło się. Odśwież dane przed zapisem.',status=409)
        previous = round(float(account['balance'])*100)
        old_opening = _effective_opening(db,account)
        day = _opening_day(db,account)
        if source_id is not None:
            source = db.execute("SELECT * FROM budget_account_reconciliations WHERE id=? AND account_id=? AND record_type='RECONCILIATION'",(source_id,account_id)).fetchone()
            if not source or opening:
                raise ValidationError('Wybierz korektę tego konta bez wcześniej ustawionego salda początkowego.')
            amount = old_opening + source['difference_cents']
            if abs(amount) > 999_999_999_99 or (amount < 0 and not is_credit(account)):
                raise ValidationError('Ta korekta nie odpowiada poprawnemu saldu początkowemu.')
            # Preserve the old cash effect and retry identity; only its role and
            # effective setup date change. The new request below is also retained.
            db.execute("UPDATE budget_account_reconciliations SET record_type='OPENING',opening_balance_cents=?,date=? WHERE id=?",
                       (amount,day,source_id))
            observed = previous
        else:
            observed = previous + amount - old_opening
            if abs(observed)>999_999_999_99:
                raise ValidationError('Wynikowe saldo konta przekracza dopuszczalny zakres.')
            db.execute('UPDATE budget_accounts SET balance=? WHERE id=?',(observed/100,account_id))
        record_id = db.execute('''INSERT INTO budget_account_reconciliations
            (account_id,previous_balance_cents,observed_balance_cents,difference_cents,date,notes,request_id,request_payload,created_at,record_type,opening_balance_cents)
            VALUES (?,?,?,?,?,?,?,?,?,'OPENING',?)''',
            (account_id,previous,observed,observed-previous,day,_notes(data),token,fingerprint,now,amount)).lastrowid
        db.commit()
        return dict(id=record_id)
    except Exception:
        db.rollback(); raise
    finally:
        if db.in_transaction:
            db.rollback()


def create(data):
    account_type = data.get('account_type', 'BANK')
    if account_type not in ('BANK', 'CREDIT_CARD'):
        raise ValidationError('Wybierz konto zwykłe albo kartę kredytową.')
    name = text_field(data.get('name'),'Nazwa konta',150)
    balance = balance_cents(data.get('balance'), account_type)
    token, fingerprint, db, now = _request_id(data), _fingerprint(dict(data,operation='CREATE')), get_db(), _now()
    try:
        db.execute('BEGIN IMMEDIATE')
        retry = _retry(db,'budget_account_reconciliations',token,fingerprint)
        if retry:
            row = db.execute('SELECT account_id FROM budget_account_reconciliations WHERE id=?',(retry['id'],)).fetchone()
            return dict(id=row['account_id'])
        account_id = db.execute("INSERT INTO budget_accounts (name,balance,currency,account_type) VALUES (?,?,'PLN',?)",(name,balance/100,account_type)).lastrowid
        db.execute('''INSERT INTO budget_account_reconciliations
            (account_id,previous_balance_cents,observed_balance_cents,difference_cents,date,notes,request_id,request_payload,created_at,record_type,opening_balance_cents)
            VALUES (?,?,?,0,?,?,?,?,?,'OPENING',?)''',
            (account_id,balance,balance,date.today().isoformat(),'Saldo początkowe przy dodaniu konta',token,fingerprint,now,balance))
        if not db.execute('SELECT 1 FROM budget_categories_v2 LIMIT 1').fetchone():
            for index,(label,icon) in enumerate(STARTER_CATEGORIES):
                db.execute('INSERT INTO budget_categories_v2 (name,icon,sort_order) VALUES (?,?,?)',(label,icon,index))
        db.commit()
        return dict(id=account_id)
    except Exception:
        db.rollback(); raise
    finally:
        if db.in_transaction:
            db.rollback()


def transfer(data):
    source_id = positive_id(data.get('source_account_id'),'konto źródłowe')
    target_id = positive_id(data.get('target_account_id'),'konto docelowe')
    if source_id==target_id:
        raise ValidationError('Wybierz dwa różne konta.')
    amount, day, notes = cents(data.get('amount')), _date(data.get('date'),'Data przelewu'), _notes(data)
    if day>date.today().isoformat():
        raise ValidationError('Zapisz przelew po jego wykonaniu.')
    reserve_id = positive_id(data['reserve_id'],'rezerwa') if data.get('reserve_id') is not None else None
    reserve_action = data.get('reserve_action','MOVE')
    if reserve_action not in ('MOVE','FUND') or (reserve_action=='FUND' and (reserve_id is None or not data.get('move_money'))):
        raise ValidationError('Odłożenie wymaga rzeczywistego przelewu i wskazania rezerwy.')
    move_money = data.get('move_money')
    if type(move_money) is not bool or (reserve_id is None and not move_money):
        raise ValidationError('Bez rezerwy można zapisać wyłącznie faktyczny przelew między kontami.')
    token, fingerprint, db, now = _request_id(data), _fingerprint(data), get_db(), _now()
    try:
        db.execute('BEGIN IMMEDIATE')
        retry = _retry(db,'budget_account_transfers',token,fingerprint)
        if retry:
            return retry
        source, target = _account(db,source_id), _account(db,target_id)
        require_cash(source)
        if reserve_id is not None:
            require_cash(target)
        if is_credit(target) and amount > max(0, -round(float(target['balance'])*100)):
            raise ValidationError('Spłata nie może przekraczać aktualnego zadłużenia karty. Odśwież saldo lub zmniejsz kwotę.')
        _expected(data,'source_balance',source['balance']); _expected(data,'target_balance',target['balance'])
        for account_id in (source_id,target_id):
            last = _account_day(db,account_id)
            if last and day<last:
                raise ValidationError('Data przelewu nie może poprzedzać ostatniej operacji na tych kontach.')
        source_balance, target_balance = round(float(source['balance'])*100), round(float(target['balance'])*100)
        cycle = None
        if reserve_id is not None:
            reserve = _row(db,reserve_id,_version(data))
            if reserve['is_archived'] or reserve['completed_at']:
                raise ValidationError('Rezerwa nie jest aktywna.')
            last = last_reserve_day(db,reserve_id)
            if day<reserve['start_date'] or (last and day<last):
                raise ValidationError('Data nie może poprzedzać ostatniej operacji rezerwy.')
            if reserve_action=='FUND':
                if amount>max(0,source_balance-reserved_cents(db,source_id)):
                    raise ValidationError('Na koncie źródłowym brakuje wolnych środków na nowe odłożenie.')
            elif amount>location_cents(db,reserve_id,source_id):
                raise ValidationError('Na koncie źródłowym nie ma takiej kwoty odłożonej na wybraną rezerwę.')
            if move_money:
                # A location with insufficient backing must be reconciled first.
                if source_balance<reserved_cents(db,source_id):
                    raise ValidationError('Rezerwy na koncie źródłowym przekraczają saldo. Najpierw sprawdź saldo i odłożone kwoty.')
            elif amount>max(0,target_balance-reserved_cents(db,target_id)):
                raise ValidationError('Konto docelowe nie ma tylu środków poza rezerwami.')
            cycle = reserve['cycle']
        elif amount>max(0,source_balance-reserved_cents(db,source_id)):
            raise ValidationError('Przelew przekracza wolne środki. Wybierz rezerwę, jeśli przenosisz odłożone pieniądze.')
        if move_money:
            if amount>source_balance or target_balance+amount>999_999_999_99:
                raise ValidationError('Przelew przekracza saldo źródłowe lub dopuszczalne saldo docelowe.')
            db.execute('UPDATE budget_accounts SET balance=? WHERE id=?',((source_balance-amount)/100,source_id))
            db.execute('UPDATE budget_accounts SET balance=? WHERE id=?',((target_balance+amount)/100,target_id))
        transfer_id = db.execute('''INSERT INTO budget_account_transfers
            (source_account_id,target_account_id,reserve_id,cycle,move_money,reserve_action,amount_cents,date,notes,request_id,request_payload,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (source_id,target_id,reserve_id,cycle,int(move_money),reserve_action,amount,day,notes,token,fingerprint,now)).lastrowid
        if reserve_action=='FUND':
            fund(db,reserve_id,target_id,amount,day,notes,token)
        elif reserve_id is not None:
            db.execute('UPDATE budget_reserves SET version=version+1,updated_at=? WHERE id=?',(now,reserve_id))
        db.commit()
        return dict(id=transfer_id)
    except Exception:
        db.rollback(); raise
    finally:
        if db.in_transaction:
            db.rollback()


def reconcile(account_id,data):
    notes = _notes(data)
    token, fingerprint, db, now = _request_id(data), _fingerprint(dict(data,account_id=account_id)), get_db(), _now()
    day = date.today().isoformat()
    try:
        db.execute('BEGIN IMMEDIATE')
        retry = _retry(db,'budget_account_reconciliations',token,fingerprint)
        if retry:
            return retry
        account = _account(db,account_id)
        observed = balance_cents(data.get('balance'), account['account_type'])
        _expected(data,'expected_balance',account['balance'])
        last = _account_day(db,account_id)
        if last and last>day:
            raise ValidationError('Na koncie są operacje z przyszłą datą. Sprawdź je przed potwierdzeniem dzisiejszego salda.')
        previous = round(float(account['balance'])*100)
        if observed!=previous and not notes:
            raise ValidationError('Podaj powód różnicy salda, np. brakujący zapis lub korekta.')
        record_id = db.execute('''INSERT INTO budget_account_reconciliations
            (account_id,previous_balance_cents,observed_balance_cents,difference_cents,date,notes,request_id,request_payload,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)''',(account_id,previous,observed,observed-previous,day,notes,token,fingerprint,now)).lastrowid
        db.execute('UPDATE budget_accounts SET balance=? WHERE id=?',(observed/100,account_id))
        db.commit()
        return dict(id=record_id)
    except Exception:
        db.rollback(); raise
    finally:
        if db.in_transaction:
            db.rollback()


def workspace():
    db, accounts, warnings = get_db(), [], []
    for row in db.execute("SELECT * FROM budget_accounts WHERE UPPER(COALESCE(currency,'PLN'))='PLN' ORDER BY id"):
        reserved = reserved_cents(db,row['id'])/100
        available = round(float(row['balance'])-reserved,2)
        verified = db.execute("SELECT date,created_at FROM budget_account_reconciliations WHERE account_id=? AND record_type='RECONCILIATION' ORDER BY id DESC LIMIT 1",(row['id'],)).fetchone()
        opening = db.execute("SELECT id,date,opening_balance_cents FROM budget_account_reconciliations WHERE account_id=? AND record_type='OPENING' ORDER BY id DESC LIMIT 1",(row['id'],)).fetchone()
        allocations = []
        for reserve in db.execute('SELECT id,name,due_date,version FROM budget_reserves WHERE is_archived=0 AND completed_at IS NULL ORDER BY due_date,id'):
            amount = location_cents(db,reserve['id'],row['id'])
            if amount>0:
                allocations.append(dict(reserve_id=reserve['id'],name=reserve['name'],amount=amount/100,due_date=reserve['due_date'],version=reserve['version']))
        accounts.append(dict(id=row['id'],name=row['name'],account_type=row['account_type'],balance=float(row['balance']),reserved=reserved,available=available,
            verified_on=verified['date'] if verified else None,allocations=allocations,
            opening_balance=opening['opening_balance_cents']/100 if opening else None,
            opening_date=opening['date'] if opening else None,opening_record_id=opening['id'] if opening else None,
            inferred_opening_balance=_effective_opening(db,row)/100))
        if available<0 and not is_credit(row):
            warnings.append(f'{row["name"]}: odłożone kwoty przekraczają saldo o {abs(available):.2f} PLN. Sprawdź saldo lub przenieś przypisanie rezerwy.')
    history = []
    for t in db.execute('''SELECT t.*,s.name source_name,a.name target_name,a.account_type target_type,r.name reserve_name FROM budget_account_transfers t
        JOIN budget_accounts s ON s.id=t.source_account_id JOIN budget_accounts a ON a.id=t.target_account_id
        LEFT JOIN budget_reserves r ON r.id=t.reserve_id ORDER BY date DESC,t.id DESC LIMIT 100'''):
        payment = t['target_type']=='CREDIT_CARD' and t['move_money']
        history.append(dict(id=f't{t["id"]}',kind='CARD_PAYMENT' if payment else 'TRANSFER' if t['move_money'] else 'LOCATION',date=t['date'],created_at=t['created_at'],
            source_account_id=t['source_account_id'],target_account_id=t['target_account_id'],account_id=None,amount=t['amount_cents']/100,
            title=f'{t["source_name"]} → {t["target_name"]}',detail=('Spłata karty — bez ponownego wydatku' if payment else t['reserve_name'] or 'Pieniądze poza rezerwami') + (' · Odłożenie obciąża budżet miesiąca' if t['reserve_action']=='FUND' else '') + (' · Historia bez zmiany salda' if not t['cash_effect'] else ''),notes=t['notes']))
    for r in db.execute('''SELECT r.*,a.name account_name FROM budget_account_reconciliations r JOIN budget_accounts a ON a.id=r.account_id
        WHERE r.record_type='RECONCILIATION' ORDER BY date DESC,r.id DESC LIMIT 100'''):
        history.append(dict(id=f'r{r["id"]}',kind='RECONCILIATION',date=r['date'],created_at=r['created_at'],account_id=r['account_id'],
            source_account_id=None,target_account_id=None,amount=r['difference_cents']/100,title=r['account_name'],
            previous_balance=r['previous_balance_cents']/100,observed_balance=r['observed_balance_cents']/100,
            detail=f'Saldo {r["previous_balance_cents"]/100:.2f} → {r["observed_balance_cents"]/100:.2f} PLN',notes=r['notes']))
    history.sort(key=lambda r:(r['date'],r['created_at'],r['id']),reverse=True)
    reserves = [dict(id=r['id'],name=r['name'],version=r['version'],locations=locations(db,r['id']))
        for r in db.execute('SELECT id,name,version FROM budget_reserves WHERE is_archived=0 AND completed_at IS NULL ORDER BY name')]
    return dict(as_of=date.today().isoformat(),accounts=accounts,reserves=reserves,history=history[:100],warnings=warnings,
        totals={**{key:round(sum(a[key] for a in accounts),2) for key in ('balance','reserved','available')}, **account_totals(db)})
