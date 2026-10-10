"""Recurring obligations and explicit, atomic payments with optional reserves."""
from datetime import date
from uuid import uuid4

from api.exceptions import ApiError, NotFoundError, ValidationError
from database import get_db
from budget_bill_schedule import amount_cents, due_date, due_in_month


def save(data, bill_id=None):
    from routes_budget_workspace import cents, positive_id, text_field, month_value
    from budget_reserves_service import _account, _date, _fingerprint, _request_id
    db = get_db()
    title = text_field(data.get('title'),'Nazwa zobowiązania',150)
    account_id = positive_id(data.get('account_id'),'konto')
    category_id = positive_id(data.get('category_id'),'kategorię')
    amount = cents(data.get('amount'))
    day = data.get('due_day')
    if isinstance(day,bool) or not isinstance(day,int) or not 1<=day<=31:
        raise ValidationError('Dzień płatności musi być liczbą od 1 do 31.')
    frequency = data.get('frequency','MONTHLY')
    if frequency not in ('MONTHLY','QUARTERLY','YEARLY','ONCE'):
        raise ValidationError('Nieprawidłowa częstotliwość rachunku.')
    interval = {'MONTHLY':1,'QUARTERLY':3,'YEARLY':12,'ONCE':1}[frequency]
    stored_frequency = 'ONCE' if frequency=='ONCE' else 'MONTHLY'
    first = month_value(data.get('due_month')) if frequency=='ONCE' else month_value(data.get('start_month') or date.today().strftime('%Y-%m'))
    end = month_value(data['end_month']) if data.get('end_month') else None
    if end and end<first: raise ValidationError('Koniec zobowiązania nie może poprzedzać początku.')
    promotion = _date(data['promotion_end'],'Koniec promocji') if data.get('promotion_end') else None
    notice = _date(data['notice_date'],'Termin wypowiedzenia') if data.get('notice_date') else None
    regular = cents(data['regular_amount']) if data.get('regular_amount') not in (None,'') else None
    if bool(promotion) != (regular is not None):
        raise ValidationError('Podaj razem koniec promocji i kwotę po promocji.')
    variable = data.get('variable_amount',False)
    if type(variable) is not bool: raise ValidationError('Nieprawidłowy rodzaj kwoty.')
    notes = data.get('notes','')
    if not isinstance(notes,str) or len(notes)>2000: raise ValidationError('Opis może mieć najwyżej 2000 znaków.')
    reserve_id = positive_id(data['reserve_id'],'rezerwę') if data.get('reserve_id') is not None else None
    token = _request_id(data) if data.get('request_id') else str(uuid4())
    fingerprint = _fingerprint(data)
    try:
        db.execute('BEGIN IMMEDIATE')
        _account(db,account_id)
        if not db.execute('SELECT 1 FROM budget_categories_v2 WHERE id=?',(category_id,)).fetchone():
            raise NotFoundError('Kategoria nie istnieje.')
        if bill_id is None:
            previous=db.execute('SELECT id,request_payload FROM budget_bills_v2 WHERE request_id=?',(token,)).fetchone()
            if previous:
                if previous['request_payload']!=fingerprint: raise ApiError('bill_request_conflict','Zapis przyjęto z innymi danymi.',status=409)
                return dict(id=previous['id'])
        else:
            current=db.execute('SELECT * FROM budget_bills_v2 WHERE id=?',(bill_id,)).fetchone()
            if not current: raise NotFoundError('Zobowiązanie nie istnieje.')
            if type(data.get('version')) is not int or data['version']!=current['version']:
                raise ApiError('bill_version_conflict','Zobowiązanie zmieniło się. Odśwież dane.',status=409)
            if any(current[key]!=value for key,value in (('category_id',category_id),('account_id',account_id),('reserve_id',reserve_id))) \
                    and db.execute('SELECT 1 FROM budget_bill_payments_v2 WHERE bill_id=?',(bill_id,)).fetchone():
                raise ValidationError('Rachunek ma historię płatności. Cofnij błędne rozliczenie przed zmianą konta, kategorii lub rezerwy; dla przyszłych płatności dodaj osobny rachunek.')
        if reserve_id and data.get('active',True):
            reserve=db.execute('SELECT * FROM budget_reserves WHERE id=?',(reserve_id,)).fetchone()
            if not reserve or reserve['is_archived'] or reserve['completed_at']: raise ValidationError('Wybierz aktywną rezerwę.')
            if db.execute('SELECT 1 FROM budget_bills_v2 WHERE reserve_id=? AND active=1 AND id!=?',(reserve_id,bill_id or 0)).fetchone():
                raise ValidationError('Ta rezerwa już finansuje inne zobowiązanie.')
            expected = 'ONCE' if reserve['frequency']=='ONCE' else 'YEARLY'
            candidate=dict(due_day=day)
            candidate.update(frequency=stored_frequency,due_month=first,start_month=first,interval_months=interval,end_month=end)
            monthly=reserve['monthly_amount_cents'] is not None
            if monthly and not reserve['open_ended'] and category_id!=reserve['category_id']:
                raise ValidationError('Rachunek musi korzystać z kategorii miesięcznej puli.')
            if not monthly and (frequency!=expected or not due_in_month(candidate,reserve['due_date'][:7]) or due_date(candidate,reserve['due_date'][:7])!=reserve['due_date'] or amount!=reserve['target_cents']):
                raise ValidationError('Kwota, pierwszy termin i powtarzalność muszą odpowiadać rezerwie. Dla rezerwy corocznej wybierz płatność coroczną.')
            if end and not monthly:raise ValidationError('Przed zakończeniem zobowiązania odłącz rezerwę, aby osobno zdecydować o dalszym odkładaniu.')
            if promotion and not monthly: raise ValidationError('Kwotę kosztu finansowanego z rezerwy zmieniaj wspólnie z rezerwą; promocja nie jest dostępna dla tego powiązania.')
        fields=dict(title=title,account_id=account_id,category_id=category_id,amount_cents=amount,due_day=day,
            frequency=stored_frequency,due_month=first if frequency=='ONCE' else None,start_month=first,
            interval_months=interval,end_month=end,promotion_end=promotion,notice_date=notice,
            regular_amount_cents=regular,variable_amount=int(variable),reserve_id=reserve_id,notes=notes.strip())
        if bill_id is not None and any(not due_in_month(fields,p['month']) for p in db.execute('SELECT month FROM budget_bill_payments_v2 WHERE bill_id=?',(bill_id,))):
            raise ValidationError('Rachunek ma zapisane płatności poza wybranym okresem. Zachowaj jego historię i dodaj osobny rachunek z nowym rodzajem lub terminem.')
        if 'active' in data:
            if type(data['active']) is not bool:raise ValidationError('Nieprawidłowy stan zobowiązania.')
            fields['active']=int(data['active'])
        if bill_id is None:
            fields.update(request_id=token,request_payload=fingerprint)
            keys=','.join(fields); marks=','.join('?' for _ in fields)
            bill_id=db.execute(f'INSERT INTO budget_bills_v2({keys}) VALUES({marks})',tuple(fields.values())).lastrowid
        else:
            db.execute('UPDATE budget_bills_v2 SET '+','.join(k+'=?' for k in fields)+',version=version+1 WHERE id=?',(*fields.values(),bill_id))
        db.commit(); return dict(id=bill_id)
    except Exception:
        db.rollback(); raise
    finally:
        if db.in_transaction: db.rollback()


