from database import get_db

class WatchlistService:
    @staticmethod
    def add_to_watchlist(ticker):
        db = get_db()
        try:
            # Check if exists to avoid error if unique constraint hit (though INSERT OR IGNORE handles it too)
            # Using INSERT OR IGNORE is cleaner
            db.execute('INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)', (ticker,))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def remove_from_watchlist(ticker):
        db = get_db()
        try:
            db.execute('DELETE FROM watchlist WHERE ticker = ?', (ticker,))
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    @staticmethod
    def get_radar_tickers():
        db = get_db()
        # Get watchlist tickers
        watchlist = db.execute('SELECT ticker FROM watchlist').fetchall()
        watchlist_tickers = {row['ticker'] for row in watchlist}
        
        # Get holdings tickers (where quantity > 0)
        holdings = db.execute('SELECT DISTINCT ticker FROM holdings WHERE quantity > 0').fetchall()
        holdings_tickers = {row['ticker'] for row in holdings}
        
        # Combine and return list
        return list(watchlist_tickers.union(holdings_tickers))

    @staticmethod
    def get_watchlist():
        db = get_db()
        watchlist = db.execute('SELECT ticker, added_at FROM watchlist ORDER BY added_at DESC').fetchall()
        return [{key: row[key] for key in row.keys()} for row in watchlist]
