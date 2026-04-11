import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402


class DashboardDividendsEndpointTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'dashboard-dividends-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    @staticmethod
    def _frozen_date(year=2026, month=4, day=20):
        class FrozenDate(date):
            @classmethod
            def today(cls):
                return cls(year, month, day)

        return FrozenDate

    def test_current_month_dividends_returns_received_expected_and_top_payers(self):
        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO portfolios (name, current_cash, account_type, created_at) VALUES (?, ?, ?, ?)",
                ('Income', 0, 'STANDARD', '2026-01-01'),
            )
            portfolio_id = db.execute("SELECT id FROM portfolios WHERE name = ?", ('Income',)).fetchone()['id']

            db.execute(
                """
                INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost)
                VALUES (?, ?, ?, ?, ?)
                """,
                (portfolio_id, 'DNP.WA', 10.0, 100.0, 1000.0),
            )
            db.execute(
                """
                INSERT INTO radar_cache (ticker, price, ex_dividend_date, dividend_yield)
                VALUES (?, ?, ?, ?)
                """,
                ('DNP.WA', 120.0, '2026-04-10', 12.0),
            )
            db.execute(
                """
                INSERT INTO dividends (portfolio_id, ticker, amount, date)
                VALUES (?, ?, ?, ?), (?, ?, ?, ?), (?, ?, ?, ?)
                """,
                (
                    portfolio_id, 'DNP.WA', 120.0, '2026-04-15',
                    portfolio_id, 'ABC.WA', 80.0, '2026-04-08',
                    portfolio_id, 'DNP.WA', 40.0, '2026-03-10',
                ),
            )
            db.commit()

        with patch('routes_dashboard.date', self._frozen_date(2026, 4, 20)):
            response = self.client.get('/api/dashboard/dividends/current-month')

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()['payload']

        self.assertEqual(payload['month_label'], 'Kwiecień 2026')
        self.assertAlmostEqual(payload['received_this_month'], 200.0)
        self.assertAlmostEqual(payload['expected_this_month'], 12.0)
        self.assertEqual(payload['top_payers'][0]['ticker'], 'DNP.WA')
        self.assertAlmostEqual(payload['top_payers'][0]['amount'], 120.0)
