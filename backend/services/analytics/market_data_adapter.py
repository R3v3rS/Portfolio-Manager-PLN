from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from flask import g, has_app_context

from backend.api.exceptions import ValidationError
from backend.database import get_db


class MarketDataAdapter:
    """Adapter for analytics-oriented market and holdings data reads."""

    _PERIOD_TO_DAYS: dict[str, int] = {
        "1mo": 31,
        "3mo": 93,
        "6mo": 186,
        "1y": 366,
        "2y": 731,
        "5y": 1827,
        "10y": 3653,
    }

    @classmethod
    def _db(cls):
        if has_app_context() and hasattr(g, "db"):
            return g.db
        return get_db()

    @classmethod
    def _normalize_tickers(cls, tickers: list[str]) -> list[str]:
        normalized = sorted({str(t).strip().upper() for t in tickers if t})
        if not normalized:
            raise ValidationError("tickers list cannot be empty")
        return normalized

    @classmethod
    def _period_start_date(cls, period: str) -> datetime | None:
        period_normalized = (period or "1y").strip().lower()
        if period_normalized == "max":
            return None
        if period_normalized == "ytd":
            return datetime(datetime.utcnow().year, 1, 1)
        days = cls._PERIOD_TO_DAYS.get(period_normalized)
        if days is None:
            raise ValidationError(
                "Unsupported period",
                details={"period": period, "supported": sorted([*cls._PERIOD_TO_DAYS.keys(), "max", "ytd"])},
            )
        return datetime.utcnow() - timedelta(days=days)

    @classmethod
    def _fetch_stock_prices_from_db(cls, tickers: list[str], period: str) -> pd.DataFrame:
        db = cls._db()
        placeholders = ",".join("?" for _ in tickers)
        params: list[Any] = list(tickers)
        start_dt = cls._period_start_date(period)

        query = f"""
            SELECT ticker, date, close_price
            FROM stock_prices
            WHERE ticker IN ({placeholders})
        """
        if start_dt is not None:
            query += " AND date >= ?"
            params.append(start_dt.date().isoformat())
        query += " ORDER BY ticker ASC, date ASC"

        rows = db.execute(query, tuple(params)).fetchall()
        if not rows:
            return pd.DataFrame(columns=["ticker", "date", "close_price"])

        return pd.DataFrame(
            [
                {
                    "ticker": row["ticker"],
                    "date": row["date"],
                    "close_price": row["close_price"],
                }
                for row in rows
            ]
        )

    @classmethod
    def _stale_or_missing_tickers(cls, tickers: list[str], db_prices: pd.DataFrame) -> list[str]:
        if db_prices.empty:
            return tickers

        latest_dates: dict[str, datetime] = {}
        for ticker in tickers:
            ticker_rows = db_prices[db_prices["ticker"] == ticker]
            if ticker_rows.empty:
                continue
            latest_dates[ticker] = pd.to_datetime(ticker_rows["date"]).max().to_pydatetime()

        freshness_cutoff = datetime.utcnow() - timedelta(hours=24)
        missing_or_stale = []
        for ticker in tickers:
            latest = latest_dates.get(ticker)
            if latest is None or latest < freshness_cutoff:
                missing_or_stale.append(ticker)
        return missing_or_stale

    @classmethod
    def _upsert_history_from_yfinance(cls, tickers: list[str], period: str) -> None:
        if not tickers:
            return

        db = cls._db()
        downloaded = yf.download(
            tickers=tickers,
            period=period,
            group_by="ticker",
            auto_adjust=False,
            threads=False,
            progress=False,
        )

        if downloaded is None or downloaded.empty:
            return

        for ticker in tickers:
            ticker_frame = None
            if isinstance(downloaded.columns, pd.MultiIndex):
                if ticker in downloaded.columns.levels[0]:
                    ticker_frame = downloaded[ticker]
            else:
                ticker_frame = downloaded

            if ticker_frame is None or ticker_frame.empty or "Close" not in ticker_frame.columns:
                continue

            closes = ticker_frame["Close"].dropna()
            if closes.empty:
                continue

            for idx, close_value in closes.items():
                db.execute(
                    """
                    INSERT INTO stock_prices (ticker, date, close_price)
                    VALUES (?, ?, ?)
                    ON CONFLICT(ticker, date) DO UPDATE SET close_price = excluded.close_price
                    """,
                    (
                        ticker,
                        pd.to_datetime(idx).date().isoformat(),
                        float(close_value),
                    ),
                )

        db.commit()

    @classmethod
    def get_historical_returns(cls, tickers: list[str], period: str = "1y") -> dict[str, pd.Series]:
        normalized_tickers = cls._normalize_tickers(tickers)

        db_prices = cls._fetch_stock_prices_from_db(normalized_tickers, period)
        tickers_to_refresh = cls._stale_or_missing_tickers(normalized_tickers, db_prices)
        if tickers_to_refresh:
            cls._upsert_history_from_yfinance(tickers_to_refresh, period)
            db_prices = cls._fetch_stock_prices_from_db(normalized_tickers, period)

        result: dict[str, pd.Series] = {}
        for ticker in normalized_tickers:
            ticker_rows = db_prices[db_prices["ticker"] == ticker].copy()
            if ticker_rows.empty:
                result[ticker] = pd.Series(dtype="float64")
                continue

            ticker_rows["date"] = pd.to_datetime(ticker_rows["date"])
            ticker_rows["close_price"] = pd.to_numeric(ticker_rows["close_price"], errors="coerce")
            ticker_rows = ticker_rows.dropna(subset=["close_price"]).sort_values("date")
            ticker_rows = ticker_rows.set_index("date")

            returns = np.log(ticker_rows["close_price"] / ticker_rows["close_price"].shift(1)).dropna()
            returns.name = ticker
            result[ticker] = returns

        return result

    @classmethod
    def get_holdings_snapshot(
        cls,
        portfolio_id: int,
        sub_portfolio_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if portfolio_id <= 0:
            raise ValidationError("portfolio_id must be a positive integer")

        db = cls._db()
        params: list[Any] = [portfolio_id]
        query = """
            SELECT ticker, quantity, average_buy_price, total_cost, sector, currency, sub_portfolio_id
            FROM holdings
            WHERE portfolio_id = ?
        """
        if sub_portfolio_id is not None:
            if sub_portfolio_id <= 0:
                raise ValidationError("sub_portfolio_id must be a positive integer when provided")
            query += " AND sub_portfolio_id = ?"
            params.append(sub_portfolio_id)

        rows = db.execute(query, tuple(params)).fetchall()
        if not rows:
            return []

        aggregated: dict[str, dict[str, Any]] = {}
        for row in rows:
            ticker = (row["ticker"] or "").strip().upper()
            if not ticker:
                continue

            quantity = float(row["quantity"] or 0)
            total_cost = float(row["total_cost"] or 0)
            avg_buy_price = float(row["average_buy_price"] or 0)

            if ticker not in aggregated:
                aggregated[ticker] = {
                    "ticker": ticker,
                    "quantity": 0.0,
                    "total_cost": 0.0,
                    "weighted_buy_value": 0.0,
                    "sector": row["sector"],
                    "currency": row["currency"],
                }

            aggregated[ticker]["quantity"] += quantity
            aggregated[ticker]["total_cost"] += total_cost
            aggregated[ticker]["weighted_buy_value"] += quantity * avg_buy_price

        tickers = sorted(aggregated.keys())
        placeholders = ",".join("?" for _ in tickers)
        price_rows = db.execute(
            f"SELECT ticker, price FROM price_cache WHERE ticker IN ({placeholders})",
            tuple(tickers),
        ).fetchall()
        price_map = {row["ticker"]: float(row["price"]) for row in price_rows if row["price"] is not None}

        position_values: dict[str, float] = {}
        for ticker, item in aggregated.items():
            current_price = price_map.get(ticker)
            current_value = item["quantity"] * current_price if current_price is not None else 0.0
            position_values[ticker] = current_value

        total_portfolio_value = sum(position_values.values())

        snapshot: list[dict[str, Any]] = []
        for ticker in tickers:
            item = aggregated[ticker]
            quantity = item["quantity"]
            average_buy_price = item["weighted_buy_value"] / quantity if quantity else 0.0
            current_value = position_values[ticker]
            weight = (current_value / total_portfolio_value) if total_portfolio_value > 0 else 0.0

            snapshot.append(
                {
                    "ticker": ticker,
                    "quantity": quantity,
                    "average_buy_price": average_buy_price,
                    "total_cost": item["total_cost"],
                    "sector": item["sector"],
                    "currency": item["currency"],
                    "weight": weight,
                }
            )

        return snapshot
