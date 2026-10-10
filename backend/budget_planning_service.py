"""Household pay cycles, reserve plans, carryover policies and larger purchases."""
import calendar
from datetime import date,timedelta
from uuid import UUID,uuid4,uuid5

from api.exceptions import ApiError,NotFoundError,ValidationError
from database import get_db


def shift_month(month,delta):
    year,current=map(int,month.split('-')); total=year*12+current-1+delta
    return f'{total//12:04d}-{total%12+1:02d}'


def payday(month,day):
    year,current=map(int,month.split('-'))
    return date(year,current,min(day,calendar.monthrange(year,current)[1]))


def settings(db):
    raw=dict(db.execute('SELECT * FROM budget_planning_settings WHERE id=1').fetchone())
    income=db.execute('SELECT * FROM budget_expected_incomes WHERE id=? AND active=1',(raw['income_id'],)).fetchone() if raw['income_id'] else None
    if not income:
        income=db.execute("SELECT * FROM budget_expected_incomes WHERE active=1 AND frequency='MONTHLY' ORDER BY amount_cents DESC,id LIMIT 1").fetchone()
    account=raw['spending_account_id'] or (income['account_id'] if income else None)
    if not account:
        row=db.execute("SELECT id FROM budget_accounts WHERE UPPER(COALESCE(currency,'PLN'))='PLN' ORDER BY id LIMIT 1").fetchone()
        account=row['id'] if row else None
    return dict(**raw,resolved_pay_day=raw['pay_day'] or (date.fromisoformat(income['start_date']).day if income else 10),
        resolved_spending_account_id=account,resolved_loan_account_id=raw['loan_account_id'] or account,
        resolved_income_id=income['id'] if income else None)


def check_version(current, version, label):
    expected=current['version'] if current else 0
    if type(version) is not int or version!=expected:
        raise ApiError('planning_version_conflict',f'{label} zmienił się. Odśwież dane.',status=409)


def save_settings(data):
    from routes_budget_workspace import positive_id
    from budget_reserves_service import _account
    db=get_db()
    day=data.get('pay_day')
    if day is not None and (type(day) is not int or not 1<=day<=31): raise ValidationError('Wybierz dzień wypłaty od 1 do 31.')
    spending=positive_id(data['spending_account_id'],'konto wydatków') if data.get('spending_account_id') else None
    loan=positive_id(data['loan_account_id'],'konto rat') if data.get('loan_account_id') else None
    income=positive_id(data['income_id'],'dochód') if data.get('income_id') else None
    try:
        db.execute('BEGIN IMMEDIATE')
        check_version(db.execute('SELECT * FROM budget_planning_settings WHERE id=1').fetchone(),data.get('version'),'Ustawienie okresu')
        for account_id in (spending,loan):
            if account_id: _account(db,account_id)
        if income and not db.execute("SELECT 1 FROM budget_expected_incomes WHERE id=? AND frequency='MONTHLY' AND active=1",(income,)).fetchone():
            raise ValidationError('Wybierz aktywny miesięczny wpływ.')
        db.execute('UPDATE budget_planning_settings SET pay_day=?,income_id=?,spending_account_id=?,loan_account_id=?,version=version+1 WHERE id=1',(day,income,spending,loan))
        db.commit(); return dict(id=1)
    except Exception: db.rollback(); raise


