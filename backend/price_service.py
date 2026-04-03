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
import json
from collections import defaultdict, deque
from threading import Lock


logger = logging.getLogger("integrations.yfinance")

# Force yfinance to use a persistent cache directory to reuse cookies/crumbs
cache_dir = os.path.join(tempfile.gettempdir(), 'yfinance_cache_portfel')
if not os.path.exists(cache_dir):
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception as e:
        logger.warning("Failed to create cache dir %s: %s", cache_dir, e)
        # Fallback
        cache_dir = os.path.join(tempfile.gettempdir(), 'yfinance_cache_fallback')
        os.makedirs(cache_dir, exist_ok=True)

os.environ['YFINANCE_CACHE_DIR'] = cache_dir
logger.info("Using yfinance cache at: %s", cache_dir)

class PriceService:
    _price_cache = {}
    _price_cache_updated_at = {}
    _metadata_cache = {}
    _metadata_cache_updated_at = {}
    _metadata_ttl = timedelta(days=30)
    _default_history_start = date(2000, 1, 1)
    _supported_error_types = {
        "network_timeout",
        "rate_limit",
        "empty_data",
        "invalid_ticker",
        "parsing_error",
        "unknown",
    }
    _error_aggregation_window_seconds = 60
    _error_aggregation_threshold = 10
    _error_aggregation_summary_interval_seconds = 10
    _error_occurrences = defaultdict(deque)
    _error_aggregation_last_summary = {}
    _error_aggregation_lock = Lock()

    @staticmethod
    def _is_env_flag_enabled(value):
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _verbose_provider_logs_enabled(cls):
        return cls._is_env_flag_enabled(os.getenv("VERBOSE_PROVIDER_LOGS", "false"))

    @classmethod
    def _log_verbose_provider_event(cls, **kwargs):
        if not cls._verbose_provider_logs_enabled():
            return
        payload = dict(kwargs)
        payload["level"] = payload.get("level", logging.DEBUG)
        cls._log_provider_event(**payload)

    @classmethod
    def _build_aggregated_error_payload(cls, error_type):
        now = time.monotonic()
        with cls._error_aggregation_lock:
            bucket = cls._error_occurrences[error_type]
            bucket.append(now)
            window_start = now - cls._error_aggregation_window_seconds
            while bucket and bucket[0] < window_start:
                bucket.popleft()

            count = len(bucket)
            if count <= cls._error_aggregation_threshold:
                return None

            last_summary_at = cls._error_aggregation_last_summary.get(error_type)
            should_emit = (
                last_summary_at is None
                or (now - last_summary_at) >= cls._error_aggregation_summary_interval_seconds
            )
            if not should_emit:
                return {"suppress": True}

            cls._error_aggregation_last_summary[error_type] = now
            return {
                "suppress": True,
                "count": count,
                "window_seconds": cls._error_aggregation_window_seconds,
            }

    @staticmethod
    def _safe_error_message(exc, max_len=300):
        if exc is None:
            return None
        try:
            message = str(exc)
        except Exception:
            message = repr(exc)
        if not message:
            return None
        return message[:max_len]

    @staticmethod
    def _classify_error(exc):
        if exc is None:
            return "unknown"

        exc_name = exc.__class__.__name__.lower()
        exc_message = (PriceService._safe_error_message(exc, max_len=1000) or "").lower()
        combined = f"{exc_name} {exc_message}"

        if "timeout" in combined:
            return "network_timeout"
        if "rate" in combined and "limit" in combined:
            return "rate_limit"
        if "too many requests" in combined or "http 429" in combined:
            return "rate_limit"
        if "empty" in combined and ("data" in combined or "frame" in combined):
            return "empty_data"
        if "no data" in combined or "possibly delisted" in combined:
            return "empty_data"
        if "invalid ticker" in combined or "not found" in combined:
            return "invalid_ticker"
        if "parser" in combined or "parse" in combined:
            return "parsing_error"
        if "jsondecodeerror" in combined:
            return "parsing_error"

        # unknown must stay as the last branch so that no exception
        # can "fall through" outside the controlled classification set.
        return "unknown"

    @classmethod
    def _log_provider_event(
        cls,
        *,
        level,
        operation,
        status,
        ticker=None,
        tickers_count=None,
        attempt=None,
        max_attempts=None,
        duration_ms=None,
        error=None,
        request_id=None,
        trace_id=None,
        message=None,
    ):
        payload = {
            "provider": "yfinance",
            "operation": operation,
            "status": status,
            "ticker": ticker,
            "tickers_count": tickers_count,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "duration_ms": duration_ms,
            "error_type": (cls._classify_error(error) if error else None),
            "error_message": (cls._safe_error_message(error, max_len=300) if error else None),
            "request_id": request_id,
            "trace_id": trace_id,
            "message": message,
        }
        if payload.get("error_type") and payload["error_type"] not in cls._supported_error_types:
            payload["error_type"] = "unknown"
        error_type = payload.get("error_type")
        should_aggregate = (
            not cls._verbose_provider_logs_enabled()
            and level >= logging.WARNING
            and error_type is not None
        )
        if should_aggregate:
            aggregated = cls._build_aggregated_error_payload(error_type)
            if aggregated is not None:
                if aggregated.get("count") is not None:
                    summary_payload = {
                        "provider": "yfinance",
                        "operation": "provider_errors.aggregate",
                        "status": "warning",
                        "error_type": error_type,
                        "tickers_count": tickers_count,
                        "message": f"{error_type} x{aggregated['count']} in last {aggregated['window_seconds']}s",
                    }
                    logger.warning(json.dumps(summary_payload, ensure_ascii=False))
                if aggregated.get("suppress"):
                    return
        cleaned_payload = {k: v for k, v in payload.items() if v is not None}
        logger.log(level, json.dumps(cleaned_payload, ensure_ascii=False))

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
    def _load_metadata_from_db(cls, ticker, allow_stale=False):
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

        is_stale = (datetime.now() - updated_dt) > cls._metadata_ttl
        if is_stale and not allow_stale:
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
        operation = kwargs.pop("operation", "download")
        ticker = kwargs.get("tickers")
        if not ticker and args:
            ticker = args[0]
        tickers_count = len(ticker) if isinstance(ticker, (list, tuple, set)) else None
        for attempt in range(1, attempts + 1):
            started_at = time.perf_counter()
            cls._log_provider_event(
                level=logging.INFO,
                operation=operation,
                status="start",
                ticker=ticker if isinstance(ticker, str) else None,
                tickers_count=tickers_count,
                attempt=attempt,
                max_attempts=attempts,
                duration_ms=0.0,
                message="Starting download attempt",
            )
            try:
                result = yf.download(*args, **kwargs)
                cls._log_provider_event(
                    level=logging.INFO,
                    operation=operation,
                    status="success",
                    ticker=ticker if isinstance(ticker, str) else None,
                    tickers_count=tickers_count,
                    attempt=attempt,
                    max_attempts=attempts,
                    duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                )
                return result
            except Exception as e:
                cls._log_provider_event(
                    level=logging.WARNING if attempt < attempts else logging.ERROR,
                    operation=operation,
                    status="retry" if attempt < attempts else "failed",
                    ticker=ticker if isinstance(ticker, str) else None,
                    tickers_count=tickers_count,
                    attempt=attempt,
                    max_attempts=attempts,
                    duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                    error=e,
                )
                if attempt == attempts:
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
            fallback_reason = None
            cls._log_provider_event(
                level=logging.INFO,
                operation="get_prices.bulk",
                status="start",
                tickers_count=len(missing_tickers),
                message="Fetching missing tickers in bulk",
            )
            
            # Attempt 1: Bulk Download
            try:
                # Fetch 5 days of data to handle weekends/holidays/gaps (with retry)
                data = cls._download_with_retry(
                    missing_tickers,
                    period="5d",
                    group_by='ticker',
                    threads=False,
                    operation="get_prices.bulk_download",
                )

                if data.empty:
                    cls._log_provider_event(
                        level=logging.WARNING,
                        operation="get_prices.bulk",
                        status="retry",
                        tickers_count=len(missing_tickers),
                        message="Bulk download returned empty data; falling back to per-ticker",
                    )
                    fallback_reason = "bulk_empty_data"
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
                        cls._log_provider_event(
                            level=logging.ERROR,
                            operation="get_prices.bulk_process",
                            status="failed",
                            ticker=ticker,
                            error=e,
                        )

            except Exception as e:
                fallback_reason = fallback_reason or "bulk_exception"
                cls._log_provider_event(
                    level=logging.WARNING,
                    operation="get_prices.bulk",
                    status="retry",
                    tickers_count=len(missing_tickers),
                    error=e,
                    message="Bulk fetch failed, switching to individual fallback",
                )
            
            # Attempt 2: Individual Fetch (Fallback for any still missing)
            remaining_tickers = [t for t in missing_tickers if t not in cls._price_cache]
            if remaining_tickers:
                fallback_reason = fallback_reason or "bulk_partial_result"
                fallback_started_at = time.perf_counter()
                cls._log_provider_event(
                    level=logging.WARNING,
                    operation="get_prices.fallback",
                    status="start",
                    tickers_count=len(remaining_tickers),
                    message=f"Switching from bulk to per-ticker fallback; reason={fallback_reason}",
                )
                fallback_success_count = 0
                for ticker in remaining_tickers:
                    try:
                        fallback_ticker_succeeded = False
                        cls._log_verbose_provider_event(
                            operation="get_prices.fallback_ticker",
                            status="start",
                            ticker=ticker,
                            message="Per-ticker fallback started",
                        )
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
                                fallback_ticker_succeeded = True
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
                                    fallback_ticker_succeeded = True
                            except Exception as fast_info_error:
                                cls._log_provider_event(
                                    level=logging.WARNING,
                                    operation="get_prices.fast_info",
                                    status="failed",
                                    ticker=ticker,
                                    error=fast_info_error,
                                    message="No data from history and fast_info fallback",
                                )
                        if fallback_ticker_succeeded:
                            fallback_success_count += 1
                            cls._log_verbose_provider_event(
                                operation="get_prices.fallback_ticker",
                                status="success",
                                ticker=ticker,
                                message="Per-ticker fallback succeeded",
                            )
                        else:
                            cls._log_verbose_provider_event(
                                operation="get_prices.fallback_ticker",
                                status="failed",
                                ticker=ticker,
                                message="Per-ticker fallback returned no price",
                            )
                    except Exception as e:
                        cls._log_provider_event(
                            level=logging.ERROR,
                            operation="get_prices.fallback_process",
                            status="failed",
                            ticker=ticker,
                            error=e,
                        )
                fallback_failed_count = len(remaining_tickers) - fallback_success_count
                fallback_duration_ms = round((time.perf_counter() - fallback_started_at) * 1000, 2)
                fallback_status = (
                    "success"
                    if fallback_failed_count == 0
                    else ("failed" if fallback_success_count == 0 else "partial")
                )
                cls._log_provider_event(
                    level=logging.INFO if fallback_status == "success" else logging.WARNING,
                    operation="get_prices.fallback",
                    status=fallback_status,
                    tickers_count=len(remaining_tickers),
                    duration_ms=fallback_duration_ms,
                    message=(
                        "Per-ticker fallback completed: "
                        f"success={fallback_success_count}, failed={fallback_failed_count}, "
                        f"reason={fallback_reason}"
                    ),
                )

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
            holdings = db.execute(
                """
                SELECT DISTINCT ticker
                FROM holdings
                WHERE ticker IS NOT NULL
                  AND ticker != 'CASH'
                """
            ).fetchall()
            tickers = [h['ticker'] for h in holdings]
            if tickers:
                cls._log_verbose_provider_event(
                    operation="warmup_cache",
                    status="start",
                    tickers_count=len(tickers),
                    message="Warming up price cache",
                )
                cls.get_prices(tickers)
        except Exception as e:
            cls._log_provider_event(
                level=logging.WARNING,
                operation="warmup_cache",
                status="failed",
                error=e,
            )

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
            f'''SELECT ticker, MIN(date) as min_date, MAX(date) as max_date
                FROM stock_prices
                WHERE ticker IN ({placeholders})
                GROUP BY ticker''',
            tuple(normalized)
        ).fetchall()
        
        db_ranges = {row['ticker']: (row['min_date'], row['max_date']) for row in rows}

        expected_latest_day = cls._latest_expected_market_day()

        required_start = None
        if required_start_date:
            required_start = datetime.strptime(required_start_date, '%Y-%m-%d').date() if isinstance(required_start_date, str) else required_start_date

        needs_sync = []
        for ticker in normalized:
            db_range = db_ranges.get(ticker)
            if not db_range:
                needs_sync.append(ticker)
                continue

            min_date, max_date = db_range
            min_dt = datetime.strptime(min_date, '%Y-%m-%d').date() if isinstance(min_date, str) else min_date
            max_dt = datetime.strptime(max_date, '%Y-%m-%d').date() if isinstance(max_date, str) else max_date

            # If we need earlier data than what we have
            if required_start and min_dt > required_start:
                needs_sync.append(ticker)
                continue

            # If we need newer data than what we have
            if max_dt < expected_latest_day:
                needs_sync.append(ticker)

        return needs_sync

    @classmethod
    def sync_stock_history(cls, ticker, required_start_date=None):
        """
        Incremental sync of stock prices from yfinance to local DB.
        """
        db = get_db()
        
        # 1. Find the date range available in DB
        result = db.execute(
            'SELECT MIN(date) as min_date, MAX(date) as max_date FROM stock_prices WHERE ticker = ?',
            (ticker,)
        ).fetchone()
        
        max_date_str = result['max_date']
        min_date_str = result['min_date']
        max_date = None
        min_date = None
        
        if max_date_str:
            if isinstance(max_date_str, str):
                max_date = datetime.strptime(max_date_str, '%Y-%m-%d').date()
            else:
                max_date = max_date_str
        
        if min_date_str:
            if isinstance(min_date_str, str):
                min_date = datetime.strptime(min_date_str, '%Y-%m-%d').date()
            else:
                min_date = min_date_str

        today = date.today()
        expected_latest_day = cls._latest_expected_market_day(today)
        
        # 2. Determine fetch start date
        required_start = None
        if required_start_date:
            required_start = datetime.strptime(required_start_date, '%Y-%m-%d').date() if isinstance(required_start_date, str) else required_start_date

        if max_date:
            # Refresh a short recent window even when history looks up to date.
            # This heals occasional bad rows caused by vendor corrections/data glitches.
            recent_refresh_start = max_date - timedelta(days=7)

            # If we need earlier data than what we have, start from the required date.
            if required_start and (min_date is None or required_start < min_date):
                fetch_start = required_start
            # If we are up to date, still refresh the latest days using UPSERT.
            elif max_date >= expected_latest_day:
                fetch_start = recent_refresh_start
            # Otherwise fetch from where we left off, but include a short overlap to self-heal.
            else:
                fetch_start = max(max_date + timedelta(days=1), recent_refresh_start)
        else:
            fetch_start = required_start or cls._default_history_start

        if fetch_start >= today:
            cls._log_provider_event(
                level=logging.INFO,
                operation="sync_stock_history",
                status="success",
                ticker=ticker,
                message=f"Skipping sync because start date {fetch_start.isoformat()} is not before today",
            )
            return max_date_str

        cls._log_provider_event(
            level=logging.INFO,
            operation="sync_stock_history",
            status="start",
            ticker=ticker,
            message=f"Syncing history from {fetch_start.isoformat()}",
        )

        try:
            # 3. Fetch from yfinance (with retry)
            # Use fetch_start to today
            data = cls._normalize_yf_dataframe(
                cls._download_with_retry(
                    ticker,
                    start=fetch_start,
                    interval="1d",
                    threads=False,
                    operation="sync_stock_history.download",
                )
            )

            if data is None or data.empty:
                cls._log_provider_event(
                    level=logging.INFO,
                    operation="sync_stock_history",
                    status="success",
                    ticker=ticker,
                    message=f"No new history data from {fetch_start.isoformat()}",
                )
                return max_date_str

            if 'Close' not in data.columns:
                cls._log_provider_event(
                    level=logging.WARNING,
                    operation="sync_stock_history",
                    status="failed",
                    ticker=ticker,
                    message="No 'Close' column found; skipping history sync",
                )
                return max_date_str

            data = data.dropna(subset=['Close'])
            if data.empty:
                cls._log_provider_event(
                    level=logging.INFO,
                    operation="sync_stock_history",
                    status="success",
                    ticker=ticker,
                    message=f"No valid close prices from {fetch_start.isoformat()}",
                )
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
                    '''INSERT INTO stock_prices (ticker, date, close_price)
                       VALUES (?, ?, ?)
                       ON CONFLICT(ticker, date)
                       DO UPDATE SET close_price = excluded.close_price''',
                    (ticker, price_date.isoformat(), round(price, 2))
                )
                inserted_rows += cursor.rowcount

            db.commit()

            if inserted_rows == 0:
                cls._log_provider_event(
                    level=logging.INFO,
                    operation="sync_stock_history",
                    status="success",
                    ticker=ticker,
                    message=f"History already up to date (last_date={max_date.isoformat() if max_date else 'none'})",
                )
            else:
                cls._log_provider_event(
                    level=logging.INFO,
                    operation="sync_stock_history",
                    status="success",
                    ticker=ticker,
                    message=f"Inserted {inserted_rows} new history rows",
                )

        except Exception as e:
            cls._log_provider_event(
                level=logging.ERROR,
                operation="sync_stock_history",
                status="failed",
                ticker=ticker,
                error=e,
            )
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

        stale_db_cached = None

        if not force_refresh:
            cached = cls._metadata_cache.get(ticker)
            updated_at = cls._metadata_cache_updated_at.get(ticker)
            if cached and updated_at and (now - updated_at) <= cls._metadata_ttl:
                cls._log_verbose_provider_event(
                    operation="fetch_metadata",
                    status="success",
                    ticker=ticker,
                    message="Metadata cache hit (memory)",
                )
                return cached

            db_cached = cls._load_metadata_from_db(ticker)
            if db_cached:
                cls._log_verbose_provider_event(
                    operation="fetch_metadata",
                    status="success",
                    ticker=ticker,
                    message="Metadata cache hit (db)",
                )
                return db_cached

            stale_db_cached = cls._load_metadata_from_db(ticker, allow_stale=True)

        try:
            cls._log_provider_event(
                level=logging.INFO,
                operation="fetch_metadata",
                status="start",
                ticker=ticker,
                message="Fetching metadata from Yahoo",
            )
            t = yf.Ticker(ticker)
            info = t.info
            if not isinstance(info, dict) or not info:
                raise ValueError("Empty or invalid metadata response")
            
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
            cls._log_provider_event(
                level=logging.INFO,
                operation="fetch_metadata",
                status="success",
                ticker=ticker,
                message="Metadata refreshed from Yahoo" if stale_db_cached else "Metadata fetched from Yahoo",
            )
            return metadata
        except Exception as e:
            cls._log_provider_event(
                level=logging.WARNING,
                operation="fetch_metadata",
                status="failed",
                ticker=ticker,
                error=e,
            )
            # Fallback to stale in-memory cache if available.
            stale_cached = cls._metadata_cache.get(ticker)
            if stale_cached:
                cls._log_provider_event(
                    level=logging.WARNING,
                    operation="fetch_metadata",
                    status="partial",
                    ticker=ticker,
                    message="Using stale in-memory metadata fallback",
                )
                return stale_cached
            # Fallback to stale DB cache if available.
            if stale_db_cached:
                cls._log_provider_event(
                    level=logging.WARNING,
                    operation="fetch_metadata",
                    status="partial",
                    ticker=ticker,
                    message="Using stale DB metadata fallback",
                )
                return stale_db_cached
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
            
        normalized_tickers = sorted({str(t).strip().upper() for t in tickers if t})
        
        # Try bulk download first for efficiency
        try:
            # Fetch 1 year of history for all tickers at once
            data = cls._download_with_retry(
                normalized_tickers,
                period="1y",
                group_by='ticker',
                threads=False,
                operation="get_quotes.bulk_download",
            )
            
            for ticker in normalized_tickers:
                try:
                    ticker_df = None
                    if isinstance(data.columns, pd.MultiIndex):
                        if ticker in data.columns.levels[0]:
                            ticker_df = data[ticker]
                    elif 'Close' in data.columns and len(normalized_tickers) == 1:
                        ticker_df = data

                    ticker_df = cls._normalize_yf_dataframe(ticker_df)
                    if ticker_df is None or ticker_df.empty or 'Close' not in ticker_df.columns:
                        quotes[ticker] = {
                            'price': 0.0,
                            'change_1d': None,
                            'change_7d': None,
                            'change_1m': None,
                            'change_1y': None,
                            'prev_close': None,
                            'price_7d_ago': None
                        }
                        continue

                    hist = ticker_df.dropna(subset=['Close'])
                    if hist.empty:
                        quotes[ticker] = {
                            'price': 0.0,
                            'change_1d': None,
                            'change_7d': None,
                            'change_1m': None,
                            'change_1y': None,
                            'prev_close': None,
                            'price_7d_ago': None
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
                    prev_close = None
                    if len(hist) >= 2:
                        prev_close = cls._safe_float_from_value(hist['Close'].iloc[-2])
                        if prev_close is not None:
                            change_1d = calc_change(current_price, prev_close)

                    # 7D Change (approx 5 trading days ago)
                    change_7d = None
                    price_7d_ago = None
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
                        'prev_close': round(float(prev_close), 2) if prev_close is not None else None,
                        'price_7d_ago': round(float(price_7d_ago), 2) if price_7d_ago is not None else None,
                    }
                    
                    # Update cache
                    cls._price_cache[ticker] = round(float(current_price), 2)
                    cls._price_cache_updated_at[ticker] = datetime.now().isoformat(timespec='seconds')
                except Exception as e:
                    cls._log_provider_event(
                        level=logging.ERROR,
                        operation="get_quotes.bulk_process",
                        status="failed",
                        ticker=ticker,
                        error=e,
                    )
                    quotes[ticker] = {
                        'price': 0.0,
                        'change_1d': None,
                        'change_7d': None,
                        'change_1m': None,
                        'change_1y': None,
                        'prev_close': None,
                        'price_7d_ago': None
                    }

        except Exception as e:
            cls._log_provider_event(
                level=logging.ERROR,
                operation="get_quotes.bulk",
                status="failed",
                tickers_count=len(normalized_tickers),
                error=e,
            )
            # Fallback to individual if bulk fails
            for ticker in normalized_tickers:
                if ticker not in quotes:
                    cls._log_verbose_provider_event(
                        operation="get_quotes.fallback_ticker",
                        status="start",
                        ticker=ticker,
                        message="Bulk quotes failed; individual fallback placeholder",
                    )
                    # ... (rest of individual fetch logic if needed, but bulk usually works or everything fails)
                    pass
        
        return quotes

    @classmethod
    def get_cached_radar_data(cls, tickers):
        if not tickers:
            return {}

        placeholders = ','.join(['?'] * len(tickers))
        db = get_db()
        rows = db.execute(
            f'''SELECT ticker, price, change_1d, change_7d, change_1m, change_1y,
                       next_earnings, ex_dividend_date, dividend_yield, score, last_updated_at
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
                'score': row['score'],
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
            
            # Fetch score if not already present or needs refresh
            analysis = cls.get_stock_analysis(ticker)
            score = analysis.get('score') if analysis else None

            db.execute(
                '''INSERT INTO radar_cache
                   (ticker, price, change_1d, change_7d, change_1m, change_1y,
                    next_earnings, ex_dividend_date, dividend_yield, score, last_updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ticker) DO UPDATE SET
                     price = excluded.price,
                     change_1d = excluded.change_1d,
                     change_7d = excluded.change_7d,
                     change_1m = excluded.change_1m,
                     change_1y = excluded.change_1y,
                     next_earnings = excluded.next_earnings,
                     ex_dividend_date = excluded.ex_dividend_date,
                     dividend_yield = excluded.dividend_yield,
                     score = excluded.score,
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
                    score,
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
                    cls._log_provider_event(
                        level=logging.WARNING,
                        operation="fetch_market_events.calendar",
                        status="failed",
                        ticker=ticker,
                        error=e,
                    )

                # 2. Try Info for everything else (and fallback for earnings)
                try:
                    info = t.info
                    
                    if not next_earnings and info.get('earningsTimestamp'):
                         next_earnings = datetime.fromtimestamp(info['earningsTimestamp']).strftime('%Y-%m-%d')
                    
                    if info.get('exDividendDate'):
                         ex_dividend_date = datetime.fromtimestamp(info['exDividendDate']).strftime('%Y-%m-%d')
                    
                    dividend_yield = info.get('dividendYield')
                    
                except Exception as e:
                    cls._log_provider_event(
                        level=logging.WARNING,
                        operation="fetch_market_events.info",
                        status="failed",
                        ticker=ticker,
                        error=e,
                    )

                events[ticker] = {
                    "next_earnings": next_earnings,
                    "ex_dividend_date": ex_dividend_date,
                    "dividend_yield": dividend_yield
                }
            except Exception as e:
                cls._log_provider_event(
                    level=logging.ERROR,
                    operation="fetch_market_events",
                    status="failed",
                    ticker=ticker,
                    error=e,
                )
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
            cls._log_verbose_provider_event(
                operation="get_stock_analysis",
                status="start",
                ticker=ticker,
                message="Starting stock analysis",
            )
            t = yf.Ticker(ticker)
            info = t.info
            
            # Helper to safely get value
            def get_val(key, default=None):
                val = info.get(key)
                return val if val is not None and val != 'null' else default

            # 1. Fundamentals & Quality
            fundamentals = {
                "trailingPE": get_val("trailingPE"),
                "priceToBook": get_val("priceToBook"),
                "returnOnEquity": get_val("returnOnEquity"),
                "payoutRatio": get_val("payoutRatio"),
                "operatingMargins": get_val("operatingMargins"),
                "profitMargins": get_val("profitMargins"),
                "returnOnAssets": get_val("returnOnAssets"),
                "freeCashflow": get_val("freeCashflow"),
                "operatingCashflow": get_val("operatingCashflow")
            }

            # 2. Growth
            growth = {
                "revenueGrowth": get_val("revenueGrowth"),
                "earningsGrowth": get_val("earningsGrowth"),
                "earningsQuarterlyGrowth": get_val("earningsQuarterlyGrowth")
            }

            # 3. Risk & Stability
            risk = {
                "debtToEquity": get_val("debtToEquity"),
                "currentRatio": get_val("currentRatio"),
                "quickRatio": get_val("quickRatio"),
                "beta": get_val("beta")
            }

            # 4. Market & Sentiment
            market = {
                "heldPercentInstitutions": get_val("heldPercentInstitutions"),
                "heldPercentInsiders": get_val("heldPercentInsiders"),
                "shortPercentOfFloat": get_val("shortPercentOfFloat"),
                "shortRatio": get_val("shortRatio"),
                "averageVolume": get_val("averageVolume"),
                "volume": get_val("volume"),
                "fiftyTwoWeekLow": get_val("fiftyTwoWeekLow"),
                "fiftyTwoWeekHigh": get_val("fiftyTwoWeekHigh")
            }

            # 5. Analyst Consensus
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

            # 6. Scoring Logic
            # Returns a dict with "score" (0-100) and sub-scores
            def calculate_score(f, g, r):
                q_score = 0
                g_score = 0
                r_score = 0
                
                # Quality (max 40)
                if (f.get("returnOnEquity") or 0) > 0.15: q_score += 15
                elif (f.get("returnOnEquity") or 0) > 0.10: q_score += 10
                
                if (f.get("profitMargins") or 0) > 0.10: q_score += 15
                elif (f.get("profitMargins") or 0) > 0.05: q_score += 10
                
                if (f.get("freeCashflow") or 0) > 0: q_score += 10
                
                # Growth (max 30)
                if (g.get("revenueGrowth") or 0) > 0.15: g_score += 15
                elif (g.get("revenueGrowth") or 0) > 0.05: g_score += 10
                
                if (g.get("earningsGrowth") or 0) > 0.15: g_score += 15
                elif (g.get("earningsGrowth") or 0) > 0.05: g_score += 10
                
                # Risk (max 30) - lower is better for debt/beta, higher for current ratio
                d_e = r.get("debtToEquity")
                if d_e is not None:
                    if d_e < 80: r_score += 10 # yfinance debtToEquity is often in percent (e.g. 80.0 means 0.8)
                    elif d_e < 150: r_score += 5
                else: r_score += 5 # neutral if missing
                
                c_r = r.get("currentRatio")
                if c_r is not None:
                    if c_r > 1.5: r_score += 10
                    elif c_r > 1.0: r_score += 5
                else: r_score += 5
                
                beta = r.get("beta")
                if beta is not None:
                    if beta < 1.0: r_score += 10
                    elif beta < 1.3: r_score += 5
                else: r_score += 5
                
                total = q_score + g_score + r_score
                return total, {"quality": q_score, "growth": g_score, "risk": r_score}

            total_score, score_details = calculate_score(fundamentals, growth, risk)

            # 7. Technicals
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
                        "score": total_score,
                        "details": score_details,
                        "fundamentals": fundamentals,
                        "growth": growth,
                        "risk": risk,
                        "market": market,
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
                    
                    rs = gain / loss.replace(0, float('nan'))
                    hist['RSI'] = 100 - (100 / (1 + rs))
                    
                    # Handle division by zero or NaN if loss is 0
                    technicals["rsi14"] = hist['RSI'].iloc[-1]
                    
                    # Cleanup NaN/Infinite values just in case
                    if pd.isna(technicals["rsi14"]): technicals["rsi14"] = None
                    if pd.isna(technicals["sma50"]): technicals["sma50"] = None
                    if pd.isna(technicals["sma200"]): technicals["sma200"] = None

            except Exception as e:
                cls._log_provider_event(
                    level=logging.WARNING,
                    operation="get_stock_analysis.technicals",
                    status="partial",
                    ticker=ticker,
                    error=e,
                )

            return {
                "score": total_score,
                "details": score_details,
                "fundamentals": fundamentals,
                "growth": growth,
                "risk": risk,
                "market": market,
                "analyst": analyst,
                "technicals": technicals
            }

        except Exception as e:
            cls._log_provider_event(
                level=logging.ERROR,
                operation="get_stock_analysis",
                status="failed",
                ticker=ticker,
                error=e,
            )
            return None

    @classmethod
    def audit_price_history_quality(cls, days=30, jump_threshold_percent=25.0, refresh_flagged=False):
        """
        Checks recent price history quality and flags suspicious day-over-day jumps.
        Optionally refreshes flagged tickers from the provider and re-evaluates.
        """
        db = get_db()
        days = max(2, min(int(days), 365))
        jump_threshold_percent = max(1.0, float(jump_threshold_percent))

        active_tickers = [
            row['ticker']
            for row in db.execute(
                "SELECT DISTINCT ticker FROM holdings WHERE ticker IS NOT NULL AND ticker != 'CASH'"
            ).fetchall()
        ]
        if not active_tickers:
            return {
                'days': days,
                'jump_threshold_percent': jump_threshold_percent,
                'flagged_count': 0,
                'flagged_tickers': [],
                'issues': [],
                'refreshed_tickers': [],
            }

        def _scan_once():
            issues = []
            flagged = set()
            for ticker in active_tickers:
                rows = db.execute(
                    '''SELECT date, close_price
                       FROM stock_prices
                       WHERE ticker = ?
                       ORDER BY date DESC
                       LIMIT ?''',
                    (ticker, days + 1)
                ).fetchall()
                if len(rows) < 2:
                    continue

                # Iterate from oldest to newest for stable comparisons.
                ordered = list(reversed(rows))
                for idx in range(1, len(ordered)):
                    previous = float(ordered[idx - 1]['close_price'] or 0.0)
                    current = float(ordered[idx]['close_price'] or 0.0)
                    if previous <= 0:
                        continue
                    change_percent = ((current - previous) / previous) * 100.0
                    if abs(change_percent) >= jump_threshold_percent:
                        issue = {
                            'ticker': ticker,
                            'date': str(ordered[idx]['date']),
                            'previous_date': str(ordered[idx - 1]['date']),
                            'previous_close': round(previous, 4),
                            'close': round(current, 4),
                            'change_percent': round(change_percent, 2),
                        }
                        issues.append(issue)
                        flagged.add(ticker)
            issues.sort(key=lambda item: abs(item['change_percent']), reverse=True)
            return issues, sorted(flagged)

        issues, flagged_tickers = _scan_once()
        refreshed_tickers = []

        if refresh_flagged and flagged_tickers:
            for ticker in flagged_tickers:
                try:
                    cls.sync_stock_history(ticker)
                    refreshed_tickers.append(ticker)
                except Exception as exc:
                    cls._log_provider_event(
                        level=logging.WARNING,
                        operation="audit_price_history_quality.refresh",
                        status="failed",
                        ticker=ticker,
                        error=exc,
                    )
            # Re-run scan after refresh.
            issues, flagged_tickers = _scan_once()

        return {
            'days': days,
            'jump_threshold_percent': jump_threshold_percent,
            'flagged_count': len(flagged_tickers),
            'flagged_tickers': flagged_tickers,
            'issues': issues,
            'refreshed_tickers': refreshed_tickers,
        }
