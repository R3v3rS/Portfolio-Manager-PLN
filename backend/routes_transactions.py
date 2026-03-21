from flask import request

from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp
from validators.request_models import validate_portfolio_trade
from validators.responses import error_response, success_response


@portfolio_bp.route('/deposit', methods=['POST'])
def deposit():
    data = request.json
    try:
        PortfolioService.deposit_cash(data['portfolio_id'], data['amount'], data.get('date'))
        return success_response(None, message='Deposit successful')
    except Exception as e:
        return error_response(str(e), status_code=400, code='validation_error')


@portfolio_bp.route('/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    try:
        PortfolioService.withdraw_cash(data['portfolio_id'], data['amount'], data.get('date'))
        return success_response(None, message='Withdrawal successful')
    except Exception as e:
        return error_response(str(e), status_code=400, code='validation_error')


@portfolio_bp.route('/buy', methods=['POST'])
def buy():
    data = validate_portfolio_trade(request.get_json(silent=True))
    PortfolioService.buy_stock(
        data['portfolio_id'],
        data['ticker'],
        data['quantity'],
        data['price'],
        data.get('date'),
        data['commission'],
        data['auto_fx_fees']
    )
    return success_response(None, message='Buy successful')


@portfolio_bp.route('/sell', methods=['POST'])
def sell():
    data = validate_portfolio_trade(request.get_json(silent=True))
    PortfolioService.sell_stock(
        data['portfolio_id'],
        data['ticker'],
        data['quantity'],
        data['price'],
        data.get('date')
    )
    return success_response(None, message='Sell successful')


@portfolio_bp.route('/transactions/<int:portfolio_id>', methods=['GET'])
def get_transactions(portfolio_id):
    try:
        transactions = PortfolioService.get_transactions(portfolio_id)
        return success_response({'transactions': transactions})
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/transactions/all', methods=['GET'])
def get_all_transactions():
    try:
        transactions = PortfolioService.get_all_transactions()
        return success_response({'transactions': transactions})
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/dividend', methods=['POST'])
def record_dividend():
    data = request.json
    try:
        PortfolioService.record_dividend(
            data['portfolio_id'],
            data['ticker'],
            data['amount'],
            data['date']
        )
        return success_response(None, message='Dividend recorded successfully', status_code=201)
    except Exception as e:
        return error_response(str(e), status_code=400, code='validation_error')


@portfolio_bp.route('/dividends/<int:portfolio_id>', methods=['GET'])
def get_dividends(portfolio_id):
    try:
        dividends = PortfolioService.get_dividends(portfolio_id)
        return success_response({'dividends': dividends})
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')


@portfolio_bp.route('/dividends/monthly/<int:portfolio_id>', methods=['GET'])
def get_monthly_dividends(portfolio_id):
    try:
        monthly_data = PortfolioService.get_monthly_dividends(portfolio_id)
        return success_response({'monthly_dividends': monthly_data})
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')