def reserve_plans(db,month):
    from budget_reserves_service import plan,_balance
    today=date.today()
    cursor=today if month==today.strftime('%Y-%m') else date.fromisoformat(month+'-01')
    result=[]
    for row in db.execute('SELECT r.*,a.name account_name FROM budget_reserves r JOIN budget_accounts a ON a.id=r.account_id ORDER BY r.due_date,r.id'):
        history=db.execute('SELECT plan_json FROM budget_reserve_plan_history WHERE reserve_id=? AND month=?',(row['id'],month)).fetchone()
        if history and (month<today.strftime('%Y-%m') or row['completed_at']):
            import json
            snapshot=json.loads(history['plan_json'])
            contribution=db.execute("SELECT COALESCE(SUM(CASE WHEN kind='ADD' THEN amount_cents WHEN kind='RELEASE' THEN -amount_cents ELSE 0 END),0) FROM budget_reserve_movements WHERE reserve_id=? AND substr(date,1,7)=?",(row['id'],month)).fetchone()[0]
            from budget_media_service import allocated_cents
            funded=allocated_cents(db,dict(id=row['id'],category_id=snapshot['category_id']),month) if snapshot['monthly_amount'] is not None and not snapshot['open_ended'] else contribution
            snapshot.update(contributed=contribution/100,funded=max(0,funded)/100,remaining=max(0,round(snapshot['planned']*100)-max(0,funded))/100,historical=True)
            if row['completed_at'] and month>=row['completed_at'][:7]:snapshot.update(active=False,remaining=0)
            result.append(snapshot)
            continue
        if row['is_archived']: continue
        monthly=row['monthly_amount_cents'] is not None and month>=(row['monthly_start_month'] or row['start_date'][:7])
        if row['monthly_amount_cents'] is not None and month < row['start_date'][:7]: continue
        stored=db.execute('SELECT * FROM budget_reserve_month_plans WHERE reserve_id=? AND month=?',(row['id'],month)).fetchone()
        if row['completed_at'] and not stored: continue
        funded=db.execute('''SELECT COALESCE(SUM(CASE WHEN kind='ADD' THEN amount_cents WHEN kind='RELEASE' THEN -amount_cents ELSE 0 END),0)
            FROM budget_reserve_movements WHERE reserve_id=? AND substr(date,1,7)=?''',(row['id'],month)).fetchone()[0]
        # Derive the month's target before its contributions. A partial deposit
        # must not silently mark the entire automatic monthly plan as complete.
        if month<today.strftime('%Y-%m'):
            saved=db.execute('''SELECT COALESCE(SUM(CASE WHEN kind='ADD' THEN amount_cents ELSE -amount_cents END),0)
                FROM budget_reserve_movements WHERE reserve_id=? AND substr(date,1,7)<=?''',(row['id'],month)).fetchone()[0]
        else:
            saved=_balance(db,row['id'])
        if monthly:
            from budget_media_service import allocated_cents
            contributed=funded
            if not row['open_ended']: funded=allocated_cents(db,row,month)
            recommendation=row['monthly_amount_cents']
            if row['open_ended']:
                target=stored['amount_cents'] if stored and month<today.strftime('%Y-%m') else recommendation
                recommendation=target
            else:
                target=stored['amount_cents'] if stored else recommendation
        else:
            recommended=plan(row['target_cents'],max(0,saved-funded),row['start_date'],row['due_date'],cursor,False)
            next_day=recommended['next_contribution_date']
            recommendation=round(recommended['monthly_required']*100) if next_day and next_day[:7]<=month and not row['completed_at'] else 0
            if recommended['urgent'] and row['due_date'][:7]==month and not row['completed_at']: recommendation=round(recommended['remaining']*100)
            target=stored['amount_cents'] if stored else max(0,funded,recommendation)
        result.append(dict(reserve_id=row['id'],name=row['name'],account_id=row['account_id'],account_name=row['account_name'],
            category_id=row['category_id'],
            monthly_amount=(target if row['open_ended'] else row['monthly_amount_cents'])/100 if monthly else None,
            open_ended=bool(row['open_ended']) if monthly else False,
            contributed=contributed/100 if monthly else funded/100,
            due_date=row['due_date'],recommended=recommendation/100,planned=target/100,funded=max(0,funded)/100,
            remaining=max(0,target-max(0,funded))/100,priority=stored['priority'] if stored else 2,
            automatic=not bool(stored),version=stored['version'] if stored else 0,reserve_version=row['version'],active=not bool(row['completed_at'])))
    return sorted(result,key=lambda r:(r['priority'],r['due_date'],r['reserve_id']))


