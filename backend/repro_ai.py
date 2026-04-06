
import os
import sqlite3
from flask import Flask, g
import json

# Setup minimal Flask app to mock context
app = Flask(__name__)
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'portfolio.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def test_query():
    with app.app_context():
        db = get_db()
        portfolio_id = 1 # Assuming ID 1 exists
        try:
            rows = db.execute(
                '''
                SELECT
                    h.ticker,
                    h.quantity,
                    h.total_cost,
                    h.sector,
                    h.currency,
                    pc.price AS current_price
                FROM holdings h
                LEFT JOIN price_cache pc ON pc.ticker = h.ticker
                WHERE h.portfolio_id = ? AND h.quantity > 0
                ORDER BY h.total_cost DESC
                ''',
                (portfolio_id,),
            ).fetchall()
            
            print(f"Found {len(rows)} rows.")
            
            positions = []
            total_portfolio_value = 0.0

            for row in rows:
                ticker = row['ticker']
                quantity = float(row['quantity'] or 0)
                total_cost = float(row['total_cost'] or 0)
                
                # Use 0.0 if current_price is None or cannot be converted to float
                current_price_raw = row['current_price']
                try:
                    current_price = float(current_price_raw) if current_price_raw is not None else 0.0
                except (ValueError, TypeError):
                    current_price = 0.0

                current_value = quantity * current_price
                unrealized_pnl = current_value - total_cost
                unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost > 0 else 0.0

                position = {
                    'ticker': ticker,
                    'sector': row['sector'] or 'Nieznany',
                    'currency': row['currency'] or 'PLN',
                    'quantity': quantity,
                    'total_cost': total_cost,
                    'current_price': current_price,
                    'current_value': current_value,
                    'unrealized_pnl': unrealized_pnl,
                    'unrealized_pnl_pct': unrealized_pnl_pct,
                }
                positions.append(position)
                total_portfolio_value += current_value
                print(f"Processed {ticker}: {current_value}")

            for position in positions:
                weight = (position['current_value'] / total_portfolio_value * 100) if total_portfolio_value > 0 else 0.0
                position['weight_pct'] = weight

            print(f"Total Portfolio Value: {total_portfolio_value}")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error: {e}")

if __name__ == "__main__":
    test_query()
