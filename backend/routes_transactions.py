from flask import jsonify, request

from portfolio_service import PortfolioService
from routes_portfolio_base import portfolio_bp
from validators.request_models import validate_portfolio_trade


@portfolio_bp.route('/deposit', methods=['POST'])
def deposit():
    data = request.json
    try:
        PortfolioService.deposit_cash(data['portfolio_id'], data['amount'], data.get('date'))
        return jsonify({'message': 'Deposit successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@portfolio_bp.route('/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    try:
        PortfolioService.withdraw_cash(data['portfolio_id'], data['amount'], data.get('date'))
        return jsonify({'message': 'Withdrawal successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


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
    return jsonify({'message': 'Buy successful'}), 200


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
    return jsonify({'message': 'Sell successful'}), 200


@portfolio_bp.route('/transactions/<int:portfolio_id>', methods=['GET'])
def get_transactions(portfolio_id):
    try:
        transactions = PortfolioService.get_transactions(portfolio_id)
        return jsonify({'transactions': transactions}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/transactions/all', methods=['GET'])
def get_all_transactions():
    try:
        transactions = PortfolioService.get_all_transactions()
        return jsonify({'transactions': transactions}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        return jsonify({'message': 'Dividend recorded successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@portfolio_bp.route('/dividends/<int:portfolio_id>', methods=['GET'])
def get_dividends(portfolio_id):
    try:
        dividends = PortfolioService.get_dividends(portfolio_id)
        return jsonify({'dividends': dividends}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/dividends/monthly/<int:portfolio_id>', methods=['GET'])
def get_monthly_dividends(portfolio_id):
    try:
        monthly_data = PortfolioService.get_monthly_dividends(portfolio_id)
        return jsonify({'monthly_dividends': monthly_data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
