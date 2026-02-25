import sqlite3
from flask import g, current_app

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(app):
    app.teardown_appcontext(close_db)
    
    # Create tables if they don't exist
    with app.app_context():
        db = get_db()
        
        # Portfolios table
        db.execute('''
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                account_type VARCHAR(20) DEFAULT 'STANDARD',
                current_cash DECIMAL(10,2) DEFAULT 0.00,
                total_deposits DECIMAL(10,2) DEFAULT 0.00,
                savings_rate DECIMAL(5,2) DEFAULT 0.00,
                last_interest_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create index for portfolios name
        db.execute('CREATE INDEX IF NOT EXISTS idx_portfolios_name ON portfolios(name);')

        # Transactions table
        db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                date TEXT DEFAULT CURRENT_TIMESTAMP,
                type VARCHAR(10) NOT NULL CHECK (type IN ('BUY', 'SELL', 'DEPOSIT', 'WITHDRAW', 'DIVIDEND', 'INTEREST')),
                quantity DECIMAL(10,4) NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                total_value DECIMAL(10,2) NOT NULL,
                realized_profit DECIMAL(10,2) DEFAULT 0.0,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
        ''')
        
        # Create indexes for transactions
        db.execute('CREATE INDEX IF NOT EXISTS idx_transactions_portfolio ON transactions(portfolio_id);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_transactions_ticker ON transactions(ticker);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);')

        # Holdings table
        db.execute('''
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                quantity DECIMAL(10,4) NOT NULL,
                average_buy_price DECIMAL(10,2) NOT NULL,
                total_cost DECIMAL(10,2) NOT NULL,
                UNIQUE(portfolio_id, ticker),
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
        ''')
        
        # Create indexes for holdings
        db.execute('CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON holdings(ticker);')
        
        # Stock prices history table
        db.execute('''
            CREATE TABLE IF NOT EXISTS stock_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker VARCHAR(10) NOT NULL,
                date DATE NOT NULL,
                close_price DECIMAL(10,2) NOT NULL,
                UNIQUE(ticker, date)
            );
        ''')
        
        # Create index for stock prices
        db.execute('CREATE INDEX IF NOT EXISTS idx_stock_prices_ticker ON stock_prices(ticker);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices(date);')
        
        # Dividends table
        db.execute('''
            CREATE TABLE IF NOT EXISTS dividends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                date DATE NOT NULL,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
        ''')
        
        # Create index for dividends
        db.execute('CREATE INDEX IF NOT EXISTS idx_dividends_portfolio ON dividends(portfolio_id);')

        # Bonds table
        db.execute('''
            CREATE TABLE IF NOT EXISTS bonds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL,
                principal DECIMAL(15,2) NOT NULL,
                interest_rate DECIMAL(5,2) NOT NULL,
                purchase_date DATE NOT NULL,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
        ''')
        
        # Create index for bonds
        db.execute('CREATE INDEX IF NOT EXISTS idx_bonds_portfolio ON bonds(portfolio_id);')
        
        db.commit()
