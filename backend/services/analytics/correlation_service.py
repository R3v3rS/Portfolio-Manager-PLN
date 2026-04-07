from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from services.analytics.market_data_adapter import MarketDataAdapter

CORRELATION_CLUSTER_THRESHOLD = 0.75


def _normalize_tickers(tickers: list[str]) -> list[str]:
    normalized = sorted({str(t).strip().upper() for t in tickers if str(t).strip()})
    return normalized


def _build_returns_dataframe(tickers: list[str], period: str) -> pd.DataFrame:
    historical_returns = MarketDataAdapter.get_historical_returns(tickers=tickers, period=period)

    aligned_returns: list[pd.Series] = []
    for ticker in tickers:
        series = historical_returns.get(ticker, pd.Series(dtype="float64"))
        series = pd.to_numeric(series, errors="coerce")
        series.name = ticker
        aligned_returns.append(series)

    if not aligned_returns:
        return pd.DataFrame(columns=tickers)

    returns_df = pd.concat(aligned_returns, axis=1).sort_index()
    for ticker in tickers:
        if ticker not in returns_df.columns:
            returns_df[ticker] = np.nan

    return returns_df[tickers]


def _average_pair_correlation(correlation_df: pd.DataFrame, tickers: list[str]) -> float:
    if len(tickers) < 2:
        return 0.0

    pair_values: list[float] = []
    for left_idx in range(len(tickers)):
        for right_idx in range(left_idx + 1, len(tickers)):
            value = float(correlation_df.iloc[left_idx, right_idx])
            if np.isfinite(value):
                pair_values.append(value)

    if not pair_values:
        return 0.0

    return float(np.mean(pair_values))


def _find_high_correlation_pairs(correlation_df: pd.DataFrame, tickers: list[str]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []

    for left_idx in range(len(tickers)):
        for right_idx in range(left_idx + 1, len(tickers)):
            corr = float(correlation_df.iloc[left_idx, right_idx])
            if corr > CORRELATION_CLUSTER_THRESHOLD:
                pairs.append(
                    {
                        "pair": [tickers[left_idx], tickers[right_idx]],
                        "correlation": corr,
                    }
                )

    return sorted(pairs, key=lambda item: item["correlation"], reverse=True)


def _build_clusters_from_pairs(
    tickers: list[str],
    high_correlation_pairs: list[dict[str, Any]],
) -> list[list[str]]:
    adjacency: dict[str, set[str]] = {ticker: set() for ticker in tickers}

    for item in high_correlation_pairs:
        left, right = item["pair"]
        adjacency[left].add(right)
        adjacency[right].add(left)

    visited: set[str] = set()
    clusters: list[list[str]] = []

    for ticker in tickers:
        if ticker in visited:
            continue

        stack = [ticker]
        component: list[str] = []

        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)
            component.append(current)

            for neighbour in adjacency[current]:
                if neighbour not in visited:
                    stack.append(neighbour)

        if len(component) > 1:
            clusters.append(sorted(component))

    clusters.sort(key=lambda cluster: (-len(cluster), cluster))
    return clusters


def calculate_correlation_matrix(tickers: list[str], period: str = "1y") -> dict[str, Any]:
    normalized_tickers = _normalize_tickers(tickers)
    if not normalized_tickers:
        return {
            "recharts_data": [],
            "high_correlation_pairs": [],
            "avg_correlation": 0.0,
            "period": period,
        }

    returns_df = _build_returns_dataframe(tickers=normalized_tickers, period=period)
    correlation_df = returns_df.corr(method="pearson", min_periods=2)
    correlation_df = correlation_df.reindex(index=normalized_tickers, columns=normalized_tickers)

    for ticker in normalized_tickers:
        correlation_df.loc[ticker, ticker] = 1.0

    correlation_df = correlation_df.fillna(0.0)

    recharts_data: list[dict[str, Any]] = []
    for row_symbol in normalized_tickers:
        row: dict[str, Any] = {"symbol": row_symbol}
        for col_symbol in normalized_tickers:
            row[col_symbol] = float(correlation_df.loc[row_symbol, col_symbol])
        recharts_data.append(row)

    high_correlation_pairs = _find_high_correlation_pairs(
        correlation_df=correlation_df,
        tickers=normalized_tickers,
    )

    return {
        "recharts_data": recharts_data,
        "high_correlation_pairs": high_correlation_pairs,
        "avg_correlation": _average_pair_correlation(
            correlation_df=correlation_df,
            tickers=normalized_tickers,
        ),
        "period": period,
    }


def portfolio_correlation_risk(
    portfolio_id: int,
    sub_portfolio_id: int | None = None,
) -> dict[str, Any]:
    holdings_snapshot = MarketDataAdapter.get_holdings_snapshot(
        portfolio_id=portfolio_id,
        sub_portfolio_id=sub_portfolio_id,
    )

    tickers = sorted(
        {
            str(item.get("ticker", "")).strip().upper()
            for item in holdings_snapshot
            if str(item.get("ticker", "")).strip() and float(item.get("quantity") or 0.0) > 0
        }
    )

    if len(tickers) < 2:
        return {
            "avg_correlation": 0.0,
            "risk_level": "low",
            "clusters": [],
            "high_correlation_pairs": [],
            "recharts_data": [],
            "recommendation": "Portfel ma mniej niż 2 aktywa; dodaj nieskorelowane instrumenty dla lepszej dywersyfikacji.",
        }

    matrix_data = calculate_correlation_matrix(tickers=tickers, period="1y")
    avg_correlation = float(matrix_data["avg_correlation"])
    high_correlation_pairs = matrix_data["high_correlation_pairs"]
    clusters = _build_clusters_from_pairs(tickers=tickers, high_correlation_pairs=high_correlation_pairs)

    max_cluster_size = max((len(cluster) for cluster in clusters), default=1)
    high_pair_count = len(high_correlation_pairs)

    if avg_correlation >= 0.75 or max_cluster_size >= 4:
        risk_level = "high"
        recommendation = (
            "Wysokie ryzyko koncentracji korelacyjnej. Rozważ zwiększenie ekspozycji na aktywa z innych sektorów"
            " lub klas aktywów, aby ograniczyć wspólne spadki."
        )
    elif avg_correlation >= 0.50 or high_pair_count >= 2:
        risk_level = "medium"
        recommendation = (
            "Umiarkowane ryzyko korelacyjne. Sprawdź największe pary i rozważ częściową dywersyfikację"
            " w kierunku aktywów o niższej korelacji."
        )
    else:
        risk_level = "low"
        recommendation = "Niskie ryzyko korelacyjne. Utrzymuj dywersyfikację i monitoruj zmiany zależności w czasie."

    return {
        "avg_correlation": avg_correlation,
        "risk_level": risk_level,
        "clusters": clusters,
        "high_correlation_pairs": high_correlation_pairs,
        "recharts_data": matrix_data["recharts_data"],
        "recommendation": recommendation,
    }
