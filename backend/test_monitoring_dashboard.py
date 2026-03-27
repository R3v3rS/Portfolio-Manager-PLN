import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from monitoring.dashboard import calculate_monitoring_stats  # noqa: E402


class MonitoringDashboardParserTestCase(unittest.TestCase):
    def write_lines(self, file_path, rows):
        with open(file_path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    def test_empty_log_file_returns_zeroed_metrics(self):
        now = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
        start = now - timedelta(minutes=30)

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = os.path.join(tmp_dir, "backend.log")
            Path(log_path).touch()

            stats = calculate_monitoring_stats(log_path, now=now, app_started_at=start)

        self.assertEqual(stats["total_requests"], 0)
        self.assertEqual(stats["total_errors"], 0)
        self.assertEqual(stats["errors_last_1h"], 0)
        self.assertEqual(stats["requests_per_minute"], 0.0)
        self.assertEqual(stats["error_rate_percent"], 0.0)
        self.assertEqual(stats["errors_by_type"], {})
        self.assertEqual(stats["slowest_operations"], [])
        self.assertEqual(stats["last_errors"], [])
        self.assertTrue(stats["log_file_exists"])

    def test_mixed_entries_compute_expected_metrics(self):
        now = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
        start = now - timedelta(hours=2)
        recent = now - timedelta(minutes=5)

        rows = [
            {
                "timestamp": recent.isoformat(),
                "provider": "yfinance",
                "operation": "get_prices.bulk_download",
                "status": "start",
            },
            {
                "timestamp": (recent + timedelta(seconds=2)).isoformat(),
                "provider": "yfinance",
                "operation": "get_prices.bulk_download",
                "status": "failed",
                "error_type": "network_timeout",
                "error_message": "Read timeout",
                "duration_ms": 1500,
                "ticker": "AAPL",
            },
            {
                "timestamp": (recent + timedelta(seconds=6)).isoformat(),
                "provider": "yfinance",
                "operation": "fetch_metadata",
                "status": "start",
            },
            {
                "timestamp": (recent + timedelta(seconds=8)).isoformat(),
                "provider": "yfinance",
                "operation": "fetch_metadata",
                "status": "retry",
                "error_type": "rate_limit",
            },
            {
                "timestamp": (recent + timedelta(seconds=12)).isoformat(),
                "provider": "yfinance",
                "operation": "fetch_metadata",
                "status": "failed",
                "error_type": "rate_limit",
                "error_message": "HTTP 429",
                "duration_ms": 300,
                "ticker": "MSFT",
            },
            {
                "timestamp": (recent + timedelta(seconds=20)).isoformat(),
                "provider": "other",
                "operation": "noop",
                "status": "failed",
            },
            {"timestamp": "bad-timestamp", "provider": "yfinance", "status": "failed"},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = os.path.join(tmp_dir, "backend.log")
            self.write_lines(log_path, rows)
            stats = calculate_monitoring_stats(log_path, now=now, app_started_at=start)

        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["total_errors"], 2)
        self.assertEqual(stats["errors_last_1h"], 2)
        self.assertEqual(stats["requests_per_minute"], 0.2)
        self.assertEqual(stats["error_rate_percent"], 100.0)
        self.assertEqual(stats["errors_by_type"], {"network_timeout": 1, "rate_limit": 1})
        self.assertEqual(len(stats["slowest_operations"]), 2)
        self.assertEqual(stats["slowest_operations"][0]["duration_ms"], 1500.0)
        self.assertEqual(stats["last_errors"][0]["ticker"], "MSFT")
        self.assertEqual(stats["last_errors"][1]["ticker"], "AAPL")

    def test_old_entries_do_not_affect_last_hour_metrics(self):
        now = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
        start = now - timedelta(hours=3)
        old_time = now - timedelta(hours=2)

        rows = [
            {
                "timestamp": old_time.isoformat(),
                "provider": "yfinance",
                "operation": "get_quotes",
                "status": "start",
            },
            {
                "timestamp": (old_time + timedelta(seconds=1)).isoformat(),
                "provider": "yfinance",
                "operation": "get_quotes",
                "status": "failed",
                "error_type": "network_timeout",
                "error_message": "Timeout",
                "duration_ms": 111,
                "ticker": "TSLA",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = os.path.join(tmp_dir, "backend.log")
            self.write_lines(log_path, rows)
            stats = calculate_monitoring_stats(log_path, now=now, app_started_at=start)

        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["total_errors"], 1)
        self.assertEqual(stats["errors_last_1h"], 0)
        self.assertEqual(stats["requests_per_minute"], 0.0)
        self.assertEqual(stats["error_rate_percent"], 0.0)
        self.assertEqual(stats["errors_by_type"], {})
        self.assertEqual(stats["slowest_operations"], [])
        self.assertEqual(len(stats["last_errors"]), 1)

    def test_identical_durations_do_not_crash_heap_sorting(self):
        now = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
        start = now - timedelta(hours=1)
        recent = now - timedelta(minutes=2)

        rows = [
            {
                "timestamp": (recent + timedelta(seconds=idx)).isoformat(),
                "provider": "yfinance",
                "operation": "bulk_download",
                "status": "failed",
                "error_type": "timeout",
                "duration_ms": 500,
                "ticker": f"TICK{idx}",
            }
            for idx in range(6)
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = os.path.join(tmp_dir, "backend.log")
            self.write_lines(log_path, rows)
            stats = calculate_monitoring_stats(log_path, now=now, app_started_at=start)

        self.assertEqual(len(stats["slowest_operations"]), 5)
        self.assertTrue(all(item["duration_ms"] == 500.0 for item in stats["slowest_operations"]))



if __name__ == "__main__":
    unittest.main()
