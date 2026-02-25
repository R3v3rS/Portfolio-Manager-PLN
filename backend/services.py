import yfinance as yf
import pandas as pd
from database import get_db
import sqlite3
from datetime import datetime

class PriceService:
    _price_cache = {}

    @classmethod
    def get_prices(cls, tickers):
        if not tickers:
            return {}
        
        # Identify missing tickers in cache
        missing_tickers = [t for t in tickers if t not in cls._price_cache]
        
        if missing_tickers:
            print(f"Fetching prices for: {missing_tickers}")
            try:
                # Fetch 5 days of data to handle weekends/holidays/gaps
                data = yf.download(missing_tickers, period="5d", group_by='ticker', threads=False)
                
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

class PortfolioService:
    @staticmethod
    def create_portfolio(name, initial_cash=0.0):
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                'INSERT INTO portfolios (name, current_cash, total_deposits) VALUES (?, ?, ?)',
                (name, initial_cash, initial_cash)
            )
            portfolio_id = cursor.lastrowid
            
            if initial_cash > 0:
                cursor.execute(
                    '''INSERT INTO transactions 
                       (portfolio_id, ticker, type, quantity, price, total_value) 
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (portfolio_id, 'CASH', 'DEPOSIT', 1, initial_cash, initial_cash)
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
        return dict(portfolio) if portfolio else None

    @staticmethod
    def list_portfolios():
        db = get_db()
        portfolios = db.execute('SELECT * FROM portfolios').fetchall()
        return [dict(p) for p in portfolios]

    @staticmethod
    def deposit_cash(portfolio_id, amount):
        db = get_db()
        try:
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash + ?, total_deposits = total_deposits + ? WHERE id = ?',
                (amount, amount, portfolio_id)
            )
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (portfolio_id, 'CASH', 'DEPOSIT', 1, amount, amount)
            )
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def withdraw_cash(portfolio_id, amount):
        db = get_db()
        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio or portfolio['current_cash'] < amount:
            raise ValueError("Insufficient funds")

        try:
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                (amount, portfolio_id)
            )
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (portfolio_id, 'CASH', 'WITHDRAW', 1, amount, amount)
            )
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def buy_stock(portfolio_id, ticker, quantity, price):
        db = get_db()
        total_cost = quantity * price
        
        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio or portfolio['current_cash'] < total_cost:
            raise ValueError("Insufficient funds")

        try:
            # Update cash
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                (total_cost, portfolio_id)
            )

            # Record transaction
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (portfolio_id, ticker, 'BUY', quantity, price, total_cost)
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
        
        try:
            # Update cash
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                (total_value, portfolio_id)
            )

            # Record transaction
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (portfolio_id, ticker, 'SELL', quantity, price, total_value)
            )

            # Update holdings
            new_quantity = holding['quantity'] - quantity
            if new_quantity > 0:
                new_total_cost = holding['total_cost'] - cost_basis # Reduce cost proportionally
                # Avg price remains unchanged on sell
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
            h_dict = dict(h)
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
        return [dict(t) for t in transactions]

    @staticmethod
    def get_all_transactions():
        db = get_db()
        transactions = db.execute(
            '''SELECT t.*, p.name as portfolio_name 
               FROM transactions t 
               JOIN portfolios p ON t.portfolio_id = p.id 
               ORDER BY t.date DESC'''
        ).fetchall()
        return [dict(t) for t in transactions]

    @staticmethod
    def get_portfolio_value(portfolio_id):
        portfolio = PortfolioService.get_portfolio(portfolio_id)
        if not portfolio:
            return None
        
        holdings = PortfolioService.get_holdings(portfolio_id)
        tickers = [h['ticker'] for h in holdings]
        current_prices = PriceService.get_prices(tickers)
        
        holdings_value = 0.0
        for h in holdings:
            ticker = h['ticker']
            price = current_prices.get(ticker)
            
            # Use current price if available, otherwise fallback to average buy price
            if price is None:
                price = h['average_buy_price']
                
            holdings_value += h['quantity'] * price
            
        total_value = portfolio['current_cash'] + holdings_value
        total_result = total_value - portfolio['total_deposits']
        total_result_percent = (total_result / portfolio['total_deposits'] * 100) if portfolio['total_deposits'] > 0 else 0.0
        
        return {
            'portfolio_value': total_value,
            'cash_value': portfolio['current_cash'],
            'holdings_value': holdings_value,
            'total_result': total_result,
            'total_result_percent': total_result_percent
        }
