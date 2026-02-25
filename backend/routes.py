from flask import Blueprint, request, jsonify
from services import PortfolioService, PriceService

portfolio_bp = Blueprint('portfolio', __name__)

@portfolio_bp.route('/create', methods=['POST'])
def create_portfolio():
    data = request.json
    try:
        portfolio_id = PortfolioService.create_portfolio(data['name'], data.get('initial_cash', 0.0))
        return jsonify({'id': portfolio_id, 'message': 'Portfolio created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/list', methods=['GET'])
def list_portfolios():
    try:
        portfolios = PortfolioService.list_portfolios()
        # Enrich with value data
        result = []
        for p in portfolios:
            val_data = PortfolioService.get_portfolio_value(p['id'])
            p.update(val_data)
            result.append(p)
        return jsonify({'portfolios': result}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/deposit', methods=['POST'])
def deposit():
    data = request.json
    try:
        PortfolioService.deposit_cash(data['portfolio_id'], data['amount'])
        return jsonify({'message': 'Deposit successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    try:
        PortfolioService.withdraw_cash(data['portfolio_id'], data['amount'])
        return jsonify({'message': 'Withdrawal successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/buy', methods=['POST'])
def buy():
    data = request.json
    try:
        PortfolioService.buy_stock(
            data['portfolio_id'], 
            data['ticker'], 
            data['quantity'], 
            data['price'],
            data.get('date') # Accept optional custom date
        )
        return jsonify({'message': 'Buy successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/sell', methods=['POST'])
def sell():
    data = request.json
    try:
        PortfolioService.sell_stock(
            data['portfolio_id'], 
            data['ticker'], 
            data['quantity'], 
            data['price']
        )
        return jsonify({'message': 'Sell successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/value/<int:portfolio_id>', methods=['GET'])
def get_value(portfolio_id):
    try:
        value_data = PortfolioService.get_portfolio_value(portfolio_id)
        if value_data:
            return jsonify(value_data), 200
        return jsonify({'error': 'Portfolio not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/holdings/<int:portfolio_id>', methods=['GET'])
def get_holdings(portfolio_id):
    try:
        holdings = PortfolioService.get_holdings(portfolio_id)
        return jsonify({'holdings': holdings}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

@portfolio_bp.route('/history/<string:ticker>', methods=['GET'])
def get_stock_history(ticker):
    try:
        from database import get_db
        db = get_db()
        
        # Ensure data is synced (at least last 30 days if new)
        PriceService.sync_stock_history(ticker)
        
        prices = db.execute(
            'SELECT date, close_price FROM stock_prices WHERE ticker = ? ORDER BY date ASC',
            (ticker,)
        ).fetchall()
        
        # Get last updated timestamp
        last_updated = db.execute(
            'SELECT MAX(date) as last_date FROM stock_prices WHERE ticker = ?',
            (ticker,)
        ).fetchone()
        
        return jsonify({
            'ticker': ticker,
            'history': [dict(p) for p in prices],
            'last_updated': last_updated['last_date'] if last_updated else None
        }), 200
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
