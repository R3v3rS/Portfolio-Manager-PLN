from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, current_app, request

from backend.api.exceptions import NotFoundError, ValidationError
from backend.api.response import error_response, success_response
from backend.services.analytics import correlation_service, diversification_service, performance_metrics

analytics_bp = Blueprint("analytics_bp", __name__)

_ALLOWED_PERIODS = {"3m", "6m", "1y", "2y"}
_CACHE_TTL = timedelta(hours=4)


def _get_connection() -> sqlite3.Connection:
    db_path = current_app.config["DATABASE"]
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_analytics_cache_table() -> None:
    with _get_connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_cache (
                portfolio_id INTEGER NOT NULL,
                sub_portfolio_id INTEGER,
                period TEXT NOT NULL,
                result_json TEXT NOT NULL,
                cached_at TEXT NOT NULL,
                PRIMARY KEY (portfolio_id, sub_portfolio_id, period)
            )
            """
        )
        db.commit()


@analytics_bp.record_once
def _on_blueprint_registered(state) -> None:
    app = state.app
    with app.app_context():
        _ensure_analytics_cache_table()


def _parse_int_param(name: str, required: bool) -> int | None:
    raw = request.args.get(name)
    if raw in (None, ""):
        if required:
            raise ValidationError(f"{name} is required")
        return None

    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be an integer") from None

    if value <= 0:
        raise ValidationError(f"{name} must be a positive integer")

    return value


def _validate_period() -> str:
    period = (request.args.get("period") or "1y").strip().lower()
    if period not in _ALLOWED_PERIODS:
        raise ValidationError(
            "Unsupported period",
            details={"period": period, "supported": sorted(_ALLOWED_PERIODS)},
        )
    return period


def _portfolio_exists(portfolio_id: int) -> bool:
    with _get_connection() as db:
        row = db.execute("SELECT 1 FROM portfolios WHERE id = ?", (portfolio_id,)).fetchone()
    return row is not None


def _load_from_cache(portfolio_id: int, sub_portfolio_id: int | None, period: str) -> dict[str, Any] | None:
    with _get_connection() as db:
        row = db.execute(
            """
            SELECT result_json, cached_at
            FROM analytics_cache
            WHERE portfolio_id = ?
              AND sub_portfolio_id IS ?
              AND period = ?
            """,
            (portfolio_id, sub_portfolio_id, period),
        ).fetchone()

    if not row:
        return None

    cached_at = datetime.fromisoformat(row["cached_at"])
    now_utc = datetime.now(timezone.utc)
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=timezone.utc)

    if now_utc - cached_at > _CACHE_TTL:
        return None

    return json.loads(row["result_json"])


def _save_cache(portfolio_id: int, sub_portfolio_id: int | None, period: str, result: dict[str, Any]) -> None:
    with _get_connection() as db:
        db.execute(
            """
            INSERT INTO analytics_cache (portfolio_id, sub_portfolio_id, period, result_json, cached_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(portfolio_id, sub_portfolio_id, period)
            DO UPDATE SET
                result_json = excluded.result_json,
                cached_at = excluded.cached_at
            """,
            (
                portfolio_id,
                sub_portfolio_id,
                period,
                json.dumps(result),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        db.commit()


def _run_with_app_context(func, app, *args, **kwargs):
    with app.app_context():
        return func(*args, **kwargs)


@analytics_bp.route("/api/analytics/summary", methods=["GET"])
def analytics_summary():
    try:
        portfolio_id = _parse_int_param("portfolio_id", required=True)
        sub_portfolio_id = _parse_int_param("sub_portfolio_id", required=False)
        period = _validate_period()

        if not _portfolio_exists(portfolio_id):
            raise NotFoundError("Portfolio not found", details={"portfolio_id": portfolio_id})

        cached_result = _load_from_cache(portfolio_id, sub_portfolio_id, period)
        if cached_result is not None:
            return success_response({
                "portfolio_id": portfolio_id,
                "sub_portfolio_id": sub_portfolio_id,
                "period": period,
                "cached": True,
                **cached_result,
            })

        app = current_app._get_current_object()
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_performance = executor.submit(
                _run_with_app_context,
                performance_metrics.calculate_performance_summary,
                app,
                portfolio_id,
                sub_portfolio_id,
                period,
            )
            future_var = executor.submit(
                _run_with_app_context,
                performance_metrics.portfolio_var,
                app,
                portfolio_id,
                sub_portfolio_id,
                period,
            )
            future_correlation = executor.submit(
                _run_with_app_context,
                correlation_service.portfolio_correlation_risk,
                app,
                portfolio_id,
                sub_portfolio_id,
            )
            future_diversification = executor.submit(
                _run_with_app_context,
                diversification_service.diversification_score,
                app,
                portfolio_id,
                sub_portfolio_id,
            )

            result = {
                "performance_summary": future_performance.result(),
                "portfolio_var": future_var.result(),
                "correlation_risk": future_correlation.result(),
                "diversification": future_diversification.result(),
            }

        _save_cache(portfolio_id, sub_portfolio_id, period, result)

        return success_response(
            {
                "portfolio_id": portfolio_id,
                "sub_portfolio_id": sub_portfolio_id,
                "period": period,
                "cached": False,
                **result,
            }
        )
    except (ValidationError, NotFoundError):
        raise
    except Exception as exc:
        return error_response("analytics_summary_error", str(exc), status=500)
