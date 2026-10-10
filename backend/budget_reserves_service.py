"""Earmarked cash with monthly budget allocations and separate actual payments."""
import calendar
import json
from datetime import date, datetime, timezone
from uuid import UUID, uuid5

from api.exceptions import ApiError, NotFoundError, ValidationError
from budget_category_hierarchy_service import category_options
from database import get_db
from routes_budget_workspace import cents, day_value, insert_entry, positive_id, text_field


def reserved_cents(db, account_id=None, through=None):
    params, filters = [], []
    if account_id is not None:
        filters.append('m.account_id=?')
        params.append(account_id)
    if through is not None:
        filters.append('m.date<=?')
        params.append(through)
    where = ' WHERE ' + ' AND '.join(filters) if filters else ''
    total = db.execute('''SELECT COALESCE(SUM(CASE WHEN m.kind='ADD' THEN m.amount_cents
        ELSE -m.amount_cents END),0) FROM budget_reserve_movements m
        JOIN budget_reserves r ON r.id=m.reserve_id''' + where, params).fetchone()[0]
    return total + _transferred_cents(db, account_id=account_id, through=through)


def _transferred_cents(db, account_id=None, reserve_id=None, through=None):
    if account_id is None:
        return 0  # Moving locations never changes the total saved on a goal.
    filters, params = ["reserve_id IS NOT NULL", "reserve_action='MOVE'"], [account_id, account_id]
    if reserve_id is not None:
        filters.append('reserve_id=?'); params.append(reserve_id)
    if through is not None:
        filters.append('date<=?'); params.append(through)
    return db.execute('''SELECT COALESCE(SUM(CASE WHEN target_account_id=? THEN amount_cents ELSE 0 END
        - CASE WHEN source_account_id=? THEN amount_cents ELSE 0 END),0)
        FROM budget_account_transfers WHERE ''' + ' AND '.join(filters), params).fetchone()[0]


def location_cents(db, reserve_id, account_id):
    total = db.execute('''SELECT COALESCE(SUM(CASE WHEN kind='ADD' THEN amount_cents ELSE -amount_cents END),0)
        FROM budget_reserve_movements WHERE reserve_id=? AND account_id=?''', (reserve_id,account_id)).fetchone()[0]
    return total + _transferred_cents(db, account_id, reserve_id)


def locations(db, reserve_id):
    return [dict(account_id=a['id'],account_name=a['name'],amount=amount/100)
        for a in db.execute('SELECT id,name FROM budget_accounts ORDER BY id')
        if (amount := location_cents(db,reserve_id,a['id'])) > 0]


def last_reserve_day(db, reserve_id):
    return db.execute('''SELECT MAX(date) FROM (
        SELECT date FROM budget_reserve_movements WHERE reserve_id=?
        UNION ALL SELECT date FROM budget_account_transfers WHERE reserve_id=?)''', (reserve_id,reserve_id)).fetchone()[0]


def _balance(db, reserve_id):
    return db.execute('''SELECT COALESCE(SUM(CASE WHEN kind='ADD' THEN amount_cents ELSE -amount_cents END),0)
        FROM budget_reserve_movements WHERE reserve_id=?''', (reserve_id,)).fetchone()[0]


def _row(db, reserve_id, version=None):
    row = db.execute('SELECT * FROM budget_reserves WHERE id=?', (reserve_id,)).fetchone()
    if not row:
        raise NotFoundError('Rezerwa nie istnieje.')
    if version is not None and (type(version) is not int or version != row['version']):
        raise ApiError('reserve_version_conflict', 'Rezerwa została zmieniona. Odśwież dane przed kolejnym zapisem.', status=409)
    return row


def _version(data):
    if type(data.get('version')) is not int:
        raise ValidationError('Brak wersji rezerwy. Odśwież dane.')
    return data['version']


def _request_id(data):
    value = data.get('request_id')
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError('Nieprawidłowy identyfikator zapisu.') from None
    return value


def _fingerprint(data):
    # Optimistic versions change after a successful write; retries keep their identity.
    return json.dumps({k:v for k,v in data.items() if k not in ('version','request_id')}, sort_keys=True, ensure_ascii=False)


