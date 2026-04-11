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
from database import init_db  # noqa: E402


class WithdrawValidationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'withdraw-validation-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    def _create_parent(self, name='Parent', initial_cash=1000.0):
        response = self.client.post('/api/portfolio/create', json={
            'name': name,
            'initial_cash': initial_cash,
            'account_type': 'STANDARD',
            'created_at': '2026-03-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _create_child(self, parent_id, name='Child', initial_cash=500.0):
        response = self.client.post(f'/api/portfolio/{parent_id}/children', json={
            'name': name,
            'initial_cash': initial_cash,
            'created_at': '2026-03-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _archive_child(self, child_id):
        response = self.client.post(f'/api/portfolio/{child_id}/archive')
        self.assertEqual(response.status_code, 200, response.get_json())

    def test_withdraw_without_subportfolio_happy_path(self):
        parent_id = self._create_parent(initial_cash=1000.0)

        response = self.client.post('/api/portfolio/withdraw', json={
            'portfolio_id': parent_id,
            'amount': 100.0,
            'date': '2026-03-10',
        })

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['payload']['message'], 'Withdrawal successful')

    def test_withdraw_with_valid_subportfolio_happy_path(self):
        parent_id = self._create_parent(initial_cash=1000.0)
        child_id = self._create_child(parent_id, initial_cash=500.0)

        response = self.client.post('/api/portfolio/withdraw', json={
            'portfolio_id': parent_id,
            'sub_portfolio_id': child_id,
            'amount': 100.0,
            'date': '2026-03-10',
        })

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['payload']['message'], 'Withdrawal successful')

    def test_withdraw_with_subportfolio_from_different_parent_returns_422(self):
        parent_a_id = self._create_parent(name='Parent A', initial_cash=1000.0)
        parent_b_id = self._create_parent(name='Parent B', initial_cash=1000.0)
        foreign_child_id = self._create_child(parent_b_id, name='B Child', initial_cash=500.0)

        response = self.client.post('/api/portfolio/withdraw', json={
            'portfolio_id': parent_a_id,
            'sub_portfolio_id': foreign_child_id,
            'amount': 100.0,
            'date': '2026-03-10',
        })

        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(
            response.get_json()['error']['message'],
            'Sub-portfolio belongs to a different parent portfolio',
        )

    def test_withdraw_with_archived_subportfolio_returns_422(self):
        parent_id = self._create_parent(initial_cash=1000.0)
        child_id = self._create_child(parent_id, initial_cash=500.0)
        self._archive_child(child_id)

        response = self.client.post('/api/portfolio/withdraw', json={
            'portfolio_id': parent_id,
            'sub_portfolio_id': child_id,
            'amount': 100.0,
            'date': '2026-03-10',
        })

        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(
            response.get_json()['error']['message'],
            'Cannot withdraw from an archived sub-portfolio',
        )

    def test_withdraw_with_non_existing_subportfolio_returns_422(self):
        parent_id = self._create_parent(initial_cash=1000.0)

        response = self.client.post('/api/portfolio/withdraw', json={
            'portfolio_id': parent_id,
            'sub_portfolio_id': 999999,
            'amount': 100.0,
            'date': '2026-03-10',
        })

        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()['error']['message'], 'Sub-portfolio not found')


if __name__ == '__main__':
    unittest.main()
