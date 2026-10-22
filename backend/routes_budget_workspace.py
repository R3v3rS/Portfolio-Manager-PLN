"""Monthly budget plans, actual cash movements, receipts and scheduled bills."""

import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, request, send_from_directory

from api.exceptions import ApiError, NotFoundError, ValidationError
from api.response import success_response
from database import get_db
from budget_summary_service import monthly_budget_totals
from budget_category_hierarchy_service import category_workspace, save_category


workspace_bp = Blueprint('budget_workspace', __name__)
STARTER_CATEGORIES = (
    ('Jedzenie', 'UtensilsCrossed'),
    ('Mieszkanie', 'House'),
    ('Rachunki', 'ReceiptText'),
    ('Transport', 'Car'),
    ('Zdrowie', 'HeartPulse'),
    ('Przyjemności', 'Sparkles'),
    ('Inne', 'Shapes'),
)
MONTH_PATTERN = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
RECEIPT_TYPES = {
    'image/jpeg': ('.jpg', b'\xff\xd8\xff'),
    'image/png': ('.png', b'\x89PNG\r\n\x1a\n'),
    'image/webp': ('.webp', b'RIFF'),
    'application/pdf': ('.pdf', b'%PDF-'),
}


def body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ValidationError('Oczekiwano danych formularza.')
    return value


def text_field(value, label, limit=150):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'{label} jest wymagane.')
    result = value.strip()
    if len(result) > limit:
        raise ValidationError(f'{label} jest zbyt długie.')
    return result


def optional_text(value, limit=150):
    if value is None:
        return None
    if not isinstance(value, str) or len(value.strip()) > limit:
        raise ValidationError('Nieprawidłowy tekst.')
    return value.strip() or None


def positive_id(value, label):
    if isinstance(value, bool):
        raise ValidationError(f'Nieprawidłowe pole: {label}.')
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f'Nieprawidłowe pole: {label}.') from None
    if number <= 0 or str(number) != str(value):
        raise ValidationError(f'Nieprawidłowe pole: {label}.')
    return number


def cents(value, label='Kwota', allow_zero=False):
    if isinstance(value, bool):
        raise ValidationError(f'{label} musi być kwotą w złotych.')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValidationError(f'{label} musi być kwotą w złotych.') from None
    if not amount.is_finite() or amount > Decimal('999999999.99') or amount < 0:
        raise ValidationError(f'{label} musi być poprawną kwotą w dopuszczalnym zakresie.')
    try:
        rounded = amount.quantize(Decimal('0.01'))
    except InvalidOperation:
        raise ValidationError(f'{label} musi być poprawną kwotą.') from None
    if amount != rounded:
        raise ValidationError(f'{label} może mieć najwyżej dwa miejsca po przecinku.')
    result = int(amount * 100)
    if result < 0 or (result == 0 and not allow_zero) or result > 999_999_999_99:
        raise ValidationError(f'{label} musi być dodatnią kwotą.')
    return result


def month_value(value):
    if not isinstance(value, str) or not MONTH_PATTERN.fullmatch(value):
        raise ValidationError('Miesiąc musi mieć format RRRR-MM.')
    return value


def day_value(value):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError('Data musi mieć format RRRR-MM-DD.') from None
    if parsed.isoformat() != value:
        raise ValidationError('Data musi mieć format RRRR-MM-DD.')
    return value


def exists(table, row_id, label):
    row = get_db().execute(f'SELECT id FROM {table} WHERE id = ?', (row_id,)).fetchone()
    if not row:
        raise NotFoundError(f'{label} nie istnieje.')


def validate_lines(data, kind, amount_cents):
    if kind == 'INCOME':
        return []
    raw_lines = data.get('lines')
    if raw_lines is None:
        raw_lines = [{'category_id': data.get('category_id'), 'amount': data.get('amount'), 'label': ''}]
    if not isinstance(raw_lines, list) or not raw_lines or len(raw_lines) > 100:
        raise ValidationError('Wydatek wymaga od jednej do stu pozycji.')
    lines = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            raise ValidationError('Nieprawidłowa pozycja wydatku.')
        category_id = positive_id(raw.get('category_id'), 'kategoria')
        exists('budget_categories_v2', category_id, 'Kategoria')
        lines.append({
            'category_id': category_id,
            'amount_cents': cents(raw.get('amount'), 'Kwota pozycji'),
            'label': optional_text(raw.get('label'), 120) or '',
        })
    if sum(line['amount_cents'] for line in lines) != amount_cents:
        raise ValidationError('Suma pozycji musi być równa kwocie wydatku.')
    return lines


