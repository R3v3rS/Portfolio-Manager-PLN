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


class AssignValidationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'assign-validation-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

        self.parent_id = self._create_parent()
        self.child_id = self._create_child(self.parent_id)
        self.tx_id = self._insert_transaction(self.parent_id)

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

    def _insert_transaction(self, portfolio_id):
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                '''
                INSERT INTO transactions (
                    portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (portfolio_id, 'VAL', 'BUY', 1, 100.0, 100.0, '2026-03-02', None),
            )
            db.commit()
            return cursor.lastrowid

    def test_assign_transaction_rejects_invalid_sub_portfolio_id(self):
        invalid_values = [0, -1, '1', 1.5, True, [], {}]

        for value in invalid_values:
            response = self.client.put(
                f'/api/portfolio/transactions/{self.tx_id}/assign',
                json={'sub_portfolio_id': value},
            )
            self.assertEqual(response.status_code, 422, response.get_json())
            self.assertEqual(
                response.get_json()['error']['message'],
                'sub_portfolio_id must be a positive integer or null',
            )

    def test_assign_transactions_bulk_rejects_invalid_sub_portfolio_id(self):
        invalid_values = [0, -1, '1', 1.5, True, [], {}]

        for value in invalid_values:
            response = self.client.post('/api/portfolio/transactions/assign-bulk', json={
                'transaction_ids': [self.tx_id],
                'sub_portfolio_id': value,
            })
            self.assertEqual(response.status_code, 422, response.get_json())
            self.assertEqual(
                response.get_json()['error']['message'],
                'sub_portfolio_id must be a positive integer or null',
            )

    def test_assign_transactions_bulk_rejects_invalid_transaction_ids(self):
        invalid_values = [
            None,
            [],
            '1,2',
            [0],
            [-1],
            [1.5],
            ['1'],
            [True],
            [self.tx_id, 0],
        ]

        for value in invalid_values:
            response = self.client.post('/api/portfolio/transactions/assign-bulk', json={
                'transaction_ids': value,
                'sub_portfolio_id': self.child_id,
            })
            self.assertEqual(response.status_code, 422, response.get_json())
            self.assertEqual(
                response.get_json()['error']['message'],
                'transaction_ids must be a non-empty list of positive integers',
            )


if __name__ == '__main__':
    unittest.main()