def candidates(db,bill,month):
    from budget_import_parser import normalized
    words={w for w in normalized(bill['title']).split() if len(w)>2}
    found=[]
    for entry in db.execute('''SELECT e.* FROM budget_entries_v2 e WHERE e.account_id=? AND e.kind='EXPENSE'
        AND substr(e.date,1,7)=? AND NOT EXISTS(SELECT 1 FROM budget_bill_payments_v2 p WHERE p.entry_id=e.id)
        AND NOT EXISTS(SELECT 1 FROM loan_installment_payments p WHERE p.budget_entry_id=e.id)
        AND NOT EXISTS(SELECT 1 FROM loan_overpayments p WHERE p.budget_entry_id=e.id)
        AND NOT EXISTS(SELECT 1 FROM budget_reserve_movements p WHERE p.budget_entry_id=e.id)
        ORDER BY e.date DESC,e.id DESC''',(bill['account_id'],month)):
        if not bill['variable_amount'] and entry['amount_cents']!=amount_cents(bill,month): continue
        same_category=db.execute('SELECT 1 FROM budget_entry_lines_v2 WHERE entry_id=? AND category_id=?',(entry['id'],bill['category_id'])).fetchone()
        same_name=words.intersection(normalized((entry['merchant'] or '')+' '+entry['description']).split())
        if same_category or same_name:
            found.append(dict(id=entry['id'],date=entry['date'],description=entry['description'],amount=entry['amount_cents']/100,version=entry['version']))
    return found[:20]


