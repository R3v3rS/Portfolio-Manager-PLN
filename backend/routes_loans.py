from datetime import date, datetime
import math
import sqlite3

from flask import Blueprint, request

from api.exceptions import ApiError, NotFoundError, ValidationError
from api.response import success_response
from database import get_db
from loan_service import LoanService
from routes_budget_workspace import cents, insert_entry, positive_id
from routes_portfolio_base import (
    optional_string,
    require_json_body,
    require_non_empty_string,
    require_number,
    require_positive_int,
)

loans_bp = Blueprint('loans_bp', __name__)

VALID_INSTALLMENT_TYPES = {'EQUAL', 'DECREASING'}
VALID_OVERPAYMENT_TYPES = {'REDUCE_TERM', 'REDUCE_INSTALLMENT'}
DATE_FORMAT = '%Y-%m-%d'


def ensure_loan_exists(loan_id: int):
    loan = LoanService.get_loan_details(loan_id)
    if not loan:
        raise NotFoundError('Loan not found', details={'loan_id': loan_id})
    return loan


def parse_iso_date(value: str, field: str) -> str:
    try:
        parsed = datetime.strptime(value, DATE_FORMAT).date()
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f'Field {field} must be a valid date in YYYY-MM-DD format',
            details={'field': field},
    ) from exc
    return parsed.isoformat()


def require_date_string(data: dict, field: str) -> str:
    return parse_iso_date(require_non_empty_string(data, field), field)


def require_enum_string(data: dict, field: str, allowed_values: set[str]) -> str:
    value = require_non_empty_string(data, field)
    if value not in allowed_values:
        raise ValidationError(
            f"Field {field} must be one of: {', '.join(sorted(allowed_values))}",
            details={'field': field},
        )
    return value


def parse_positive_float_arg(name: str, *, default: float | None = None) -> float | None:
    value = request.args.get(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'Field {name} must be a number', details={'field': name}) from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValidationError(f'Field {name} must be greater than zero', details={'field': name})
    return parsed


def parse_schedule_inputs():
    sim_amount_raw = request.args.get('sim_amount')
    sim_date_raw = request.args.get('sim_date')
    simulation_overpayments = None

    sim_amount = parse_positive_float_arg('sim_amount') if sim_amount_raw is not None else None
    sim_date = parse_iso_date(sim_date_raw, 'sim_date') if sim_date_raw is not None else None

    if sim_amount_raw is not None and sim_date_raw is None:
        raise ValidationError(
            'Fields sim_amount and sim_date must be provided together',
            details={'field': 'sim_date'},
        )

    if sim_date_raw is not None and sim_amount_raw is None:
        raise ValidationError(
            'Fields sim_amount and sim_date must be provided together',
            details={'field': 'sim_amount'},
        )

    if sim_amount is not None and sim_date is not None:
        simulation_overpayments = [{
            'amount': sim_amount,
            'date': sim_date,
        }]

    monthly_overpayment = parse_positive_float_arg('monthly_overpayment', default=0.0)
    if monthly_overpayment is None:
        monthly_overpayment = 0.0

    monthly_overpayment_strategy = request.args.get('simulated_action', 'REDUCE_TERM')
    if monthly_overpayment_strategy not in VALID_OVERPAYMENT_TYPES:
        raise ValidationError(
            'Field simulated_action must be one of: REDUCE_INSTALLMENT, REDUCE_TERM',
            details={'field': 'simulated_action'},
        )

    return simulation_overpayments, monthly_overpayment, monthly_overpayment_strategy


def loan_budget_entry(db, account_id, amount_cents, description, paid_on, loan_id=None):
    account = db.execute("SELECT id FROM budget_accounts WHERE id = ? AND UPPER(COALESCE(currency,'PLN'))='PLN'", (account_id,)).fetchone()
    if not account:
        raise ValidationError('Wybierz istniejące konto budżetowe w PLN.')
    from loan_budget_service import settings
    configured=settings(db,loan_id)['category_id'] if loan_id else None
    category = db.execute('SELECT id FROM budget_categories_v2 WHERE id=?',(configured,)).fetchone() if configured else db.execute(
        "SELECT id FROM budget_categories_v2 WHERE name = 'Rachunki' COLLATE NOCASE"
    ).fetchone()
    if category:
        category_id = category['id']
    else:
        sort_order = db.execute('SELECT COALESCE(MAX(sort_order), -1) + 1 FROM budget_categories_v2').fetchone()[0]
        category_id = db.execute(
            "INSERT INTO budget_categories_v2 (name, icon, sort_order) VALUES ('Rachunki', 'ReceiptText', ?)",
            (sort_order,),
        ).lastrowid
    return insert_entry(db, {
        'account_id': account_id, 'kind': 'EXPENSE', 'amount_cents': amount_cents,
        'date': paid_on, 'description': description, 'merchant': None,
        'lines': [{'category_id': category_id, 'label': '', 'amount_cents': amount_cents}],
    })


