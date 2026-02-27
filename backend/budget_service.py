import sqlite3
from flask import g
from datetime import date
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
        
        total_envelopes = db.execute("SELECT SUM(balance) FROM envelopes WHERE account_id = ?", (account_id,)).fetchone()[0] or 0.0
        return float(account['balance']) - float(total_envelopes)

    @staticmethod
    def get_total_allocated(account_id):
        db = BudgetService.get_db()
        return db.execute("SELECT SUM(balance) FROM envelopes WHERE account_id = ?", (account_id,)).fetchone()[0] or 0.0

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
        transaction_date = date if date else date.today()
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
        transaction_date = date if date else date.today()
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
        transaction_date = date if date else date.today()
        
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
    def transfer_between_accounts(from_account_id, to_account_id, amount, description, date=None):
        db = BudgetService.get_db()
        transaction_date = date if date else date.today()
        
        # 1. Validate Source Free Pool
        free_pool = BudgetService.get_free_pool(from_account_id)
        if free_pool < amount:
             raise ValueError(f"Insufficient free pool in source account. Available: {free_pool}, Requested: {amount}")

        # 2. Get Account Names for better descriptions (optional, but nice)
        from_acc = db.execute("SELECT name FROM budget_accounts WHERE id = ?", (from_account_id,)).fetchone()
        to_acc = db.execute("SELECT name FROM budget_accounts WHERE id = ?", (to_account_id,)).fetchone()
        
        from_name = from_acc['name'] if from_acc else "Unknown"
        to_name = to_acc['name'] if to_acc else "Unknown"

        # 3. Update Balances
        db.execute("UPDATE budget_accounts SET balance = balance - ? WHERE id = ?", (amount, from_account_id))
        db.execute("UPDATE budget_accounts SET balance = balance + ? WHERE id = ?", (amount, to_account_id))
        
        # 4. Record Transactions
        # Source: EXPENSE (Transfer Out)
        db.execute("""
            INSERT INTO budget_transactions (type, amount, account_id, description, date)
            VALUES ('EXPENSE', ?, ?, ?, ?)
        """, (amount, from_account_id, f"Transfer to {to_name}: {description}", transaction_date))
        
        # Dest: INCOME (Transfer In)
        db.execute("""
            INSERT INTO budget_transactions (type, amount, account_id, description, date)
            VALUES ('INCOME', ?, ?, ?, ?)
        """, (amount, to_account_id, f"Transfer from {from_name}: {description}", transaction_date))
        
        db.commit()

    @staticmethod
    def transfer_to_investment(budget_account_id, portfolio_id, amount, envelope_id=None, description="Transfer to Investments", date=None):
        """
        Transfers money from Budget (Account/Envelope) to Investment (Portfolio).
        Executes in a SINGLE transaction to ensure atomicity.
        """
        db = BudgetService.get_db()
        transaction_date = date if date else date.today()
        
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
        transaction_date = date if date else date.today()
        
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
        """, (source_envelope_id, amount, reason, date.today(), due_date))
        
        db.execute("""
            INSERT INTO budget_transactions (type, amount, envelope_id, description, date)
            VALUES ('BORROW', ?, ?, ?, ?)
        """, (amount, source_envelope_id, f"Borrowed: {reason}", date.today()))
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
        """, (amount, loan['source_envelope_id'], f"Repayment for loan {loan_id}", date.today()))
        db.commit()

    @staticmethod
    def get_summary(account_id=None):
        db = BudgetService.get_db()
        
        accounts = db.execute("SELECT * FROM budget_accounts").fetchall()
        
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
                "accounts": [dict(a) for a in accounts]
            }

        # Calculate for specific account_id
        account_row = db.execute("SELECT balance FROM budget_accounts WHERE id = ?", (account_id,)).fetchone()
        total_account_balance = account_row['balance'] if account_row else 0.0
        
        free_pool = BudgetService.get_free_pool(account_id)
        total_allocated = BudgetService.get_total_allocated(account_id)
        total_borrowed = BudgetService.get_total_borrowed(account_id)
        
        envelopes = db.execute("""
            SELECT e.id, e.name, e.balance, e.target_amount, c.name as category_name, c.icon as category_icon, e.icon, e.account_id, e.category_id
            FROM envelopes e
            JOIN envelope_categories c ON e.category_id = c.id
            WHERE e.account_id = ?
        """, (account_id,)).fetchall()
        
        loans = db.execute("""
            SELECT el.id, e.name as source_envelope, el.amount, (el.amount - el.repaid_amount) as remaining, el.due_date, el.reason
            FROM envelope_loans el
            JOIN envelopes e ON el.source_envelope_id = e.id
            WHERE el.status = 'OPEN' AND e.account_id = ?
        """, (account_id,)).fetchall()

        return {
            "account_balance": total_account_balance,
            "free_pool": free_pool,
            "total_allocated": total_allocated,
            "total_borrowed": total_borrowed,
            "envelopes": [dict(e) for e in envelopes],
            "loans": [dict(l) for l in loans],
            "accounts": [dict(a) for a in accounts]
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
