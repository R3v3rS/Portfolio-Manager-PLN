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


class DividendsSubportfolioTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'dividends-subportfolio-test.db')

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

    def _insert_dividend(self, portfolio_id, ticker, amount, date, sub_portfolio_id=None):
        with self.app.app_context():
            db = get_db()
            db.execute(
                '''
                INSERT INTO dividends (portfolio_id, ticker, amount, date, sub_portfolio_id)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (portfolio_id, ticker, amount, date, sub_portfolio_id),
            )
            db.commit()

    def test_get_dividends_for_child_uses_parent_and_child_filter(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id, name='Growth Child')
        other_parent_id = self._create_parent(name='Other Parent')
        other_child_id = self._create_child(other_parent_id, name='Other Child')

        self._insert_dividend(parent_id, 'PARENT', 10.0, '2026-01-10')
        self._insert_dividend(parent_id, 'CHILD', 20.0, '2026-02-10', sub_portfolio_id=child_id)
        self._insert_dividend(parent_id, 'CHILD2', 30.0, '2026-03-10', sub_portfolio_id=child_id)
        self._insert_dividend(other_parent_id, 'FOREIGN', 99.0, '2026-03-11', sub_portfolio_id=other_child_id)

        response = self.client.get(f'/api/portfolio/dividends/{child_id}')
        self.assertEqual(response.status_code, 200, response.get_json())

        payload = response.get_json()['payload']['dividends']
        self.assertEqual(len(payload), 2)
        self.assertEqual([row['ticker'] for row in payload], ['CHILD2', 'CHILD'])
        for row in payload:
            self.assertEqual(row['portfolio_id'], parent_id)
            self.assertEqual(row['sub_portfolio_id'], child_id)
            self.assertEqual(row['sub_portfolio_name'], 'Growth Child')

    def test_get_dividends_for_parent_returns_own_and_children_with_subportfolio_name(self):
        parent_id = self._create_parent(name='Main Parent')
        child_id = self._create_child(parent_id, name='Income Child')

        self._insert_dividend(parent_id, 'OWN', 11.0, '2026-01-05')
        self._insert_dividend(parent_id, 'SUB', 22.0, '2026-01-15', sub_portfolio_id=child_id)

        response = self.client.get(f'/api/portfolio/dividends/{parent_id}')
        self.assertEqual(response.status_code, 200, response.get_json())

        payload = response.get_json()['payload']['dividends']
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]['ticker'], 'SUB')
        self.assertEqual(payload[0]['sub_portfolio_id'], child_id)
        self.assertEqual(payload[0]['sub_portfolio_name'], 'Income Child')
        self.assertEqual(payload[1]['ticker'], 'OWN')
        self.assertIsNone(payload[1]['sub_portfolio_id'])
        self.assertIsNone(payload[1]['sub_portfolio_name'])

    def test_get_monthly_dividends_for_parent_and_child(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)

        self._insert_dividend(parent_id, 'OWN_JAN', 10.0, '2026-01-03')
        self._insert_dividend(parent_id, 'CHILD_JAN', 20.0, '2026-01-20', sub_portfolio_id=child_id)
        self._insert_dividend(parent_id, 'CHILD_FEB', 5.0, '2026-02-02', sub_portfolio_id=child_id)

        parent_response = self.client.get(f'/api/portfolio/dividends/monthly/{parent_id}')
        self.assertEqual(parent_response.status_code, 200, parent_response.get_json())
        parent_monthly = parent_response.get_json()['payload']['monthly_dividends']
        self.assertEqual(
            parent_monthly,
            [
                {'label': 'Jan 2026', 'amount': 30.0, 'key': '2026-01'},
                {'label': 'Feb 2026', 'amount': 5.0, 'key': '2026-02'},
            ],
        )

        child_response = self.client.get(f'/api/portfolio/dividends/monthly/{child_id}')
        self.assertEqual(child_response.status_code, 200, child_response.get_json())
        child_monthly = child_response.get_json()['payload']['monthly_dividends']
        self.assertEqual(
            child_monthly,
            [
                {'label': 'Jan 2026', 'amount': 20.0, 'key': '2026-01'},
                {'label': 'Feb 2026', 'amount': 5.0, 'key': '2026-02'},
            ],
        )


if __name__ == '__main__':
    unittest.main()
