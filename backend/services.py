import yfinance as yf
import pandas as pd
from database import get_db
import sqlite3
from datetime import datetime, timedelta, date
import time
import random
import logging

class PriceService:
    _price_cache = {}

    @classmethod
    def _download_with_retry(cls, *args, **kwargs):
        """Download wrapper with simple retry + exponential backoff."""
        attempts = 3
        delay = 1
        for attempt in range(1, attempts + 1):
            try:
                return yf.download(*args, **kwargs)
            except Exception as e:
                logging.warning(f"yfinance download failed (attempt {attempt}/{attempts}): {e}")
                if attempt == attempts:
                    logging.error("yfinance download failed after retries")
                    raise
                sleep_time = delay + random.uniform(0, 0.5)
                time.sleep(sleep_time)
                delay *= 2

    @classmethod
    def get_prices(cls, tickers):
        if not tickers:
            return {}
        
        # Identify missing tickers in cache
        missing_tickers = [t for t in tickers if t not in cls._price_cache]
        
        if missing_tickers:
            print(f"Fetching prices for: {missing_tickers}")
            try:
                # Fetch 5 days of data to handle weekends/holidays/gaps (with retry)
                data = cls._download_with_retry(missing_tickers, period="5d", group_by='ticker', threads=False)

                if data.empty:
                    for ticker in missing_tickers:
                        print(f"[WARNING] No valid data for {ticker} (Empty DataFrame)")
                else:
                    for ticker in missing_tickers:
                        try:
                            # yfinance with group_by='ticker' returns MultiIndex: (Ticker, Attribute)
                            # We access the ticker's sub-dataframe directly
                            ticker_df = None

                            if isinstance(data.columns, pd.MultiIndex):
                                if ticker in data.columns.levels[0]:
                                    ticker_df = data[ticker]
                            elif 'Close' in data.columns and len(missing_tickers) == 1:
                                # Fallback if yfinance returns flattened columns for single ticker
                                ticker_df = data

                            if ticker_df is not None and 'Close' in ticker_df.columns:
                                df_cleaned = ticker_df.dropna(subset=['Close'])
                                if not df_cleaned.empty:
                                    price = df_cleaned['Close'].iloc[-1]
                                    if hasattr(price, 'item'):
                                        price = price.item()
                                    cls._price_cache[ticker] = round(float(price), 2)
                                else:
                                    print(f"[WARNING] No valid data for {ticker} (All values NaN)")
                            else:
                                print(f"[WARNING] No valid data for {ticker} (Missing 'Close' column or Ticker not found)")

                        except Exception as e:
                            print(f"[ERROR] Failed to process {ticker}: {e}")
            except Exception as e:
                print(f"[CRITICAL] yfinance fetch failed: {e}")
            
            # Final Safety Step: Mark any missing tickers as None
            for ticker in missing_tickers:
                if ticker not in cls._price_cache:
                    cls._price_cache[ticker] = None

        return cls._price_cache

    @classmethod
    def warmup_cache(cls):
        db = get_db()
        try:
            holdings = db.execute('SELECT DISTINCT ticker FROM holdings').fetchall()
            tickers = [h['ticker'] for h in holdings]
            if tickers:
                print(f"Warming up price cache for: {tickers}")
                cls.get_prices(tickers)
        except Exception as e:
            print(f"Cache warmup failed: {e}")

    @classmethod
    def sync_stock_history(cls, ticker, required_start_date=None):
        """
        Incremental sync of stock prices from yfinance to local DB.
        """
        db = get_db()
        
        # 1. Find the latest date available in DB
        result = db.execute(
            'SELECT MAX(date) as max_date FROM stock_prices WHERE ticker = ?',
            (ticker,)
        ).fetchone()
        
        max_date_str = result['max_date']
        max_date = None
        if max_date_str:
            if isinstance(max_date_str, str):
                max_date = datetime.strptime(max_date_str, '%Y-%m-%d').date()
            else:
                max_date = max_date_str # Handle if sqlite returns date object

        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # 2. Determine fetch start date
        fetch_start = None
        
        if not max_date:
            # If no data, use required_start_date or default to 1 year ago
            if required_start_date:
                if isinstance(required_start_date, str):
                    fetch_start = datetime.strptime(required_start_date, '%Y-%m-%d').date()
                else:
                    fetch_start = required_start_date
            else:
                fetch_start = today - timedelta(days=365)
        elif max_date < yesterday:
            # If data exists but is old, start from the day after max_date
            fetch_start = max_date + timedelta(days=1)
        else:
            # Already up to date
            print(f"History for {ticker} is already up to date (last: {max_date})")
            return max_date_str

        if fetch_start >= today:
             return max_date_str

        print(f"Syncing {ticker} history starting from {fetch_start}...")

        try:
            # 3. Fetch from yfinance (with retry)
            # Use fetch_start to today
            data = cls._download_with_retry(ticker, start=fetch_start, interval="1d", threads=False)

            if not data.empty:
                # 4. Save to DB
                cursor = db.cursor()
                for timestamp, row in data.iterrows():
                    price_date = timestamp.date()
                    # Check if 'Close' exists (handle MultiIndex if necessary)
                    price = None
                    if 'Close' in data.columns:
                        price = row['Close']
                        if hasattr(price, 'item'):
                            price = price.item()

                    if price is not None and not pd.isna(price):
                        cursor.execute(
                            '''INSERT OR IGNORE INTO stock_prices (ticker, date, close_price)
                               VALUES (?, ?, ?)''',
                            (ticker, price_date.isoformat(), round(float(price), 2))
                        )
                db.commit()
                print(f"Successfully synced {ticker} history.")
            else:
                print(f"No history data found for {ticker} from {fetch_start}")

        except Exception as e:
            print(f"Error syncing history for {ticker}: {e}")
            db.rollback()

        # Return latest date in DB
        new_max = db.execute(
            'SELECT MAX(date) as max_date FROM stock_prices WHERE ticker = ?',
            (ticker,)
        ).fetchone()
        return new_max['max_date']