def _date(value, label):
    value = day_value(value)
    if not '2000-01-01' <= value <= '2100-12-31':
        raise ValidationError(f'{label}: dopuszczalny zakres lat to 2000–2100.')
    return value


def _account(db, account_id):
    row = db.execute('SELECT * FROM budget_accounts WHERE id=?', (account_id,)).fetchone()
    if not row:
        raise NotFoundError('Konto budżetowe nie istnieje.')
    if (row['currency'] or 'PLN').upper() != 'PLN':
        raise ValidationError('Rezerwa wymaga konta w PLN.')
    return row


def _fields(data):
    name = text_field(data.get('name'), 'Nazwa rezerwy', 120)
    notes = data.get('notes', '')
    if not isinstance(notes, str) or len(notes) > 2000:
        raise ValidationError('Opis może mieć najwyżej 2000 znaków.')
    open_ended=data.get('open_ended',False)
    if type(open_ended) is not bool: raise ValidationError('Nieprawidłowy tryb rezerwy.')
    if open_ended:
        monthly=cents(data.get('monthly_amount') if data.get('monthly_amount') is not None else 0,'Stały plan miesięczny',allow_zero=True)
    else:
        monthly=cents(data['monthly_amount'],'Miesięczna pula',allow_zero=True) if data.get('monthly_amount') is not None else None
    # Continuous envelopes have no expense deadline. The legacy target fields
    # remain inert; migrations do not rewrite existing financial records.
    amount = max(1,monthly) if monthly is not None else cents(data.get('target_amount'))
    due = date.today().isoformat() if monthly is not None else _date(data.get('due_date'), 'Termin')
    frequency = data.get('frequency','YEARLY')
    if frequency not in ('ONCE','YEARLY'):
        raise ValidationError('Wybierz koszt jednorazowy albo coroczny.')
    return name, notes.strip(), positive_id(data.get('account_id'), 'konto'), amount, due, frequency, monthly, open_ended


def _now():
    return datetime.now(timezone.utc).isoformat()


