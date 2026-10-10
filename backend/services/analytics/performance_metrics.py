from __future__ import annotations

from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

from services.analytics.market_data_adapter import MarketDataAdapter

TRADING_DAYS_PER_YEAR = 252
MIN_HISTORY_POINTS = 30


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.05) -> float | None:
    """Annualized Sharpe ratio of daily log returns."""
    if returns is None:
        return None
    clean = pd.to_numeric(returns, errors='coerce').dropna()
    if len(clean) < MIN_HISTORY_POINTS:
        return None
    excess = clean - np.log1p(risk_free_rate) / TRADING_DAYS_PER_YEAR
    std = float(excess.std(ddof=1))
    return None if np.isclose(std, 0) else float(excess.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR))


def max_drawdown(price_series: pd.Series) -> dict[str, Any]:
    prices = pd.to_numeric(price_series, errors='coerce').copy()
    prices.index = pd.to_datetime(prices.index, errors='coerce')
    prices = prices[~prices.index.isna()].sort_index().dropna()
    if prices.empty:
        return {'value': None, 'start_date': '', 'end_date': '', 'recovery_date': None, 'duration_days': 0}
    drawdowns = prices / prices.cummax() - 1
    trough = drawdowns.idxmin()
    peak = prices.loc[:trough].idxmax()
    recovered = prices.loc[trough:][prices.loc[trough:] >= prices.loc[peak]]
    recovery = recovered.index[0] if not recovered.empty else None
    return {
        'value': float(drawdowns.loc[trough]), 'start_date': peak.date().isoformat(),
        'end_date': trough.date().isoformat(),
        'recovery_date': recovery.date().isoformat() if recovery is not None else None,
        'duration_days': max(int(((recovery if recovery is not None else trough) - peak).days), 0),
    }


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> dict[str, Any]:
    """Historical/parametric VaR and CVaR, expressed as daily simple returns."""
    clean = pd.to_numeric(returns, errors='coerce').dropna()
    if clean.empty:
        return {'historical_var': None, 'parametric_var': None, 'cvar': None,
                'confidence_level': confidence, 'interpretation': 'Brak historii do oszacowania VaR.'}
    alpha = min(max(1 - float(confidence), 1e-6), 1 - 1e-6)
    historical = float(clean.quantile(alpha))
    mean, std = float(clean.mean()), float(clean.std(ddof=1))
    parametric = mean if np.isclose(std, 0) else mean + std * NormalDist().inv_cdf(alpha)
    tail = clean[clean <= historical]
    return {
        'historical_var': historical, 'parametric_var': float(parametric),
        'cvar': float(tail.mean()) if not tail.empty else historical, 'confidence_level': float(confidence),
        'interpretation': f'Jednodniowy VaR historyczny przy poziomie ufności {confidence:.0%}: {historical:.2%}.',
    }


def _weighted_returns(snapshot, period):
    """Current-weight basket; missing observations must not become zero returns."""
    weights = {item['ticker']: float(item.get('weight') or 0) for item in snapshot}
    tickers = sorted(weights)
    currencies = {item.get('currency') or 'PLN' for item in snapshot} - {'PLN'}
    history_tickers = sorted(set(tickers) | {f'{currency}PLN=X' for currency in currencies})
    historical = MarketDataAdapter.get_historical_returns(tickers=history_tickers, period=period)
    columns = []
    for item in snapshot:
        ticker = item['ticker']
        series = pd.to_numeric(historical.get(ticker, pd.Series(dtype='float64')), errors='coerce')
        currency = item.get('currency') or 'PLN'
        if currency != 'PLN':
            series = series + pd.to_numeric(historical.get(f'{currency}PLN=X', pd.Series(dtype='float64')),
                                           errors='coerce')
        columns.append(series.rename(ticker))
    frame = pd.concat(columns, axis=1).sort_index().replace([np.inf, -np.inf], np.nan)
    complete = frame.dropna(subset=tickers)
    # Weight simple asset returns, then convert the basket back to log returns.
    return np.log1p(np.expm1(complete).mul(pd.Series(weights), axis=1).sum(axis=1))


