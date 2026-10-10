from database import get_db
from portfolio_core_service import PortfolioCoreService, SymbolMapping
from typing import Optional, Any
from difflib import get_close_matches
import pandas as pd
import re
import hashlib
import logging
import math


logger = logging.getLogger(__name__)


class PortfolioImportService(PortfolioCoreService):
    @staticmethod
    def _assert_holding_consistency(cursor, holding_id: Optional[int]) -> None:
        if not holding_id:
            return
        row = cursor.execute(
            'SELECT quantity, total_cost, average_buy_price FROM holdings WHERE id = ?',
            (holding_id,),
        ).fetchone()
        if not row:
            return
        quantity = float(row['quantity'] or 0.0)
        total_cost = float(row['total_cost'] or 0.0)
        average_buy_price = float(row['average_buy_price'] or 0.0)
        assert quantity >= -0.000001
        assert total_cost >= -0.000001
        if quantity <= 0:
            return
        assert average_buy_price > 0
        recomputed_avg = total_cost / quantity
        assert abs(recomputed_avg - average_buy_price) < 0.001

    @staticmethod
    def _try_parse_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() in {'nan', 'none', 'null'}:
            return None
        normalized = text.replace('\u00a0', '').replace(' ', '').replace(',', '.')
        try:
            parsed = float(normalized)
            return parsed if math.isfinite(parsed) else None
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
    def _parse_xtb_quantity(comment: str, row_number: int) -> float:
        normalized_comment = str(comment or '').strip()
        if not normalized_comment:
            raise ValueError(f"Could not parse quantity from empty comment at row {row_number}")

        qty_match = re.search(r'@\s*[\d\.,]+\s*$', normalized_comment)
        prefix = normalized_comment[:qty_match.start()] if qty_match else normalized_comment
        prefix = re.sub(r'\b(?:OPEN|CLOSE)\b', ' ', prefix, flags=re.IGNORECASE)
        prefix = re.sub(r'\b(?:BUY|SELL)\b', ' ', prefix, flags=re.IGNORECASE)

        fraction_match = re.search(r'(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)', prefix)
        if fraction_match:
            qty_text = fraction_match.group(1)
        else:
            number_matches = re.findall(r'\d+(?:[.,]\d+)?', prefix)
            if not number_matches:
                raise ValueError(f"Could not parse quantity from comment at row {row_number}: {comment}")
            qty_text = number_matches[-1]

        qty = PortfolioImportService._try_parse_float(qty_text)
        if qty is None:
            raise ValueError(f"Invalid quantity value in comment at row {row_number}: {comment}")
        if qty <= 0:
            raise ValueError(f"Quantity must be greater than 0 at row {row_number}: {qty}")
        return qty

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
    def resolve_import_symbol(symbol_input: str) -> Optional[SymbolMapping]:
        """Import uses exact identities, never a fuzzy name match."""
        symbol = PortfolioImportService._normalize_symbol_input(symbol_input)
        if not symbol:
            return None
        rows = get_db().execute('SELECT id, symbol_input, ticker, currency, created_at FROM symbol_mappings').fetchall()
        aliases = [row for row in rows if PortfolioImportService._normalize_symbol_input(row['symbol_input']) == symbol]
        # Convert only a known Warsaw instrument, not every arbitrary .PL symbol.
        candidate = str(symbol_input).strip().upper()
        if candidate.endswith('.PL'):
            candidate = candidate[:-3] + '.WA'
        matches = aliases or [row for row in rows if str(row['ticker']).strip().upper() == candidate]
        if not matches or len({(row['ticker'], row['currency']) for row in matches}) != 1:
            return None
        row = matches[0]
        return SymbolMapping(id=row['id'], symbol_input=row['symbol_input'], ticker=row['ticker'],
                             currency=row['currency'], created_at=row['created_at'])

    @staticmethod
    def import_xtb_csv(portfolio_id: int, df: pd.DataFrame, confirmed_hashes=None, sub_portfolio_id=None):
        # Both entry points use the same validation and atomic booking engine.
        from import_staging_service import ImportStagingService
        session = ImportStagingService.create_session(portfolio_id, df, sub_portfolio_id, source_file='Import bezpośredni')
        if session['summary']['missing_symbols']:
            return {'success': False, 'missing_symbols': session['summary']['missing_symbols'], 'session': session}
        confirmed_hashes = set(confirmed_hashes or [])
        conflicts = [row for row in session['rows'] if row['conflict_type']]
        if session['unsupported_rows'] or any(row['row_hash'] not in confirmed_hashes for row in conflicts):
            return {'success': True, 'status': 'warning', 'session': session, 'missing_symbols': [],
                    'potential_conflicts': [{
                        'row_hash': row['row_hash'], 'conflict_type': row['conflict_type'],
                        'import_data': {'date': row['date'], 'ticker': row['ticker'], 'amount': row['total_value'],
                                        'type': row['type'], 'quantity': row['quantity']},
                        'existing_match': {'id': None, 'date': row['date'], 'amount': row['total_value'],
                                           'type': row['type'], 'quantity': row['quantity'], 'source': 'database'},
                    } for row in conflicts if row['conflict_type'] in {'database_duplicate', 'file_internal_duplicate'}]}
        if any(row['conflict_type'] not in {'database_duplicate', 'file_internal_duplicate'} for row in conflicts):
            return {'success': True, 'status': 'warning', 'session': session, 'missing_symbols': []}
        result = ImportStagingService.book_session(session['session_id'], [row['id'] for row in conflicts])
        return {'success': True, 'status': 'warning' if result['remaining'] else 'success',
                'missing_symbols': [], **result}