def save(data, reserve_id=None):
    fields = _fields(data)
    name, notes, account_id, amount, due, frequency, monthly, open_ended = fields
    db, now, old = get_db(), _now(), None
    try:
        db.execute('BEGIN IMMEDIATE')
        if reserve_id is None:
            token, fingerprint = _request_id(data), _fingerprint(data)
            previous = db.execute('SELECT * FROM budget_reserves WHERE request_id=?', (token,)).fetchone()
            if previous:
                if previous['request_payload'] != fingerprint:
                    raise ApiError('reserve_request_conflict', 'Ten zapis został już przyjęty z innymi danymi.', status=409)
                return dict(id=previous['id'])
        _account(db, account_id)
        category_id=positive_id(data['category_id'],'kategorię') if data.get('category_id') else None
        if category_id and not db.execute('SELECT 1 FROM budget_categories_v2 WHERE id=? AND is_unassigned=0',(category_id,)).fetchone(): raise ValidationError('Wybierz kategorię przyszłego wydatku.')
        if monthly is not None and not open_ended and not category_id: raise ValidationError('Wybierz kategorię miesięcznej puli, np. Prąd lub Woda.')
        if monthly is not None and not open_ended:
            if db.execute('SELECT 1 FROM budget_categories_v2 WHERE parent_id=?',(category_id,)).fetchone():
                raise ValidationError('Wybierz osobną podkategorię bez dalszych podkategorii, np. Media › Prąd.')
            if db.execute('SELECT 1 FROM budget_reserves WHERE category_id=? AND monthly_amount_cents IS NOT NULL AND open_ended=0 AND is_archived=0 AND id!=?',(category_id,reserve_id or 0)).fetchone():
                raise ValidationError('Ta kategoria ma już miesięczną pulę. Edytuj ją albo wybierz osobną kategorię.')
        if reserve_id is None:
            token, fingerprint = _request_id(data), _fingerprint(data)
            previous = db.execute('SELECT * FROM budget_reserves WHERE request_id=?', (token,)).fetchone()
            if previous:
                if previous['request_payload'] != fingerprint:
                    raise ApiError('reserve_request_conflict', 'Ten zapis został już przyjęty z innymi danymi.', status=409)
                return dict(id=previous['id'])
            if due < date.today().isoformat():
                raise ValidationError('Termin nowej rezerwy nie może być wcześniejszy niż dzisiaj.')
            reserve_id = db.execute('''INSERT INTO budget_reserves
                (name,notes,account_id,target_cents,start_date,due_date,anniversary,frequency,request_id,request_payload,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (name,notes,account_id,amount,date.today().isoformat(),due,due,frequency,token,fingerprint,now,now)).lastrowid
        else:
            old = _row(db,reserve_id,_version(data))
            from budget_plan_history import freeze
            freeze(db,reserve_id)
            if old['open_ended'] and open_ended and monthly!=old['monthly_amount_cents']:
                # Freeze completed months before changing the fixed plan.
                # This is plan metadata; no cash or reserve movements are added.
                from budget_planning_service import shift_month
                cursor=old['monthly_start_month'] or old['start_date'][:7]
                while cursor<date.today().strftime('%Y-%m'):
                    db.execute('INSERT OR IGNORE INTO budget_reserve_month_plans(reserve_id,month,amount_cents) VALUES(?,?,?)',
                        (reserve_id,cursor,old['monthly_amount_cents']))
                    cursor=shift_month(cursor,1)
            if old['monthly_amount_cents'] is not None and bool(old['open_ended'])!=open_ended and db.execute('SELECT 1 FROM budget_reserve_movements WHERE reserve_id=?',(reserve_id,)).fetchone():
                raise ValidationError('Rezerwa ma historię miesięcznego trybu. Zachowaj jej rodzaj; kwotę stałą możesz edytować.')
            if monthly is None and old['monthly_amount_cents'] is not None and db.execute('SELECT 1 FROM budget_reserve_movements WHERE reserve_id=?',(reserve_id,)).fetchone():
                raise ValidationError('Pula ma zapisaną historię. Zachowaj miesięczny tryb; możesz zmieniać kwotę domyślną.')
            if monthly is not None:
                # Keep legacy target metadata to explain periods before conversion.
                amount,due,frequency=old['target_cents'],old['due_date'],old['frequency']
                linked=db.execute('SELECT category_id FROM budget_bills_v2 WHERE reserve_id=? AND active=1',(reserve_id,)).fetchone()
                if linked and not open_ended and linked['category_id']!=category_id:
                    raise ValidationError('Wybierz tę samą kategorię co rachunek finansowany z tej rezerwy.')
            if old['monthly_amount_cents'] is not None:
                due=old['due_date']
                if not open_ended and category_id!=old['category_id'] and db.execute('SELECT 1 FROM budget_reserve_movements WHERE reserve_id=?',(reserve_id,)).fetchone():
                    raise ValidationError('Pula ma zapisaną historię. Zachowaj jej kategorię, aby nie zmieniać wcześniejszych rozliczeń.')
            if old['is_archived'] or old['completed_at']:
                raise ValidationError('Przywróć rezerwę lub utwórz nową dla kolejnego wydatku.')
            if due < old['start_date']:
                raise ValidationError('Termin nie może poprzedzać początku bieżącego cyklu.')
            if monthly is None and (amount!=old['target_cents'] or due!=old['due_date'] or frequency!=old['frequency']) and db.execute(
                    'SELECT 1 FROM budget_bills_v2 WHERE reserve_id=? AND active=1',(reserve_id,)).fetchone():
                raise ValidationError('Rezerwa finansuje zobowiązanie. Najpierw odłącz ją w rachunkach, następnie zmień kwotę lub termin i połącz ponownie.')
            anniversary = due if due != old['due_date'] else old['anniversary']
            db.execute('''UPDATE budget_reserves SET name=?,notes=?,account_id=?,target_cents=?,due_date=?,anniversary=?,
                frequency=?,version=version+1,updated_at=? WHERE id=?''',
                (name,notes,account_id,amount,due,anniversary,frequency,now,reserve_id))
        monthly_start=None
        if monthly is not None:
            monthly_start=old['monthly_start_month'] if old is not None and old['monthly_amount_cents'] is not None else date.today().strftime('%Y-%m')
        db.execute('UPDATE budget_reserves SET category_id=?,monthly_amount_cents=?,monthly_start_month=?,open_ended=? WHERE id=?',(category_id,monthly,monthly_start,int(open_ended),reserve_id))
        db.commit()
        return dict(id=reserve_id)
    except Exception:
        db.rollback()
        raise
    finally:
        if db.in_transaction:
            db.rollback()


def plan(target, saved, start, due, today, funded_this_month=False):
    remaining = max(0, target-saved)
    current_month = max(today.strftime('%Y-%m'), start[:7])
    year, month = map(int,current_month.split('-'))
    if funded_this_month:
        year, month = (year+1,1) if month==12 else (year,month+1)
    anchor_day = date.fromisoformat(start).day
    next_date = max(today.isoformat(),date(year,month,min(anchor_day,calendar.monthrange(year,month)[1])).isoformat())
    due_day = date.fromisoformat(due)
    last_slot = date(due_day.year,due_day.month,min(anchor_day,calendar.monthrange(due_day.year,due_day.month)[1]))
    # A scheduled deposit must precede the expense deadline. This gives twelve
    # deposits for an exact annual anniversary, rather than counting thirteen.
    slots = max(0,(due_day.year-year)*12+due_day.month-month+(1 if last_slot<due_day else 0)) if next_date<due else 0
    # Round upward to cents so equal deposits are sufficient; the last can be smaller.
    required = (remaining+slots-1)//slots if slots else remaining
    return dict(remaining=remaining/100,monthly_required=required/100,months_left=slots,
        next_contribution_date=next_date if remaining and slots else None,
        overdue=due<today.isoformat() and remaining>0,
        urgent=remaining>0 and slots==0,
        progress_percent=round(min(100,saved/target*100),2),surplus=max(0,saved-target)/100)


def workspace():
    db, today = get_db(), date.today()
    accounts = []
    warnings = []
    for row in db.execute("SELECT * FROM budget_accounts WHERE UPPER(COALESCE(currency,'PLN'))='PLN' ORDER BY id"):
        reserved = reserved_cents(db,row['id'])/100
        available = round(float(row['balance'])-reserved,2)
        accounts.append(dict(id=row['id'],name=row['name'],balance=float(row['balance']),reserved=reserved,available=available))
        if available < -.005:
            warnings.append(f'{row["name"]}: zapisane rezerwy przekraczają saldo konta o {abs(available):.2f} PLN. Sprawdź wydatki i zwolnij lub popraw rezerwy.')
    items = []
    for row in db.execute('SELECT r.*,a.name account_name FROM budget_reserves r JOIN budget_accounts a ON a.id=r.account_id ORDER BY r.due_date,r.id'):
        saved = _balance(db,row['id'])
        funded = db.execute('''SELECT COALESCE(SUM(CASE WHEN kind='ADD' THEN amount_cents
            WHEN kind='RELEASE' THEN -amount_cents ELSE 0 END),0) FROM budget_reserve_movements
            WHERE reserve_id=? AND cycle=? AND substr(date,1,7)=?''',
            (row['id'],row['cycle'],today.strftime('%Y-%m'))).fetchone()[0] > 0
        status = 'ARCHIVED' if row['is_archived'] else 'COMPLETED' if row['completed_at'] else 'ACTIVE'
        item = dict(id=row['id'],name=row['name'],notes=row['notes'],account_id=row['account_id'],account_name=row['account_name'],category_id=row['category_id'],
            monthly_amount=row['monthly_amount_cents']/100 if row['monthly_amount_cents'] is not None else None,
            open_ended=bool(row['open_ended']),
            target_amount=row['target_cents']/100,saved=saved/100,due_date=row['due_date'],start_date=row['start_date'],
            frequency=row['frequency'],cycle=row['cycle'],version=row['version'],status=status,funded_this_month=funded)
        item.update(plan(row['target_cents'],saved,row['start_date'],row['due_date'],today,funded))
        if row['monthly_amount_cents'] is not None:
            from budget_planning_service import reserve_plans
            current=next(r for r in reserve_plans(db,today.strftime('%Y-%m')) if r['reserve_id']==row['id']) if status=='ACTIVE' else None
            left=current['remaining'] if current else 0
            item.update(month_planned=current['planned'] if current else 0,month_allocated=current['funded'] if current else 0)
            item.update(monthly_required=left,remaining=left,months_left=0,progress_percent=0,surplus=0,
                urgent=False,overdue=False,next_contribution_date=today.isoformat() if left else None)
        item['locations'] = locations(db,row['id'])
        if status!='ACTIVE':
            item.update(monthly_required=0,next_contribution_date=None,urgent=False,overdue=False)
        item['movements'] = [dict(id=m['id'],cycle=m['cycle'],kind=m['kind'],amount=m['amount_cents']/100,date=m['date'],
            notes=m['notes'],account_id=m['account_id'],account_name=m['account_name'],budget_cost=m['budget_cost_cents']/100,
            expense_amount=m['expense_amount_cents']/100 if m['expense_amount_cents'] is not None else None,
            budget_entry_id=m['budget_entry_id']) for m in db.execute('''SELECT m.*,a.name account_name,e.amount_cents expense_amount_cents
                FROM budget_reserve_movements m LEFT JOIN budget_entries_v2 e ON e.id=m.budget_entry_id
                JOIN budget_accounts a ON a.id=m.account_id
                WHERE m.reserve_id=? ORDER BY m.date DESC,m.id DESC''',(row['id'],))]
        item['transfers'] = [dict(id=t['id'],amount=t['amount_cents']/100,date=t['date'],notes=t['notes'],
            source_account_name=t['source_name'],target_account_name=t['target_name'],move_money=bool(t['move_money']),reserve_action=t['reserve_action'])
            for t in db.execute('''SELECT t.*,s.name source_name,a.name target_name FROM budget_account_transfers t
                JOIN budget_accounts s ON s.id=t.source_account_id JOIN budget_accounts a ON a.id=t.target_account_id
                WHERE reserve_id=? ORDER BY date DESC,t.id DESC''',(row['id'],))]
        items.append(item)
    active = [r for r in items if r['status']=='ACTIVE']
    from budget_planning_service import reserve_plans
    current_plans={r['reserve_id']:r for r in reserve_plans(db,today.strftime('%Y-%m'))}
    return dict(as_of=today.isoformat(),items=items,accounts=accounts,warnings=warnings,
        categories=category_options(db),
        totals=dict(saved=round(sum(r['saved'] for r in active),2),remaining=round(sum(r['remaining'] for r in active),2),
            monthly_remaining=round(sum(current_plans.get(r['id'],{}).get('remaining',0) for r in active),2),
            monthly_required=round(sum(r['monthly_required'] for r in active if not r['urgent']),2),
            urgent_amount=round(sum(r['remaining'] for r in active if r['urgent']),2),active=len(active)))


def _next_year(row, paid):
    anchor = date.fromisoformat(row['anniversary'])
    year = max(date.fromisoformat(row['due_date']).year+1,paid.year)
    while year<=2100:
        result = date(year,anchor.month,min(anchor.day,calendar.monthrange(year,anchor.month)[1]))
        if result>paid:
            return result.isoformat()
        year+=1
    raise ValidationError('Nie można wyznaczyć kolejnego terminu po roku 2100.')


def move(reserve_id,data, *, within_transaction=False):
    kind = data.get('kind')
    if kind not in ('ADD','RELEASE','SPEND'):
        raise ValidationError('Nieprawidłowy rodzaj operacji rezerwy.')
    amount = cents(data.get('amount'))
    day = _date(data.get('date'),'Data operacji')
    if day>date.today().isoformat():
        raise ValidationError('Przyszła wpłata jest planem. Zapisz odłożenie dopiero po jego wykonaniu.')
    notes = data.get('notes','')
    if not isinstance(notes,str) or len(notes)>500:
        raise ValidationError('Notatka może mieć najwyżej 500 znaków.')
    token, fingerprint = _request_id(data), _fingerprint(dict(data,reserve_id=reserve_id))
    db, now = get_db(), _now()
    try:
        if not within_transaction:
            db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM budget_cancelled_requests WHERE request_id=?',(token,)).fetchone():
            raise ApiError('reserve_request_cancelled','Ta operacja została cofnięta. Otwórz nowy formularz.',status=409)
        previous = db.execute('SELECT * FROM budget_reserve_movements WHERE request_id=?',(token,)).fetchone()
        if previous:
            if previous['request_payload']!=fingerprint:
                raise ApiError('reserve_request_conflict','Ten zapis został już przyjęty z innymi danymi.',status=409)
            return dict(id=previous['id'],budget_entry_id=previous['budget_entry_id'])
        row = _row(db,reserve_id,_version(data))
        if row['is_archived'] or row['completed_at']:
            raise ValidationError('Ta rezerwa nie jest aktywna.')
        last_day = last_reserve_day(db,reserve_id)
        if day<row['start_date'] or (last_day and day<last_day):
            raise ValidationError('Data nie może poprzedzać początku cyklu ani ostatniej operacji. Zwolnij błędną kwotę i zapisz poprawne odłożenie.')
        account_id = positive_id(data.get('account_id',row['account_id']),'konto')
        account = _account(db,account_id)
        saved = _balance(db,reserve_id)
        at_account = location_cents(db,reserve_id,account_id)
        all_reserved = reserved_cents(db,account_id)
        balance = round(float(account['balance'])*100)
        released, entry_id = amount, None
        releases = [(account_id,amount)]
        if kind=='ADD':
            if amount>max(0,balance-all_reserved):
                raise ValidationError('Na koncie brakuje środków wolnych od innych rezerw.')
        elif kind=='RELEASE':
            if amount>at_account:
                raise ValidationError('Nie można zwolnić więcej niż odłożono na tę rezerwę na wybranym koncie.')
        else:
            from budget_plan_history import freeze
            freeze(db,reserve_id,include_current=True)
            existing = None
            if data.get('existing_entry_id') is not None:
                entry_id = positive_id(data['existing_entry_id'],'zapisany wydatek')
                existing = db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry_id,)).fetchone()
                if not existing or (existing['kind'],existing['account_id'],existing['amount_cents'],existing['date'])!=('EXPENSE',account_id,amount,day):
                    raise ValidationError('Zapisany wydatek musi mieć tę samą kwotę, datę i konto płatności.')
                from budget_category_service import require_version
                require_version(existing,data.get('entry_version'),'Powiązane wydatki')
                if any(db.execute(f'SELECT 1 FROM {table} WHERE {column}=?',(entry_id,)).fetchone()
                       for table,column in (('budget_bill_payments_v2','entry_id'),('loan_installment_payments','budget_entry_id'),
                                            ('loan_overpayments','budget_entry_id'),('budget_reserve_movements','budget_entry_id'))):
                    raise ValidationError('Ten wydatek rozlicza już rachunek, kredyt lub inną rezerwę.')
                # Current cash already includes this payment, including HISTORY imports.
                balance += amount
            else:
                category_id = positive_id(data.get('category_id'),'kategoria')
                if not db.execute('SELECT 1 FROM budget_categories_v2 WHERE id=?',(category_id,)).fetchone():
                    raise NotFoundError('Kategoria nie istnieje.')
            if row['monthly_amount_cents'] is not None and not row['open_ended']:
                if existing is not None:
                    lines=list(db.execute('SELECT category_id FROM budget_entry_lines_v2 WHERE entry_id=?',(entry_id,)))
                    if not lines or any(line['category_id']!=row['category_id'] for line in lines):
                        raise ValidationError('Przypisz płatność do kategorii tej puli przed powiązaniem.')
                elif category_id!=row['category_id']:
                    raise ValidationError('Płatność musi korzystać z kategorii miesięcznej puli.')
            if amount>balance-(all_reserved-at_account):
                raise ValidationError('Płatność naruszałaby środki innych rezerw lub przekraczała saldo konta.')
            released = saved if row['frequency']=='ONCE' and row['monthly_amount_cents'] is None else min(saved,amount)
            # The expense is paid from exactly one account. Earmarks consumed on
            # other accounts are released there, without fictitious bank transfers.
            first_release = min(at_account,released)
            releases, left = [(account_id,first_release)], released-first_release
            for location in locations(db,reserve_id):
                if location['account_id']==account_id or not left:
                    continue
                used = min(round(location['amount']*100),left)
                releases.append((location['account_id'],used)); left -= used
            if existing is None:
                entry_id = insert_entry(db,dict(account_id=account_id,kind='EXPENSE',amount_cents=amount,date=day,
                    description=f'{row["name"]} — płatność z rezerwy',merchant=None,
                    lines=[dict(category_id=category_id,amount_cents=amount,label=row['name'])]))
            # This is an explicit reserve payment, not automatic import matching.
            # The bills screen calls us inside its own transaction and creates
            # its payment record there; direct reserve payments settle it here.
            if not within_transaction:
                linked=db.execute('SELECT * FROM budget_bills_v2 WHERE active=1 AND reserve_id=?',(reserve_id,)).fetchone()
                if linked:
                    from budget_bill_schedule import due_in_month,amount_cents
                    occurrence=day[:7] if row['monthly_amount_cents'] is not None else row['due_date'][:7]
                    previous=db.execute('SELECT 1 FROM budget_bill_payments_v2 WHERE bill_id=? AND month=?',(linked['id'],occurrence)).fetchone()
                    if previous and row['monthly_amount_cents'] is None:
                        raise ValidationError('Zobowiązanie finansowane z tej rezerwy jest już rozliczone.')
                    if not previous and due_in_month(linked,occurrence):
                        db.execute('INSERT INTO budget_bill_payments_v2(bill_id,month,entry_id,planned_amount_cents) VALUES(?,?,?,?)',(linked['id'],occurrence,entry_id,amount_cents(linked,occurrence)))
                        db.execute('UPDATE budget_bills_v2 SET version=version+1 WHERE id=?',(linked['id'],))
            if row['monthly_amount_cents'] is not None:
                pass # Payments consume earmarks; the envelope stays active.
            elif row['frequency']=='YEARLY':
                next_due = _next_year(row,date.fromisoformat(day))
                db.execute('UPDATE budget_reserves SET due_date=?,start_date=?,cycle=cycle+1 WHERE id=?',(next_due,day,reserve_id))
            else:
                db.execute('UPDATE budget_reserves SET completed_at=? WHERE id=?',(now,reserve_id))
        movement_id = None
        movement_ids = []
        from budget_reserve_funding_service import budget_pool
        budget_cost = amount if kind=='ADD' else -min(budget_pool(db,reserve_id),released)
        for index,(location_id,location_amount) in enumerate(releases):
            location_token = token if index==0 else str(uuid5(UUID(token),str(location_id)))
            inserted = db.execute('''INSERT INTO budget_reserve_movements
                (reserve_id,account_id,cycle,kind,amount_cents,budget_cost_cents,date,notes,budget_entry_id,request_id,request_payload,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (reserve_id,location_id,row['cycle'],kind,location_amount,budget_cost if index==0 else 0,day,notes.strip(),entry_id if index==0 else None,
                 location_token,fingerprint,now)).lastrowid
            if index==0:
                movement_id = inserted
            movement_ids.append(inserted)
        if kind=='SPEND':
            db.execute('''INSERT INTO budget_settlements(entry_id,reserve_id,created_entry,before_json,movement_ids,recorded_at)
                VALUES(?,?,?,?,?,?)''',(entry_id,reserve_id,int(existing is None),json.dumps(dict(row)),json.dumps(movement_ids),now))
        db.execute('UPDATE budget_reserves SET version=version+1,updated_at=? WHERE id=?',(now,reserve_id))
        if not within_transaction:
            db.commit()
        return dict(id=movement_id,budget_entry_id=entry_id)
    except Exception:
        if not within_transaction:
            db.rollback()
        raise
    finally:
        if not within_transaction and db.in_transaction:
            db.rollback()


def archive(reserve_id,data):
    if type(data.get('archived')) is not bool:
        raise ValidationError('Nieprawidłowy stan archiwizacji.')
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        _row(db,reserve_id,_version(data))
        if data['archived'] and _balance(db,reserve_id)>0:
            raise ValidationError('Najpierw zwolnij odłożone środki albo zapisz płatność.')
        from budget_plan_history import freeze
        freeze(db,reserve_id,include_current=True)
        db.execute('UPDATE budget_reserves SET is_archived=?,version=version+1,updated_at=? WHERE id=?',
            (int(data['archived']),_now(),reserve_id))
        db.commit()
        return dict(id=reserve_id)
    except Exception:
        db.rollback()
        raise
