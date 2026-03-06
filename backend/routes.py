from flask import Blueprint, request, jsonify
from portfolio_service import PortfolioService
from bond_service import BondService
from price_service import PriceService
from modules.ppk.ppk_service import PPKService
import pandas as pd
from database import get_db

portfolio_bp = Blueprint('portfolio', __name__)

@portfolio_bp.route('/limits', methods=['GET'])
def get_tax_limits():
    try:
        limits = PortfolioService.get_tax_limits()
        return jsonify({'limits': limits}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/create', methods=['POST'])
def create_portfolio():
    data = request.json
    try:
        portfolio_id = PortfolioService.create_portfolio(
            data['name'], 
            data.get('initial_cash', 0.0),
            data.get('account_type', 'STANDARD'),
            data.get('created_at')
        )
        return jsonify({'id': portfolio_id, 'message': 'Portfolio created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/bonds/<int:portfolio_id>', methods=['GET'])
def get_bonds(portfolio_id):
    try:
        bonds = BondService.get_bonds(portfolio_id)
        return jsonify({'bonds': bonds}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/bonds', methods=['POST'])
def add_bond():
    data = request.json
    try:
        BondService.add_bond(
            data['portfolio_id'],
            data['name'],
            data['principal'],
            data['interest_rate'],
            data['purchase_date']
        )
        return jsonify({'message': 'Bond added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/savings/rate', methods=['POST'])
def update_savings_rate():
    data = request.json
    try:
        PortfolioService.update_savings_rate(data['portfolio_id'], data['rate'])
        return jsonify({'message': 'Rate updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/savings/interest/manual', methods=['POST'])
def add_manual_interest():
    data = request.json
    try:
        PortfolioService.add_manual_interest(data['portfolio_id'], data['amount'], data['date'])
        return jsonify({'message': 'Interest added successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/history/monthly/<int:portfolio_id>', methods=['GET'])
def get_portfolio_history_monthly(portfolio_id):
    try:
        benchmark = request.args.get('benchmark')
        # If benchmark is empty string, treat as None
        if benchmark == '':
            benchmark = None
            
        history = PortfolioService.get_portfolio_history(portfolio_id, benchmark_ticker=benchmark)
        return jsonify({'history': history}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/history/profit/<int:portfolio_id>', methods=['GET'])
def get_portfolio_profit_history(portfolio_id):
    try:
        history = PortfolioService.get_portfolio_profit_history(portfolio_id)
        return jsonify({'history': history}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    data = request.json
    try:
        PortfolioService.buy_stock(
            data['portfolio_id'], 
            data['ticker'], 
            data['quantity'], 
            data['price'],
            data.get('date'), # Accept optional custom date
            data.get('commission', 0.0),
            data.get('auto_fx_fees', False)
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


@portfolio_bp.route('/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio(portfolio_id):
    try:
        PortfolioService.delete_portfolio(portfolio_id)
        return jsonify({'message': 'Portfolio deleted successfully'}), 200
    except ValueError as e:
        message = str(e)
        if message == 'Portfolio not found':
            return jsonify({'error': message}), 404
        return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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



@portfolio_bp.route('/ppk/transactions/<int:portfolio_id>', methods=['GET'])
def get_ppk_transactions(portfolio_id):
    try:
        current_price_raw = request.args.get('current_price')
        current_price_data = None
        current_price = None

        if current_price_raw is not None:
            current_price = float(current_price_raw)
        else:
            try:
                current_price_data = PPKService.fetch_current_price()
                current_price = current_price_data['price']
            except Exception:
                current_price_data = None

        transactions = PPKService.get_transactions(portfolio_id)
        summary = PPKService.get_portfolio_summary(portfolio_id, current_price)
        return jsonify({'transactions': transactions, 'summary': summary, 'currentPrice': current_price_data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/ppk/transactions', methods=['POST'])
def add_ppk_transaction():
    data = request.json
    try:
        PPKService.add_transaction(
            data['portfolio_id'],
            data.get('date'),
            data['employeeUnits'],
            data['employerUnits'],
            data['pricePerUnit']
        )
        return jsonify({'message': 'PPK transaction added successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

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
        
        # Ensure data is synced only when local history is missing or stale.
        if PriceService.needs_history_sync(ticker):
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

@portfolio_bp.route('/<int:portfolio_id>/import/xtb', methods=['POST'])
def import_xtb_csv(portfolio_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        df = pd.read_csv(file)
        result = PortfolioService.import_xtb_csv(portfolio_id, df)
        if not result['success']:
            return jsonify(result), 400
        return jsonify({'message': 'Import successful', **result}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/<int:portfolio_id>/closed-positions', methods=['GET'])
def closed_positions(portfolio_id):
    db = get_db()
    rows = db.execute(
        '''SELECT ticker, SUM(realized_profit) as realized_profit, MAX(date) as last_sell_date
           FROM transactions
           WHERE portfolio_id = ? AND type = 'SELL'
           GROUP BY ticker
           ORDER BY realized_profit DESC''',
        (portfolio_id,)
    ).fetchall()

    tickers = [r['ticker'] for r in rows if r['ticker']]
    metadata_cache = {}

    if tickers:
        placeholders = ','.join('?' for _ in tickers)
        metadata_rows = db.execute(
            f'''SELECT ticker, name
                FROM instrument_metadata
                WHERE ticker IN ({placeholders})''',
            tuple(tickers)
        ).fetchall()
        metadata_cache = {
            row['ticker']: row['name']
            for row in metadata_rows
            if row['ticker']
        }

    def get_company_name(ticker):
        name = metadata_cache.get(ticker)
        return name if name else ticker

    total = sum(r['realized_profit'] or 0 for r in rows)
    positions = [
        {
            'ticker': r['ticker'],
            'company_name': get_company_name(r['ticker']),
            'realized_profit': float(r['realized_profit'] or 0),
            'last_sell_date': str(r['last_sell_date']) if r['last_sell_date'] else None
        }
        for r in rows
    ]
    return jsonify({
        'positions': positions,
        'total_historical_profit': total
    })



@portfolio_bp.route('/<int:portfolio_id>/metadata/refresh', methods=['POST'])
def refresh_portfolio_metadata(portfolio_id):
    try:
        data = request.get_json(silent=True) or {}
        tickers = data.get('tickers')
        refreshed = PortfolioService.refresh_instrument_metadata(portfolio_id, tickers=tickers)
        return jsonify({'message': 'Metadata refreshed', 'tickers': refreshed}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/<int:portfolio_id>/performance', methods=['GET'])
def get_performance_matrix(portfolio_id):
    try:
        matrix = PortfolioService.get_performance_matrix(portfolio_id)
        return jsonify({'matrix': matrix}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
