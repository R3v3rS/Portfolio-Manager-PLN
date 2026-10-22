"""Expected income is a plan; only explicitly recording receipt books cash."""
import calendar
from datetime import date
from api.exceptions import ApiError, NotFoundError, ValidationError
from database import get_db
from routes_budget_workspace import cents, insert_entry, positive_id, text_field
from budget_reserves_service import _account, _date, _fingerprint, _now, _request_id


def months(first,last):
    year,month=map(int,first[:7].split('-'))
    while f'{year:04d}-{month:02d}'<=last[:7]:
        yield year,month
        year,month=(year+1,1) if month==12 else (year,month+1)


def occurrences(row,first,last):
    start=row['start_date']
    end=min(row['end_date'] or last,last)
    if row['frequency']=='ONCE':
        if first<=start<=end:yield start
        return
    anchor=date.fromisoformat(start).day
    for year,month in months(max(first,start),end):
        day=date(year,month,min(anchor,calendar.monthrange(year,month)[1])).isoformat()
        if max(first,start)<=day<=end:yield day


def row_for(db,income_id,version=None):
    row=db.execute('SELECT * FROM budget_expected_incomes WHERE id=?',(income_id,)).fetchone()
    if not row:raise NotFoundError('Planowany dochód nie istnieje.')
    if type(version) is not int or row['version']!=version:
        raise ApiError('income_version_conflict','Plan dochodu zmienił się. Odśwież dane przed zapisem.',status=409)
    return row


def is_received(row,day,received):
    # Editing a payday must not recreate an already settled monthly salary.
    return any(income_id==row['id'] and (row['frequency']=='ONCE' or occurrence[:7]==day[:7])
               for income_id,occurrence in received)


def pending_amount_cents(db, first, last):
    """Unsettled income in the selected period; never books account cash."""
    received = {(r['income_id'], r['occurrence_date']) for r in db.execute(
        'SELECT income_id,occurrence_date FROM budget_expected_income_receipts')}
    return sum(row['amount_cents'] for row in db.execute('''
        SELECT i.* FROM budget_expected_incomes i
        JOIN budget_accounts a ON a.id=i.account_id
        WHERE i.active=1 AND UPPER(COALESCE(a.currency,'PLN'))='PLN'
    ''') for day in occurrences(row, first, last) if not is_received(row, day, received))


