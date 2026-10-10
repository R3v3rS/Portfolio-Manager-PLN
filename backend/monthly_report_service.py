"""A read-only monthly review of recorded finances. Never fetch or book data."""
import calendar
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from api.exceptions import ValidationError
from database import get_db
from loan_service import LoanService
from actual_results_service import analyze
from budget_summary_service import reserve_budget_costs
from budget_category_hierarchy_service import category_workspace


def report_period(month=None):
    today = date.today()
    if month is None:
        month = (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    if not isinstance(month, str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
        raise ValidationError('Wybierz miesiąc w formacie YYYY-MM.')
    if month < '2000-01' or month > today.strftime('%Y-%m'):
        raise ValidationError('Wybierz miesiąc od stycznia 2000 do bieżącego miesiąca.')
    first = date.fromisoformat(month + '-01')
    if first < date(2000, 1, 1) or first > today:
        raise ValidationError('Wybierz miesiąc od stycznia 2000 do bieżącego miesiąca.')
    last_calendar_day = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
    end = min(last_calendar_day, today)
    previous_end = first - timedelta(days=1)
    previous_start = previous_end.replace(day=1)
    # A current-month report compares elapsed calendar days, never a whole prior month.
    if end < last_calendar_day:
        previous_end = previous_end.replace(day=min(end.day, previous_end.day))
    return first, end, previous_start, previous_end, end < last_calendar_day


def _budget(db, first, end):
    args = (first.isoformat(), end.isoformat())
    rows = db.execute('''SELECT e.* FROM budget_entries_v2 e JOIN budget_accounts a ON a.id=e.account_id
        WHERE e.date BETWEEN ? AND ? AND UPPER(COALESCE(a.currency,'PLN'))='PLN' ''', args).fetchall()
    from budget_refunds_service import flows
    income,expenses,refunds=flows(db,*args,pln_only=True)
    spent = dict(db.execute('''SELECT l.category_id, SUM(CASE WHEN e.kind='EXPENSE' THEN l.amount_cents ELSE -l.amount_cents END) FROM budget_entry_lines_v2 l
        JOIN budget_entries_v2 e ON e.id=l.entry_id JOIN budget_accounts a ON a.id=e.account_id
        WHERE (e.kind='EXPENSE' OR EXISTS(SELECT 1 FROM budget_purchase_refunds r WHERE r.entry_id=e.id)) AND e.date BETWEEN ? AND ? AND UPPER(COALESCE(a.currency,'PLN'))='PLN'
        GROUP BY l.category_id''', args).fetchall())
    month = first.strftime('%Y-%m')
    categories = [{**c, 'difference': c['remaining']} for c in category_workspace(db, month, through=end.isoformat(), pln_only=True)
                  if c['planned'] or c['spent']]
    unattributed = expenses - sum(spent.values())
    if unattributed > 0:
        categories.append(dict(id=None, name='Bez kategorii', planned=0, spent=unattributed/100, difference=-unattributed/100))

    transfers = db.execute('''SELECT t.direction, COALESCE(SUM(t.amount_cents),0) AS amount
        FROM budget_investment_transfers t JOIN budget_accounts a ON a.id=t.account_id
        WHERE t.date BETWEEN ? AND ? AND UPPER(COALESCE(a.currency,'PLN'))='PLN' GROUP BY t.direction''', args).fetchall()
    transfers = {r['direction']:r['amount']/100 for r in transfers}
    adjustments = db.execute("SELECT COALESCE(SUM(difference_cents),0),COUNT(*) FROM budget_account_reconciliations WHERE record_type='RECONCILIATION' AND date BETWEEN ? AND ?", args).fetchone()
    allocation = reserve_budget_costs(db, *args)
    return dict(income=income/100, expenses=expenses/100, refunds=refunds/100, net=(income-expenses)/100,
                **allocation,budget_spent=round(expenses/100+allocation['reserve_adjustment'],2),
                budget_net=round((income-expenses)/100-allocation['reserve_adjustment'],2),
                transfer_to_investments=transfers.get('OUT',0), transfer_from_investments=transfers.get('IN',0),
                balance_adjustments=adjustments[0]/100,balance_checks=adjustments[1],
                entry_count=len(rows), receipt_count=sum(bool(r['receipt_filename']) for r in rows),
                planned=round(sum(r['planned'] for r in categories if r.get('parent_id') is None),2), categories=categories,
                category_amount_mismatch=unattributed<0)


def _operations(db, first, end):
    rows = [dict(r) for r in db.execute('''SELECT t.*, date(t.date) AS day, p.name AS portfolio_name
        FROM transactions t JOIN portfolios p ON p.id=COALESCE(t.sub_portfolio_id,t.portfolio_id)
        WHERE date(t.date) BETWEEN ? AND ? ORDER BY date(t.date),t.id''', (first.isoformat(),end.isoformat()))]
    pairs = defaultdict(list)
    for row in rows:
        if row['transfer_id']:
            pairs[row['transfer_id']].append(row)
    internal = set()
    for pair in pairs.values():
        if len(pair)==2 and {r['type'] for r in pair}=={'DEPOSIT','WITHDRAW'} and pair[0]['day']==pair[1]['day'] \
                and abs(float(pair[0]['total_value'])-float(pair[1]['total_value']))<.005:
            internal.update(r['id'] for r in pair)
    def total(kind, field='total_value', external=False):
        return round(sum(float(r[field] or 0) for r in rows if r['type']==kind and (not external or r['id'] not in internal)),2)
    by_kind = defaultdict(int)
    for row in rows:
        by_kind[row['type']] += 1
    by_portfolio = defaultdict(lambda: {'count':0,'dividends':0,'interest':0})
    for row in rows:
        item = by_portfolio[row['sub_portfolio_id'] or row['portfolio_id']]
        item['name'] = row['portfolio_name']; item['count'] += 1
        if row['type'] in ('DIVIDEND','INTEREST'):
            item['dividends' if row['type']=='DIVIDEND' else 'interest'] += float(row['total_value'] or 0)
    return dict(count=len(rows), buys=by_kind['BUY'], sells=by_kind['SELL'],
                deposits=total('DEPOSIT',external=True), withdrawals=total('WITHDRAW',external=True),
                internal_transfers=round(sum(float(r['total_value']) for r in rows if r['id'] in internal and r['type']=='DEPOSIT'),2),
                dividends=total('DIVIDEND'), interest=total('INTEREST'),
                commissions=round(sum(float(r['commission'] or 0) for r in rows if r['type'] in ('BUY','SELL')),2),
                realized_profit=total('SELL','realized_profit'),
                portfolios=[dict(id=key, **{k:round(v,2) if isinstance(v,float) else v for k,v in item.items()}) for key,item in sorted(by_portfolio.items())])


def _performance(db, first, end):
    from special_account_results import analyze_special
    rows = db.execute('SELECT id,name,account_type,is_archived FROM portfolios WHERE parent_portfolio_id IS NULL ORDER BY name').fetchall()
    items = []
    for row in rows:
        if row['is_archived']:
            continue
        supported = row['account_type'] in ('STANDARD','IKE','IKZE','SAVINGS','PPK','BONDS')
        if not supported:
            items.append(dict(id=row['id'], name=row['name'], account_type=row['account_type'],
                opening_value=None, closing_value=None, profit=None, return_percent=None,
                status='unsupported', warnings=['Brak historycznej wyceny tego typu konta w analizie wyników.']))
            continue
        if row['account_type'] in ('PPK','BONDS'):
            result = analyze_special(db,row,first,end)
            items.append(dict(id=row['id'],name=row['name'],account_type=row['account_type'],**result))
            continue
        result = analyze([row['id']], first.isoformat(),end.isoformat())
        reliable = result['status']=='ok'
        items.append(dict(id=row['id'], name=row['name'], account_type=row['account_type'],
            opening_value=result['opening_value'], closing_value=result['closing_value'],
            profit=result['profit'] if reliable else None, return_percent=result['dietz_percent'] if reliable else None,
            status=result['status'], warnings=result['warnings']))
    supported_items = [r for r in items if r['status']!='unsupported']
    complete = bool(supported_items) and all(r['profit'] is not None for r in supported_items)
    return dict(items=items, profit=round(sum(r['profit'] for r in supported_items),2) if complete else None,
                available_profit=round(sum(r['profit'] for r in supported_items if r['profit'] is not None),2),
                valued_count=sum(r['profit'] is not None for r in supported_items),
                complete=complete, scope='all_active_investment_accounts',
                excluded_count=sum(r['status']=='unsupported' for r in items),
                archived_count=db.execute('SELECT COUNT(*) FROM portfolios WHERE is_archived=1').fetchone()[0])


def _loans(db, first, end):
    items, warnings = [], []
    paid = [dict(r) for r in db.execute('SELECT * FROM loan_installment_payments')]
    paid_keys = {(r['loan_id'],r['installment_month']) for r in paid if r['paid_on']<=end.isoformat()}
    overpayments = [dict(r) for r in db.execute('''SELECT loan_id, amount, budget_entry_id, CAST(date AS TEXT) AS day
        FROM loan_overpayments WHERE date(date) BETWEEN ? AND ?''', (first.isoformat(),end.isoformat()))]
    for loan in db.execute('''SELECT id,name,original_amount,duration_months,CAST(start_date AS TEXT) AS start_date,
            installment_type FROM loans'''):
        try:
            start_date = date.fromisoformat(loan['start_date'])
        except (ValueError,TypeError):
            start_date = None
        if start_date and start_date>end:
            continue
        recorded = [r for r in paid if r['loan_id']==loan['id'] and first.isoformat()<=r['paid_on']<=end.isoformat()]
        extra = [r for r in overpayments if r['loan_id']==loan['id']]
        scheduled_count = scheduled_amount = without_record = estimated_balance = None
        try:
            schedule,_,_ = LoanService.calculate_schedule(dict(loan), LoanService.get_loan_rates(loan['id']), LoanService.get_loan_overpayments(loan['id']))
            due = [r for r in schedule if first.isoformat()<=r['date']<=end.isoformat() and r['installment']>0 and not r.get('is_mid_month')]
            scheduled_count = len(due)
            scheduled_amount = round(sum(r['installment'] for r in due),2)
            without_record = sum((loan['id'],r['month']) not in paid_keys for r in due)
            estimated_balance = next((r['remaining_balance'] for r in reversed(schedule) if r['date']<=end.isoformat()),None)
        except (ValueError,TypeError,IndexError,ZeroDivisionError):
            warnings.append(f'{loan["name"]}: nie można odczytać harmonogramu. Zapisane płatności pozostają w raporcie.')
        items.append(dict(id=loan['id'], name=loan['name'], scheduled_count=scheduled_count, scheduled_amount=scheduled_amount,
            without_record=without_record, estimated_balance=estimated_balance, paid_count=len(recorded),
            paid_amount=sum(r['amount_cents'] for r in recorded)/100,
            overpaid_amount=round(sum(float(r['amount']) for r in extra),2),
            budget_linked_amount=round(sum(r['amount_cents'] for r in recorded if r['budget_entry_id'])/100
                + sum(float(r['amount']) for r in extra if r['budget_entry_id']),2)))
    return dict(items=items, paid_amount=round(sum(r['paid_amount'] for r in items),2),
        overpaid_amount=round(sum(r['overpaid_amount'] for r in items),2),
        without_record=sum(r['without_record'] or 0 for r in items), warnings=warnings)


def generate(month=None):
    first,end,prev_first,prev_end,partial = report_period(month)
    db = get_db()
    budget, previous = _budget(db,first,end), _budget(db,prev_first,prev_end)
    operations = _operations(db,first,end)
    performance = _performance(db,first,end)
    loans = _loans(db,first,end)
    month_index = max(2000*12, first.year*12+first.month-1-11)
    history_start = date(month_index//12, month_index%12+1, 1)
    history = [dict(r) for r in db.execute('''SELECT date,net_worth,total_assets,total_liabilities,assets_breakdown,valuation_notes
        FROM net_worth_snapshots WHERE date BETWEEN ? AND ? ORDER BY date''', (history_start.isoformat(),end.isoformat()))]
    import json
    for point in history:
        point['assets_breakdown'] = json.loads(point['assets_breakdown']) if point['assets_breakdown'] else None
        point['valuation_notes'] = json.loads(point['valuation_notes']) if point['valuation_notes'] else []
    snapshots = [r for r in history if r['date']>=(first-timedelta(days=1)).isoformat()]
    opening = next((r for r in snapshots if r['date']==(first-timedelta(days=1)).isoformat()),None)
    closing = next((r for r in snapshots if r['date']==end.isoformat()),None)
    in_period = [r for r in snapshots if r['date']>=first.isoformat()]
    entries = [dict(r) for r in db.execute('''SELECT id,title,ticker,kind,status,entry_date,is_archived
        FROM investor_journal WHERE entry_date BETWEEN ? AND ? ORDER BY entry_date,id''', (first.isoformat(),end.isoformat()))]
    reviews = [dict(r) for r in db.execute('''SELECT r.id,r.entry_id,r.review_date,r.outcome,r.notes,r.lessons,j.title,j.ticker
        FROM investor_journal_reviews r JOIN investor_journal j ON j.id=r.entry_id
        WHERE r.review_date BETWEEN ? AND ? ORDER BY r.review_date DESC,r.id DESC''', (first.isoformat(),end.isoformat()))]
    due = [dict(r) for r in db.execute('''SELECT id,title,ticker,review_date FROM investor_journal
        WHERE is_archived=0 AND status!='CLOSED' AND review_date<=? ORDER BY review_date,id''', (end.isoformat(),))]
    tasks = []
    for row in db.execute('SELECT id,title,category,completed_at FROM dashboard_tasks WHERE completed_at IS NOT NULL ORDER BY completed_at DESC,id DESC'):
        # Match the same local calendar as date.today(), including UTC saves near midnight.
        completed_day = datetime.fromisoformat(row['completed_at']).astimezone().date()
        if first<=completed_day<=end:
            tasks.append(dict(row))
    ppk_rows = db.execute('''SELECT t.*,p.name FROM ppk_transactions t JOIN portfolios p ON p.id=t.portfolio_id
        WHERE date(t.date) BETWEEN ? AND ?''', (first.isoformat(),end.isoformat())).fetchall()
    ppk = dict(count=len(ppk_rows),employee_contributions=round(sum(float(r['employee_units'])*float(r['price_per_unit']) for r in ppk_rows),2),
               employer_contributions=round(sum(float(r['employer_units'])*float(r['price_per_unit']) for r in ppk_rows),2))
    warnings = list(loans['warnings'])
    if not opening or not closing:
        warnings.append('Brak zapisanej wyceny całego majątku na obu granicach okresu. Zmiana majątku netto nie jest wyliczana.')
    if budget['category_amount_mismatch']:
        warnings.append('Suma pozycji kategorii przekracza zapisane wydatki. Sprawdź przypisanie kategorii w budżecie.')
    if db.execute("SELECT 1 FROM budget_accounts WHERE UPPER(COALESCE(currency,'PLN'))!='PLN' LIMIT 1").fetchone():
        warnings.append('Budżet obejmuje tylko konta PLN. Konta w innych walutach nie są sumowane bez kursu przeliczenia.')
    insights = []
    if not budget['entry_count']:
        insights.append(dict(tone='neutral',text='W tym okresie nie zapisano wpływów ani wydatków w budżecie.',href=f'/budget?month={first:%Y-%m}&view=entries',label='Zobacz wpisy'))
    overspent = [r for r in budget['categories'] if r['planned']>0 and r['spent']>r['planned']]
    if overspent:
        insights.append(dict(tone='attention',text='Wydatki przekroczyły zapisany plan w kategoriach: '+', '.join(r['name'] for r in overspent)+'.',href=f'/budget?month={first:%Y-%m}&view=plan',label='Sprawdź plan'))
    if loans['without_record']:
        insights.append(dict(tone='attention',text=f'Raty bez zapisu płatności w harmonogramie okresu: {loans["without_record"]}. To nie jest potwierdzenie zaległości w banku.',href='/loans',label='Sprawdź kredyty'))
    if due:
        insights.append(dict(tone='attention',text=f'Tezy z obecnie zapisanym terminem przeglądu do końca okresu: {len(due)}. To aktualny stan dziennika.',href='/journal',label='Przejrzyj dziennik'))
    if performance['items'] and not performance['complete']:
        insights.append(dict(tone='neutral',text='Wynik inwestycji wymaga pełnych i zgodnych wycen. Braki opisano przy portfelach.',href='/portfolios',label='Sprawdź portfele'))
    return dict(schema_version=1,month=first.strftime('%Y-%m'),generated_at=datetime.now(timezone.utc).isoformat(),
        period=dict(start=first.isoformat(),end=end.isoformat(),partial=partial,previous_start=prev_first.isoformat(),previous_end=prev_end.isoformat()),
        budget=dict(**budget,previous=previous,changes={key:round(budget[key]-previous[key],2) for key in ('income','expenses','net')}),
        investments=dict(operations=operations,performance=performance,ppk=ppk), loans=loans,
        wealth=dict(opening=opening,closing=closing,latest=in_period[-1] if in_period else None,
            change=round(closing['net_worth']-opening['net_worth'],2) if opening and closing else None,observations=len(in_period),
            history=history,history_start=history_start.isoformat(),
            observed_change=round(history[-1]['net_worth']-history[0]['net_worth'],2) if len(history)>1 else None),
        journal=dict(entries=entries,reviews=reviews,due=due),completed_tasks=tasks,insights=insights,warnings=warnings)