def reverse_budget_entry(db, entry_id):
    if not entry_id:
        return
    entry = db.execute('SELECT account_id, amount_cents FROM budget_entries_v2 WHERE id = ?', (entry_id,)).fetchone()
    if not entry:
        return
    db.execute('UPDATE budget_accounts SET balance = ROUND(balance + ?, 2) WHERE id = ?',
               (entry['amount_cents'] / 100, entry['account_id']))
    db.execute('DELETE FROM budget_entry_lines_v2 WHERE entry_id = ?', (entry_id,))
    db.execute('DELETE FROM budget_entries_v2 WHERE id = ?', (entry_id,))


def optional_budget_account(data):
    value = data.get('account_id')
    return positive_id(value, 'konto') if value not in (None, '') else None


def net_worth_exclusion(data, *, default=None):
    value = data.get('exclude_from_net_worth', default)
    if not isinstance(value, bool):
        raise ValidationError('Pole exclude_from_net_worth musi mieć wartość true lub false.')
    return value


@loans_bp.route('/', methods=['POST'])
def create_loan():
    data = require_json_body()

    db = get_db()
    cursor = db.cursor()

    start_date = require_date_string(data, 'start_date')

    cursor.execute(
        '''
        INSERT INTO loans (name, original_amount, duration_months, start_date, installment_type, category, exclude_from_net_worth)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            require_non_empty_string(data, 'name'),
            require_number(data, 'original_amount', positive=True),
            require_positive_int(data, 'duration_months'),
            start_date,
            require_enum_string(data, 'installment_type', VALID_INSTALLMENT_TYPES),
            optional_string(data, 'category') or 'GOTOWKOWY',
            net_worth_exclusion(data, default=False),
        ),
    )

    loan_id = cursor.lastrowid
    from loan_budget_service import ensure_settings
    ensure_settings(db,loan_id)

    cursor.execute(
        '''
        INSERT INTO loan_rates (loan_id, interest_rate, valid_from_date)
        VALUES (?, ?, ?)
        ''',
        (
            loan_id,
            require_number(data, 'initial_rate', non_negative=True),
            start_date,
        ),
    )

    db.commit()
    return success_response({'message': 'Loan created successfully', 'id': loan_id}, status=201)


@loans_bp.route('/', methods=['GET'])
def list_loans():
    db = get_db()
    loans = db.execute('SELECT * FROM loans').fetchall()
    result = []
    for row in loans:
        loan = dict(row)
        loan['start_date'] = str(loan['start_date'])[:10]
        loan['exclude_from_net_worth'] = bool(loan['exclude_from_net_worth'])
        loan.update(LoanService.get_status(loan['id']))
        result.append(loan)
    return success_response(result)


@loans_bp.put('/<int:loan_id>/net-worth-inclusion')
def update_net_worth_inclusion(loan_id):
    ensure_loan_exists(loan_id)
    excluded = net_worth_exclusion(require_json_body())
    db = get_db()
    db.execute('UPDATE loans SET exclude_from_net_worth = ? WHERE id = ?', (excluded, loan_id))
    db.commit()
    return success_response({'id': loan_id, 'exclude_from_net_worth': excluded})


@loans_bp.put('/<int:loan_id>/budget-settings')
def save_loan_budget_settings(loan_id):
    ensure_loan_exists(loan_id)
    from loan_budget_service import ensure_settings,settings
    from budget_category_service import require_version
    data=require_json_body();db=get_db()
    account_id=optional_budget_account(data)
    category_id=positive_id(data.get('category_id'),'kategorię rat')
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM loan_budget_settings WHERE loan_id=?',(loan_id,)).fetchone()
        require_version(row or {'version':0},data.get('version'),'Ustawienia kredytu')
        if account_id and not db.execute("SELECT 1 FROM budget_accounts WHERE id=? AND UPPER(COALESCE(currency,'PLN'))='PLN'",(account_id,)).fetchone():
            raise ValidationError('Wybierz konto w PLN.')
        if not db.execute('SELECT 1 FROM budget_categories_v2 WHERE id=? AND is_unassigned=0',(category_id,)).fetchone():
            raise ValidationError('Wybierz kategorię rat.')
        ensure_settings(db,loan_id)
        db.execute('UPDATE loan_budget_settings SET account_id=?,category_id=?,version=version+1 WHERE loan_id=?',(account_id,category_id,loan_id))
        db.commit();return success_response(settings(db,loan_id))
    except Exception:db.rollback();raise


@loans_bp.get('/<int:loan_id>/payment-candidates')
def loan_payment_candidates(loan_id):
    ensure_loan_exists(loan_id)
    from loan_budget_service import candidates
    day=require_date_string(dict(request.args),'paid_on')
    amount=cents(request.args.get('amount'))
    account=positive_id(request.args.get('account_id'),'konto')
    return success_response({'items':candidates(get_db(),account,day,amount)})


@loans_bp.route('/<int:loan_id>', methods=['DELETE'])
def delete_loan(loan_id):
    ensure_loan_exists(loan_id)
    db = get_db()

    db.execute('DELETE FROM loan_rates WHERE loan_id = ?', (loan_id,))
    db.execute('DELETE FROM loan_installment_payments WHERE loan_id = ?', (loan_id,))
    db.execute('DELETE FROM loan_balance_checks WHERE loan_id = ?', (loan_id,))
    db.execute('DELETE FROM loan_overpayments WHERE loan_id = ?', (loan_id,))
    db.execute('DELETE FROM loan_budget_settings WHERE loan_id = ?', (loan_id,))
    db.execute('DELETE FROM loans WHERE id = ?', (loan_id,))

    db.commit()
    return success_response({'message': 'Loan deleted successfully'})


@loans_bp.route('/<int:loan_id>/rates', methods=['POST'])
def add_rate(loan_id):
    ensure_loan_exists(loan_id)
    data = require_json_body()
    db = get_db()
    db.execute(
        '''
        INSERT INTO loan_rates (loan_id, interest_rate, valid_from_date)
        VALUES (?, ?, ?)
        ''',
        (
            loan_id,
            require_number(data, 'interest_rate', non_negative=True),
            require_date_string(data, 'valid_from_date'),
        ),
    )
    db.commit()
    return success_response({'message': 'Rate added successfully'}, status=201)


@loans_bp.route('/<int:loan_id>/overpayments', methods=['POST'])
def add_overpayment(loan_id):
    loan = ensure_loan_exists(loan_id)
    data = require_json_body()
    overpayment_type = optional_string(data, 'type') or 'REDUCE_TERM'
    if overpayment_type not in VALID_OVERPAYMENT_TYPES:
        raise ValidationError(
            'Field type must be one of: REDUCE_INSTALLMENT, REDUCE_TERM',
            details={'field': 'type'},
        )

    amount_cents = cents(require_number(data, 'amount', positive=True))
    overpayment_date = require_date_string(data, 'date')
    if overpayment_date < str(loan['start_date'])[:10]:
        raise ValidationError('Nadpłata nie może poprzedzać początku kredytu.')
    if overpayment_date > date.today().isoformat():
        raise ValidationError('Przyszłą nadpłatę sprawdź w symulatorze; zapisz ją po wykonaniu.')
    projected = LoanService.get_status(loan_id, as_of=overpayment_date)['estimated_balance']
    if amount_cents > round(projected * 100):
        raise ValidationError('Nadpłata przekracza szacunkowy kapitał pozostały w tym dniu.')
    account_id = optional_budget_account(data)
    db = get_db()
    from loan_budget_service import ensure_settings, link_expense, candidates
    if data.get('existing_entry_id') is not None and not account_id:
        raise ValidationError('Wybierz konto istniejącej płatności.')
    try:
        db.execute('BEGIN IMMEDIATE')
        ensure_settings(db,loan_id)
        before = None
        if data.get('existing_entry_id') is not None:
            budget_entry_id,before = link_expense(db,loan_id,data,account_id,overpayment_date,amount_cents)
        else:
            if account_id and candidates(db,account_id,overpayment_date,amount_cents) and data.get('confirm_new_expense') is not True:
                raise ApiError('loan_existing_payment','Znaleziono podobny wydatek. Powiąż istniejącą płatność albo potwierdź odrębną nadpłatę.',status=409)
            budget_entry_id = loan_budget_entry(
                db, account_id, amount_cents, f'Nadpłata kredytu: {loan["name"]}', overpayment_date,loan_id
            ) if account_id else None
        cursor = db.execute('''INSERT INTO loan_overpayments
            (loan_id, amount, date, type, budget_entry_id, budget_entry_created, linked_entry_before)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (loan_id,amount_cents/100,overpayment_date,overpayment_type,budget_entry_id,int(before is None),before))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return success_response({'message': 'Overpayment added successfully', 'id': cursor.lastrowid}, status=201)


