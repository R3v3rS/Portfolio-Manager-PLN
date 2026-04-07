from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from backend.services.analytics.market_data_adapter import MarketDataAdapter

TRADING_DAYS_PER_YEAR = 252


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.05) -> float | None:
    """Calculate annualized Sharpe ratio from daily log returns."""
    if returns is None:
        return None

    clean_returns = pd.to_numeric(returns, errors="coerce").dropna()
    if len(clean_returns) < 30:
        return None

    risk_free_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess_returns = clean_returns - risk_free_daily

    daily_std = float(excess_returns.std(ddof=1))
    if np.isclose(daily_std, 0.0):
        return None

    daily_mean = float(excess_returns.mean())
    return float((daily_mean / daily_std) * np.sqrt(TRADING_DAYS_PER_YEAR))


def max_drawdown(price_series: pd.Series) -> dict[str, Any]:
    """Calculate max drawdown and drawdown period metadata from a price/index series."""
    clean_prices = pd.to_numeric(price_series, errors="coerce")
    clean_prices.index = pd.to_datetime(clean_prices.index, errors="coerce")
    clean_prices = clean_prices[~clean_prices.index.isna()].sort_index().dropna()

    if clean_prices.empty:
        return {
            "value": 0.0,
            "start_date": "",
            "end_date": "",
            "recovery_date": None,
            "duration_days": 0,
        }

    running_peak = clean_prices.cummax()
    drawdowns = clean_prices / running_peak - 1.0

    trough_date = drawdowns.idxmin()
    max_dd_value = float(drawdowns.loc[trough_date])

    peak_to_trough_slice = clean_prices.loc[:trough_date]
    start_date = peak_to_trough_slice.idxmax()

    peak_value = float(clean_prices.loc[start_date])
    post_trough_prices = clean_prices.loc[trough_date:]
    recovered = post_trough_prices[post_trough_prices >= peak_value]
    recovery_date = recovered.index[0] if not recovered.empty else None

    if recovery_date is not None:
        duration_days = int((recovery_date - start_date).days)
    else:
        duration_days = int((trough_date - start_date).days)

    return {
        "value": max_dd_value,
        "start_date": start_date.date().isoformat(),
        "end_date": trough_date.date().isoformat(),
        "recovery_date": recovery_date.date().isoformat() if recovery_date is not None else None,
        "duration_days": max(duration_days, 0),
    }


def calculate_performance_summary(
    portfolio_id: int,
    sub_portfolio_id: int | None = None,
    period: str = "1y",
) -> dict[str, Any]:
    """Build risk/performance summary based on historical market returns and holding weights."""
    holdings_snapshot = MarketDataAdapter.get_holdings_snapshot(
        portfolio_id=portfolio_id,
        sub_portfolio_id=sub_portfolio_id,
    )

    if not holdings_snapshot:
        empty_prices = pd.Series(dtype="float64")
        return {
            "sharpe_ratio": None,
            "max_drawdown": max_drawdown(empty_prices),
            "volatility_annualized": 0.0,
            "best_day": {"date": "", "return": 0.0},
            "worst_day": {"date": "", "return": 0.0},
            "total_return_pct": 0.0,
            "period": period,
        }

    weights_map: dict[str, float] = {
        str(item.get("ticker", "")).upper(): float(item.get("weight") or 0.0)
        for item in holdings_snapshot
        if item.get("ticker")
    }
    tickers = [ticker for ticker, weight in weights_map.items() if weight > 0]

    if not tickers:
        empty_prices = pd.Series(dtype="float64")
        return {
            "sharpe_ratio": None,
            "max_drawdown": max_drawdown(empty_prices),
            "volatility_annualized": 0.0,
            "best_day": {"date": "", "return": 0.0},
            "worst_day": {"date": "", "return": 0.0},
            "total_return_pct": 0.0,
            "period": period,
        }

    historical_returns = MarketDataAdapter.get_historical_returns(tickers=tickers, period=period)

    aligned_returns: list[pd.Series] = []
    for ticker in tickers:
        series = historical_returns.get(ticker, pd.Series(dtype="float64"))
        series = pd.to_numeric(series, errors="coerce")
        series.name = ticker
        aligned_returns.append(series)

    if not aligned_returns:
        empty_prices = pd.Series(dtype="float64")
        return {
            "sharpe_ratio": None,
            "max_drawdown": max_drawdown(empty_prices),
            "volatility_annualized": 0.0,
            "best_day": {"date": "", "return": 0.0},
            "worst_day": {"date": "", "return": 0.0},
            "total_return_pct": 0.0,
            "period": period,
        }

    returns_df = pd.concat(aligned_returns, axis=1).sort_index()
    for ticker in tickers:
        if ticker not in returns_df.columns:
            returns_df[ticker] = np.nan

    weights = pd.Series({ticker: weights_map[ticker] for ticker in tickers}, dtype="float64")
    weighted_returns = returns_df[tickers].fillna(0.0).mul(weights, axis=1).sum(axis=1)
    weighted_returns = pd.to_numeric(weighted_returns, errors="coerce").dropna()

    if weighted_returns.empty:
        empty_prices = pd.Series(dtype="float64")
        return {
            "sharpe_ratio": None,
            "max_drawdown": max_drawdown(empty_prices),
            "volatility_annualized": 0.0,
            "best_day": {"date": "", "return": 0.0},
            "worst_day": {"date": "", "return": 0.0},
            "total_return_pct": 0.0,
            "period": period,
        }

    synthetic_price_index = np.exp(weighted_returns.cumsum())

    best_idx = weighted_returns.idxmax()
    worst_idx = weighted_returns.idxmin()

    total_return_pct = float((np.exp(weighted_returns.sum()) - 1.0) * 100.0)

    return {
        "sharpe_ratio": sharpe_ratio(weighted_returns),
        "max_drawdown": max_drawdown(synthetic_price_index),
        "volatility_annualized": float(weighted_returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)),
        "best_day": {
            "date": best_idx.date().isoformat(),
            "return": float(weighted_returns.loc[best_idx]),
        },
        "worst_day": {
            "date": worst_idx.date().isoformat(),
            "return": float(weighted_returns.loc[worst_idx]),
        },
        "total_return_pct": total_return_pct,
        "period": period,
    }