def validate_entry(data):
    account_id = positive_id(data.get('account_id'), 'konto')
    exists('budget_accounts', account_id, 'Konto')
    kind = data.get('kind')
    if kind not in ('INCOME', 'EXPENSE'):
        raise ValidationError('Rodzaj wpisu musi być przychodem albo wydatkiem.')
    if kind == 'INCOME':
        from budget_account_types import is_credit
        if is_credit(get_db().execute('SELECT * FROM budget_accounts WHERE id=?',(account_id,)).fetchone()):
            raise ValidationError('Spłatę karty zapisz jako przelew z konta bankowego. Zwrot zakupu dodaj przy pierwotnym wydatku. Te operacje nie są dochodem.')
    amount_cents = cents(data.get('amount'))
    return {
        'account_id': account_id,
        'kind': kind,
        'amount_cents': amount_cents,
        'date': day_value(data.get('date')),
        'description': text_field(data.get('description'), 'Opis'),
        'merchant': optional_text(data.get('merchant')),
        'lines': validate_lines(data, kind, amount_cents),
    }


def insert_entry(db, entry):
    movement = entry['amount_cents'] if entry['kind'] == 'INCOME' else -entry['amount_cents']
    effect = entry.get('cash_effect', 1)
    if type(effect) is not int or effect not in (0, 1):
        raise ValidationError('Nieprawidłowy wpływ wpisu na saldo.')
    db.execute('UPDATE budget_accounts SET balance = ROUND(balance + ?, 2) WHERE id = ?',
               (movement * effect / 100, entry['account_id']))
    cursor = db.execute('''
        INSERT INTO budget_entries_v2 (account_id, kind, amount_cents, date, description, merchant, cash_effect, classification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (entry['account_id'], entry['kind'], entry['amount_cents'], entry['date'],
          entry['description'], entry['merchant'], effect, line_classification(db, entry['lines'], entry['kind'])))
    entry_id = cursor.lastrowid
    for line in entry['lines']:
        db.execute('''
            INSERT INTO budget_entry_lines_v2 (entry_id, category_id, label, amount_cents)
            VALUES (?, ?, ?, ?)
        ''', (entry_id, line['category_id'], line['label'], line['amount_cents']))
    return entry_id


def line_classification(db, lines, kind='EXPENSE'):
    if kind != 'EXPENSE':
        return 'GENERAL'
    if not lines or any(db.execute('SELECT is_unassigned FROM budget_categories_v2 WHERE id=?', (line['category_id'],)).fetchone()[0] for line in lines):
        return 'UNASSIGNED'
    return 'SPLIT' if len(lines) > 1 or any(line.get('label') for line in lines) else 'GENERAL'


def receipt_dir():
    return Path(current_app.config.get(
        'BUDGET_RECEIPT_DIR',
        Path(current_app.root_path) / 'uploads' / 'budget-receipts',
    ))


def entry_row(entry_id):
    row = get_db().execute('SELECT * FROM budget_entries_v2 WHERE id = ?', (entry_id,)).fetchone()
    if not row:
        raise NotFoundError('Wpis nie istnieje.')
    return row


@workspace_bp.get('/')
@workspace_bp.get('')
def workspace():
    month = month_value(request.args.get('month') or date.today().strftime('%Y-%m'))
    return success_response(workspace_data(get_db(), month))


def workspace_data(db, month):
    from budget_planning_service import workspace as planning_workspace
    accounts = [dict(row) for row in db.execute(
        'SELECT id, name, ROUND(balance, 2) AS balance, currency, account_type FROM budget_accounts ORDER BY id'
    ).fetchall()]
    categories = category_workspace(db, month)
    labels = {c['id']: c['selection_label'] for c in categories}
    from budget_bill_schedule import due_in_month
    from budget_bills_service import serialize
    bills = []
    for row in db.execute('SELECT b.*,a.name account_name FROM budget_bills_v2 b JOIN budget_accounts a ON a.id=b.account_id ORDER BY b.due_day,b.id'):
        paid = db.execute('SELECT 1 FROM budget_bill_payments_v2 WHERE bill_id=? AND month=?',(row['id'],month)).fetchone()
        if (row['active'] or paid) and due_in_month(row,month):
            bills.append({**serialize(db,row,month),'account_name':row['account_name'],'category_name':labels[row['category_id']]})
    rows = db.execute('''
        SELECT e.*, a.name AS account_name, p.bill_id,rf.purchase_entry_id,
               COALESCE(lp.loan_id, lo.loan_id) AS loan_id
        FROM budget_entries_v2 e
        JOIN budget_accounts a ON a.id = e.account_id
        LEFT JOIN budget_bill_payments_v2 p ON p.entry_id = e.id
        LEFT JOIN budget_purchase_refunds rf ON rf.entry_id=e.id
        LEFT JOIN loan_installment_payments lp ON lp.budget_entry_id = e.id
        LEFT JOIN loan_overpayments lo ON lo.budget_entry_id = e.id
        WHERE substr(e.date, 1, 7) = ?
        ORDER BY e.date DESC, e.id DESC
    ''', (month,)).fetchall()
    entries = []
    for row in rows:
        lines = [dict(line) for line in db.execute('''
            SELECT l.category_id, c.name AS category_name, l.label, l.amount_cents
            FROM budget_entry_lines_v2 l
            JOIN budget_categories_v2 c ON c.id = l.category_id
            WHERE l.entry_id = ? ORDER BY l.id
        ''', (row['id'],)).fetchall()]
        entries.append({
            'id': row['id'], 'account_id': row['account_id'], 'account_name': row['account_name'],
            'kind': 'REFUND' if row['purchase_entry_id'] else row['kind'], 'refund_of': row['purchase_entry_id'],
            'refunded': db.execute('SELECT COALESCE(SUM(e.amount_cents),0)/100.0 FROM budget_purchase_refunds r JOIN budget_entries_v2 e ON e.id=r.entry_id WHERE r.purchase_entry_id=?',(row['id'],)).fetchone()[0],
            'amount': row['amount_cents'] / 100, 'date': row['date'],
            'description': row['description'], 'merchant': row['merchant'],
            'has_receipt': bool(row['receipt_filename']), 'bill_id': row['bill_id'],
            'loan_id': row['loan_id'],
            'reserve_id': db.execute('SELECT reserve_id FROM budget_reserve_movements WHERE budget_entry_id=? LIMIT 1',(row['id'],)).fetchone()[0] if db.execute('SELECT 1 FROM budget_reserve_movements WHERE budget_entry_id=?',(row['id'],)).fetchone() else None,
            'version': row['version'], 'cash_effect': bool(row['cash_effect']),
            'classification_status': row['classification_status'] if row['classification_status'] != 'GENERAL' else ('SPLIT' if len(lines)>1 else 'GENERAL'),
            'lines': [{**line, 'category_name': labels[line['category_id']], 'amount': line['amount_cents'] / 100} for line in lines],
        })
    transfers = db.execute('''
        SELECT t.*, a.name AS account_name, p.name AS portfolio_name
        FROM budget_investment_transfers t
        JOIN budget_accounts a ON a.id = t.account_id
        JOIN portfolios p ON p.id = t.portfolio_id
        WHERE substr(t.date, 1, 7) = ?
    ''', (month,)).fetchall()
    entries.extend({
        'id': -row['id'], 'account_id': row['account_id'], 'account_name': row['account_name'],
        'kind': 'TRANSFER', 'direction': row['direction'], 'amount': row['amount_cents'] / 100,
        'date': row['date'], 'description': row['description'], 'merchant': None, 'lines': [],
        'has_receipt': False, 'bill_id': None, 'loan_id': None,
        'portfolio_id': row['portfolio_id'], 'portfolio_name': row['portfolio_name'],
        'investment_transaction_id': row['investment_transaction_id'],
    } for row in transfers)
    entries.sort(key=lambda entry: (entry['date'], abs(entry['id'])), reverse=True)
    totals=monthly_budget_totals(db, month)
    planning=planning_workspace(db,month)
    from budget_month_plan_service import rows as month_plan
    planning['month_plan']=month_plan(db,month,categories,bills,planning['loans'],planning['reserve_plans'],totals)
    from budget_plan_read_service import category_details
    allocations=category_details(db,month,categories,bills,planning['loans'],planning['reserve_plans'])
    for category in categories:category['plan_details']=allocations[category['id']]
    for item in planning['month_plan']:
        if item['kind']=='RESERVES':
            ordinary=[r for r in planning['reserve_plans'] if r.get('monthly_amount') is None or r.get('open_ended')]
            item['plan_done']=round(sum(min(r['funded'],r['planned']) for r in ordinary),2)
            item['extra']=round(sum(max(0,r['funded']-r['planned']) for r in ordinary),2)
        elif item['kind']=='DAILY':
            roots=[c for c in categories if c['parent_id'] is None]
            item['plan_done']=round(sum(min(c['plan_details']['ordinary_spent'],c['plan_details']['ordinary_planned']) for c in roots),2)
            item['extra']=round(sum(c['plan_details']['ordinary_over'] for c in roots),2)
        else:
            item['plan_done']=min(item['done'],item['planned'])
            item['extra']=round(max(0,item['done']-item['planned']),2)
    from budget_chart_service import pace,fixed_summary
    bank_transfers=[dict(r,amount=r['amount_cents']/100,description=r['notes']) for r in db.execute('''SELECT t.id,t.date,t.notes,t.amount_cents,t.source_account_id,t.target_account_id,
        t.move_money,t.reserve_action,s.name source_name,a.name target_name,r.name reserve_name
        FROM budget_account_transfers t JOIN budget_accounts s ON s.id=t.source_account_id
        JOIN budget_accounts a ON a.id=t.target_account_id LEFT JOIN budget_reserves r ON r.id=t.reserve_id
        WHERE substr(t.date,1,7)=? ORDER BY t.date DESC,t.id DESC''',(month,))]
    return {
        'chart':pace(db,month,categories,bills,planning['loans'],planning['reserve_plans'],totals),
        'fixed_costs':fixed_summary(bills,planning['loans']),
        'month': month, 'accounts': accounts, 'categories': categories,
        'bills': bills, 'entries': entries, 'bank_transfers':bank_transfers,
        'totals': totals,
        'planning': planning,
    }


@workspace_bp.get('/plans/year')
def year_plan():
    from budget_usability_service import annual_plan
    return success_response(annual_plan(get_db(), request.args.get('start') or date.today().strftime('%Y-%m')))


@workspace_bp.post('/plans/transfer-preview')
def plan_transfer_preview():
    from budget_usability_service import transfer_preview
    return success_response(transfer_preview(get_db(), body()))


@workspace_bp.post('/plans/transfer')
def plan_transfer():
    from budget_usability_service import transfer_plan
    return success_response(transfer_plan(get_db(), body()))


@workspace_bp.post('/accounts')
def create_account():
    from budget_accounts_service import create
    data = body()
    data.setdefault('request_id', str(uuid4()))
    return success_response(create(data), 201)


@workspace_bp.post('/categories')
def create_category():
    return success_response(save_category(get_db(), body()), 201)


@workspace_bp.put('/categories/<int:category_id>')
def update_category(category_id):
    return success_response(save_category(get_db(), body(), category_id))


@workspace_bp.put('/plans/<int:category_id>')
def set_plan(category_id):
    data = body()
    exists('budget_categories_v2', category_id, 'Kategoria')
    month = month_value(data.get('month'))
    amount = cents(data.get('amount'), 'Plan', allow_zero=True)
    db = get_db()
    if db.execute('SELECT 1 FROM budget_reserves WHERE category_id=? AND monthly_amount_cents IS NOT NULL AND open_ended=0 AND is_archived=0',(category_id,)).fetchone():
        raise ValidationError('Kategoria korzysta z miesięcznej puli. Skoryguj kwotę w sekcji „Odłożenia i miesięczne pule”.')
    db.execute('''
        INSERT INTO budget_plans_v2 (category_id, month, amount_cents) VALUES (?, ?, ?)
        ON CONFLICT(category_id, month) DO UPDATE SET amount_cents = excluded.amount_cents
    ''', (category_id, month, amount))
    db.commit()
    return success_response({'category_id': category_id, 'month': month, 'amount': amount / 100})


@workspace_bp.post('/plans/copy')
def copy_plans():
    data = body()
    source, target = month_value(data.get('source')), month_value(data.get('target'))
    if source == target:
        raise ValidationError('Wybierz inny miesiąc docelowy.')
    db = get_db()
    from budget_default_plan_service import resolve
    amounts,_=resolve(db,source)
    copied=0
    for category_id,amount in amounts.items():
        copied+=db.execute('INSERT OR IGNORE INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,?,?)',
                           (category_id,target,amount)).rowcount
    db.commit()
    return success_response({'copied': copied})


@workspace_bp.get('/plans/defaults')
def get_default_plans():
    from budget_default_plan_service import defaults
    month=month_value(request.args.get('month') or date.today().strftime('%Y-%m'))
    return success_response(defaults(get_db(),month))


@workspace_bp.put('/plans/defaults')
def put_default_plans():
    from budget_default_plan_service import save_defaults
    return success_response(save_defaults(get_db(),body()))


@workspace_bp.post('/plans/copy-preview')
def preview_plan_copy():
    from budget_default_plan_service import copy_preview
    return success_response(copy_preview(get_db(),body()))


@workspace_bp.post('/plans/copy-range')
def save_plan_copy():
    from budget_default_plan_service import copy_range
    return success_response(copy_range(get_db(),body()))


@workspace_bp.delete('/plans/<int:category_id>')
def reset_plan(category_id):
    exists('budget_categories_v2',category_id,'Kategoria')
    month=month_value(request.args.get('month'))
    db=get_db()
    db.execute('DELETE FROM budget_plans_v2 WHERE category_id=? AND month=?',(category_id,month))
    db.commit()
    return success_response({'category_id':category_id,'month':month})


@workspace_bp.post('/entries')
def create_entry():
    data=body()
    entry = validate_entry(data)
    if entry['date']>date.today().isoformat():
        raise ValidationError('Przyszłą płatność dodaj do planu rachunków lub zakupów, a przyszły wpływ do planowanych dochodów. Saldo zmieniamy po wykonaniu operacji.')
    from budget_reserves_service import _request_id, _fingerprint
    data.setdefault('request_id',str(uuid4()))
    token=_request_id(data)
    fingerprint=_fingerprint(entry)
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT * FROM budget_entry_requests WHERE request_id=?',(token,)).fetchone()
        if previous:
            if previous['request_payload']!=fingerprint or not previous['entry_id']:
                raise ApiError('entry_request_conflict','Ten zapis został już wykorzystany lub cofnięty. Odśwież formularz.',status=409)
            return success_response({'id':previous['entry_id']},201)
        entry_id = insert_entry(db, entry)
        db.execute('INSERT INTO budget_entry_requests VALUES(?,?,?)',(token,fingerprint,entry_id))
        db.commit()
    except Exception:
        db.rollback();raise
    finally:
        if db.in_transaction:db.rollback()
    return success_response({'id': entry_id}, 201)


@workspace_bp.put('/entries/<int:entry_id>')
def replace_entry(entry_id):
    data = body()
    entry = validate_entry(data)
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    try:
        old = entry_row(entry_id)
        if db.execute('SELECT 1 FROM budget_purchase_refunds WHERE entry_id=? OR purchase_entry_id=?',(entry_id,entry_id)).fetchone():
            raise ValidationError('Wpis ma powiązany zwrot. Usuń błędny zwrot przed zmianą zakupu.')
        if db.execute('SELECT 1 FROM budget_expected_income_receipts WHERE budget_entry_id=?',(entry_id,)).fetchone():
            raise ValidationError('Ten wpływ rozlicza plan dochodu. Usuń błędny wpis i zapisz otrzymanie ponownie.')
        if db.execute('SELECT 1 FROM budget_reserve_movements WHERE budget_entry_id=?',(entry_id,)).fetchone():
            raise ValidationError('Ten wydatek rozlicza rezerwę. Korektę zapisz osobnym wpisem, aby zachować historię cyklu.')
        if db.execute('SELECT 1 FROM budget_bill_payments_v2 WHERE entry_id=?',(entry_id,)).fetchone():
            raise ValidationError('Najpierw cofnij rozliczenie rachunku, zanim zmienisz ten wydatek.')
        if db.execute('SELECT 1 FROM loan_installment_payments WHERE budget_entry_id=? UNION ALL SELECT 1 FROM loan_overpayments WHERE budget_entry_id=?',(entry_id,entry_id)).fetchone():
            raise ValidationError('Ten wydatek jest połączony z kredytem. Popraw go na ekranie kredytu.')
        if entry['date']>date.today().isoformat() and entry['date']!=old['date']:
            raise ValidationError('Przyszłą operację zapisz jako plan. Nie zmieniaj jeszcze salda konta.')
        if 'version' in data and (type(data['version']) is not int or data['version'] != old['version']):
            raise ApiError('budget_entry_version_conflict', 'Wydatek zmienił się. Odśwież dane przed korektą.', status=409)
        old_movement = old['amount_cents'] if old['kind'] == 'INCOME' else -old['amount_cents']
        if db.execute('SELECT 1 FROM budget_import_sources WHERE entry_id=?', (entry_id,)).fetchone() and \
                (old['account_id'], old['kind'], old['amount_cents'], old['date']) != \
                (entry['account_id'], entry['kind'], entry['amount_cents'], entry['date']):
            raise ValidationError('Kwota, data i konto wpisu z banku pochodzą z wyciągu. Możesz zmienić opis lub podział kategorii.')
        new_movement = entry['amount_cents'] if entry['kind'] == 'INCOME' else -entry['amount_cents']
        db.execute('UPDATE budget_accounts SET balance = ROUND(balance - ?, 2) WHERE id = ?',
                   (old_movement * old['cash_effect'] / 100, old['account_id']))
        db.execute('UPDATE budget_accounts SET balance = ROUND(balance + ?, 2) WHERE id = ?',
                   (new_movement * old['cash_effect'] / 100, entry['account_id']))
        db.execute('''
            UPDATE budget_entries_v2
            SET account_id = ?, kind = ?, amount_cents = ?, date = ?, description = ?, merchant = ?, classification_status = ?, version=version+1
            WHERE id = ?
        ''', (entry['account_id'], entry['kind'], entry['amount_cents'], entry['date'],
              entry['description'], entry['merchant'], line_classification(db, entry['lines'], entry['kind']), entry_id))
        db.execute('DELETE FROM budget_entry_lines_v2 WHERE entry_id = ?', (entry_id,))
        for line in entry['lines']:
            db.execute('''INSERT INTO budget_entry_lines_v2 (entry_id, category_id, label, amount_cents)
                VALUES (?, ?, ?, ?)''', (entry_id, line['category_id'], line['label'], line['amount_cents']))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return success_response({'id': entry_id})


@workspace_bp.get('/entries/<int:entry_id>/settlement-preview')
def settlement_preview(entry_id):
    from budget_settlement_service import preview
    return success_response(preview(get_db(),entry_id))


@workspace_bp.post('/entries/<int:entry_id>/reverse-settlement')
def reverse_settlement(entry_id):
    from budget_settlement_service import reverse
    return success_response(reverse(entry_id,body()))


@workspace_bp.post('/entries/<int:entry_id>/apply-balance')
def apply_entry_balance(entry_id):
    from budget_entry_balance_service import apply
    return success_response(apply(entry_id, body()))


@workspace_bp.post('/entries/<int:entry_id>/refunds')
def refund_purchase(entry_id):
    from budget_refunds_service import create
    return success_response(create(entry_id,body()),201)


@workspace_bp.delete('/entries/<int:entry_id>')
def delete_entry(entry_id):
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        row = entry_row(entry_id)
        if db.execute('SELECT 1 FROM budget_purchase_refunds WHERE purchase_entry_id=?',(entry_id,)).fetchone():
            raise ValidationError('Najpierw usuń zwroty powiązane z zakupem.')
        if db.execute('SELECT 1 FROM budget_reserve_movements WHERE budget_entry_id=?',(entry_id,)).fetchone():
            raise ValidationError('Ten wydatek rozlicza rezerwę i jest częścią historii jej cyklu.')
        if db.execute('SELECT 1 FROM budget_settlements WHERE entry_id=?',(entry_id,)).fetchone():
            raise ValidationError('Cofnij rozliczenie na ekranie rachunków. Podgląd pokaże zmianę salda i zachowa historię korekty.')
        if db.execute('SELECT 1 FROM loan_installment_payments WHERE budget_entry_id=? UNION ALL SELECT 1 FROM loan_overpayments WHERE budget_entry_id=?',(entry_id,entry_id)).fetchone():
            raise ValidationError('Ten wydatek jest połączony z kredytem. Cofnij go na ekranie kredytu.')
        refund=db.execute('SELECT purchase_entry_id FROM budget_purchase_refunds WHERE entry_id=?',(entry_id,)).fetchone()
        if refund:
            db.execute('DELETE FROM budget_purchase_refunds WHERE entry_id=?',(entry_id,))
            db.execute('UPDATE budget_entries_v2 SET version=version+1 WHERE id=?',(refund[0],))
        movement = row['amount_cents'] if row['kind'] == 'INCOME' else -row['amount_cents']
        db.execute('UPDATE budget_accounts SET balance=ROUND(balance-?,2) WHERE id=?',
                   (movement * row['cash_effect'] / 100, row['account_id']))
        db.execute('DELETE FROM budget_import_sources WHERE entry_id=?', (entry_id,))
        db.execute('UPDATE budget_import_rows SET entry_id=NULL WHERE entry_id=?', (entry_id,))
        db.execute("UPDATE budget_receipt_drafts SET entry_id=NULL,status='DELETED' WHERE entry_id=?", (entry_id,))
        db.execute('DELETE FROM budget_bill_payments_v2 WHERE entry_id=?', (entry_id,))
        db.execute('''UPDATE budget_expected_incomes SET version=version+1 WHERE id IN
            (SELECT income_id FROM budget_expected_income_receipts WHERE budget_entry_id=?)''',(entry_id,))
        db.execute('DELETE FROM budget_expected_income_receipts WHERE budget_entry_id=?',(entry_id,))
        db.execute('DELETE FROM budget_entry_lines_v2 WHERE entry_id=?', (entry_id,))
        db.execute('DELETE FROM budget_entries_v2 WHERE id=?', (entry_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    if row['receipt_filename']:
        try:
            (receipt_dir() / row['receipt_filename']).unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning('Nie udało się usunąć pliku paragonu po cofnięciu wpisu %s.',entry_id)
    return success_response({'deleted': entry_id})


@workspace_bp.post('/bills')
def create_bill():
    from budget_bills_service import save
    return success_response(save(body()),201)


@workspace_bp.put('/bills/<int:bill_id>')
def update_bill(bill_id):
    from budget_bills_service import save
    return success_response(save(body(),bill_id))


@workspace_bp.delete('/bills/<int:bill_id>')
def deactivate_bill(bill_id):
    exists('budget_bills_v2', bill_id, 'Rachunek')
    db = get_db()
    db.execute('UPDATE budget_bills_v2 SET active = 0, version=version+1 WHERE id = ?', (bill_id,))
    db.commit()
    return success_response({'id': bill_id})


@workspace_bp.post('/bills/<int:bill_id>/pay')
def pay_bill(bill_id):
    from budget_bills_service import pay
    return success_response(pay(bill_id,body()),201)


@workspace_bp.post('/entries/<int:entry_id>/receipt')
def upload_receipt(entry_id):
    row = entry_row(entry_id)
    if row['kind'] != 'EXPENSE':
        raise ValidationError('Paragon można przypisać tylko do wydatku.')
    upload = request.files.get('file')
    if not upload:
        raise ValidationError('Wybierz zdjęcie lub plik PDF.')
    mime = upload.mimetype
    if mime not in RECEIPT_TYPES:
        raise ValidationError('Dozwolone są JPG, PNG, WebP i PDF.')
    content = upload.read(MAX_RECEIPT_BYTES + 1)
    if len(content) > MAX_RECEIPT_BYTES:
        raise ValidationError('Paragon może mieć maksymalnie 8 MB.')
    extension, signature = RECEIPT_TYPES[mime]
    if not content.startswith(signature) or (mime == 'image/webp' and content[8:12] != b'WEBP'):
        raise ValidationError('Plik nie zgadza się z wybranym formatem.')
    target_dir = receipt_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f'{uuid4().hex}{extension}'
    target = target_dir / filename
    target.write_bytes(content)
    db = get_db()
    try:
        db.execute('''
            UPDATE budget_entries_v2 SET receipt_filename = ?, receipt_original_name = ?, version=version+1 WHERE id = ?
        ''', (filename, optional_text(upload.filename, 150), entry_id))
        db.commit()
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if row['receipt_filename'] and not db.execute('SELECT 1 FROM budget_receipt_drafts WHERE filename=?', (row['receipt_filename'],)).fetchone():
        (target_dir / row['receipt_filename']).unlink(missing_ok=True)
    return success_response({'entry_id': entry_id, 'has_receipt': True})


@workspace_bp.get('/entries/<int:entry_id>/receipt')
def download_receipt(entry_id):
    row = entry_row(entry_id)
    if not row['receipt_filename']:
        raise NotFoundError('Ten wydatek nie ma załączonego paragonu.')
    return send_from_directory(
        receipt_dir(), row['receipt_filename'],
        as_attachment=True, download_name=row['receipt_original_name'] or row['receipt_filename'],
    )
