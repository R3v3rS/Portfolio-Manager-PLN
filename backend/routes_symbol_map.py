from flask import Blueprint, jsonify, request
from database import get_db

symbol_map_bp = Blueprint('symbol_map', __name__)


@symbol_map_bp.route('', methods=['GET'])
def list_symbol_mappings():
    db = get_db()
    rows = db.execute(
        '''SELECT id, symbol_input, ticker, currency, created_at
           FROM symbol_mappings
           ORDER BY symbol_input ASC'''
    ).fetchall()
    return jsonify([
        {
            'id': row['id'],
            'symbol_input': row['symbol_input'],
            'ticker': row['ticker'],
            'currency': row['currency'],
            'created_at': str(row['created_at']) if row['created_at'] else None,
        }
        for row in rows
    ]), 200


@symbol_map_bp.route('', methods=['POST'])
def create_symbol_mapping():
    payload = request.get_json(silent=True) or {}
    symbol_input_raw = payload.get('symbol_input', '')
    ticker_raw = payload.get('ticker', '')
    currency_raw = payload.get('currency')

    symbol_input = str(symbol_input_raw).strip().upper()
    ticker = str(ticker_raw).strip().upper()
    currency = str(currency_raw).strip().upper() if currency_raw is not None else None

    if not symbol_input:
        return jsonify({'error': 'symbol_input is required'}), 400
    if not ticker:
        return jsonify({'error': 'ticker is required'}), 400

    db = get_db()

    existing = db.execute(
        'SELECT id FROM symbol_mappings WHERE symbol_input = ?',
        (symbol_input,)
    ).fetchone()
    if existing:
        return jsonify({'error': f'Mapping for {symbol_input} already exists'}), 409

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

    return jsonify({
        'id': row['id'],
        'symbol_input': row['symbol_input'],
        'ticker': row['ticker'],
        'currency': row['currency'],
        'created_at': str(row['created_at']) if row['created_at'] else None,
    }), 201


@symbol_map_bp.route('/<int:mapping_id>', methods=['PUT'])
def update_symbol_mapping(mapping_id: int):
    payload = request.get_json(silent=True) or {}
    ticker_raw = payload.get('ticker')
    currency_raw = payload.get('currency')

    ticker = str(ticker_raw).strip().upper() if ticker_raw is not None else None
    currency = str(currency_raw).strip().upper() if currency_raw is not None else None

    if ticker is None and currency is None:
        return jsonify({'error': 'No fields to update'}), 400

    db = get_db()
    existing = db.execute('SELECT id FROM symbol_mappings WHERE id = ?', (mapping_id,)).fetchone()
    if not existing:
        return jsonify({'error': 'Mapping not found'}), 404

    if ticker is not None and not ticker:
        return jsonify({'error': 'ticker cannot be empty'}), 400

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

    return jsonify({
        'id': row['id'],
        'symbol_input': row['symbol_input'],
        'ticker': row['ticker'],
        'currency': row['currency'],
        'created_at': str(row['created_at']) if row['created_at'] else None,
    }), 200


@symbol_map_bp.route('/<int:mapping_id>', methods=['DELETE'])
def delete_symbol_mapping(mapping_id: int):
    db = get_db()
    existing = db.execute('SELECT id FROM symbol_mappings WHERE id = ?', (mapping_id,)).fetchone()
    if not existing:
        return jsonify({'error': 'Mapping not found'}), 404

    db.execute('DELETE FROM symbol_mappings WHERE id = ?', (mapping_id,))
    db.commit()
    return jsonify({'success': True}), 200
