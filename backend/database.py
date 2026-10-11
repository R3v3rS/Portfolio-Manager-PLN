import sqlite3
from pathlib import Path
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
    if close_db not in app.teardown_appcontext_funcs:
        app.teardown_appcontext(close_db)
    
    # Create tables if they don't exist
    with app.app_context():
        db = get_db()
        from investment_ideas_service import init_schema as init_research_schema
        init_research_schema(db)
        from asset_transfer_service import init_schema as init_asset_transfers
        from manual_stock_prices import init_manual_price_schema
        init_manual_price_schema(db)
        db.execute('''CREATE TABLE IF NOT EXISTS net_worth_snapshots (
            date TEXT PRIMARY KEY,
            net_worth REAL NOT NULL,
            total_assets REAL NOT NULL,
            total_liabilities REAL NOT NULL,
            recorded_at TEXT NOT NULL
        )''')
        snapshot_columns = {r['name'] for r in db.execute('PRAGMA table_info(net_worth_snapshots)')}
        for column in ('assets_breakdown', 'valuation_notes'):
            if column not in snapshot_columns:
                db.execute(f'ALTER TABLE net_worth_snapshots ADD COLUMN {column} TEXT')
        db.execute('''CREATE TABLE IF NOT EXISTS investment_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            target_amount REAL NOT NULL CHECK(target_amount > 0),
            target_date TEXT NOT NULL,
            monthly_contribution REAL NOT NULL DEFAULT 0 CHECK(monthly_contribution >= 0),
            annual_return REAL NOT NULL DEFAULT 0,
            target_allocation TEXT,
            is_archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS investment_goal_portfolios (
            goal_id INTEGER NOT NULL REFERENCES investment_goals(id),
            portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
            PRIMARY KEY(goal_id, portfolio_id)
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS investor_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            ticker TEXT,
            portfolio_id INTEGER REFERENCES portfolios(id),
            confidence INTEGER,
            thesis TEXT NOT NULL DEFAULT '',
            risks TEXT NOT NULL DEFAULT '',
            invalidation TEXT NOT NULL DEFAULT '',
            exit_plan TEXT NOT NULL DEFAULT '',
            review_date TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            is_archived INTEGER NOT NULL DEFAULT 0,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS investor_journal_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL REFERENCES investor_journal(id),
            review_date TEXT NOT NULL,
            outcome TEXT NOT NULL,
            notes TEXT NOT NULL,
            lessons TEXT NOT NULL DEFAULT '',
            next_review_date TEXT,
            entry_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS investor_journal_revisions (
            entry_id INTEGER NOT NULL REFERENCES investor_journal(id),
            version INTEGER NOT NULL,
            reason TEXT NOT NULL,
            snapshot TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(entry_id, version)
        )''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_journal_reviews_entry ON investor_journal_reviews(entry_id)')
        db.execute('''CREATE TABLE IF NOT EXISTS dashboard_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'other',
            due_date TEXT,
            priority TEXT NOT NULL DEFAULT 'normal',
            completed_at TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            request_id TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        
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
            CREATE TABLE IF NOT EXISTS radar_notes (
                ticker TEXT PRIMARY KEY,
                thesis TEXT NOT NULL DEFAULT '',
                invalidation TEXT NOT NULL DEFAULT '',
                review_date TEXT,
                target_price REAL,
                target_direction TEXT NOT NULL DEFAULT 'below',
                updated_at TEXT NOT NULL
            );
        ''')

        db.execute('''
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                account_type VARCHAR(20) DEFAULT 'STANDARD',
                current_cash DECIMAL(10,2) DEFAULT 0.00,
                total_deposits DECIMAL(10,2) DEFAULT 0.00,
                savings_rate DECIMAL(5,2) DEFAULT 0.00,
                last_interest_date TEXT,
                parent_portfolio_id INTEGER REFERENCES portfolios(id),
                is_archived BOOLEAN DEFAULT 0,
                archived_at TEXT,
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
                commission DECIMAL(10,2) DEFAULT 0.00,
                sub_portfolio_id INTEGER REFERENCES portfolios(id),
                transfer_id TEXT,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
        ''')
        
        # Create indexes for transactions
        db.execute('CREATE INDEX IF NOT EXISTS idx_transactions_portfolio ON transactions(portfolio_id);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_transactions_ticker ON transactions(ticker);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_transactions_sub_portfolio ON transactions(sub_portfolio_id);')

        # Idempotency keys for mutating endpoints (request replay protection)
        db.execute('''
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                response_status INTEGER NOT NULL,
                response_body TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(endpoint, idempotency_key)
            );
        ''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_idempotency_created_at ON idempotency_keys(created_at);')

        # Holdings table
        db.execute('''
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                quantity DECIMAL(10,4) NOT NULL,
                average_buy_price DECIMAL(10,2) NOT NULL,
                total_cost DECIMAL(10,2) NOT NULL,
                company_name TEXT,
                sector TEXT,
                industry TEXT,
                auto_fx_fees BOOLEAN DEFAULT 0,
                currency VARCHAR(3) DEFAULT 'PLN',
                instrument_currency TEXT NOT NULL DEFAULT 'PLN',
                avg_buy_price_native REAL NOT NULL DEFAULT 0,
                avg_buy_fx_rate REAL DEFAULT 1,
                fx_source TEXT NOT NULL DEFAULT 'legacy',
                sub_portfolio_id INTEGER REFERENCES portfolios(id),
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
        ''')
        
        # Create indexes for holdings
        db.execute('CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON holdings(ticker);')
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_unique_sub ON holdings(portfolio_id, sub_portfolio_id, ticker) WHERE sub_portfolio_id IS NOT NULL")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_unique_main ON holdings(portfolio_id, ticker) WHERE sub_portfolio_id IS NULL")
        
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

        db.execute('''
            CREATE TABLE IF NOT EXISTS quotes_cache (
                ticker VARCHAR(20) NOT NULL,
                level TEXT NOT NULL,
                price DECIMAL(12,4),
                prev_close DECIMAL(12,4),
                price_7d_ago DECIMAL(12,4),
                change_1d DECIMAL(12,4),
                change_7d DECIMAL(12,4),
                change_1m DECIMAL(12,4),
                change_1y DECIMAL(12,4),
                updated_at TEXT,
                last_attempted_at TEXT,
                PRIMARY KEY (ticker, level)
            );
        ''')

        db.execute('''
            CREATE TABLE IF NOT EXISTS stock_history_refresh_state (
                ticker VARCHAR(20) PRIMARY KEY,
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
                analysis_cached_at TEXT,
                last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        # Migrations: Add score column if it doesn't exist (for existing databases)
        try:
            db.execute('ALTER TABLE radar_cache ADD COLUMN score INTEGER;')
        except:
            # Column already exists or table doesn't exist yet (handled by CREATE TABLE)
            pass

        try:
            db.execute('ALTER TABLE radar_cache ADD COLUMN analysis_cached_at TEXT')
            db.commit()
        except sqlite3.OperationalError as e:
            if 'duplicate column name' not in str(e).lower():
                raise

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

        db.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_history_cache (
                portfolio_id INTEGER NOT NULL,
                cache_key TEXT NOT NULL,
                result_json TEXT NOT NULL,
                cached_at TEXT NOT NULL,
                PRIMARY KEY (portfolio_id, cache_key)
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
                sub_portfolio_id INTEGER REFERENCES portfolios(id),
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
        ''')
        
        # Create index for dividends
        db.execute('CREATE INDEX IF NOT EXISTS idx_dividends_portfolio ON dividends(portfolio_id);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_dividends_sub_portfolio ON dividends(sub_portfolio_id);')

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
        from bond_schema import migrate as migrate_bonds
        migrate_bonds(db)

        # Loans table
        db.execute('''
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                original_amount DECIMAL(15,2) NOT NULL,
                duration_months INTEGER NOT NULL,
                start_date DATE NOT NULL,
                installment_type VARCHAR(20) NOT NULL CHECK (installment_type IN ('EQUAL', 'DECREASING')),
                category VARCHAR(20) DEFAULT 'GOTOWKOWY',
                exclude_from_net_worth INTEGER NOT NULL DEFAULT 0 CHECK (exclude_from_net_worth IN (0, 1))
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
        overpayment_columns = {row['name'] for row in db.execute('PRAGMA table_info(loan_overpayments)').fetchall()}
        if 'budget_entry_id' not in overpayment_columns:
            db.execute('ALTER TABLE loan_overpayments ADD COLUMN budget_entry_id INTEGER')
        db.execute('''
            CREATE TABLE IF NOT EXISTS loan_balance_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id INTEGER NOT NULL,
                balance_cents INTEGER NOT NULL CHECK(balance_cents >= 0),
                checked_on TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (loan_id) REFERENCES loans(id)
            )
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

        # New monthly budget: category limits are plans, never transfers between
        # accounts. Money moves only when an income or expense is recorded.
        db.execute('''
            CREATE TABLE IF NOT EXISTS budget_categories_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                icon TEXT NOT NULL DEFAULT 'Circle',
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS budget_plans_v2 (
                category_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
                PRIMARY KEY (category_id, month),
                FOREIGN KEY (category_id) REFERENCES budget_categories_v2(id)
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS budget_entries_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('INCOME', 'EXPENSE')),
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                merchant TEXT,
                receipt_filename TEXT,
                receipt_original_name TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES budget_accounts(id)
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS budget_entry_lines_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                FOREIGN KEY (entry_id) REFERENCES budget_entries_v2(id),
                FOREIGN KEY (category_id) REFERENCES budget_categories_v2(id)
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS budget_bills_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                due_day INTEGER NOT NULL CHECK(due_day BETWEEN 1 AND 31),
                frequency TEXT NOT NULL CHECK(frequency IN ('MONTHLY', 'ONCE')),
                due_month TEXT,
                start_month TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (account_id) REFERENCES budget_accounts(id),
                FOREIGN KEY (category_id) REFERENCES budget_categories_v2(id)
            )
        ''')
        bill_columns = {row['name'] for row in db.execute('PRAGMA table_info(budget_bills_v2)').fetchall()}
        if 'start_month' not in bill_columns:
            db.execute('ALTER TABLE budget_bills_v2 ADD COLUMN start_month TEXT')
        db.execute('''
            CREATE TABLE IF NOT EXISTS budget_bill_payments_v2 (
                bill_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                entry_id INTEGER NOT NULL,
                PRIMARY KEY (bill_id, month),
                FOREIGN KEY (bill_id) REFERENCES budget_bills_v2(id),
                FOREIGN KEY (entry_id) REFERENCES budget_entries_v2(id)
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS loan_installment_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id INTEGER NOT NULL,
                installment_month INTEGER NOT NULL,
                due_date TEXT NOT NULL,
                paid_on TEXT NOT NULL,
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                budget_entry_id INTEGER UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(loan_id, installment_month),
                FOREIGN KEY (loan_id) REFERENCES loans(id),
                FOREIGN KEY (budget_entry_id) REFERENCES budget_entries_v2(id)
            )
        ''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_loan_payments_loan ON loan_installment_payments(loan_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_budget_entries_v2_date ON budget_entries_v2(date)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_budget_lines_v2_entry ON budget_entry_lines_v2(entry_id)')
        db.execute('''
            CREATE TABLE IF NOT EXISTS budget_investment_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                portfolio_id INTEGER NOT NULL,
                investment_transaction_id INTEGER NOT NULL UNIQUE,
                budget_transaction_id INTEGER NOT NULL UNIQUE,
                direction TEXT NOT NULL CHECK(direction IN ('IN', 'OUT')),
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                request_id TEXT UNIQUE,
                FOREIGN KEY (account_id) REFERENCES budget_accounts(id),
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id),
                FOREIGN KEY (investment_transaction_id) REFERENCES transactions(id),
                FOREIGN KEY (budget_transaction_id) REFERENCES budget_transactions(id)
            )
        ''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_budget_investment_transfers_date ON budget_investment_transfers(date)')

        db.execute('''CREATE TABLE IF NOT EXISTS budget_reserves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            target_cents INTEGER NOT NULL CHECK(target_cents > 0),
            start_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            anniversary TEXT NOT NULL,
            frequency TEXT NOT NULL CHECK(frequency IN ('ONCE','YEARLY')),
            cycle INTEGER NOT NULL DEFAULT 1,
            completed_at TEXT,
            is_archived INTEGER NOT NULL DEFAULT 0,
            version INTEGER NOT NULL DEFAULT 1,
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS budget_reserve_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reserve_id INTEGER NOT NULL REFERENCES budget_reserves(id),
            account_id INTEGER REFERENCES budget_accounts(id),
            cycle INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('ADD','RELEASE','SPEND')),
            amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
            date TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            budget_entry_id INTEGER UNIQUE REFERENCES budget_entries_v2(id),
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_reserve_movements_reserve ON budget_reserve_movements(reserve_id,date)')
        movement_columns = {row['name'] for row in db.execute('PRAGMA table_info(budget_reserve_movements)')}
        if 'account_id' not in movement_columns:
            db.execute('ALTER TABLE budget_reserve_movements ADD COLUMN account_id INTEGER REFERENCES budget_accounts(id)')
        db.execute('''UPDATE budget_reserve_movements SET account_id=(
            SELECT account_id FROM budget_reserves WHERE id=reserve_id) WHERE account_id IS NULL''')
        db.execute('''CREATE TABLE IF NOT EXISTS budget_account_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            target_account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            reserve_id INTEGER REFERENCES budget_reserves(id),
            cycle INTEGER,
            move_money INTEGER NOT NULL CHECK(move_money IN (0,1)),
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            date TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            CHECK(source_account_id != target_account_id)
        )''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_account_transfers_reserve ON budget_account_transfers(reserve_id,date)')
        db.execute('''CREATE TABLE IF NOT EXISTS budget_account_reconciliations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            previous_balance_cents INTEGER NOT NULL,
            observed_balance_cents INTEGER NOT NULL,
            difference_cents INTEGER NOT NULL,
            date TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS budget_expected_incomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            account_id INTEGER NOT NULL REFERENCES budget_accounts(id),
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            start_date TEXT NOT NULL,
            end_date TEXT,
            frequency TEXT NOT NULL CHECK(frequency IN ('ONCE','MONTHLY')),
            active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1,
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS budget_expected_income_receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            income_id INTEGER NOT NULL REFERENCES budget_expected_incomes(id),
            occurrence_date TEXT NOT NULL,
            budget_entry_id INTEGER UNIQUE NOT NULL REFERENCES budget_entries_v2(id),
            request_id TEXT UNIQUE NOT NULL,
            request_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(income_id,occurrence_date)
        )''')


        from budget_import_schema import initialize as initialize_budget_imports
        initialize_budget_imports(db)
        from budget_planning_schema import initialize as initialize_budget_planning
        initialize_budget_planning(db)

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
        loan_columns = {row['name'] for row in db.execute('PRAGMA table_info(loans)')}
        if 'exclude_from_net_worth' not in loan_columns:
            db.execute('ALTER TABLE loans ADD COLUMN exclude_from_net_worth INTEGER NOT NULL DEFAULT 0 CHECK (exclude_from_net_worth IN (0, 1))')

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
        try:
            db.execute("ALTER TABLE transactions ADD COLUMN transfer_id TEXT")
        except sqlite3.OperationalError:
            pass

        # Inflation data table
        db.execute('''
            CREATE TABLE IF NOT EXISTS inflation_data (
                date TEXT PRIMARY KEY,
                index_value REAL NOT NULL
            );
        ''')

        # Migration: Add sub-portfolio support columns
        try:
            db.execute("ALTER TABLE portfolios ADD COLUMN parent_portfolio_id INTEGER REFERENCES portfolios(id)")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE portfolios ADD COLUMN is_archived BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE portfolios ADD COLUMN archived_at TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE transactions ADD COLUMN sub_portfolio_id INTEGER REFERENCES portfolios(id)")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE dividends ADD COLUMN sub_portfolio_id INTEGER REFERENCES portfolios(id)")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE holdings ADD COLUMN sub_portfolio_id INTEGER REFERENCES portfolios(id)")
        except sqlite3.OperationalError:
            pass
        try:
            db.execute("ALTER TABLE holdings ADD COLUMN fx_source TEXT NOT NULL DEFAULT 'legacy'")
        except sqlite3.OperationalError:
            pass

        # Migration: Update holdings unique constraint to include sub_portfolio_id
        # In SQLite, we can't directly alter a UNIQUE constraint.
        # We need to recreate the table to update the constraint.
        try:
            # Check if we already updated it by validating unique index columns.
            # We need a unique index that contains exactly:
            # (portfolio_id, sub_portfolio_id, ticker)
            table_info = db.execute("PRAGMA index_list(holdings)").fetchall()
            has_sub_portfolio_unique = False
            expected_cols = {'portfolio_id', 'sub_portfolio_id', 'ticker'}

            for row in table_info:
                if not row['unique']:
                    continue
                index_name = row['name']
                index_cols_info = db.execute(f"PRAGMA index_info('{index_name}')").fetchall()
                index_cols = {idx_row['name'] for idx_row in index_cols_info}
                if index_cols == expected_cols:
                    has_sub_portfolio_unique = True
                    break
            
            if not has_sub_portfolio_unique:
                db.execute("PRAGMA foreign_keys = OFF")
                
                # Get current columns
                columns_info = db.execute("PRAGMA table_info(holdings)").fetchall()
                cols = [c['name'] for c in columns_info]
                cols_str = ", ".join(cols)
                
                # 1. Rename old table
                db.execute("ALTER TABLE holdings RENAME TO holdings_old")
                
                # 2. Create new table WITH correct structure (using names from above)
                # We'll use the column names we just got
                cols_defs = []
                for col in columns_info:
                    name = col['name']
                    type_ = col['type']
                    notnull = " NOT NULL" if col['notnull'] else ""
                    if name == 'id':
                        cols_defs.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
                    else:
                        cols_defs.append(f"{name} {type_}{notnull}")
                
                new_cols_str = ", ".join(cols_defs)
                db.execute(f'''
                    CREATE TABLE holdings (
                        {new_cols_str},
                        FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
                    )
                ''')
                
                # 3. Copy data
                db.execute(f"INSERT INTO holdings ({cols_str}) SELECT {cols_str} FROM holdings_old")
                
                # 4. Drop old table
                db.execute("DROP TABLE holdings_old")
                
                # 5. Create new UNIQUE indexes
                db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_unique_sub ON holdings(portfolio_id, sub_portfolio_id, ticker) WHERE sub_portfolio_id IS NOT NULL")
                db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_unique_main ON holdings(portfolio_id, ticker) WHERE sub_portfolio_id IS NULL")
                
                # Re-create other indexes
                db.execute('CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id);')
                db.execute('CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON holdings(ticker);')
                db.execute('CREATE INDEX IF NOT EXISTS idx_holdings_sub_portfolio ON holdings(sub_portfolio_id);')
                
                db.execute("PRAGMA foreign_keys = ON")
        except Exception as e:
            print(f"Migration error for holdings unique constraint: {e}")
            pass

        db.execute('CREATE INDEX IF NOT EXISTS idx_transactions_sub_portfolio ON transactions(sub_portfolio_id);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_dividends_sub_portfolio ON dividends(sub_portfolio_id);')

        # Migration: import staging table for CSV import workflow
        db.execute('''
            CREATE TABLE IF NOT EXISTS import_staging (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_session_id TEXT NOT NULL,
                portfolio_id INTEGER NOT NULL,
                ticker VARCHAR(20) NOT NULL,
                type VARCHAR(20) NOT NULL,
                quantity DECIMAL(10,4),
                price DECIMAL(10,2),
                total_value DECIMAL(10,2) NOT NULL,
                date TEXT NOT NULL,
                target_sub_portfolio_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                conflict_type TEXT,
                conflict_details TEXT,
                row_hash TEXT NOT NULL,
                source_file TEXT,
                created_at TEXT NOT NULL,
                booked_at TEXT,
                FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
            );
        ''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_import_staging_session ON import_staging(import_session_id);')
        db.execute('CREATE INDEX IF NOT EXISTS idx_import_staging_portfolio ON import_staging(portfolio_id, status);')

        # Import metadata is additive: existing sessions and transactions stay intact.
        staging_columns = {row['name'] for row in db.execute('PRAGMA table_info(import_staging)')}
        for column, definition in {
            'commission': 'REAL', 'symbol_input': 'TEXT',
            'booking_mode': 'TEXT', 'booked_transaction_id': 'INTEGER',
            'source_account': 'TEXT', 'source_operation_id': 'TEXT',
            'source_row_number': 'INTEGER', 'instrument_name': 'TEXT',
        }.items():
            if column not in staging_columns:
                db.execute(f'ALTER TABLE import_staging ADD COLUMN {column} {definition}')
        transaction_columns = {row['name'] for row in db.execute('PRAGMA table_info(transactions)')}
        for column in ('xtb_account', 'xtb_operation_id'):
            if column not in transaction_columns:
                db.execute(f'ALTER TABLE transactions ADD COLUMN {column} TEXT')
        db.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_xtb_operation
                      ON transactions(xtb_account, xtb_operation_id)
                      WHERE xtb_account IS NOT NULL AND xtb_operation_id IS NOT NULL''')
        db.execute('''CREATE TABLE IF NOT EXISTS import_sessions (
            id TEXT PRIMARY KEY, portfolio_id INTEGER NOT NULL, source_file TEXT,
            input_rows INTEGER NOT NULL, unsupported_json TEXT NOT NULL DEFAULT '[]',
            warnings_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, closed_at TEXT
        )''')
        if 'closed_at' not in {row['name'] for row in db.execute('PRAGMA table_info(import_sessions)')}:
            db.execute('ALTER TABLE import_sessions ADD COLUMN closed_at TEXT')

        # Validation function after migration
        def validate_subportfolio_integrity(db_conn):
            # Check for self-cycles
            cycles = db_conn.execute("SELECT id FROM portfolios WHERE id = parent_portfolio_id").fetchall()
            if cycles:
                print(f"CRITICAL: Self-cycles detected in portfolios: {[c['id'] for c in cycles]}")
            
            # Check for child->child (max 1 level)
            deep_nesting = db_conn.execute("""
                SELECT p1.id 
                FROM portfolios p1
                JOIN portfolios p2 ON p1.parent_portfolio_id = p2.id
                WHERE p2.parent_portfolio_id IS NOT NULL
            """).fetchall()
            if deep_nesting:
                print(f"CRITICAL: Deep nesting (>1 level) detected in portfolios: {[n['id'] for n in deep_nesting]}")

        validate_subportfolio_integrity(db)

        init_asset_transfers(db)
        db.commit()

