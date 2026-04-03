from flask import current_app, request
from database import get_db
from portfolio_service import PortfolioService
from api.response import success_response
from api.exceptions import ApiError
from job_registry import job_registry
import threading
from datetime import date, datetime
from uuid import uuid4
from routes_portfolio_base import (
    portfolio_bp,
    optional_bool,
    optional_number,
    optional_positive_int,
    optional_string,
    raise_portfolio_validation_error,
    require_json_body,
    require_non_empty_string,
    require_number,
    require_positive_int,
)


def _parse_transfer_date(raw_value):
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'date must be a non-empty string in YYYY-MM-DD format', status=422)

    try:
        parsed = datetime.strptime(raw_value.strip(), '%Y-%m-%d').date()
    except ValueError as exc:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'date must be in YYYY-MM-DD format', status=422) from exc

    if parsed > date.today():
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'date cannot be in the future', status=422)
    return parsed


def _resolve_transfer_scope(db, *, portfolio_id, sub_portfolio_id, field_prefix):
    portfolio = db.execute(
        'SELECT id, parent_portfolio_id, is_archived, current_cash FROM portfolios WHERE id = ?',
        (portfolio_id,),
    ).fetchone()
    if not portfolio:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', f'{field_prefix}_portfolio_id not found', status=422)

    resolved_parent_id = portfolio['parent_portfolio_id'] or portfolio['id']
    resolved_sub_id = portfolio['id'] if portfolio['parent_portfolio_id'] else None

    if sub_portfolio_id is not None:
        child = db.execute(
            'SELECT id, parent_portfolio_id, is_archived, current_cash FROM portfolios WHERE id = ?',
            (sub_portfolio_id,),
        ).fetchone()
        if not child:
            raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', f'{field_prefix}_sub_portfolio_id not found', status=422)
        if child['parent_portfolio_id'] != resolved_parent_id:
            raise ApiError(
                'CASH_TRANSFER_VALIDATION_ERROR',
                f'{field_prefix}_sub_portfolio_id belongs to a different parent',
                status=422,
            )
        if portfolio['parent_portfolio_id'] and child['id'] != portfolio['id']:
            raise ApiError(
                'CASH_TRANSFER_VALIDATION_ERROR',
                f'{field_prefix}_portfolio_id is a child, so {field_prefix}_sub_portfolio_id must match it or be null',
                status=422,
            )
        resolved_sub_id = child['id']

    resolved_cash = float(portfolio['current_cash'])
    if resolved_sub_id is not None:
        child_scope = db.execute(
            'SELECT id, is_archived, current_cash FROM portfolios WHERE id = ?',
            (resolved_sub_id,),
        ).fetchone()
        if child_scope['is_archived']:
            raise ApiError(
                'CASH_TRANSFER_VALIDATION_ERROR',
                f'Archived child portfolio cannot be used as {field_prefix}',
                status=422,
            )
        resolved_cash = float(child_scope['current_cash'])

    return {
        'parent_id': resolved_parent_id,
        'sub_id': resolved_sub_id,
        'cash': resolved_cash,
    }


def _legacy_cash_seed_for_child_scope(db, child_id):
    rows = db.execute(
        '''
        SELECT type, total_value
        FROM transactions
        WHERE portfolio_id = ? AND (sub_portfolio_id IS NULL OR sub_portfolio_id = 0)
        ''',
        (child_id,),
    ).fetchall()

    cash = 0.0
    for row in rows:
        tx_type = row['type']
        value = float(row['total_value'])
        if tx_type in ('DEPOSIT', 'DIVIDEND', 'INTEREST', 'SELL'):
            cash += value
        elif tx_type in ('WITHDRAW', 'BUY'):
            cash -= value

    return cash


def _repair_cash_transfer_scope(db, portfolio_id):
    scope = db.execute('SELECT id, parent_portfolio_id FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
    if not scope:
        return

    if scope['parent_portfolio_id']:
        parent_id = int(scope['parent_portfolio_id'])
        child_id = int(scope['id'])
        PortfolioService.repair_portfolio_state(parent_id, subportfolio_id=child_id)

        legacy_seed = _legacy_cash_seed_for_child_scope(db, child_id)
        if abs(legacy_seed) > 0.0000001:
            repaired_cash_row = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (child_id,)).fetchone()
            repaired_cash = float(repaired_cash_row['current_cash']) if repaired_cash_row else 0.0
            db.execute('UPDATE portfolios SET current_cash = ? WHERE id = ?', (repaired_cash + legacy_seed, child_id))
            db.commit()
        return

    PortfolioService.repair_portfolio_state(int(scope['id']), subportfolio_id=None)