def _observed_period(returns, period):
    start = MarketDataAdapter._period_start_date(period)
    return {'observed_from': returns.index[0].date().isoformat() if len(returns) else None,
            'observed_to': returns.index[-1].date().isoformat() if len(returns) else None,
            'requested_from': start.date().isoformat() if start else None}


def _history_status(snapshot, returns):
    if not snapshot:
        return 'no_holdings'
    if any(not item.get('current_value_pln') for item in snapshot):
        return 'missing_prices'
    return 'ok' if len(returns) >= MIN_HISTORY_POINTS else 'insufficient_history'


def portfolio_var(portfolio_id: int, sub_portfolio_id: int | None = None, period: str = '1y') -> dict[str, Any]:
    snapshot = MarketDataAdapter.get_holdings_snapshot(portfolio_id, sub_portfolio_id)
    returns = (_weighted_returns(snapshot, period)
               if snapshot and all(item.get('current_value_pln') for item in snapshot)
               else pd.Series(dtype='float64'))
    status = _history_status(snapshot, returns)
    result = {
        'var_1d_pct': None, 'var_1d_pln': None, 'cvar_1d_pct': None, 'cvar_1d_pln': None,
        'portfolio_value': None, 'currency': 'PLN', 'period_used': period,
        'data_points': len(returns), 'data_status': status, **_observed_period(returns, period),
    }
    if status != 'ok':
        return result
    metrics = value_at_risk(np.expm1(returns))
    value = sum(item['current_value_pln'] for item in snapshot)
    result.update({
        'var_1d_pct': metrics['historical_var'], 'var_1d_pln': metrics['historical_var'] * value,
        'cvar_1d_pct': metrics['cvar'], 'cvar_1d_pln': metrics['cvar'] * value, 'portfolio_value': value,
    })
    return result


def calculate_performance_summary(portfolio_id: int, sub_portfolio_id: int | None = None,
                                  period: str = '1y') -> dict[str, Any]:
    snapshot = MarketDataAdapter.get_holdings_snapshot(portfolio_id, sub_portfolio_id)
    returns = (_weighted_returns(snapshot, period)
               if snapshot and all(item.get('current_value_pln') for item in snapshot)
               else pd.Series(dtype='float64'))
    status = _history_status(snapshot, returns)
    result = {
        'sharpe_ratio': None, 'max_drawdown': max_drawdown(pd.Series(dtype='float64')),
        'volatility_annualized': None, 'best_day': {'date': '', 'return': None},
        'worst_day': {'date': '', 'return': None}, 'total_return_pct': None,
        'period': period, 'data_points': len(returns), 'data_status': status, **_observed_period(returns, period),
        'risk_free_rate': 0.05, 'method': 'current_holdings_basket', 'drawdown_series': [],
    }
    if status != 'ok':
        return result
    prices = np.exp(returns.cumsum())
    # Include the initial unit value so a loss on the first observed day counts.
    prices.loc[prices.index[0] - pd.Timedelta(days=1)] = 1.0
    prices = prices.sort_index()
    drawdowns = prices / prices.cummax() - 1
    best, worst = returns.idxmax(), returns.idxmin()
    result.update({
        'sharpe_ratio': sharpe_ratio(returns), 'max_drawdown': max_drawdown(prices),
        'drawdown_series': [{'date': day.date().isoformat(), 'value': round(float(value) * 100, 4)} for day, value in drawdowns.items()],
        'volatility_annualized': float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)),
        'best_day': {'date': best.date().isoformat(), 'return': float(np.expm1(returns.loc[best]))},
        'worst_day': {'date': worst.date().isoformat(), 'return': float(np.expm1(returns.loc[worst]))},
        'total_return_pct': float(np.expm1(returns.sum()) * 100),
    })
    return result
