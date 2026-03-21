from database import get_db
from flask import Blueprint, request

from price_service import PriceService
from validators.responses import error_response, success_response
from watchlist_service import WatchlistService

radar_bp = Blueprint('radar', __name__)

@radar_bp.route('/', methods=['GET'])
def get_radar():
    try:
        # 1. Get unique tickers
        tickers = WatchlistService.get_radar_tickers()
        
        if not tickers:
            return success_response([])

        should_refresh = request.args.get('refresh') == '1'
        if should_refresh:
            radar_data_map = PriceService.refresh_radar_data(tickers)
        else:
            radar_data_map = PriceService.get_cached_radar_data(tickers)
        
        # 4. Get Holdings Quantity
        # Get total quantity per ticker across all portfolios
        db = get_db()
        holdings_rows = db.execute('SELECT ticker, SUM(quantity) as total_qty FROM holdings GROUP BY ticker').fetchall()
        holdings_map = {row['ticker']: row['total_qty'] for row in holdings_rows}
        
        # Get watchlist added_at dates to show when it was watched
        watchlist_rows = db.execute('SELECT ticker, added_at FROM watchlist').fetchall()
        watchlist_map = {row['ticker']: row['added_at'] for row in watchlist_rows}
        
        result = []
        for ticker in tickers:
            radar_data = radar_data_map.get(ticker, {})
            qty = holdings_map.get(ticker, 0)
            
            result.append({
                'ticker': ticker,
                'price': radar_data.get('price'),
                'change_1d': radar_data.get('change_1d'),
                'change_7d': radar_data.get('change_7d'),
                'change_1m': radar_data.get('change_1m'),
                'change_1y': radar_data.get('change_1y'),
                'next_earnings': radar_data.get('next_earnings'),
                'ex_dividend_date': radar_data.get('ex_dividend_date'),
                'dividend_yield': radar_data.get('dividend_yield'),
                'last_updated_at': radar_data.get('last_updated_at'),
                'quantity': qty,
                'is_held': qty > 0,
                'is_watched': ticker in watchlist_map,
                'watched_since': watchlist_map.get(ticker)
            })
            
        return success_response(result)
    except Exception as e:
        print(f"Radar error: {e}")
        return error_response(str(e), status_code=500, code='internal_server_error')

@radar_bp.route('/refresh', methods=['POST'])
def refresh_radar_tickers():
    try:
        data = request.get_json(silent=True) or {}
        requested_tickers = data.get('tickers') or []

        if requested_tickers:
            tickers = [ticker.upper() for ticker in requested_tickers if ticker]
        else:
            tickers = WatchlistService.get_radar_tickers()

        if not tickers:
            return success_response({'tickers': []}, message='No tickers to refresh')

        refreshed = PriceService.refresh_radar_data(tickers)
        return success_response({'tickers': list(refreshed.keys())}, message='Radar data refreshed')
    except Exception as e:
        print(f"Radar refresh error: {e}")
        return error_response(str(e), status_code=500, code='internal_server_error')

@radar_bp.route('/watchlist', methods=['POST'])
def add_watchlist():
    data = request.get_json()
    ticker = data.get('ticker')
    if not ticker:
        return error_response('Ticker is required', status_code=400, code='validation_error')
    
    try:
        WatchlistService.add_to_watchlist(ticker)
        return success_response(None, message='Added to watchlist', status_code=201)
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')

@radar_bp.route('/watchlist/<ticker>', methods=['DELETE'])
def remove_watchlist(ticker):
    try:
        WatchlistService.remove_from_watchlist(ticker)
        return success_response(None, message='Removed from watchlist')
    except Exception as e:
        return error_response(str(e), status_code=500, code='internal_server_error')

@radar_bp.route('/analysis/<ticker>', methods=['GET'])
def get_stock_analysis(ticker):
    try:
        analysis = PriceService.get_stock_analysis(ticker)
        if not analysis:
            return error_response('Analysis failed or no data found', status_code=404, code='not_found')
        return success_response(analysis)
    except Exception as e:
        print(f"Analysis error: {e}")
        return error_response(str(e), status_code=500, code='internal_server_error')
