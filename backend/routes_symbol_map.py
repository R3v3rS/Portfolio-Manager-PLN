from flask import Blueprint

from api.exceptions import ApiError, NotFoundError, ValidationError
from api.response import SymbolMappingDTO, success_response
from database import get_db
from routes_portfolio_base import require_json_body

symbol_map_bp = Blueprint('symbol_map', __name__)


def serialize_symbol_mapping(row) -> SymbolMappingDTO:
    return {
        'id': row['id'],
        'symbol_input': row['symbol_input'],
        'ticker': row['ticker'],
        'currency': row['currency'],
        'created_at': str(row['created_at']) if row['created_at'] else None,
    }


def normalize_upper_string(value) -> str:
    return str(value).strip().upper()


@symbol_map_bp.route('', methods=['GET'], strict_slashes=False)
def list_symbol_mappings():
    db = get_db()
    rows = db.execute(
        '''SELECT id, symbol_input, ticker, currency, created_at
           FROM symbol_mappings
           ORDER BY symbol_input ASC'''
    ).fetchall()
    return success_response([serialize_symbol_mapping(row) for row in rows])


@symbol_map_bp.route('', methods=['POST'], strict_slashes=False)
def create_symbol_mapping():
    payload = require_json_body()
    symbol_input = normalize_upper_string(payload.get('symbol_input', ''))
    ticker = normalize_upper_string(payload.get('ticker', ''))
    currency_raw = payload.get('currency')
    currency = normalize_upper_string(currency_raw) if currency_raw is not None else None

    if not symbol_input:
        raise ValidationError('symbol_input is required', details={'field': 'symbol_input'})
    if not ticker:
        raise ValidationError('ticker is required', details={'field': 'ticker'})

    db = get_db()

    existing = db.execute(
        'SELECT id FROM symbol_mappings WHERE symbol_input = ?',
        (symbol_input,)
    ).fetchone()
    if existing:
        raise ApiError(
            'symbol_mapping_conflict',
            f'Mapping for {symbol_input} already exists',
            details={'field': 'symbol_input', 'symbol_input': symbol_input},
            status=409,
        )

    cursor = db.execute(
        '''INSERT INTO symbol_mappings (symbol_input, ticker, currency)
           VALUES (?, ?, ?)''',
        (symbol_input, ticker, currency)
    )
    db.commit()

    row = db.execute(
        '''SELECT id, symbol_input, ticker, currency, created_at
           FROM symbol_mappings
           WHERE id = ?''',
        (cursor.lastrowid,)
    ).fetchone()

    return success_response(serialize_symbol_mapping(row), status=201)


@symbol_map_bp.route('/<int:mapping_id>', methods=['PUT'], strict_slashes=False)
def update_symbol_mapping(mapping_id: int):
    payload = require_json_body()
    ticker_raw = payload.get('ticker')
    currency_raw = payload.get('currency')

    ticker = normalize_upper_string(ticker_raw) if ticker_raw is not None else None
    currency = normalize_upper_string(currency_raw) if currency_raw is not None else None

    if ticker is None and currency is None:
        raise ValidationError('No fields to update', details={'fields': ['ticker', 'currency']})

    db = get_db()
    existing = db.execute('SELECT id FROM symbol_mappings WHERE id = ?', (mapping_id,)).fetchone()
    if not existing:
        raise NotFoundError('Mapping not found', details={'mapping_id': mapping_id})

    if ticker is not None and not ticker:
        raise ValidationError('ticker cannot be empty', details={'field': 'ticker'})

    if ticker is not None and currency is not None:
        db.execute(
            'UPDATE symbol_mappings SET ticker = ?, currency = ? WHERE id = ?',
            (ticker, currency, mapping_id)
        )
    elif ticker is not None:
        db.execute(
            'UPDATE symbol_mappings SET ticker = ? WHERE id = ?',
            (ticker, mapping_id)
        )
    else:
        db.execute(
            'UPDATE symbol_mappings SET currency = ? WHERE id = ?',
            (currency, mapping_id)
        )

    db.commit()

    row = db.execute(
        '''SELECT id, symbol_input, ticker, currency, created_at
           FROM symbol_mappings
           WHERE id = ?''',
        (mapping_id,)
    ).fetchone()

    return success_response(serialize_symbol_mapping(row))


@symbol_map_bp.route('/<int:mapping_id>', methods=['DELETE'], strict_slashes=False)
def delete_symbol_mapping(mapping_id: int):
    db = get_db()
    existing = db.execute('SELECT id FROM symbol_mappings WHERE id = ?', (mapping_id,)).fetchone()
    if not existing:
        raise NotFoundError('Mapping not found', details={'mapping_id': mapping_id})

    db.execute('DELETE FROM symbol_mappings WHERE id = ?', (mapping_id,))
    db.commit()
    return success_response({'success': True, 'message': 'Mapping deleted'})
