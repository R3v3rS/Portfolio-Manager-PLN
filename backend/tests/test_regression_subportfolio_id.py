import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402


class RegressionSubportfolioIdTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'regression-subportfolio-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    def _create_parent(self, name='Parent'):
        response = self.client.post('/api/portfolio/create', json={
            'name': name,
            'initial_cash': 0.0,
            'account_type': 'STANDARD',
            'created_at': '2026-01-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def test_buy_sell_without_sub_portfolio_id_uses_null(self):
        parent_id = self._create_parent()

        # 1. Deposit cash without sub_portfolio_id
        response = self.client.post('/api/portfolio/deposit', json={
            'portfolio_id': parent_id,
            'amount': 1000.0,
            'date': '2026-01-01',
            # sub_portfolio_id is missing
        })
        self.assertEqual(response.status_code, 200, response.get_json())

        # 2. Buy stock without sub_portfolio_id
        response = self.client.post('/api/portfolio/buy', json={
            'portfolio_id': parent_id,
            'ticker': 'AAPL',
            'quantity': 10,
            'price': 50.0,
            'date': '2026-01-02',
            # sub_portfolio_id is missing
        })
        self.assertEqual(response.status_code, 200, response.get_json())

        # Verify DB state for holdings
        with self.app.app_context():
            db = get_db()
            holding = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?', (parent_id, 'AAPL')).fetchone()
            self.assertIsNotNone(holding)
            self.assertIsNone(holding['sub_portfolio_id'], "sub_portfolio_id should be NULL in holdings")

            transaction = db.execute('SELECT * FROM transactions WHERE portfolio_id = ? AND ticker = ? AND type = "BUY"', (parent_id, 'AAPL')).fetchone()
            self.assertIsNotNone(transaction)
            self.assertIsNone(transaction['sub_portfolio_id'], "sub_portfolio_id should be NULL in transactions")

        # 3. Sell stock without sub_portfolio_id
        response = self.client.post('/api/portfolio/sell', json={
            'portfolio_id': parent_id,
            'ticker': 'AAPL',
            'quantity': 5,
            'price': 60.0,
            'date': '2026-01-03',
            # sub_portfolio_id is missing
        })
        self.assertEqual(response.status_code, 200, response.get_json())

        # Verify remaining holding
        with self.app.app_context():
            db = get_db()
            holding = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?', (parent_id, 'AAPL')).fetchone()
            self.assertIsNotNone(holding)
            self.assertEqual(holding['quantity'], 5)
            self.assertIsNone(holding['sub_portfolio_id'], "sub_portfolio_id should still be NULL in holdings")

    def test_buy_with_explicit_null_sub_portfolio_id_uses_null(self):
        parent_id = self._create_parent()

        # 1. Deposit cash with sub_portfolio_id = null
        response = self.client.post('/api/portfolio/deposit', json={
            'portfolio_id': parent_id,
            'amount': 1000.0,
            'date': '2026-01-01',
            'sub_portfolio_id': None
        })
        self.assertEqual(response.status_code, 200, response.get_json())

        # 2. Buy stock with sub_portfolio_id = null
        response = self.client.post('/api/portfolio/buy', json={
            'portfolio_id': parent_id,
            'ticker': 'MSFT',
            'quantity': 10,
            'price': 100.0,
            'date': '2026-01-02',
            'sub_portfolio_id': None
        })
        self.assertEqual(response.status_code, 200, response.get_json())

        # Verify DB state
        with self.app.app_context():
            db = get_db()
            holding = db.execute('SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ?', (parent_id, 'MSFT')).fetchone()
            self.assertIsNotNone(holding)
            self.assertIsNone(holding['sub_portfolio_id'], "sub_portfolio_id should be NULL when explicitly sent as null")


if __name__ == '__main__':
    unittest.main()
