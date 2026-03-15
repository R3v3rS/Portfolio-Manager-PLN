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
    _metadata_cache = {}
    _metadata_cache_updated_at = {}
    _metadata_ttl = timedelta(days=7)
    _default_history_start = date(2000, 1, 1)

    @staticmethod
    def _normalize_yf_dataframe(df):
        if df is None or df.empty:
            return df
        if isinstance(df.columns, pd.MultiIndex):
            df = df.copy()
            df.columns = df.columns.get_level_values(0)
        return df

    @staticmethod
    def _safe_float_from_value(value):
        if value is None:
            return None
        if isinstance(value, (pd.Series, pd.DataFrame)):
            if value.empty:
                return None
            if isinstance(value, pd.DataFrame):
                value = value.iloc[-1].squeeze()
            elif len(value) > 1:
                value = value.iloc[-1]
        if pd.isna(value):
            return None
        return float(value)

    @classmethod
    def _load_metadata_from_db(cls, ticker):
        db = get_db()
        row = db.execute(
            '''SELECT company_name, sector, industry, currency, updated_at
               FROM asset_metadata
               WHERE ticker = ?''',
            (ticker,)
        ).fetchone()
        if not row:
            return None

        updated_at = row['updated_at']
        if not updated_at:
            return None

        try:
            updated_dt = datetime.fromisoformat(str(updated_at))
        except ValueError:
            return None

        if datetime.now() - updated_dt > cls._metadata_ttl:
            return None

        metadata = {
            'company_name': row['company_name'] or 'Unknown',
            'sector': row['sector'] or 'Unknown',
            'industry': row['industry'] or 'Unknown',
            'currency': (row['currency'] or 'PLN').upper()
        }
        cls._metadata_cache[ticker] = metadata
        cls._metadata_cache_updated_at[ticker] = updated_dt
        return metadata

    @classmethod
    def _save_metadata_to_db(cls, ticker, metadata):
        db = get_db()
        now_iso = datetime.now().isoformat(timespec='seconds')
        db.execute(
            '''INSERT INTO asset_metadata (ticker, company_name, sector, industry, currency, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker)
               DO UPDATE SET
                    company_name = excluded.company_name,
                    sector = excluded.sector,
                    industry = excluded.industry,
                    currency = excluded.currency,
                    updated_at = excluded.updated_at''',
            (
                ticker,
                metadata.get('company_name') or 'Unknown',
                metadata.get('sector') or 'Unknown',
                metadata.get('industry') or 'Unknown',
                (metadata.get('currency') or 'PLN').upper(),
                now_iso
            )
        )
        db.commit()
        cls._metadata_cache[ticker] = metadata
        cls._metadata_cache_updated_at[ticker] = datetime.fromisoformat(now_iso)

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
    def _load_price_cache_from_db(cls, tickers):
        db = get_db()
        placeholders = ','.join('?' for _ in tickers)
        rows = db.execute(
            f'''SELECT ticker, price, updated_at
                FROM price_cache
                WHERE ticker IN ({placeholders})''',
            tuple(tickers)
        ).fetchall()

        for row in rows:
            ticker = row['ticker']
            cls._price_cache[ticker] = float(row['price']) if row['price'] is not None else None
            cls._price_cache_updated_at[ticker] = row['updated_at']

    @classmethod
    def _save_price_cache_to_db(cls, ticker, price, updated_at=None):
        db = get_db()
        now_iso = datetime.now().isoformat(timespec='seconds')
        effective_updated_at = updated_at or now_iso
        db.execute(
            '''INSERT INTO price_cache (ticker, price, updated_at, last_attempted_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(ticker)
               DO UPDATE SET
                    price = excluded.price,
                    updated_at = excluded.updated_at,
                    last_attempted_at = excluded.last_attempted_at''',
            (ticker, price, effective_updated_at, now_iso)
        )
        db.commit()

    @classmethod
    def _mark_price_refresh_attempt(cls, ticker):
        db = get_db()
        now_iso = datetime.now().isoformat(timespec='seconds')
        db.execute(
            '''INSERT INTO price_cache (ticker, last_attempted_at)
               VALUES (?, ?)
               ON CONFLICT(ticker)
               DO UPDATE SET
                    last_attempted_at = excluded.last_attempted_at''',
            (ticker, now_iso)
        )
        db.commit()

    @staticmethod
    def _is_same_day(timestamp):
        if not timestamp:
            return False
        try:
            parsed = datetime.fromisoformat(str(timestamp))
        except ValueError:
            return False
        return parsed.date() == datetime.now().date()

    @classmethod
    def get_prices(cls, tickers, force_refresh=False):
        if not tickers:
            return {}

        normalized_tickers = sorted({str(t).strip().upper() for t in tickers if t})
        if not normalized_tickers:
            return {}

        cls._load_price_cache_from_db(normalized_tickers)

        missing_tickers = []
        for ticker in normalized_tickers:
            if force_refresh:
                missing_tickers.append(ticker)
                continue

            updated_at = cls._price_cache_updated_at.get(ticker)
            if ticker not in cls._price_cache or not cls._is_same_day(updated_at):
                missing_tickers.append(ticker)
        
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

                        ticker_df = cls._normalize_yf_dataframe(ticker_df)
                        if ticker_df is not None and not ticker_df.empty and 'Close' in ticker_df.columns:
                            df_cleaned = ticker_df.dropna(subset=['Close'])
                            if not df_cleaned.empty:
                                price = cls._safe_float_from_value(df_cleaned['Close'].iloc[-1])
                                if price is not None:
                                    normalized_price = round(price, 2)
                                    now_iso = datetime.now().isoformat(timespec='seconds')
                                    cls._price_cache[ticker] = normalized_price
                                    cls._price_cache_updated_at[ticker] = now_iso
                                    cls._save_price_cache_to_db(ticker, normalized_price, now_iso)
                        
                    except Exception as e:
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error processing yfinance data for {ticker}: {e}")

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
                        hist = cls._normalize_yf_dataframe(t.history(period="5d"))
                        if hist is not None and not hist.empty and 'Close' in hist.columns:
                            hist = hist.dropna(subset=['Close'])
                        if hist is not None and not hist.empty and 'Close' in hist.columns:
                            price = cls._safe_float_from_value(hist['Close'].iloc[-1])
                            if price is not None:
                                normalized_price = round(price, 2)
                                now_iso = datetime.now().isoformat(timespec='seconds')
                                cls._price_cache[ticker] = normalized_price
                                cls._price_cache_updated_at[ticker] = now_iso
                                cls._save_price_cache_to_db(ticker, normalized_price, now_iso)
                        else:
                            # Try fast_info as last resort
                            try:
                                price = t.fast_info.last_price
                                if price:
                                    normalized_price = round(float(price), 2)
                                    now_iso = datetime.now().isoformat(timespec='seconds')
                                    cls._price_cache[ticker] = normalized_price
                                    cls._price_cache_updated_at[ticker] = now_iso
                                    cls._save_price_cache_to_db(ticker, normalized_price, now_iso)
                            except:
                                print(f"[WARNING] No data for {ticker}")
                    except Exception as e:
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error processing yfinance data for {ticker}: {e}")

            # Final safety step: remember refresh attempt (prevents repeated retries during market close)
            for ticker in missing_tickers:
                if ticker not in cls._price_cache:
                    cls._price_cache[ticker] = None
                    cls._price_cache_updated_at[ticker] = None
                cls._mark_price_refresh_attempt(ticker)

        return {ticker: cls._price_cache.get(ticker) for ticker in normalized_tickers}

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

    @staticmethod
    def _latest_expected_market_day(reference_date=None):
        """
        Returns the latest day that can reasonably have a market close.
        Uses weekday calendar (Mon-Fri) to avoid weekend re-sync loops.
        """
        current = reference_date or date.today()
        candidate = current - timedelta(days=1)
        while candidate.weekday() >= 5:  # 5=Saturday, 6=Sunday
            candidate -= timedelta(days=1)
        return candidate

    @classmethod
    def get_tickers_requiring_history_sync(cls, tickers, required_start_date=None):
        """
        Returns only tickers that are missing history or are stale.
        """
        normalized = sorted({str(t).strip().upper() for t in tickers if t})
        if not normalized:
            return []

        db = get_db()
        placeholders = ','.join('?' for _ in normalized)
        rows = db.execute(
            f'''SELECT ticker, MAX(date) as max_date
                FROM stock_prices
                WHERE ticker IN ({placeholders})
                GROUP BY ticker''',
            tuple(normalized)
        ).fetchall()
        latest_by_ticker = {row['ticker']: row['max_date'] for row in rows}

        expected_latest_day = cls._latest_expected_market_day()

        required_start = None
        if required_start_date:
            required_start = datetime.strptime(required_start_date, '%Y-%m-%d').date() if isinstance(required_start_date, str) else required_start_date

        needs_sync = []
        for ticker in normalized:
            max_date = latest_by_ticker.get(ticker)
            if not max_date:
                needs_sync.append(ticker)
                continue

            max_dt = datetime.strptime(max_date, '%Y-%m-%d').date() if isinstance(max_date, str) else max_date
            if required_start and max_dt < required_start:
                needs_sync.append(ticker)
                continue

            if max_dt < expected_latest_day:
                needs_sync.append(ticker)

        return needs_sync

    @classmethod
    def sync_stock_history(cls, ticker, required_start_date=None):
        """
        Incremental sync of stock prices from yfinance to local DB.
        """
        logger = logging.getLogger(__name__)
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
        expected_latest_day = cls._latest_expected_market_day(today)
        
        # 2. Determine fetch start date
        required_start = None
        if required_start_date:
            required_start = datetime.strptime(required_start_date, '%Y-%m-%d').date() if isinstance(required_start_date, str) else required_start_date

        if max_date:
            if max_date >= expected_latest_day:
                logger.info("%s history already up to date (last_date=%s)", ticker, max_date.isoformat())
                return max_date_str
            fetch_start = max_date + timedelta(days=1)
        else:
            fetch_start = required_start or cls._default_history_start

        if fetch_start >= today:
            logger.info("Skipping %s history sync because start date %s is not before today", ticker, fetch_start.isoformat())
            return max_date_str

        logger.info("Syncing %s history from %s", ticker, fetch_start.isoformat())

        try:
            # 3. Fetch from yfinance (with retry)
            # Use fetch_start to today
            data = cls._normalize_yf_dataframe(
                cls._download_with_retry(ticker, start=fetch_start, interval="1d", threads=False)
            )

            if data is None or data.empty:
                logger.info("No new history data for %s from %s", ticker, fetch_start.isoformat())
                return max_date_str

            if 'Close' not in data.columns:
                logger.warning("No 'Close' column found for %s; skipping history sync", ticker)
                return max_date_str

            data = data.dropna(subset=['Close'])
            if data.empty:
                logger.info("No valid close prices found for %s from %s", ticker, fetch_start.isoformat())
                return max_date_str

            # 4. Save to DB (duplicate-safe)
            cursor = db.cursor()
            inserted_rows = 0
            for timestamp, row in data.iterrows():
                price_date = timestamp.date() if hasattr(timestamp, 'date') else pd.to_datetime(timestamp).date()
                price = cls._safe_float_from_value(row.get('Close'))
                if price is None:
                    continue

                cursor.execute(
                    '''INSERT OR IGNORE INTO stock_prices (ticker, date, close_price)
                       VALUES (?, ?, ?)''',
                    (ticker, price_date.isoformat(), round(price, 2))
                )
                inserted_rows += cursor.rowcount

            db.commit()

            if inserted_rows == 0:
                logger.info("%s history already up to date (last_date=%s)", ticker, max_date.isoformat() if max_date else 'none')
            else:
                logger.info("Inserted %s new history rows for %s", inserted_rows, ticker)

        except Exception as e:
            logger.error(f"Error processing yfinance data for {ticker}: {e}")
            db.rollback()

        # Return latest date in DB
        new_max = db.execute(
            'SELECT MAX(date) as max_date FROM stock_prices WHERE ticker = ?',
            (ticker,)
        ).fetchone()
        return new_max['max_date']

    @classmethod
    def fetch_metadata(cls, ticker, force_refresh=False):
        """
        Fetches company name, sector, and industry from yfinance.
        """
        if not ticker:
            return None

        ticker = ticker.strip().upper()
        now = datetime.now()

        if not force_refresh:
            cached = cls._metadata_cache.get(ticker)
            updated_at = cls._metadata_cache_updated_at.get(ticker)
            if cached and updated_at and (now - updated_at) <= cls._metadata_ttl:
                return cached

            db_cached = cls._load_metadata_from_db(ticker)
            if db_cached:
                return db_cached

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
            
            metadata = {
                'company_name': company_name,
                'sector': sector,
                'industry': industry,
                'currency': currency
            }
            cls._save_metadata_to_db(ticker, metadata)
            return metadata
        except Exception as e:
            print(f"Metadata fetch error for {ticker}: {e}")
            # Fallback to stale cache if available.
            stale_cached = cls._metadata_cache.get(ticker)
            if stale_cached:
                return stale_cached
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
                hist = cls._normalize_yf_dataframe(t.history(period="1y"))
                if hist is None or hist.empty or 'Close' not in hist.columns:
                     # Fallback if no history
                    quotes[ticker] = {
                        'price': 0.0,
                        'change_1d': None,
                        'change_7d': None,
                        'change_1m': None,
                        'change_1y': None
                    }
                    continue

                hist = hist.dropna(subset=['Close'])
                if hist.empty:
                    quotes[ticker] = {
                        'price': 0.0,
                        'change_1d': None,
                        'change_7d': None,
                        'change_1m': None,
                        'change_1y': None
                    }
                    continue

                # Get latest price
                current_price = cls._safe_float_from_value(hist['Close'].iloc[-1])
                if current_price is None:
                    raise ValueError(f"No valid latest close price for {ticker}")
                
                # Helper to calculate percentage change safely
                def calc_change(current, old):
                    if old == 0: return 0.0
                    return ((current - old) / old) * 100

                # 1D Change (compare with previous row)
                change_1d = None
                if len(hist) >= 2:
                    prev_close = cls._safe_float_from_value(hist['Close'].iloc[-2])
                    if prev_close is not None:
                        change_1d = calc_change(current_price, prev_close)

                # 7D Change (approx 5 trading days ago)
                change_7d = None
                if len(hist) >= 6:
                    price_7d_ago = cls._safe_float_from_value(hist['Close'].iloc[-6])
                    if price_7d_ago is not None:
                        change_7d = calc_change(current_price, price_7d_ago)

                # 1M Change (approx 21 trading days ago)
                change_1m = None
                if len(hist) >= 22:
                    price_1m_ago = cls._safe_float_from_value(hist['Close'].iloc[-22])
                    if price_1m_ago is not None:
                        change_1m = calc_change(current_price, price_1m_ago)

                # 1Y Change (approx start of the dataframe if it has enough data)
                change_1y = None
                # If we asked for 1y, the first row is roughly 1y ago
                if len(hist) > 0:
                     price_1y_ago = cls._safe_float_from_value(hist['Close'].iloc[0])
                     if price_1y_ago is not None:
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
                logger = logging.getLogger(__name__)
                logger.error(f"Error processing yfinance data for {ticker}: {e}")
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
                hist = cls._normalize_yf_dataframe(t.history(period="1y"))
                if hist is None or hist.empty or 'Close' not in hist.columns:
                    return {
                        "fundamentals": fundamentals,
                        "analyst": analyst,
                        "technicals": technicals
                    }

                hist = hist.dropna(subset=['Close'])

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
