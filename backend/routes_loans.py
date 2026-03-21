from flask import Blueprint, request

from api.exceptions import NotFoundError, ValidationError
from api.response import success_response
from database import get_db
from loan_service import LoanService
from routes_portfolio_base import (
    optional_string,
    require_json_body,
    require_non_empty_string,
    require_number,
    require_positive_int,
)

loans_bp = Blueprint('loans_bp', __name__)


def parse_optional_float_arg(name: str, *, default: float | None = None) -> float | None:
    value = request.args.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f'Field {name} must be a number', details={'field': name}) from exc


@loans_bp.route('/', methods=['POST'])
def create_loan():
    data = require_json_body()

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        '''
        INSERT INTO loans (name, original_amount, duration_months, start_date, installment_type, category)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (
            require_non_empty_string(data, 'name'),
            require_number(data, 'original_amount', positive=True),
            require_positive_int(data, 'duration_months'),
            require_non_empty_string(data, 'start_date'),
            require_non_empty_string(data, 'installment_type'),
            optional_string(data, 'category') or 'GOTOWKOWY',
        ),
    )

    loan_id = cursor.lastrowid

    cursor.execute(
        '''
        INSERT INTO loan_rates (loan_id, interest_rate, valid_from_date)
        VALUES (?, ?, ?)
        ''',
        (
            loan_id,
            require_number(data, 'initial_rate', non_negative=True),
            require_non_empty_string(data, 'start_date'),
        ),
    )

    db.commit()
    return success_response({'message': 'Loan created successfully', 'id': loan_id}, status=201)


@loans_bp.route('/', methods=['GET'])
def list_loans():
    db = get_db()
    loans = db.execute('SELECT * FROM loans').fetchall()
    return success_response([dict(l) for l in loans])


@loans_bp.route('/<int:loan_id>', methods=['DELETE'])
def delete_loan(loan_id):
    db = get_db()

    loan = db.execute('SELECT * FROM loans WHERE id = ?', (loan_id,)).fetchone()
    if not loan:
        raise NotFoundError('Loan not found')

    db.execute('DELETE FROM loan_rates WHERE loan_id = ?', (loan_id,))
    db.execute('DELETE FROM loan_overpayments WHERE loan_id = ?', (loan_id,))
    db.execute('DELETE FROM loans WHERE id = ?', (loan_id,))

    db.commit()
    return success_response({'message': 'Loan deleted successfully'})


@loans_bp.route('/<int:loan_id>/rates', methods=['POST'])
def add_rate(loan_id):
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
            require_non_empty_string(data, 'valid_from_date'),
        ),
    )
    db.commit()
    return success_response({'message': 'Rate added successfully'}, status=201)


@loans_bp.route('/<int:loan_id>/overpayments', methods=['POST'])
def add_overpayment(loan_id):
    data = require_json_body()
    overpayment_type = optional_string(data, 'type') or 'REDUCE_TERM'
    if overpayment_type not in ['REDUCE_TERM', 'REDUCE_INSTALLMENT']:
        overpayment_type = 'REDUCE_TERM'

    db = get_db()
    db.execute(
        '''
        INSERT INTO loan_overpayments (loan_id, amount, date, type)
        VALUES (?, ?, ?, ?)
        ''',
        (
            loan_id,
            require_number(data, 'amount', positive=True),
            require_non_empty_string(data, 'date'),
            overpayment_type,
        ),
    )
    db.commit()
    return success_response({'message': 'Overpayment added successfully'}, status=201)


@loans_bp.route('/<int:loan_id>/schedule', methods=['GET'])
def get_schedule(loan_id):
    loan = LoanService.get_loan_details(loan_id)
    if not loan:
        raise NotFoundError('Loan not found')

    simulation_overpayments = None
    sim_amount = parse_optional_float_arg('sim_amount')
    sim_date = request.args.get('sim_date')

    monthly_overpayment = parse_optional_float_arg('monthly_overpayment', default=0.0) or 0.0
    monthly_overpayment_strategy = request.args.get('simulated_action', 'REDUCE_TERM')

    if sim_amount is not None and sim_date:
        simulation_overpayments = [{
            'amount': sim_amount,
            'date': sim_date,
        }]

    result = LoanService.generate_amortization_schedule(
        loan_id,
        simulation_overpayments,
        monthly_overpayment,
        monthly_overpayment_strategy,
    )
    return success_response(result)
