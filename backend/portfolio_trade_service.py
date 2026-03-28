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
    def deposit_cash(portfolio_id, amount, date_str=None, sub_portfolio_id=None):
        db = get_db()
        try:
            PortfolioTradeService._capitalize_savings(db, portfolio_id)
            if not date_str:
                date_str = date.today().isoformat()
            
            # If sub_portfolio_id is provided, validate it belongs to the parent
            if sub_portfolio_id:
                child = db.execute('SELECT id, is_archived FROM portfolios WHERE id = ? AND parent_portfolio_id = ?', (sub_portfolio_id, portfolio_id)).fetchone()
                if not child:
                    raise ValueError("Invalid sub-portfolio for this parent")
                if child['is_archived']:
                    raise ValueError("Cannot deposit to an archived sub-portfolio")

            target_id = sub_portfolio_id if sub_portfolio_id else portfolio_id
            db.execute('UPDATE portfolios SET current_cash = current_cash + ?, total_deposits = total_deposits + ? WHERE id = ?', (amount, amount, target_id))
            
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, 'CASH', 'DEPOSIT', 1, amount, amount, date_str, sub_portfolio_id))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def withdraw_cash(portfolio_id, amount, date_str=None, sub_portfolio_id=None):
        db = get_db()
        
        target_id = sub_portfolio_id if sub_portfolio_id else portfolio_id
        portfolio = db.execute('SELECT current_cash, account_type, last_interest_date, savings_rate FROM portfolios WHERE id = ?', (target_id,)).fetchone()
        
        live_interest = 0
        if portfolio and portfolio['account_type'] == 'SAVINGS':
            last_date_str = portfolio['last_interest_date']
            if last_date_str:
                last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
                days = (date.today() - last_date).days
                if days > 0:
                    live_interest = float(portfolio['current_cash']) * (float(portfolio['savings_rate']) / 100) * (days / 365.0)
        
        if not portfolio or (portfolio['current_cash'] + live_interest) < amount:
            raise ValueError(f"Insufficient funds in {('sub-portfolio' if sub_portfolio_id else 'parent portfolio')}")
            
        try:
            PortfolioTradeService._capitalize_savings(db, target_id)
            if not date_str:
                date_str = date.today().isoformat()
            
            db.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (amount, target_id))
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, 'CASH', 'WITHDRAW', 1, amount, amount, date_str, sub_portfolio_id))
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
    def buy_stock(portfolio_id, ticker, quantity, price, purchase_date=None, commission=0.0, auto_fx_fees=False, sub_portfolio_id=None):
        db = get_db()
        try:
            # If sub_portfolio_id is provided, validate it belongs to the parent
            if sub_portfolio_id:
                child = db.execute('SELECT id, is_archived FROM portfolios WHERE id = ? AND parent_portfolio_id = ?', (sub_portfolio_id, portfolio_id)).fetchone()
                if not child:
                    raise ValueError("Invalid sub-portfolio for this parent")
                if child['is_archived']:
                    raise ValueError("Cannot record buy for an archived sub-portfolio")

            existing_holding = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS ' + ('?' if sub_portfolio_id else 'NULL'), 
                                         (portfolio_id, ticker, sub_portfolio_id) if sub_portfolio_id else (portfolio_id, ticker)).fetchone()
            
            currency = (existing_holding['currency'] if existing_holding and existing_holding['currency'] else None)
            if not currency:
                meta = PriceService.fetch_metadata(ticker)
                currency = (meta.get('currency') if meta else None) or 'PLN'
            currency = currency.upper()
            unit_price_pln = float(price)
            base_commission = float(commission or 0.0)
            total_commission = base_commission
            gross_cost = quantity * unit_price_pln
            total_cost = gross_cost + total_commission
            if not purchase_date:
                purchase_date = date.today().isoformat()

            # Check cash of the specific portfolio (parent or child)
            target_id = sub_portfolio_id if sub_portfolio_id else portfolio_id
            portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (target_id,)).fetchone()
            if not portfolio or portfolio['current_cash'] < total_cost:
                raise ValueError(f"Insufficient cash in {('sub-portfolio' if sub_portfolio_id else 'parent portfolio')}")

            PriceService.sync_stock_history(ticker, purchase_date)
            db.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (total_cost, target_id))
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date, commission, sub_portfolio_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, ticker, 'BUY', quantity, unit_price_pln, total_cost, purchase_date, total_commission, sub_portfolio_id))
            
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
                       (portfolio_id, ticker, quantity, average_buy_price, total_cost, auto_fx_fees, currency, sub_portfolio_id) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, ticker, quantity, total_cost / quantity, total_cost, 1 if (auto_fx_fees or currency != 'PLN') else 0, currency, sub_portfolio_id))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def sell_stock(portfolio_id, ticker, quantity, price, sell_date=None, sub_portfolio_id=None):
        db = get_db()
        # Find holding in the specific portfolio/sub-portfolio
        holding = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS ' + ('?' if sub_portfolio_id else 'NULL'), 
                            (portfolio_id, ticker, sub_portfolio_id) if sub_portfolio_id else (portfolio_id, ticker)).fetchone()
        
        if not holding or holding['quantity'] < quantity:
            raise ValueError("Insufficient shares in " + ("sub-portfolio" if sub_portfolio_id else "parent portfolio"))
        
        unit_price_pln = float(price)
        total_value = quantity * unit_price_pln
        cost_basis = quantity * holding['average_buy_price']
        realized_profit = total_value - cost_basis
        if not sell_date:
            sell_date = date.today().isoformat()
        try:
            target_id = sub_portfolio_id if sub_portfolio_id else portfolio_id
            db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (total_value, target_id))
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, realized_profit, date, commission, sub_portfolio_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, ticker, 'SELL', quantity, unit_price_pln, total_value, realized_profit, sell_date, 0.0, sub_portfolio_id))
            
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
    def record_dividend(portfolio_id, ticker, amount, date, sub_portfolio_id=None):
        db = get_db()
        try:
            # If sub_portfolio_id is provided, validate it belongs to the parent
            if sub_portfolio_id:
                child = db.execute('SELECT id, is_archived FROM portfolios WHERE id = ? AND parent_portfolio_id = ?', (sub_portfolio_id, portfolio_id)).fetchone()
                if not child:
                    raise ValueError("Invalid sub-portfolio for this parent")
                if child['is_archived']:
                    raise ValueError("Cannot record dividend for an archived sub-portfolio")

            db.execute('''INSERT INTO dividends (portfolio_id, ticker, amount, date, sub_portfolio_id)
                   VALUES (?, ?, ?, ?, ?)''', (portfolio_id, ticker, amount, date, sub_portfolio_id))
            
            # Update cash of the specific portfolio (parent or child)
            target_id = sub_portfolio_id if sub_portfolio_id else portfolio_id
            db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (amount, target_id))
            
            db.execute('''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (portfolio_id, ticker, 'DIVIDEND', 1, amount, amount, date, sub_portfolio_id))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def validate_transfer_target(db, portfolio_id, target_sub_portfolio_id):
        """
        Validates if a target sub-portfolio is a valid transfer destination.
        Returns the child portfolio record if valid, or None if target is parent.
        Raises ValueError if invalid.
        """
        if not target_sub_portfolio_id:
            return None
            
        child = db.execute(
            'SELECT id, is_archived, parent_portfolio_id FROM portfolios WHERE id = ?', 
            (target_sub_portfolio_id,)
        ).fetchone()
        
        if not child:
            raise ValueError("Target sub-portfolio not found")
        if child['parent_portfolio_id'] != portfolio_id:
            raise ValueError("Target sub-portfolio belongs to a different parent")
        if child['is_archived']:
            raise ValueError("Cannot assign to an archived sub-portfolio")
            
        return child

    @staticmethod
    def assign_transaction_to_subportfolio(transaction_id, sub_portfolio_id):
        db = get_db()
        tx = db.execute('SELECT * FROM transactions WHERE id = ?', (transaction_id,)).fetchone()
        if not tx:
            raise ValueError("Transaction not found")
        
        portfolio_id = tx['portfolio_id']
        old_sub_portfolio_id = tx['sub_portfolio_id']
        tx_type = tx['type']
        total_value = float(tx['total_value'])
        
        if sub_portfolio_id == old_sub_portfolio_id:
            return True

        if tx_type == 'INTEREST' and sub_portfolio_id is not None:
            raise ValueError("INTEREST transactions must remain in parent portfolio")

        try:
            # Validate target
            PortfolioTradeService.validate_transfer_target(db, portfolio_id, sub_portfolio_id)

            # 1. Update the transaction
            db.execute('UPDATE transactions SET sub_portfolio_id = ? WHERE id = ?', (sub_portfolio_id, transaction_id))
            
            # 2. Update dividends if applicable
            if tx_type == 'DIVIDEND':
                db.execute('UPDATE dividends SET sub_portfolio_id = ? WHERE portfolio_id = ? AND ticker = ? AND date = ? AND amount = ?', 
                           (sub_portfolio_id, portfolio_id, tx['ticker'], tx['date'], tx['total_value']))

            # 3. Move cash between sub-portfolios
            # In sub-portfolio mode, the PortfolioAuditService.repair_portfolio_state 
            # is responsible for setting the definitive cash balance based on transaction history.
            # We don't manually adjust current_cash here because it would lead to double-counting 
            # if repair_portfolio_state is called immediately after (which it is in routes_transactions).
            
            # HOWEVER, if we are NOT in a repair job context, we might want to update it.
            # Given the current architecture, repair_portfolio_state is the source of truth.
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def assign_transactions_bulk(transaction_ids, sub_portfolio_id):
        if not transaction_ids:
            return True
            
        db = get_db()
        try:
            # Check if all transactions belong to the same parent portfolio
            placeholders = ', '.join(['?'] * len(transaction_ids))
            parents = db.execute(f'SELECT DISTINCT portfolio_id FROM transactions WHERE id IN ({placeholders})', transaction_ids).fetchall()
            
            if not parents:
                raise ValueError("No transactions found")
            if len(parents) > 1:
                raise ValueError("Bulk assignment must be for transactions within the same parent portfolio")
                
            portfolio_id = parents[0]['portfolio_id']
            
            # Validate target sub-portfolio
            PortfolioTradeService.validate_transfer_target(db, portfolio_id, sub_portfolio_id)
            
            # Process each transaction to handle cash movement
            # In a more optimized version, we could group cash movements, 
            # but for safety and clarity we'll do them one by one or in a loop.
            for tx_id in transaction_ids:
                PortfolioTradeService.assign_transaction_to_subportfolio(tx_id, sub_portfolio_id)
                
            return True
        except Exception as e:
            # assign_transaction_to_subportfolio already does rollback, but we might need it here too if error happens outside
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
        fx_prices = PriceService.get_prices(list(fx_ticker_map.values()))
        rates = {'PLN': 1.0}
        for currency, fx_ticker in fx_ticker_map.items():
            rate = fx_prices.get(fx_ticker)
            rates[currency] = float(rate) if rate else 1.0
        return rates

    @staticmethod
    def _calculate_fx_fee(amount_pln: float, currency: str) -> float:
        return amount_pln * PortfolioTradeService.FX_FEE_RATE if (currency or 'PLN').upper() != 'PLN' else 0.0
