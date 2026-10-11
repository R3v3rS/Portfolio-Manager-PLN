from flask import Blueprint, request
from datetime import date, datetime, timedelta
import math

from api.exceptions import NotFoundError, ValidationError
from api.response import success_response
from database import get_db
from price_service import PriceService
from routes_portfolio_base import require_json_body, require_non_empty_string
from watchlist_service import WatchlistService

radar_bp = Blueprint('radar', __name__)


def iso_date(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def optional_json_body() -> dict:
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValidationError('Invalid JSON body')
    return data


@radar_bp.route('/', methods=['GET'])
def get_radar():
    tickers = WatchlistService.get_radar_tickers()

    if not tickers:
        return success_response([])

    should_refresh = request.args.get('refresh') == '1'
    radar_data_map = (
        PriceService.refresh_radar_data(tickers)
        if should_refresh
        else PriceService.get_cached_radar_data(tickers)
    )

    db = get_db()
    holdings_rows = db.execute('SELECT ticker, SUM(quantity) as total_qty FROM holdings GROUP BY ticker').fetchall()
    holdings_map = {row['ticker']: row['total_qty'] for row in holdings_rows}

    watchlist_rows = db.execute('SELECT ticker, added_at FROM watchlist').fetchall()
    watchlist_map = {row['ticker']: row['added_at'] for row in watchlist_rows}

    result = []
    metadata = {row['ticker']: dict(row) for row in db.execute('SELECT * FROM asset_metadata')}
    notes = {row['ticker']: dict(row) for row in db.execute('SELECT * FROM radar_notes')}
    # Use the same persisted quotes as the portfolio. Never treat a radar refresh
    # attempt as proof that the underlying quote itself is fresh.
    quotes = {}
    for row in db.execute('SELECT * FROM quotes_cache WHERE price > 0 ORDER BY julianday(updated_at) DESC, CASE WHEN level = \'full\' THEN 0 ELSE 1 END'):
        quotes.setdefault(row['ticker'], dict(row))
    prices = {row['ticker']: dict(row) for row in db.execute('SELECT * FROM price_cache WHERE price > 0')}
    for ticker in tickers:
        radar_data = dict(radar_data_map.get(ticker, {}))
        quote = quotes.get(ticker)
        if quote:
            for field in ('price', 'change_1d', 'change_7d', 'change_1m', 'change_1y'):
                radar_data[field] = quote.get(field)
            radar_data['last_updated_at'] = quote['updated_at']
        price = prices.get(ticker)
        if price and (not quote or str(price['updated_at'] or '').replace('T', ' ') > str(quote['updated_at'] or '').replace('T', ' ')):
            radar_data['price'] = price['price']
            radar_data['last_updated_at'] = price['updated_at']
            for field in ('change_1d', 'change_7d', 'change_1m', 'change_1y'):
                radar_data[field] = None
        # Lite portfolio quotes have no monthly/yearly momentum. Derive missing
        # values from persisted closes near the calendar cutoff, not old radar percentages.
        try:
            quoted_on = datetime.fromisoformat(str(radar_data.get('last_updated_at'))).date()
        except (ValueError, TypeError):
            quoted_on = None
        current_price = radar_data.get('price')
        if quoted_on and current_price and current_price > 0:
            for field, days in (('change_7d', 7), ('change_1m', 30), ('change_1y', 365)):
                if radar_data.get(field) is not None:
                    continue
                cutoff = quoted_on - timedelta(days=days)
                previous = db.execute('''SELECT close_price FROM stock_prices WHERE ticker = ?
                    AND date <= ? AND date >= ? AND close_price > 0 ORDER BY date DESC LIMIT 1''',
                    (ticker, cutoff.isoformat(), (cutoff - timedelta(days=7)).isoformat())).fetchone()
                if previous:
                    radar_data[field] = (float(current_price) / float(previous['close_price']) - 1) * 100
        meta = metadata.get(ticker, {})
        qty = holdings_map.get(ticker, 0)

        result.append({
            'ticker': ticker,
            'company_name': meta.get('company_name') or ticker,
            'sector': meta.get('sector'),
            'currency': meta.get('currency'),
            'instrument_type': 'ETF' if ticker.upper().startswith('ETF') or ' ETF' in str(meta.get('company_name', '')).upper() else 'OTHER',
            'notes': notes.get(ticker),
            'sparkline': [{'date': iso_date(row['date']), 'close_price': row['close_price']} for row in reversed(db.execute(
                '''SELECT date, close_price FROM stock_prices WHERE ticker = ? AND close_price > 0
                   AND date <= date('now') ORDER BY date DESC LIMIT 30''', (ticker,)).fetchall())],
            'events_updated_at': iso_date(radar_data_map.get(ticker, {}).get('last_updated_at')),
            'price': radar_data.get('price'),
            'change_1d': radar_data.get('change_1d'),
            'change_7d': radar_data.get('change_7d'),
            'change_1m': radar_data.get('change_1m'),
            'change_1y': radar_data.get('change_1y'),
            'next_earnings': iso_date(radar_data.get('next_earnings')),
            'ex_dividend_date': iso_date(radar_data.get('ex_dividend_date')),
            'dividend_yield': radar_data.get('dividend_yield'),
            'score': radar_data.get('score'),
            'last_updated_at': iso_date(radar_data.get('last_updated_at')),
            'quantity': qty,
            'is_held': qty > 0,
            'is_watched': ticker in watchlist_map,
            'watched_since': watchlist_map.get(ticker),
        })

    return success_response(sorted(result, key=lambda item: item['ticker']))


@radar_bp.route('/history/<ticker>', methods=['GET'])
def radar_history(ticker):
    # Read-only cached history: comparing instruments must not make N provider calls.
    rows = get_db().execute(
        '''SELECT date, close_price FROM stock_prices WHERE ticker = ?
           AND date >= date('now', '-2 years') AND date <= date('now')
           AND close_price > 0 ORDER BY date''', (ticker.upper(),)
    ).fetchall()
    return success_response([{'date': iso_date(row['date']), 'close_price': row['close_price']} for row in rows])


@radar_bp.route('/notes/<ticker>', methods=['POST'])
def save_radar_notes(ticker):
    ticker = ticker.upper()
    if ticker not in WatchlistService.get_radar_tickers():
        raise NotFoundError('Instrument nie jest na radarze')
    data = require_json_body()
    for field in ('thesis', 'invalidation'):
        if not isinstance(data.get(field, ''), str) or len(data.get(field, '')) > 4000:
            raise ValidationError('Notatka może zawierać maksymalnie 4000 znaków')
    target = data.get('target_price')
    if target is not None and (isinstance(target, bool) or not isinstance(target, (int, float)) or not math.isfinite(target) or target <= 0):
        raise ValidationError('Poziom ceny musi być dodatnią liczbą')
    direction = data.get('target_direction', 'below')
    if direction not in ('below', 'above'):
        raise ValidationError('Nieprawidłowy kierunek alertu')
    review_date = data.get('review_date') or None
    if review_date:
        try:
            date.fromisoformat(review_date)
        except (ValueError, TypeError):
            raise ValidationError('Nieprawidłowa data przeglądu')
    db = get_db()
    db.execute('''INSERT INTO radar_notes (ticker, thesis, invalidation, review_date, target_price, target_direction, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(ticker) DO UPDATE SET
        thesis=excluded.thesis, invalidation=excluded.invalidation, review_date=excluded.review_date,
        target_price=excluded.target_price, target_direction=excluded.target_direction, updated_at=excluded.updated_at''',
        (ticker, data.get('thesis', '').strip(), data.get('invalidation', '').strip(), review_date, target, direction, datetime.now().isoformat(timespec='seconds')))
    db.commit()
    return success_response(dict(db.execute('SELECT * FROM radar_notes WHERE ticker = ?', (ticker,)).fetchone()))


@radar_bp.route('/refresh', methods=['POST'])
def refresh_radar_tickers():
    data = optional_json_body()
    requested_tickers = data.get('tickers') or []

    if requested_tickers:
        tickers = [str(ticker).upper() for ticker in requested_tickers if ticker]
    else:
        tickers = WatchlistService.get_radar_tickers()

    if not tickers:
        return success_response({'message': 'No tickers to refresh', 'tickers': []})

    refreshed = PriceService.refresh_radar_data(tickers)
    return success_response({
        'message': 'Radar data refreshed',
        'tickers': list(refreshed.keys()),
    })


@radar_bp.route('/watchlist', methods=['POST'])
def add_watchlist():
    data = require_json_body()
    ticker = require_non_empty_string(data, 'ticker').upper()
    WatchlistService.add_to_watchlist(ticker)
    return success_response({'message': 'Added to watchlist'}, status=201)


@radar_bp.route('/watchlist/<ticker>', methods=['DELETE'])
def remove_watchlist(ticker):
    WatchlistService.remove_from_watchlist(ticker)
    return success_response({'message': 'Removed from watchlist'})


@radar_bp.route('/analysis/<ticker>', methods=['GET'])
def get_stock_analysis(ticker):
    analysis = PriceService.get_stock_analysis(ticker)
    if not analysis:
        raise NotFoundError('Analysis failed or no data found')
    return success_response(analysis)
