from __future__ import annotations

from typing import Any

import numpy as np

from backend.services.analytics.market_data_adapter import MarketDataAdapter


def herfindahl_index(weights: list[float]) -> float:
    """Calculate Herfindahl-Hirschman Index (HHI) for normalized weights."""
    if not weights:
        return 0.0

    normalized_weights = [float(weight) for weight in weights]
    if any(weight < 0 for weight in normalized_weights):
        raise ValueError("weights cannot contain negative values")

    total_weight = float(sum(normalized_weights))
    if not np.isclose(total_weight, 1.0, atol=1e-6):
        raise ValueError("weights must sum to 1.0")

    return float(sum(weight**2 for weight in normalized_weights))


def _score_and_rating_from_hhi(hhi: float) -> tuple[int, str]:
    if hhi > 0.25:
        score = int(np.clip(np.interp(hhi, [0.25, 1.0], [40, 0]), 0, 40))
        return score, "poor"

    if hhi >= 0.15:
        score = int(np.clip(np.interp(hhi, [0.25, 0.15], [40, 65]), 40, 65))
        return score, "fair"

    if hhi >= 0.05:
        score = int(np.clip(np.interp(hhi, [0.15, 0.05], [65, 85]), 65, 85))
        return score, "good"

    score = int(np.clip(np.interp(hhi, [0.05, 0.0], [85, 100]), 85, 100))
    return score, "excellent"


def _recommendation(rating: str, top_weight: float) -> str:
    if rating == "poor":
        return (
            "Dywersyfikacja jest niska. Ogranicz udział największej pozycji i dodaj ekspozycję"
            " na inne sektory oraz klasy aktywów."
        )
    if rating == "fair":
        return (
            "Dywersyfikacja jest umiarkowana. Rozważ zmniejszenie koncentracji w 1-2 największych"
            " pozycjach i zwiększenie udziału mniej reprezentowanych sektorów."
        )
    if rating == "good":
        if top_weight > 0.25:
            return (
                "Portfel jest dobrze zdywersyfikowany, ale największa pozycja jest relatywnie wysoka."
                " Rozważ jej częściową redukcję."
            )
        return "Portfel ma dobrą dywersyfikację. Utrzymuj obecny poziom i okresowo monitoruj koncentrację."
    return "Bardzo dobra dywersyfikacja. Kontynuuj bieżącą strategię i monitoruj zmiany wag w czasie."


def diversification_score(
    portfolio_id: int,
    sub_portfolio_id: int | None = None,
) -> dict[str, Any]:
    holdings_snapshot = MarketDataAdapter.get_holdings_snapshot(
        portfolio_id=portfolio_id,
        sub_portfolio_id=sub_portfolio_id,
    )

    positive_holdings = [
        item
        for item in holdings_snapshot
        if str(item.get("ticker", "")).strip() and float(item.get("weight") or 0.0) > 0
    ]

    if not positive_holdings:
        return {
            "hhi": 0.0,
            "score": 100,
            "rating": "excellent",
            "by_asset": [],
            "by_sector": [],
            "top_concentration_warning": None,
            "recommendation": "Brak dodatnich pozycji w portfelu. Dodaj aktywa, aby ocenić dywersyfikację.",
        }

    total_weight = float(sum(float(item.get("weight") or 0.0) for item in positive_holdings))
    normalized_assets: list[dict[str, Any]] = []

    for item in positive_holdings:
        ticker = str(item.get("ticker", "")).strip().upper()
        raw_sector = item.get("sector")
        sector = str(raw_sector).strip() if raw_sector is not None else ""
        sector = sector if sector else "Nieznany"
        weight = float(item.get("weight") or 0.0)
        normalized_weight = weight / total_weight if total_weight > 0 else 0.0
        normalized_assets.append(
            {
                "ticker": ticker,
                "sector": sector,
                "weight": normalized_weight,
            }
        )

    asset_weights = [item["weight"] for item in normalized_assets]
    hhi_value = herfindahl_index(asset_weights)
    score, rating = _score_and_rating_from_hhi(hhi_value)

    by_asset = sorted(
        [
            {
                "ticker": item["ticker"],
                "weight": float(item["weight"]),
                "sector": item["sector"],
                "hhi_contribution": float(item["weight"] ** 2),
            }
            for item in normalized_assets
        ],
        key=lambda row: row["weight"],
        reverse=True,
    )

    sector_weights: dict[str, float] = {}
    for item in normalized_assets:
        sector_weights[item["sector"]] = sector_weights.get(item["sector"], 0.0) + float(item["weight"])

    by_sector = sorted(
        [
            {
                "sector": sector,
                "weight": float(weight),
                "hhi_contribution": float(weight**2),
            }
            for sector, weight in sector_weights.items()
        ],
        key=lambda row: row["weight"],
        reverse=True,
    )

    top_asset = by_asset[0] if by_asset else None
    top_concentration_warning = None
    if top_asset and top_asset["weight"] >= 0.35:
        top_concentration_warning = (
            f"Wysoka koncentracja: {top_asset['ticker']} stanowi {top_asset['weight']:.1%} portfela."
        )

    return {
        "hhi": hhi_value,
        "score": score,
        "rating": rating,
        "by_asset": by_asset,
        "by_sector": by_sector,
        "top_concentration_warning": top_concentration_warning,
        "recommendation": _recommendation(rating=rating, top_weight=top_asset["weight"] if top_asset else 0.0),
    }
