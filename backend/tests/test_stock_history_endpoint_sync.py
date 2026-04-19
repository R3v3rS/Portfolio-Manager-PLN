import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from database import init_db


class StockHistoryEndpointSyncTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "stock-history-test.db")

        warmup_patcher = patch("app.PriceService.warmup_cache", return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_does_not_sync_when_not_needed(self):
        with patch("routes_history.PriceService.get_tickers_requiring_history_sync", return_value=[]), patch(
            "routes_history.PriceService.should_refresh_stock_history",
            return_value=False,
        ), patch(
            "routes_history.PriceService.sync_stock_history",
            return_value=None,
        ) as sync_mock:
            response = self.client.get("/api/portfolio/history/AAPL")
            self.assertEqual(response.status_code, 200)
            sync_mock.assert_not_called()

    def test_syncs_when_needed(self):
        with patch("routes_history.PriceService.get_tickers_requiring_history_sync", return_value=["AAPL"]), patch(
            "routes_history.PriceService.should_refresh_stock_history",
            return_value=False,
        ), patch(
            "routes_history.PriceService.sync_stock_history",
            return_value=None,
        ) as sync_mock:
            response = self.client.get("/api/portfolio/history/AAPL")
            self.assertEqual(response.status_code, 200)
            sync_mock.assert_called_once()

    def test_refresh_forces_sync(self):
        with patch("routes_history.PriceService.get_tickers_requiring_history_sync", return_value=[]), patch(
            "routes_history.PriceService.should_refresh_stock_history",
            return_value=False,
        ), patch(
            "routes_history.PriceService.sync_stock_history",
            return_value=None,
        ) as sync_mock:
            response = self.client.get("/api/portfolio/history/AAPL?refresh=1")
            self.assertEqual(response.status_code, 200)
            sync_mock.assert_called_once()

    def test_refresh_validation(self):
        response = self.client.get("/api/portfolio/history/AAPL?refresh=2")
        self.assertEqual(response.status_code, 400)

    def test_syncs_when_refresh_ttl_expired(self):
        with patch("routes_history.PriceService.get_tickers_requiring_history_sync", return_value=[]), patch(
            "routes_history.PriceService.should_refresh_stock_history",
            return_value=True,
        ), patch(
            "routes_history.PriceService.sync_stock_history",
            return_value=None,
        ) as sync_mock:
            response = self.client.get("/api/portfolio/history/AAPL")
            self.assertEqual(response.status_code, 200)
            sync_mock.assert_called_once()
