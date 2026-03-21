from datetime import date as date_cls

from flask import Blueprint, request

from api.exceptions import NotFoundError, ValidationError
from api.response import success_response
from budget_service import BudgetService
from database import reset_budget_data
from routes_portfolio_base import (
    optional_number,
    optional_string,
    require_json_body,
    require_non_empty_string,
    require_number,
    require_positive_int,
)

budget_bp = Blueprint('budget', __name__)


NOT_FOUND_MESSAGES = {
    'Budget Account not found',
    'Envelope not found',
    'Investment Portfolio not found',
    'Loan not found',
    'Source envelope not found',
    'Target envelope not found',
}


TARGET_AMOUNT_ERRORS = {
    'Target amount must be positive',
}


TARGET_MONTHLESS_ENVELOPE_TYPES = {'MONTHLY'}


def raise_budget_validation_error(error: ValueError):
    message = str(error)
    if message in NOT_FOUND_MESSAGES:
        raise NotFoundError(message) from error
    if message in TARGET_AMOUNT_ERRORS:
        raise ValidationError(message, details={'field': 'target_amount'}) from error
    raise ValidationError(message) from error


def require_query_positive_int(field: str) -> int:
    value = request.args.get(field)
    return require_positive_int({field: value}, field)


def optional_query_positive_int(field: str) -> int | None:
    value = request.args.get(field)
    if value is None:
        return None
    return require_positive_int({field: value}, field)


def optional_body_positive_int(data: dict, field: str) -> int | None:
    if data.get(field) is None:
        return None
    return require_positive_int(data, field)


@budget_bp.route('/reset', methods=['POST'])
def reset_budget():
    reset_budget_data()
    return success_response({'message': 'Budget data reset successfully'})


@budget_bp.route('/transactions', methods=['GET'])
def get_transactions():
    transactions = BudgetService.get_transactions(
        require_query_positive_int('account_id'),
        optional_query_positive_int('envelope_id'),
        optional_query_positive_int('category_id'),
    )
    return success_response(transactions)


@budget_bp.route('/summary', methods=['GET'])
def get_summary():
    account_id = optional_query_positive_int('account_id')
    target_month = request.args.get('month')
    summary = BudgetService.get_summary(account_id, target_month)
    return success_response(summary)


@budget_bp.route('/analytics', methods=['GET'])
def get_analytics():
    analytics = BudgetService.get_analytics(
        require_query_positive_int('account_id'),
        require_query_positive_int('year'),
        require_query_positive_int('month'),
    )
    return success_response(analytics)


@budget_bp.route('/income', methods=['POST'])
def add_income():
    data = require_json_body()
    open_loans = BudgetService.add_income(
        require_positive_int(data, 'account_id'),
        require_number(data, 'amount', positive=True),
        optional_string(data, 'description') or 'Income',
        optional_string(data, 'date'),
    )
    return success_response({'message': 'Income added', 'open_loans': open_loans})


@budget_bp.route('/allocate', methods=['POST'])
def allocate():
    data = require_json_body()
    try:
        BudgetService.allocate_money(
            require_positive_int(data, 'envelope_id'),
            require_number(data, 'amount', positive=True),
            optional_string(data, 'date'),
        )
    except ValueError as error:
        raise_budget_validation_error(error)
    return success_response({'message': 'Money allocated'})


@budget_bp.route('/expense', methods=['POST'])
def expense():
    data = require_json_body()
    try:
        BudgetService.spend(
            account_id=require_positive_int(data, 'account_id'),
            amount=require_number(data, 'amount', positive=True),
            description=optional_string(data, 'description') or 'Expense',
            envelope_id=optional_body_positive_int(data, 'envelope_id'),
            date=optional_string(data, 'date'),
        )
    except ValueError as error:
        raise_budget_validation_error(error)
    return success_response({'message': 'Expense recorded'})


@budget_bp.route('/account-transfer', methods=['POST'])
def account_transfer():
    data = require_json_body()
    try:
        BudgetService.transfer_between_accounts(
            from_account_id=require_positive_int(data, 'from_account_id'),
            to_account_id=require_positive_int(data, 'to_account_id'),
            amount=require_number(data, 'amount', positive=True),
            description=optional_string(data, 'description') or 'Transfer',
            date=optional_string(data, 'date'),
            target_envelope_id=optional_body_positive_int(data, 'target_envelope_id'),
            source_envelope_id=optional_body_positive_int(data, 'source_envelope_id'),
        )
    except ValueError as error:
        raise_budget_validation_error(error)
    return success_response({'message': 'Transfer successful'})


@budget_bp.route('/transfer-to-portfolio', methods=['POST'])
def transfer_to_portfolio():
    data = require_json_body()
    try:
        BudgetService.transfer_to_investment(
            budget_account_id=require_positive_int(data, 'budget_account_id'),
            portfolio_id=require_positive_int(data, 'portfolio_id'),
            amount=require_number(data, 'amount', positive=True),
            envelope_id=optional_body_positive_int(data, 'envelope_id'),
            description=optional_string(data, 'description') or 'Transfer to Investments',
            date=optional_string(data, 'date'),
        )
    except ValueError as error:
        raise_budget_validation_error(error)
    return success_response({'message': 'Transfer to Investment Portfolio successful'})


