import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from price_service import PriceService  # noqa: E402


def _single_close_df(value):
    return pd.DataFrame({"Close": [value]})


def _multi_close_df(values_by_ticker):
    data = {}
    for ticker, value in values_by_ticker.items():
        data[(ticker, "Close")] = [value]
    return pd.DataFrame(data)


class PriceServiceScenarioTestCase(unittest.TestCase):
    def setUp(self):
        PriceService._price_cache.clear()
        PriceService._price_cache_updated_at.clear()
        PriceService._error_occurrences.clear()
        PriceService._error_aggregation_last_summary.clear()

    def _patch_cache_io(self):
        return patch.multiple(
            PriceService,
            _load_price_cache_from_db=Mock(),
            _save_price_cache_to_db=Mock(),
            _mark_price_refresh_attempt=Mock(),
        )

    def test_scenario_success_bulk_download(self):
        with self._patch_cache_io(), patch.object(PriceService, "_download_with_retry", return_value=_single_close_df(101.25)) as dl:
            prices = PriceService.get_prices(["AAPL"], force_refresh=True)

        self.assertEqual(prices, {"AAPL": 101.25})
        dl.assert_called_once()

    def test_scenario_retry_then_success(self):
        side_effects = [
            TimeoutError("network timeout"),
            _single_close_df(123.45),
        ]
        with patch("price_service.time.sleep"), patch("price_service.random.uniform", return_value=0.0), patch("price_service.yf.download", side_effect=side_effects), patch.object(PriceService, "_log_provider_event") as log_event:
            result = PriceService._download_with_retry(
                ["AAPL"],
                period="5d",
                operation="get_prices.bulk_download",
            )

        self.assertFalse(result.empty)
        statuses = [call.kwargs["status"] for call in log_event.call_args_list if "status" in call.kwargs]
        self.assertIn("retry", statuses)
        self.assertIn("success", statuses)
        retry_call = next(call for call in log_event.call_args_list if call.kwargs.get("status") == "retry")
        self.assertEqual(retry_call.kwargs["level"], logging.WARNING)

    def test_scenario_retry_then_final_failure(self):
        with patch("price_service.time.sleep"), patch("price_service.random.uniform", return_value=0.0), patch("price_service.yf.download", side_effect=TimeoutError("timeout")), patch.object(PriceService, "_log_provider_event") as log_event:
            with self.assertRaises(TimeoutError):
                PriceService._download_with_retry(
                    ["AAPL"],
                    period="5d",
                    operation="get_prices.bulk_download",
                )

        failed_call = [call for call in log_event.call_args_list if call.kwargs.get("status") == "failed"]
        self.assertEqual(len(failed_call), 1)
        self.assertEqual(failed_call[0].kwargs["level"], logging.ERROR)

    def test_scenario_fallback_activation(self):
        empty_df = pd.DataFrame()
        ticker_obj = Mock()
        ticker_obj.history.return_value = _single_close_df(88.88)
        ticker_obj.fast_info.last_price = None

        with self._patch_cache_io(), patch.object(PriceService, "_download_with_retry", return_value=empty_df), patch("price_service.yf.Ticker", return_value=ticker_obj), patch.object(PriceService, "_log_provider_event") as log_event:
            prices = PriceService.get_prices(["MSFT"], force_refresh=True)

        self.assertEqual(prices, {"MSFT": 88.88})
        fallback_start = [c for c in log_event.call_args_list if c.kwargs.get("operation") == "get_prices.fallback" and c.kwargs.get("status") == "start"]
        self.assertEqual(len(fallback_start), 1)

    def test_scenario_partial_success_in_fallback(self):
        bulk_df = _multi_close_df({"AAPL": 150.0})

        success_ticker = Mock()
        success_ticker.history.return_value = _single_close_df(77.77)
        success_ticker.fast_info.last_price = None

        failed_ticker = Mock()
        failed_ticker.history.return_value = pd.DataFrame()
        failed_ticker.fast_info.last_price = None

        def ticker_factory(symbol):
            return success_ticker if symbol == "MSFT" else failed_ticker

        with self._patch_cache_io(), patch.object(PriceService, "_download_with_retry", return_value=bulk_df), patch("price_service.yf.Ticker", side_effect=ticker_factory), patch.object(PriceService, "_log_provider_event") as log_event:
            prices = PriceService.get_prices(["AAPL", "MSFT", "GOOG"], force_refresh=True)

        self.assertEqual(prices["AAPL"], 150.0)
        self.assertEqual(prices["MSFT"], 77.77)
        self.assertIsNone(prices["GOOG"])

        fallback_summary = [
            c for c in log_event.call_args_list
            if c.kwargs.get("operation") == "get_prices.fallback" and c.kwargs.get("status") == "partial"
        ]
        self.assertEqual(len(fallback_summary), 1)

    def test_get_stock_analysis_sets_rsi14_to_none_when_loss_is_zero(self):
        ticker_obj = Mock()
        ticker_obj.info = {}
        ticker_obj.history.return_value = pd.DataFrame({"Close": [float(i) for i in range(1, 61)]})

        with patch("price_service.yf.Ticker", return_value=ticker_obj):
            analysis = PriceService.get_stock_analysis("AAPL")

        self.assertIn("technicals", analysis)
        self.assertEqual(
            set(analysis["technicals"].keys()),
            {"sma50", "sma200", "rsi14"},
        )
        self.assertIsNone(analysis["technicals"]["rsi14"])

    def test_sync_stock_history_logs_upserted_rows_message(self):
        db_mock = Mock()
        initial_range_row = {"min_date": None, "max_date": None}
        final_max_row = {"max_date": "2024-01-04"}

        first_query = Mock()
        first_query.fetchone.return_value = initial_range_row
        second_query = Mock()
        second_query.fetchone.return_value = final_max_row
        db_mock.execute.side_effect = [first_query, second_query]

        cursor_mock = Mock()
        cursor_mock.rowcount = 1
        db_mock.cursor.return_value = cursor_mock

        history_df = pd.DataFrame(
            {"Close": [100.12, 101.34]},
            index=pd.to_datetime(["2024-01-03", "2024-01-04"]),
        )

        with patch("price_service.get_db", return_value=db_mock), patch.object(
            PriceService, "_download_with_retry", return_value=history_df
        ), patch.object(PriceService, "_normalize_yf_dataframe", return_value=history_df), patch.object(
            PriceService, "_log_provider_event"
        ) as log_event:
            result = PriceService.sync_stock_history("AAPL")

        self.assertEqual(result, "2024-01-04")
        messages = [
            call.kwargs.get("message")
            for call in log_event.call_args_list
            if call.kwargs.get("operation") == "sync_stock_history"
        ]
        self.assertIn("Upserted 2 history rows (new + refreshed)", messages)
        self.assertTrue(all("Inserted " not in (message or "") for message in messages))


if __name__ == "__main__":
    unittest.main()
