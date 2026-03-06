from price_service import PriceService
from database import get_db
import sqlite3
from datetime import datetime, timedelta, date
from bond_service import BondService
from math_utils import xirr
from modules.ppk.ppk_service import PPKService
from dataclasses import dataclass
from typing import Optional, Any
import pandas as pd
import re
from difflib import get_close_matches


@dataclass
class SymbolMapping:
    id: int
    symbol_input: str
    ticker: str
    currency: Optional[str]
    created_at: str

class PortfolioService:
    FX_FEE_RATE = 0.005

    @staticmethod
    def _normalize_symbol_input(symbol_input: str) -> str:
        return ' '.join(str(symbol_input or '').strip().upper().split())

    @staticmethod
    def resolve_symbol_mapping(symbol_input: str) -> Optional[SymbolMapping]:
        normalized_symbol = PortfolioService._normalize_symbol_input(symbol_input)
        if not normalized_symbol:
            return None

        db = get_db()
        mapping = db.execute(
            'SELECT id, symbol_input, ticker, currency, created_at FROM symbol_mappings WHERE symbol_input = ?',
            (normalized_symbol,)
        ).fetchone()
        if mapping:
            return SymbolMapping(
                id=mapping['id'],
                symbol_input=mapping['symbol_input'],
                ticker=mapping['ticker'],
                currency=mapping['currency'],
                created_at=mapping['created_at']
            )

        rows = db.execute('SELECT id, symbol_input, ticker, currency, created_at FROM symbol_mappings').fetchall()
        normalized_lookup: dict[str, SymbolMapping] = {}
        for row in rows:
            row_symbol = PortfolioService._normalize_symbol_input(row['symbol_input'])
            if row_symbol and row_symbol not in normalized_lookup:
                normalized_lookup[row_symbol] = SymbolMapping(
                    id=row['id'],
                    symbol_input=row['symbol_input'],
                    ticker=row['ticker'],
                    currency=row['currency'],
                    created_at=row['created_at']
                )

        if normalized_symbol in normalized_lookup:
            return normalized_lookup[normalized_symbol]

        closest = get_close_matches(normalized_symbol, list(normalized_lookup.keys()), n=1, cutoff=0.92)
        if closest:
            return normalized_lookup[closest[0]]

        return None

    @staticmethod
    def resolve_symbol(symbol_input: str) -> Optional[str]:
        mapping = PortfolioService.resolve_symbol_mapping(symbol_input)
        return mapping.ticker if mapping else None

    @staticmethod
    def import_xtb_csv(portfolio_id: int, df: pd.DataFrame) -> dict[str, Any]:
        df = df.sort_values('Time')

        db = get_db()
        cursor = db.cursor()
        missing_symbols: list[str] = []

        normalized_columns = {str(col).strip().lower(): col for col in df.columns}
        symbol_column = normalized_columns.get('symbol')
        instrument_column = normalized_columns.get('instrument')

        db.execute('BEGIN')
        try:
            for _, row in df.iterrows():
                typ = row['Type']
                typ_lower = str(typ).lower()
                time = row['Time']
                amount = float(str(row['Amount']).replace(',', '.'))
                comment = str(row['Comment']) if not pd.isna(row['Comment']) else ''

                ticker: Optional[str] = None
                ticker_currency = 'PLN'
                is_stock_operation = typ_lower in {'stock purchase', 'stock sell'}

                if is_stock_operation:
                    symbol_input = ''
                    if symbol_column is not None:
                        symbol_value = row[symbol_column]
                        symbol_input = '' if pd.isna(symbol_value) else str(symbol_value)
                    elif instrument_column is not None:
                        instrument_value = row[instrument_column]
                        symbol_input = '' if pd.isna(instrument_value) else str(instrument_value)

                    mapping = PortfolioService.resolve_symbol_mapping(symbol_input)
                    ticker = mapping.ticker if mapping else None
                    ticker_currency = (mapping.currency or 'PLN') if mapping else 'PLN'
                    if ticker is None:
                        normalized_symbol = symbol_input.strip().upper()
                        if normalized_symbol and normalized_symbol not in missing_symbols:
                            missing_symbols.append(normalized_symbol)
                        continue

                if typ_lower == 'deposit':
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                        (amount, portfolio_id)
                    )
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, 'CASH', 'DEPOSIT', 1, amount, amount, time)
                    )
                elif typ_lower == 'withdrawal':
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                        (abs(amount), portfolio_id)
                    )
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, 'CASH', 'WITHDRAW', 1, abs(amount), abs(amount), time)
                    )
                elif typ_lower == 'stock purchase':
                    if not ticker:
                        raise ValueError('Missing ticker for stock purchase row')
                    m = re.search(r'(?:OPEN|CLOSE) BUY ([\d\.,]+)(?:/[\d\.,]+)? @ ([\d\.,]+)', comment)
                    if not m:
                        raise ValueError(f"Could not parse purchase comment: {comment}")
                    qty = float(str(m.group(1)).replace(',', '.'))
                    total_cost = abs(amount)
                    # XTB CSV amount is cash movement in account currency (PLN for this app),
                    # while comment unit price may be in instrument currency (e.g. EUR for EUNL.DE).
                    # Keep transaction and holding prices in PLN per unit to avoid mixed-currency math.
                    price = total_cost / qty if qty else 0.0
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                        (total_cost, portfolio_id)
                    )
                    holding = cursor.execute(
                        'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?',
                        (portfolio_id, ticker)
                    ).fetchone()
                    if holding:
                        new_qty = holding['quantity'] + qty
                        new_total_cost = holding['total_cost'] + total_cost
                        new_avg_price = new_total_cost / new_qty
                        cursor.execute(
                            '''UPDATE holdings SET quantity = ?, total_cost = ?, average_buy_price = ?, currency = ?, auto_fx_fees = ? WHERE id = ?''',
                            (new_qty, new_total_cost, new_avg_price, ticker_currency, 1 if ticker_currency != 'PLN' else holding['auto_fx_fees'], holding['id'])
                        )
                    else:
                        cursor.execute(
                            '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost, currency, auto_fx_fees)
                               VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (portfolio_id, ticker, qty, price, total_cost, ticker_currency, 1 if ticker_currency != 'PLN' else 0)
                        )
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, commission)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, ticker, 'BUY', qty, price, total_cost, time, 0.0)
                    )
                elif typ_lower == 'stock sell':
                    if not ticker:
                        raise ValueError('Missing ticker for stock sell row')
                    m = re.search(r'(?:OPEN|CLOSE) BUY ([\d\.,]+)(?:/[\d\.,]+)? @ ([\d\.,]+)', comment)
                    if not m:
                        raise ValueError(f"Could not parse sell comment: {comment}")
                    qty = float(str(m.group(1)).replace(',', '.'))
                    sell_total = abs(amount)
                    price = sell_total / qty if qty else 0.0
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                        (amount, portfolio_id)
                    )
                    holding = cursor.execute(
                        'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?',
                        (portfolio_id, ticker)
                    ).fetchone()
                    realized_profit = 0.0
                    if holding:
                        # In XTB CSV, Amount is already net cash flow after broker/FX fees.
                        realized_profit = sell_total - (holding['average_buy_price'] * qty)
                        new_qty = holding['quantity'] - qty
                        new_total_cost = holding['total_cost'] - (qty * holding['average_buy_price'])
                        if new_qty > 0:
                            cursor.execute(
                                '''UPDATE holdings SET quantity = ?, total_cost = ? WHERE id = ?''',
                                (new_qty, new_total_cost, holding['id'])
                            )
                        else:
                            cursor.execute('DELETE FROM holdings WHERE id = ?', (holding['id'],))
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, realized_profit, date, commission)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, ticker, 'SELL', qty, price, sell_total, realized_profit, time, 0.0)
                    )

            if missing_symbols:
                db.rollback()
                return {'success': False, 'missing_symbols': missing_symbols}

            db.commit()
            return {'success': True, 'missing_symbols': []}
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def get_tax_limits():
        db = get_db()
        current_year = date.today().year
        
        # Hardcoded limits for 2026 (and default)
        limits = {
            2026: {'IKE': 28260.0, 'IKZE': 11304.0}
        }
        
        year_limits = limits.get(current_year, limits[2026])
        ike_limit = year_limits['IKE']
        ikze_limit = year_limits['IKZE']
        
        # Calculate IKE deposits
        ike_deposited = 0.0
        # Use upper(name) to be case-insensitive safe
        portfolios = db.execute("SELECT id FROM portfolios WHERE upper(name) LIKE '%IKE%'").fetchall()
        for p in portfolios:
            res = db.execute("""
                SELECT SUM(total_value) as total 
                FROM transactions 
                WHERE portfolio_id = ? 
                AND type = 'DEPOSIT' 
                AND date >= ?
            """, (p['id'], f"{current_year}-01-01")).fetchone()
            if res and res['total']:
                ike_deposited += float(res['total'])
                
        # Calculate IKZE deposits
        ikze_deposited = 0.0
        portfolios = db.execute("SELECT id FROM portfolios WHERE upper(name) LIKE '%IKZE%'").fetchall()
        for p in portfolios:
            res = db.execute("""
                SELECT SUM(total_value) as total 
                FROM transactions 
                WHERE portfolio_id = ? 
                AND type = 'DEPOSIT' 
                AND date >= ?
            """, (p['id'], f"{current_year}-01-01")).fetchone()
            if res and res['total']:
                ikze_deposited += float(res['total'])
        
        return {
            "year": current_year,
            "IKE": {
                "deposited": ike_deposited,
                "limit": ike_limit,
                "percentage": round((ike_deposited / ike_limit * 100), 2) if ike_limit > 0 else 0.0
            },
            "IKZE": {
                "deposited": ikze_deposited,
                "limit": ikze_limit,
                "percentage": round((ikze_deposited / ikze_limit * 100), 2) if ikze_limit > 0 else 0.0
            }
        }

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
            
            if account_type == 'PPK':
                PPKService.create_portfolio_entry(portfolio_id, name, created_at)
            
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
    def delete_portfolio(portfolio_id):
        db = get_db()
        portfolio = db.execute('SELECT id, current_cash, account_type FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        if not portfolio:
            raise ValueError('Portfolio not found')

        has_transactions = db.execute(
            'SELECT 1 FROM transactions WHERE portfolio_id = ? LIMIT 1',
            (portfolio_id,)
        ).fetchone() is not None
        has_holdings = db.execute(
            'SELECT 1 FROM holdings WHERE portfolio_id = ? LIMIT 1',
            (portfolio_id,)
        ).fetchone() is not None
        has_bonds = db.execute(
            'SELECT 1 FROM bonds WHERE portfolio_id = ? LIMIT 1',
            (portfolio_id,)
        ).fetchone() is not None
        has_dividends = db.execute(
            'SELECT 1 FROM dividends WHERE portfolio_id = ? LIMIT 1',
            (portfolio_id,)
        ).fetchone() is not None
        has_ppk_transactions = db.execute(
            'SELECT 1 FROM ppk_transactions WHERE portfolio_id = ? LIMIT 1',
            (portfolio_id,)
        ).fetchone() is not None

        is_empty = (
            float(portfolio['current_cash'] or 0) == 0.0
            and not has_transactions
            and not has_holdings
            and not has_bonds
            and not has_dividends
            and not has_ppk_transactions
        )

        if not is_empty:
            raise ValueError('Only empty portfolios can be deleted')

        try:
            db.execute('DELETE FROM ppk_portfolios WHERE id = ?', (portfolio_id,))
            db.execute('DELETE FROM portfolios WHERE id = ?', (portfolio_id,))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
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
        portfolio = db.execute(
            'SELECT current_cash, account_type, last_interest_date, savings_rate FROM portfolios WHERE id = ?',
            (portfolio_id,)
        ).fetchone()
        
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
    def buy_stock(portfolio_id, ticker, quantity, price, purchase_date=None, commission=0.0, auto_fx_fees=False):
        db = get_db()

        existing_holding = db.execute(
            'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?',
            (portfolio_id, ticker)
        ).fetchone()

        currency = (existing_holding['currency'] if existing_holding and existing_holding['currency'] else None)
        if not currency:
            meta = PriceService.fetch_metadata(ticker)
            currency = (meta.get('currency') if meta else None) or 'PLN'
        currency = currency.upper()

        fx_rate = PortfolioService._get_fx_rates_to_pln({currency}).get(currency, 1.0)
        unit_price_pln = float(price) * fx_rate
        gross_cost = quantity * unit_price_pln
        base_commission = float(commission or 0.0)
        fx_fee = PortfolioService._calculate_fx_fee(gross_cost, currency)
        total_commission = base_commission + fx_fee
        total_cost = gross_cost + total_commission

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

            # Record transaction (PLN unit price)
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, date, commission) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, ticker, 'BUY', quantity, unit_price_pln, total_cost, purchase_date, total_commission)
            )

            # Update holdings
            holding = existing_holding
            if holding:
                new_quantity = holding['quantity'] + quantity
                new_total_cost = holding['total_cost'] + total_cost
                new_avg_price = new_total_cost / new_quantity

                db.execute(
                    '''UPDATE holdings 
                       SET quantity = ?, total_cost = ?, average_buy_price = ?, auto_fx_fees = ?, currency = ?
                       WHERE id = ?''',
                    (
                        new_quantity,
                        new_total_cost,
                        new_avg_price,
                        1 if (auto_fx_fees or currency != 'PLN') else holding['auto_fx_fees'],
                        currency,
                        holding['id']
                    )
                )
            else:
                db.execute(
                    '''INSERT INTO holdings 
                       (portfolio_id, ticker, quantity, average_buy_price, total_cost, auto_fx_fees, currency) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (portfolio_id, ticker, quantity, total_cost / quantity, total_cost, 1 if (auto_fx_fees or currency != 'PLN') else 0, currency)
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

        holding_currency = (holding['currency'] or 'PLN').upper()
        fx_rate = PortfolioService._get_fx_rates_to_pln({holding_currency}).get(holding_currency, 1.0)
        unit_price_pln = price * fx_rate
        gross_total_value = quantity * unit_price_pln
        sell_fx_fee = PortfolioService._calculate_fx_fee(gross_total_value, holding_currency)
        total_value = gross_total_value - sell_fx_fee
        cost_basis = quantity * holding['average_buy_price']
        realized_profit = total_value - cost_basis

        try:
            # Update cash
            db.execute(
                'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                (total_value, portfolio_id)
            )

            # Record transaction with realized_profit
            db.execute(
                '''INSERT INTO transactions 
                   (portfolio_id, ticker, type, quantity, price, total_value, realized_profit, commission) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, ticker, 'SELL', quantity, unit_price_pln, total_value, realized_profit, sell_fx_fee)
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
        return amount_pln * PortfolioService.FX_FEE_RATE if (currency or 'PLN').upper() != 'PLN' else 0.0


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
        price_updates = PriceService.get_price_updates(tickers)
        fx_rates = PortfolioService._get_fx_rates_to_pln({h['currency'] or 'PLN' for h in holdings})

        updates_needed = False

        holdings_value = 0.0
        for h in holdings:
            h_dict = {key: h[key] for key in h.keys()}

            # Enrich Metadata if missing
            if not h_dict.get('company_name') or not h_dict.get('sector'):
                meta = PriceService.fetch_metadata(h_dict['ticker'])
                if meta:
                    db.execute(
                        'UPDATE holdings SET company_name = ?, sector = ?, industry = ? WHERE id = ?',
                        (meta['company_name'], meta['sector'], meta['industry'], h_dict['id'])
                    )
                    h_dict.update(meta)
                    updates_needed = True

            price_native = current_prices.get(h_dict['ticker'])
            if price_native is None:
                # average_buy_price is stored in PLN, so for native fallback convert back for display
                currency = (h_dict.get('currency') or 'PLN').upper()
                fx_rate = fx_rates.get(currency, 1.0)
                price_native = (h_dict['average_buy_price'] / fx_rate) if fx_rate else h_dict['average_buy_price']

            currency = (h_dict.get('currency') or 'PLN').upper()
            fx_rate = fx_rates.get(currency, 1.0)
            price_pln = price_native * fx_rate

            h_dict['current_price'] = price_native
            h_dict['fx_rate_used'] = fx_rate
            h_dict['current_price_pln'] = price_pln
            h_dict['price_last_updated_at'] = price_updates.get(h_dict['ticker'])
            gross_current_value = h_dict['quantity'] * price_pln
            estimated_sell_fee = PortfolioService._calculate_fx_fee(gross_current_value, currency)
            h_dict['current_value_gross'] = gross_current_value
            h_dict['estimated_sell_fee'] = estimated_sell_fee
            h_dict['current_value'] = gross_current_value - estimated_sell_fee
            h_dict['auto_fx_fees'] = 1 if currency != 'PLN' else h_dict.get('auto_fx_fees', 0)
            h_dict['profit_loss'] = h_dict['current_value'] - h_dict['total_cost']
            h_dict['profit_loss_percent'] = (h_dict['profit_loss'] / h_dict['total_cost'] * 100) if h_dict['total_cost'] != 0 else 0.0
            holdings_value += h_dict['current_value']
            results.append(h_dict)

        if updates_needed:
            db.commit()

        # Calculate weights using total value (including cash if we had it here, but we'll use total holdings value for now or fetch portfolio cash)
        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        cash = portfolio['current_cash'] if portfolio else 0
        total_portfolio_value = holdings_value + cash

        return PortfolioService.calculate_metrics(results, total_portfolio_value, cash)

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
    def _calculate_historical_metrics(portfolio_id, benchmark_ticker=None):
        db = get_db()
        transactions = db.execute(
            'SELECT * FROM transactions WHERE portfolio_id = ? ORDER BY date ASC',
            (portfolio_id,)
        ).fetchall()
        
        if not transactions:
            return {}
            
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
        
        # Build ticker -> currency map for FX-aware valuation.
        ticker_currency: dict[str, str] = {}
        holding_rows = db.execute(
            'SELECT DISTINCT ticker, currency FROM holdings WHERE portfolio_id = ? AND ticker IS NOT NULL',
            (portfolio_id,)
        ).fetchall()
        for row in holding_rows:
            if row['ticker'] and row['ticker'] != 'CASH':
                ticker_currency[row['ticker']] = (row['currency'] or 'PLN').upper()

        # Sync only currently open stock tickers (quantity > 0).
        # This avoids unnecessary refreshes for fully closed positions.
