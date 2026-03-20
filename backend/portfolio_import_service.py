from database import get_db
from portfolio_core_service import PortfolioCoreService, SymbolMapping
from typing import Optional, Any
from difflib import get_close_matches
import pandas as pd
import re


class PortfolioImportService(PortfolioCoreService):
    @staticmethod
    def resolve_symbol_mapping(symbol_input: str) -> Optional[SymbolMapping]:
        normalized_symbol = PortfolioImportService._normalize_symbol_input(symbol_input)
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
            row_symbol = PortfolioImportService._normalize_symbol_input(row['symbol_input'])
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
        mapping = PortfolioImportService.resolve_symbol_mapping(symbol_input)
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
                typ_lower = str(typ).strip().lower()
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

                    mapping = PortfolioImportService.resolve_symbol_mapping(symbol_input)
                    ticker = mapping.ticker if mapping else None
                    ticker_currency = (mapping.currency or 'PLN') if mapping else 'PLN'
                    if ticker is None:
                        normalized_symbol = symbol_input.strip().upper()
                        if normalized_symbol and normalized_symbol not in missing_symbols:
                            missing_symbols.append(normalized_symbol)
                        continue

                if typ_lower in {'deposit', 'ike deposit'}:
                    deposit_amount = abs(amount)
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                        (deposit_amount, portfolio_id)
                    )
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, 'CASH', 'DEPOSIT', 1, deposit_amount, deposit_amount, time)
                    )
                elif typ_lower == 'free funds interest':
                    interest_amount = abs(amount)
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                        (interest_amount, portfolio_id)
                    )
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, 'CASH', 'INTEREST', 1, interest_amount, interest_amount, time)
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
