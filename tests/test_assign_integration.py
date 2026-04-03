import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402
from routes_transactions import PortfolioService  # noqa: E402


class AssignTransactionsIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'assign-integration-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    # -------- Helpers --------

    def _create_parent(self, name='Parent'):
        response = self.client.post('/api/portfolio/create', json={
            'name': name,
            'initial_cash': 10000.0,
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

    def _archive_child(self, child_id):
        response = self.client.post(f'/api/portfolio/{child_id}/archive')
        self.assertEqual(response.status_code, 200, response.get_json())

    def _insert_transaction(self, portfolio_id, tx_type='BUY', sub_portfolio_id=None, ticker='TST'):
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                '''
                INSERT INTO transactions (
                    portfolio_id, ticker, type, quantity, price, total_value, date, sub_portfolio_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (portfolio_id, ticker, tx_type, 1, 100.0, 100.0, '2026-03-02', sub_portfolio_id),
            )
            db.commit()
            return cursor.lastrowid

    @staticmethod
    def _is_parent_scope(sub_portfolio_id):
        return sub_portfolio_id in (None, 0)

    def _tx_state(self, tx_id):
        with self.app.app_context():
            db = get_db()
            row = db.execute(
                'SELECT id, portfolio_id, sub_portfolio_id, type FROM transactions WHERE id = ?',
                (tx_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        return dict(row)

    def _assign_single(self, tx_id, sub_portfolio_id):
        return self.client.put(
            f'/api/portfolio/transactions/{tx_id}/assign',
            json={'sub_portfolio_id': sub_portfolio_id},
        )

    def _assign_bulk(self, tx_ids, sub_portfolio_id):
        return self.client.post('/api/portfolio/transactions/assign-bulk', json={
            'transaction_ids': tx_ids,
            'sub_portfolio_id': sub_portfolio_id,
        })

    # -------- Happy paths (200) --------

    def test_assign_parent_to_child_changes_only_sub_portfolio(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)

        tx_id = self._insert_transaction(parent_id, tx_type='BUY', sub_portfolio_id=None, ticker='P2C')
        before = self._tx_state(tx_id)
        self.assertTrue(self._is_parent_scope(before['sub_portfolio_id']))

        response = self._assign_single(tx_id, child_id)
        self.assertEqual(response.status_code, 200, response.get_json())

        after = self._tx_state(tx_id)
        self.assertEqual(after['portfolio_id'], before['portfolio_id'])
        self.assertEqual(after['sub_portfolio_id'], child_id)

    def test_assign_child_to_parent_changes_only_sub_portfolio(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)

        tx_id = self._insert_transaction(parent_id, tx_type='BUY', sub_portfolio_id=child_id, ticker='C2P')
        before = self._tx_state(tx_id)
        self.assertEqual(before['sub_portfolio_id'], child_id)

        response = self._assign_single(tx_id, None)
        self.assertEqual(response.status_code, 200, response.get_json())

        after = self._tx_state(tx_id)
        self.assertEqual(after['portfolio_id'], before['portfolio_id'])
        self.assertTrue(self._is_parent_scope(after['sub_portfolio_id']))

    def test_assign_child_a_to_child_b_changes_only_sub_portfolio(self):
        parent_id = self._create_parent()
        child_a_id = self._create_child(parent_id, name='Child A')
        child_b_id = self._create_child(parent_id, name='Child B')

        tx_id = self._insert_transaction(parent_id, tx_type='BUY', sub_portfolio_id=child_a_id, ticker='A2B')
        before = self._tx_state(tx_id)
        self.assertEqual(before['sub_portfolio_id'], child_a_id)

        response = self._assign_single(tx_id, child_b_id)
        self.assertEqual(response.status_code, 200, response.get_json())

        after = self._tx_state(tx_id)
        self.assertEqual(after['portfolio_id'], before['portfolio_id'])
        self.assertEqual(after['sub_portfolio_id'], child_b_id)

    # -------- Validation errors (422) --------

    def test_assign_to_child_of_different_parent_returns_422(self):
        parent_a_id = self._create_parent(name='Parent A')
        child_a_id = self._create_child(parent_a_id, name='A Child')

        parent_b_id = self._create_parent(name='Parent B')
        child_b_id = self._create_child(parent_b_id, name='B Child')

        tx_id = self._insert_transaction(parent_a_id, tx_type='BUY', sub_portfolio_id=None, ticker='CROSS')

        response = self._assign_single(tx_id, child_b_id)
        self.assertEqual(response.status_code, 422, response.get_json())

        after = self._tx_state(tx_id)
        self.assertEqual(after['portfolio_id'], parent_a_id)
        self.assertTrue(self._is_parent_scope(after['sub_portfolio_id']))
        self.assertNotEqual(child_a_id, child_b_id)

    def test_assign_to_archived_child_returns_422(self):
        parent_id = self._create_parent()
        archived_child_id = self._create_child(parent_id, name='Archived Child')
        self._archive_child(archived_child_id)

        tx_id = self._insert_transaction(parent_id, tx_type='BUY', sub_portfolio_id=None, ticker='ARCH')

        response = self._assign_single(tx_id, archived_child_id)
        self.assertEqual(response.status_code, 422, response.get_json())

        after = self._tx_state(tx_id)
        self.assertEqual(after['portfolio_id'], parent_id)
        self.assertTrue(self._is_parent_scope(after['sub_portfolio_id']))

    def test_assign_interest_to_child_returns_422(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)

        tx_id = self._insert_transaction(parent_id, tx_type='INTEREST', sub_portfolio_id=None, ticker='CASH')

        response = self._assign_single(tx_id, child_id)
        self.assertEqual(response.status_code, 422, response.get_json())

        after = self._tx_state(tx_id)
        self.assertEqual(after['portfolio_id'], parent_id)
        self.assertTrue(self._is_parent_scope(after['sub_portfolio_id']))
        self.assertEqual(after['type'], 'INTEREST')

    def test_bulk_assign_with_interest_in_set_returns_422_and_is_atomic(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)

        buy_tx_id = self._insert_transaction(parent_id, tx_type='BUY', sub_portfolio_id=None, ticker='BULK1')
        interest_tx_id = self._insert_transaction(parent_id, tx_type='INTEREST', sub_portfolio_id=None, ticker='CASH')

        before_buy = self._tx_state(buy_tx_id)
        before_interest = self._tx_state(interest_tx_id)

        response = self._assign_bulk([buy_tx_id, interest_tx_id], child_id)
        self.assertEqual(response.status_code, 422, response.get_json())

        after_buy = self._tx_state(buy_tx_id)
        after_interest = self._tx_state(interest_tx_id)

        self.assertEqual(after_buy['portfolio_id'], before_buy['portfolio_id'])
        self.assertEqual(after_buy['sub_portfolio_id'], before_buy['sub_portfolio_id'])

        self.assertEqual(after_interest['portfolio_id'], before_interest['portfolio_id'])
        self.assertEqual(after_interest['sub_portfolio_id'], before_interest['sub_portfolio_id'])
        self.assertEqual(after_interest['type'], 'INTEREST')

    def test_bulk_assign_cross_parent_returns_422(self):
        parent_a_id = self._create_parent(name='Parent A')
        child_a_id = self._create_child(parent_a_id, name='A Child')

        parent_b_id = self._create_parent(name='Parent B')

        tx_a_id = self._insert_transaction(parent_a_id, tx_type='BUY', sub_portfolio_id=None, ticker='PA')
        tx_b_id = self._insert_transaction(parent_b_id, tx_type='BUY', sub_portfolio_id=None, ticker='PB')

        before_a = self._tx_state(tx_a_id)
        before_b = self._tx_state(tx_b_id)

        response = self._assign_bulk([tx_a_id, tx_b_id], child_a_id)
        self.assertEqual(response.status_code, 422, response.get_json())

        after_a = self._tx_state(tx_a_id)
        after_b = self._tx_state(tx_b_id)

        self.assertEqual(after_a['portfolio_id'], before_a['portfolio_id'])
        self.assertEqual(after_a['sub_portfolio_id'], before_a['sub_portfolio_id'])

        self.assertEqual(after_b['portfolio_id'], before_b['portfolio_id'])
        self.assertEqual(after_b['sub_portfolio_id'], before_b['sub_portfolio_id'])

    def test_assign_single_rebuilds_parent_and_children_with_correct_argument_order(self):
        parent_id = self._create_parent()
        old_child_id = self._create_child(parent_id, name='Old Child')
        new_child_id = self._create_child(parent_id, name='New Child')
        tx_id = self._insert_transaction(parent_id, tx_type='BUY', sub_portfolio_id=old_child_id, ticker='ORDER1')

        with patch.object(PortfolioService, 'repair_portfolio_state', wraps=PortfolioService.repair_portfolio_state) as repair_spy:
            response = self._assign_single(tx_id, new_child_id)

        self.assertEqual(response.status_code, 200, response.get_json())
        expected_calls = [
            call(parent_id, subportfolio_id=None),
            call(parent_id, subportfolio_id=new_child_id),
            call(parent_id, subportfolio_id=old_child_id),
        ]
        self.assertEqual(repair_spy.call_args_list, expected_calls)
        self.assertTrue(all(call.args[0] == parent_id for call in repair_spy.call_args_list))

    def test_assign_bulk_rebuilds_parent_and_children_with_correct_argument_order(self):
        parent_id = self._create_parent()
        old_child_a_id = self._create_child(parent_id, name='Old Child A')
        old_child_b_id = self._create_child(parent_id, name='Old Child B')
        target_child_id = self._create_child(parent_id, name='Target Child')

        tx_a_id = self._insert_transaction(parent_id, tx_type='BUY', sub_portfolio_id=old_child_a_id, ticker='ORDER2A')
        tx_b_id = self._insert_transaction(parent_id, tx_type='BUY', sub_portfolio_id=old_child_b_id, ticker='ORDER2B')

        with patch.object(PortfolioService, 'repair_portfolio_state', wraps=PortfolioService.repair_portfolio_state) as repair_spy:
            response = self._assign_bulk([tx_a_id, tx_b_id], target_child_id)

        self.assertEqual(response.status_code, 200, response.get_json())
        expected_subportfolio_scopes = {
            call.kwargs.get('subportfolio_id')
            for call in repair_spy.call_args_list
        }
        self.assertEqual(expected_subportfolio_scopes, {None, target_child_id, old_child_a_id, old_child_b_id})
        self.assertEqual(len(repair_spy.call_args_list), 4)
        self.assertTrue(all(call.args[0] == parent_id for call in repair_spy.call_args_list))


if __name__ == '__main__':
    unittest.main()
