from flask import current_app, request
from database import get_db
from portfolio_service import PortfolioService
from api.response import success_response
from api.exceptions import ApiError, NotFoundError, ValidationError
from job_registry import job_registry
import threading
from routes_portfolio_base import (
    portfolio_bp,
    optional_bool,
    optional_number,
    optional_string,
    raise_portfolio_validation_error,
    require_json_body,
    require_non_empty_string,
    require_number,
    require_positive_int,
)


@portfolio_bp.route('/deposit', methods=['POST'])
def deposit():
    data = require_json_body()
    try:
        PortfolioService.deposit_cash(
            require_positive_int(data, 'portfolio_id'),
            require_number(data, 'amount', positive=True),
            optional_string(data, 'date'),
            sub_portfolio_id=optional_number(data, 'sub_portfolio_id')
        )
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Deposit successful'})


@portfolio_bp.route('/withdraw', methods=['POST'])
def withdraw():
    data = require_json_body()
    try:
        PortfolioService.withdraw_cash(
            require_positive_int(data, 'portfolio_id'),
            require_number(data, 'amount', positive=True),
            optional_string(data, 'date'),
            sub_portfolio_id=optional_number(data, 'sub_portfolio_id')
        )
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Withdrawal successful'})


@portfolio_bp.route('/buy', methods=['POST'])
def buy():
    data = require_json_body()
    try:
        PortfolioService.buy_stock(
            require_positive_int(data, 'portfolio_id'),
            require_non_empty_string(data, 'ticker'),
            require_number(data, 'quantity', positive=True),
            require_number(data, 'price', positive=True),
            optional_string(data, 'date'),
            optional_number(data, 'commission', default=0.0, non_negative=True),
            optional_bool(data, 'auto_fx_fees', default=False),
            sub_portfolio_id=optional_number(data, 'sub_portfolio_id')
        )
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Buy successful'})


@portfolio_bp.route('/sell', methods=['POST'])
def sell():
    data = require_json_body()
    try:
        PortfolioService.sell_stock(
            require_positive_int(data, 'portfolio_id'),
            require_non_empty_string(data, 'ticker'),
            require_number(data, 'quantity', positive=True),
            require_number(data, 'price', positive=True),
            optional_string(data, 'date'),
            sub_portfolio_id=optional_number(data, 'sub_portfolio_id')
        )
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Sell successful'})


@portfolio_bp.route('/transactions/<int:portfolio_id>', methods=['GET'])
def get_transactions(portfolio_id):
    ticker = request.args.get('ticker')
    transactions = PortfolioService.get_transactions(portfolio_id, ticker=ticker)
    return success_response({'transactions': transactions})


@portfolio_bp.route('/transactions/all', methods=['GET'])
def get_all_transactions():
    ticker = request.args.get('ticker')
    transactions = PortfolioService.get_all_transactions(ticker=ticker)
    return success_response({'transactions': transactions})


@portfolio_bp.route('/dividend', methods=['POST'])
def record_dividend():
    data = require_json_body()
    try:
        PortfolioService.record_dividend(
            require_positive_int(data, 'portfolio_id'),
            require_non_empty_string(data, 'ticker'),
            require_number(data, 'amount', positive=True),
            require_non_empty_string(data, 'date'),
            sub_portfolio_id=optional_number(data, 'sub_portfolio_id')
        )
    except ValueError as error:
        raise_portfolio_validation_error(error)
    return success_response({'message': 'Dividend recorded successfully'}, status=201)