@budget_bp.route('/withdraw-from-portfolio', methods=['POST'])
def withdraw_from_portfolio():
    data = require_json_body()
    try:
        BudgetService.withdraw_from_investment(
            portfolio_id=require_positive_int(data, 'portfolio_id'),
            budget_account_id=require_positive_int(data, 'budget_account_id'),
            amount=require_number(data, 'amount', positive=True),
            description=optional_string(data, 'description') or 'Wypłata z portfela inwestycyjnego',
            date=optional_string(data, 'date'),
        )
    except ValueError as error:
        raise_budget_validation_error(error)
    return success_response({'message': 'Withdrawal from Investment Portfolio successful'})


@budget_bp.route('/borrow', methods=['POST'])
def borrow():
    data = require_json_body()
    BudgetService.borrow_from_envelope(
        require_positive_int(data, 'source_envelope_id'),
        require_number(data, 'amount', positive=True),
        require_non_empty_string(data, 'reason'),
        optional_string(data, 'due_date'),
    )
    return success_response({'message': 'Borrowed from envelope'})


@budget_bp.route('/repay', methods=['POST'])
def repay():
    data = require_json_body()
    try:
        BudgetService.repay_envelope_loan(
            require_positive_int(data, 'loan_id'),
            require_number(data, 'amount', positive=True),
        )
    except ValueError as error:
        raise_budget_validation_error(error)
    return success_response({'message': 'Loan repaid'})


@budget_bp.route('/categories', methods=['GET', 'POST'])
def manage_categories():
    db = BudgetService.get_db()
    if request.method == 'GET':
        cats = db.execute('SELECT * FROM envelope_categories').fetchall()
        return success_response([dict(c) for c in cats])

    data = require_json_body()
    db.execute(
        'INSERT INTO envelope_categories (name, icon) VALUES (?, ?)',
        (require_non_empty_string(data, 'name'), optional_string(data, 'icon') or '📁'),
    )
    db.commit()
    return success_response({'message': 'Category created'})


@budget_bp.route('/envelopes', methods=['GET', 'POST'])
def manage_envelopes():
    db = BudgetService.get_db()
    if request.method == 'GET':
        account_id = optional_query_positive_int('account_id')
        if account_id:
            envelopes = db.execute('SELECT * FROM envelopes WHERE account_id = ?', (account_id,)).fetchall()
        else:
            envelopes = db.execute('SELECT * FROM envelopes').fetchall()
        return success_response([dict(e) for e in envelopes])

    data = require_json_body()
    env_type = (optional_string(data, 'type') or 'MONTHLY').upper()
    target_month = optional_string(data, 'target_month')

    if env_type in TARGET_MONTHLESS_ENVELOPE_TYPES and not target_month:
        today = date_cls.today()
        target_month = f'{today.year}-{today.month:02d}'

    db.execute(
        '''
        INSERT INTO envelopes (category_id, account_id, name, icon, target_amount, type, target_month, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
        ''',
        (
            require_positive_int(data, 'category_id'),
            require_positive_int(data, 'account_id'),
            require_non_empty_string(data, 'name'),
            optional_string(data, 'icon') or '✉️',
            optional_number(data, 'target_amount', default=None, non_negative=True),
            env_type,
            target_month,
        ),
    )
    db.commit()
    return success_response({'message': 'Envelope created'})


@budget_bp.route('/envelopes/<int:envelope_id>', methods=['PATCH'])
def update_envelope(envelope_id):
    data = require_json_body()
    has_target = 'target_amount' in data
    has_name = 'name' in data

    if not has_target and not has_name:
        raise ValidationError('Nothing to update. Provide target_amount and/or name.')

    try:
        BudgetService.update_envelope_target(
            envelope_id,
            require_number(data, 'target_amount', non_negative=True) if has_target else None,
            require_non_empty_string(data, 'name') if has_name else None,
        )
    except ValueError as error:
        raise_budget_validation_error(error)

    return success_response({'message': 'Envelope updated'})


@budget_bp.route('/envelopes/close', methods=['POST'])
def close_envelope():
    data = require_json_body()
    try:
        BudgetService.close_envelope(require_positive_int(data, 'envelope_id'))
    except ValueError as error:
        raise_budget_validation_error(error)
    return success_response({'message': 'Envelope closed'})


@budget_bp.route('/budget/clone', methods=['POST'])
def clone_budget():
    data = require_json_body()
    try:
        BudgetService.clone_budget_for_month(
            require_positive_int(data, 'account_id'),
            require_non_empty_string(data, 'from_month'),
            require_non_empty_string(data, 'to_month'),
        )
    except ValueError as error:
        raise_budget_validation_error(error)
    return success_response({'message': 'Budget cloned successfully'})


@budget_bp.route('/accounts', methods=['GET', 'POST'])
def manage_accounts():
    db = BudgetService.get_db()
    if request.method == 'GET':
        accounts = db.execute('SELECT * FROM budget_accounts').fetchall()
        return success_response([dict(a) for a in accounts])

    data = require_json_body()
    db.execute(
        'INSERT INTO budget_accounts (name, balance, currency) VALUES (?, ?, ?)',
        (
            require_non_empty_string(data, 'name'),
            optional_number(data, 'balance', default=0.0, non_negative=True),
            optional_string(data, 'currency') or 'PLN',
        ),
    )
    db.commit()
    return success_response({'message': 'Account created'})