# Get unique tickers and SYNC their history first!
        tickers = {t['ticker'] for t in transactions if t['ticker'] not in ['CASH', '']}

        # Resolve missing currencies lazily via metadata (fallback PLN).
        for ticker in tickers:
            if ticker not in ticker_currency:
                try:
                    meta = PriceService.fetch_metadata(ticker)
                    ticker_currency[ticker] = ((meta or {}).get('currency') or 'PLN').upper()
                except Exception:
                    ticker_currency[ticker] = 'PLN'

        fx_tickers = {f"{currency}PLN=X" for currency in set(ticker_currency.values()) if currency != 'PLN'}

        sync_tickers = set(tickers)
        sync_tickers.update(fx_tickers)
        if benchmark_ticker:
            sync_tickers.add(benchmark_ticker)

        if account_type not in ['SAVINGS', 'BONDS'] or benchmark_ticker:
            for ticker in sync_tickers:
                try:
                    # Force sync so we have the prices!
                    PriceService.sync_stock_history(ticker, start_date)
                except Exception as e:
                    print(f"Failed to sync history for {ticker}: {e}")

        # Load prices into memory
        price_history = {}
        if account_type not in ['SAVINGS', 'BONDS'] or benchmark_ticker:
            for ticker in sync_tickers:
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

        # Benchmark Simulation Setup
        benchmark_shares = 0.0
        
        monthly_data = {}
        
        for end_date in month_ends:
            current_cash = 0.0
            invested_capital = 0.0
            holdings_qty = {}
            
            # Reset benchmark calculation for each month end to ensure correctness? 
            # No, we can iterate transactions up to end_date. 
            # But simpler to just re-run simulation up to end_date or keep state.
            # Keeping state is tricky if we iterate month by month. 
            # Actually, the transactions loop below iterates ALL transactions up to end_date every time.
            # So we should reset benchmark_shares inside the loop or do it cumulatively.
            # The current loop iterates `for t in transactions` inside `for end_date in month_ends`.
            # And `if t_date > end_date: continue`.
            # So it re-calculates state from scratch for each month.
            # So we should reset benchmark_shares = 0.0 here.
            
            benchmark_shares = 0.0
            
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
                    # Benchmark Simulation
                    if benchmark_ticker:
                        bp = get_price_at_date(benchmark_ticker, t_date)
                        if bp > 0:
                            benchmark_shares += (t_val / bp)
                elif t['type'] == 'WITHDRAW':
                    invested_capital -= t_val
                    # Benchmark Simulation
                    if benchmark_ticker:
                        bp = get_price_at_date(benchmark_ticker, t_date)
                        if bp > 0:
                            benchmark_shares -= (t_val / bp)
                
                if t_ticker != 'CASH':
                    if t['type'] == 'BUY':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) + t_qty
                    elif t['type'] == 'SELL':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) - t_qty
            
            total_value = current_cash
            if account_type not in ['SAVINGS', 'BONDS']:
                for ticker, qty in holdings_qty.items():
                    if qty > 0.0001:
                        native_price = get_price_at_date(ticker, end_date)
                        currency = ticker_currency.get(ticker, 'PLN')
                        fx_rate = 1.0 if currency == 'PLN' else get_price_at_date(f"{currency}PLN=X", end_date)
                        if fx_rate <= 0:
                            fx_rate = 1.0
                        gross_value_pln = qty * native_price * fx_rate
                        net_value_pln = gross_value_pln - PortfolioService._calculate_fx_fee(gross_value_pln, currency)
                        total_value += net_value_pln
            
            profit = total_value - invested_capital
            
            metrics = {
                "total_value": total_value,
                "profit": profit
            }
            
            if benchmark_ticker:
                bp_end = get_price_at_date(benchmark_ticker, end_date)
                metrics["benchmark_value"] = round(benchmark_shares * bp_end, 2)
            
            monthly_data[end_date.strftime('%Y-%m')] = metrics
            
        return monthly_data

    @staticmethod
    def get_portfolio_history(portfolio_id, benchmark_ticker=None):
        """
        Reconstructs portfolio value over time based on transactions.
        Groups by month.
        """
        monthly_data = PortfolioService._calculate_historical_metrics(portfolio_id, benchmark_ticker)
        if not monthly_data:
            return []

        sorted_keys = sorted(monthly_data.keys())
        result = []
        for k in sorted_keys:
            dt = datetime.strptime(k, '%Y-%m')
            entry = {
                'date': k,
                'label': dt.strftime('%b %Y'),
                'value': round(monthly_data[k]['total_value'], 2)
            }
            if 'benchmark_value' in monthly_data[k]:
                entry['benchmark_value'] = monthly_data[k]['benchmark_value']
            result.append(entry)
            
        return result

    @staticmethod
    def get_portfolio_profit_history(portfolio_id):
        """
        Calculates cumulative profit over time (month-end).
        Profit = Total Value - Net Invested Capital (Deposits - Withdrawals).
        """
        monthly_data = PortfolioService._calculate_historical_metrics(portfolio_id)
        if not monthly_data:
            return []

        sorted_keys = sorted(monthly_data.keys())
        result = []
        for k in sorted_keys:
            dt = datetime.strptime(k, '%Y-%m')
            result.append({
                'date': k,
                'label': dt.strftime('%b %Y'),
                'value': round(monthly_data[k]['profit'], 2)
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
        extra_data = {}
        ppk_total_contribution = None
        ppk_total_result = None

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
        elif account_type == 'PPK':
            current_price = None
            try:
                current_price = PPKService.fetch_current_price()['price']
            except Exception:
                current_price = None

            ppk_summary = PPKService.get_portfolio_summary(portfolio_id, current_price)
            # For PPK show withdrawable value (employee 100%, employer 70%, reduced by 19% tax on gains).
            holdings_value = ppk_summary['totalNetValue']
            total_value = current_cash + holdings_value
            ppk_total_contribution = float(ppk_summary['totalPurchaseValue'])
            ppk_total_result = float(ppk_summary['netProfit'])
            extra_data = ppk_summary
        else:
            # STANDARD or IKE
            holdings = PortfolioService.get_holdings(portfolio_id)
            holdings_value = sum(float(h.get('current_value', 0.0) or 0.0) for h in holdings)
            total_value = current_cash + holdings_value
        
        # Get total dividends
        db = get_db()
        div_result = db.execute(
            'SELECT SUM(amount) as total_div FROM dividends WHERE portfolio_id = ?',
            (portfolio_id,)
        ).fetchone()
        total_dividends = div_result['total_div'] or 0.0
        
        # Use net contributed capital (deposits - withdrawals) as the performance baseline.
        # This keeps profit/loss meaningful after partial withdrawals.
        flows_result = db.execute(
            '''SELECT
                   COALESCE(SUM(CASE WHEN type = 'DEPOSIT' THEN total_value ELSE 0 END), 0) AS deposits,
                   COALESCE(SUM(CASE WHEN type = 'WITHDRAW' THEN total_value ELSE 0 END), 0) AS withdrawals
               FROM transactions
               WHERE portfolio_id = ?''',
            (portfolio_id,)
        ).fetchone()
        net_contributions = float(flows_result['deposits']) - float(flows_result['withdrawals'])
        if account_type == 'PPK':
            # PPK contribution baseline comes from PPK unit purchases, not generic cash flows.
            net_contributions = ppk_total_contribution or 0.0

        total_result = ppk_total_result if (account_type == 'PPK' and ppk_total_result is not None) else (total_value - net_contributions)
        total_result_percent = (total_result / net_contributions * 100) if net_contributions > 0 else 0.0
        
        # Calculate XIRR
        xirr_percent = 0.0
        try:
            # Fetch deposits and withdrawals for XIRR calculation
            transactions = db.execute(
                'SELECT date, type, total_value FROM transactions WHERE portfolio_id = ? AND type IN (?, ?)',
                (portfolio_id, 'DEPOSIT', 'WITHDRAW')
            ).fetchall()
            
            cash_flows = []
            for t in transactions:
                try:
                    t_date_str = str(t['date']).split(' ')[0] # Handle 'YYYY-MM-DD HH:MM:SS'
                    t_date = datetime.strptime(t_date_str, '%Y-%m-%d').date()
                    amount = float(t['total_value'])
                    
                    if t['type'] == 'DEPOSIT':
                        cash_flows.append((t_date, -amount))
                    elif t['type'] == 'WITHDRAW':
                        cash_flows.append((t_date, amount))
                except Exception as e:
                    print(f"Error parsing transaction for XIRR: {e}")
                    continue
            
            # Add current portfolio value as final cash flow (treated as if we withdrew everything today)
            if cash_flows:
                cash_flows.append((date.today(), total_value))
                xirr_percent = xirr(cash_flows)
                
        except Exception as e:
            print(f"Error calculating XIRR: {e}")
            xirr_percent = 0.0

        result = {
            'portfolio_value': total_value,
            'cash_value': current_cash + live_interest, # Include live interest in cash display for SAVINGS
            'holdings_value': holdings_value,
            'total_dividends': total_dividends,
            'total_result': total_result,
            'total_result_percent': total_result_percent,
            'xirr_percent': xirr_percent,
            'live_interest': live_interest # Just for informational purposes
        }
        
        if extra_data:
            result.update(extra_data)
            
        return result

    @staticmethod
    def get_performance_matrix(portfolio_id):
        """
        Calculates monthly returns using Modified Dietz method (simplified).
        Returns a matrix of returns by year and month.
        """
        # 1. Get month-end values
        monthly_values_map = PortfolioService._calculate_historical_metrics(portfolio_id)
        if not monthly_values_map:
            return {}

        # 2. Get all cash flow transactions (Deposit/Withdraw)
        db = get_db()
        transactions = db.execute(
            '''SELECT date, type, total_value 
               FROM transactions 
               WHERE portfolio_id = ? AND type IN ('DEPOSIT', 'WITHDRAW')
               ORDER BY date ASC''',
            (portfolio_id,)
        ).fetchall()
        
        # Group cash flows by month (YYYY-MM)
        monthly_flows = {}
        for t in transactions:
            t_date_str = str(t['date']).split(' ')[0]
            month_key = t_date_str[:7] # YYYY-MM
            amount = float(t['total_value'])
            
            if month_key not in monthly_flows:
                monthly_flows[month_key] = 0.0
                
            if t['type'] == 'DEPOSIT':
                monthly_flows[month_key] += amount
            elif t['type'] == 'WITHDRAW':
                monthly_flows[month_key] -= amount

        # 3. Calculate Monthly Returns
        sorted_months = sorted(monthly_values_map.keys())
        results = {} # { "2024": { "1": 2.5, "YTD": ... } }
        
        previous_end_value = 0.0
        
        # We need to process from the very first month found in transactions or values
        # If the first month in monthly_values_map is say 2024-03, we assume 2024-02 end value was 0 (or strictly speaking, we start calculation from 2024-03)
        
        # To calculate YTD properly, we need to track cumulative return for each year
        # Cumulative Return = (1 + r1) * (1 + r2) * ... - 1
        
        yearly_compounding = {} # Year -> running product (1.0 start)

        for month_key in sorted_months:
            year, month = month_key.split('-')
            year_key = str(year)
            month_int = str(int(month)) # "01" -> "1"
            
            if year_key not in results:
                results[year_key] = {}
                yearly_compounding[year_key] = 1.0

            # Data for calculation
            end_value = monthly_values_map[month_key]['total_value']
            net_flows = monthly_flows.get(month_key, 0.0)
            start_value = previous_end_value
            
            # Modified Dietz (Simplified)
            # Return = (End - Start - NetFlows) / (Start + NetFlows/2)
            
            profit = end_value - start_value - net_flows
            denominator = start_value + (net_flows / 2.0)
            
            if denominator <= 0:
                # Edge case: if denominator is zero or negative (e.g. huge withdrawal matching start value), 
                # usually return is 0 or undefined. If it's the first deposit, return is 0 (no gain on capital yet).
                monthly_return = 0.0
            else:
                monthly_return = profit / denominator
                
            monthly_return_percent = round(monthly_return * 100, 2)
            
            results[year_key][month_int] = monthly_return_percent
            
            # Update YTD compounding
            yearly_compounding[year_key] *= (1.0 + monthly_return)
            
            # Update YTD field
            ytd_val = (yearly_compounding[year_key] - 1.0) * 100
            results[year_key]['YTD'] = round(ytd_val, 2)
            
            # Prepare for next iteration
            previous_end_value = end_value
            
        return results