def pay(bill_id, data):
    from routes_budget_workspace import cents, day_value, insert_entry, month_value
    from budget_reserves_service import move, _request_id, _fingerprint
    month = month_value(data.get('month'))
    paid_on = day_value(data.get('date') or date.today().isoformat())
    if paid_on[:7]!=month: raise ValidationError('Data opłacenia musi należeć do wybranego miesiąca.')
    if paid_on>date.today().isoformat(): raise ValidationError('Zapisz opłacenie dopiero po wykonaniu płatności. Przyszły rachunek pozostaje w planie.')
    db=get_db();token=_request_id(data) if data.get('request_id') else str(uuid4())
    fingerprint=_fingerprint(dict(data,bill_id=bill_id))
    try:
        db.execute('BEGIN IMMEDIATE')
        retry=db.execute('SELECT entry_id,request_payload FROM budget_bill_payments_v2 WHERE request_id=?',(token,)).fetchone()
        if db.execute('SELECT 1 FROM budget_cancelled_requests WHERE request_id=?',(token,)).fetchone():
            raise ApiError('bill_request_cancelled','Ta płatność została cofnięta. Otwórz nowy formularz.',status=409)
        if retry:
            if retry['request_payload']!=fingerprint: raise ApiError('bill_payment_request_conflict','Płatność zapisano z innymi danymi.',status=409)
            return dict(entry_id=retry['entry_id'])
        bill=db.execute('SELECT * FROM budget_bills_v2 WHERE id=? AND active=1',(bill_id,)).fetchone()
        if not bill: raise NotFoundError('Rachunek nie istnieje.')
        if not due_in_month(bill,month): raise ValidationError('Ten rachunek nie należy do wybranego miesiąca.')
        if data.get('version') is not None and (type(data['version']) is not int or data['version']!=bill['version']):
            raise ApiError('bill_version_conflict','Zobowiązanie zmieniło się. Odśwież dane.',status=409)
        previous=db.execute('SELECT entry_id FROM budget_bill_payments_v2 WHERE bill_id=? AND month=?',(bill_id,month)).fetchone()
        if previous: raise ValidationError('Ten rachunek jest już opłacony.')
        amount=cents(data['amount']) if data.get('amount') is not None else amount_cents(bill,month)
        existing=None
        entry_before=None
        if data.get('existing_entry_id') is not None:
            from budget_category_service import require_version
            existing=db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(data['existing_entry_id'],)).fetchone()
            if not existing or (existing['kind'],existing['account_id'],existing['amount_cents'],existing['date'])!=('EXPENSE',bill['account_id'],amount,paid_on):
                raise ValidationError('Wybierz wydatek z tego konta o wskazanej kwocie i dacie.')
            require_version(existing,data.get('entry_version'),'Wydatek')
            if any(db.execute(f'SELECT 1 FROM {table} WHERE {column}=?',(existing['id'],)).fetchone() for table,column in
                (('budget_bill_payments_v2','entry_id'),('loan_installment_payments','budget_entry_id'),('loan_overpayments','budget_entry_id'),('budget_reserve_movements','budget_entry_id'))):
                raise ValidationError('Ten wydatek już rozlicza zobowiązanie.')
            lines=[dict(line) for line in db.execute('SELECT category_id,label,amount_cents FROM budget_entry_lines_v2 WHERE entry_id=?',(existing['id'],))]
            if existing['classification_status']=='UNASSIGNED':
                import json
                entry_before=dict(classification_status=existing['classification_status'],lines=lines)
                db.execute('UPDATE budget_entry_lines_v2 SET category_id=? WHERE entry_id=?',(bill['category_id'],existing['id']))
                db.execute("UPDATE budget_entries_v2 SET classification_status='GENERAL' WHERE id=?",(existing['id'],))
                lines=[dict(line,category_id=bill['category_id']) for line in lines]
            if not lines or any(line['category_id']!=bill['category_id'] for line in lines):
                raise ValidationError('Przed powiązaniem przypisz cały wydatek do kategorii tego rachunku. Inna kategoria mogłaby pozostawić kwotę rachunku w planie drugi raz.')
        elif candidates(db,bill,month) and data.get('confirm_separate') is not True:
            raise ApiError('bill_existing_payment','Znaleziono podobną płatność. Powiąż istniejący wydatek albo potwierdź, że jest to odrębna płatność.',status=409)
        if not existing and 'expected_balance' in data:
            balance=db.execute('SELECT balance FROM budget_accounts WHERE id=?',(bill['account_id'],)).fetchone()[0]
            if data['expected_balance']!=round(balance,2):
                raise ApiError('bill_balance_conflict','Saldo konta zmieniło się. Odśwież podgląd płatności.',status=409)
        if bill['reserve_id']:
            reserve=db.execute('SELECT * FROM budget_reserves WHERE id=?',(bill['reserve_id'],)).fetchone()
            if not reserve: raise ValidationError('Rezerwa nie istnieje.')
            if reserve['monthly_amount_cents'] is None and reserve['due_date'][:7]!=month:raise ValidationError('Wybrany miesiąc nie odpowiada bieżącemu kosztowi rezerwy.')
            result=move(bill['reserve_id'],dict(kind='SPEND',amount=amount/100,date=paid_on,account_id=bill['account_id'],
                category_id=bill['category_id'],version=data.get('reserve_version',reserve['version']),
                request_id=token,notes=bill['title'],**(dict(existing_entry_id=existing['id'],entry_version=existing['version']) if existing else {})),within_transaction=True)
            entry_id=result['budget_entry_id']
        elif existing:
            entry_id=existing['id']
        else:
            entry_id=insert_entry(db,dict(account_id=bill['account_id'],kind='EXPENSE',amount_cents=amount,date=paid_on,
                description=bill['title'],merchant=None,lines=[dict(category_id=bill['category_id'],label='',amount_cents=amount)]))
        db.execute('INSERT INTO budget_bill_payments_v2(bill_id,month,entry_id,request_id,request_payload,planned_amount_cents) VALUES(?,?,?,?,?,?)',(bill_id,month,entry_id,token,fingerprint,amount_cents(bill,month)))
        if not bill['reserve_id']:
            from budget_reserves_service import _now
            import json
            db.execute('INSERT INTO budget_settlements(entry_id,created_entry,before_json,recorded_at) VALUES(?,?,?,?)',
                (entry_id,int(existing is None),json.dumps(dict(entry_before=entry_before)) if entry_before else None,_now()))
        elif entry_before:
            import json
            before=json.loads(db.execute('SELECT before_json FROM budget_settlements WHERE entry_id=?',(entry_id,)).fetchone()[0])
            before['entry_before']=entry_before
            db.execute('UPDATE budget_settlements SET before_json=? WHERE entry_id=?',(json.dumps(before),entry_id))
        if existing: db.execute('UPDATE budget_entries_v2 SET version=version+1 WHERE id=?',(entry_id,))
        db.execute('UPDATE budget_bills_v2 SET version=version+1 WHERE id=?',(bill_id,))
        db.commit(); return dict(entry_id=entry_id)
    except Exception:
        db.rollback(); raise
    finally:
        if db.in_transaction: db.rollback()