def save_reserve_plan(reserve_id,data):
    from routes_budget_workspace import cents,month_value
    db=get_db();month=month_value(data.get('month'));amount=cents(data.get('amount'),'Plan odłożenia',allow_zero=True)
    priority=data.get('priority',2)
    if type(priority) is not int or not 1<=priority<=3: raise ValidationError('Wybierz priorytet od 1 do 3.')
    if month<date.today().strftime('%Y-%m'): raise ValidationError('Zapisz plan na bieżący lub przyszły miesiąc.')
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM budget_reserves WHERE id=? AND is_archived=0 AND completed_at IS NULL',(reserve_id,)).fetchone()
        if not row: raise ValidationError('Wybierz aktywną rezerwę.')
        if row['open_ended']: raise ValidationError('Ta rezerwa ma stały plan miesięczny. Zmień kwotę w jej ustawieniach.')
        current=db.execute('SELECT * FROM budget_reserve_month_plans WHERE reserve_id=? AND month=?',(reserve_id,month)).fetchone()
        check_version(current,data.get('version'),'Plan odłożenia')
        db.execute('''INSERT INTO budget_reserve_month_plans(reserve_id,month,amount_cents,priority) VALUES(?,?,?,?)
            ON CONFLICT(reserve_id,month) DO UPDATE SET amount_cents=excluded.amount_cents,priority=excluded.priority,version=version+1''',(reserve_id,month,amount,priority))
        db.commit();return dict(id=reserve_id)
    except Exception: db.rollback();raise


def save_policy(category_id,data):
    from routes_budget_workspace import month_value,positive_id
    db=get_db();month=month_value(data.get('start_month'));mode=data.get('mode')
    if mode not in ('RESET','ROLLOVER','RESERVE'): raise ValidationError('Wybierz zasadę niewykorzystanego limitu.')
    reserve_id=positive_id(data.get('reserve_id'),'rezerwę') if mode=='RESERVE' else None
    try:
        db.execute('BEGIN IMMEDIATE')
        category=db.execute('SELECT * FROM budget_categories_v2 WHERE id=?',(category_id,)).fetchone()
        if not category or category['parent_id'] or category['is_unassigned']:
            raise ValidationError('Zasadę ustawia się dla kategorii głównej; jej podkategorie korzystają ze wspólnego limitu.')
        if mode!='RESET' and db.execute('SELECT 1 FROM budget_reserves WHERE category_id=? AND monthly_amount_cents IS NOT NULL AND open_ended=0 AND is_archived=0',(category_id,)).fetchone():
            raise ValidationError('Odłożone środki tej puli już przechodzą na kolejne faktury. Nie przenoś dodatkowo limitu kategorii.')
        if reserve_id and not db.execute('SELECT 1 FROM budget_reserves WHERE id=? AND is_archived=0 AND completed_at IS NULL',(reserve_id,)).fetchone():
            raise ValidationError('Wybierz aktywną rezerwę.')
        current=db.execute('SELECT * FROM budget_category_policies WHERE category_id=?',(category_id,)).fetchone()
        check_version(current,data.get('version'),'Zasada kategorii')
        db.execute('''INSERT INTO budget_category_policies(category_id,mode,reserve_id,start_month) VALUES(?,?,?,?)
            ON CONFLICT(category_id) DO UPDATE SET mode=excluded.mode,reserve_id=excluded.reserve_id,start_month=excluded.start_month,version=version+1''',(category_id,mode,reserve_id,month))
        db.commit();return dict(id=category_id)
    except Exception: db.rollback();raise