class FinancialService:
    @staticmethod
    def calculate_metrics(holdings, total_value, cash_value):
        """
        Oblicza wagi i dywersyfikację portfela.
        """
        if total_value == 0:
            return []
            
        enriched = []
        # Add cash as a component of diversification
        cash_weight = (cash_value / total_value) * 100
        
        for h in holdings:
            # We assume holdings already have 'current_value' from get_holdings enrichment
            weight = (h.get('current_value', 0) / total_value) * 100
            h['weight_percent'] = round(weight, 2)
            enriched.append(h)
            
        return enriched

class BondService:
    @staticmethod
    def add_bond(portfolio_id, name, principal, interest_rate, purchase_date):
        db = get_db()
        try:
            db.execute(
                '''INSERT INTO bonds (portfolio_id, name, principal, interest_rate, purchase_date)
                   VALUES (?, ?, ?, ?, ?)''',
                (portfolio_id, name, principal, interest_rate, purchase_date)
            )
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def get_bonds(portfolio_id):
        db = get_db()
        bonds = db.execute('SELECT * FROM bonds WHERE portfolio_id = ?', (portfolio_id,)).fetchall()
        
        results = []
        today = date.today()
        
        for b in bonds:
            b_dict = {key: b[key] for key in b.keys()}
            p_date = datetime.strptime(b_dict['purchase_date'], '%Y-%m-%d').date()
            days_passed = (today - p_date).days
            if days_passed < 0: days_passed = 0
            
            # accrued_interest = principal * (interest_rate / 100) * (days_passed / 365)
            accrued = float(b_dict['principal']) * (float(b_dict['interest_rate']) / 100) * (days_passed / 365.0)
            b_dict['accrued_interest'] = round(accrued, 2)
            b_dict['total_value'] = round(float(b_dict['principal']) + accrued, 2)
            results.append(b_dict)
            
        return results

