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

# Force yfinance to use a persistent cache directory to reuse cookies/crumbs
cache_dir = os.path.join(tempfile.gettempdir(), 'yfinance_cache_portfel')
if not os.path.exists(cache_dir):
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception as e:
        print(f"Failed to create cache dir {cache_dir}: {e}")
        # Fallback
        cache_dir = os.path.join(tempfile.gettempdir(), 'yfinance_cache_fallback')
        os.makedirs(cache_dir, exist_ok=True)

os.environ['YFINANCE_CACHE_DIR'] = cache_dir
print(f"Using yfinance cache at: {cache_dir}")

class PriceService:
    _price_cache = {}
    _price_cache_updated_at = {}

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
                                cls._price_cache_updated_at[ticker] = datetime.now().isoformat(timespec='seconds')
                        
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
                            cls._price_cache_updated_at[ticker] = datetime.now().isoformat(timespec='seconds')
                        else:
                            # Try fast_info as last resort
                            try:
                                price = t.fast_info.last_price
                                if price:
                                    cls._price_cache[ticker] = round(float(price), 2)
                                    cls._price_cache_updated_at[ticker] = datetime.now().isoformat(timespec='seconds')
                            except:
                                print(f"[WARNING] No data for {ticker}")
                    except Exception as e:
                         print(f"[ERROR] Individual fetch failed for {ticker}: {e}")

            # Final Safety Step: Mark any missing tickers as None
            for ticker in missing_tickers:
                if ticker not in cls._price_cache:
                    cls._price_cache[ticker] = None
                    cls._price_cache_updated_at[ticker] = None
        
        return cls._price_cache

    @classmethod
    def get_price_updates(cls, tickers):
        if not tickers:
            return {}

        cls.get_prices(tickers)
        return {ticker: cls._price_cache_updated_at.get(ticker) for ticker in tickers}

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
            currency = clean(info.get('currency')) or "PLN"
            
            return {
                'company_name': company_name,
                'sector': sector,
                'industry': industry,
                'currency': currency
            }
        except Exception as e:
            print(f"Metadata fetch error for {ticker}: {e}")
            return None

    @classmethod
    def get_quotes(cls, tickers):
        """
        Fetches current price and multi-timeframe momentum (1D, 7D, 1M, 1Y) for a list of tickers.
        Returns: { 'AAPL': {'price': 150.0, 'change_1d': 1.5, 'change_7d': ..., 'change_1m': ..., 'change_1y': ...}, ... }
        """
        quotes = {}
        if not tickers:
            return quotes
            
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                
                # Fetch 1 year history to calculate all changes
                hist = t.history(period="1y")
                
                if hist.empty:
                     # Fallback if no history
                    quotes[ticker] = {
                        'price': 0.0,
                        'change_1d': None,
                        'change_7d': None,
                        'change_1m': None,
                        'change_1y': None
                    }
                    continue

                # Get latest price
                current_price = hist['Close'].iloc[-1]
                
                # Helper to calculate percentage change safely
                def calc_change(current, old):
                    if old == 0: return 0.0
                    return ((current - old) / old) * 100

                # 1D Change (compare with previous row)
                change_1d = None
                if len(hist) >= 2:
                    prev_close = hist['Close'].iloc[-2]
                    change_1d = calc_change(current_price, prev_close)

                # 7D Change (approx 5 trading days ago)
                change_7d = None
                if len(hist) >= 6:
                    price_7d_ago = hist['Close'].iloc[-6]
                    change_7d = calc_change(current_price, price_7d_ago)

                # 1M Change (approx 21 trading days ago)
                change_1m = None
                if len(hist) >= 22:
                    price_1m_ago = hist['Close'].iloc[-22]
                    change_1m = calc_change(current_price, price_1m_ago)

                # 1Y Change (approx start of the dataframe if it has enough data)
                change_1y = None
                # If we asked for 1y, the first row is roughly 1y ago
                if len(hist) > 0:
                     price_1y_ago = hist['Close'].iloc[0]
                     change_1y = calc_change(current_price, price_1y_ago)

                quotes[ticker] = {
                    'price': round(float(current_price), 2),
                    'change_1d': round(change_1d, 2) if change_1d is not None else None,
                    'change_7d': round(change_7d, 2) if change_7d is not None else None,
                    'change_1m': round(change_1m, 2) if change_1m is not None else None,
                    'change_1y': round(change_1y, 2) if change_1y is not None else None,
                }
                
                # Update cache while we are at it
                cls._price_cache[ticker] = round(float(current_price), 2)
                    
            except Exception as e:
                print(f"Error fetching quote for {ticker}: {e}")
                quotes[ticker] = {
                    'price': 0.0,
                    'change_1d': None,
                    'change_7d': None,
                    'change_1m': None,
                    'change_1y': None
                }
        
        return quotes

    @classmethod
    def get_cached_radar_data(cls, tickers):
        if not tickers:
            return {}

        placeholders = ','.join(['?'] * len(tickers))
        db = get_db()
        rows = db.execute(
            f'''SELECT ticker, price, change_1d, change_7d, change_1m, change_1y,
                       next_earnings, ex_dividend_date, dividend_yield, last_updated_at
                FROM radar_cache
                WHERE ticker IN ({placeholders})''',
            tickers
        ).fetchall()

        return {
            row['ticker']: {
                'price': row['price'],
                'change_1d': row['change_1d'],
                'change_7d': row['change_7d'],
                'change_1m': row['change_1m'],
                'change_1y': row['change_1y'],
                'next_earnings': row['next_earnings'],
                'ex_dividend_date': row['ex_dividend_date'],
                'dividend_yield': row['dividend_yield'],
                'last_updated_at': row['last_updated_at']
            }
            for row in rows
        }

    @classmethod
    def refresh_radar_data(cls, tickers):
        if not tickers:
            return {}

        quotes = cls.get_quotes(tickers)
        events = cls.fetch_market_events(tickers)

        db = get_db()
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        for ticker in tickers:
            quote = quotes.get(ticker, {})
            event = events.get(ticker, {})

            db.execute(
                '''INSERT INTO radar_cache
                   (ticker, price, change_1d, change_7d, change_1m, change_1y,
                    next_earnings, ex_dividend_date, dividend_yield, last_updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ticker) DO UPDATE SET
                     price = excluded.price,
                     change_1d = excluded.change_1d,
                     change_7d = excluded.change_7d,
                     change_1m = excluded.change_1m,
                     change_1y = excluded.change_1y,
                     next_earnings = excluded.next_earnings,
                     ex_dividend_date = excluded.ex_dividend_date,
                     dividend_yield = excluded.dividend_yield,
                     last_updated_at = excluded.last_updated_at''',
                (
                    ticker,
                    quote.get('price'),
                    quote.get('change_1d'),
                    quote.get('change_7d'),
                    quote.get('change_1m'),
                    quote.get('change_1y'),
                    event.get('next_earnings'),
                    event.get('ex_dividend_date'),
                    event.get('dividend_yield'),
                    now
                )
            )

        db.commit()
        return cls.get_cached_radar_data(tickers)

    @classmethod
    def fetch_market_events(cls, tickers):
        """
        Fetches upcoming earnings and dividend info.
        """
        events = {}
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                
                next_earnings = None
                ex_dividend_date = None
                dividend_yield = None
                
                # 1. Try Calendar for Earnings
                try:
                    cal = t.calendar
                    # t.calendar can be a dict or dataframe depending on version
                    if isinstance(cal, dict) and 'Earnings Date' in cal:
                        dates = cal['Earnings Date']
                        if dates:
                            # It might be a list of dates or just one
                            if isinstance(dates, list):
                                next_earnings = str(dates[0].date()) if hasattr(dates[0], 'date') else str(dates[0])
                            else:
                                next_earnings = str(dates)
                    elif hasattr(cal, 'get'):
                        # DataFrame or similar?
                        pass 
                except Exception as e:
                    print(f"Calendar fetch error {ticker}: {e}")

                # 2. Try Info for everything else (and fallback for earnings)
                try:
                    info = t.info
                    
                    if not next_earnings and info.get('earningsTimestamp'):
                         next_earnings = datetime.fromtimestamp(info['earningsTimestamp']).strftime('%Y-%m-%d')
                    
                    if info.get('exDividendDate'):
                         ex_dividend_date = datetime.fromtimestamp(info['exDividendDate']).strftime('%Y-%m-%d')
                    
                    dividend_yield = info.get('dividendYield')
                    
                except Exception as e:
                    print(f"Info fetch error {ticker}: {e}")

                events[ticker] = {
                    "next_earnings": next_earnings,
                    "ex_dividend_date": ex_dividend_date,
                    "dividend_yield": dividend_yield
                }
            except Exception as e:
                print(f"Error fetching events for {ticker}: {e}")
                events[ticker] = {
                    "next_earnings": None,
                    "ex_dividend_date": None,
                    "dividend_yield": None
                }
        return events

    @classmethod
    def get_stock_analysis(cls, ticker):
        """
        Fetches deep fundamental, analyst, and technical data for a single ticker.
        """
        try:
            print(f"Analyzing {ticker}...")
            t = yf.Ticker(ticker)
            info = t.info
            
            # Helper to safely get value
            def get_val(key, default=None):
                val = info.get(key)
                return val if val is not None and val != 'null' else default

            # 1. Fundamentals
            fundamentals = {
                "trailingPE": get_val("trailingPE"),
                "priceToBook": get_val("priceToBook"),
                "returnOnEquity": get_val("returnOnEquity"),
                "payoutRatio": get_val("payoutRatio")
            }

            # 2. Analyst Consensus
            target_mean = get_val("targetMeanPrice")
            current_price = get_val("currentPrice") or get_val("regularMarketPrice")
            
            upside_potential = None
            if target_mean and current_price:
                try:
                    upside_potential = ((target_mean - current_price) / current_price) * 100
                except:
                    pass

            analyst = {
                "targetMeanPrice": target_mean,
                "recommendationKey": get_val("recommendationKey"),
                "upsidePotential": upside_potential
            }

            # 3. Technicals
            technicals = {
                "sma50": None,
                "sma200": None,
                "rsi14": None
            }
            
            try:
                # Fetch 1 year of history + extra buffer for MA/RSI calculation
                hist = t.history(period="1y")
                
                if not hist.empty and len(hist) > 50:
                    # SMA 50
                    hist['SMA50'] = hist['Close'].rolling(window=50).mean()
                    technicals["sma50"] = hist['SMA50'].iloc[-1]
                    
                    # SMA 200
                    if len(hist) > 200:
                        hist['SMA200'] = hist['Close'].rolling(window=200).mean()
                        technicals["sma200"] = hist['SMA200'].iloc[-1]

                    # RSI 14
                    delta = hist['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    
                    rs = gain / loss
                    hist['RSI'] = 100 - (100 / (1 + rs))
                    
                    # Handle division by zero or NaN if loss is 0
                    technicals["rsi14"] = hist['RSI'].iloc[-1]
                    
                    # Cleanup NaN/Infinite values just in case
                    if pd.isna(technicals["rsi14"]): technicals["rsi14"] = None
                    if pd.isna(technicals["sma50"]): technicals["sma50"] = None
                    if pd.isna(technicals["sma200"]): technicals["sma200"] = None

            except Exception as e:
                print(f"Technical analysis failed for {ticker}: {e}")

            return {
                "fundamentals": fundamentals,
                "analyst": analyst,
                "technicals": technicals
            }

        except Exception as e:
            print(f"Analysis failed for {ticker}: {e}")
            return None