def close_month(data):
    from routes_budget_workspace import month_value
    from budget_category_hierarchy_service import category_workspace
    from budget_reserves_service import _request_id,_fingerprint,_now,move
    db=get_db();month=month_value(data.get('month'));token=_request_id(data);fingerprint=_fingerprint(data)
    if month>=date.today().strftime('%Y-%m'): raise ValidationError('Można zamknąć tylko zakończony miesiąc.')
    try:
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT * FROM budget_month_closings WHERE request_id=?',(token,)).fetchone()
        if previous:
            if previous['request_payload']!=fingerprint: raise ApiError('closing_request_conflict','To zamknięcie przyjęto z innymi danymi.',status=409)
            return dict(id=previous['id'])
        if db.execute('SELECT 1 FROM budget_month_closings WHERE month=?',(month,)).fetchone(): raise ValidationError('Ten miesiąc już zamknięto. Środki nie zostaną odłożone ponownie.')
        if data.get('review_token'):
            from budget_month_review_service import review
            if review(db,month)['token']!=data['review_token']: raise ApiError('closing_review_conflict','Dane zmieniły się po sprawdzeniu miesiąca. Odśwież listę przed zamknięciem.',status=409)
        categories={c['id']:c for c in category_workspace(db,month)}
        expected=data.get('category_versions',{})
        if not isinstance(expected,dict): raise ValidationError('Odśwież zasady przed zamknięciem.')
        expected_amounts=data.get('amounts',{})
        if not isinstance(expected_amounts,dict): raise ValidationError('Odśwież kwoty przed zamknięciem.')
        closing=db.execute('INSERT INTO budget_month_closings(month,request_id,request_payload,created_at) VALUES(?,?,?,?)',(month,token,fingerprint,_now())).lastrowid
        for policy in db.execute("SELECT * FROM budget_category_policies WHERE mode='RESERVE' AND start_month<=?",(month,)).fetchall():
            check_version(policy,expected.get(str(policy['category_id'])),'Zasada kategorii')
            amount=max(0,round(categories[policy['category_id']]['remaining']*100))
            preview=expected_amounts.get(str(policy['category_id']))
            if isinstance(preview,bool) or not isinstance(preview,(int,float)) or preview!=amount/100:
                raise ApiError('closing_amount_conflict','Wydatki lub plan zmieniły się. Odśwież kwoty przed zamknięciem.',status=409)
            movement=None
            if amount:
                reserve=db.execute('SELECT * FROM budget_reserves WHERE id=?',(policy['reserve_id'],)).fetchone()
                movement=move(reserve['id'],dict(kind='ADD',amount=amount/100,date=date.today().isoformat(),version=reserve['version'],
                    notes=f'Niewykorzystany limit {categories[policy["category_id"]]["name"]} za {month}',
                    request_id=str(uuid5(UUID(token),str(policy['category_id'])))),within_transaction=True)['id']
            db.execute('INSERT INTO budget_month_closing_items(closing_id,category_id,reserve_id,amount_cents,movement_id) VALUES(?,?,?,?,?)',
                (closing,policy['category_id'],policy['reserve_id'],amount,movement))
        import json
        from budget_month_snapshot import capture
        from budget_plan_history import freeze
        for reserve in db.execute('SELECT id FROM budget_reserves').fetchall(): freeze(db,reserve['id'])
        db.execute('INSERT INTO budget_month_snapshots VALUES(?,?,?)',(month,json.dumps(capture(db,month),ensure_ascii=False),_now()))
        db.commit();return dict(id=closing)
    except Exception: db.rollback();raise
    finally:
        if db.in_transaction: db.rollback()


def purchase_items(db):
    from budget_reserves_service import _balance,plan
    result=[]
    for row in db.execute('SELECT p.*,a.name account_name,r.completed_at,r.is_archived FROM budget_purchase_plans p JOIN budget_accounts a ON a.id=p.account_id LEFT JOIN budget_reserves r ON r.id=p.reserve_id ORDER BY p.due_date,p.id'):
        saved=_balance(db,row['reserve_id']) if row['reserve_id'] else 0
        value=dict(row)
        value.update(amount=row['amount_cents']/100,low=row['low_cents']/100,high=row['high_cents']/100,saved=saved/100,
            status='COMPLETED' if row['completed_at'] else 'CANCELLED' if row['is_archived'] and row['status']=='PLANNED' else row['status'])
        if row['reserve_id']:
            reserve=db.execute('SELECT * FROM budget_reserves WHERE id=?',(row['reserve_id'],)).fetchone()
            value.update(amount=reserve['target_cents']/100,due_date=reserve['due_date'],
                account_id=reserve['account_id'],account_name=db.execute('SELECT name FROM budget_accounts WHERE id=?',(reserve['account_id'],)).fetchone()[0],
                reserve_version=reserve['version'],low=min(row['low_cents'],reserve['target_cents'])/100,high=max(row['high_cents'],reserve['target_cents'])/100,
                monthly_required=plan(reserve['target_cents'],saved,reserve['start_date'],reserve['due_date'],date.today())['monthly_required'])
        else: value['monthly_required']=0
        result.append(value)
    return result


