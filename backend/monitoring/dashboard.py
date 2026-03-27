from __future__ import annotations

import json
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from heapq import heappop, heappush
from typing import Any

from flask import Blueprint, current_app, jsonify

monitoring_bp = Blueprint("monitoring", __name__)


def _parse_timestamp(raw_value: Any) -> datetime | None:
    if not raw_value or not isinstance(raw_value, str):
        return None
    normalized = raw_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _default_metrics(now: datetime, app_started_at: datetime) -> dict[str, Any]:
    uptime_seconds = max(0, int((now - app_started_at).total_seconds()))
    return {
        "uptime": uptime_seconds,
        "total_requests": 0,
        "total_errors": 0,
        "errors_last_1h": 0,
        "requests_per_minute": 0.0,
        "error_rate_percent": 0.0,
        "errors_by_type": {},
        "slowest_operations": [],
        "last_errors": [],
        "log_file_exists": False,
    }


def calculate_monitoring_stats(
    log_file_path: str,
    *,
    now: datetime | None = None,
    app_started_at: datetime | None = None,
) -> dict[str, Any]:
    utc_now = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    start_time = app_started_at.astimezone(timezone.utc) if app_started_at else utc_now

    metrics = _default_metrics(utc_now, start_time)

    if not log_file_path or not os.path.exists(log_file_path):
        return metrics

    metrics["log_file_exists"] = True

    one_hour_ago = utc_now - timedelta(hours=1)
    ten_minutes_ago = utc_now - timedelta(minutes=10)

    total_requests = 0
    total_errors = 0
    errors_last_1h = 0
    requests_last_1h = 0
    requests_last_10m = 0
    errors_by_type = defaultdict(int)
    slowest_heap: list[tuple[float, dict[str, Any]]] = []
    last_errors = deque(maxlen=10)

    with open(log_file_path, "r", encoding="utf-8") as log_file:
        for line in log_file:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            timestamp = _parse_timestamp(entry.get("timestamp"))
            if timestamp is None or timestamp < start_time:
                continue

            if entry.get("provider") != "yfinance":
                continue

            status = str(entry.get("status") or "").lower()
            if status == "start":
                total_requests += 1
                if timestamp >= one_hour_ago:
                    requests_last_1h += 1
                if timestamp >= ten_minutes_ago:
                    requests_last_10m += 1

            duration_ms = entry.get("duration_ms")
            try:
                duration_value = float(duration_ms)
            except (TypeError, ValueError):
                duration_value = None

            if timestamp >= one_hour_ago and duration_value is not None:
                operation_item = {
                    "timestamp": timestamp.isoformat(),
                    "operation": entry.get("operation"),
                    "ticker": entry.get("ticker"),
                    "duration_ms": round(duration_value, 2),
                }
                heappush(slowest_heap, (duration_value, operation_item))
                if len(slowest_heap) > 5:
                    heappop(slowest_heap)

            if status == "failed":
                total_errors += 1
                error_type = entry.get("error_type") or "unknown"
                if timestamp >= one_hour_ago:
                    errors_last_1h += 1
                    errors_by_type[str(error_type)] += 1

                last_errors.append(
                    {
                        "time": timestamp.isoformat(),
                        "ticker": entry.get("ticker"),
                        "error_type": error_type,
                        "error_message": entry.get("error_message"),
                    }
                )

    metrics["total_requests"] = total_requests
    metrics["total_errors"] = total_errors
    metrics["errors_last_1h"] = errors_last_1h
    metrics["requests_per_minute"] = round(requests_last_10m / 10.0, 2)
    metrics["error_rate_percent"] = round((errors_last_1h / requests_last_1h) * 100.0, 2) if requests_last_1h else 0.0
    metrics["errors_by_type"] = dict(sorted(errors_by_type.items(), key=lambda item: item[1], reverse=True))
    metrics["slowest_operations"] = [
        payload for _duration, payload in sorted(slowest_heap, key=lambda row: row[0], reverse=True)
    ]
    metrics["last_errors"] = list(reversed(last_errors))
    return metrics


