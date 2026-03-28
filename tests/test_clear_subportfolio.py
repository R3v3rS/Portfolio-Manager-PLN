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


class ClearSubportfolioTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'clear-subportfolio-test.db')

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
            'initial_cash': 1000.0,
            'account_type': 'STANDARD',
            'created_at': '2026-03-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _create_child(self, parent_id, name='Child'):
        response = self.client.post(f'/api/portfolio/{parent_id}/children', json={
            'name': name,
            'initial_cash': 100.0,
            'created_at': '2026-03-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _insert_position_data(self, parent_id, child_id):
        with self.app.app_context():
            db = get_db()
            db.execute(
                '''
                INSERT INTO transactions (
                    portfolio_id, ticker, date, type, quantity, price, total_value, sub_portfolio_id
                ) VALUES (?, 'AAPL', '2026-03-02', 'BUY', 1, 100, 100, ?)
                ''',
                (parent_id, child_id),
            )
            db.execute(
                '''
                INSERT INTO holdings (
                    portfolio_id, ticker, quantity, average_buy_price, total_cost, sub_portfolio_id
                ) VALUES (?, 'AAPL', 1, 100, 100, ?)
                ''',
                (parent_id, child_id),
            )
            db.execute(
                '''
                INSERT INTO dividends (portfolio_id, ticker, amount, date, sub_portfolio_id)
                VALUES (?, 'AAPL', 3.5, '2026-03-05', ?)
                ''',
                (parent_id, child_id),
            )
            db.commit()

    def test_clear_child_portfolio_returns_422(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)
        self._insert_position_data(parent_id, child_id)

        response = self.client.post(f'/api/portfolio/{child_id}/clear')

        self.assertEqual(response.status_code, 422, response.get_json())
        body = response.get_json()['error']
        self.assertEqual(body['code'], 'INVALID_ACTION')
        self.assertEqual(
            body['message'],
            'Czyszczenie sub-portfela nie jest dozwolone. Przenieś transakcje ręcznie.',
        )

    def test_clear_parent_with_active_children_returns_422(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)
        self._insert_position_data(parent_id, child_id)

        response = self.client.post(f'/api/portfolio/{parent_id}/clear')

        self.assertEqual(response.status_code, 422, response.get_json())
        body = response.get_json()['error']
        self.assertEqual(body['code'], 'INVALID_ACTION')
        self.assertEqual(body['message'], 'Najpierw zarchiwizuj sub-portfele.')

    def test_clear_parent_without_active_children_keeps_existing_behavior(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)
        self._insert_position_data(parent_id, child_id)

        archive_response = self.client.post(f'/api/portfolio/{child_id}/archive')
        self.assertEqual(archive_response.status_code, 200, archive_response.get_json())

        clear_response = self.client.post(f'/api/portfolio/{parent_id}/clear')
        self.assertEqual(clear_response.status_code, 200, clear_response.get_json())

        payload = clear_response.get_json()['payload']
        self.assertTrue(payload['success'])
        self.assertGreaterEqual(payload['deleted']['transactions'], 1)
        self.assertEqual(payload['deleted']['holdings'], 1)
        self.assertEqual(payload['deleted']['dividends'], 1)


if __name__ == '__main__':
    unittest.main()
