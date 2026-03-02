from flask import Blueprint, request, jsonify
from portfolio_service import PortfolioService
from bond_service import BondService
from price_service import PriceService
from ppk_service import PPKService
import re
import pandas as pd
from werkzeug.utils import secure_filename
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
        transactions = PPKService.get_transactions(portfolio_id)
        summary = PPKService.get_portfolio_summary(portfolio_id)
        return jsonify({'transactions': transactions, 'summary': summary}), 200
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

@portfolio_bp.route('/<int:portfolio_id>/import/xtb', methods=['POST'])
def import_xtb_csv(portfolio_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        df = pd.read_csv(file)
        df = df.sort_values('Time')  # Chronological order

        db = get_db()
        cursor = db.cursor()
        db.execute('BEGIN')
        for _, row in df.iterrows():
            typ = row['Type']
            ticker = row['Instrument']
            time = row['Time']
            # Zamiana przecinka na kropkę w Amount
            amount = float(str(row['Amount']).replace(',', '.'))
            comment = str(row['Comment']) if not pd.isna(row['Comment']) else ''
            # Deposit/Withdrawal
            if typ.lower() == 'deposit':
                cursor.execute(
                    'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                    (amount, portfolio_id)
                )
                cursor.execute(
                    '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (portfolio_id, 'CASH', 'DEPOSIT', 1, amount, amount, time)
                )
            elif typ.lower() == 'withdrawal':
                cursor.execute(
                    'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                    (abs(amount), portfolio_id)
                )
                cursor.execute(
                    '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (portfolio_id, 'CASH', 'WITHDRAW', 1, abs(amount), abs(amount), time)
                )
            elif typ.lower() == 'stock purchase':
                # Akceptuj liczby z przecinkiem lub kropką
                m = re.search(r'(?:OPEN|CLOSE) BUY ([\d\.,]+)(?:/[\d\.,]+)? @ ([\d\.,]+)', comment)
                if not m:
                    raise ValueError(f"Could not parse purchase comment: {comment}")
                qty = float(str(m.group(1)).replace(',', '.'))
                price = float(str(m.group(2)).replace(',', '.'))
                total_cost = abs(amount)
                # Update cash
                cursor.execute(
                    'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                    (total_cost, portfolio_id)
                )
                # Update or insert holding
                holding = cursor.execute(
                    'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?',
                    (portfolio_id, ticker)
                ).fetchone()
                if holding:
                    new_qty = holding['quantity'] + qty
                    new_total_cost = holding['total_cost'] + total_cost
                    new_avg_price = new_total_cost / new_qty
                    cursor.execute(
                        '''UPDATE holdings SET quantity = ?, total_cost = ?, average_buy_price = ? WHERE id = ?''',
                        (new_qty, new_total_cost, new_avg_price, holding['id'])
                    )
                else:
                    cursor.execute(
                        '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost)
                           VALUES (?, ?, ?, ?, ?)''',
                        (portfolio_id, ticker, qty, price, total_cost)
                    )
                # Log transaction
                cursor.execute(
                    '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (portfolio_id, ticker, 'BUY', qty, price, total_cost, time)
                )
            elif typ.lower() == 'stock sell':
                m = re.search(r'(?:OPEN|CLOSE) BUY ([\d\.,]+)(?:/[\d\.,]+)? @ ([\d\.,]+)', comment)
                if not m:
                    raise ValueError(f"Could not parse sell comment: {comment}")
                qty = float(str(m.group(1)).replace(',', '.'))
                price = float(str(m.group(2)).replace(',', '.'))
                # Add cash
                cursor.execute(
                    'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                    (amount, portfolio_id)
                )
                # Fetch holding BEFORE update
                holding = cursor.execute(
                    'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?',
                    (portfolio_id, ticker)
                ).fetchone()
                realized_profit = 0.0
                if holding:
                    realized_profit = (price - holding['average_buy_price']) * qty
                    new_qty = holding['quantity'] - qty
                    new_total_cost = holding['total_cost'] - (qty * holding['average_buy_price'])
                    if new_qty > 0:
                        cursor.execute(
                            '''UPDATE holdings SET quantity = ?, total_cost = ? WHERE id = ?''',
                            (new_qty, new_total_cost, holding['id'])
                        )
                    else:
                        cursor.execute('DELETE FROM holdings WHERE id = ?', (holding['id'],))
                # Log transaction with realized_profit
                cursor.execute(
                    '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, realized_profit, date)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (portfolio_id, ticker, 'SELL', qty, price, abs(amount), realized_profit, time)
                )
        db.commit()
        return jsonify({'message': 'Import successful'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/<int:portfolio_id>/closed-positions', methods=['GET'])
def closed_positions(portfolio_id):
    db = get_db()
    rows = db.execute(
        '''SELECT ticker, SUM(realized_profit) as realized_profit
           FROM transactions
           WHERE portfolio_id = ? AND type = 'SELL'
           GROUP BY ticker
           ORDER BY realized_profit DESC''',
        (portfolio_id,)
    ).fetchall()

    metadata_cache = {}

    def get_company_name(ticker):
        if ticker in metadata_cache:
            return metadata_cache[ticker]

        metadata = PriceService.fetch_metadata(ticker)
        company_name = metadata.get('company_name') if metadata else None
        metadata_cache[ticker] = company_name
        return company_name

    total = sum(r['realized_profit'] or 0 for r in rows)
    positions = [
        {
            'ticker': r['ticker'],
            'company_name': get_company_name(r['ticker']),
            'realized_profit': float(r['realized_profit'] or 0)
        }
        for r in rows
    ]
    return jsonify({
        'positions': positions,
        'total_historical_profit': total
    })

@portfolio_bp.route('/<int:portfolio_id>/performance', methods=['GET'])
def get_performance_matrix(portfolio_id):
    try:
        matrix = PortfolioService.get_performance_matrix(portfolio_id)
        return jsonify({'matrix': matrix}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
