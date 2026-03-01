import sqlite3
from flask import g
from datetime import date as date_cls
from database import get_db

class BudgetService:
    @staticmethod
    def get_db():
        return get_db()

    @staticmethod
    def get_free_pool(account_id):
        db = BudgetService.get_db()
        account = db.execute("SELECT balance FROM budget_accounts WHERE id = ?", (account_id,)).fetchone()
        if not account:
            return 0.0
        
        # New Logic: Free Pool = Account Balance - Sum(Positive Envelopes) - Sum(Abs(Negative Envelopes))
        # This reserves funds to cover overspending immediately.
        
        sum_positive = db.execute("""
            SELECT SUM(balance) FROM envelopes 
            WHERE account_id = ? AND balance > 0 AND status = 'ACTIVE'
        """, (account_id,)).fetchone()[0] or 0.0
        
        sum_negative = db.execute("""
            SELECT SUM(ABS(balance)) FROM envelopes 
            WHERE account_id = ? AND balance < 0 AND status = 'ACTIVE'
        """, (account_id,)).fetchone()[0] or 0.0
        
        return float(account['balance']) - float(sum_positive) - float(sum_negative)

    @staticmethod
    def get_total_allocated(account_id):
        db = BudgetService.get_db()
        # Only count positive balances as "Allocated"
        return db.execute("""
            SELECT SUM(balance) FROM envelopes 
            WHERE account_id = ? AND balance > 0 AND status = 'ACTIVE'
        """, (account_id,)).fetchone()[0] or 0.0

    @staticmethod
    def get_total_borrowed(account_id):
        db = BudgetService.get_db()
        # Sum of (amount - repaid_amount) for OPEN loans where source envelope belongs to account_id
        result = db.execute("""
            SELECT SUM(el.amount - el.repaid_amount) 
            FROM envelope_loans el
            JOIN envelopes e ON el.source_envelope_id = e.id
            WHERE el.status = 'OPEN' AND e.account_id = ?
        """, (account_id,)).fetchone()[0]
        return result or 0.0

    @staticmethod
    def add_income(account_id, amount, description="Income", date=None):
        db = BudgetService.get_db()
        transaction_date = date if date else date_cls.today()
        db.execute("UPDATE budget_accounts SET balance = balance + ? WHERE id = ?", (amount, account_id))
        db.execute("""
            INSERT INTO budget_transactions (type, amount, account_id, description, date)
            VALUES ('INCOME', ?, ?, ?, ?)
        """, (amount, account_id, description, transaction_date))
        db.commit()
        
        # Check for open loans to prompt repayment for this account
        open_loans = db.execute("""
            SELECT el.*, e.name as envelope_name 
            FROM envelope_loans el
            JOIN envelopes e ON el.source_envelope_id = e.id
            WHERE el.status = 'OPEN' AND e.account_id = ?
        """, (account_id,)).fetchall()
        return [dict(l) for l in open_loans]

    @staticmethod
    def allocate_money(envelope_id, amount, date=None):
        db = BudgetService.get_db()
        transaction_date = date if date else date_cls.today()
        envelope = db.execute("SELECT account_id FROM envelopes WHERE id = ?", (envelope_id,)).fetchone()
        if not envelope:
            raise ValueError("Envelope not found")
            
        account_id = envelope['account_id']
        free_pool = BudgetService.get_free_pool(account_id)
        
        if free_pool < amount:
            raise ValueError(f"Insufficient free pool. Available: {free_pool}, Requested: {amount}")

        db.execute("UPDATE envelopes SET balance = balance + ? WHERE id = ?", (amount, envelope_id))
        db.execute("""
            INSERT INTO budget_transactions (type, amount, envelope_id, description, date)
            VALUES ('ALLOCATE', ?, ?, 'Allocation', ?)
        """, (amount, envelope_id, transaction_date))
        db.commit()

    @staticmethod
    def spend(account_id, amount, description, envelope_id=None, date=None):
        db = BudgetService.get_db()
        transaction_date = date if date else date_cls.today()
        
        if envelope_id:
            # Spending from Envelope
            envelope = db.execute("SELECT account_id, balance FROM envelopes WHERE id = ?", (envelope_id,)).fetchone()
            if not envelope:
                raise ValueError("Envelope not found")
            
            # Ensure envelope belongs to the account
            if envelope['account_id'] != account_id:
                raise ValueError("Envelope does not belong to the specified account")
                
            # Update Envelope Balance
            db.execute("UPDATE envelopes SET balance = balance - ? WHERE id = ?", (amount, envelope_id))
        else:
            # Spending from Free Pool (Direct Expense)
            free_pool = BudgetService.get_free_pool(account_id)
            if free_pool < amount:
                raise ValueError(f"Insufficient free pool. Available: {free_pool}, Requested: {amount}")
        
        # Update Account Balance (applies to both cases)
        db.execute("UPDATE budget_accounts SET balance = balance - ? WHERE id = ?", (amount, account_id))
        
        # Record Transaction
        db.execute("""
            INSERT INTO budget_transactions (type, amount, account_id, envelope_id, description, date)
            VALUES ('EXPENSE', ?, ?, ?, ?, ?)
        """, (amount, account_id, envelope_id, description, transaction_date))
        
        db.commit()

    @staticmethod
    def transfer_between_accounts(from_account_id, to_account_id, amount, description, date=None, target_envelope_id=None, source_envelope_id=None):
        db = BudgetService.get_db()
        transaction_date = date if date else date_cls.today()
        
        # 1. Validate Source Funds
        source_env_name = None
        if source_envelope_id:
            source_env = db.execute("SELECT name, balance, account_id FROM envelopes WHERE id = ?", (source_envelope_id,)).fetchone()
            if not source_env:
                raise ValueError("Source envelope not found")
            if source_env['account_id'] != from_account_id:
                raise ValueError("Source envelope does not belong to the source account")
            if source_env['balance'] < amount:
                 raise ValueError(f"Insufficient funds in source envelope. Available: {source_env['balance']}, Requested: {amount}")
            source_env_name = source_env['name']
        else:
            free_pool = BudgetService.get_free_pool(from_account_id)
            if free_pool < amount:
                 raise ValueError(f"Insufficient free pool in source account. Available: {free_pool}, Requested: {amount}")

        # 2. Get Account Names for better descriptions
        from_acc = db.execute("SELECT name FROM budget_accounts WHERE id = ?", (from_account_id,)).fetchone()
        to_acc = db.execute("SELECT name FROM budget_accounts WHERE id = ?", (to_account_id,)).fetchone()
        
        from_name = from_acc['name'] if from_acc else "Unknown"
        to_name = to_acc['name'] if to_acc else "Unknown"

        # Check Target Envelope if provided
        target_env_name = None
        if target_envelope_id:
            target_env = db.execute("SELECT name, account_id FROM envelopes WHERE id = ?", (target_envelope_id,)).fetchone()
            if not target_env:
                raise ValueError("Target envelope not found")
            if target_env['account_id'] != to_account_id:
                raise ValueError("Target envelope does not belong to the destination account")
            target_env_name = target_env['name']

        # 3. Update Balances
        db.execute("UPDATE budget_accounts SET balance = balance - ? WHERE id = ?", (amount, from_account_id))
        db.execute("UPDATE budget_accounts SET balance = balance + ? WHERE id = ?", (amount, to_account_id))
        
        if source_envelope_id:
             db.execute("UPDATE envelopes SET balance = balance - ? WHERE id = ?", (amount, source_envelope_id))
             
        if target_envelope_id:
             db.execute("UPDATE envelopes SET balance = balance + ? WHERE id = ?", (amount, target_envelope_id))

        # 4. Record Transactions
        # Source: EXPENSE (Transfer Out)
        
        # Construct Description for Source Transaction
        # "Transfer to [DestAccount]" OR "Transfer to [DestAccount] (Env: [TargetEnv])"
        source_base_desc = f"Transfer to {to_name}"
        if target_env_name:
             source_base_desc += f" (Target: {target_env_name})"
        
        # If source envelope is used, maybe we want to emphasize that?
        # User requested: "Przelew: Paliwo -> Paliwo" style if possible, or clear indication.
        # Let's try to be descriptive.
        if source_envelope_id and target_envelope_id:
             final_source_desc = f"Transfer: {source_env_name} -> {target_env_name} ({to_name})"
        elif source_envelope_id:
             final_source_desc = f"Transfer: {source_env_name} -> {to_name}"
        elif target_envelope_id:
             final_source_desc = f"Transfer to {to_name} (Target: {target_env_name})"
        else:
             final_source_desc = f"Transfer to {to_name}: {description}"

        db.execute("""
            INSERT INTO budget_transactions (type, amount, account_id, envelope_id, description, date)
            VALUES ('EXPENSE', ?, ?, ?, ?, ?)
        """, (amount, from_account_id, source_envelope_id, final_source_desc, transaction_date))
        
        # Dest: INCOME (Transfer In)
        # "Transfer from [SourceAccount]" OR "Transfer from [SourceAccount] (Source: [SourceEnv])"
        dest_base_desc = f"Transfer from {from_name}"
        
        if source_envelope_id and target_envelope_id:
             final_dest_desc = f"Transfer: {source_env_name} ({from_name}) -> {target_env_name}"
        elif source_envelope_id:
             final_dest_desc = f"Transfer from {from_name} (Source: {source_env_name})"
        elif target_envelope_id:
             final_dest_desc = f"Transfer from {from_name} -> {target_env_name}"
        else:
             final_dest_desc = f"Transfer from {from_name}: {description}"
            
        db.execute("""
            INSERT INTO budget_transactions (type, amount, account_id, envelope_id, description, date)
            VALUES ('INCOME', ?, ?, ?, ?, ?)
        """, (amount, to_account_id, target_envelope_id, final_dest_desc, transaction_date))
        
        db.commit()

    @staticmethod
    def transfer_to_investment(budget_account_id, portfolio_id, amount, envelope_id=None, description="Transfer to Investments", date=None):
        """
        Transfers money from Budget (Account/Envelope) to Investment (Portfolio).
        Executes in a SINGLE transaction to ensure atomicity.
        """
        db = BudgetService.get_db()
        transaction_date = date if date else date_cls.today()
        
        # Get names for descriptions
        account = db.execute("SELECT name, balance FROM budget_accounts WHERE id = ?", (budget_account_id,)).fetchone()
        portfolio = db.execute("SELECT name FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        
        if not account:
            raise ValueError("Budget Account not found")
        if not portfolio:
            raise ValueError("Investment Portfolio not found")
            
        account_name = account['name']
        portfolio_name = portfolio['name']

        try:
            # --- STEP A: BUDGET SIDE ---
            
            if envelope_id:
                # Deduct from Envelope
                envelope = db.execute("SELECT balance, account_id, name FROM envelopes WHERE id = ?", (envelope_id,)).fetchone()
                if not envelope:
                    raise ValueError("Envelope not found")
                if envelope['account_id'] != budget_account_id:
                    raise ValueError("Envelope does not belong to the specified account")
                
                # Check envelope balance (Optional strict mode, but good practice)
                # if envelope['balance'] < amount: raise ValueError("Insufficient funds in envelope")

                db.execute("UPDATE envelopes SET balance = balance - ? WHERE id = ?", (amount, envelope_id))
                source_desc = f"Transfer to Investment ({portfolio_name}) from Envelope: {envelope['name']}"
            else:
                # Deduct from Free Pool
                free_pool = BudgetService.get_free_pool(budget_account_id)
                if free_pool < amount:
                    raise ValueError(f"Insufficient free pool. Available: {free_pool}, Requested: {amount}")
                source_desc = f"Transfer to Investment ({portfolio_name}) from Free Pool"

            # Deduct from Account Balance
            if account['balance'] < amount:
                 raise ValueError(f"Insufficient funds in account. Available: {account['balance']}")

            db.execute("UPDATE budget_accounts SET balance = balance - ? WHERE id = ?", (amount, budget_account_id))
            
            # Record Budget Transaction
            db.execute("""
                INSERT INTO budget_transactions (type, amount, account_id, envelope_id, description, date)
                VALUES ('EXPENSE', ?, ?, ?, ?, ?)
            """, (amount, budget_account_id, envelope_id, source_desc, transaction_date))


            # --- STEP B: INVESTMENT SIDE ---
            
            # Update Portfolio Cash
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash + ?, total_deposits = total_deposits + ? WHERE id = ?',
                (amount, amount, portfolio_id)
            )
            
            # Record Portfolio Transaction
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, 'CASH', 'DEPOSIT', 1, amount, amount, transaction_date)
            )

            # Commit everything
            db.commit()
            
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def withdraw_from_investment(portfolio_id, budget_account_id, amount, description="Wypłata z portfela inwestycyjnego", date=None):
        """
        Transfers money from Investment (Portfolio) to Budget (Account).
        Executes in a SINGLE transaction to ensure atomicity.
        """
        db = BudgetService.get_db()
        transaction_date = date if date else date_cls.today()
        
        # Get portfolio and account details
        portfolio = db.execute("SELECT name, current_cash FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
        account = db.execute("SELECT name FROM budget_accounts WHERE id = ?", (budget_account_id,)).fetchone()
        
        if not portfolio:
            raise ValueError("Investment Portfolio not found")
        if not account:
            raise ValueError("Budget Account not found")
            
        portfolio_name = portfolio['name']
        account_name = account['name']
        
        if portfolio['current_cash'] < amount:
            raise ValueError(f"Insufficient funds in portfolio. Available: {portfolio['current_cash']}")

        try:
            # --- STEP A: INVESTMENT SIDE ---
            
            # Deduct from Portfolio Cash
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                (amount, portfolio_id)
            )
            
            # Record Portfolio Transaction (WITHDRAW)
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, 'CASH', 'WITHDRAW', 1, amount, amount, transaction_date)
            )

            # --- STEP B: BUDGET SIDE ---
            
            # Add to Budget Account Balance
            db.execute(
                "UPDATE budget_accounts SET balance = balance + ? WHERE id = ?",
                (amount, budget_account_id)
            )
            
            # Record Budget Transaction (INCOME)
            # envelope_id is NULL, so it goes to Free Pool
            full_description = f"{description} (From: {portfolio_name})"
            db.execute("""
                INSERT INTO budget_transactions (type, amount, account_id, description, date)
                VALUES ('INCOME', ?, ?, ?, ?)
            """, (amount, budget_account_id, full_description, transaction_date))
            
            # Commit everything
            db.commit()
            
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def borrow_from_envelope(source_envelope_id, amount, reason, due_date=None):
        db = BudgetService.get_db()
        
        # Borrowing decreases envelope balance, but does NOT touch account balance.
        # This effectively increases the Free Pool for that account.
        
        db.execute("UPDATE envelopes SET balance = balance - ? WHERE id = ?", (amount, source_envelope_id))
        
        db.execute("""
            INSERT INTO envelope_loans (source_envelope_id, amount, reason, borrow_date, due_date, status)
            VALUES (?, ?, ?, ?, ?, 'OPEN')
        """, (source_envelope_id, amount, reason, date_cls.today(), due_date))
        
        db.execute("""
            INSERT INTO budget_transactions (type, amount, envelope_id, description, date)
            VALUES ('BORROW', ?, ?, ?, ?)
        """, (amount, source_envelope_id, f"Borrowed: {reason}", date_cls.today()))
        db.commit()

    @staticmethod
    def repay_envelope_loan(loan_id, amount):
        db = BudgetService.get_db()
        loan = db.execute("""
            SELECT el.*, e.account_id 
            FROM envelope_loans el
            JOIN envelopes e ON el.source_envelope_id = e.id
            WHERE el.id = ?
        """, (loan_id,)).fetchone()
        
        if not loan:
            raise ValueError("Loan not found")
            
        account_id = loan['account_id']
        free_pool = BudgetService.get_free_pool(account_id)
        
        if free_pool < amount:
            raise ValueError(f"Insufficient free pool to repay. Available: {free_pool}")

        if loan['status'] == 'CLOSED':
            raise ValueError("Loan is already closed")

        new_repaid_total = loan['repaid_amount'] + amount
        if new_repaid_total > loan['amount']:
             raise ValueError(f"Repayment amount exceeds loan balance. Remaining: {loan['amount'] - loan['repaid_amount']}")

        status = 'CLOSED' if new_repaid_total >= loan['amount'] else 'OPEN'

        db.execute("UPDATE envelopes SET balance = balance + ? WHERE id = ?", (amount, loan['source_envelope_id']))
        db.execute("UPDATE envelope_loans SET repaid_amount = ?, status = ? WHERE id = ?", (new_repaid_total, status, loan_id))
        
        db.execute("""
            INSERT INTO budget_transactions (type, amount, envelope_id, description, date)
            VALUES ('REPAY', ?, ?, ?, ?)
        """, (amount, loan['source_envelope_id'], f"Repayment for loan {loan_id}", date_cls.today()))
        db.commit()

    @staticmethod
    def update_envelope_target(envelope_id, new_target):
        db = BudgetService.get_db()
        if new_target < 0:
            raise ValueError("Target amount must be positive")
            
        db.execute("UPDATE envelopes SET target_amount = ? WHERE id = ?", (new_target, envelope_id))
        db.commit()

    @staticmethod
    def close_envelope(envelope_id):
        db = BudgetService.get_db()
        envelope = db.execute("SELECT * FROM envelopes WHERE id = ?", (envelope_id,)).fetchone()
        if not envelope:
            raise ValueError("Envelope not found")
            
        env_type = envelope['type'] or 'MONTHLY'
        balance = envelope['balance']
        
        # Logic:
        # If balance > 0: Return to Free Pool (set to 0, create transaction).
        # If balance <= 0: Just close (keep negative balance for history/reporting).
        
        if balance > 0:
            db.execute("UPDATE envelopes SET balance = 0, status = 'CLOSED' WHERE id = ?", (envelope_id,))
            
            # Log it as a negative ALLOCATE (returning to pool)
            db.execute("""
                INSERT INTO budget_transactions (type, amount, account_id, envelope_id, description, date)
                VALUES ('ALLOCATE', ?, ?, ?, ?, ?)
            """, (-balance, envelope['account_id'], envelope_id, "Closed Envelope (Returned to Pool)", date_cls.today()))
        else:
            # Just mark as CLOSED. Balance remains negative (or zero).
            db.execute("UPDATE envelopes SET status = 'CLOSED' WHERE id = ?", (envelope_id,))
            
        db.commit()

    @staticmethod
    def clone_budget_for_month(account_id, from_month, to_month):
        db = BudgetService.get_db()
        
        # Check if target month already has envelopes? Maybe prevent duplicate cloning.
        existing = db.execute("SELECT count(*) FROM envelopes WHERE account_id = ? AND type = 'MONTHLY' AND target_month = ?", (account_id, to_month)).fetchone()[0]
        if existing > 0:
            raise ValueError(f"Budget for {to_month} already exists.")

        # Get source envelopes
        source_envelopes = db.execute("""
            SELECT * FROM envelopes 
            WHERE account_id = ? AND type = 'MONTHLY' AND target_month = ? AND status != 'CLOSED'
        """, (account_id, from_month)).fetchall()
        
        for env in source_envelopes:
            db.execute("""
                INSERT INTO envelopes (category_id, account_id, name, icon, target_amount, type, target_month, status, balance)
                VALUES (?, ?, ?, ?, ?, 'MONTHLY', ?, 'ACTIVE', 0)
            """, (env['category_id'], env['account_id'], env['name'], env['icon'], env['target_amount'], to_month))
            
        db.commit()

    @staticmethod
    def get_summary(account_id=None, target_month=None):
        db = BudgetService.get_db()
        
        # Determine target month (YYYY-MM)
        if not target_month:
            today = date_cls.today()
            target_month = f"{today.year}-{today.month:02d}"
        
        accounts = db.execute("SELECT * FROM budget_accounts").fetchall()
        
        # Calculate free_pool for ALL accounts
        accounts_data = []
        for acc in accounts:
            acc_dict = dict(acc)
            acc_dict['free_pool'] = BudgetService.get_free_pool(acc['id'])
            accounts_data.append(acc_dict)
        
        # If no account_id provided, default to the first account if exists
        if account_id is None and accounts:
            account_id = accounts[0]['id']
            
        if not account_id:
             return {
                "account_balance": 0.0,
                "free_pool": 0.0,
                "total_allocated": 0.0,
                "total_borrowed": 0.0,
                "envelopes": [],
                "loans": [],
                "accounts": accounts_data,
                "flow_analysis": {"income": 0.0, "investment_transfers": 0.0, "savings_rate": 0.0}
            }

        # Calculate for specific account_id
        account_row = db.execute("SELECT balance FROM budget_accounts WHERE id = ?", (account_id,)).fetchone()
        total_account_balance = account_row['balance'] if account_row else 0.0
        
        free_pool = BudgetService.get_free_pool(account_id)
        total_allocated = BudgetService.get_total_allocated(account_id)
        total_borrowed = BudgetService.get_total_borrowed(account_id)
        
        # Envelopes Query: Fetch BOTH Active and Closed for the target month
        # We need Closed ones to show in "Rozliczone" section
        envelopes_rows = db.execute("""
            SELECT e.id, e.name, e.balance, e.target_amount, e.type, e.target_month, e.status, c.name as category_name, c.icon as category_icon, e.icon, e.account_id, e.category_id
            FROM envelopes e
            JOIN envelope_categories c ON e.category_id = c.id
            WHERE e.account_id = ?
            AND (
                (e.type = 'MONTHLY' AND e.target_month = ?) OR
                (e.type = 'LONG_TERM') -- For Long Term, we might want to see Closed ones too? Or just Active?
                OR (e.type IS NULL)
            )
        """, (account_id, target_month)).fetchall()
        
        # Filter Long Term: If Closed, maybe don't show unless explicitly asked?
        # User only mentioned "Closing Logic... display these as 'ROZLICZONE' in a separate... history section."
        # This likely applies to Monthly envelopes primarily.
        # But let's fetch all and let frontend filter/group.
        
        loans_rows = db.execute("""
            SELECT el.id, e.name as source_envelope, el.source_envelope_id, el.amount, (el.amount - el.repaid_amount) as remaining, el.due_date, el.reason
            FROM envelope_loans el
            JOIN envelopes e ON el.source_envelope_id = e.id
            WHERE el.status = 'OPEN' AND e.account_id = ?
        """, (account_id,)).fetchall()

        # Process Envelopes to include loan info and calculate total_spent
        envelopes = []
        
        # Get expenses for all envelopes in this month to avoid N+1 queries
        try:
            year_str, month_str = target_month.split('-')
        except ValueError:
            today = date_cls.today()
            year_str = str(today.year)
            month_str = f"{today.month:02d}"

        expenses_rows = db.execute("""
            SELECT envelope_id, SUM(amount) as spent
            FROM budget_transactions
            WHERE type = 'EXPENSE' 
            AND envelope_id IS NOT NULL
            AND strftime('%Y', date) = ? AND strftime('%m', date) = ?
            GROUP BY envelope_id
        """, (year_str, month_str)).fetchall()
        
        spent_map = {row['envelope_id']: row['spent'] for row in expenses_rows}

        for env in envelopes_rows:
            env_dict = dict(env)
            # Calculate outstanding loans for this envelope
            outstanding_loans = sum(l['remaining'] for l in loans_rows if l['source_envelope_id'] == env['id'])
            env_dict['outstanding_loans'] = outstanding_loans
            
            # Add total_spent
            env_dict['total_spent'] = spent_map.get(env['id'], 0.0)
            
            envelopes.append(env_dict)

        # Flow Analysis (Target Month)
        try:
            year_str, month_str = target_month.split('-')
        except ValueError:
            # Fallback if format is wrong
            today = date_cls.today()
            year_str = str(today.year)
            month_str = f"{today.month:02d}"
        
        total_income = db.execute("""
            SELECT SUM(amount) FROM budget_transactions 
            WHERE type = 'INCOME' AND account_id = ? 
            AND strftime('%Y', date) = ? AND strftime('%m', date) = ?
        """, (account_id, year_str, month_str)).fetchone()[0] or 0.0

        total_investment_transfers = db.execute("""
            SELECT SUM(amount) FROM budget_transactions 
            WHERE type = 'EXPENSE' AND account_id = ? 
            AND description LIKE 'Transfer to Investment%'
            AND strftime('%Y', date) = ? AND strftime('%m', date) = ?
        """, (account_id, year_str, month_str)).fetchone()[0] or 0.0
        
        # Savings Rate: (Investment Transfers + Remaining Free Pool) / Income
        # Note: Remaining Free Pool is a snapshot, not a flow. 
        # The prompt says: "Savings Rate" widget that calculates: (Transfers to Investment + Remaining Free Pool) / Monthly Income.
        # This is a bit hybrid (Flow + Stock), but I will follow the formula.
        
        numerator = total_investment_transfers + free_pool
        savings_rate = (numerator / total_income * 100) if total_income > 0 else 0.0

        flow_analysis = {
            "income": total_income,
            "investment_transfers": total_investment_transfers,
            "savings_rate": savings_rate
        }

        return {
            "account_balance": total_account_balance,
            "free_pool": free_pool,
            "total_allocated": total_allocated,
            "total_borrowed": total_borrowed,
            "envelopes": envelopes,
            "loans": [dict(l) for l in loans_rows],
            "accounts": accounts_data,
            "flow_analysis": flow_analysis
        }

    @staticmethod
    def get_transactions(account_id, envelope_id=None, category_id=None):
        db = BudgetService.get_db()
        
        query = """
            SELECT t.id, t.type, t.amount, t.description, t.date, 
                   e.name as envelope_name, e.icon as envelope_icon,
                   c.name as category_name, c.icon as category_icon
            FROM budget_transactions t
            LEFT JOIN envelopes e ON t.envelope_id = e.id
            LEFT JOIN envelope_categories c ON e.category_id = c.id
            WHERE t.account_id = ? OR e.account_id = ?
        """
        params = [account_id, account_id]
        
        if envelope_id:
            query += " AND t.envelope_id = ?"
            params.append(envelope_id)
            
        if category_id:
            query += " AND e.category_id = ?"
            params.append(category_id)
            
        query += " ORDER BY t.date DESC, t.id DESC"
        
        transactions = db.execute(query, params).fetchall()
        return [dict(t) for t in transactions]

    @staticmethod
    def get_analytics(account_id, year, month):
        db = BudgetService.get_db()
        
        year_str = str(year)
        month_str = f"{month:02d}"
        
        # 1. Total Expenses
        total_expenses = db.execute("""
            SELECT SUM(amount) 
            FROM budget_transactions 
            WHERE type = 'EXPENSE' 
              AND account_id = ? 
              AND strftime('%Y', date) = ? 
              AND strftime('%m', date) = ?
        """, (account_id, year_str, month_str)).fetchone()[0] or 0.0

        # 2. By Category
        # Join transactions -> envelopes -> categories
        # Expenses from Free Pool have envelope_id = NULL
        by_category_rows = db.execute("""
            SELECT c.name, SUM(t.amount) as value
            FROM budget_transactions t
            LEFT JOIN envelopes e ON t.envelope_id = e.id
            LEFT JOIN envelope_categories c ON e.category_id = c.id
            WHERE t.type = 'EXPENSE' 
              AND t.account_id = ?
              AND strftime('%Y', t.date) = ? 
              AND strftime('%m', t.date) = ?
            GROUP BY c.name
        """, (account_id, year_str, month_str)).fetchall()
        
        # 3. By Envelope
        by_envelope_rows = db.execute("""
            SELECT e.name, SUM(t.amount) as value
            FROM budget_transactions t
            JOIN envelopes e ON t.envelope_id = e.id
            WHERE t.type = 'EXPENSE' 
              AND t.account_id = ?
              AND strftime('%Y', t.date) = ? 
              AND strftime('%m', t.date) = ?
            GROUP BY e.name
        """, (account_id, year_str, month_str)).fetchall()

        # Helper to generate colors
        colors = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884d8", "#82ca9d", "#ffc658", "#8dd1e1"]
        
        by_category = []
        for i, row in enumerate(by_category_rows):
            name = row['name'] if row['name'] else "Wolne Środki" 
            by_category.append({
                "name": name, 
                "value": row['value'], 
                "fill": colors[i % len(colors)]
            })

        by_envelope = [{"name": row['name'], "value": row['value']} for row in by_envelope_rows]

        return {
            "total_expenses": total_expenses,
            "by_category": by_category,
            "by_envelope": by_envelope
        }