@loans_bp.route('/<int:loan_id>/overpayments/<int:overpayment_id>', methods=['DELETE'])
def delete_overpayment(loan_id, overpayment_id):
    ensure_loan_exists(loan_id)
    db = get_db()
    row = db.execute('SELECT * FROM loan_overpayments WHERE id = ? AND loan_id = ?',
                     (overpayment_id, loan_id)).fetchone()
    if not row:
        raise NotFoundError('Nadpłata nie istnieje.')
    from loan_budget_service import restore_expense
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM loan_overpayments WHERE id = ?', (overpayment_id,))
        if not row['budget_entry_created']:
            restore_expense(db,row)
        else:
            reverse_budget_entry(db, row['budget_entry_id'])
        db.commit()
    except Exception:
        db.rollback()
        raise
    return success_response({'deleted': overpayment_id})


@loans_bp.route('/<int:loan_id>/payments', methods=['POST'])
def record_installment(loan_id):
    loan=ensure_loan_exists(loan_id);data=require_json_body()
    month=require_positive_int(data,'installment_month');paid_on=require_date_string(data,'paid_on')
    if paid_on<str(loan['start_date'])[:10] or paid_on>date.today().isoformat():
        raise ValidationError('Data spłaty musi mieścić się między początkiem kredytu a dziś.')
    from loan_budget_service import candidates,link_expense,ensure_settings
    db=get_db();account=optional_budget_account(data)
    applying=data.get('apply_to_budget') is True
    if applying and not account:raise ValidationError('Wybierz konto płatności.')
    try:
        db.execute('BEGIN IMMEDIATE');ensure_settings(db,loan_id)
        previous=db.execute('SELECT * FROM loan_installment_payments WHERE loan_id=? AND installment_month=?',(loan_id,month)).fetchone()
        if applying:
            if not previous or previous['id']!=positive_id(data.get('payment_id'),'zapis spłaty'):
                raise NotFoundError('Nie znaleziono zapisanej spłaty.')
            amount=cents(data.get('amount'))
            if (previous['paid_on'],previous['amount_cents'])!=(paid_on,amount):
                raise ValidationError('Zapis spłaty zmienił się. Odśwież dane.')
        else:
            if previous:raise ValidationError('Ta rata jest już zapisana jako opłacona.')
            schedule=LoanService.generate_amortization_schedule(loan_id)['simulation']['schedule']
            installment=next((r for r in schedule if r['month']==month and r['installment']>0 and not r.get('is_mid_month')),None)
            if not installment:raise ValidationError('Nie znaleziono raty w harmonogramie.')
            amount=cents(data.get('amount',installment['installment']))
        if previous and previous['budget_entry_id']:
            entry=db.execute('SELECT account_id FROM budget_entries_v2 WHERE id=?',(previous['budget_entry_id'],)).fetchone()
            if not entry or entry['account_id']!=account or (data.get('existing_entry_id') and data['existing_entry_id']!=previous['budget_entry_id']):
                raise ValidationError('Ta spłata jest już rozliczona. Nie pomniejszamy salda ponownie.')
            return success_response({'id':previous['id'],'budget_entry_id':previous['budget_entry_id']},status=201)
        entry_id=None;entry_before=None;created=True
        if data.get('existing_entry_id'):
            if not account:raise ValidationError('Wybierz konto istniejącego wydatku.')
            entry_id,entry_before=link_expense(db,loan_id,data,account,paid_on,amount);created=False
        elif account:
            if candidates(db,account,paid_on,amount) and data.get('confirm_new_expense') is not True:
                raise ValidationError('Znaleziono możliwą płatność w budżecie. Powiąż istniejący wydatek albo potwierdź, że to osobna płatność.')
            entry_id=loan_budget_entry(db,account,amount,f'Rata kredytu: {loan["name"]} ({month}/{loan["duration_months"]})',paid_on,loan_id)
        if applying:
            db.execute('UPDATE loan_installment_payments SET budget_entry_id=?,budget_entry_created=?,linked_entry_before=? WHERE id=?',
                (entry_id,int(created),entry_before,previous['id']))
            payment_id=previous['id']
        else:
            payment_id=db.execute('''INSERT INTO loan_installment_payments
                (loan_id,installment_month,due_date,paid_on,amount_cents,budget_entry_id,budget_entry_created,linked_entry_before)
                VALUES(?,?,?,?,?,?,?,?)''',(loan_id,month,installment['date'],paid_on,amount,entry_id,int(created),entry_before)).lastrowid
        if account:
            # The first booked payment establishes a default for future raty.
            # An explicitly configured account remains unchanged by a one-off payment elsewhere.
            db.execute('UPDATE loan_budget_settings SET account_id=?,version=version+1 WHERE loan_id=? AND account_id IS NULL',(account,loan_id))
        db.commit();return success_response({'id':payment_id,'budget_entry_id':entry_id},status=201)
    except Exception:db.rollback();raise
    finally:
        if db.in_transaction:db.rollback()