def save(data,income_id=None):
    name=text_field(data.get('name'),'Nazwa dochodu',150)
    account_id=positive_id(data.get('account_id'),'konto')
    amount=cents(data.get('amount'))
    start=_date(data.get('start_date'),'Pierwszy termin')
    end=_date(data['end_date'],'Koniec planu') if data.get('end_date') else None
    if end and end<start:raise ValidationError('Koniec planu nie może poprzedzać pierwszego terminu.')
    frequency=data.get('frequency')
    if frequency not in ('ONCE','MONTHLY'):raise ValidationError('Wybierz dochód jednorazowy albo miesięczny.')
    db,now=get_db(),_now()
    try:
        db.execute('BEGIN IMMEDIATE')
        from budget_account_types import require_cash
        require_cash(_account(db,account_id))
        if income_id is None:
            token,fingerprint=_request_id(data),_fingerprint(data)
            previous=db.execute('SELECT * FROM budget_expected_incomes WHERE request_id=?',(token,)).fetchone()
            if previous:
                if previous['request_payload']!=fingerprint:raise ApiError('income_request_conflict','Ten zapis przyjęto z innymi danymi.',status=409)
                return dict(id=previous['id'])
            if start<date.today().isoformat():raise ValidationError('Nowy plan musi zaczynać się dzisiaj lub w przyszłości.')
            income_id=db.execute('''INSERT INTO budget_expected_incomes
                (name,account_id,amount_cents,start_date,end_date,frequency,request_id,request_payload,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',(name,account_id,amount,start,end,frequency,token,fingerprint,now,now)).lastrowid
        else:
            row=row_for(db,income_id,data.get('version'))
            if row['frequency']!=frequency and db.execute('SELECT 1 FROM budget_expected_income_receipts WHERE income_id=?',(income_id,)).fetchone():
                raise ValidationError('Plan ma rozliczone wpływy. Aby zmienić powtarzalność, dodaj nowy plan i wstrzymaj obecny.')
            db.execute('''UPDATE budget_expected_incomes SET name=?,account_id=?,amount_cents=?,start_date=?,end_date=?,frequency=?,
                version=version+1,updated_at=? WHERE id=?''',(name,account_id,amount,start,end,frequency,now,income_id))
        db.commit();return dict(id=income_id)
    except Exception:
        db.rollback();raise
    finally:
        if db.in_transaction:db.rollback()


def set_active(income_id,data):
    if type(data.get('active')) is not bool:raise ValidationError('Nieprawidłowy stan planu.')
    db=get_db()
    try:
        db.execute('BEGIN IMMEDIATE');row_for(db,income_id,data.get('version'))
        db.execute('UPDATE budget_expected_incomes SET active=?,version=version+1,updated_at=? WHERE id=?',(int(data['active']),_now(),income_id))
        db.commit();return dict(id=income_id)
    except Exception:db.rollback();raise


def receive(income_id,data):
    token,fingerprint=_request_id(data),_fingerprint(dict(data,income_id=income_id))
    occurrence=_date(data.get('occurrence_date'),'Termin planowanego wpływu')
    db=get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT * FROM budget_expected_income_receipts WHERE request_id=?',(token,)).fetchone()
        if previous:
            if previous['request_payload']!=fingerprint:raise ApiError('income_request_conflict','Ten wpływ przyjęto z innymi danymi.',status=409)
            return dict(id=previous['id'],budget_entry_id=previous['budget_entry_id'])
        row=row_for(db,income_id,data.get('version'))
        if not row['active']:raise ValidationError('Plan dochodu jest wstrzymany.')
        if occurrence not in occurrences(row,occurrence,occurrence):raise ValidationError('Ten termin nie należy do planu dochodu.')
        received={(r['income_id'],r['occurrence_date']) for r in db.execute('SELECT income_id,occurrence_date FROM budget_expected_income_receipts WHERE income_id=?',(income_id,))}
        if is_received(row,occurrence,received):
            raise ApiError('income_already_received','Ten termin jest już rozliczony.',status=409)
        from budget_account_types import require_cash
        require_cash(_account(db,row['account_id']))
        if data.get('existing_entry_id') is not None:
            entry_id=positive_id(data['existing_entry_id'],'istniejący wpływ')
            entry=db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry_id,)).fetchone()
            if not entry or entry['kind']!='INCOME' or entry['account_id']!=row['account_id'] or entry['date']>date.today().isoformat():
                raise ValidationError('Wybierz otrzymany wpływ z konta tego dochodu.')
            if db.execute('SELECT 1 FROM budget_expected_income_receipts WHERE budget_entry_id=?',(entry_id,)).fetchone():
                raise ValidationError('Ten wpływ jest już przypisany do innego terminu.')
            if db.execute('SELECT 1 FROM budget_purchase_refunds WHERE entry_id=?',(entry_id,)).fetchone(): raise ValidationError('Zwrot zakupu nie jest otrzymaniem planowanego dochodu.')
        else:
            amount=cents(data.get('amount'))
            paid_on=_date(data.get('date'),'Data otrzymania')
            if paid_on>date.today().isoformat():raise ValidationError('Zapisz wpływ dopiero po otrzymaniu pieniędzy.')
            entry_id=insert_entry(db,dict(account_id=row['account_id'],kind='INCOME',amount_cents=amount,date=paid_on,
                description=f'{row["name"]} — otrzymany wpływ',merchant=None,lines=[]))
        receipt_id=db.execute('''INSERT INTO budget_expected_income_receipts
            (income_id,occurrence_date,budget_entry_id,request_id,request_payload,created_at) VALUES (?,?,?,?,?,?)''',
            (income_id,occurrence,entry_id,token,fingerprint,_now())).lastrowid
        db.execute('UPDATE budget_expected_incomes SET version=version+1,updated_at=? WHERE id=?',(_now(),income_id))
        db.commit();return dict(id=receipt_id,budget_entry_id=entry_id)
    except Exception:db.rollback();raise
    finally:
        if db.in_transaction:db.rollback()


def items(db,today,end):
    result=[]
    received={(r['income_id'],r['occurrence_date']) for r in db.execute('SELECT income_id,occurrence_date FROM budget_expected_income_receipts')}
    for row in db.execute('''SELECT i.*,a.name account_name FROM budget_expected_incomes i JOIN budget_accounts a ON a.id=i.account_id ORDER BY active DESC,i.id'''):
        first=row['start_date'] if row['frequency']=='ONCE' else max(row['start_date'],today.strftime('%Y-%m')+'-01')
        next_day=next((d for d in occurrences(row,first,max(end,today.isoformat())) if not is_received(row,d,received)),None)
        result.append(dict(id=row['id'],name=row['name'],account_id=row['account_id'],account_name=row['account_name'],amount=row['amount_cents']/100,
            start_date=row['start_date'],end_date=row['end_date'],frequency=row['frequency'],active=bool(row['active']),version=row['version'],
            next_occurrence=next_day,overdue=bool(next_day and next_day<today.isoformat()),
            received_count=db.execute('SELECT COUNT(*) FROM budget_expected_income_receipts WHERE income_id=?',(row['id'],)).fetchone()[0]))
    return result