class PortfolioService:
    @staticmethod
    def create_portfolio(name, initial_cash=0.0, account_type='STANDARD', created_at=None):
        db = get_db()
        cursor = db.cursor()
        try:
            # If no created_at is provided, default to today
            if not created_at:
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Ensure created_at has a time component for TIMESTAMP column compatibility
            if ' ' not in created_at:
                created_at = f"{created_at} 00:00:00"
            
            # For interest tracking, extract only the date part if it's a full timestamp
            interest_date = created_at.split(' ')[0] if ' ' in created_at else created_at
            
            cursor.execute(
                '''INSERT INTO portfolios (name, current_cash, total_deposits, account_type, last_interest_date, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (name, initial_cash, initial_cash, account_type, interest_date, created_at)
            )
            portfolio_id = cursor.lastrowid
            
            if initial_cash > 0:
                cursor.execute(
                    '''INSERT INTO transactions 
                       (portfolio_id, ticker, type, quantity, price, total_value, date) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (portfolio_id, 'CASH', 'DEPOSIT', 1, initial_cash, initial_cash, created_at)
                )
            
            db.commit()
            return portfolio_id
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def get_portfolio(portfolio_id):
        db = get_db()
        portfolio = db.execute('SELECT * FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if portfolio:
            p = {key: portfolio[key] for key in portfolio.keys()}
            if p.get('last_interest_date'):
                p['last_interest_date'] = str(p['last_interest_date'])
            if p.get('created_at'):
                p['created_at'] = str(p['created_at'])
            return p
        return None

    @staticmethod
    def list_portfolios():
        db = get_db()
        try:
            # Explicitly selecting columns can be safer, but SELECT * is requested to be checked.
            # We will use SELECT * and handle the mapping carefully.
            portfolios = db.execute('SELECT * FROM portfolios').fetchall()
            results = []
            for row in portfolios:
                try:
                    p = {key: row[key] for key in row.keys()}
                    # Safe conversion of date/datetime objects to string
                    if p.get('last_interest_date'):
                        p['last_interest_date'] = str(p['last_interest_date'])
                    if p.get('created_at'):
                        p['created_at'] = str(p['created_at'])
                    results.append(p)
                except Exception as e:
                    print(f"MAPPING ERROR for row {row['id']}: {e}")
                    # Continue or re-raise? User asked to print. We'll continue to try to return valid ones.
            return results
        except Exception as e:
            print(f"DB FETCH ERROR: {e}")
            raise e

    @staticmethod
    def _capitalize_savings(db, portfolio_id):
        """
        Calculates and records interest for SAVINGS account.
        """
        portfolio = db.execute('SELECT * FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio or portfolio['account_type'] != 'SAVINGS':
            return
            
        last_date_str = portfolio['last_interest_date']
        if not last_date_str:
            return
            
        last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
        today = date.today()
        days_passed = (today - last_date).days
        
        if days_passed > 0:
            rate = float(portfolio['savings_rate'])
            cash = float(portfolio['current_cash'])
            interest = cash * (rate / 100) * (days_passed / 365.0)
            
            if interest > 0.01:
                # Add interest to cash
                db.execute(
                    'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                    (interest, portfolio_id)
                )
                # Log transaction
                db.execute(
                    '''INSERT INTO transactions 
                       (portfolio_id, ticker, type, quantity, price, total_value, date) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (portfolio_id, 'CASH', 'INTEREST', 1, interest, interest, today.isoformat())
                )
        
        # Update last interest date anyway to reset the clock
        db.execute(
            'UPDATE portfolios SET last_interest_date = ? WHERE id = ?',
            (today.isoformat(), portfolio_id)
        )

    @staticmethod
    def deposit_cash(portfolio_id, amount, date_str=None):
        db = get_db()
        try:
            # Capitalize first if SAVINGS
            PortfolioService._capitalize_savings(db, portfolio_id)
            
            # Default to today if no date provided
            if not date_str:
                date_str = date.today().isoformat()
            
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash + ?, total_deposits = total_deposits + ? WHERE id = ?',
                (amount, amount, portfolio_id)
            )
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, 'CASH', 'DEPOSIT', 1, amount, amount, date_str)
            )
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def withdraw_cash(portfolio_id, amount, date_str=None):
        db = get_db()
        portfolio = db.execute('SELECT current_cash, account_type FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        
        # Note: If SAVINGS, we need to calculate live interest before checking balance
        live_interest = 0
        if portfolio and portfolio['account_type'] == 'SAVINGS':
            # Temporary calculation for check
            last_date = datetime.strptime(portfolio['last_interest_date'], '%Y-%m-%d').date()
            days = (date.today() - last_date).days
            if days > 0:
                live_interest = float(portfolio['current_cash']) * (float(portfolio['savings_rate']) / 100) * (days / 365.0)

        if not portfolio or (portfolio['current_cash'] + live_interest) < amount:
            raise ValueError("Insufficient funds")

        try:
            # Capitalize first
            PortfolioService._capitalize_savings(db, portfolio_id)
            
            # Default to today if no date provided
            if not date_str:
                date_str = date.today().isoformat()
            
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                (amount, portfolio_id)
            )
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, 'CASH', 'WITHDRAW', 1, amount, amount, date_str)
            )
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def update_savings_rate(portfolio_id, new_rate):
        db = get_db()
        try:
            # Capitalize before rate change
            PortfolioService._capitalize_savings(db, portfolio_id)
            db.execute(
                'UPDATE portfolios SET savings_rate = ? WHERE id = ?',
                (new_rate, portfolio_id)
            )
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def buy_stock(portfolio_id, ticker, quantity, price, purchase_date=None):
        db = get_db()
        total_cost = quantity * price
        
        # Default to today if no date provided
        if not purchase_date:
            purchase_date = date.today().isoformat()
            
        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio or portfolio['current_cash'] < total_cost:
            raise ValueError("Insufficient funds")

        try:
            # Trigger history sync from the purchase date
            PriceService.sync_stock_history(ticker, purchase_date)

            # Update cash
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                (total_cost, portfolio_id)
            )

            # Record transaction
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, ticker, 'BUY', quantity, price, total_cost, purchase_date)
            )

            # Update holdings
            holding = db.execute(
                'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?',
                (portfolio_id, ticker)
            ).fetchone()

            if holding:
                new_quantity = holding['quantity'] + quantity
                new_total_cost = holding['total_cost'] + total_cost
                new_avg_price = new_total_cost / new_quantity
                
                db.execute(
                    '''UPDATE holdings 
                       SET quantity = ?, total_cost = ?, average_buy_price = ? 
                       WHERE id = ?''',
                    (new_quantity, new_total_cost, new_avg_price, holding['id'])
                )
            else:
                db.execute(
                    '''INSERT INTO holdings 
                       (portfolio_id, ticker, quantity, average_buy_price, total_cost) 
                       VALUES (?, ?, ?, ?, ?)''',
                    (portfolio_id, ticker, quantity, price, total_cost)
                )

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def sell_stock(portfolio_id, ticker, quantity, price):
        db = get_db()
        holding = db.execute(
            'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?',
            (portfolio_id, ticker)
        ).fetchone()

        if not holding or holding['quantity'] < quantity:
            raise ValueError("Insufficient shares")

        total_value = quantity * price
        cost_basis = quantity * holding['average_buy_price']
        realized_profit = (price - holding['average_buy_price']) * quantity

        try:
            # Update cash
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                (total_value, portfolio_id)
            )

            # Record transaction with realized_profit
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, realized_profit) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, ticker, 'SELL', quantity, price, total_value, realized_profit)
            )

            # Update holdings
            new_quantity = holding['quantity'] - quantity
            if new_quantity > 0:
                new_total_cost = holding['total_cost'] - cost_basis
                db.execute(
                    '''UPDATE holdings 
                       SET quantity = ?, total_cost = ?
                       WHERE id = ?''',
                    (new_quantity, new_total_cost, holding['id'])
                )
            else:
                db.execute('DELETE FROM holdings WHERE id = ?', (holding['id'],))

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def get_holdings(portfolio_id):
        db = get_db()
        holdings = db.execute('SELECT * FROM holdings WHERE portfolio_id = ?', (portfolio_id,)).fetchall()
        
        # Enrich with current prices
        results = []
        if not holdings:
            return results
            
        tickers = [h['ticker'] for h in holdings]
        current_prices = PriceService.get_prices(tickers)
        
        holdings_value = 0.0
        for h in holdings:
            h_dict = {key: h[key] for key in h.keys()}
            price = current_prices.get(h_dict['ticker'])
            
            if price is None:
                price = h_dict['average_buy_price']
            
            h_dict['current_price'] = price
            h_dict['current_value'] = h_dict['quantity'] * price
            h_dict['profit_loss'] = h_dict['current_value'] - h_dict['total_cost']
            h_dict['profit_loss_percent'] = (h_dict['profit_loss'] / h_dict['total_cost'] * 100) if h_dict['total_cost'] != 0 else 0.0
            holdings_value += h_dict['current_value']
            results.append(h_dict)
        
        # Calculate weights using total value (including cash if we had it here, but we'll use total holdings value for now or fetch portfolio cash)
        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        cash = portfolio['current_cash'] if portfolio else 0
        total_portfolio_value = holdings_value + cash
        
        return FinancialService.calculate_metrics(results, total_portfolio_value, cash)

    @staticmethod
    def get_transactions(portfolio_id):
        db = get_db()
        transactions = db.execute(
            'SELECT * FROM transactions WHERE portfolio_id = ? ORDER BY date DESC', 
            (portfolio_id,)
        ).fetchall()
        return [{key: t[key] for key in t.keys()} for t in transactions]

    @staticmethod
    def get_all_transactions():
        db = get_db()
        transactions = db.execute(
            '''SELECT t.*, p.name as portfolio_name 
               FROM transactions t 
               JOIN portfolios p ON t.portfolio_id = p.id 
               ORDER BY t.date DESC'''
        ).fetchall()
        return [{key: t[key] for key in t.keys()} for t in transactions]

    @staticmethod
    def record_dividend(portfolio_id, ticker, amount, date):
        db = get_db()
        try:
            # 1. Add dividend record
            db.execute(
                '''INSERT INTO dividends (portfolio_id, ticker, amount, date)
                   VALUES (?, ?, ?, ?)''',
                (portfolio_id, ticker, amount, date)
            )
            
            # 2. Increase cash balance of the portfolio
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                (amount, portfolio_id)
            )
            
            # 3. Log as a special transaction for history visibility
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, ticker, 'DIVIDEND', 1, amount, amount, date)
            )
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def get_dividends(portfolio_id):
        db = get_db()
        dividends = db.execute(
            'SELECT * FROM dividends WHERE portfolio_id = ? ORDER BY date DESC',
            (portfolio_id,)
        ).fetchall()
        return [{key: d[key] for key in d.keys()} for d in dividends]

    @staticmethod
    def get_monthly_dividends(portfolio_id):
        db = get_db()
        # Query to group by month and year
        # SQLite strftime('%Y-%m', date) returns "YYYY-MM"
        query = '''
            SELECT 
                strftime('%Y-%m', date) as month_key,
                SUM(amount) as total_amount
            FROM dividends
            WHERE portfolio_id = ?
            GROUP BY month_key
            ORDER BY month_key ASC
        '''
        results = db.execute(query, (portfolio_id,)).fetchall()
        
        if not results:
            return []

        # Convert to list of dicts and format labels
        formatted_results = []
        for r in results:
            month_date = datetime.strptime(r['month_key'], '%Y-%m')
            formatted_results.append({
                'label': month_date.strftime('%b %Y'), # e.g., "Jan 2024"
                'amount': float(r['total_amount']),
                'key': r['month_key']
            })
            
        return formatted_results

    @staticmethod
    def add_manual_interest(portfolio_id, amount, date_str):
        db = get_db()
        try:
            PortfolioService._capitalize_savings(db, portfolio_id)
            
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                (amount, portfolio_id)
            )
            
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, 'CASH', 'INTEREST', 1, amount, amount, date_str)
            )
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def get_portfolio_history(portfolio_id):
        """
        Reconstructs portfolio value over time based on transactions.
        Groups by month.
        """
        db = get_db()
        transactions = db.execute(
            'SELECT * FROM transactions WHERE portfolio_id = ? ORDER BY date ASC',
            (portfolio_id,)
        ).fetchall()
        
        if not transactions:
            return []
            
        portfolio = db.execute('SELECT account_type, created_at FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        account_type = portfolio['account_type']
        
        first_trans_date = transactions[0]['date']
        if isinstance(first_trans_date, str):
            start_date = datetime.strptime(first_trans_date.split(' ')[0], '%Y-%m-%d').date()
        else:
            start_date = first_trans_date
        
        today = date.today()
        
        # Generate month-end dates
        month_ends = []
        curr_y, curr_m = start_date.year, start_date.month
        while date(curr_y, curr_m, 1) <= today:
            if curr_m == 12:
                next_m, next_y = 1, curr_y + 1
            else:
                next_m, next_y = curr_m + 1, curr_y
                
            month_end = date(next_y, next_m, 1) - timedelta(days=1)
            if month_end > today:
                month_end = today
            month_ends.append(month_end)
            
            if month_end == today:
                break
            curr_m, curr_y = next_m, next_y
        
        # Get unique tickers and SYNC their history first!
        tickers = {t['ticker'] for t in transactions if t['ticker'] not in ['CASH', '']}
        
        if account_type not in ['SAVINGS', 'BONDS']:
            for ticker in tickers:
                try:
                    # Force sync so we have the prices!
                    PriceService.sync_stock_history(ticker, start_date)
                except Exception as e:
                    print(f"Failed to sync history for {ticker}: {e}")

        # Load prices into memory
        price_history = {}
        if account_type not in ['SAVINGS', 'BONDS']:
            for ticker in tickers:
                rows = db.execute(
                    'SELECT date, close_price FROM stock_prices WHERE ticker = ? ORDER BY date ASC',
                    (ticker,)
                ).fetchall()
                # Store dates as pure YYYY-MM-DD strings
                price_history[ticker] = {str(row['date']).split(' ')[0].split('T')[0]: row['close_price'] for row in rows}

        def get_price_at_date(ticker, target_date):
            if ticker not in price_history or not price_history[ticker]:
                return 0
            
            target_str = target_date.strftime('%Y-%m-%d')
            if target_str in price_history[ticker]:
                return price_history[ticker][target_str]
            
            # Find closest available price BEFORE the target date
            past_dates = [d for d in price_history[ticker].keys() if d <= target_str]
            if past_dates:
                return price_history[ticker][max(past_dates)]
            return 0

        monthly_data = {}
        # Calculate values per month
        for end_date in month_ends:
            current_cash = 0.0
            holdings_qty = {}
            
            for t in transactions:
                t_date_str = str(t['date']).split(' ')[0].split('T')[0]
                t_date = datetime.strptime(t_date_str, '%Y-%m-%d').date()
                
                if t_date > end_date:
                    continue
                
                t_val = float(t['total_value'])
                t_qty = float(t['quantity'])
                t_ticker = t['ticker']
                
                if t['type'] in ['DEPOSIT', 'SELL', 'DIVIDEND', 'INTEREST']:
                    current_cash += t_val
                elif t['type'] in ['WITHDRAW', 'BUY']:
                    current_cash -= t_val
                
                if t_ticker != 'CASH':
                    if t['type'] == 'BUY':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) + t_qty
                    elif t['type'] == 'SELL':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) - t_qty
            
            total_value = current_cash
            if account_type not in ['SAVINGS', 'BONDS']:
                for ticker, qty in holdings_qty.items():
                    if qty > 0.0001:
                        total_value += qty * get_price_at_date(ticker, end_date)
            
            monthly_data[end_date.strftime('%Y-%m')] = total_value

        sorted_keys = sorted(monthly_data.keys())
        result = []
        for k in sorted_keys:
            dt = datetime.strptime(k, '%Y-%m')
            result.append({
                'date': k,
                'label': dt.strftime('%b %Y'),
                'value': round(monthly_data[k], 2)
            })
            
        return result

    @staticmethod
    def get_portfolio_profit_history(portfolio_id):
        """
        Calculates cumulative profit over time (month-end).
        Profit = Total Value - Net Invested Capital (Deposits - Withdrawals).
        """
        db = get_db()
        transactions = db.execute(
            'SELECT * FROM transactions WHERE portfolio_id = ? ORDER BY date ASC',
            (portfolio_id,)
        ).fetchall()
        
        if not transactions:
            return []
            
        portfolio = db.execute('SELECT account_type, created_at FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        account_type = portfolio['account_type']
        
        first_trans_date = transactions[0]['date']
        if isinstance(first_trans_date, str):
            start_date = datetime.strptime(first_trans_date.split(' ')[0], '%Y-%m-%d').date()
        else:
            start_date = first_trans_date
        
        today = date.today()
        
        # Generate month-end dates
        month_ends = []
        curr_y, curr_m = start_date.year, start_date.month
        while date(curr_y, curr_m, 1) <= today:
            if curr_m == 12:
                next_m, next_y = 1, curr_y + 1
            else:
                next_m, next_y = curr_m + 1, curr_y
                
            month_end = date(next_y, next_m, 1) - timedelta(days=1)
            if month_end > today:
                month_end = today
            month_ends.append(month_end)
            
            if month_end == today:
                break
            curr_m, curr_y = next_m, next_y
        
        # Get unique tickers and SYNC their history first!
        tickers = {t['ticker'] for t in transactions if t['ticker'] not in ['CASH', '']}
        
        if account_type not in ['SAVINGS', 'BONDS']:
            for ticker in tickers:
                try:
                    PriceService.sync_stock_history(ticker, start_date)
                except Exception as e:
                    print(f"Failed to sync history for {ticker}: {e}")

        # Load prices into memory
        price_history = {}
        if account_type not in ['SAVINGS', 'BONDS']:
            for ticker in tickers:
                rows = db.execute(
                    'SELECT date, close_price FROM stock_prices WHERE ticker = ? ORDER BY date ASC',
                    (ticker,)
                ).fetchall()
                price_history[ticker] = {str(row['date']).split(' ')[0].split('T')[0]: row['close_price'] for row in rows}

        def get_price_at_date(ticker, target_date):
            if ticker not in price_history or not price_history[ticker]:
                return 0
            
            target_str = target_date.strftime('%Y-%m-%d')
            if target_str in price_history[ticker]:
                return price_history[ticker][target_str]
            
            past_dates = [d for d in price_history[ticker].keys() if d <= target_str]
            if past_dates:
                return price_history[ticker][max(past_dates)]
            return 0

        monthly_data = {}
        
        for end_date in month_ends:
            current_cash = 0.0
            invested_capital = 0.0
            holdings_qty = {}
            
            for t in transactions:
                t_date_str = str(t['date']).split(' ')[0].split('T')[0]
                t_date = datetime.strptime(t_date_str, '%Y-%m-%d').date()
                
                if t_date > end_date:
                    continue
                
                t_val = float(t['total_value'])
                t_qty = float(t['quantity'])
                t_ticker = t['ticker']
                
                if t['type'] in ['DEPOSIT', 'SELL', 'DIVIDEND', 'INTEREST']:
                    current_cash += t_val
                elif t['type'] in ['WITHDRAW', 'BUY']:
                    current_cash -= t_val
                
                # Track Net Invested Capital
                if t['type'] == 'DEPOSIT':
                    invested_capital += t_val
                elif t['type'] == 'WITHDRAW':
                    invested_capital -= t_val
                
                if t_ticker != 'CASH':
                    if t['type'] == 'BUY':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) + t_qty
                    elif t['type'] == 'SELL':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) - t_qty
            
            total_value = current_cash
            if account_type not in ['SAVINGS', 'BONDS']:
                for ticker, qty in holdings_qty.items():
                    if qty > 0.0001:
                        total_value += qty * get_price_at_date(ticker, end_date)
            
            # For BONDS, we should ideally sum bond values, but sticking to current logic:
            # Current logic in get_portfolio_value sums bond 'total_value' (principal + accrued).
            # But here we don't have historical bond values easily unless we recalc.
            # For now, let's assume BONDS portfolio value is mainly cash + principal (if we implemented it)
            # The user previously noted BONDS logic is partial.
            # However, if account_type is SAVINGS, we might want to add accrued interest to total_value if possible?
            # The prompt says: "Ensure it includes gains from... interest already recorded in the transactions."
            # Since 'INTEREST' transactions are recorded in 'current_cash', they are already in 'total_value'.
            # So 'profit' = 'total_value' (includes interest) - 'invested_capital' (only deposits/withdraws).
            # This is correct.
            
            profit = total_value - invested_capital
            monthly_data[end_date.strftime('%Y-%m')] = profit

        sorted_keys = sorted(monthly_data.keys())
        result = []
        for k in sorted_keys:
            dt = datetime.strptime(k, '%Y-%m')
            result.append({
                'date': k,
                'label': dt.strftime('%b %Y'),
                'value': round(monthly_data[k], 2)
            })
            
        return result

    @staticmethod
    def get_portfolio_value(portfolio_id):
        portfolio = PortfolioService.get_portfolio(portfolio_id)
        if not portfolio:
            return None
        
        account_type = portfolio['account_type']
        current_cash = float(portfolio['current_cash'])
        holdings_value = 0.0
        live_interest = 0.0
        
        if account_type == 'SAVINGS':
            # Calculate live accrued interest from last_interest_date to today
            last_date_str = portfolio['last_interest_date']
            if last_date_str:
                last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
                days = (date.today() - last_date).days
                if days > 0:
                    live_interest = current_cash * (float(portfolio['savings_rate']) / 100) * (days / 365.0)
            
            # For savings, total value is cash + live interest
            total_value = current_cash + live_interest
        elif account_type == 'BONDS':
            # Get bonds and their accrued interest
            bonds = BondService.get_bonds(portfolio_id)
            holdings_value = sum(b['total_value'] for b in bonds)
            total_value = current_cash + holdings_value
        else:
            # STANDARD or IKE
            holdings = PortfolioService.get_holdings(portfolio_id)
            tickers = [h['ticker'] for h in holdings]
            current_prices = PriceService.get_prices(tickers)
            
            for h in holdings:
                ticker = h['ticker']
                price = current_prices.get(ticker)
                if price is None:
                    price = h['average_buy_price']
                holdings_value += h['quantity'] * price
            
            total_value = current_cash + holdings_value
        
        # Get total dividends
        db = get_db()
        div_result = db.execute(
            'SELECT SUM(amount) as total_div FROM dividends WHERE portfolio_id = ?',
            (portfolio_id,)
        ).fetchone()
        total_dividends = div_result['total_div'] or 0.0
        
        total_result = total_value - portfolio['total_deposits']
        total_result_percent = (total_result / portfolio['total_deposits'] * 100) if portfolio['total_deposits'] > 0 else 0.0
        
        return {
            'portfolio_value': total_value,
            'cash_value': current_cash + live_interest, # Include live interest in cash display for SAVINGS
            'holdings_value': holdings_value,
            'total_dividends': total_dividends,
            'total_result': total_result,
            'total_result_percent': total_result_percent,
            'live_interest': live_interest # Just for informational purposes
        }
