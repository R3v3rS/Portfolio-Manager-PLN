import json
import logging
import math
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import pandas as pd

from database import get_db
from portfolio_import_service import PortfolioImportService
from price_service import PriceService
from portfolio_scope import resolve_portfolio_scope
from import_parser import parse_xtb_dataframe
from api.exceptions import ValidationError


logger = logging.getLogger(__name__)


class ImportRowSkipError(Exception):
    pass


class ImportBookingError(Exception):
    def __init__(self, message: str, row_errors: list[str]):
        super().__init__(message)
        self.row_errors = row_errors


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

        if not instrument_currency:
            raise ImportBookingError('Booking failed', [f'{ticker}: nie udało się ustalić waluty instrumentu. Uzupełnij walutę w mapowaniu symbolu.'])
        return instrument_currency

    @staticmethod
    def _resolve_buy_fx_rate(instrument_currency: str, tx_date: str, *, sync_history=True) -> tuple[Optional[float], str]:
        currency = (instrument_currency or 'PLN').upper()
        if currency == 'PLN':
            return 1.0, 'pln_native'

        tx_day = str(tx_date).split(' ')[0].split('T')[0]
        fx_ticker = f'{currency}PLN=X'
        if sync_history:
            PriceService.sync_stock_history(fx_ticker, tx_day)
        db = get_db()
        fx_row = db.execute(
            '''SELECT close_price
               FROM stock_prices
               WHERE ticker = ? AND DATE(date) <= DATE(?)
               ORDER BY DATE(date) DESC
               LIMIT 1''',
            (fx_ticker, tx_day),
        ).fetchone()

        if not fx_row:
            return None, 'missing'

        fx_rate = float(fx_row['close_price'])
        if not math.isfinite(fx_rate) or fx_rate <= 0:
            return None, 'missing'
        return fx_rate, 'historical_close'

    @staticmethod
    def _normalized_import_datetime(value: Any, row_number: int) -> str:
        parsed = pd.to_datetime(value, errors='coerce')
        if pd.isna(parsed):
            raise ValueError(f"Invalid date at row {row_number}: {value}")
        if parsed.hour or parsed.minute or parsed.second or parsed.microsecond:
            return parsed.isoformat(sep=' ', timespec='seconds')
        return parsed.date().isoformat()

    @staticmethod
    def _has_time_component(value: str) -> bool:
        parsed = pd.to_datetime(value, errors='coerce')
        if pd.isna(parsed):
            return False
        return bool(parsed.hour or parsed.minute or parsed.second or parsed.microsecond)

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
    def _transaction_match_counts(
        db,
        portfolio_id: int,
        date_value: str,
        ticker: str,
        tx_type: str,
        total_value: float,
        quantity: float,
        sub_portfolio_id: Optional[int],
        legacy_only: bool = False,
    ) -> dict[str, int]:
        # Duplicate detection is portfolio-wide (across main + sub-portfolios),
        # so users are warned even if an identical transaction was booked in a different scope.
        # If the source row includes time, keep the match time-specific. XTB can emit
        # several identical fills on one day, and collapsing them to DATE causes false duplicates.
        _ = sub_portfolio_id
        legacy_filter = ' AND xtb_operation_id IS NULL' if legacy_only else ''
        if ImportStagingService._has_time_component(date_value):
            exact = db.execute(
                '''SELECT COUNT(*) AS count FROM transactions
                   WHERE portfolio_id = ? AND datetime(date) = datetime(?) AND ticker = ? AND type = ?
                   AND ABS(total_value - ?) < 0.01 AND ABS(quantity - ?) < 0.00000001''' + legacy_filter,
                (portfolio_id, date_value, ticker, tx_type, total_value, quantity),
            ).fetchone()
            legacy_date_only = db.execute(
                '''SELECT COUNT(*) AS count FROM transactions
                   WHERE portfolio_id = ? AND DATE(date) = DATE(?) AND ticker = ? AND type = ?
                   AND instr(date, ' ') = 0 AND instr(date, 'T') = 0
                   AND ABS(total_value - ?) < 0.01 AND ABS(quantity - ?) < 0.00000001''' + legacy_filter,
                (portfolio_id, date_value, ticker, tx_type, total_value, quantity),
            ).fetchone()
            return {
                'exact': int(exact['count'] or 0) if exact else 0,
                'legacy_date_only': int(legacy_date_only['count'] or 0) if legacy_date_only else 0,
            }
        else:
            existing = db.execute(
                '''SELECT COUNT(*) AS count FROM transactions
                   WHERE portfolio_id = ? AND DATE(date) = DATE(?) AND ticker = ? AND type = ?
                   AND ABS(total_value - ?) < 0.01 AND ABS(quantity - ?) < 0.00000001''' + legacy_filter,
                (portfolio_id, date_value, ticker, tx_type, total_value, quantity),
            ).fetchone()
            return {
                'exact': int(existing['count'] or 0) if existing else 0,
                'legacy_date_only': 0,
            }

    @staticmethod
    def _validate_subportfolio(db, parent_portfolio_id: int, sub_portfolio_id: Optional[int]) -> None:
        parent = db.execute('SELECT is_archived, account_type FROM portfolios WHERE id = ?', (parent_portfolio_id,)).fetchone()
        if not parent:
            raise ValueError('Portfolio not found')
        if parent['is_archived'] or parent['account_type'] == 'PPK':
            raise ValueError('Nie można importować do zarchiwizowanego portfela ani PPK.')
        if sub_portfolio_id is None:
            return
        child = db.execute('SELECT id, is_archived FROM portfolios WHERE id = ? AND parent_portfolio_id = ?',
                           (sub_portfolio_id, parent_portfolio_id)).fetchone()
        if not child:
            raise ValueError('Invalid sub-portfolio for this parent')
        if child['is_archived']:
            raise ValueError('Cannot import to an archived sub-portfolio')

    @staticmethod
    def _row_to_dict(row):
        item = dict(row)
        for name in ('quantity', 'price', 'total_value', 'commission'):
            item[name] = float(item[name]) if item.get(name) is not None else None
        details = item.get('conflict_details')
        item['conflict_details'] = json.loads(details) if isinstance(details, str) else details
        return item

    @staticmethod
    def _refresh_conflicts(db, rows):
        """Allocate existing occurrences once; identical stock fills can be legitimate."""
        exact, legacy, seen, inventory, seen_ids = {}, {}, {}, {}, {}
        for row in rows:
            if row['status'] == 'rejected':
                continue
            if row['conflict_type'] == 'missing_symbol':
                continue
            identity = (row.get('source_account'), row.get('source_operation_id'))
            has_identity = all(identity)
            identity_match = db.execute('SELECT * FROM transactions WHERE xtb_account = ? AND xtb_operation_id = ?', identity).fetchone() if has_identity else None
            source_id_row = seen_ids.get(identity) if has_identity else None
            key = (row['date'], row['ticker'], row['type'], round(row['total_value'], 2), round(row['quantity'] or 0, 8))
            match_key = (key, bool(has_identity))
            day_key = (row['date'].split(' ')[0].split('T')[0], *key[1:])
            day_key = (day_key, bool(has_identity))
            if match_key not in exact:
                counts = ImportStagingService._transaction_match_counts(db, row['portfolio_id'], row['date'],
                    row['ticker'], row['type'], row['total_value'], row['quantity'], row['target_sub_portfolio_id'], legacy_only=bool(has_identity))
                exact[match_key] = counts['exact']
                legacy.setdefault(day_key, counts['legacy_date_only'])
            duplicate = False
            if not identity_match and source_id_row is None and exact[match_key] > 0:
                exact[match_key] -= 1
                duplicate = True
            elif not identity_match and source_id_row is None and legacy[day_key] > 0:
                legacy[day_key] -= 1
                duplicate = True
            source = seen.get(row['row_hash'])
            seen.setdefault(row['row_hash'], row['id'])
            if row['status'] == 'booked':
                continue
            conflict, details = None, None
            if has_identity:
                seen_ids.setdefault(identity, row)
            identity_data = source_id_row or (dict(identity_match) if identity_match else None)
            if identity_data and (identity_data['ticker'] != row['ticker'] or identity_data['type'] != row['type'] or
                                  identity_data['date'] != row['date'] or
                                  abs(float(identity_data['total_value']) - float(row['total_value'])) >= 0.01 or
                                  abs(float(identity_data['quantity'] or 0) - float(row['quantity'] or 0)) >= 1e-8):
                conflict, details = 'source_mismatch', {'reason': 'Identyfikator operacji ma inne dane. Sprawdź eksport i zapisany wpis.'}
            elif source_id_row is not None or (source is not None and not has_identity and row['type'] not in {'BUY', 'SELL'}):
                conflict = 'file_internal_duplicate'
                details = {'source_row': source_id_row['id'] if source_id_row else source, 'also_database_duplicate': duplicate or bool(identity_match)}
            elif identity_match or duplicate:
                conflict = 'database_duplicate'
                if identity_match:
                    details = {'matched_by': 'broker_operation_id', 'portfolio_id': identity_match['portfolio_id']}
            scope = (row['ticker'], row['target_sub_portfolio_id'])
            inventory.setdefault(scope, ImportStagingService._fetch_holding_qty(db, row['portfolio_id'], *scope))
            if conflict is None and row['type'] == 'SELL':
                available = inventory[scope]
                required = float(row['quantity'])
                if available + 1e-8 < required:
                    conflict = 'missing_holding' if available <= 1e-8 else 'insufficient_qty'
                    details = {'required_qty': required, 'available_qty': available}
                else:
                    inventory[scope] -= required
            elif conflict is None and row['type'] == 'BUY':
                inventory[scope] += float(row['quantity'])
            row['conflict_type'], row['conflict_details'] = conflict, details
            db.execute('UPDATE import_staging SET conflict_type = ?, conflict_details = ? WHERE id = ?',
                       (conflict, json.dumps(details) if details else None, row['id']))

    @staticmethod
    def create_session(portfolio_id, df, sub_portfolio_id=None, source_file=None):
        db = get_db()
        try:
            portfolio_id, sub_portfolio_id = resolve_portfolio_scope(db, portfolio_id, sub_portfolio_id)
        except ValidationError as error:
            raise ValueError('Invalid sub-portfolio for this parent') from error
        ImportStagingService._validate_subportfolio(db, portfolio_id, sub_portfolio_id)
        if df.attrs.get('cash_operations_xlsx'):
            product = next((column for column in df.columns if str(column).strip().lower() == 'product'), None)
            if product is not None:
                products = {str(value).strip().upper() for value in df[product].dropna() if str(value).strip()}
                account_type = db.execute('SELECT account_type FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()['account_type']
                if len(products) > 1 or any(value in {'IKE', 'IKZE'} and value != account_type for value in products):
                    raise ValueError('Typ rachunku w Cash Operations nie odpowiada wybranemu portfelowi. Wybierz właściwe konto.')
        parsed, unsupported, warnings = parse_xtb_dataframe(df, ImportStagingService._normalized_import_datetime)
        session_id, created_at = str(uuid4()), ImportStagingService._now_iso()
        try:
            db.execute('BEGIN IMMEDIATE')
            ImportStagingService._validate_subportfolio(db, portfolio_id, sub_portfolio_id)
            db.execute('INSERT INTO import_sessions (id, portfolio_id, source_file, input_rows, unsupported_json, warnings_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (session_id, portfolio_id, source_file, len(df), json.dumps(unsupported), json.dumps(warnings), created_at))
            for row in parsed:
                db.execute('''INSERT INTO import_staging
                    (import_session_id, portfolio_id, ticker, type, quantity, price, total_value, date,
                     target_sub_portfolio_id, status, conflict_type, conflict_details, row_hash,
                     source_file, created_at, commission, symbol_input, source_account, source_operation_id, source_row_number, instrument_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (session_id, portfolio_id, row['ticker'], row['type'], row['quantity'], row['price'],
                     row['total_value'], row['date'], sub_portfolio_id, row['status'], row['conflict_type'],
                     json.dumps(row['conflict_details']) if row['conflict_details'] else None,
                     row['row_hash'], source_file, created_at, row['commission'], row['symbol_input'],
                     row.get('source_account'), row.get('source_operation_id'), row.get('source_row_number'), row.get('instrument_name')))
            rows = [dict(r) for r in db.execute('SELECT * FROM import_staging WHERE import_session_id = ? ORDER BY id', (session_id,))]
            ImportStagingService._refresh_conflicts(db, rows)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return ImportStagingService.get_session(session_id)

    @staticmethod
    def get_session(session_id):
        db = get_db()
        rows = [ImportStagingService._row_to_dict(row) for row in db.execute(
            'SELECT * FROM import_staging WHERE import_session_id = ? ORDER BY datetime(date), id', (session_id,))]
        meta = db.execute('SELECT * FROM import_sessions WHERE id = ?', (session_id,)).fetchone()
        if not rows and not meta:
            raise ValueError('Session not found')
        unsupported = json.loads(meta['unsupported_json']) if meta else []
        active = [r for r in rows if r['status'] in {'pending', 'assigned'}]
        return {
            'session_id': session_id, 'portfolio_id': meta['portfolio_id'] if meta else rows[0]['portfolio_id'],
            'source_file': meta['source_file'] if meta else rows[0]['source_file'],
            'created_at': meta['created_at'] if meta else rows[0]['created_at'],
            'closed': bool(meta['closed_at']) if meta else False,
            'rows': rows, 'unsupported_rows': unsupported,
            'warnings': json.loads(meta['warnings_json']) if meta else [],
            'summary': {
                'input_rows': meta['input_rows'] if meta else len(rows), 'total': len(rows),
                'pending': len(active), 'conflicts': sum(r['conflict_type'] is not None for r in active),
                'rejected': sum(r['status'] == 'rejected' for r in rows),
                'booked': sum(r['status'] == 'booked' for r in rows), 'unsupported': len(unsupported),
                'missing_symbols': sorted({r['ticker'] for r in rows if r['conflict_type'] == 'missing_symbol' and r.get('booking_mode') != 'cancelled'}),
            },
        }

    @staticmethod
    def list_sessions(portfolio_id):
        db = get_db()
        root_id, _ = resolve_portfolio_scope(db, portfolio_id)
        ids = db.execute('''SELECT import_session_id AS id, MIN(created_at) AS created_at
            FROM import_staging WHERE portfolio_id = ? GROUP BY import_session_id
            UNION SELECT id, created_at FROM import_sessions WHERE portfolio_id = ?
            ORDER BY created_at DESC''', (root_id, root_id)).fetchall()
        # Legacy sessions have no metadata; they are still recoverable.
        result, seen = [], set()
        for item in ids:
            if item['id'] in seen:
                continue
            seen.add(item['id'])
            session = ImportStagingService.get_session(item['id'])
            if session['closed']:
                continue
            if session['summary']['pending'] or session['summary']['missing_symbols'] or session['summary']['unsupported']:
                result.append({key: session[key] for key in ('session_id', 'source_file', 'created_at', 'summary')})
        return result

    @staticmethod
    def assign_row(session_id, row_id, target_sub_portfolio_id):
        db = get_db()
        try:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM import_staging WHERE id = ? AND import_session_id = ?', (row_id, session_id)).fetchone()
            if not row:
                raise ValueError('Row not found in session')
            if row['status'] in {'booked', 'rejected'}:
                raise ImportRowSkipError('Cannot modify booked or rejected row')
            ImportStagingService._validate_subportfolio(db, row['portfolio_id'], target_sub_portfolio_id)
            db.execute("UPDATE import_staging SET target_sub_portfolio_id = ?, status = 'assigned' WHERE id = ?",
                       (target_sub_portfolio_id, row_id))
            rows = [dict(r) for r in db.execute('SELECT * FROM import_staging WHERE import_session_id = ? ORDER BY datetime(date), id', (session_id,))]
            ImportStagingService._refresh_conflicts(db, rows)
            db.commit()
            return ImportStagingService._row_to_dict(db.execute('SELECT * FROM import_staging WHERE id = ?', (row_id,)).fetchone())
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def assign_all(session_id, target_sub_portfolio_id):
        session = ImportStagingService.get_session(session_id)
        assigned = skipped = 0
        for row in session['rows']:
            if row['status'] not in {'pending', 'assigned'}:
                skipped += 1
                continue
            ImportStagingService.assign_row(session_id, row['id'], target_sub_portfolio_id)
            assigned += 1
        return {'assigned': assigned, 'skipped': skipped}

    @staticmethod
    def reject_row(session_id, row_id):
        db = get_db()
        try:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM import_staging WHERE id = ? AND import_session_id = ?', (row_id, session_id)).fetchone()
            if not row:
                raise ValueError('Row not found in session')
            if row['status'] == 'booked':
                raise ValueError('Cannot modify booked row')
            db.execute("UPDATE import_staging SET status = 'rejected' WHERE id = ?", (row_id,))
            rows = [dict(r) for r in db.execute('SELECT * FROM import_staging WHERE import_session_id = ? ORDER BY datetime(date), id', (session_id,))]
            ImportStagingService._refresh_conflicts(db, rows)
            db.commit()
            return ImportStagingService._row_to_dict(db.execute('SELECT * FROM import_staging WHERE id = ?', (row_id,)).fetchone())
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def refresh_symbols(session_id):
        db = get_db()
        ImportStagingService.get_session(session_id)
        try:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("SELECT * FROM import_staging WHERE import_session_id = ? AND conflict_type = 'missing_symbol' AND COALESCE(booking_mode, '') != 'cancelled'", (session_id,)).fetchall()
            for row in rows:
                mapping = PortfolioImportService.resolve_import_symbol(row['symbol_input'] or row['ticker'])
                if mapping:
                    new_hash = PortfolioImportService._generate_row_hash(row['date'], mapping.ticker, row['total_value'], row['type'], row['quantity'])
                    db.execute("UPDATE import_staging SET ticker = ?, row_hash = ?, status = 'pending', conflict_type = NULL, conflict_details = NULL WHERE id = ?",
                               (mapping.ticker, new_hash, row['id']))
            rows = [dict(r) for r in db.execute('SELECT * FROM import_staging WHERE import_session_id = ? ORDER BY datetime(date), id', (session_id,))]
            ImportStagingService._refresh_conflicts(db, rows)
            db.commit()
        except Exception:
            db.rollback()
            raise
        return ImportStagingService.get_session(session_id)

    @staticmethod
    def _prepare_buy_fields(rows):
        """All provider calls/commits happen before the financial transaction."""
        db = get_db()
        prepared, currencies, earliest, rates = {}, {}, {}, {}
        eligible = [row for row in rows if row['type'] == 'BUY' and row['status'] in {'pending', 'assigned'} and not row['conflict_type']]
        for row in eligible:
            if row['ticker'] not in currencies:
                currencies[row['ticker']] = ImportStagingService._resolve_instrument_currency(db, row['ticker'])
            currency = currencies[row['ticker']]
            day = row['date'].split(' ')[0].split('T')[0]
            earliest[currency] = min(earliest.get(currency, day), day)
        for currency, day in earliest.items():
            if currency != 'PLN':
                PriceService.sync_stock_history(f'{currency}PLN=X', day)
        for row in eligible:
            currency = currencies[row['ticker']]
            key = (currency, row['date'].split(' ')[0].split('T')[0])
            if key not in rates:
                rates[key] = ImportStagingService._resolve_buy_fx_rate(currency, row['date'], sync_history=False)
            fx, source = rates[key]
            if fx is None:
                raise ImportBookingError('Booking failed', [f"row_id={row['id']}: brak historycznego kursu {currency}/PLN dla {row['date']}. Uzupełnij kurs i ponów sesję."])
            prepared[row['id']] = {'instrument_currency': currency, 'fx_rate': fx, 'fx_source': source}
        return prepared

    @staticmethod
    def _book_single_row(row, db, book_tx_only=False):
        portfolio_id, sub_id = row['portfolio_id'], row['target_sub_portfolio_id']
        target = sub_id or portfolio_id
        qty, total, price = float(row['quantity']), float(row['total_value']), float(row['price'])
        tx_type, ticker = row['type'], row['ticker']
        # Unknown is distinct from a confirmed zero fee; cash uses the net exported amount.
        commission = float(row['commission']) if row.get('commission') is not None else None
        profit = 0.0
        if not book_tx_only:
            if tx_type in {'DEPOSIT', 'INTEREST', 'DIVIDEND'}:
                db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (total, target))
            elif tx_type == 'WITHDRAW':
                db.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (total, target))
            elif tx_type == 'BUY':
                fields = row['_buy_fields']
                currency, fx = fields['instrument_currency'], fields['fx_rate']
                holding = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS ?',
                                     (portfolio_id, ticker, sub_id)).fetchone()
                native_cost = (qty * price) / fx
                if holding:
                    # A legacy holding must be repaired explicitly if its native basis is unknown.
                    old_qty, old_cost = float(holding['quantity']), float(holding['total_cost'])
                    old_fx = holding['avg_buy_fx_rate']
                    old_currency = holding['instrument_currency'] or holding['currency']
                    if old_currency and str(old_currency).upper() != currency:
                        raise ValueError('Waluta historycznej pozycji różni się od waluty instrumentu. Uzgodnij pozycję przed importem.')
                    if currency != 'PLN' and (not old_fx or not math.isfinite(float(old_fx)) or float(old_fx) <= 0):
                        raise ValueError('Brak uzgodnionego kursu historycznej pozycji. Uzgodnij pozycję przed importem.')
                    old_native = float(holding['avg_buy_price_native'] or 0) * old_qty
                    if old_native <= 0:
                        if not old_fx or (currency != 'PLN' and holding['instrument_currency'] != currency):
                            raise ValueError('Brak uzgodnionej waluty lub kosztu historycznej pozycji.')
                        old_native = old_cost / float(old_fx)
                    new_qty, new_cost = old_qty + qty, old_cost + total
                    new_native = old_native + native_cost
                    effective_fx = (old_native * float(old_fx or 1) + qty * price) / new_native if new_native else fx
                    db.execute('''UPDATE holdings SET quantity = ?, total_cost = ?, average_buy_price = ?,
                        currency = ?, instrument_currency = ?, avg_buy_price_native = ?, avg_buy_fx_rate = ?,
                        fx_source = ?, auto_fx_fees = ? WHERE id = ?''',
                        (new_qty, new_cost, new_cost/new_qty, currency, currency, new_native/new_qty,
                         effective_fx, 'weighted_historical', int(currency != 'PLN'), holding['id']))
                else:
                    db.execute('''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost,
                        sub_portfolio_id, currency, instrument_currency, avg_buy_fx_rate, avg_buy_price_native, fx_source, auto_fx_fees)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (portfolio_id, ticker, qty, total/qty, total, sub_id, currency, currency, fx,
                         price/fx, fields['fx_source'], int(currency != 'PLN')))
                db.execute('UPDATE portfolios SET current_cash = current_cash - ? WHERE id = ?', (total, target))
            elif tx_type == 'SELL':
                holding = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS ?',
                                     (portfolio_id, ticker, sub_id)).fetchone()
                if not holding or float(holding['quantity']) + 1e-8 < qty:
                    raise ValueError('Sprzedaż przekracza posiadaną liczbę akcji.')
                basis = float(holding['total_cost']) / float(holding['quantity'])
                profit = total - basis * qty
                new_qty = max(float(holding['quantity']) - qty, 0)
                if new_qty > 1e-8:
                    db.execute('UPDATE holdings SET quantity = ?, total_cost = ? WHERE id = ?',
                               (new_qty, new_qty*basis, holding['id']))
                else:
                    db.execute('DELETE FROM holdings WHERE id = ?', (holding['id'],))
                db.execute('UPDATE portfolios SET current_cash = current_cash + ? WHERE id = ?', (total, target))
        inserted = db.execute('''INSERT INTO transactions
            (portfolio_id, sub_portfolio_id, ticker, type, quantity, price, total_value, realized_profit, date, commission, xtb_account, xtb_operation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (portfolio_id, sub_id, ticker, tx_type, qty, price, total, profit, row['date'], commission,
             row.get('source_account'), row.get('source_operation_id') if row.get('source_account') else None))
        return inserted.lastrowid

    @staticmethod
    def book_session(session_id, confirmed_row_ids=None):
        confirmed = set()
        for rid in confirmed_row_ids or []:
            try:
                number = int(rid)
                if isinstance(rid, bool) or number <= 0 or float(rid) != number:
                    raise ValueError()
                confirmed.add(number)
            except (TypeError, ValueError, OverflowError):
                logger.warning(f'Invalid confirmed_row_id ignored: {rid!r}')
        preview = ImportStagingService.get_session(session_id)
        # A refresh can commit market caches, but no balances or imported operations exist yet.
        prepared = ImportStagingService._prepare_buy_fields(preview['rows'])
        db = get_db()
        result = {'booked': 0, 'booked_tx_only': 0, 'skipped_conflicts': 0, 'duplicate_skipped': 0,
                  'rejected': 0, 'errors': []}
        try:
            db.execute('BEGIN IMMEDIATE')
            rows = [dict(r) for r in db.execute('SELECT * FROM import_staging WHERE import_session_id = ? ORDER BY datetime(date), id', (session_id,))]
            # Revalidate within the write lock: another session may have been booked meanwhile.
            for row in rows:
                if row['status'] in {'pending', 'assigned'}:
                    ImportStagingService._validate_subportfolio(db, row['portfolio_id'], row['target_sub_portfolio_id'])
            ImportStagingService._refresh_conflicts(db, rows)
            for row in rows:
                if row['status'] == 'rejected':
                    result['rejected'] += 1
                    continue
                if row['status'] not in {'pending', 'assigned'}:
                    continue
                conflict = row['conflict_type']
                if conflict:
                    if row['id'] not in confirmed:
                        result['skipped_conflicts'] += 1
                        continue
                    if conflict in {'database_duplicate', 'file_internal_duplicate'}:
                        db.execute("UPDATE import_staging SET status = 'rejected', booking_mode = 'duplicate_skipped' WHERE id = ?", (row['id'],))
                        result['duplicate_skipped'] += 1
                        continue
                    if conflict not in {'missing_holding', 'insufficient_qty'}:
                        result['skipped_conflicts'] += 1
                        continue
                history_only = conflict in {'missing_holding', 'insufficient_qty'}
                if row['type'] == 'BUY' and not history_only:
                    if row['id'] not in prepared:
                        # A row changed while FX was loaded. Never call providers inside this transaction.
                        raise ImportBookingError('Booking failed', [f"row_id={row['id']}: zmienił się zakres importu. Odśwież sesję i ponów."])
                    row['_buy_fields'] = prepared[row['id']]
                try:
                    tx_id = ImportStagingService._book_single_row(row, db, book_tx_only=history_only)
                except Exception as exc:
                    raise ImportBookingError('Booking failed', [f"row_id={row['id']}: {exc}"]) from exc
                db.execute("UPDATE import_staging SET status = 'booked', booked_at = ?, booking_mode = ?, booked_transaction_id = ? WHERE id = ?",
                           (ImportStagingService._now_iso(), 'history_only' if history_only else 'normal', tx_id, row['id']))
                result['booked_tx_only' if history_only else 'booked'] += 1
            for portfolio_id in {r['portfolio_id'] for r in rows} | {r['target_sub_portfolio_id'] for r in rows if r['target_sub_portfolio_id']}:
                db.execute('DELETE FROM portfolio_history_cache WHERE portfolio_id = ?', (portfolio_id,))
                if db.execute("SELECT 1 FROM sqlite_master WHERE name = 'analytics_cache'").fetchone():
                    db.execute('DELETE FROM analytics_cache WHERE portfolio_id = ?', (portfolio_id,))
            db.commit()
        except Exception:
            db.rollback()
            raise
        result['session'] = ImportStagingService.get_session(session_id)
        result['remaining'] = result['session']['summary']['pending']
        return result

    @staticmethod
    def delete_session(session_id):
        # Cancellation preserves the audit trail and never deletes booked transactions.
        db = get_db()
        ImportStagingService.get_session(session_id)
        try:
            db.execute('BEGIN IMMEDIATE')
            deleted = db.execute("SELECT COUNT(*) FROM import_staging WHERE import_session_id = ? AND status IN ('pending', 'assigned')", (session_id,)).fetchone()[0]
            db.execute("UPDATE import_staging SET status = 'rejected', booking_mode = 'cancelled' WHERE import_session_id = ? AND status != 'booked'", (session_id,))
            db.execute('UPDATE import_sessions SET closed_at = ? WHERE id = ?', (ImportStagingService._now_iso(), session_id))
            db.commit()
            return {'deleted': deleted}
        except Exception:
            db.rollback()
            raise
