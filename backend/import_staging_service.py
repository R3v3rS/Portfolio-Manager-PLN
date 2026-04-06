import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import pandas as pd

from database import get_db
from portfolio_import_service import PortfolioImportService
from price_service import PriceService


logger = logging.getLogger(__name__)


class ImportRowSkipError(Exception):
    pass


class ImportStagingService:
    @staticmethod
    def _resolve_instrument_currency(db, ticker: str) -> str:
        instrument_currency = None
        mapping = db.execute('SELECT currency FROM symbol_mappings WHERE ticker = ?', (ticker,)).fetchone()
        if mapping and mapping['currency']:
            instrument_currency = str(mapping['currency']).upper()

        if not instrument_currency:
            meta = PriceService.fetch_metadata(ticker)
            instrument_currency = (meta.get('currency') if meta else None)
            instrument_currency = str(instrument_currency).upper() if instrument_currency else None

        return instrument_currency or 'PLN'

    @staticmethod
    def _resolve_buy_fx_rate(instrument_currency: str, tx_date: str) -> tuple[Optional[float], str]:
        currency = (instrument_currency or 'PLN').upper()
        if currency == 'PLN':
            return 1.0, 'pln_native'

        fx_ticker = f'{currency}PLN=X'
        PriceService.sync_stock_history(fx_ticker, tx_date)
        db = get_db()
        fx_row = db.execute(
            '''SELECT close_price
               FROM stock_prices
               WHERE ticker = ? AND DATE(date) <= DATE(?)
               ORDER BY DATE(date) DESC
               LIMIT 1''',
            (fx_ticker, tx_date),
        ).fetchone()

        if not fx_row:
            return None, 'missing'

        fx_rate = float(fx_row['close_price'])
        if fx_rate <= 0:
            return None, 'missing'
        return fx_rate, 'historical_close'

    @staticmethod
    def _iso_date(value: Any, row_number: int) -> str:
        parsed = pd.to_datetime(value, errors='coerce')
        if pd.isna(parsed):
            raise ValueError(f"Invalid date at row {row_number}: {value}")
        return parsed.date().isoformat()

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat(timespec='seconds')

    @staticmethod
    def _fetch_holding_qty(db, portfolio_id: int, ticker: str, sub_portfolio_id: Optional[int]) -> float:
        query = (
            'SELECT quantity FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS '
            + ('?' if sub_portfolio_id else 'NULL')
        )
        params = (portfolio_id, ticker, sub_portfolio_id) if sub_portfolio_id else (portfolio_id, ticker)
        row = db.execute(query, params).fetchone()
        return float(row['quantity']) if row else 0.0

    @staticmethod
    def _update_staging_conflict(db, row_id: int, conflict_type: str, conflict_details: dict[str, Any]) -> None:
        db.execute(
            '''UPDATE import_staging
               SET conflict_type = ?, conflict_details = ?
               WHERE id = ?''',
            (conflict_type, json.dumps(conflict_details), row_id),
        )

    @staticmethod
    def _transaction_exists(
        db,
        portfolio_id: int,
        date_value: str,
        ticker: str,
        tx_type: str,
        total_value: float,
        quantity: float,
        sub_portfolio_id: Optional[int],
    ) -> bool:
        # Duplicate detection is portfolio-wide (across main + sub-portfolios),
        # so users are warned even if an identical transaction was booked in a different scope.
        _ = sub_portfolio_id
        existing = db.execute(
            '''SELECT id FROM transactions
               WHERE portfolio_id = ? AND DATE(date) = DATE(?) AND ticker = ? AND type = ?
               AND ABS(total_value - ?) < 0.01 AND ABS(quantity - ?) < 0.00000001''',
            (portfolio_id, date_value, ticker, tx_type, total_value, quantity),
        ).fetchone()
        return existing is not None

    @staticmethod
    def _validate_subportfolio(db, parent_portfolio_id: int, sub_portfolio_id: int) -> None:
        child = db.execute(
            'SELECT id, is_archived FROM portfolios WHERE id = ? AND parent_portfolio_id = ?',
            (sub_portfolio_id, parent_portfolio_id),
        ).fetchone()
        if not child:
            raise ValueError('Invalid sub-portfolio for this parent')
        if child['is_archived']:
            raise ValueError('Cannot assign to an archived sub-portfolio')

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        details = row['conflict_details']
        return {
            'id': row['id'],
            'ticker': row['ticker'],
            'type': row['type'],
            'quantity': float(row['quantity']) if row['quantity'] is not None else None,
            'total_value': float(row['total_value']),
            'date': row['date'],
            'status': row['status'],
            'conflict_type': row['conflict_type'],
            'conflict_details': json.loads(details) if details else None,
            'row_hash': row['row_hash'],
            'target_sub_portfolio_id': row['target_sub_portfolio_id'],
        }

    @staticmethod
    def create_session(
        portfolio_id: int,
        df: pd.DataFrame,
        sub_portfolio_id: Optional[int] = None,
        source_file: Optional[str] = None,
    ) -> dict[str, Any]:
        db = get_db()
        session_id = str(uuid4())
        created_at = ImportStagingService._now_iso()
        internal_hashes: dict[str, int] = {}
        rows_payload: list[dict[str, Any]] = []
        missing_symbols: list[str] = []
        simulated_holdings: dict[tuple[str, Optional[int]], float] = {}

        try:
            db.execute('BEGIN')
            if sub_portfolio_id:
                ImportStagingService._validate_subportfolio(db, portfolio_id, sub_portfolio_id)

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

            for idx, row in df.sort_values(time_column).iterrows():
                row_number = idx + 1
                typ_lower = str(row[type_column]).strip().lower()
                tx_type = ''
                tx_qty = 1.0
                tx_ticker = 'CASH'
                conflict_type = None
                conflict_details = None
                status = 'pending'

                amount = PortfolioImportService._try_parse_float(row[amount_column])
                if amount is None:
                    raise ValueError(f"Invalid numeric value in column '{amount_column}' at row {row_number}: {row[amount_column]}")
                tx_total = abs(amount)
                date_value = ImportStagingService._iso_date(row[time_column], row_number)

                comment = ''
                if comment_column is not None and not pd.isna(row[comment_column]):
                    comment = str(row[comment_column])

                if typ_lower in {'deposit', 'ike deposit'}:
                    tx_type = 'DEPOSIT'
                elif typ_lower == 'free funds interest':
                    tx_type = 'INTEREST'
                elif typ_lower == 'withdrawal':
                    tx_type = 'WITHDRAW'
                elif typ_lower == 'stock purchase':
                    tx_type = 'BUY'
                    tx_qty = PortfolioImportService._parse_xtb_quantity(comment, row_number)
                elif typ_lower == 'stock sell':
                    tx_type = 'SELL'
                    tx_qty = PortfolioImportService._parse_xtb_quantity(comment, row_number)
                else:
                    continue

                if tx_type in {'BUY', 'SELL'}:
                    symbol_input = ''
                    if symbol_column is not None:
                        symbol_value = row[symbol_column]
                        symbol_input = '' if pd.isna(symbol_value) else str(symbol_value)
                    elif instrument_column is not None:
                        instrument_value = row[instrument_column]
                        symbol_input = '' if pd.isna(instrument_value) else str(instrument_value)

                    mapping = PortfolioImportService.resolve_symbol_mapping(symbol_input)
                    if not mapping:
                        normalized_symbol = symbol_input.strip().upper() or 'UNKNOWN'
                        tx_ticker = normalized_symbol
                        status = 'rejected'
                        conflict_type = 'missing_symbol'
                        conflict_details = {'symbol_input': normalized_symbol}
                        if normalized_symbol not in missing_symbols:
                            missing_symbols.append(normalized_symbol)
                    else:
                        tx_ticker = mapping.ticker

                row_hash = PortfolioImportService._generate_row_hash(date_value, tx_ticker, tx_total, tx_type, tx_qty)

                if conflict_type is None:
                    file_duplicate_source_row = None
                    if row_hash in internal_hashes:
                        file_duplicate_source_row = internal_hashes[row_hash]
                    else:
                        internal_hashes[row_hash] = row_number

                    is_database_duplicate = ImportStagingService._transaction_exists(
                        db,
                        portfolio_id,
                        date_value,
                        tx_ticker,
                        tx_type,
                        tx_total,
                        tx_qty,
                        sub_portfolio_id,
                    )

                    if file_duplicate_source_row is not None and is_database_duplicate:
                        conflict_type = 'file_internal_duplicate'
                        conflict_details = {
                            'source_row': file_duplicate_source_row,
                            'also_database_duplicate': True,
                            'conflict_types': ['file_internal_duplicate', 'database_duplicate'],
                        }
                    elif file_duplicate_source_row is not None:
                        conflict_type = 'file_internal_duplicate'
                        conflict_details = {'source_row': file_duplicate_source_row}
                    elif is_database_duplicate:
                        conflict_type = 'database_duplicate'

                    holding_key = (tx_ticker, sub_portfolio_id)
                    if holding_key not in simulated_holdings:
                        simulated_holdings[holding_key] = ImportStagingService._fetch_holding_qty(
                            db, portfolio_id, tx_ticker, sub_portfolio_id
                        )

                    if conflict_type is None and tx_type == 'SELL':
                        available_qty = simulated_holdings[holding_key]
                        if available_qty <= 0:
                            conflict_type = 'missing_holding'
                            conflict_details = {'required_qty': tx_qty, 'available_qty': available_qty}
                        elif tx_qty > available_qty:
                            conflict_type = 'insufficient_qty'
                            conflict_details = {'required_qty': tx_qty, 'available_qty': available_qty}
                        else:
                            simulated_holdings[holding_key] = available_qty - tx_qty
                    elif conflict_type is None and tx_type == 'BUY':
                        simulated_holdings[holding_key] = simulated_holdings[holding_key] + tx_qty

                if conflict_type is not None:
                    logger.warning(
                        'import_staging_conflict session_id=%s portfolio_id=%s ticker=%s row_hash=%s conflict_type=%s',
                        session_id,
                        portfolio_id,
                        tx_ticker,
                        row_hash,
                        conflict_type,
                    )

                inserted = db.execute(
                    '''INSERT INTO import_staging
                       (import_session_id, portfolio_id, ticker, type, quantity, price, total_value, date,
                        target_sub_portfolio_id, status, conflict_type, conflict_details, row_hash, source_file, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        session_id,
                        portfolio_id,
                        tx_ticker,
                        tx_type,
                        tx_qty,
                        (tx_total / tx_qty) if tx_qty else 0.0,
                        tx_total,
                        date_value,
                        sub_portfolio_id,
                        status,
                        conflict_type,
                        json.dumps(conflict_details) if conflict_details else None,
                        row_hash,
                        source_file,
                        created_at,
                    ),
                )
                rows_payload.append(
                    {
                        'id': inserted.lastrowid,
                        'ticker': tx_ticker,
                        'type': tx_type,
                        'quantity': tx_qty,
                        'total_value': tx_total,
                        'date': date_value,
                        'status': status,
                        'conflict_type': conflict_type,
                        'conflict_details': conflict_details,
                        'row_hash': row_hash,
                    }
                )

            db.commit()
        except Exception:
            db.rollback()
            raise

        conflicts = sum(1 for r in rows_payload if r['conflict_type'] is not None)
        rejected = sum(1 for r in rows_payload if r['status'] == 'rejected')
        pending = sum(1 for r in rows_payload if r['status'] == 'pending')
        return {
            'session_id': session_id,
            'portfolio_id': portfolio_id,
            'rows': rows_payload,
            'summary': {
                'total': len(rows_payload),
                'pending': pending,
                'conflicts': conflicts,
                'rejected': rejected,
                'missing_symbols': missing_symbols,
            },
        }

    @staticmethod
    def get_session(session_id: str) -> dict[str, Any]:
        db = get_db()
        session_rows = db.execute(
            '''SELECT * FROM import_staging
               WHERE import_session_id = ?
               ORDER BY id''',
            (session_id,),
        ).fetchall()
        if not session_rows:
            raise ValueError('Session not found')

        portfolio_id = session_rows[0]['portfolio_id']
        rows = [ImportStagingService._row_to_dict(row) for row in session_rows]
        return {
            'session_id': session_id,
            'portfolio_id': portfolio_id,
            'rows': rows,
            'summary': {
                'total': len(rows),
                'pending': sum(1 for row in rows if row['status'] == 'pending'),
                'conflicts': sum(1 for row in rows if row['conflict_type'] is not None),
                'rejected': sum(1 for row in rows if row['status'] == 'rejected'),
                'missing_symbols': sorted({
                    row['ticker'] for row in rows if row['conflict_type'] == 'missing_symbol'
                }),
            },
        }

    @staticmethod
    def assign_row(session_id: str, row_id: int, target_sub_portfolio_id: int) -> dict[str, Any]:
        db = get_db()
        try:
            db.execute('BEGIN')
            row = db.execute(
                'SELECT * FROM import_staging WHERE id = ? AND import_session_id = ?',
                (row_id, session_id),
            ).fetchone()
            if not row:
                raise ValueError('Row not found in session')
            if row['status'] == 'booked':
                raise ImportRowSkipError('Cannot modify booked row')

            ImportStagingService._validate_subportfolio(db, row['portfolio_id'], target_sub_portfolio_id)

            conflict_type = row['conflict_type']
            conflict_details = row['conflict_details']
            status = 'assigned'

            if row['type'] == 'SELL' and conflict_type in {'missing_holding', 'insufficient_qty'}:
                available_qty = ImportStagingService._fetch_holding_qty(
                    db,
                    row['portfolio_id'],
                    row['ticker'],
                    target_sub_portfolio_id,
                )
                required_qty = float(row['quantity'] or 0.0)

                if available_qty <= 0:
                    conflict_type = 'missing_holding'
                    conflict_details = json.dumps({'required_qty': required_qty, 'available_qty': 0})
                elif required_qty > available_qty:
                    conflict_type = 'insufficient_qty'
                    conflict_details = json.dumps({'required_qty': required_qty, 'available_qty': available_qty})
                else:
                    conflict_type = None
                    conflict_details = None

            db.execute(
                '''UPDATE import_staging
                   SET target_sub_portfolio_id = ?, status = ?, conflict_type = ?, conflict_details = ?
                   WHERE id = ? AND import_session_id = ?''',
                (
                    target_sub_portfolio_id,
                    status,
                    conflict_type,
                    conflict_details,
                    row_id,
                    session_id,
                ),
            )
            updated = db.execute('SELECT * FROM import_staging WHERE id = ?', (row_id,)).fetchone()
            db.commit()
            return ImportStagingService._row_to_dict(updated)
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def assign_all(session_id: str, target_sub_portfolio_id: int) -> dict[str, int]:
        db = get_db()
        session = db.execute(
            'SELECT 1 FROM import_staging WHERE import_session_id = ? LIMIT 1',
            (session_id,),
        ).fetchone()
        if not session:
            raise ValueError('Session not found')

        rows = db.execute(
            '''SELECT id FROM import_staging
               WHERE import_session_id = ? AND status IN ('pending', 'assigned', 'booked')''',
            (session_id,),
        ).fetchall()
        assigned = 0
        skipped = 0
        for row in rows:
            try:
                ImportStagingService.assign_row(session_id, row['id'], target_sub_portfolio_id)
                assigned += 1
            except ImportRowSkipError:
                skipped += 1
        return {'assigned': assigned, 'skipped': skipped}

    @staticmethod
    def reject_row(session_id: str, row_id: int) -> dict[str, Any]:
        db = get_db()
        try:
            db.execute('BEGIN')
            row = db.execute(
                'SELECT * FROM import_staging WHERE id = ? AND import_session_id = ?',
                (row_id, session_id),
            ).fetchone()
            if not row:
                raise ValueError('Row not found in session')
            if row['status'] == 'booked':
                raise ValueError('Cannot modify booked row')

            db.execute(
                '''UPDATE import_staging
                   SET status = 'rejected'
                   WHERE id = ? AND import_session_id = ?''',
                (row_id, session_id),
            )
            updated = db.execute('SELECT * FROM import_staging WHERE id = ?', (row_id,)).fetchone()
            db.commit()
            return ImportStagingService._row_to_dict(updated)
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _book_single_row(row, db, book_tx_only: bool = False) -> None:
        cursor = db.cursor()
        portfolio_id = row['portfolio_id']
        sub_portfolio_id = row['target_sub_portfolio_id']
        target_portfolio_id = sub_portfolio_id if sub_portfolio_id else portfolio_id
        tx_type = row['type']
        qty = float(row['quantity'] or 0.0)
        total_value = float(row['total_value'] or 0.0)
        price = float(row['price'] or 0.0)
        date_value = row['date']
        ticker = row['ticker']

        if tx_type == 'DEPOSIT':
            if not book_tx_only:
                cursor.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (total_value, target_portfolio_id))
            cursor.execute(
                '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id)
                   VALUES (?, 'CASH', 'DEPOSIT', 1, ?, ?, ?, ?)''',
                (portfolio_id, total_value, total_value, date_value, sub_portfolio_id),
            )
        elif tx_type == 'WITHDRAW':
            if not book_tx_only:
                cursor.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (total_value, target_portfolio_id))
            cursor.execute(
                '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id)
                   VALUES (?, 'CASH', 'WITHDRAW', 1, ?, ?, ?, ?)''',
                (portfolio_id, total_value, total_value, date_value, sub_portfolio_id),
            )
        elif tx_type == 'INTEREST':
            if not book_tx_only:
                cursor.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (total_value, target_portfolio_id))
            cursor.execute(
                '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id)
                   VALUES (?, 'CASH', 'INTEREST', 1, ?, ?, ?, ?)''',
                (portfolio_id, total_value, total_value, date_value, sub_portfolio_id),
            )
        elif tx_type == 'BUY':
            cursor.execute(
                '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date, commission, sub_portfolio_id)
                   VALUES (?, ?, 'BUY', ?, ?, ?, ?, 0.0, ?)''',
                (portfolio_id, ticker, qty, price, total_value, date_value, sub_portfolio_id),
            )
            if book_tx_only:
                return
            cursor.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (total_value, target_portfolio_id))
            holding = cursor.execute(
                'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS ' + ('?' if sub_portfolio_id else 'NULL'),
                (portfolio_id, ticker, sub_portfolio_id) if sub_portfolio_id else (portfolio_id, ticker),
            ).fetchone()
            if holding:
                new_qty = float(holding['quantity']) + qty
                new_total_cost = float(holding['total_cost']) + total_value
                new_avg = new_total_cost / new_qty if new_qty else 0.0
                cursor.execute(
                    'UPDATE holdings SET quantity = ?, total_cost = ?, average_buy_price = ? WHERE id = ?',
                    (new_qty, new_total_cost, new_avg, holding['id']),
                )
            else:
                instrument_currency = ImportStagingService._resolve_instrument_currency(db, ticker)
                avg_buy_fx_rate, fx_source = ImportStagingService._resolve_buy_fx_rate(
                    instrument_currency,
                    date_value,
                )
                cursor.execute(
                    '''INSERT INTO holdings
                       (portfolio_id, ticker, quantity, average_buy_price, total_cost, sub_portfolio_id,
                        instrument_currency, avg_buy_fx_rate, avg_buy_price_native, fx_source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        portfolio_id,
                        ticker,
                        qty,
                        price,
                        total_value,
                        sub_portfolio_id,
                        instrument_currency,
                        avg_buy_fx_rate,
                        price if avg_buy_fx_rate in (None, 0) else (price / avg_buy_fx_rate),
                        fx_source,
                    ),
                )
        elif tx_type == 'SELL':
            realized_profit = 0.0
            if not book_tx_only:
                cursor.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (total_value, target_portfolio_id))
                holding = cursor.execute(
                    'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS ' + ('?' if sub_portfolio_id else 'NULL'),
                    (portfolio_id, ticker, sub_portfolio_id) if sub_portfolio_id else (portfolio_id, ticker),
                ).fetchone()
                if holding:
                    avg_price = float(holding['average_buy_price'] or 0.0)
                    realized_profit = total_value - (avg_price * qty)
                    new_qty = float(holding['quantity']) - qty
                    new_total_cost = float(holding['total_cost']) - (qty * avg_price)
                    if new_qty > 0.000001:
                        cursor.execute(
                            'UPDATE holdings SET quantity = ?, total_cost = ? WHERE id = ?',
                            (new_qty, new_total_cost, holding['id']),
                        )
                    else:
                        cursor.execute('DELETE FROM holdings WHERE id = ?', (holding['id'],))
            cursor.execute(
                '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, realized_profit, date, commission, sub_portfolio_id)
                   VALUES (?, ?, 'SELL', ?, ?, ?, ?, ?, 0.0, ?)''',
                (portfolio_id, ticker, qty, price, total_value, realized_profit, date_value, sub_portfolio_id),
            )

    @staticmethod
    def book_session(session_id: str, confirmed_row_ids: Optional[list[int]] = None) -> dict[str, Any]:
        db = get_db()
        confirmed = set()
        for rid in (confirmed_row_ids or []):
            try:
                confirmed.add(int(rid))
            except (TypeError, ValueError):
                logger.warning(f"Invalid confirmed_row_id ignored: {rid!r}")
        result = {
            'booked': 0,
            'booked_tx_only': 0,
            'skipped_conflicts': 0,
            'rejected': 0,
            'errors': [],
        }

        try:
            db.execute('BEGIN')
            rows = db.execute(
                'SELECT * FROM import_staging WHERE import_session_id = ? ORDER BY id',
                (session_id,),
            ).fetchall()
            if not rows:
                raise ValueError('Session not found')

            for row in rows:
                if row['status'] == 'rejected':
                    result['rejected'] += 1
                    continue
                if row['status'] not in {'pending', 'assigned'}:
                    continue

                book_tx_only = False
                if row['conflict_type'] is not None:
                    if row['id'] in confirmed:
                        # Only inventory conflicts are book_tx_only.
                        # Duplicate conflicts should behave like regular confirmed import
                        # (same as legacy direct CSV flow).
                        if row['conflict_type'] in {'missing_holding', 'insufficient_qty'}:
                            book_tx_only = True
                    else:
                        result['skipped_conflicts'] += 1
                        continue

                if row['type'] == 'SELL' and not book_tx_only:
                    available_qty = ImportStagingService._fetch_holding_qty(
                        db,
                        row['portfolio_id'],
                        row['ticker'],
                        row['target_sub_portfolio_id'],
                    )
                    needed_qty = float(row['quantity'] or 0.0)
                    if available_qty <= 0:
                        ImportStagingService._update_staging_conflict(
                            db,
                            row['id'],
                            'missing_holding',
                            {'required_qty': needed_qty, 'available_qty': available_qty},
                        )
                        result['skipped_conflicts'] += 1
                        continue
                    if needed_qty > available_qty:
                        ImportStagingService._update_staging_conflict(
                            db,
                            row['id'],
                            'insufficient_qty',
                            {'required_qty': needed_qty, 'available_qty': available_qty},
                        )
                        result['skipped_conflicts'] += 1
                        continue

                try:
                    ImportStagingService._book_single_row(row, db, book_tx_only=book_tx_only)
                    db.execute(
                        '''UPDATE import_staging
                           SET status = 'booked', booked_at = ?
                           WHERE id = ?''',
                        (ImportStagingService._now_iso(), row['id']),
                    )
                    if book_tx_only:
                        result['booked_tx_only'] += 1
                    else:
                        result['booked'] += 1
                except Exception as exc:
                    result['errors'].append(f"row_id={row['id']}: {exc}")

            if result['errors']:
                raise ValueError('Errors while booking rows')

            db.commit()
            return result
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def delete_session(session_id: str) -> dict[str, int]:
        db = get_db()
        try:
            db.execute('BEGIN')
            deleted = db.execute(
                "DELETE FROM import_staging WHERE import_session_id = ? AND status IN ('pending', 'assigned')",
                (session_id,),
            ).rowcount
            db.commit()
            return {'deleted': deleted}
        except Exception:
            db.rollback()
            raise
