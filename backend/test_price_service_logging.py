import json
import logging
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

    def test_log_provider_event_includes_contract_fields_for_error(self):
        with patch("price_service.logger.log") as logger_log:
            PriceService._log_provider_event(
                level=logging.WARNING,
                operation="get_prices.bulk_download",
                status="retry",
                ticker="AAPL",
                attempt=2,
                max_attempts=3,
                duration_ms=12.34,
                error=TimeoutError("network timeout"),
                request_id="req-1",
                trace_id="trace-1",
                message="Retrying provider call",
            )

            logger_log.assert_called_once()
            level, payload_text = logger_log.call_args.args
            self.assertEqual(level, logging.WARNING)
            payload = json.loads(payload_text)
            self.assertEqual(payload["provider"], "yfinance")
            self.assertEqual(payload["operation"], "get_prices.bulk_download")
            self.assertEqual(payload["status"], "retry")
            self.assertEqual(payload["ticker"], "AAPL")
            self.assertEqual(payload["attempt"], 2)
            self.assertEqual(payload["max_attempts"], 3)
            self.assertEqual(payload["duration_ms"], 12.34)
            self.assertEqual(payload["error_type"], "network_timeout")
            self.assertIn("timeout", payload["error_message"].lower())
            self.assertEqual(payload["request_id"], "req-1")
            self.assertEqual(payload["trace_id"], "trace-1")
            self.assertEqual(payload["message"], "Retrying provider call")

    def test_log_provider_event_accepts_optional_none_fields(self):
        with patch("price_service.logger.log") as logger_log:
            PriceService._log_provider_event(
                level=logging.INFO,
                operation="get_prices.bulk",
                status="success",
                ticker=None,
                tickers_count=None,
                attempt=None,
                max_attempts=None,
                duration_ms=None,
                error=None,
                request_id=None,
                trace_id=None,
                message=None,
            )

            logger_log.assert_called_once()
            level, payload_text = logger_log.call_args.args
            self.assertEqual(level, logging.INFO)
            payload = json.loads(payload_text)
            self.assertEqual(payload, {
                "provider": "yfinance",
                "operation": "get_prices.bulk",
                "status": "success",
            })

    def test_log_provider_event_respects_explicit_log_levels(self):
        with patch("price_service.logger.log") as logger_log:
            PriceService._log_provider_event(level=logging.INFO, operation="op.info", status="success")
            PriceService._log_provider_event(level=logging.WARNING, operation="op.warn", status="retry")
            PriceService._log_provider_event(level=logging.ERROR, operation="op.err", status="failed")

            emitted_levels = [call.args[0] for call in logger_log.call_args_list]
            self.assertEqual(emitted_levels, [logging.INFO, logging.WARNING, logging.ERROR])

    def test_warmup_cache_excludes_cash_and_null_tickers_from_query(self):
        holdings_rows = [{"ticker": "AAPL"}, {"ticker": "MSFT"}]
        db_mock = unittest.mock.Mock()
        db_mock.execute.return_value.fetchall.return_value = holdings_rows

        with patch("price_service.get_db", return_value=db_mock):
            with patch.object(PriceService, "get_prices") as get_prices_mock:
                PriceService.warmup_cache()

        db_mock.execute.assert_called_once()
        executed_sql = db_mock.execute.call_args.args[0]
        self.assertIn("WHERE ticker IS NOT NULL", executed_sql)
        self.assertIn("ticker != 'CASH'", executed_sql)
        get_prices_mock.assert_called_once_with(["AAPL", "MSFT"])

    def test_classify_error_known_and_unknown_paths(self):
        test_cases = [
            (TimeoutError("Read timeout"), "network_timeout"),
            (RuntimeError("Too many requests (HTTP 429)"), "rate_limit"),
            (ValueError("Empty DataFrame"), "empty_data"),
            (LookupError("invalid ticker symbol"), "invalid_ticker"),
            (ValueError("parse failed"), "parsing_error"),
        ]

        for exc, expected in test_cases:
            with self.subTest(expected=expected):
                self.assertEqual(PriceService._classify_error(exc), expected)

        class CustomFailure(Exception):
            pass

        self.assertEqual(PriceService._classify_error(CustomFailure("something else")), "unknown")


if __name__ == "__main__":
    unittest.main()