def save_purchase(data,purchase_id=None):
    from routes_budget_workspace import cents,positive_id,text_field
    from budget_reserves_service import _account,_date,_request_id,_fingerprint,_now,_balance
    name=text_field(data.get('name'),'Nazwa zakupu lub wydarzenia',120)
    amount=cents(data.get('amount'));low=cents(data.get('low',data.get('amount')));high=cents(data.get('high',data.get('amount')))
    if not low<=amount<=high: raise ValidationError('Wariant oszczędny nie może być droższy od podstawowego, a rozszerzony tańszy.')
    due=_date(data.get('due_date'),'Termin zakupu')
    account_id=positive_id(data.get('account_id'),'konto')
    category_id=positive_id(data['category_id'],'kategorię') if data.get('category_id') else None
    status=data.get('status','IDEA')
    if status not in ('IDEA','PLANNED','CANCELLED'): raise ValidationError('Nieprawidłowy stan zakupu.')
    if status=='PLANNED' and due<date.today().isoformat(): raise ValidationError('Zaplanuj zakup na dzisiaj lub przyszłość.')
    notes=data.get('notes','')
    if not isinstance(notes,str) or len(notes)>2000: raise ValidationError('Opis może mieć najwyżej 2000 znaków.')
    db,now=get_db(),_now();token=_request_id(data) if purchase_id is None else None;fingerprint=_fingerprint(data)
    try:
        db.execute('BEGIN IMMEDIATE');_account(db,account_id)
        if category_id and not db.execute('SELECT 1 FROM budget_categories_v2 WHERE id=?',(category_id,)).fetchone(): raise NotFoundError('Kategoria nie istnieje.')
        current=db.execute('SELECT * FROM budget_purchase_plans WHERE id=?',(purchase_id,)).fetchone() if purchase_id else None
        if purchase_id and not current: raise NotFoundError('Plan zakupu nie istnieje.')
        if current: check_version(current,data.get('version'),'Plan zakupu')
        else:
            retry=db.execute('SELECT * FROM budget_purchase_plans WHERE request_id=?',(token,)).fetchone()
            if retry:
                if retry['request_payload']!=fingerprint: raise ApiError('purchase_request_conflict','Plan zapisano z innymi danymi.',status=409)
                return dict(id=retry['id'])
        reserve_id=current['reserve_id'] if current else None
        if reserve_id:
            reserve=db.execute('SELECT * FROM budget_reserves WHERE id=?',(reserve_id,)).fetchone()
            check_version(reserve,data.get('reserve_version'),'Rezerwa zakupu')
            if reserve['completed_at']: raise ValidationError('Ten zakup został rozliczony w rezerwie.')
            if status!='PLANNED' and _balance(db,reserve_id)>0: raise ValidationError('Najpierw zwolnij odłożone środki w rezerwie, potem zmień zakup na pomysł lub anuluj.')
            if due<reserve['start_date']: raise ValidationError('Termin nie może poprzedzać początku odkładania.')
            if db.execute('SELECT 1 FROM budget_bills_v2 WHERE reserve_id=? AND active=1',(reserve_id,)).fetchone():
                raise ValidationError('Rezerwa finansuje rachunek. Zmień lub odłącz zobowiązanie przed edycją planu zakupu.')
            db.execute('''UPDATE budget_reserves SET name=?,target_cents=?,due_date=?,anniversary=?,account_id=?,
                is_archived=?,version=version+1,updated_at=? WHERE id=?''',(name,amount,due,due,account_id,int(status!='PLANNED'),now,reserve_id))
        elif status=='PLANNED':
            reserve_id=db.execute('''INSERT INTO budget_reserves
                (name,notes,account_id,target_cents,start_date,due_date,anniversary,frequency,request_id,request_payload,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,'ONCE',?,?,?,?)''',(name,notes,account_id,amount,date.today().isoformat(),due,due,
                str(uuid4()),fingerprint,now,now)).lastrowid
        values=(name,amount,low,high,due,account_id,category_id,reserve_id,status,notes.strip(),now)
        if current:
            db.execute('''UPDATE budget_purchase_plans SET name=?,amount_cents=?,low_cents=?,high_cents=?,due_date=?,account_id=?,
                category_id=?,reserve_id=?,status=?,notes=?,updated_at=?,version=version+1 WHERE id=?''',(*values,purchase_id))
        else:
            purchase_id=db.execute('''INSERT INTO budget_purchase_plans
                (name,amount_cents,low_cents,high_cents,due_date,account_id,category_id,reserve_id,status,notes,updated_at,request_id,request_payload,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(*values,token,fingerprint,now)).lastrowid
        db.commit();return dict(id=purchase_id)
    except Exception: db.rollback();raise
    finally:
        if db.in_transaction: db.rollback()


def workspace(db,month):
    from budget_bill_schedule import due_in_month,due_date
    from budget_bills_service import serialize
    from expected_income_service import pending_amount_cents
    from budget_category_hierarchy_service import category_options
    config=settings(db);today=date.today();day=config['resolved_pay_day']
    start=payday(month,day);end=payday(shift_month(month,1),day)-timedelta(days=1)
    next_pay=payday(today.strftime('%Y-%m'),day)
    if next_pay<=today: next_pay=payday(shift_month(today.strftime('%Y-%m'),1),day)
    from budget_refunds_service import flows as net_flows
    flows=net_flows(db,start.isoformat(),end.isoformat())
    catalog=[];before_pay=0
    for row in db.execute('SELECT b.*,a.name account_name FROM budget_bills_v2 b JOIN budget_accounts a ON a.id=b.account_id ORDER BY b.active DESC,b.title,b.id'):
        item=serialize(db,row,month);item['account_name']=row['account_name'];catalog.append(item)
        if not row['active']: continue
        for key in sorted({today.strftime('%Y-%m'),next_pay.strftime('%Y-%m')}):
            if due_in_month(row,key) and today.isoformat()<=due_date(row,key)<next_pay.isoformat():
                occurrence=serialize(db,row,key)
                if occurrence['status']!='PAID': before_pay+=round(occurrence['amount']*100)
    options=category_options(db)
    policies={r['category_id']:dict(r) for r in db.execute('SELECT * FROM budget_category_policies')}
    from budget_loan_plan_service import items as loan_items
    from budget_month_review_service import review
    loans,loan_warnings=loan_items(db,month)
    from budget_matching_service import suggestions
    return dict(payment_matches=suggestions(db,month),settings=config,loans=loans,loan_warnings=loan_warnings,month_review=review(db,month),reserve_plans=reserve_plans(db,month),purchases=purchase_items(db),bill_catalog=catalog,
        policies=[dict(category_id=c['id'],name=c['name'],mode=policies.get(c['id'],{}).get('mode','RESET'),
            reserve_id=policies.get(c['id'],{}).get('reserve_id'),start_month=policies.get(c['id'],{}).get('start_month',month),version=policies.get(c['id'],{}).get('version',0))
            for c in options if not c['parent_id'] and not c['is_unassigned']],
        cycle=dict(start=start.isoformat(),end=end.isoformat(),next_payday=next_pay.isoformat(),income=flows[0]/100,spent=flows[1]/100,
            expected_income=pending_amount_cents(db,start.isoformat(),end.isoformat())/100,bills_before_payday=before_pay/100),
        closing=dict(db.execute('SELECT id,month,created_at FROM budget_month_closings WHERE month=?',(month,)).fetchone() or {}))
