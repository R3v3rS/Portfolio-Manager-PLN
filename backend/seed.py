import sqlite3
import datetime
from datetime import timedelta
import os
from database import init_db
from flask import Flask

def seed_database():
    app = Flask(__name__)
    db_path = os.path.join(os.path.dirname(__file__), 'portfolio.db')
    app.config['DATABASE'] = db_path
    
    # Initialize the database to create all tables
    init_db(app)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create a sample portfolio
        cursor.execute("""
            INSERT INTO portfolios (name, account_type, current_cash, total_deposits, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, ('Emerytura IKE', 'IKE', 2500.0, 15000.0, '2023-01-01'))
        
        portfolio_id = cursor.lastrowid
        
        # Add some initial deposits
        cursor.execute("""
            INSERT INTO transactions (portfolio_id, type, ticker, quantity, price, total_value, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (portfolio_id, 'DEPOSIT', 'CASH', 1, 15000.0, 15000.0, '2023-01-01'))

        # Add some stock purchases
        transactions = [
            (portfolio_id, 'BUY', 'CDR.WA', 10, 120.50, 1205.0, '2023-01-15'),
            (portfolio_id, 'BUY', 'AAPL', 5, 150.0, 750.0, '2023-02-10'),
            (portfolio_id, 'BUY', 'PKO.WA', 50, 30.20, 1510.0, '2023-03-05'),
            (portfolio_id, 'BUY', 'MSFT', 10, 250.0, 2500.0, '2023-04-20'),
            (portfolio_id, 'BUY', 'CDR.WA', 5, 110.0, 550.0, '2023-06-10'),
            (portfolio_id, 'SELL', 'PKO.WA', 20, 35.0, 700.0, '2023-08-15'),
            (portfolio_id, 'DIVIDEND', 'AAPL', 1, 15.0, 15.0, '2023-09-01'),
        ]
        
        cursor.executemany("""
            INSERT INTO transactions (portfolio_id, type, ticker, quantity, price, total_value, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, transactions)

        # Update cash balance based on transactions
        cursor.execute("UPDATE portfolios SET current_cash = 8280.0 WHERE id = ?", (portfolio_id,))

        # Add holdings
        holdings = [
            (portfolio_id, 'CDR.WA', 15, 117.0, 1755.0, 'CD Projekt', 'Gaming', 'Tech'),
            (portfolio_id, 'AAPL', 5, 150.0, 750.0, 'Apple', 'Tech', 'Hardware'),
            (portfolio_id, 'PKO.WA', 30, 30.20, 906.0, 'PKO BP', 'Finance', 'Banking'),
            (portfolio_id, 'MSFT', 10, 250.0, 2500.0, 'Microsoft', 'Tech', 'Software'),
        ]

        cursor.executemany("""
            INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost, company_name, sector, industry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, holdings)

        # Add some historical prices for the charts
        today = datetime.date.today()
        price_history = []
        for i in range(30):
            date = today - timedelta(days=30 - i)
            price_history.append(('CDR.WA', date.strftime('%Y-%m-%d'), 110 + (i * 0.5) + (i % 4 * 2)))
            price_history.append(('AAPL', date.strftime('%Y-%m-%d'), 150 + (i * 1.5) - (i % 3 * 1)))
            
        cursor.executemany("""
            INSERT OR IGNORE INTO stock_prices (ticker, date, close_price)
            VALUES (?, ?, ?)
        """, price_history)

        conn.commit()
        print("Przykładowe dane zostały dodane pomyślnie!")

    except Exception as e:
        print(f"Wystąpił błąd: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    seed_database()