@monitoring_bp.route("", methods=["GET"])
def monitoring_dashboard():
    return """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Monitoring yfinance</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; background: #f7f9fc; color: #1f2d3d; }
    h1 { margin-bottom: 16px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .card { border-radius: 10px; padding: 16px; background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
    .label { font-size: 12px; text-transform: uppercase; color: #6b7280; }
    .value { font-size: 28px; font-weight: 700; margin-top: 8px; }
    .status-ok { border-left: 6px solid #16a34a; }
    .status-warning { border-left: 6px solid #f59e0b; }
    .status-critical { border-left: 6px solid #dc2626; }
    table { width: 100%; border-collapse: collapse; margin-top: 18px; background: white; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; font-size: 14px; }
    th { background: #f3f4f6; }
    .meta { color: #6b7280; margin-bottom: 18px; }
    .pill { display: inline-block; background: #eef2ff; padding: 6px 10px; border-radius: 9999px; margin-right: 6px; margin-top: 4px; }
  </style>
</head>
<body>
  <h1>Monitoring yfinance</h1>
  <div class="meta">Automatyczne odświeżanie co 30 sekund.</div>
  <div class="grid" id="cards"></div>

  <h2>Błędy wg typu (ostatnia 1h)</h2>
  <div id="errorsByType"></div>

  <h2>Najwolniejsze operacje (ostatnia 1h)</h2>
  <table>
    <thead>
      <tr><th>Czas</th><th>Operacja</th><th>Ticker</th><th>duration_ms</th></tr>
    </thead>
    <tbody id="slowestBody"></tbody>
  </table>

  <h2>Ostatnie 10 błędów</h2>
  <table>
    <thead>
      <tr><th>Czas</th><th>Ticker</th><th>Typ</th><th>Wiadomość</th></tr>
    </thead>
    <tbody id="errorsBody"></tbody>
  </table>

  <script>
    const cardsEl = document.getElementById('cards');
    const errorsByTypeEl = document.getElementById('errorsByType');
    const errorsBodyEl = document.getElementById('errorsBody');
    const slowestBodyEl = document.getElementById('slowestBody');

    function statusClass(errorRate) {
      if (errorRate > 30) return 'status-critical';
      if (errorRate > 10) return 'status-warning';
      return 'status-ok';
    }

    function metricCard(label, value, cssClass = 'status-ok') {
      return `
        <div class="card ${cssClass}">
          <div class="label">${label}</div>
          <div class="value">${value}</div>
        </div>`;
    }

    function formatDuration(seconds) {
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      const s = seconds % 60;
      return `${h}h ${m}m ${s}s`;
    }

    function render(data) {
      const rateClass = statusClass(data.error_rate_percent || 0);
      cardsEl.innerHTML = [
        metricCard('Uptime', formatDuration(data.uptime || 0)),
        metricCard('Total requests', data.total_requests ?? 0),
        metricCard('Total errors', data.total_errors ?? 0, (data.total_errors ?? 0) > 0 ? 'status-warning' : 'status-ok'),
        metricCard('Errors last 1h', data.errors_last_1h ?? 0, (data.errors_last_1h ?? 0) > 0 ? 'status-warning' : 'status-ok'),
        metricCard('Requests / minute (10m avg)', (data.requests_per_minute ?? 0).toFixed(2)),
        metricCard('Error rate % (1h)', `${(data.error_rate_percent ?? 0).toFixed(2)}%`, rateClass)
      ].join('');

      const byType = data.errors_by_type || {};
      const typeEntries = Object.entries(byType);
      if (!typeEntries.length) {
        errorsByTypeEl.innerHTML = '<span class="pill">brak błędów</span>';
      } else {
        errorsByTypeEl.innerHTML = typeEntries
          .map(([type, count]) => `<span class="pill">${type}: ${count}</span>`)
          .join('');
      }

      const slowestRows = (data.slowest_operations || []).map((item) => `
        <tr>
          <td>${item.timestamp || '-'}</td>
          <td>${item.operation || '-'}</td>
          <td>${item.ticker || '-'}</td>
          <td>${item.duration_ms ?? '-'}</td>
        </tr>`).join('');
      slowestBodyEl.innerHTML = slowestRows || '<tr><td colspan="4">Brak danych</td></tr>';

      const errorRows = (data.last_errors || []).map((row) => `
        <tr>
          <td>${row.time || '-'}</td>
          <td>${row.ticker || '-'}</td>
          <td>${row.error_type || '-'}</td>
          <td>${row.error_message || '-'}</td>
        </tr>`).join('');
      errorsBodyEl.innerHTML = errorRows || '<tr><td colspan="4">Brak błędów</td></tr>';
    }

    async function refresh() {
      try {
        const response = await fetch('/monitoring/stats');
        const data = await response.json();
        render(data);
      } catch (error) {
        console.error('Nie udało się pobrać statystyk monitoringu.', error);
      }
    }

    refresh();
    setInterval(refresh, 30000);
  </script>
</body>
</html>"""


@monitoring_bp.route("/stats", methods=["GET"])
def monitoring_stats():
    log_file_path = current_app.config.get("BACKEND_LOG_PATH") or os.path.join(
        os.path.dirname(__file__), "..", "logs", "backend.log"
    )
    app_started_at = current_app.config.get("APP_STARTED_AT")
    return jsonify(calculate_monitoring_stats(log_file_path, app_started_at=app_started_at))
