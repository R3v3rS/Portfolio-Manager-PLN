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


class AuditCashNegativeDaysTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'audit-cash-negative-test.db')

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

    def _insert_transaction(self, *, portfolio_id, tx_type, total_value, date='2026-03-01', sub_portfolio_id=None):
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                '''
                INSERT INTO transactions (
                    portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (portfolio_id, 'CASH', tx_type, 1.0, float(total_value), float(total_value), date, sub_portfolio_id),
            )
            db.commit()
            return cursor.lastrowid

    def _get_row(self, portfolio_id):
        response = self.client.get('/api/portfolio/audit/consistency')
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = response.get_json()['payload']['portfolios']
        return next(row for row in rows if row['portfolio_id'] == portfolio_id)

    def test_portfolio_without_incidents_returns_ok_true_and_empty_incidents(self):
        parent_id = self._create_parent('No incidents')
        self._create_child(parent_id)
        self._insert_transaction(portfolio_id=parent_id, tx_type='DEPOSIT', total_value=100.0, date='2026-03-01')
        self._insert_transaction(portfolio_id=parent_id, tx_type='WITHDRAW', total_value=20.0, date='2026-03-02')

        row = self._get_row(parent_id)

        check = row['checks']['cash_negative_days']
        self.assertTrue(check['ok'])
        self.assertEqual(check['incidents'], [])

    def test_withdraw_above_balance_creates_incident_with_correct_date_and_amount(self):
        parent_id = self._create_parent('Withdraw incident')
        self._create_child(parent_id)
        self._insert_transaction(portfolio_id=parent_id, tx_type='DEPOSIT', total_value=100.0, date='2026-03-01')
        withdraw_id = self._insert_transaction(portfolio_id=parent_id, tx_type='WITHDRAW', total_value=150.0, date='2026-03-02')

        row = self._get_row(parent_id)

        check = row['checks']['cash_negative_days']
        self.assertFalse(check['ok'])
        self.assertGreaterEqual(len(check['incidents']), 1)
        first = check['incidents'][0]
        self.assertEqual(first['date'], '2026-03-02')
        self.assertAlmostEqual(first['balance_pln'], -50.0, places=2)
        self.assertEqual(first['triggering_transaction_id'], withdraw_id)
        self.assertEqual(first['triggering_type'], 'WITHDRAW')
        self.assertAlmostEqual(first['triggering_amount'], 150.0, places=2)

    def test_buy_can_trigger_negative_balance(self):
        parent_id = self._create_parent('Buy incident')
        self._create_child(parent_id)
        self._insert_transaction(portfolio_id=parent_id, tx_type='DEPOSIT', total_value=100.0, date='2026-03-01')
        buy_id = self._insert_transaction(portfolio_id=parent_id, tx_type='BUY', total_value=130.0, date='2026-03-02')

        row = self._get_row(parent_id)

        check = row['checks']['cash_negative_days']
        self.assertFalse(check['ok'])
        first = check['incidents'][0]
        self.assertEqual(first['date'], '2026-03-02')
        self.assertEqual(first['triggering_transaction_id'], buy_id)
        self.assertEqual(first['triggering_type'], 'BUY')
        self.assertAlmostEqual(first['triggering_amount'], 130.0, places=2)

    def test_later_deposit_repairs_balance_but_incident_day_remains_visible(self):
        parent_id = self._create_parent('Repair later')
        self._create_child(parent_id)
        self._insert_transaction(portfolio_id=parent_id, tx_type='DEPOSIT', total_value=100.0, date='2026-03-01')
        self._insert_transaction(portfolio_id=parent_id, tx_type='WITHDRAW', total_value=150.0, date='2026-03-02')
        self._insert_transaction(portfolio_id=parent_id, tx_type='DEPOSIT', total_value=100.0, date='2026-03-03')

        row = self._get_row(parent_id)

        check = row['checks']['cash_negative_days']
        incident_dates = {incident['date'] for incident in check['incidents']}
        self.assertIn('2026-03-02', incident_dates)
        self.assertNotIn('2026-03-03', incident_dates)

    def test_child_is_checked_separately_and_parent_stays_clean(self):
        parent_id = self._create_parent('Child separate')
        child_id = self._create_child(parent_id)

        self._insert_transaction(portfolio_id=parent_id, tx_type='DEPOSIT', total_value=100.0, date='2026-03-01')
        self._insert_transaction(
            portfolio_id=parent_id,
            tx_type='BUY',
            total_value=150.0,
            date='2026-03-02',
            sub_portfolio_id=child_id,
        )

        parent_row = self._get_row(parent_id)
        child_row = self._get_row(child_id)

        self.assertTrue(parent_row['checks']['cash_negative_days']['ok'])
        self.assertEqual(parent_row['checks']['cash_negative_days']['incidents'], [])

        self.assertFalse(child_row['checks']['cash_negative_days']['ok'])
        self.assertGreaterEqual(len(child_row['checks']['cash_negative_days']['incidents']), 1)


if __name__ == '__main__':
    unittest.main()
