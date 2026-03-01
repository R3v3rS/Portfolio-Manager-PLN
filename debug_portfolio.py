
import sys
import os

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database import get_db, init_db
from portfolio_service import PortfolioService
import sqlite3
from flask import Flask

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(os.getcwd(), 'instance', 'database.sqlite')

def inspect_portfolios():
    with app.app_context():
        try:
            db = get_db()
            portfolios = db.execute('SELECT * FROM portfolios').fetchall()
            print(f"Found {len(portfolios)} portfolios.")
            
            for p in portfolios:
                print(f"Checking portfolio: ID={p['id']}, Name={p['name']}")
                try:
                    # Inspect holdings
                    holdings = db.execute('SELECT * FROM holdings WHERE portfolio_id = ?', (p['id'],)).fetchall()
                    print(f"  Holdings: {len(holdings)}")
                    for h in holdings:
                        print(f"    Ticker: {h['ticker']}, Qty: {h['quantity']}, Currency: {h['currency']}, AutoFX: {h['auto_fx_fees']}")
                    
                    # Try to get value
                    val = PortfolioService.get_portfolio_value(p['id'])
                    print(f"  Value: {val['portfolio_value']}")
                except Exception as e:
                    print(f"  ERROR processing portfolio {p['id']}: {e}")
                    import traceback
                    traceback.print_exc()

        except Exception as e:
            print(f"Global error: {e}")

if __name__ == "__main__":
    if not os.path.exists(app.config['DATABASE']):
        print(f"Database not found at {app.config['DATABASE']}")
    else:
        inspect_portfolios()
