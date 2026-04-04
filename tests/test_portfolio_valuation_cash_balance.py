import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import init_db  # noqa: E402
from portfolio_service import PortfolioService  # noqa: E402


class PortfolioValuationCashBalanceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'valuation-cash-balance-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    def _create_parent(self, name, initial_cash=0.0):
        response = self.client.post('/api/portfolio/create', json={
            'name': name,
            'initial_cash': initial_cash,
            'account_type': 'STANDARD',
            'created_at': '2026-01-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _create_child(self, parent_id, name, initial_cash=0.0):
        response = self.client.post(f'/api/portfolio/{parent_id}/children', json={
            'name': name,
            'initial_cash': initial_cash,
            'created_at': '2026-01-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def test_buy_sell_dividend_are_reflected_in_cash_balance_on_date(self):
        parent_id = self._create_parent('Parent', initial_cash=0.0)
        child_id = self._create_child(parent_id, 'Child', initial_cash=1000.0)

        buy = self.client.post('/api/portfolio/buy', json={
            'portfolio_id': child_id,
            'ticker': 'AAA',
            'quantity': 10,
            'price': 20,
            'date': '2026-01-10',
            'sub_portfolio_id': None,
        })
        self.assertEqual(buy.status_code, 200, buy.get_json())

        sell = self.client.post('/api/portfolio/sell', json={
            'portfolio_id': child_id,
            'ticker': 'AAA',
            'quantity': 10,
            'price': 25,
            'date': '2026-01-11',
            'sub_portfolio_id': None,
        })
        self.assertEqual(sell.status_code, 200, sell.get_json())

        dividend = self.client.post('/api/portfolio/dividend', json={
            'portfolio_id': child_id,
            'ticker': 'AAA',
            'amount': 30,
            'date': '2026-01-12',
            'sub_portfolio_id': None,
        })
        self.assertEqual(dividend.status_code, 201, dividend.get_json())

        with self.app.app_context():
            balance = PortfolioService.get_cash_balance_on_date(parent_id, '2026-01-12', sub_portfolio_id=child_id)

        self.assertAlmostEqual(balance, 1080.0)


if __name__ == '__main__':
    unittest.main()
