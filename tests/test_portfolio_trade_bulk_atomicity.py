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
from database import get_db, init_db  # noqa: E402
from portfolio_trade_service import PortfolioTradeService  # noqa: E402


class PortfolioTradeBulkAtomicityTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'trade-bulk-atomicity-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    def _create_parent(self):
        response = self.client.post('/api/portfolio/create', json={
            'name': 'Parent',
            'initial_cash': 10000.0,
            'account_type': 'STANDARD',
            'created_at': '2026-03-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _create_child(self, parent_id):
        response = self.client.post(f'/api/portfolio/{parent_id}/children', json={
            'name': 'Child',
            'initial_cash': 0.0,
            'created_at': '2026-03-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _insert_transaction(self, portfolio_id, tx_type, total_value):
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                '''
                INSERT INTO transactions (
                    portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (portfolio_id, 'VAL', tx_type, 1, total_value, total_value, '2026-03-02', None),
            )
            db.commit()
            return cursor.lastrowid

    def test_assign_transactions_bulk_rolls_back_entire_batch_on_error(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)

        buy_tx_id = self._insert_transaction(parent_id, 'BUY', 100.0)
        interest_tx_id = self._insert_transaction(parent_id, 'INTEREST', 5.0)

        with self.app.app_context():
            with self.assertRaises(ValueError):
                PortfolioTradeService.assign_transactions_bulk([buy_tx_id, interest_tx_id], child_id)

            db = get_db()
            rows = db.execute(
                'SELECT id, sub_portfolio_id FROM transactions WHERE id IN (?, ?) ORDER BY id',
                (buy_tx_id, interest_tx_id),
            ).fetchall()

            self.assertEqual(len(rows), 2)
            self.assertIsNone(rows[0]['sub_portfolio_id'])
            self.assertIsNone(rows[1]['sub_portfolio_id'])


if __name__ == '__main__':
    unittest.main()