@portfolio_bp.route('/transactions/<int:transaction_id>/assign', methods=['PUT'])
def assign_transaction(transaction_id):
    data = require_json_body()
    sub_portfolio_id = data.get('sub_portfolio_id') # Can be None to unassign

    # Resolve portfolio_id for the job
    db = get_db()
    tx = db.execute('SELECT portfolio_id FROM transactions WHERE id = ?', (transaction_id,)).fetchone()
    if not tx:
        raise NotFoundError('Transaction not found')
    portfolio_id = tx['portfolio_id']

    # Start async job to re-calculate history after assignment
    job_id = job_registry.create_job()
    app = current_app._get_current_object()
    
    def run_recalculation():
        with app.app_context():
            try:
                job_registry.update_job(job_id, status='running', progress=10)
                
                # 1. Update the transaction assignment
                PortfolioService.assign_transaction_to_subportfolio(transaction_id, sub_portfolio_id)
                job_registry.update_job(job_id, progress=40)
                
                # 2. Rebuild the portfolio state/holdings
                # We rebuild the parent (sub_portfolio_id=None) and the specific sub-portfolio
                PortfolioService.repair_portfolio_state(portfolio_id, subportfolio_id=None)
                if sub_portfolio_id:
                    PortfolioService.repair_portfolio_state(sub_portfolio_id)
                
                job_registry.update_job(job_id, progress=80)
                
                # 3. Clear history cache
                PortfolioService.clear_cache(portfolio_id)
                # Also clear child if applicable
                if sub_portfolio_id:
                    PortfolioService.clear_cache(sub_portfolio_id)
                
                job_registry.update_job(job_id, status='done', progress=100)
            except Exception as e:
                import traceback
                traceback.print_exc()
                job_registry.update_job(job_id, status='failed', error=str(e))

    thread = threading.Thread(target=run_recalculation, daemon=True)
    thread.start()

    return success_response({
        'job_id': job_id,
        'message': 'Transaction assignment started'
    }, status=202)


@portfolio_bp.route('/transactions/assign-bulk', methods=['POST'])
def assign_transactions_bulk():
    data = require_json_body()
    transaction_ids = data.get('transaction_ids', [])
    sub_portfolio_id = data.get('sub_portfolio_id')
    
    if not transaction_ids:
        raise ValidationError('No transactions provided')

    # Resolve portfolio_id for the job (assuming all belong to same parent as validated in service)
    db = get_db()
    tx = db.execute('SELECT portfolio_id FROM transactions WHERE id = ?', (transaction_ids[0],)).fetchone()
    if not tx:
        raise NotFoundError('Transaction not found')
    portfolio_id = tx['portfolio_id']

    # Start async job
    job_id = job_registry.create_job()
    app = current_app._get_current_object()
    
    def run_bulk_recalculation():
        with app.app_context():
            try:
                job_registry.update_job(job_id, status='running', progress=10)
                
                # 1. Update the transactions
                PortfolioService.assign_transactions_bulk(transaction_ids, sub_portfolio_id)
                job_registry.update_job(job_id, progress=40)
                
                # 2. Rebuild the portfolio state
                PortfolioService.repair_portfolio_state(portfolio_id, subportfolio_id=None)
                if sub_portfolio_id:
                    PortfolioService.repair_portfolio_state(sub_portfolio_id)
                    
                job_registry.update_job(job_id, progress=80)
                
                # 3. Clear history cache
                PortfolioService.clear_cache(portfolio_id)
                if sub_portfolio_id:
                    PortfolioService.clear_cache(sub_portfolio_id)
                    
                job_registry.update_job(job_id, status='done', progress=100)
            except Exception as e:
                import traceback
                traceback.print_exc()
                job_registry.update_job(job_id, status='failed', error=str(e))

    thread = threading.Thread(target=run_bulk_recalculation, daemon=True)
    thread.start()

    return success_response({
        'job_id': job_id,
        'message': 'Bulk transaction assignment started'
    }, status=202)


@portfolio_bp.route('/dividends/<int:portfolio_id>', methods=['GET'])
def get_dividends(portfolio_id):
    dividends = PortfolioService.get_dividends(portfolio_id)
    return success_response({'dividends': dividends})


@portfolio_bp.route('/dividends/monthly/<int:portfolio_id>', methods=['GET'])
def get_monthly_dividends(portfolio_id):
    monthly_data = PortfolioService.get_monthly_dividends(portfolio_id)
    return success_response({'monthly_dividends': monthly_data})
