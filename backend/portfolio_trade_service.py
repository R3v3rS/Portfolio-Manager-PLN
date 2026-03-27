from price_service import PriceService
from database import get_db
from datetime import datetime, date
from portfolio_core_service import PortfolioCoreService


class PortfolioTradeService(PortfolioCoreService):
    @staticmethod
    def _capitalize_savings(db, portfolio_id):
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
                db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (interest, portfolio_id))
                db.execute('''INSERT INTO transactions 
                       (portfolio_id, ticker, type, quantity, price, total_value, date) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, 'CASH', 'INTEREST', 1, interest, interest, today.isoformat()))
        db.execute('UPDATE portfolios SET last_interest_date = ? WHERE id = ?', (today.isoformat(), portfolio_id))

    @staticmethod
    def deposit_cash(portfolio_id, amount, date_str=None):
        db = get_db()
        try:
            PortfolioTradeService._capitalize_savings(db, portfolio_id)
            if not date_str:
                date_str = date.today().isoformat()
            db.execute('UPDATE portfolios SET current_cash = current_cash + ?, total_deposits = total_deposits + ? WHERE id = ?', (amount, amount, portfolio_id))
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, 'CASH', 'DEPOSIT', 1, amount, amount, date_str))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def withdraw_cash(portfolio_id, amount, date_str=None):
        db = get_db()
        portfolio = db.execute('SELECT current_cash, account_type, last_interest_date, savings_rate FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        live_interest = 0
        if portfolio and portfolio['account_type'] == 'SAVINGS':
            last_date = datetime.strptime(portfolio['last_interest_date'], '%Y-%m-%d').date()
            days = (date.today() - last_date).days
            if days > 0:
                live_interest = float(portfolio['current_cash']) * (float(portfolio['savings_rate']) / 100) * (days / 365.0)
        if not portfolio or (portfolio['current_cash'] + live_interest) < amount:
            raise ValueError("Insufficient funds")
        try:
            PortfolioTradeService._capitalize_savings(db, portfolio_id)
            if not date_str:
                date_str = date.today().isoformat()
            db.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (amount, portfolio_id))
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, 'CASH', 'WITHDRAW', 1, amount, amount, date_str))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def update_savings_rate(portfolio_id, new_rate):
        db = get_db()
        try:
            PortfolioTradeService._capitalize_savings(db, portfolio_id)
            db.execute('UPDATE portfolios SET savings_rate = ? WHERE id = ?', (new_rate, portfolio_id))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def buy_stock(portfolio_id, ticker, quantity, price, purchase_date=None, commission=0.0, auto_fx_fees=False):
        db = get_db()
        context = PriceService.build_context()
        existing_holding = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?', (portfolio_id, ticker)).fetchone()
        currency = (existing_holding['currency'] if existing_holding and existing_holding['currency'] else None)
        if not currency:
            meta = PriceService.fetch_metadata(ticker, context=context)
            currency = (meta.get('currency') if meta else None) or 'PLN'
        currency = currency.upper()
        unit_price_pln = float(price)
        base_commission = float(commission or 0.0)
        total_commission = base_commission
        gross_cost = quantity * unit_price_pln
        total_cost = gross_cost + total_commission
        if not purchase_date:
            purchase_date = date.today().isoformat()
        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio or portfolio['current_cash'] < total_cost:
            raise ValueError("Insufficient funds")
        try:
            PriceService.sync_stock_history(ticker, purchase_date, context=context)
            db.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (total_cost, portfolio_id))
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date, commission) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, ticker, 'BUY', quantity, unit_price_pln, total_cost, purchase_date, total_commission))
            holding = existing_holding
            if holding:
                new_quantity = holding['quantity'] + quantity
                new_total_cost = holding['total_cost'] + total_cost
                new_avg_price = new_total_cost / new_quantity
                db.execute('''UPDATE holdings 
                       SET quantity = ?, total_cost = ?, average_buy_price = ?, auto_fx_fees = ?, currency = ?
                       WHERE id = ?''', (new_quantity, new_total_cost, new_avg_price, 1 if (auto_fx_fees or currency != 'PLN') else holding['auto_fx_fees'], currency, holding['id']))
            else:
                db.execute('''INSERT INTO holdings 
                       (portfolio_id, ticker, quantity, average_buy_price, total_cost, auto_fx_fees, currency) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, ticker, quantity, total_cost / quantity, total_cost, 1 if (auto_fx_fees or currency != 'PLN') else 0, currency))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def sell_stock(portfolio_id, ticker, quantity, price, sell_date=None):
        db = get_db()
        holding = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?', (portfolio_id, ticker)).fetchone()
        if not holding or holding['quantity'] < quantity:
            raise ValueError("Insufficient shares")
        unit_price_pln = float(price)
        total_value = quantity * unit_price_pln
        cost_basis = quantity * holding['average_buy_price']
        realized_profit = total_value - cost_basis
        if not sell_date:
            sell_date = date.today().isoformat()
        try:
            db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (total_value, portfolio_id))
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, realized_profit, date, commission) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, ticker, 'SELL', quantity, unit_price_pln, total_value, realized_profit, sell_date, 0.0))
            new_quantity = holding['quantity'] - quantity
            if new_quantity > 0.000001:
                new_total_cost = holding['total_cost'] - cost_basis
                db.execute('''UPDATE holdings 
                       SET quantity = ?, total_cost = ?
                       WHERE id = ?''', (new_quantity, new_total_cost, holding['id']))
            else:
                db.execute('DELETE FROM holdings WHERE id = ?', (holding['id'],))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def record_dividend(portfolio_id, ticker, amount, date):
        db = get_db()
        try:
            db.execute('''INSERT INTO dividends (portfolio_id, ticker, amount, date)
                   VALUES (?, ?, ?, ?)''', (portfolio_id, ticker, amount, date))
            db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (amount, portfolio_id))
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, ticker, 'DIVIDEND', 1, amount, amount, date))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def add_manual_interest(portfolio_id, amount, date_str):
        db = get_db()
        try:
            PortfolioTradeService._capitalize_savings(db, portfolio_id)
            db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (amount, portfolio_id))
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, 'CASH', 'INTEREST', 1, amount, amount, date_str))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def _get_fx_rates_to_pln(currencies: set[str]) -> dict[str, float]:
        normalized = {str(c or '').strip().upper() for c in currencies if c}
        normalized.discard('PLN')
        if not normalized:
            return {'PLN': 1.0}
        fx_ticker_map = {currency: f"{currency}PLN=X" for currency in normalized}
        context = PriceService.build_context()
        fx_prices = PriceService.get_prices(list(fx_ticker_map.values()), context=context)
        rates = {'PLN': 1.0}
        for currency, fx_ticker in fx_ticker_map.items():
            rate = fx_prices.get(fx_ticker)
            rates[currency] = float(rate) if rate else 1.0
        return rates

    @staticmethod
    def _calculate_fx_fee(amount_pln: float, currency: str) -> float:
        return amount_pln * PortfolioTradeService.FX_FEE_RATE if (currency or 'PLN').upper() != 'PLN' else 0.0