def serialize(db,row,month):
    from budget_planning_service import shift_month
    payment=db.execute('SELECT p.entry_id,p.planned_amount_cents,e.amount_cents,e.date FROM budget_bill_payments_v2 p LEFT JOIN budget_entries_v2 e ON e.id=p.entry_id WHERE bill_id=? AND month=?',(row['id'],month)).fetchone()
    due=due_date(row,month)
    frequency='ONCE' if row['frequency']=='ONCE' else {1:'MONTHLY',3:'QUARTERLY',12:'YEARLY'}[row['interval_months']]
    reserve=db.execute('SELECT name,version FROM budget_reserves WHERE id=?',(row['reserve_id'],)).fetchone() if row['reserve_id'] else None
    from budget_bill_funding import occurrence
    funding=occurrence(db,row,month)
    return dict(id=row['id'],title=row['title'],amount=(payment['amount_cents'] if payment and payment['amount_cents'] is not None else amount_cents(row,month))/100,
        planned_amount=(payment['planned_amount_cents'] if payment and payment['planned_amount_cents'] is not None else amount_cents(row,month))/100,
        paid_on=payment['date'] if payment else None,
        base_amount=row['amount_cents']/100,reserve_covered=funding['covered_cents']/100,unfunded=funding['unfunded_cents']/100,
        funding_source='Miesięczna pula mediów' if funding['media'] else reserve['name'] if reserve else 'Wolne środki konta',
        due_date=due,frequency=frequency,start_month=row['start_month'],end_month=row['end_month'],
        due_month=row['due_month'],due_day=row['due_day'],account_id=row['account_id'],category_id=row['category_id'],
        active=bool(row['active']),version=row['version'],variable_amount=bool(row['variable_amount']),notes=row['notes'],
        promotion_end=row['promotion_end'],notice_date=row['notice_date'],regular_amount=row['regular_amount_cents']/100 if row['regular_amount_cents'] is not None else None,
        reserve_id=row['reserve_id'],reserve_name=reserve['name'] if reserve else None,reserve_version=reserve['version'] if reserve else None,
        status='PAID' if payment else 'OVERDUE' if due<date.today().isoformat() else 'UPCOMING',entry_id=payment['entry_id'] if payment else None,
        annual_cost=sum(amount_cents(row,key) for key in (shift_month(month,i) for i in range(12)) if due_in_month(row,key))/100,
        next_due_date=next((due_date(row,key) for key in (shift_month(month,i) for i in range(13)) if due_in_month(row,key)),None),
        payment_candidates=candidates(db,row,month) if not payment and due_in_month(row,month) else [])
