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
        
        # Watchlist table
        db.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT UNIQUE NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

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

        db.execute('''
            CREATE TABLE IF NOT EXISTS ppk_weekly_history (
                fund_id VARCHAR(20) PRIMARY KEY,
                data TEXT NOT NULL,
                last_week TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # PPK portfolios table
        db.execute('''
            CREATE TABLE IF NOT EXISTS ppk_portfolios (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id) REFERENCES portfolios(id)
            );
        ''')

        # PPK transactions table
        db.execute('''
            CREATE TABLE IF NOT EXISTS ppk_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                employee_units DECIMAL(14,6) NOT NULL,
                employer_units DECIMAL(14,6) NOT NULL,
                price_per_unit DECIMAL(14,6) NOT NULL,
                FOREIGN KEY (portfolio_id) REFERENCES ppk_portfolios(id)
            );
        ''')

        db.execute('CREATE INDEX IF NOT EXISTS idx_ppk_transactions_portfolio ON ppk_transactions(portfolio_id);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_ppk_transactions_date ON ppk_transactions(date);')
        
        # Create index for portfolios name
        db.execute('CREATE INDEX IF NOT EXISTS idx_portfolios_name ON portfolios(name);')

        # Transactions table (Portfolio)
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

        # Latest price cache state (limits automatic refreshes to once per day)
        db.execute('''
            CREATE TABLE IF NOT EXISTS price_cache (
                ticker VARCHAR(20) PRIMARY KEY,
                price DECIMAL(12,4),
                updated_at TEXT,
                last_attempted_at TEXT
            );
        ''')

        # Radar cache table (snapshot to avoid frequent API calls)
        db.execute('''
            CREATE TABLE IF NOT EXISTS radar_cache (
                ticker VARCHAR(10) PRIMARY KEY,
                price DECIMAL(10,2),
                change_1d DECIMAL(10,2),
                change_7d DECIMAL(10,2),
                change_1m DECIMAL(10,2),
                change_1y DECIMAL(10,2),
                next_earnings DATE,
                ex_dividend_date DATE,
                dividend_yield DECIMAL(10,6),
                score INTEGER,
                last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Migrations: Add score column if it doesn't exist (for existing databases)
        try:
            db.execute('ALTER TABLE radar_cache ADD COLUMN score INTEGER;')
        except:
            # Column already exists or table doesn't exist yet (handled by CREATE TABLE)
            pass

        # Asset metadata cache table (to avoid repeated yfinance info calls)
        db.execute('''
            CREATE TABLE IF NOT EXISTS asset_metadata (
                ticker VARCHAR(20) PRIMARY KEY,
                company_name TEXT,
                sector TEXT,
                industry TEXT,
                currency VARCHAR(10) DEFAULT 'PLN',
                updated_at TEXT NOT NULL
            );
        ''')

        # Symbol mappings table (CSV import symbol -> ticker resolver)
        db.execute('''
            CREATE TABLE IF NOT EXISTS symbol_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_input TEXT UNIQUE NOT NULL,
                ticker VARCHAR(20) NOT NULL,
                currency VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        db.execute('CREATE INDEX IF NOT EXISTS idx_symbol_mappings_symbol_input ON symbol_mappings(symbol_input);')
        
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

        # Loans table
        db.execute('''
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                original_amount DECIMAL(15,2) NOT NULL,
                duration_months INTEGER NOT NULL,
                start_date DATE NOT NULL,
                installment_type VARCHAR(20) NOT NULL CHECK (installment_type IN ('EQUAL', 'DECREASING')),
                category VARCHAR(20) DEFAULT 'GOTOWKOWY'
            );
        ''')

        # Loan Rates table
        db.execute('''
            CREATE TABLE IF NOT EXISTS loan_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id INTEGER NOT NULL,
                interest_rate DECIMAL(5,2) NOT NULL,
                valid_from_date DATE NOT NULL,
                FOREIGN KEY (loan_id) REFERENCES loans(id)
            );
        ''')

        # Loan Overpayments table
        db.execute('''
            CREATE TABLE IF NOT EXISTS loan_overpayments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id INTEGER NOT NULL,
                amount DECIMAL(15,2) NOT NULL,
                date DATE NOT NULL,
                type VARCHAR(20) DEFAULT 'REDUCE_TERM' CHECK (type IN ('REDUCE_TERM', 'REDUCE_INSTALLMENT')),
                FOREIGN KEY (loan_id) REFERENCES loans(id)
            );
        ''')

        # --- Budgeting Module Tables ---

        # Budget Accounts (renamed from 'accounts' to avoid confusion if any, but prompt said 'accounts')
        # Since there is no 'accounts' table yet (only portfolios), I will use 'budget_accounts' to be safe,
        # or just 'accounts' if I'm sure. I'll use 'budget_accounts' to be distinct from potential future features.
        # WAIT, prompt specifically asked for "accounts". I'll use "budget_accounts" to be safe but map it in my mind.
        # Actually, let's stick to "budget_accounts" to avoid name collision with potentially existing auth accounts tables often found in such apps.
        db.execute('''
            CREATE TABLE IF NOT EXISTS budget_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                balance DECIMAL(15,2) DEFAULT 0.00,
                currency VARCHAR(3) DEFAULT 'PLN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Envelope Categories
        db.execute('''
            CREATE TABLE IF NOT EXISTS envelope_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                icon VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Envelopes
        db.execute('''
            CREATE TABLE IF NOT EXISTS envelopes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                account_id INTEGER DEFAULT 1,
                name VARCHAR(100) NOT NULL,
                icon VARCHAR(20),
                target_amount DECIMAL(10,2),
                balance DECIMAL(10,2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES envelope_categories(id),
                FOREIGN KEY (account_id) REFERENCES budget_accounts(id)
            );
        ''')

        # Budget Transactions (renamed from 'transactions' to avoid collision with portfolio transactions)
        db.execute('''
            CREATE TABLE IF NOT EXISTS budget_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type VARCHAR(20) NOT NULL CHECK (type IN ('INCOME', 'ALLOCATE', 'EXPENSE', 'TRANSFER', 'BORROW', 'REPAY')),
                amount DECIMAL(15,2) NOT NULL,
                account_id INTEGER,
                envelope_id INTEGER,
                related_envelope_id INTEGER,
                description TEXT,
                date DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES budget_accounts(id),
                FOREIGN KEY (envelope_id) REFERENCES envelopes(id),
                FOREIGN KEY (related_envelope_id) REFERENCES envelopes(id)
            );
        ''')

        # Envelope Loans (Internal Borrowing)
        db.execute('''
            CREATE TABLE IF NOT EXISTS envelope_loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_envelope_id INTEGER NOT NULL,
                amount DECIMAL(15,2) NOT NULL,
                reason TEXT,
                borrow_date DATE DEFAULT CURRENT_DATE,
                due_date DATE,
                repaid_amount DECIMAL(15,2) DEFAULT 0.00,
                status VARCHAR(10) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_envelope_id) REFERENCES envelopes(id)
            );
        ''')


        # Migration: move PPK transaction model from contribution amounts to units
        ppk_columns = {row['name'] for row in db.execute("PRAGMA table_info(ppk_transactions)").fetchall()}
        if ppk_columns and 'employee_contribution' in ppk_columns:
            db.execute('''
                CREATE TABLE IF NOT EXISTS ppk_transactions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    employee_units DECIMAL(14,6) NOT NULL,
                    employer_units DECIMAL(14,6) NOT NULL,
                    price_per_unit DECIMAL(14,6) NOT NULL,
                    FOREIGN KEY (portfolio_id) REFERENCES ppk_portfolios(id)
                );
            ''')

            db.execute('''
                INSERT INTO ppk_transactions_new (id, portfolio_id, date, employee_units, employer_units, price_per_unit)
                SELECT
                    id,
                    portfolio_id,
                    date,
                    CASE
                        WHEN COALESCE(price_per_unit, 0) > 0 THEN
                            (
                                COALESCE(employee_contribution, 0) / price_per_unit
                            )
                            *
                            CASE
                                WHEN (COALESCE(employee_contribution, 0) + COALESCE(employer_contribution, 0)) > 0
                                THEN COALESCE(units_purchased, 0) / ((COALESCE(employee_contribution, 0) + COALESCE(employer_contribution, 0)) / price_per_unit)
                                ELSE 1
                            END
                        ELSE
                            CASE
                                WHEN (COALESCE(employee_contribution, 0) + COALESCE(employer_contribution, 0)) > 0
                                THEN COALESCE(units_purchased, 0) * (COALESCE(employee_contribution, 0) / (COALESCE(employee_contribution, 0) + COALESCE(employer_contribution, 0)))
                                ELSE COALESCE(units_purchased, 0) / 2.0
                            END
                    END AS employee_units,
                    CASE
                        WHEN COALESCE(price_per_unit, 0) > 0 THEN
                            (
                                COALESCE(employer_contribution, 0) / price_per_unit
                            )
                            *
                            CASE
                                WHEN (COALESCE(employee_contribution, 0) + COALESCE(employer_contribution, 0)) > 0
                                THEN COALESCE(units_purchased, 0) / ((COALESCE(employee_contribution, 0) + COALESCE(employer_contribution, 0)) / price_per_unit)
                                ELSE 1
                            END
                        ELSE
                            CASE
                                WHEN (COALESCE(employee_contribution, 0) + COALESCE(employer_contribution, 0)) > 0
                                THEN COALESCE(units_purchased, 0) * (COALESCE(employer_contribution, 0) / (COALESCE(employee_contribution, 0) + COALESCE(employer_contribution, 0)))
                                ELSE COALESCE(units_purchased, 0) / 2.0
                            END
                    END AS employer_units,
                    COALESCE(price_per_unit, 0)
                FROM ppk_transactions;
            ''')

            db.execute('DROP TABLE ppk_transactions')
            db.execute('ALTER TABLE ppk_transactions_new RENAME TO ppk_transactions')
            db.execute('CREATE INDEX IF NOT EXISTS idx_ppk_transactions_portfolio ON ppk_transactions(portfolio_id);')
            db.execute('CREATE INDEX IF NOT EXISTS idx_ppk_transactions_date ON ppk_transactions(date);')

        # Migration: Add 'type' column to loan_overpayments if it doesn't exist
        try:
            db.execute("ALTER TABLE loan_overpayments ADD COLUMN type VARCHAR(20) DEFAULT 'REDUCE_TERM'")
        except sqlite3.OperationalError:
            pass

        # Migration: Add 'category' column to loans if it doesn't exist
        try:
            db.execute("ALTER TABLE loans ADD COLUMN category VARCHAR(20) DEFAULT 'GOTOWKOWY'")
        except sqlite3.OperationalError:
            pass

        # Migration: Add 'account_id' column to envelopes if it doesn't exist
        try:
            db.execute("ALTER TABLE envelopes ADD COLUMN account_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

        # Migration: Add 'type', 'target_month', 'status' to envelopes
        try:
            db.execute("ALTER TABLE envelopes ADD COLUMN type VARCHAR(20) DEFAULT 'MONTHLY'")
        except sqlite3.OperationalError:
            pass
            
        try:
            db.execute("ALTER TABLE envelopes ADD COLUMN target_month VARCHAR(7)") 
            # Set default target_month for existing Monthly envelopes to current month
            db.execute("UPDATE envelopes SET target_month = strftime('%Y-%m', 'now') WHERE type = 'MONTHLY' AND target_month IS NULL")
        except sqlite3.OperationalError:
            pass

        try:
            db.execute("ALTER TABLE envelopes ADD COLUMN status VARCHAR(10) DEFAULT 'ACTIVE'")
        except sqlite3.OperationalError:
            pass
            
        # Migration: Ensure 'balance' column exists in envelopes (if I added it later, but here I created it fresh. 
        # However, if table existed from previous failed run, might be issue. 
        # But this is a new module, so tables shouldn't exist.)

        # Migration: Add asset metadata columns to holdings
        try:
            db.execute("ALTER TABLE holdings ADD COLUMN company_name TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE holdings ADD COLUMN sector TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE holdings ADD COLUMN industry TEXT")
        except sqlite3.OperationalError:
            pass

        # Migration: Add 'auto_fx_fees' and 'currency' to holdings
        try:
            db.execute("ALTER TABLE holdings ADD COLUMN auto_fx_fees BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE holdings ADD COLUMN currency VARCHAR(3) DEFAULT 'PLN'")
        except sqlite3.OperationalError:
            pass

        # Migration: Add 'commission' to transactions
        try:
            db.execute("ALTER TABLE transactions ADD COLUMN commission DECIMAL(10,2) DEFAULT 0.00")
        except sqlite3.OperationalError:
            pass

        # Inflation data table
        db.execute('''
            CREATE TABLE IF NOT EXISTS inflation_data (
                date TEXT PRIMARY KEY,
                index_value REAL NOT NULL
            );
        ''')

        db.commit()

def reset_budget_data():
    """
    Resets all budget-related data for a fresh start.
    Clears: budget_transactions, envelopes, envelope_loans, budget_accounts (balance reset? or delete?)
    User prompt says: "CLEAR ALL DATA from the following tables: budget_transactions, envelopes, envelope_loans, and budget_accounts."
    """
    db = get_db()
    # Disable foreign keys temporarily to avoid constraint errors during deletion
    db.execute("PRAGMA foreign_keys = OFF")
    
    db.execute("DELETE FROM budget_transactions")
    db.execute("DELETE FROM envelope_loans")
    db.execute("DELETE FROM envelopes")
    db.execute("DELETE FROM budget_accounts")
    db.execute("DELETE FROM envelope_categories") # Optional, but maybe good for full reset? User didn't specify categories.
    # User specified: budget_transactions, envelopes, envelope_loans, and budget_accounts.
    # I will stick to those.
    
    # Reset sequences
    db.execute("DELETE FROM sqlite_sequence WHERE name='budget_transactions'")
    db.execute("DELETE FROM sqlite_sequence WHERE name='envelope_loans'")
    db.execute("DELETE FROM sqlite_sequence WHERE name='envelopes'")
    db.execute("DELETE FROM sqlite_sequence WHERE name='budget_accounts'")
    
    db.execute("PRAGMA foreign_keys = ON")
    db.commit()
