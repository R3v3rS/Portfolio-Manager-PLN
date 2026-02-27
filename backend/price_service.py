import os
import tempfile
import yfinance as yf
import pandas as pd
from database import get_db
import sqlite3
from datetime import datetime, timedelta, date
import time
import random
import logging

# Force yfinance to use a cache directory in user home to avoid path length/space issues
cache_dir = os.path.join(os.path.expanduser('~'), 'yfinance_cache_custom')
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
os.environ['YFINANCE_CACHE_DIR'] = cache_dir
print(f"Using yfinance cache at: {cache_dir}")

class PriceService:
    _price_cache = {}

    @classmethod
    def _download_with_retry(cls, *args, **kwargs):
        """Download wrapper with simple retry + exponential backoff."""
        attempts = 3
        delay = 1
        for attempt in range(1, attempts + 1):
            try:
                return yf.download(*args, **kwargs)
            except Exception as e:
                logging.warning(f"yfinance download failed (attempt {attempt}/{attempts}): {e}")
                if attempt == attempts:
                    logging.error("yfinance download failed after retries")
                    raise
                sleep_time = delay + random.uniform(0, 0.5)
                time.sleep(sleep_time)
                delay *= 2

    @classmethod
    def get_prices(cls, tickers):
        if not tickers:
            return {}
        
        # Identify missing tickers in cache
        missing_tickers = [t for t in tickers if t not in cls._price_cache]
        
        if missing_tickers:
            print(f"Fetching prices for: {missing_tickers}")
            
            # Attempt 1: Bulk Download
            try:
                # Fetch 5 days of data to handle weekends/holidays/gaps (with retry)
                data = cls._download_with_retry(missing_tickers, period="5d", group_by='ticker', threads=False)

                if data.empty:
                    print("[WARNING] Bulk download returned empty data. Trying individual fetch.")
                    raise ValueError("Empty Data")

                # Process bulk data
                for ticker in missing_tickers:
                    try:
                        ticker_df = None
                        if isinstance(data.columns, pd.MultiIndex):
                            if ticker in data.columns.levels[0]:
                                ticker_df = data[ticker]
                        elif 'Close' in data.columns and len(missing_tickers) == 1:
                            ticker_df = data

                        if ticker_df is not None and 'Close' in ticker_df.columns:
                            df_cleaned = ticker_df.dropna(subset=['Close'])
                            if not df_cleaned.empty:
                                price = df_cleaned['Close'].iloc[-1]
                                if hasattr(price, 'item'):
                                    price = price.item()
                                cls._price_cache[ticker] = round(float(price), 2)
                        
                    except Exception as e:
                        print(f"[ERROR] Failed to process bulk data for {ticker}: {e}")

            except Exception as e:
                print(f"[WARNING] Bulk fetch failed ({e}). Switching to individual fallback.")
            
            # Attempt 2: Individual Fetch (Fallback for any still missing)
            remaining_tickers = [t for t in missing_tickers if t not in cls._price_cache]
            if remaining_tickers:
                print(f"Fallback fetching for: {remaining_tickers}")
                for ticker in remaining_tickers:
                    try:
                        t = yf.Ticker(ticker)
                        # Try history first
                        hist = t.history(period="5d")
                        if not hist.empty:
                            price = hist['Close'].iloc[-1]
                            cls._price_cache[ticker] = round(float(price), 2)
                        else:
                            # Try fast_info as last resort
                            try:
                                price = t.fast_info.last_price
                                if price:
                                    cls._price_cache[ticker] = round(float(price), 2)
                            except:
                                print(f"[WARNING] No data for {ticker}")
                    except Exception as e:
                         print(f"[ERROR] Individual fetch failed for {ticker}: {e}")

            # Final Safety Step: Mark any missing tickers as None
            for ticker in missing_tickers:
                if ticker not in cls._price_cache:
                    cls._price_cache[ticker] = None
        
        return cls._price_cache

    @classmethod
    def warmup_cache(cls):
        db = get_db()
        try:
            holdings = db.execute('SELECT DISTINCT ticker FROM holdings').fetchall()
            tickers = [h['ticker'] for h in holdings]
            if tickers:
                print(f"Warming up price cache for: {tickers}")
                cls.get_prices(tickers)
        except Exception as e:
            print(f"Cache warmup failed: {e}")

    @classmethod
    def sync_stock_history(cls, ticker, required_start_date=None):
        """
        Incremental sync of stock prices from yfinance to local DB.
        """
        db = get_db()
        
        # 1. Find the latest date available in DB
        result = db.execute(
            'SELECT MAX(date) as max_date FROM stock_prices WHERE ticker = ?',
            (ticker,)
        ).fetchone()
        
        max_date_str = result['max_date']
        max_date = None
        if max_date_str:
            if isinstance(max_date_str, str):
                max_date = datetime.strptime(max_date_str, '%Y-%m-%d').date()
            else:
                max_date = max_date_str # Handle if sqlite returns date object

        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # 2. Determine fetch start date
        fetch_start = None
        
        if not max_date:
            # If no data, use required_start_date or default to 1 year ago
            if required_start_date:
                if isinstance(required_start_date, str):
                    fetch_start = datetime.strptime(required_start_date, '%Y-%m-%d').date()
                else:
                    fetch_start = required_start_date
            else:
                fetch_start = today - timedelta(days=365)
        elif max_date < yesterday:
            # If data exists but is old, start from the day after max_date
            fetch_start = max_date + timedelta(days=1)
        else:
            # Already up to date
            print(f"History for {ticker} is already up to date (last: {max_date})")
            return max_date_str

        if fetch_start >= today:
             return max_date_str

        print(f"Syncing {ticker} history starting from {fetch_start}...")

        try:
            # 3. Fetch from yfinance (with retry)
            # Use fetch_start to today
            data = cls._download_with_retry(ticker, start=fetch_start, interval="1d", threads=False)

            if not data.empty:
                # 4. Save to DB
                cursor = db.cursor()
                for timestamp, row in data.iterrows():
                    price_date = timestamp.date()
                    # Check if 'Close' exists (handle MultiIndex if necessary)
                    price = None
                    if 'Close' in data.columns:
                        price = row['Close']
                        if hasattr(price, 'item'):
                            price = price.item()

                    if price is not None and not pd.isna(price):
                        cursor.execute(
                            '''INSERT OR IGNORE INTO stock_prices (ticker, date, close_price)
                               VALUES (?, ?, ?)''',
                            (ticker, price_date.isoformat(), round(float(price), 2))
                        )
                db.commit()
                print(f"Successfully synced {ticker} history.")
            else:
                print(f"No history data found for {ticker} from {fetch_start}")

        except Exception as e:
            print(f"Error syncing history for {ticker}: {e}")
            db.rollback()

        # Return latest date in DB
        new_max = db.execute(
            'SELECT MAX(date) as max_date FROM stock_prices WHERE ticker = ?',
            (ticker,)
        ).fetchone()
        return new_max['max_date']

    @classmethod
    def fetch_metadata(cls, ticker):
        """
        Fetches company name, sector, and industry from yfinance.
        """
        try:
            print(f"Fetching metadata for {ticker}...")
            t = yf.Ticker(ticker)
            info = t.info
            
            # Helper to safely get string
            def clean(val):
                return val if val and val != 'null' else None

            company_name = clean(info.get('longName')) or clean(info.get('shortName')) or "Unknown"
            sector = clean(info.get('sector')) or "Unknown"
            industry = clean(info.get('industry')) or "Unknown"
            
            return {
                'company_name': company_name,
                'sector': sector,
                'industry': industry
            }
        except Exception as e:
            print(f"Metadata fetch error for {ticker}: {e}")
            return None