@loans_bp.route('/<int:loan_id>/payments/<int:payment_id>', methods=['DELETE'])
def delete_installment(loan_id, payment_id):
    ensure_loan_exists(loan_id)
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('''
            SELECT * FROM loan_installment_payments WHERE id = ? AND loan_id = ?
        ''', (payment_id, loan_id)).fetchone()
        if not row:
            raise NotFoundError('Zapis raty nie istnieje.')
        if row['budget_entry_id'] and db.execute('SELECT 1 FROM budget_purchase_refunds WHERE purchase_entry_id=?',(row['budget_entry_id'],)).fetchone():
            raise ValidationError('Najpierw cofnij zwrot powiązany z tym wydatkiem.')
        db.execute('DELETE FROM loan_installment_payments WHERE id = ?', (payment_id,))
        if row['budget_entry_created']:
            reverse_budget_entry(db, row['budget_entry_id'])
        else:
            from loan_budget_service import restore_expense
            restore_expense(db,row)
        db.commit()
        return success_response({'deleted': payment_id})
    except Exception:
        db.rollback()
        raise


@loans_bp.route('/<int:loan_id>/balance-checks', methods=['POST'])
def record_balance_check(loan_id):
    loan = ensure_loan_exists(loan_id)
    data = require_json_body()
    checked_on = require_date_string(data, 'checked_on')
    if checked_on < str(loan['start_date'])[:10] or checked_on > date.today().isoformat():
        raise ValidationError('Data salda musi mieścić się między początkiem kredytu a dziś.')
    balance_cents = cents(data.get('balance'), 'Saldo', allow_zero=True)
    db = get_db()
    cursor = db.execute('''
        INSERT INTO loan_balance_checks (loan_id, balance_cents, checked_on) VALUES (?, ?, ?)
    ''', (loan_id, balance_cents, checked_on))
    db.commit()
    return success_response({'id': cursor.lastrowid}, status=201)


