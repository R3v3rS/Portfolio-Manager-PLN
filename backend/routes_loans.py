from flask import Blueprint, request

from api_response import error_response, success_response
from database import get_db
from loan_service import LoanService

loans_bp = Blueprint('loans_bp', __name__)

@loans_bp.route('/', methods=['POST'])
def create_loan():
    data = request.get_json(silent=True) or {}
    required_fields = ['name', 'original_amount', 'duration_months', 'start_date', 'installment_type', 'initial_rate']

    if not data:
        return error_response('Invalid JSON body', status_code=400, code='invalid_json')

    for field in required_fields:
        if field not in data:
            return error_response(f'Missing field: {field}', status_code=400, code='missing_field', details={'field': field})

    try:
        db = get_db()
        cursor = db.cursor()
        
        # Insert Loan
        cursor.execute('''
            INSERT INTO loans (name, original_amount, duration_months, start_date, installment_type, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data['original_amount'],
            data['duration_months'],
            data['start_date'],
            data['installment_type'],
            data.get('category', 'GOTOWKOWY')
        ))
        
        loan_id = cursor.lastrowid
        
        # Insert Initial Rate
        cursor.execute('''
            INSERT INTO loan_rates (loan_id, interest_rate, valid_from_date)
            VALUES (?, ?, ?)
        ''', (
            loan_id,
            data['initial_rate'],
            data['start_date']
        ))
        
        db.commit()
        
        return success_response({'message': 'Loan created successfully', 'id': loan_id}, 201)
        
    except Exception as e:
        return error_response(str(e), status_code=500, code='loan_error')

@loans_bp.route('/', methods=['GET'])
def list_loans():
    db = get_db()
    loans = db.execute('SELECT * FROM loans').fetchall()
    return success_response([dict(l) for l in loans])

@loans_bp.route('/<int:loan_id>', methods=['DELETE'])
def delete_loan(loan_id):
    try:
        db = get_db()
        
        # Check if loan exists
        loan = db.execute('SELECT * FROM loans WHERE id = ?', (loan_id,)).fetchone()
        if not loan:
            return error_response('Loan not found', status_code=404, code='loan_not_found')
            
        # Delete related data first
        db.execute('DELETE FROM loan_rates WHERE loan_id = ?', (loan_id,))
        db.execute('DELETE FROM loan_overpayments WHERE loan_id = ?', (loan_id,))
        
        # Delete loan
        db.execute('DELETE FROM loans WHERE id = ?', (loan_id,))
        
        db.commit()
        return success_response({'message': 'Loan deleted successfully'}, 200)
    except Exception as e:
        return error_response(str(e), status_code=500, code='loan_error')

@loans_bp.route('/<int:loan_id>/rates', methods=['POST'])
def add_rate(loan_id):
    data = request.get_json(silent=True) or {}
    if not data:
        return error_response('Invalid JSON body', status_code=400, code='invalid_json')

    if 'interest_rate' not in data or 'valid_from_date' not in data:
        return error_response('Missing interest_rate or valid_from_date', status_code=400, code='missing_field')
        
    try:
        db = get_db()
        db.execute('''
            INSERT INTO loan_rates (loan_id, interest_rate, valid_from_date)
            VALUES (?, ?, ?)
        ''', (loan_id, data['interest_rate'], data['valid_from_date']))
        db.commit()
        return success_response({'message': 'Rate added successfully'}, 201)
    except Exception as e:
        return error_response(str(e), status_code=500, code='loan_error')

@loans_bp.route('/<int:loan_id>/overpayments', methods=['POST'])
def add_overpayment(loan_id):
    data = request.get_json(silent=True) or {}
    if not data:
        return error_response('Invalid JSON body', status_code=400, code='invalid_json')
        
    if 'amount' not in data or 'date' not in data:
        return error_response('Missing amount or date', status_code=400, code='missing_field')
        
    overpayment_type = data.get('type', 'REDUCE_TERM')
    if overpayment_type not in ['REDUCE_TERM', 'REDUCE_INSTALLMENT']:
        overpayment_type = 'REDUCE_TERM'
        
    try:
        db = get_db()
        db.execute('''
            INSERT INTO loan_overpayments (loan_id, amount, date, type)
            VALUES (?, ?, ?, ?)
        ''', (loan_id, data['amount'], data['date'], overpayment_type))
        db.commit()
        return success_response({'message': 'Overpayment added successfully'}, 201)
    except Exception as e:
        return error_response(str(e), status_code=500, code='loan_error')

@loans_bp.route('/<int:loan_id>/schedule', methods=['GET'])
def get_schedule(loan_id):
    # Check if loan exists
    loan = LoanService.get_loan_details(loan_id)
    if not loan:
        return error_response('Loan not found', status_code=404, code='loan_not_found')
        
    # Check for simulation params in query string
    # Example: ?sim_amount=1000&sim_date=2025-01-01
    simulation_overpayments = None
    sim_amount = request.args.get('sim_amount')
    sim_date = request.args.get('sim_date')
    
    monthly_overpayment = float(request.args.get('monthly_overpayment', 0.0))
    monthly_overpayment_strategy = request.args.get('simulated_action', 'REDUCE_TERM')

    if sim_amount and sim_date:
        simulation_overpayments = [{
            'amount': float(sim_amount),
            'date': sim_date
        }]
    
    try:
        result = LoanService.generate_amortization_schedule(
            loan_id, 
            simulation_overpayments, 
            monthly_overpayment,
            monthly_overpayment_strategy
        )
        return success_response(result)
    except Exception as e:
        return error_response(str(e), status_code=500, code='loan_error')
