from flask import current_app, request
from database import get_db
from portfolio_service import PortfolioService
from api.response import success_response
from api.exceptions import ApiError
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


def validate_assign_payload(data, *, require_transaction_ids=False):
    def raise_assign_validation(message):
        raise ApiError('ASSIGN_VALIDATION_ERROR', message, status=422)

    raw_sub_portfolio_id = data.get('sub_portfolio_id')
    if raw_sub_portfolio_id is None:
        sub_portfolio_id = None
    elif isinstance(raw_sub_portfolio_id, bool) or not isinstance(raw_sub_portfolio_id, int) or raw_sub_portfolio_id <= 0:
        raise_assign_validation('sub_portfolio_id must be a positive integer or null')
    else:
        sub_portfolio_id = raw_sub_portfolio_id

    if not require_transaction_ids:
        return sub_portfolio_id

    transaction_ids = data.get('transaction_ids')
    if (
        not isinstance(transaction_ids, list)
        or not transaction_ids
        or any(isinstance(tx_id, bool) or not isinstance(tx_id, int) or tx_id <= 0 for tx_id in transaction_ids)
    ):
        raise_assign_validation('transaction_ids must be a non-empty list of positive integers')

    return transaction_ids, sub_portfolio_id


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
    sub_portfolio_id = request.args.get('sub_portfolio_id')
    transaction_type = request.args.get('type')
    
    # sub_portfolio_id can be 'none' or a number
    if sub_portfolio_id and sub_portfolio_id != 'none':
        try:
            sub_portfolio_id = int(sub_portfolio_id)
        except ValueError:
            sub_portfolio_id = None
            
    transactions = PortfolioService.get_transactions(
        portfolio_id, 
        ticker=ticker, 
        sub_portfolio_id=sub_portfolio_id, 
        transaction_type=transaction_type
    )
    return success_response({'transactions': transactions})


