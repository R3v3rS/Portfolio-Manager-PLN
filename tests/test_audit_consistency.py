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
from portfolio_valuation_service import PortfolioValuationService  # noqa: E402


class AuditConsistencyTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'audit-consistency-test.db')

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
            'created_at': '2026-03-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _create_child(self, parent_id, name='Child'):
        response = self.client.post(f'/api/portfolio/{parent_id}/children', json={
            'name': name,
            'initial_cash': 0.0,
            'created_at': '2026-03-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _insert_transaction(self, *, portfolio_id, tx_type='DEPOSIT', sub_portfolio_id=None, date='2026-03-01'):
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                '''
                INSERT INTO transactions (
                    portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (portfolio_id, 'CASH', tx_type, 1.0, 100.0, 100.0, date, sub_portfolio_id),
            )
            db.commit()
            return cursor.lastrowid

    def _get_consistency(self):
        response = self.client.get('/api/portfolio/audit/consistency')
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()['payload']
        self.assertEqual(len(payload['portfolios']), 1)
        return payload['portfolios'][0]

    def test_portfolio_ok_returns_status_ok(self):
        parent_id = self._create_parent('OK Parent')
        self._create_child(parent_id, 'OK Child')

        row = self._get_consistency()

        self.assertEqual(row['status'], 'ok')
        self.assertTrue(row['checks']['value_match']['ok'])
        self.assertTrue(row['checks']['orphan_transactions']['ok'])
        self.assertTrue(row['checks']['interest_leaked']['ok'])
        self.assertTrue(row['checks']['archived_child_transactions']['ok'])

    def test_value_match_fail_when_parent_value_differs(self):
        parent_id = self._create_parent('Mismatch Parent')
        self._create_child(parent_id, 'Mismatch Child')

        original_get_value = PortfolioValuationService.get_portfolio_value

        def fake_get_value(portfolio_id):
            value = original_get_value(portfolio_id)
            if portfolio_id == parent_id and value:
                patched = dict(value)
                patched['portfolio_value'] = float(value['portfolio_value']) + 10.0
                return patched
            return value

        with patch.object(PortfolioValuationService, 'get_portfolio_value', side_effect=fake_get_value):
            row = self._get_consistency()

        self.assertEqual(row['status'], 'warning')
        self.assertFalse(row['checks']['value_match']['ok'])
        self.assertAlmostEqual(row['checks']['value_match']['diff_pln'], 10.0, places=2)

    def test_orphan_transaction_detected(self):
        parent_a_id = self._create_parent('Parent A')
        self._create_child(parent_a_id, 'Child A')

        parent_b_id = self._create_parent('Parent B')
        child_b_id = self._create_child(parent_b_id, 'Child B')

        self._insert_transaction(portfolio_id=parent_a_id, tx_type='BUY', sub_portfolio_id=child_b_id)

        response = self.client.get('/api/portfolio/audit/consistency')
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()['payload']['portfolios']
        row_a = next(row for row in rows if row['portfolio_id'] == parent_a_id)

        self.assertEqual(row_a['status'], 'error')
        self.assertFalse(row_a['checks']['orphan_transactions']['ok'])
        self.assertEqual(row_a['checks']['orphan_transactions']['count'], 1)

    def test_interest_leaked_detected(self):
        parent_id = self._create_parent('Interest Parent')
        child_id = self._create_child(parent_id, 'Interest Child')

        self._insert_transaction(portfolio_id=parent_id, tx_type='INTEREST', sub_portfolio_id=child_id)

        row = self._get_consistency()

        self.assertEqual(row['status'], 'error')
        self.assertFalse(row['checks']['interest_leaked']['ok'])
        self.assertEqual(row['checks']['interest_leaked']['count'], 1)

    def test_archived_child_transaction_detected(self):
        parent_id = self._create_parent('Archived Parent')
        child_id = self._create_child(parent_id, 'Archived Child')

        archive_response = self.client.post(f'/api/portfolio/{child_id}/archive')
        self.assertEqual(archive_response.status_code, 200, archive_response.get_json())

        self._insert_transaction(
            portfolio_id=parent_id,
            tx_type='BUY',
            sub_portfolio_id=child_id,
            date='2026-12-31',
        )

        row = self._get_consistency()

        self.assertEqual(row['status'], 'error')
        self.assertFalse(row['checks']['archived_child_transactions']['ok'])
        self.assertEqual(row['checks']['archived_child_transactions']['count'], 1)


if __name__ == '__main__':
    unittest.main()