@loans_bp.route('/<int:loan_id>/schedule', methods=['GET'])
def get_schedule(loan_id):
    ensure_loan_exists(loan_id)

    simulation_overpayments, monthly_overpayment, monthly_overpayment_strategy = parse_schedule_inputs()

    if simulation_overpayments:
        simulated = simulation_overpayments[0]
        estimated = LoanService.get_status(loan_id, as_of=simulated['date'])['estimated_balance']
        if simulated['amount'] > estimated + 0.005:
            raise ValidationError('Symulowana nadpłata przekracza pozostały kapitał.')
    result = LoanService.generate_amortization_schedule(
        loan_id,
        simulation_overpayments,
        monthly_overpayment,
        monthly_overpayment_strategy,
    )
    db = get_db()
    result['status'] = LoanService.get_status(loan_id)
    from loan_budget_service import settings
    result['budget_settings']=settings(db,loan_id)
    result['payments_list'] = [
        {
            'id': row['id'], 'installment_month': row['installment_month'],
            'due_date': row['due_date'], 'paid_on': row['paid_on'],
            'amount': row['amount_cents'] / 100, 'budget_linked': bool(row['budget_entry_id']),
            'budget_entry_created':bool(row['budget_entry_created']),
        }
        for row in db.execute('''
            SELECT * FROM loan_installment_payments WHERE loan_id = ?
            ORDER BY installment_month DESC
        ''', (loan_id,)).fetchall()
    ]
    result['rates_list'] = LoanService.get_loan_rates(loan_id)
    result['balance_checks_list'] = [
        {'id': row['id'], 'balance': row['balance_cents'] / 100, 'checked_on': row['checked_on']}
        for row in db.execute('''
            SELECT * FROM loan_balance_checks WHERE loan_id = ? ORDER BY checked_on DESC, id DESC
        ''', (loan_id,)).fetchall()
    ]
    return success_response(result)
