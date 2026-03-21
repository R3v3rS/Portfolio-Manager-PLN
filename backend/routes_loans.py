from datetime import datetime

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
    if parsed <= 0:
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


@loans_bp.route('/', methods=['POST'])
def create_loan():
    data = require_json_body()

    db = get_db()
    cursor = db.cursor()

    start_date = require_date_string(data, 'start_date')

    cursor.execute(
        '''
        INSERT INTO loans (name, original_amount, duration_months, start_date, installment_type, category)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (
            require_non_empty_string(data, 'name'),
            require_number(data, 'original_amount', positive=True),
            require_positive_int(data, 'duration_months'),
            start_date,
            require_enum_string(data, 'installment_type', VALID_INSTALLMENT_TYPES),
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
            start_date,
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
    ensure_loan_exists(loan_id)
    db = get_db()

    db.execute('DELETE FROM loan_rates WHERE loan_id = ?', (loan_id,))
    db.execute('DELETE FROM loan_overpayments WHERE loan_id = ?', (loan_id,))
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
    ensure_loan_exists(loan_id)
    data = require_json_body()
    overpayment_type = optional_string(data, 'type') or 'REDUCE_TERM'
    if overpayment_type not in VALID_OVERPAYMENT_TYPES:
        raise ValidationError(
            'Field type must be one of: REDUCE_INSTALLMENT, REDUCE_TERM',
            details={'field': 'type'},
        )

    db = get_db()
    db.execute(
        '''
        INSERT INTO loan_overpayments (loan_id, amount, date, type)
        VALUES (?, ?, ?, ?)
        ''',
        (
            loan_id,
            require_number(data, 'amount', positive=True),
            require_date_string(data, 'date'),
            overpayment_type,
        ),
    )
    db.commit()
    return success_response({'message': 'Overpayment added successfully'}, status=201)


@loans_bp.route('/<int:loan_id>/schedule', methods=['GET'])
def get_schedule(loan_id):
    ensure_loan_exists(loan_id)

    simulation_overpayments, monthly_overpayment, monthly_overpayment_strategy = parse_schedule_inputs()

    result = LoanService.generate_amortization_schedule(
        loan_id,
        simulation_overpayments,
        monthly_overpayment,
        monthly_overpayment_strategy,
    )
    return success_response(result)
