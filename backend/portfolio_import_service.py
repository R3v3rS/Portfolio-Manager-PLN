from database import get_db
from portfolio_core_service import PortfolioCoreService, SymbolMapping
from typing import Optional, Any
from difflib import get_close_matches
import pandas as pd
import re
import hashlib


class PortfolioImportService(PortfolioCoreService):
    @staticmethod
    def _try_parse_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in {'nan', 'none', 'null'}:
            return None
        normalized = text.replace('\u00a0', '').replace(' ', '').replace(',', '.')
        try:
            return float(normalized)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _select_column(
        normalized_columns: dict[str, str],
        aliases: list[str],
        df: Optional[pd.DataFrame] = None,
        numeric_preferred: bool = False,
    ) -> Optional[str]:
        candidates: list[str] = []
        for alias in aliases:
            col = normalized_columns.get(alias)
            if col is not None:
                candidates.append(col)

        if not candidates:
            return None
        if len(candidates) == 1 or not numeric_preferred or df is None:
            return candidates[0]

        best_col = candidates[0]
        best_score = -1.0
        for col in candidates:
            series = df[col].dropna().head(20)
            if series.empty:
                continue
            parseable = sum(1 for value in series if PortfolioImportService._try_parse_float(value) is not None)
            score = parseable / len(series)
            if score > best_score:
                best_score = score
                best_col = col

        return best_col

    @staticmethod
    def _generate_row_hash(date: str, ticker: str, amount: float, type: str, quantity: float) -> str:
        """Generuje hash dla wiersza transakcji w celu identyfikacji duplikatów."""
        # Normalizacja danych do hasha:
        # - kwoty zaokrąglone do 2 miejsc po przecinku
        # - ilości zaokrąglone do 8 miejsc po przecinku (dla krypto/ułamkowych akcji)
        # - ticker i typ wielkimi literami
        payload = f"{date}|{ticker.strip().upper()}|{amount:.2f}|{type.strip().upper()}|{quantity:.8f}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

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
    def import_xtb_csv(portfolio_id: int, df: pd.DataFrame, confirmed_hashes: Optional[list[str]] = None, sub_portfolio_id: Optional[int] = None) -> dict[str, Any]:
        db = get_db()
        cursor = db.cursor()
        missing_symbols: list[str] = []
        potential_conflicts: list[dict] = []
        internal_hashes = {} # hash -> row_index for internal duplicate source tracking
        
        # If sub_portfolio_id is provided, validate it belongs to the parent
        if sub_portfolio_id:
            child = db.execute('SELECT id, is_archived FROM portfolios WHERE id = ? AND parent_portfolio_id = ?', (sub_portfolio_id, portfolio_id)).fetchone()
            if not child:
                raise ValueError("Invalid sub-portfolio for this parent")
            if child['is_archived']:
                raise ValueError("Cannot import to an archived sub-portfolio")

        # ... (rest of the logic remains similar but needs sub_portfolio_id in queries)
        # For simplicity, I'll search and replace specific parts.
        
        # Przygotowanie transakcji do przetworzenia
        prepared_transactions = []

        normalized_columns = {str(col).strip().lower(): col for col in df.columns}
        time_column = PortfolioImportService._select_column(normalized_columns, ['time', 'date', 'close time'])
        type_column = PortfolioImportService._select_column(normalized_columns, ['type', 'transaction type'])
        amount_column = PortfolioImportService._select_column(
            normalized_columns,
            ['amount', 'profit', 'p/l', 'profit/loss', 'result'],
            df=df,
            numeric_preferred=True,
        )
        comment_column = PortfolioImportService._select_column(normalized_columns, ['comment', 'description', 'details'])
        symbol_column = PortfolioImportService._select_column(normalized_columns, ['symbol'])
        instrument_column = PortfolioImportService._select_column(normalized_columns, ['instrument'])

        missing_required: list[str] = []
        if time_column is None:
            missing_required.append('Time')
        if type_column is None:
            missing_required.append('Type')
        if amount_column is None:
            missing_required.append('Amount')
        if missing_required:
            raise ValueError(f"Missing required columns: {', '.join(missing_required)}")

        df = df.sort_values(time_column)

        # ETAP 1: Walidacja i przygotowanie danych
        for idx, row in df.iterrows():
            typ = row[type_column]
            typ_lower = str(typ).strip().lower()
            time = str(row[time_column]).strip()
            amount_value = PortfolioImportService._try_parse_float(row[amount_column])
            if amount_value is None:
                raise ValueError(f"Invalid numeric value in column '{amount_column}' at row {idx + 1}: {row[amount_column]}")
            amount = amount_value
            comment = ''
            if comment_column is not None and not pd.isna(row[comment_column]):
                comment = str(row[comment_column])

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

            # Ustalanie parametrów transakcji do walidacji duplikatów
            tx_type = ''
            tx_ticker = ticker or 'CASH'
            tx_qty = 1.0
            tx_total = abs(amount)

            if typ_lower in {'deposit', 'ike deposit'}:
                tx_type = 'DEPOSIT'
            elif typ_lower == 'free funds interest':
                tx_type = 'INTEREST'
            elif typ_lower == 'withdrawal':
                tx_type = 'WITHDRAW'
            elif typ_lower == 'stock purchase':
                tx_type = 'BUY'
                m = re.search(r'(?:OPEN|CLOSE) BUY ([\d\.,]+)(?:/[\d\.,]+)? @ ([\d\.,]+)', comment)
                if not m:
                    raise ValueError(f"Could not parse purchase comment: {comment}")
                tx_qty = float(str(m.group(1)).replace(',', '.'))
            elif typ_lower == 'stock sell':
                tx_type = 'SELL'
                m = re.search(r'(?:OPEN|CLOSE) BUY ([\d\.,]+)(?:/[\d\.,]+)? @ ([\d\.,]+)', comment)
                if not m:
                    raise ValueError(f"Could not parse sell comment: {comment}")
                tx_qty = float(str(m.group(1)).replace(',', '.'))

            if not tx_type:
                continue # Nieobsługiwany typ

            row_hash = PortfolioImportService._generate_row_hash(time, tx_ticker, tx_total, tx_type, tx_qty)
            
            # Dane do zapisu w prepared_transactions
            tx_data = {
                'hash': row_hash,
                'type_raw': typ_lower,
                'time': time,
                'amount_raw': amount,
                'comment': comment,
                'ticker': tx_ticker,
                'ticker_currency': ticker_currency,
                'tx_type': tx_type,
                'tx_qty': tx_qty,
                'tx_total': tx_total,
                'is_conflict': False, # Domyślnie brak konfliktu
                'import_data': {
                    'date': time,
                    'ticker': tx_ticker,
                    'amount': tx_total,
                    'type': tx_type,
                    'quantity': tx_qty
                }
            }

            # Sprawdzanie duplikatu wewnątrz pliku
            if row_hash in internal_hashes:
                source_idx = internal_hashes[row_hash]
                tx_data['is_conflict'] = True # Ten konkretny wiersz (kopia) jest konfliktem
                potential_conflicts.append({
                    'row_hash': row_hash,
                    'conflict_type': 'file_internal_duplicate',
                    'import_data': tx_data['import_data'],
                    'existing_match': {
                        'id': None,
                        'date': time,
                        'amount': tx_total,
                        'type': tx_type,
                        'quantity': tx_qty,
                        'source': f'file_row_{source_idx}'
                    }
                })
            else:
                internal_hashes[row_hash] = idx
                # Sprawdzanie duplikatu w bazie danych
                # Używamy ROUND dla total_value i quantity, aby uniknąć problemów z precyzją float
                # Filter by sub_portfolio_id as well
                existing = db.execute(
                    '''SELECT id, date, total_value, type, quantity FROM transactions 
                       WHERE portfolio_id = ? AND date = ? AND ticker = ? AND type = ?
                       AND ABS(total_value - ?) < 0.01 AND ABS(quantity - ?) < 0.00000001
                       AND sub_portfolio_id IS ''' + ('?' if sub_portfolio_id else 'NULL'),
                    (portfolio_id, time, tx_ticker, tx_type, tx_total, tx_qty, sub_portfolio_id) if sub_portfolio_id else (portfolio_id, time, tx_ticker, tx_type, tx_total, tx_qty)
                ).fetchone()

                if existing:
                    tx_data['is_conflict'] = True # Wiersz ma duplikat w bazie
                    potential_conflicts.append({
                        'row_hash': row_hash,
                        'conflict_type': 'database_duplicate',
                        'import_data': tx_data['import_data'],
                        'existing_match': {
                            'id': existing['id'],
                            'date': existing['date'],
                            'amount': existing['total_value'],
                            'type': existing['type'],
                            'quantity': existing['quantity'],
                            'source': 'database'
                        }
                    })

            prepared_transactions.append(tx_data)

        # Jeśli są brakujące symbole, przerywamy (istniejąca logika)
        if missing_symbols:
            return {'success': False, 'missing_symbols': missing_symbols}

        # Jeśli są konflikty i nie zostały potwierdzone, zwracamy ostrzeżenie
        confirmed_list = list(confirmed_hashes or [])
        # Tworzymy słownik do liczenia ile razy dany hash został potwierdzony
        from collections import Counter
        confirmed_counts = Counter(confirmed_list)
        
        # Sprawdzamy czy wszystkie konflikty zostały potwierdzone (tylko jeśli confirmed_hashes jest None)
        unconfirmed_conflicts = [c for c in potential_conflicts if confirmed_hashes is None]
        
        if unconfirmed_conflicts:
            return {
                'success': True, 
                'status': 'warning', 
                'potential_conflicts': potential_conflicts,
                'missing_symbols': []
            }

        # ETAP 2: Faktyczny zapis do bazy
        db.execute('BEGIN')
        try:
            for tx in prepared_transactions:
                # Sprawdzamy czy ta transakcja była konfliktem (flaga is_conflict)
                if tx['is_conflict']:
                    # Jeśli to był konflikt, sprawdzamy czy mamy jeszcze "dostępne" potwierdzenia dla tego hasha
                    if confirmed_counts[tx['hash']] > 0:
                        confirmed_counts[tx['hash']] -= 1
                        # Kontynuujemy do zapisu (użytkownik potwierdził ten konkretny konflikt)
                    else:
                        # Brak potwierdzenia dla tego konkretnego wystąpienia duplikatu - pomijamy
                        continue

                typ_lower = tx['type_raw']
                time = tx['time']
                amount = tx['amount_raw']
                comment = tx['comment']
                ticker = tx['ticker']
                ticker_currency = tx['ticker_currency']
                qty = tx['tx_qty']
                tx_total = tx['tx_total']

                # Target ID for cash updates (parent or child)
                target_portfolio_id = sub_portfolio_id if sub_portfolio_id else portfolio_id

                if typ_lower in {'deposit', 'ike deposit'}:
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                        (tx_total, target_portfolio_id)
                    )
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, 'CASH', 'DEPOSIT', 1, tx_total, tx_total, time, sub_portfolio_id)
                    )
                elif typ_lower == 'free funds interest':
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                        (tx_total, target_portfolio_id)
                    )
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, 'CASH', 'INTEREST', 1, tx_total, tx_total, time, sub_portfolio_id)
                    )
                elif typ_lower == 'withdrawal':
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                        (tx_total, target_portfolio_id)
                    )
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, 'CASH', 'WITHDRAW', 1, tx_total, tx_total, time, sub_portfolio_id)
                    )
                elif typ_lower == 'stock purchase':
                    price = tx_total / qty if qty else 0.0
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?',
                        (tx_total, target_portfolio_id)
                    )
                    holding = cursor.execute(
                        'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS ' + ('?' if sub_portfolio_id else 'NULL'),
                        (portfolio_id, ticker, sub_portfolio_id) if sub_portfolio_id else (portfolio_id, ticker)
                    ).fetchone()
                    if holding:
                        new_qty = holding['quantity'] + qty
                        new_total_cost = holding['total_cost'] + tx_total
                        new_avg_price = new_total_cost / new_qty
                        cursor.execute(
                            '''UPDATE holdings SET quantity = ?, total_cost = ?, average_buy_price = ?, currency = ?, instrument_currency = ?, auto_fx_fees = ? WHERE id = ?''',
                            (new_qty, new_total_cost, new_avg_price, ticker_currency, ticker_currency or holding['instrument_currency'] or holding['currency'] or 'PLN', 1 if ticker_currency != 'PLN' else holding['auto_fx_fees'], holding['id'])
                        )
                    else:
                        cursor.execute(
                            '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost, currency, instrument_currency, auto_fx_fees, sub_portfolio_id)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (portfolio_id, ticker, qty, price, tx_total, ticker_currency, ticker_currency or 'PLN', 1 if ticker_currency != 'PLN' else 0, sub_portfolio_id)
                        )
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, commission, sub_portfolio_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, ticker, 'BUY', qty, price, tx_total, time, 0.0, sub_portfolio_id)
                    )
                elif typ_lower == 'stock sell':
                    price = tx_total / qty if qty else 0.0
                    cursor.execute(
                        'UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?',
                        (amount, target_portfolio_id)
                    )
                    holding = cursor.execute(
                        'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS ' + ('?' if sub_portfolio_id else 'NULL'),
                        (portfolio_id, ticker, sub_portfolio_id) if sub_portfolio_id else (portfolio_id, ticker)
                    ).fetchone()
                    realized_profit = 0.0
                    if holding:
                        realized_profit = tx_total - (holding['average_buy_price'] * qty)
                        new_qty = holding['quantity'] - qty
                        new_total_cost = holding['total_cost'] - (qty * holding['average_buy_price'])
                        if new_qty > 0.000001:
                            cursor.execute(
                                '''UPDATE holdings SET quantity = ?, total_cost = ?, instrument_currency = COALESCE(instrument_currency, currency, 'PLN') WHERE id = ?''',
                                (new_qty, new_total_cost, holding['id'])
                            )
                        else:
                            cursor.execute('DELETE FROM holdings WHERE id = ?', (holding['id'],))
                    cursor.execute(
                        '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, realized_profit, date, commission, sub_portfolio_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, ticker, 'SELL', qty, price, tx_total, realized_profit, time, 0.0, sub_portfolio_id)
                    )

            db.commit()
            return {'success': True, 'missing_symbols': [], 'status': 'success'}
        except Exception:
            db.rollback()
            raise
