from flask import Blueprint, jsonify, request
from watchlist_service import WatchlistService
from price_service import PriceService
from database import get_db

radar_bp = Blueprint('radar', __name__)

@radar_bp.route('/', methods=['GET'])
def get_radar():
    try:
        # 1. Get unique tickers
        tickers = WatchlistService.get_radar_tickers()
        
        if not tickers:
            return jsonify([])

        # 2. Get Quotes (Price + Change)
        quotes = PriceService.get_quotes(tickers)
        
        # 3. Get Market Events
        events = PriceService.fetch_market_events(tickers)
        
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
            quote = quotes.get(ticker, {})
            event = events.get(ticker, {})
            qty = holdings_map.get(ticker, 0)
            
            result.append({
                'ticker': ticker,
                'price': quote.get('price'),
                'change_1d': quote.get('change_1d'),
                'change_7d': quote.get('change_7d'),
                'change_1m': quote.get('change_1m'),
                'change_1y': quote.get('change_1y'),
                'next_earnings': event.get('next_earnings'),
                'ex_dividend_date': event.get('ex_dividend_date'),
                'dividend_yield': event.get('dividend_yield'),
                'quantity': qty,
                'is_held': qty > 0,
                'is_watched': ticker in watchlist_map,
                'watched_since': watchlist_map.get(ticker)
            })
            
        return jsonify(result)
    except Exception as e:
        print(f"Radar error: {e}")
        return jsonify({'error': str(e)}), 500

@radar_bp.route('/watchlist', methods=['POST'])
def add_watchlist():
    data = request.get_json()
    ticker = data.get('ticker')
    if not ticker:
        return jsonify({'error': 'Ticker is required'}), 400
    
    try:
        WatchlistService.add_to_watchlist(ticker)
        return jsonify({'message': 'Added to watchlist'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@radar_bp.route('/watchlist/<ticker>', methods=['DELETE'])
def remove_watchlist(ticker):
    try:
        WatchlistService.remove_from_watchlist(ticker)
        return jsonify({'message': 'Removed from watchlist'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@radar_bp.route('/analysis/<ticker>', methods=['GET'])
def get_stock_analysis(ticker):
    try:
        analysis = PriceService.get_stock_analysis(ticker)
        if not analysis:
            return jsonify({'error': 'Analysis failed or no data found'}), 404
        return jsonify(analysis)
    except Exception as e:
        print(f"Analysis error: {e}")
        return jsonify({'error': str(e)}), 500
