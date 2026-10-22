"""Read-only daily forecast of budget cash and earmarks, without market returns."""
import calendar
import math
import re
from collections import defaultdict
from datetime import date, timedelta

from api.exceptions import ValidationError
from database import get_db
from routes_budget_workspace import cents
from expected_income_service import items as income_items, is_received, months, occurrences
from budget_reserves_service import _balance, _next_year, plan, reserved_cents
from budget_planning_service import settings as planning_settings,shift_month,payday
from budget_bill_schedule import due_in_month,due_date,amount_cents as bill_amount
from investment_goals_service import _available, _portfolios, _scope
from loan_service import LoanService

LABELS={'INCOME':'Dochody','BILL':'Rachunki','LOAN':'Raty','DAILY':'Codzienne wydatki',
    'REFUND':'Zwroty zakupów',
    'GOAL':'Wpłaty do inwestycji','RESERVE_ADD':'Odłożenia na rezerwy','RESERVE_COST':'Koszty rezerw',
    'EXPENSE':'Inne zapisane wydatki','TRANSFER_IN':'Powroty z inwestycji','ADJUSTMENT':'Zapisane korekty'}


def _int(value,label,low,high):
    try:
        if isinstance(value,bool) or str(int(value))!=str(value):raise ValueError()
        result=int(value)
    except (ValueError,TypeError,OverflowError):raise ValidationError(f'{label}: podaj liczbę całkowitą.') from None
    if not low<=result<=high:raise ValidationError(f'{label}: zakres od {low} do {high}.')
    return result


def _monthly_day(year,month,anchor):
    return date(year,month,min(anchor,calendar.monthrange(year,month)[1]))


