from flask import Blueprint, request

from api_response import SymbolMappingDTO, error_response, success_response
from database import get_db

symbol_map_bp = Blueprint('symbol_map', __name__)


def serialize_symbol_mapping(row) -> SymbolMappingDTO:
    return {
        'id': row['id'],
        'symbol_input': row['symbol_input'],
        'ticker': row['ticker'],
        'currency': row['currency'],
        'created_at': str(row['created_at']) if row['created_at'] else None,
    }


@symbol_map_bp.route('', methods=['GET'], strict_slashes=False)
def list_symbol_mappings():
    db = get_db()
    rows = db.execute(
        '''SELECT id, symbol_input, ticker, currency, created_at
           FROM symbol_mappings
           ORDER BY symbol_input ASC'''
    ).fetchall()
    return success_response([serialize_symbol_mapping(row) for row in rows], 200)


@symbol_map_bp.route('', methods=['POST'], strict_slashes=False)
def create_symbol_mapping():
    payload = request.get_json(silent=True) or {}
    symbol_input_raw = payload.get('symbol_input', '')
    ticker_raw = payload.get('ticker', '')
    currency_raw = payload.get('currency')

    symbol_input = str(symbol_input_raw).strip().upper()
    ticker = str(ticker_raw).strip().upper()
    currency = str(currency_raw).strip().upper() if currency_raw is not None else None

    if not symbol_input:
        return error_response('symbol_input is required', status_code=400, code='symbol_input_required')
    if not ticker:
        return error_response('ticker is required', status_code=400, code='ticker_required')

    db = get_db()

    existing = db.execute(
        'SELECT id FROM symbol_mappings WHERE symbol_input = ?',
        (symbol_input,)
    ).fetchone()
    if existing:
        return error_response(
            f'Mapping for {symbol_input} already exists',
            status_code=409,
            code='symbol_mapping_conflict',
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

    return success_response(serialize_symbol_mapping(row), 201)


@symbol_map_bp.route('/<int:mapping_id>', methods=['PUT'], strict_slashes=False)
def update_symbol_mapping(mapping_id: int):
    payload = request.get_json(silent=True) or {}
    ticker_raw = payload.get('ticker')
    currency_raw = payload.get('currency')

    ticker = str(ticker_raw).strip().upper() if ticker_raw is not None else None
    currency = str(currency_raw).strip().upper() if currency_raw is not None else None

    if ticker is None and currency is None:
        return error_response('No fields to update', status_code=400, code='empty_update')

    db = get_db()
    existing = db.execute('SELECT id FROM symbol_mappings WHERE id = ?', (mapping_id,)).fetchone()
    if not existing:
        return error_response('Mapping not found', status_code=404, code='symbol_mapping_not_found')

    if ticker is not None and not ticker:
        return error_response('ticker cannot be empty', status_code=400, code='ticker_empty')

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

    return success_response(serialize_symbol_mapping(row), 200)


@symbol_map_bp.route('/<int:mapping_id>', methods=['DELETE'], strict_slashes=False)
def delete_symbol_mapping(mapping_id: int):
    db = get_db()
    existing = db.execute('SELECT id FROM symbol_mappings WHERE id = ?', (mapping_id,)).fetchone()
    if not existing:
        return error_response('Mapping not found', status_code=404, code='symbol_mapping_not_found')

    db.execute('DELETE FROM symbol_mappings WHERE id = ?', (mapping_id,))
    db.commit()
    return success_response({'success': True, 'message': 'Mapping deleted'}, 200)