@portfolio_bp.route('/transactions/all', methods=['GET'])
def get_all_transactions():
    ticker = request.args.get('ticker')
    portfolio_id = request.args.get('portfolio_id')
    sub_portfolio_id = request.args.get('sub_portfolio_id')
    transaction_type = request.args.get('type')
    
    if portfolio_id:
        try:
            portfolio_id = int(portfolio_id)
        except ValueError:
            portfolio_id = None
            
    if sub_portfolio_id and sub_portfolio_id != 'none':
        try:
            sub_portfolio_id = int(sub_portfolio_id)
        except ValueError:
            sub_portfolio_id = None
            
    transactions = PortfolioService.get_all_transactions(
        ticker=ticker, 
        portfolio_id=portfolio_id,
        sub_portfolio_id=sub_portfolio_id,
        transaction_type=transaction_type
    )
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
    def raise_assign_validation(message):
        raise ApiError('ASSIGN_VALIDATION_ERROR', message, status=422)

    data = require_json_body()
    sub_portfolio_id = validate_assign_payload(data)

    db = get_db()
    tx = db.execute(
        'SELECT id, portfolio_id, sub_portfolio_id, type, ticker, date, total_value FROM transactions WHERE id = ?',
        (transaction_id,),
    ).fetchone()
    if not tx:
        raise_assign_validation('Transaction not found')

    portfolio_id = tx['portfolio_id']
    old_sub_portfolio_id = tx['sub_portfolio_id']
    tx_type = tx['type']

    if sub_portfolio_id is not None:
        child = db.execute(
            'SELECT id, parent_portfolio_id, is_archived FROM portfolios WHERE id = ?',
            (sub_portfolio_id,),
        ).fetchone()
        if not child:
            raise_assign_validation('Target sub-portfolio not found')
        if child['parent_portfolio_id'] != portfolio_id:
            raise_assign_validation('Target sub-portfolio belongs to a different parent')
        if child['is_archived']:
            raise_assign_validation('Cannot assign to an archived sub-portfolio')
        if tx_type == 'INTEREST':
            raise_assign_validation('INTEREST transactions must remain in parent portfolio')

    # No-op: everything already up to date, no async recalculation needed
    if old_sub_portfolio_id == sub_portfolio_id:
        return success_response({'message': 'Transaction assignment updated'})

    try:
        db.execute('UPDATE transactions SET sub_portfolio_id = ? WHERE id = ?', (sub_portfolio_id, transaction_id))
        if tx_type == 'DIVIDEND':
            db.execute(
                '''
                UPDATE dividends
                SET sub_portfolio_id = ?
                WHERE portfolio_id = ? AND ticker = ? AND date = ? AND amount = ?
                ''',
                (sub_portfolio_id, portfolio_id, tx['ticker'], tx['date'], tx['total_value']),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    job_id = job_registry.create_job()
    app = current_app._get_current_object()

    def run_recalculation():
        with app.app_context():
            try:
                job_registry.update_job(job_id, status='running', progress=10)
                job_registry.update_job(job_id, progress=40)

                # Rebuild affected scopes after assignment was already committed
                PortfolioService.repair_portfolio_state(portfolio_id, subportfolio_id=None)
                if sub_portfolio_id:
                    PortfolioService.repair_portfolio_state(sub_portfolio_id)
                if old_sub_portfolio_id and old_sub_portfolio_id != sub_portfolio_id:
                    PortfolioService.repair_portfolio_state(old_sub_portfolio_id)

                job_registry.update_job(job_id, progress=80)
                PortfolioService.clear_cache(portfolio_id)
                if sub_portfolio_id:
                    PortfolioService.clear_cache(sub_portfolio_id)
                if old_sub_portfolio_id and old_sub_portfolio_id != sub_portfolio_id:
                    PortfolioService.clear_cache(old_sub_portfolio_id)

                job_registry.update_job(job_id, status='done', progress=100)
            except Exception as e:
                import traceback
                traceback.print_exc()
                job_registry.update_job(job_id, status='failed', error=str(e))

    if current_app.config.get('TESTING'):
        run_recalculation()
    else:
        thread = threading.Thread(target=run_recalculation, daemon=True)
        thread.start()

    return success_response({'message': 'Transaction assignment updated', 'job_id': job_id}, status=200)


@portfolio_bp.route('/transactions/assign-bulk', methods=['POST'])
def assign_transactions_bulk():
    def raise_assign_validation(message):
        raise ApiError('ASSIGN_VALIDATION_ERROR', message, status=422)

    data = require_json_body()
    transaction_ids, sub_portfolio_id = validate_assign_payload(data, require_transaction_ids=True)

    unique_transaction_ids = list(dict.fromkeys(transaction_ids))
    db = get_db()
    placeholders = ', '.join(['?'] * len(unique_transaction_ids))
    rows = db.execute(
        f'''
        SELECT id, portfolio_id, sub_portfolio_id, type, ticker, date, total_value
        FROM transactions
        WHERE id IN ({placeholders})
        ''',
        unique_transaction_ids,
    ).fetchall()

    if not rows:
        raise_assign_validation('Transactions not found')
    if len(rows) != len(unique_transaction_ids):
        raise_assign_validation('One or more transactions were not found')

    portfolio_ids = {row['portfolio_id'] for row in rows}
    if len(portfolio_ids) != 1:
        raise_assign_validation('Bulk assignment must be for transactions within the same parent portfolio')

    portfolio_id = next(iter(portfolio_ids))
    old_sub_portfolio_ids = {row['sub_portfolio_id'] for row in rows if row['sub_portfolio_id'] is not None}

    if sub_portfolio_id is not None:
        child = db.execute(
            'SELECT id, parent_portfolio_id, is_archived FROM portfolios WHERE id = ?',
            (sub_portfolio_id,),
        ).fetchone()
        if not child:
            raise_assign_validation('Target sub-portfolio not found')
        if child['parent_portfolio_id'] != portfolio_id:
            raise_assign_validation('Target sub-portfolio belongs to a different parent')
        if child['is_archived']:
            raise_assign_validation('Cannot assign to an archived sub-portfolio')

        if any(row['type'] == 'INTEREST' for row in rows):
            raise_assign_validation('INTEREST transactions must remain in parent portfolio')

    if all(row['sub_portfolio_id'] == sub_portfolio_id for row in rows):
        return success_response({'message': 'Bulk transaction assignment updated'})

    try:
        db.execute(
            f'UPDATE transactions SET sub_portfolio_id = ? WHERE id IN ({placeholders})',
            [sub_portfolio_id, *unique_transaction_ids],
        )
        for row in rows:
            if row['type'] != 'DIVIDEND':
                continue
            db.execute(
                '''
                UPDATE dividends
                SET sub_portfolio_id = ?
                WHERE portfolio_id = ? AND ticker = ? AND date = ? AND amount = ?
                ''',
                (sub_portfolio_id, row['portfolio_id'], row['ticker'], row['date'], row['total_value']),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    job_id = job_registry.create_job()
    app = current_app._get_current_object()

    def run_bulk_recalculation():
        with app.app_context():
            try:
                job_registry.update_job(job_id, status='running', progress=10)
                job_registry.update_job(job_id, progress=40)

                PortfolioService.repair_portfolio_state(portfolio_id, subportfolio_id=None)
                if sub_portfolio_id:
                    PortfolioService.repair_portfolio_state(sub_portfolio_id)
                for old_id in old_sub_portfolio_ids:
                    if old_id != sub_portfolio_id:
                        PortfolioService.repair_portfolio_state(old_id)

                job_registry.update_job(job_id, progress=80)
                PortfolioService.clear_cache(portfolio_id)
                if sub_portfolio_id:
                    PortfolioService.clear_cache(sub_portfolio_id)
                for old_id in old_sub_portfolio_ids:
                    if old_id != sub_portfolio_id:
                        PortfolioService.clear_cache(old_id)

                job_registry.update_job(job_id, status='done', progress=100)
            except Exception as e:
                import traceback
                traceback.print_exc()
                job_registry.update_job(job_id, status='failed', error=str(e))

    if current_app.config.get('TESTING'):
        run_bulk_recalculation()
    else:
        thread = threading.Thread(target=run_bulk_recalculation, daemon=True)
        thread.start()

    return success_response({'message': 'Bulk transaction assignment updated', 'job_id': job_id}, status=200)


@portfolio_bp.route('/dividends/<int:portfolio_id>', methods=['GET'])
def get_dividends(portfolio_id):
    dividends = PortfolioService.get_dividends(portfolio_id)
    return success_response({'dividends': dividends})


@portfolio_bp.route('/dividends/monthly/<int:portfolio_id>', methods=['GET'])
def get_monthly_dividends(portfolio_id):
    monthly_data = PortfolioService.get_monthly_dividends(portfolio_id)
    return success_response({'monthly_dividends': monthly_data})