def workspace(options=None):
    options=options or {}
    percent=_int(options.get('income_percent',100),'Procent dochodów',0,200)
    buffer=cents(options.get('buffer',0),'Bufor bezpieczeństwa',allow_zero=True)
    variable_override=cents(options['variable_monthly'],'Codzienne wydatki',allow_zero=True) if options.get('variable_monthly') not in (None,'') else None
    excluded_raw=options.get('excluded','')
    if not isinstance(excluded_raw,str) or len(excluded_raw)>10000:raise ValidationError('Nieprawidłowa lista pominięć.')
    excluded=set(filter(None,excluded_raw.split(',')))
    if any(not re.fullmatch(r'(income|bill|loan|goal|reserve|bond):[1-9]\d{0,9}',key) for key in excluded):
        raise ValidationError('Nieprawidłowe źródło prognozy.')
    db,today=get_db(),date.today()
    end=today+timedelta(days=365)
    tomorrow=today+timedelta(days=1)
    warnings,events,sources=[],[],[]
    accounts=[dict(r) for r in db.execute("SELECT id,name,balance,account_type FROM budget_accounts WHERE UPPER(COALESCE(currency,'PLN'))='PLN' ORDER BY id")]
    card_ids={a['id'] for a in accounts if a['account_type']=='CREDIT_CARD'}
    if card_ids:
        warnings.append('Suma sald i wolne środki uwzględniają zadłużenie kart tylko raz. Saldo ujemne karty to dług, nie brak środków na rezerwy. Prognoza nie zakłada terminu spłaty karty; po wykonaniu zapisz przelew z konta bankowego. Przelew nie zmieni sumy sald ani wydatków.')
    configuration=planning_settings(db)
    account_cash={a['id']:round(float(a['balance'])*100) for a in accounts}
    account_reserved={a['id']:reserved_cents(db,a['id'],through=today.isoformat()) for a in accounts}
    if not accounts:warnings.append('Dodaj konta z aktualnymi saldami. Bez nich pokazujemy plan przepływów, ale nie wyliczamy salda końcowego.')
    if db.execute("SELECT 1 FROM budget_accounts WHERE UPPER(COALESCE(currency,'PLN'))!='PLN'").fetchone():
        warnings.append('Prognoza sumuje wyłącznie konta budżetowe w PLN.')
    opening=sum(round(float(a['balance'])*100) for a in accounts)
    opening_reserved=reserved_cents(db,through=today.isoformat())

    def add(key,day,kind,title,amount,cash,reserved=0,href='/budget',detail='',recorded=False,account_id=None,reserved_by_account=None):
        projected=max(day,tomorrow.isoformat())
        if projected<=end.isoformat():
            account_id=account_id or configuration['resolved_spending_account_id']
            reserved_by_account=reserved_by_account if reserved_by_account is not None else ({account_id:reserved} if reserved and account_id else {})
            events.append(dict(key=key,date=projected,scheduled_date=day,kind=kind,title=title,amount=amount,
                cash_delta=cash,reserved_delta=reserved,href=href,detail=detail,recorded=recorded,account_id=account_id,
                account_name=next((a['name'] for a in accounts if a['id']==account_id),None),reserved_by_account=reserved_by_account))

    def source(key,kind,name,amount,href):
        sources.append(dict(key=key,kind=kind,name=name,amount=amount/100,href=href,included=key not in excluded))
        return key not in excluded

    # Include bond payouts only when the user explicitly plans a transfer to
    # a specific budget account. Accrual/capitalization alone never adds cash.
    from bond_service import BondService
    for p in db.execute("SELECT id FROM portfolios WHERE account_type='BONDS' AND is_archived=0 AND parent_portfolio_id IS NULL"):
        bond_workspace=BondService.workspace(p['id'])
        for bond in bond_workspace['items']:
            if not bond['forecast_enabled'] or not bond['remaining_quantity'] or bond['status']=='VOID':continue
            href=f"/portfolio/{p['id']}?bond={bond['id']}"
            if bond['payout_account_id'] not in account_cash:
                warnings.append(f"{bond['name']}: konto wypłat jest niedostępne; prognozę pominięto.");continue
            planned=[e for e in bond_workspace['events'] if e['bond_id']==bond['id'] and e['kind']!='CAPITALIZATION' and today.isoformat()<e['date']<=end.isoformat()]
            total=sum(round(e['net_amount']*100) for e in planned)
            if not source(f"bond:{bond['id']}",'TRANSFER_IN',bond['name']+' · plan wypłat',total,href):continue
            if bond['warnings']:warnings.append(f"{bond['name']}: plan wypłat korzysta z niepotwierdzonego oprocentowania.")
            for event in planned:
                value=round(event['net_amount']*100)
                if value:add(event['key'],event['date'],'TRANSFER_IN',bond['name']+' · '+('wykup' if event['kind']=='MATURITY' else 'odsetki'),value,value,
                    href=href,account_id=bond['payout_account_id'],detail='Szacunek netto i plan transferu z inwestycji; saldo zmieni się dopiero po zapisie faktycznej wypłaty')

    # Balances already contain every booked entry. Undo all future-dated entries
    # before projecting them once on their dates, including dates beyond one year.
    for row in db.execute('''SELECT e.* FROM budget_entries_v2 e JOIN budget_accounts a ON a.id=e.account_id
        WHERE e.date>? AND e.cash_effect=1 AND UPPER(COALESCE(a.currency,'PLN'))='PLN' ''',(today.isoformat(),)):
        delta=row['amount_cents'] if row['kind']=='INCOME' else -row['amount_cents']
        opening-=delta
        account_cash[row['account_id']]-=delta
        kind='REFUND' if db.execute('SELECT 1 FROM budget_purchase_refunds WHERE entry_id=?',(row['id'],)).fetchone() else 'INCOME' if delta>0 else 'BILL' if db.execute('SELECT 1 FROM budget_bill_payments_v2 WHERE entry_id=?',(row['id'],)).fetchone() else 'EXPENSE'
        add(f'entry:{row["id"]}',row['date'],kind,row['description'],abs(delta),delta,
            detail='Już zapisany wpis z przyszłą datą',recorded=True,account_id=row['account_id'])
    for row in db.execute('''SELECT t.* FROM budget_investment_transfers t JOIN budget_accounts a ON a.id=t.account_id
        WHERE t.date>? AND UPPER(COALESCE(a.currency,'PLN'))='PLN' ''',(today.isoformat(),)):
        delta=row['amount_cents'] if row['direction']=='IN' else -row['amount_cents']
        opening-=delta
        account_cash[row['account_id']]-=delta
        add(f'transfer:{row["id"]}',row['date'],'TRANSFER_IN' if delta>0 else 'GOAL','Zapisany transfer inwestycyjny',abs(delta),delta,
            href='/portfolios',detail='Już zapisany transfer z przyszłą datą',recorded=True,account_id=row['account_id'])
    for row in db.execute("SELECT * FROM budget_account_reconciliations WHERE date>? AND record_type='RECONCILIATION'",(today.isoformat(),)):
        if row['account_id'] not in account_cash:continue
        opening-=row['difference_cents']
        if row['account_id'] in account_cash: account_cash[row['account_id']]-=row['difference_cents']
        add(f'adjustment:{row["id"]}',row['date'],'ADJUSTMENT','Zapisana korekta salda',abs(row['difference_cents']),row['difference_cents'],
            href='/budget/accounts',recorded=True,account_id=row['account_id'])
    if events:warnings.append('W bazie są wpisy z przyszłą datą. Cofnięto je z salda startowego i uwzględniono raz w dniu ich zapisu.')

    incomes=income_items(db,today,end.isoformat())
    received={(r['income_id'],r['occurrence_date']) for r in db.execute('SELECT income_id,occurrence_date FROM budget_expected_income_receipts')}
    for row in db.execute('''SELECT i.* FROM budget_expected_incomes i JOIN budget_accounts a ON a.id=i.account_id
        WHERE i.active=1 AND UPPER(COALESCE(a.currency,'PLN'))='PLN' '''):
        if not source(f'income:{row["id"]}','INCOME',row['name'],row['amount_cents'],'/budget/forecast'):continue
        if any(i['id']==row['id'] and i['overdue'] for i in incomes):
            warnings.append(f'{row["name"]}: miniony wpływ bez potwierdzenia nie jest doliczany do przyszłych dochodów.')
        for day in occurrences(row,today.isoformat(),end.isoformat()):
            if is_received(row,day,received):continue
            amount=(row['amount_cents']*percent+50)//100
            if amount:add(f'income:{row["id"]}:{day}',day,'INCOME',row['name'],amount,amount,detail=f'{percent}% planowanej kwoty',account_id=row['account_id'])
    if not any(s['kind']=='INCOME' and s['included'] for s in sources):warnings.append('Brak aktywnych oczekiwanych dochodów. Prognoza nie zakłada automatycznie przyszłej pensji.')

    paid_bills={(r['bill_id'],r['month']) for r in db.execute('SELECT bill_id,month FROM budget_bill_payments_v2')}
    bills=[dict(r) for r in db.execute('''SELECT b.* FROM budget_bills_v2 b JOIN budget_accounts a ON a.id=b.account_id
        WHERE UPPER(COALESCE(a.currency,'PLN'))='PLN' ''')]
    overdue=0
    for row in bills:
        if not row['active']:continue
        if not source(f'bill:{row["id"]}','BILL',row['title'],row['amount_cents'],'/budget?view=bills'):continue
        first=row['due_month'] if row['frequency']=='ONCE' else max(row['start_month'] or today.strftime('%Y-%m'),today.strftime('%Y-%m'))
        last=row['due_month'] if row['frequency']=='ONCE' else end.strftime('%Y-%m')
        for year,month in months(first,last):
            occurrence=f'{year:04d}-{month:02d}'
            if not due_in_month(row,occurrence) or (row['id'],occurrence) in paid_bills:continue
            due=_monthly_day(year,month,row['due_day']).isoformat()
            if due<today.isoformat():overdue+=1
            if row['reserve_id']:continue # Its reserve supplies the single payment event below.
            amount=bill_amount(row,occurrence)
            add(f'bill:{row["id"]}:{occurrence}',due,'BILL',row['title'],amount,-amount,
                href=f'/budget?view=bills&month={occurrence}',detail='Szacunkowa kwota' if row['variable_amount'] else 'Rachunek bez zapisu płatności',account_id=row['account_id'])
    if overdue:warnings.append(f'Nieopłacone rachunki z minionym terminem: {overdue}. Przyjęto płatność jutro; sprawdź, czy nie zostały już opłacone.')

    loan_fixed=defaultdict(lambda:defaultdict(int))
    paid_loans={(r['loan_id'],r['installment_month']) for r in db.execute('SELECT loan_id,installment_month FROM loan_installment_payments')}
    old_loans,current_overdue=0,0
    for loan_row in db.execute('''SELECT id,name,original_amount,duration_months,CAST(start_date AS TEXT) start_date,installment_type FROM loans'''):
        loan=dict(loan_row)
        from loan_budget_service import settings as loan_budget_settings
        loan_budget=loan_budget_settings(db,loan['id'])
        included=source(f'loan:{loan["id"]}','LOAN',loan['name'],0,f'/loans/{loan["id"]}')
        rates=LoanService.get_loan_rates(loan['id'])
        try:
            if not rates:raise ValueError('missing rates')
            schedule,_,_=LoanService.calculate_schedule(loan,rates,LoanService.get_loan_overpayments(loan['id']))
            for row in schedule:
                if row['installment']<=0 or row.get('is_mid_month'):continue
                if not math.isfinite(row['installment']):raise ValueError('invalid installment')
                amount=round(row['installment']*100)
                if loan_budget['category_id'] is not None:loan_fixed[row['date'][:7]][loan_budget['category_id']]+=amount
                if (loan['id'],row['month']) in paid_loans:continue
                if row['date']<today.strftime('%Y-%m')+'-01':old_loans+=1;continue
                if included:
                    if row['date']<today.isoformat():current_overdue+=1
                    add(f'loan:{loan["id"]}:{row["month"]}',row['date'],'LOAN',loan['name'],amount,-amount,
                        href=f'/loans/{loan["id"]}',detail='Rata według zapisanego oprocentowania; konto przypisane do kredytu',account_id=loan_budget['resolved_account_id'])
        except (ValueError,TypeError,IndexError,ZeroDivisionError,OverflowError):
            warnings.append(f'{loan["name"]}: brak pełnego harmonogramu lub oprocentowania. Raty tego kredytu mogą być niepełne w prognozie.')
    if old_loans:warnings.append(f'Starsze raty bez zapisu spłaty: {old_loans}. Nie doliczamy ich automatycznie; sprawdź historię kredytów.')
    if current_overdue:warnings.append(f'Raty z bieżącego miesiąca po terminie: {current_overdue}. Przyjęto płatność jutro, jeśli nie ma zapisu spłaty.')

    # Contributions earmark existing cash; the expense at the deadline consumes
    # cash and releases the corresponding earmark. Annual cycles stay separate.
    purchase_override=None
    if options.get('purchase_id') not in (None,''):
        purchase_id=_int(options['purchase_id'],'Plan zakupu',1,9999999999)
        purchase_override=db.execute("SELECT * FROM budget_purchase_plans WHERE id=? AND status='PLANNED'",(purchase_id,)).fetchone()
        if not purchase_override or not purchase_override['reserve_id']:raise ValidationError('Wybierz zaplanowany zakup z rezerwą.')
        if not db.execute('SELECT 1 FROM budget_reserves WHERE id=? AND is_archived=0 AND completed_at IS NULL',(purchase_override['reserve_id'],)).fetchone():
            raise ValidationError('Rezerwa tego zakupu jest zakończona lub wstrzymana.')
        if options.get('purchase_amount') not in (None,''):cents(options['purchase_amount'],'Kwota wariantu')
        if options.get('purchase_date'):
            from budget_reserves_service import _date
            if _date(options['purchase_date'],'Termin wariantu')<today.isoformat():raise ValidationError('Wariant zakupu musi dotyczyć dzisiaj lub przyszłości.')
    month_targets={(r['reserve_id'],r['month']):r['amount_cents'] for r in db.execute('SELECT * FROM budget_reserve_month_plans')}
    from budget_planning_service import reserve_plans
    for row in reserve_plans(db,today.strftime('%Y-%m')):
        month_targets[(row['reserve_id'],today.strftime('%Y-%m'))]=round(row['planned']*100)
    actual_funding={(r['reserve_id'],r['month']):r['amount'] for r in db.execute('''SELECT reserve_id,substr(date,1,7) month,
        SUM(CASE WHEN kind='ADD' THEN amount_cents WHEN kind='RELEASE' THEN -amount_cents ELSE 0 END) amount
        FROM budget_reserve_movements GROUP BY reserve_id,substr(date,1,7)''')}
    reserve_count=0
    for reserve in db.execute('SELECT * FROM budget_reserves WHERE is_archived=0 AND completed_at IS NULL'):
        reserve=dict(reserve)
        if reserve['account_id'] not in account_cash:continue
        linked=next((b for b in bills if b['active'] and b['reserve_id']==reserve['id']),None)
        if linked and f'bill:{linked["id"]}' in excluded:continue
        if purchase_override and purchase_override['reserve_id']==reserve['id']:
            if options.get('purchase_amount') not in (None,''):reserve['target_cents']=cents(options['purchase_amount'],'Kwota wariantu')
            if options.get('purchase_date'):reserve['due_date']=options['purchase_date']
        if reserve['monthly_amount_cents'] is not None:
            href=f'/budget/reserves?reserve={reserve["id"]}'
            if not source(f'reserve:{reserve["id"]}','RESERVE_ADD',reserve['name'],reserve['monthly_amount_cents'],href):continue
            from budget_reserves_service import locations
            reserve_locations={r['account_id']:round(r['amount']*100) for r in locations(db,reserve['id'])}
            operations=[]
            from budget_media_service import allocated_cents
            for year,month in months(today.isoformat(),end.isoformat()):
                period=f'{year:04d}-{month:02d}'
                target=reserve['monthly_amount_cents'] if reserve['open_ended'] else month_targets.get((reserve['id'],period),reserve['monthly_amount_cents'])
                contribution=0 if period<(reserve['monthly_start_month'] or reserve['start_date'][:7]) else max(0,target-max(0,actual_funding.get((reserve['id'],period),0) if reserve['open_ended'] else allocated_cents(db,reserve,period)))
                scheduled=max(today.isoformat(),_monthly_day(year,month,configuration['resolved_pay_day']).isoformat())
                if contribution:operations.append((scheduled,0,period,contribution))
                if linked and due_in_month(linked,period) and (linked['id'],period) not in paid_bills:
                    operations.append((max(today.isoformat(),due_date(linked,period)),1,period,bill_amount(linked,period)))
            for scheduled,kind,period,amount in sorted(operations):
                if scheduled>end.isoformat():continue
                if kind==0:
                    add(f'reserve-add:{reserve["id"]}:{period}',scheduled,'RESERVE_ADD',reserve['name'],amount,0,amount,
                        href=href,detail='Stała miesięczna wpłata bez terminu' if reserve['open_ended'] else 'Miesięczna pula; korekta dotyczy tylko wybranego miesiąca',account_id=reserve['account_id'])
                    reserve_locations[reserve['account_id']]=reserve_locations.get(reserve['account_id'],0)+amount
                else:
                    left=min(sum(reserve_locations.values()),amount);released=left;releases={}
                    for location_id in sorted(reserve_locations,key=lambda account_id:account_id!=linked['account_id']):
                        used=min(reserve_locations[location_id],left)
                        if used:releases[location_id]=-used;reserve_locations[location_id]-=used;left-=used
                    add(f'reserve-cost:{reserve["id"]}:{period}',scheduled,'RESERVE_COST',linked['title'],amount,-amount,-released,
                        href='/budget?view=bills',detail='Faktura finansowana z miesięcznej puli',account_id=linked['account_id'],reserved_by_account=releases)
            continue
        if not source(f'reserve:{reserve["id"]}','RESERVE_COST',reserve['name'],reserve['target_cents'],f'/budget/reserves?reserve={reserve["id"]}'):continue
        reserve_count+=1
        saved=_balance(db,reserve['id']);start,due=reserve['start_date'],reserve['due_date']
        from budget_reserves_service import locations
        reserve_locations={r['account_id']:round(r['amount']*100) for r in locations(db,reserve['id'])}
        payment_account=linked['account_id'] if linked else reserve['account_id']
        def saving_amount(scheduled,monthly):
            key=(reserve['id'],scheduled[:7])
            return min(max(0,reserve['target_cents']-saved),max(0,month_targets[key]-max(0,actual_funding.get(key,0))) if key in month_targets else monthly)
        def saving_first(first,cursor):
            key=(reserve['id'],cursor.strftime('%Y-%m'))
            if key in month_targets and month_targets[key]>max(0,actual_funding.get(key,0)):
                return min(first or due,max(cursor.isoformat(),start))
            return first
        funded=db.execute('''SELECT COALESCE(SUM(CASE WHEN kind='ADD' THEN amount_cents WHEN kind='RELEASE' THEN -amount_cents ELSE 0 END),0)
            FROM budget_reserve_movements WHERE reserve_id=? AND cycle=? AND substr(date,1,7)=?''',(reserve['id'],reserve['cycle'],today.strftime('%Y-%m'))).fetchone()[0]>0
        cycle=reserve['cycle'];cursor=today
        while due<=end.isoformat():
            saving_plan=plan(reserve['target_cents'],saved,start,due,cursor,funded)
            first=saving_first(saving_plan['next_contribution_date'],cursor)
            monthly=round(saving_plan['monthly_required']*100)
            if first:
                for year,month in months(first,due):
                    scheduled=max(first,_monthly_day(year,month,date.fromisoformat(start).day).isoformat())
                    if scheduled>=due:continue
                    amount=saving_amount(scheduled,monthly)
                    if amount:
                        add(f'reserve-add:{reserve["id"]}:{cycle}:{scheduled}',scheduled,'RESERVE_ADD',reserve['name'],amount,0,amount,
                            href=f'/budget/reserves?reserve={reserve["id"]}',detail='Wydzielenie środków; saldo kont pozostaje bez zmian',account_id=reserve['account_id'])
                        saved+=amount
                        reserve_locations[reserve['account_id']]=reserve_locations.get(reserve['account_id'],0)+amount
            used=saved if reserve['frequency']=='ONCE' else min(saved,reserve['target_cents'])
            releases={};left=used
            for location_id in sorted(reserve_locations,key=lambda account_id:account_id!=payment_account):
                release=min(reserve_locations[location_id],left)
                if release:releases[location_id]=-release;reserve_locations[location_id]-=release;left-=release
            add(f'reserve-cost:{reserve["id"]}:{cycle}',due,'RESERVE_COST',reserve['name'],reserve['target_cents'],-reserve['target_cents'],-used,
                href=f'/budget/reserves?reserve={reserve["id"]}',detail='Planowana płatność; zwolnienie odłożonych środków',account_id=payment_account,reserved_by_account=releases)
            saved-=used
            if reserve['frequency']=='ONCE':break
            paid=max(date.fromisoformat(due),today)
            due=_next_year(dict(reserve,due_date=due),paid);start=paid.isoformat();cursor=paid;funded=False;cycle+=1
        # A deadline beyond this horizon still needs monthly saving now.
        if due>end.isoformat() and reserve['frequency'] in ('ONCE','YEARLY'):
            saving_plan=plan(reserve['target_cents'],saved,start,due,cursor,funded)
            first=saving_first(saving_plan['next_contribution_date'],cursor)
            monthly=round(saving_plan['monthly_required']*100)
            if first:
                for year,month in months(first,end.isoformat()):
                    scheduled=max(first,_monthly_day(year,month,date.fromisoformat(start).day).isoformat())
                    amount=saving_amount(scheduled,monthly)
                    if amount and scheduled<=end.isoformat():
                        add(f'reserve-add:{reserve["id"]}:{cycle}:{scheduled}',scheduled,'RESERVE_ADD',reserve['name'],amount,0,amount,
                            href=f'/budget/reserves?reserve={reserve["id"]}',detail='Wydzielenie środków; saldo kont pozostaje bez zmian',account_id=reserve['account_id'])
                        saved+=amount

    # Goals describing overlapping portfolios share the same capital. Use the
    # largest monthly plan for a connected group, rather than summing it twice.
    portfolios=_portfolios();groups=[]
    for row in db.execute('SELECT * FROM investment_goals WHERE is_archived=0 AND target_date>=?',(today.isoformat(),)):
        amount=round(row['monthly_contribution']*100)
        if not source(f'goal:{row["id"]}','GOAL',row['name'],amount,f'/goals?goal={row["id"]}') or not amount:continue
        scope=set()
        for p in db.execute('SELECT portfolio_id FROM investment_goal_portfolios WHERE goal_id=?',(row['id'],)):
            if p[0] in portfolios and _available(portfolios[p[0]],portfolios):scope.update(_scope(p[0],portfolios))
        if not scope:warnings.append(f'{row["name"]}: brak aktywnego portfela; wpłaty na ten cel pominięto.');continue
        joined=[g for g in groups if g['scope']&scope]
        combined=dict(scope=set(scope),goals=[dict(row)])
        for g in joined:combined['scope'].update(g['scope']);combined['goals'].extend(g['goals']);groups.remove(g)
        groups.append(combined)
    for group in groups:
        if len(group['goals'])>1:warnings.append('Cele ze wspólnymi portfelami: '+', '.join(g['name'] for g in group['goals'])+'. Liczymy jeden wspólny plan według największej miesięcznej wpłaty.')
        for year,month in months(today.isoformat(),end.isoformat()):
            beginning=f'{year:04d}-{month:02d}-01';last=_monthly_day(year,month,31).isoformat()
            active=[g for g in group['goals'] if g['target_date']>=beginning]
            if not active:continue
            target=max(round(g['monthly_contribution']*100) for g in active)
            day=min([last]+[g['target_date'] for g in active])
            if day<today.isoformat():continue
            placeholders=','.join('?' for _ in group['scope'])
            funded=db.execute(f'''SELECT COALESCE(SUM(CASE WHEN direction='OUT' THEN amount_cents ELSE -amount_cents END),0)
                FROM budget_investment_transfers t JOIN budget_accounts a ON a.id=t.account_id
                WHERE portfolio_id IN ({placeholders}) AND substr(date,1,7)=? AND UPPER(COALESCE(a.currency,'PLN'))='PLN' ''',(*sorted(group['scope']),beginning[:7])).fetchone()[0]
            amount=max(0,target-max(0,funded))
            if amount:add(f'goal:{min(g["id"] for g in active)}:{beginning[:7]}',day,'GOAL',', '.join(g['name'] for g in active),amount,-amount,
                href='/goals',detail='Pozostała miesięczna wpłata; termin na koniec miesiąca lub termin celu')

    # Default ordinary spending = manual category limits less fixed bills and
    # loan installments in their assigned categories. Users can override it.
    from budget_category_hierarchy_service import category_options, plan_amounts
    options = category_options(db)
    roots = {c['id']: c['parent_id'] or c['id'] for c in options}
    from budget_default_plan_service import resolve
    plan_bases={}
    variable_cache={}
    def variable_plan(month):
        if month in variable_cache:return variable_cache[month]
        manual,provenance=resolve(db,month,today.strftime('%Y-%m'))
        fixed=defaultdict(int)
        for bill in bills:
            if due_in_month(bill,month) and (bill['active'] or (bill['id'],month) in paid_bills):
                from budget_bill_funding import occurrence
                value=occurrence(db,bill,month)
                if value['media']:continue
                fixed[bill['category_id']]+=value['amount_cents']
        from budget_media_service import category_targets
        for category_id,amount in category_targets(db,month).items():
            fixed[category_id]+=amount
            manual[category_id]=0
            provenance[category_id]=dict(kind='MEDIA',month=month)
        for category_id,amount in loan_fixed[month].items():fixed[category_id]+=amount
        effective=plan_amounts(options, manual, fixed)
        if month==today.strftime('%Y-%m'):
            from budget_rollover_service import carries
            for category_id,amount in carries(db,month,options).items():effective[category_id]+=amount
        result={c['id']:max(0,effective[c['id']]-sum(amount for category_id,amount in fixed.items() if roots.get(category_id)==c['id']))
                   for c in options if c['parent_id'] is None}
        plan_bases[month]=dict(month=month,ordinary_limit=sum(result.values())/100,
            categories=[dict(category_id=c['id'],name=c['path'],amount=manual.get(c['id'],0)/100,
                source=provenance.get(c['id'],{}).get('kind','NONE'),source_month=provenance.get(c['id'],{}).get('month'))
                for c in options if not c['is_unassigned']])
        variable_cache[month]=result
        return result
    default_variable=sum(variable_plan(today.strftime('%Y-%m')).values())
    # Each root owns its allowance. Spending without a cap, or a root overrun,
    # must not cancel money still planned in other categories. Media and linked
    # obligations have their own forecast events and cannot consume shopping.
    variable_spending=defaultdict(lambda:defaultdict(int))
    media_categories={}
    for entry in db.execute('''SELECT e.date,e.kind,l.category_id,l.amount_cents,r.purchase_entry_id
        FROM budget_entries_v2 e JOIN budget_accounts a ON a.id=e.account_id
        JOIN budget_entry_lines_v2 l ON l.entry_id=e.id
        LEFT JOIN budget_purchase_refunds r ON r.entry_id=e.id
        WHERE e.date BETWEEN ? AND ? AND (e.kind='EXPENSE' OR r.entry_id IS NOT NULL)
        AND UPPER(COALESCE(a.currency,'PLN'))='PLN'
        AND NOT EXISTS(SELECT 1 FROM budget_bill_payments_v2 b WHERE b.entry_id=COALESCE(r.purchase_entry_id,e.id))
        AND NOT EXISTS(SELECT 1 FROM loan_installment_payments p WHERE p.budget_entry_id=COALESCE(r.purchase_entry_id,e.id))
        AND NOT EXISTS(SELECT 1 FROM loan_overpayments o WHERE o.budget_entry_id=COALESCE(r.purchase_entry_id,e.id))
        AND NOT EXISTS(SELECT 1 FROM budget_reserve_movements m WHERE m.budget_entry_id=COALESCE(r.purchase_entry_id,e.id))''',
        (today.strftime('%Y-%m')+'-01',end.isoformat())):
        period=entry['date'][:7]
        if period not in media_categories:
            from budget_media_service import category_targets
            media_categories[period]=set(category_targets(db,period))
        if entry['category_id'] not in media_categories[period]:
            variable_spending[period][roots[entry['category_id']]]+=entry['amount_cents']*(-1 if entry['purchase_entry_id'] else 1)
    for year,month in months(tomorrow.isoformat(),end.isoformat()):
        month_key=f'{year:04d}-{month:02d}'
        if variable_override is not None:
            remaining=max(0,variable_override-sum(variable_spending[month_key].values()))
        else:
            remaining=sum(max(0,amount-variable_spending[month_key].get(root,0)) for root,amount in variable_plan(month_key).items())
        first=max(tomorrow,date(year,month,1));last=date(year,month,calendar.monthrange(year,month)[1])
        count=(last-first).days+1
        per_day,extra=divmod(remaining,count)
        for offset in range(count):
            day=(first+timedelta(days=offset)).isoformat();amount=per_day+(1 if offset<extra else 0)
            if amount:add(f'daily:{day}',day,'DAILY','Codzienne wydatki',amount,-amount,detail='Pozostały miesięczny limit rozłożony równo na dni')
    if variable_override is None and default_variable==0:warnings.append('Nie ma planu codziennych wydatków. Ustaw miesięczną kwotę poza rachunkami, ratami i kosztami rezerw.')
    if reserve_count and default_variable>0 and variable_override is None:warnings.append('Sprawdź limit codziennych wydatków: koszty rezerw nie mają przypisanej kategorii planu, więc nie możemy automatycznie wyłączyć ich z limitów kategorii.')
    if variable_override is None and any(c['source']=='ESTIMATE' for row in plan_bases.values() for c in row['categories']):
        warnings.append('Część przyszłych limitów jest szacunkiem z bieżącego miesiąca. Ustaw plan domyślny lub miesięczne wyjątki, aby prognoza miała stałą podstawę.')
    if any(s['kind']=='BILL' for s in sources) and any(s['kind'] in ('LOAN','RESERVE_COST') for s in sources):
        warnings.append('Jeśli ten sam koszt jest zapisany jako rachunek i rata lub rezerwa, wyłącz jedno źródło w prognozie.')
    events.sort(key=lambda e:(e['date'],e['key']))
    by_day=defaultdict(list)
    for event in events:by_day[event['date']].append(event)
    cash,earmarked=opening,opening_reserved
    points=[dict(date=today.isoformat(),balance=cash/100,reserved=earmarked/100,available=(cash-earmarked)/100)]
    account_points={a['id']:[dict(date=today.isoformat(),balance=account_cash[a['id']]/100,reserved=account_reserved[a['id']]/100,
        available=(account_cash[a['id']]-account_reserved[a['id']])/100)] for a in accounts}
    for offset in range(1,366):
        day=(today+timedelta(days=offset)).isoformat()
        for event in by_day[day]:
            cash+=event['cash_delta'];earmarked+=event['reserved_delta']
            if event['account_id'] in account_cash:account_cash[event['account_id']]+=event['cash_delta']
            for account_id,delta in event['reserved_by_account'].items():
                if account_id in account_reserved:account_reserved[account_id]+=delta
        points.append(dict(date=day,balance=cash/100,reserved=earmarked/100,available=(cash-earmarked)/100))
        for account_id in account_points:
            account_points[account_id].append(dict(date=day,balance=account_cash[account_id]/100,reserved=account_reserved[account_id]/100,
                available=(account_cash[account_id]-account_reserved[account_id])/100))
    summaries=[]
    for days in (30,90,365):
        window=points[:days+1];finish=window[-1]
        totals={kind:sum(e['amount'] for e in events if e['date']<=finish['date'] and e['kind']==kind)/100 for kind in LABELS}
        low=min(window,key=lambda p:p['available']);low_cash=min(window,key=lambda p:p['balance'])
        summaries.append(dict(days=days,date=finish['date'],balance=finish['balance'] if accounts else None,available=finish['available'] if accounts else None,
            reserved=finish['reserved'],minimum=low['available'] if accounts else None,minimum_date=low['date'],minimum_balance=low_cash['balance'] if accounts else None,
            first_shortfall=next((p['date'] for p in window if p['available']<0),None) if accounts else None,
            first_below_buffer=next((p['date'] for p in window if round(p['available']*100)<buffer),None) if accounts else None,totals=totals))
    account_forecasts=[]
    for account in accounts:
        trajectory=account_points[account['id']]
        account_forecasts.append(dict(id=account['id'],name=account['name'],account_type=account['account_type'],opening=trajectory[0],points=trajectory,
            summaries=[dict(days=n,date=trajectory[n]['date'],balance=trajectory[n]['balance'],reserved=trajectory[n]['reserved'],available=trajectory[n]['available'],
                minimum=min(p['available'] for p in trajectory[:n+1]),first_shortfall=None if account['id'] in card_ids else next((p['date'] for p in trajectory[:n+1] if p['available']<0),None)) for n in (30,90,365)]))
    donors={a['id']:0 if a['id'] in card_ids else max(0,round(min(p['available'] for p in account_points[a['id']][:31])*100)) for a in accounts}
    transfer_suggestions=[]
    for target in account_forecasts:
        shortfall=target['summaries'][0]['first_shortfall']
        if not shortfall:continue
        needed=max(0,-round(target['summaries'][0]['minimum']*100))
        for donor in accounts:
            if donor['id']==target['id'] or not donors[donor['id']]:continue
            amount=min(needed,donors[donor['id']]);needed-=amount;donors[donor['id']]-=amount
            if amount:transfer_suggestions.append(dict(source_account_id=donor['id'],source_name=donor['name'],target_account_id=target['id'],target_name=target['name'],
                amount=amount/100,by_date=max(today,date.fromisoformat(shortfall)-timedelta(days=1)).isoformat(),reason='Pokrycie przewidywanego braku pieniędzy poza rezerwami; sugestia nie wykonuje przelewu'))
            if not needed:break
        if needed:warnings.append(f'{target["name"]}: brak {needed/100:.2f} PLN w planie na 30 dni, którego nie pokrywają wolne środki innych kont.')
    next_pay=payday(today.strftime('%Y-%m'),configuration['resolved_pay_day'])
    if next_pay<=today:next_pay=payday(shift_month(today.strftime('%Y-%m'),1),configuration['resolved_pay_day'])
    wage=[e['date'] for e in events if e['kind']=='INCOME' and e['key'].startswith(f'income:{configuration["resolved_income_id"]}:')]
    if wage:next_pay=date.fromisoformat(min(wage))
    days=max(0,min(365,(next_pay-today).days-1));window=points[:days+1]
    before_income=dict(next_payday=next_pay.isoformat(),through=window[-1]['date'],minimum=min(p['available'] for p in window),
        must_pay=sum(e['amount'] for e in events if e['date']<next_pay.isoformat() and e['kind'] in ('BILL','LOAN','RESERVE_COST'))/100,
        balance=window[-1]['balance'],available=window[-1]['available'])
    month_plans=[]
    for period,row in sorted(plan_bases.items()):
        totals=defaultdict(int)
        for event in events:
            if event['scheduled_date'][:7]==period and not event['recorded']:
                totals[event['kind']]+=event['amount']
        month_plans.append({**row,'ordinary_limit':variable_override/100 if variable_override is not None else row['ordinary_limit'],
            'scenario':variable_override is not None,'ordinary_remaining':totals['DAILY']/100,
            'income':totals['INCOME']/100,'bills':totals['BILL']/100,'loans':totals['LOAN']/100,
            'reserves':totals['RESERVE_ADD']/100,'reserve_payments':totals['RESERVE_COST']/100,'investments':totals['GOAL']/100})
    return dict(as_of=today.isoformat(),end_date=end.isoformat(),accounts=accounts,month_plans=month_plans,opening=dict(balance=opening/100,reserved=opening_reserved/100,available=(opening-opening_reserved)/100),
        account_forecasts=account_forecasts,transfer_suggestions=transfer_suggestions,before_income=before_income,planning_settings=configuration,
        options=dict(income_percent=percent,buffer=buffer/100,variable_monthly=variable_override/100 if variable_override is not None else None,
            default_variable_monthly=default_variable/100,excluded=sorted(excluded)),points=points,summaries=summaries,
        events=[{**e,**{k:e[k]/100 for k in ('amount','cash_delta','reserved_delta')},'reserved_by_account':{k:v/100 for k,v in e['reserved_by_account'].items()}} for e in events],sources=sources,incomes=incomes,
        recent_incomes=[dict(r) for r in db.execute('''SELECT e.id,e.account_id,e.date,e.description,e.amount_cents/100.0 amount FROM budget_entries_v2 e
            JOIN budget_accounts a ON a.id=e.account_id WHERE e.kind='INCOME' AND e.date<=? AND UPPER(COALESCE(a.currency,'PLN'))='PLN'
            AND NOT EXISTS(SELECT 1 FROM budget_expected_income_receipts r WHERE r.budget_entry_id=e.id)
            AND NOT EXISTS(SELECT 1 FROM budget_purchase_refunds r WHERE r.entry_id=e.id) ORDER BY e.date DESC,e.id DESC LIMIT 100''',(today.isoformat(),))],
        warnings=list(dict.fromkeys(warnings)))