def _run_cash_transfer_recalculation(app, job_id, affected_ids):
    with app.app_context():
        try:
            job_registry.update_job(job_id, status='running', progress=10)
            unique_ids = [portfolio_id for portfolio_id in dict.fromkeys(affected_ids) if portfolio_id]

            for index, portfolio_id in enumerate(unique_ids, start=1):
                _repair_cash_transfer_scope(get_db(), portfolio_id)
                job_registry.update_job(job_id, progress=min(70, 10 + int((index / max(1, len(unique_ids))) * 60)))

            for portfolio_id in unique_ids:
                PortfolioService.clear_cache(portfolio_id)

            job_registry.update_job(job_id, status='done', progress=100)
        except Exception as e:
            import traceback
            traceback.print_exc()
            job_registry.update_job(job_id, status='failed', error=str(e))


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


@portfolio_bp.route('/transfer/cash', methods=['POST'])
def transfer_cash_between_scopes():
    data = require_json_body()
    db = get_db()

    raw_from_sub_portfolio_id = optional_positive_int(data, 'from_sub_portfolio_id')
    raw_to_sub_portfolio_id = optional_positive_int(data, 'to_sub_portfolio_id')

    amount = require_number(data, 'amount')
    if amount <= 0:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'amount must be greater than zero', status=422)

    transfer_date = _parse_transfer_date(data.get('date'))

    from_scope = _resolve_transfer_scope(
        db,
        portfolio_id=require_positive_int(data, 'from_portfolio_id'),
        sub_portfolio_id=raw_from_sub_portfolio_id,
        field_prefix='from',
    )
    to_scope = _resolve_transfer_scope(
        db,
        portfolio_id=require_positive_int(data, 'to_portfolio_id'),
        sub_portfolio_id=raw_to_sub_portfolio_id,
        field_prefix='to',
    )

    if from_scope['parent_id'] != to_scope['parent_id']:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'Transfer is only allowed within the same parent portfolio tree', status=422)

    if from_scope['parent_id'] == to_scope['parent_id'] and from_scope['sub_id'] is None and to_scope['sub_id'] is None:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'Parent to parent transfer within the same scope is not allowed', status=422)

    if from_scope['parent_id'] == to_scope['parent_id'] and from_scope['sub_id'] == to_scope['sub_id']:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'Source and destination cannot be identical', status=422)

    available_cash_on_transfer_date = PortfolioService.get_cash_balance_on_date(
        from_scope['parent_id'],
        transfer_date.isoformat(),
        sub_portfolio_id=from_scope['sub_id'],
    )
    if amount > available_cash_on_transfer_date:
        raise ApiError(
            'CASH_TRANSFER_VALIDATION_ERROR',
            f'Niewystarczająca gotówka na dzień {transfer_date.isoformat()} (dostępne: {available_cash_on_transfer_date:.2f} PLN)',
            status=422,
        )

    transfer_id = str(uuid4())
    note = optional_string(data, 'note')

    try:
        db.execute(
            '''
            INSERT INTO transactions (
                portfolio_id, ticker, date, type, quantity, price, total_value, realized_profit, commission, sub_portfolio_id, transfer_id
            ) VALUES (?, 'CASH', ?, 'WITHDRAW', 1, ?, ?, 0.0, 0.0, ?, ?)
            ''',
            (from_scope['parent_id'], transfer_date.isoformat(), amount, amount, from_scope['sub_id'], transfer_id),
        )
        db.execute(
            '''
            INSERT INTO transactions (
                portfolio_id, ticker, date, type, quantity, price, total_value, realized_profit, commission, sub_portfolio_id, transfer_id
            ) VALUES (?, 'CASH', ?, 'DEPOSIT', 1, ?, ?, 0.0, 0.0, ?, ?)
            ''',
            (to_scope['parent_id'], transfer_date.isoformat(), amount, amount, to_scope['sub_id'], transfer_id),
        )

        from_target_id = from_scope['sub_id'] or from_scope['parent_id']
        to_target_id = to_scope['sub_id'] or to_scope['parent_id']
        db.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (amount, from_target_id))
        db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (amount, to_target_id))
        db.commit()
    except Exception:
        db.rollback()
        raise

    job_id = job_registry.create_job()
    app = current_app._get_current_object()
    affected_ids = [from_scope['parent_id'], from_scope['sub_id'], to_scope['sub_id']]

    if current_app.config.get('TESTING'):
        _run_cash_transfer_recalculation(app, job_id, affected_ids)
    else:
        thread = threading.Thread(target=_run_cash_transfer_recalculation, args=(app, job_id, affected_ids), daemon=True)
        thread.start()

    response = {
        'transfer_id': transfer_id,
        'from': {'portfolio_id': from_scope['parent_id'], 'sub_portfolio_id': from_scope['sub_id']},
        'to': {'portfolio_id': to_scope['parent_id'], 'sub_portfolio_id': to_scope['sub_id']},
        'amount': amount,
        'date': transfer_date.isoformat(),
        'job_id': job_id,
    }
    if note:
        response['note'] = note
    return success_response(response, status=200)


