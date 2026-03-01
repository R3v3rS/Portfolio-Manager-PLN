from flask import Blueprint, request, jsonify
from budget_service import BudgetService
from database import reset_budget_data

budget_bp = Blueprint('budget', __name__)

@budget_bp.route('/reset', methods=['POST'])
def reset_budget():
    try:
        reset_budget_data()
        return jsonify({'message': 'Budget data reset successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@budget_bp.route('/transactions', methods=['GET'])
def get_transactions():
    account_id = request.args.get('account_id', type=int)
    if not account_id:
        return jsonify({'error': 'account_id is required'}), 400
        
    envelope_id = request.args.get('envelope_id', type=int)
    category_id = request.args.get('category_id', type=int)
    
    try:
        transactions = BudgetService.get_transactions(account_id, envelope_id, category_id)
        return jsonify(transactions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@budget_bp.route('/summary', methods=['GET'])
def get_summary():
    try:
        account_id = request.args.get('account_id', type=int)
        target_month = request.args.get('month') # Optional YYYY-MM
        summary = BudgetService.get_summary(account_id, target_month)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@budget_bp.route('/analytics', methods=['GET'])
def get_analytics():
    account_id = request.args.get('account_id', type=int)
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    if not all([account_id, year, month]):
        return jsonify({'error': 'account_id, year, and month are required'}), 400

    try:
        analytics = BudgetService.get_analytics(account_id, year, month)
        return jsonify(analytics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@budget_bp.route('/income', methods=['POST'])
def add_income():
    data = request.json
    try:
        open_loans = BudgetService.add_income(
            data['account_id'], 
            float(data['amount']), 
            data.get('description', 'Income'),
            data.get('date')
        )
        return jsonify({'message': 'Income added', 'open_loans': open_loans})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/allocate', methods=['POST'])
def allocate():
    data = request.json
    try:
        BudgetService.allocate_money(
            data['envelope_id'], 
            float(data['amount']),
            data.get('date')
        )
        return jsonify({'message': 'Money allocated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/expense', methods=['POST'])
def expense():
    data = request.json
    try:
        BudgetService.spend(
            account_id=data.get('account_id'),
            amount=float(data['amount']), 
            description=data.get('description', 'Expense'),
            envelope_id=data.get('envelope_id'),
            date=data.get('date')
        )
        return jsonify({'message': 'Expense recorded'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/account-transfer', methods=['POST'])
def account_transfer():
    data = request.json
    try:
        BudgetService.transfer_between_accounts(
            from_account_id=data['from_account_id'],
            to_account_id=data['to_account_id'],
            amount=float(data['amount']),
            description=data.get('description', 'Transfer'),
            date=data.get('date'),
            target_envelope_id=data.get('target_envelope_id'),
            source_envelope_id=data.get('source_envelope_id')
        )
        return jsonify({'message': 'Transfer successful'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/transfer-to-portfolio', methods=['POST'])
def transfer_to_portfolio():
    data = request.json
    try:
        BudgetService.transfer_to_investment(
            budget_account_id=data['budget_account_id'],
            portfolio_id=data['portfolio_id'],
            amount=float(data['amount']),
            envelope_id=data.get('envelope_id'),
            description=data.get('description', 'Transfer to Investments'),
            date=data.get('date')
        )
        return jsonify({'message': 'Transfer to Investment Portfolio successful'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/withdraw-from-portfolio', methods=['POST'])
def withdraw_from_portfolio():
    data = request.json
    try:
        BudgetService.withdraw_from_investment(
            portfolio_id=data['portfolio_id'],
            budget_account_id=data['budget_account_id'],
            amount=float(data['amount']),
            description=data.get('description', 'Wypłata z portfela inwestycyjnego'),
            date=data.get('date')
        )
        return jsonify({'message': 'Withdrawal from Investment Portfolio successful'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/borrow', methods=['POST'])
def borrow():
    data = request.json
    try:
        BudgetService.borrow_from_envelope(
            data['source_envelope_id'], 
            float(data['amount']), 
            data['reason'], 
            data.get('due_date')
        )
        return jsonify({'message': 'Borrowed from envelope'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/repay', methods=['POST'])
def repay():
    data = request.json
    try:
        BudgetService.repay_envelope_loan(data['loan_id'], float(data['amount']))
        return jsonify({'message': 'Loan repaid'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/categories', methods=['GET', 'POST'])
def manage_categories():
    db = BudgetService.get_db()
    if request.method == 'GET':
        cats = db.execute("SELECT * FROM envelope_categories").fetchall()
        return jsonify([dict(c) for c in cats])
    else:
        data = request.json
        db.execute("INSERT INTO envelope_categories (name, icon) VALUES (?, ?)", (data['name'], data.get('icon', '📁')))
        db.commit()
        return jsonify({'message': 'Category created'})

@budget_bp.route('/envelopes', methods=['GET', 'POST'])
def manage_envelopes():
    db = BudgetService.get_db()
    if request.method == 'GET':
        account_id = request.args.get('account_id', type=int)
        if account_id:
            envelopes = db.execute("SELECT * FROM envelopes WHERE account_id = ?", (account_id,)).fetchall()
        else:
            envelopes = db.execute("SELECT * FROM envelopes").fetchall()
        return jsonify([dict(e) for e in envelopes])
    else:
        data = request.json
        if 'account_id' not in data:
            return jsonify({'error': 'account_id is required'}), 400
            
        env_type = data.get('type', 'MONTHLY')
        target_month = data.get('target_month')
        
        # If type is MONTHLY, target_month is required (or default to current?)
        if env_type == 'MONTHLY' and not target_month:
             from datetime import date
             today = date.today()
             target_month = f"{today.year}-{today.month:02d}"
             
        db.execute("""
            INSERT INTO envelopes (category_id, account_id, name, icon, target_amount, type, target_month, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
        """, (data['category_id'], data['account_id'], data['name'], data.get('icon', '✉️'), data.get('target_amount'), env_type, target_month))
        db.commit()
        return jsonify({'message': 'Envelope created'})

@budget_bp.route('/envelopes/<int:envelope_id>', methods=['PATCH'])
def update_envelope(envelope_id):
    data = request.json
    try:
        if 'target_amount' in data:
            BudgetService.update_envelope_target(envelope_id, float(data['target_amount']))
        return jsonify({'message': 'Envelope updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/envelopes/close', methods=['POST'])
def close_envelope():
    data = request.json
    try:
        BudgetService.close_envelope(data['envelope_id'])
        return jsonify({'message': 'Envelope closed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/budget/clone', methods=['POST'])
def clone_budget():
    data = request.json
    try:
        BudgetService.clone_budget_for_month(
            data['account_id'],
            data['from_month'],
            data['to_month']
        )
        return jsonify({'message': 'Budget cloned successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@budget_bp.route('/accounts', methods=['GET', 'POST'])
def manage_accounts():
    db = BudgetService.get_db()
    if request.method == 'GET':
        accounts = db.execute("SELECT * FROM budget_accounts").fetchall()
        return jsonify([dict(a) for a in accounts])
    else:
        data = request.json
        db.execute("INSERT INTO budget_accounts (name, balance, currency) VALUES (?, ?, ?)", 
                   (data['name'], data.get('balance', 0.0), data.get('currency', 'PLN')))
        db.commit()
        return jsonify({'message': 'Account created'})