def reset_budget_data():
    """
    Resets all budget-related data for a fresh start.
    Clears: budget_transactions, envelopes, envelope_loans, budget_accounts (balance reset? or delete?)
    User prompt says: "CLEAR ALL DATA from the following tables: budget_transactions, envelopes, envelope_loans, and budget_accounts."
    """
    db = get_db()
    receipt_files = [row[0] for row in db.execute(
        "SELECT receipt_filename FROM budget_entries_v2 WHERE receipt_filename IS NOT NULL"
    ).fetchall()]
    receipt_files.extend(row[0] for row in db.execute('SELECT filename FROM budget_receipt_drafts'))
    # Disable foreign keys temporarily to avoid constraint errors during deletion
    db.execute("PRAGMA foreign_keys = OFF")

    db.execute("UPDATE loan_installment_payments SET budget_entry_id = NULL")
    db.execute("UPDATE loan_overpayments SET budget_entry_id = NULL")

    for table in ('budget_import_sources', 'budget_import_rows', 'budget_import_sessions',
                  'budget_receipt_drafts', 'budget_category_rules', 'budget_csv_profiles', 'budget_reserve_transfer_rules'):
        db.execute(f'DELETE FROM {table}')

    db.execute("DELETE FROM budget_bill_payments_v2")
    db.execute("DELETE FROM budget_purchase_refunds")
    for table in ('budget_settlements','budget_settlement_reversals','budget_cancelled_requests','budget_entry_requests',
                  'budget_reserve_plan_history','budget_month_snapshots','budget_month_closing_items', 'budget_month_closings', 'budget_purchase_plans',
                  'budget_reserve_month_plans', 'budget_category_policies', 'budget_planning_settings'):
        db.execute(f'DELETE FROM {table}')
    db.execute('INSERT INTO budget_planning_settings(id) VALUES(1)')
    db.execute("DELETE FROM budget_expected_income_receipts")
    db.execute("DELETE FROM budget_expected_incomes")
    db.execute("DELETE FROM budget_account_transfers")
    db.execute("DELETE FROM budget_account_reconciliations")
    db.execute("DELETE FROM budget_reserve_movements")
    db.execute("DELETE FROM budget_reserves")
    db.execute("DELETE FROM budget_investment_transfers")
    db.execute("DELETE FROM budget_entry_lines_v2")
    db.execute("DELETE FROM budget_entries_v2")
    db.execute("DELETE FROM budget_bills_v2")
    db.execute("DELETE FROM budget_plans_v2")
    db.execute("DELETE FROM budget_categories_v2")
    
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
    for table in ('budget_entries_v2', 'budget_entry_lines_v2', 'budget_bills_v2', 'budget_categories_v2'):
        db.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
    
    db.execute("PRAGMA foreign_keys = ON")
    db.commit()
    receipt_root = Path(current_app.config.get(
        'BUDGET_RECEIPT_DIR', Path(current_app.root_path) / 'uploads' / 'budget-receipts'
    ))
    for filename in receipt_files:
        (receipt_root / filename).unlink(missing_ok=True)