@portfolio_bp.route('/transfer/cash/<string:transfer_id>', methods=['DELETE'])
def delete_cash_transfer(transfer_id):
    db = get_db()
    transactions = db.execute(
        '''
        SELECT id, portfolio_id, sub_portfolio_id, type, total_value
        FROM transactions
        WHERE transfer_id = ?
        ORDER BY id ASC
        ''',
        (transfer_id,),
    ).fetchall()

    if len(transactions) != 2:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'transfer_id must match exactly two transactions', status=422)

    withdraw_tx = next((tx for tx in transactions if tx['type'] == 'WITHDRAW'), None)
    deposit_tx = next((tx for tx in transactions if tx['type'] == 'DEPOSIT'), None)
    if not withdraw_tx or not deposit_tx:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'transfer_id must contain one WITHDRAW and one DEPOSIT transaction', status=422)

    amount = float(withdraw_tx['total_value'])
    if amount <= 0 or abs(float(deposit_tx['total_value']) - amount) > 0.0001:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'transfer transactions must have matching positive amount', status=422)

    withdraw_target_id = withdraw_tx['sub_portfolio_id'] or withdraw_tx['portfolio_id']
    deposit_target_id = deposit_tx['sub_portfolio_id'] or deposit_tx['portfolio_id']

    deposit_cash_row = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (deposit_target_id,)).fetchone()
    if not deposit_cash_row or float(deposit_cash_row['current_cash']) < amount:
        raise ApiError('CASH_TRANSFER_VALIDATION_ERROR', 'Cannot revert transfer due to insufficient destination cash', status=422)

    try:
        db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (amount, withdraw_target_id))
        db.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (amount, deposit_target_id))
        db.execute('DELETE FROM transactions WHERE transfer_id = ?', (transfer_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise

    job_id = job_registry.create_job()
    app = current_app._get_current_object()
    affected_ids = [withdraw_tx['portfolio_id'], withdraw_tx['sub_portfolio_id'], deposit_tx['sub_portfolio_id']]

    if current_app.config.get('TESTING'):
        _run_cash_transfer_recalculation(app, job_id, affected_ids)
    else:
        thread = threading.Thread(target=_run_cash_transfer_recalculation, args=(app, job_id, affected_ids), daemon=True)
        thread.start()

    return success_response({'message': 'Cash transfer deleted', 'transfer_id': transfer_id, 'job_id': job_id}, status=200)


@portfolio_bp.route('/deposit', methods=['POST'])
def deposit():
    data = require_json_body()
    try:
        PortfolioService.deposit_cash(
            require_positive_int(data, 'portfolio_id'),
            require_number(data, 'amount', positive=True),
            optional_string(data, 'date'),
            sub_portfolio_id=optional_positive_int(data, 'sub_portfolio_id')
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
            sub_portfolio_id=optional_positive_int(data, 'sub_portfolio_id')
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
            sub_portfolio_id=optional_positive_int(data, 'sub_portfolio_id')
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
            sub_portfolio_id=optional_positive_int(data, 'sub_portfolio_id')
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
            sub_portfolio_id=optional_positive_int(data, 'sub_portfolio_id')
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
