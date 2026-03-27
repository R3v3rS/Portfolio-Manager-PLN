import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from price_service import PriceService  # noqa: E402


class PriceServiceLoggingTestCase(unittest.TestCase):
    def setUp(self):
        PriceService._error_occurrences.clear()
        PriceService._error_aggregation_last_summary.clear()

    def test_verbose_provider_logs_flag_parsing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(PriceService._verbose_provider_logs_enabled())

        with patch.dict(os.environ, {"VERBOSE_PROVIDER_LOGS": "true"}, clear=True):
            self.assertTrue(PriceService._verbose_provider_logs_enabled())

        with patch.dict(os.environ, {"VERBOSE_PROVIDER_LOGS": "1"}, clear=True):
            self.assertTrue(PriceService._verbose_provider_logs_enabled())

        with patch.dict(os.environ, {"VERBOSE_PROVIDER_LOGS": "false"}, clear=True):
            self.assertFalse(PriceService._verbose_provider_logs_enabled())

    def test_log_verbose_provider_event_respects_flag(self):
        with patch("price_service.logger.log") as logger_log:
            with patch.dict(os.environ, {}, clear=True):
                PriceService._log_verbose_provider_event(
                    operation="warmup_cache",
                    status="start",
                    message="Warming up",
                )
            logger_log.assert_not_called()

            with patch.dict(os.environ, {"VERBOSE_PROVIDER_LOGS": "true"}, clear=True):
                PriceService._log_verbose_provider_event(
                    operation="warmup_cache",
                    status="start",
                    message="Warming up",
                )
            self.assertEqual(logger_log.call_count, 1)

    def test_error_aggregation_reduces_log_flood_when_not_verbose(self):
        with patch.dict(os.environ, {"VERBOSE_PROVIDER_LOGS": "false"}, clear=True):
            with patch("price_service.logger.log") as logger_log, patch("price_service.logger.warning") as logger_warning:
                for _ in range(12):
                    PriceService._log_provider_event(
                        level=40,
                        operation="get_prices.bulk",
                        status="failed",
                        error=ValueError("HTTP 429 Too Many Requests"),
                    )

                self.assertEqual(logger_log.call_count, PriceService._error_aggregation_threshold)
                self.assertEqual(logger_warning.call_count, 1)
                warning_payload = logger_warning.call_args.args[0]
                self.assertIn("rate_limit x11", warning_payload)


if __name__ == "__main__":
    unittest.main()
