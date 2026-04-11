import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402


class CashTransferTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'cash-transfer-test.db')

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

    def _archive_child(self, child_id):
        response = self.client.post(f'/api/portfolio/{child_id}/archive')
        self.assertEqual(response.status_code, 200, response.get_json())

    def _cash(self, portfolio_id):
        with self.app.app_context():
            row = get_db().execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
            return float(row['current_cash']) if row else None

    def _tx_for_transfer(self, transfer_id):
        with self.app.app_context():
            rows = get_db().execute(
                'SELECT id, type, portfolio_id, sub_portfolio_id, transfer_id FROM transactions WHERE transfer_id = ? ORDER BY id',
                (transfer_id,),
            ).fetchall()
            return [{k: row[k] for k in row.keys()} for row in rows]

    def _create_tree(self):
        parent_a = self._create_parent('Parent A', initial_cash=5000.0)
        child_a1 = self._create_child(parent_a, 'A1', initial_cash=1000.0)
        child_a2 = self._create_child(parent_a, 'A2', initial_cash=500.0)
        parent_b = self._create_parent('Parent B', initial_cash=4000.0)
        child_b1 = self._create_child(parent_b, 'B1', initial_cash=1200.0)
        return parent_a, child_a1, child_a2, parent_b, child_b1

    def _transfer(self, payload):
        return self.client.post('/api/portfolio/transfer/cash', json=payload)

    def test_01_child_to_child_same_parent(self):
        parent_a, child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()

        response = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 200.0,
            'date': '2026-03-10',
            'note': 'test',
        })

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()['payload']
        transfer_id = payload['transfer_id']
        rows = self._tx_for_transfer(transfer_id)

        self.assertEqual(len(rows), 2)
        self.assertEqual({row['type'] for row in rows}, {'WITHDRAW', 'DEPOSIT'})
        self.assertTrue(all(row['transfer_id'] == transfer_id for row in rows))
        self.assertEqual(payload['from'], {'portfolio_id': parent_a, 'sub_portfolio_id': child_a1})
        self.assertEqual(payload['to'], {'portfolio_id': parent_a, 'sub_portfolio_id': child_a2})

    def test_02_child_to_parent(self):
        _parent_a, child_a1, _child_a2, _parent_b, _child_b1 = self._create_tree()

        response = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': self._parent_from_child(child_a1),
            'to_sub_portfolio_id': None,
            'amount': 100.0,
            'date': '2026-03-11',
            'note': None,
        })
        self.assertEqual(response.status_code, 200, response.get_json())

    def _parent_from_child(self, child_id):
        with self.app.app_context():
            row = get_db().execute('SELECT parent_portfolio_id FROM portfolios WHERE id = ?', (child_id,)).fetchone()
            return int(row['parent_portfolio_id'])

    def test_03_parent_to_child(self):
        parent_a, _child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()

        response = self._transfer({
            'from_portfolio_id': parent_a,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 150.0,
            'date': '2026-03-12',
            'note': None,
        })

        self.assertEqual(response.status_code, 200, response.get_json())

    def test_04_child_to_child_different_parents_returns_422(self):
        _parent_a, child_a1, _child_a2, _parent_b, child_b1 = self._create_tree()

        response = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_b1,
            'to_sub_portfolio_id': None,
            'amount': 50.0,
            'date': '2026-03-13',
            'note': None,
        })

        self.assertEqual(response.status_code, 422, response.get_json())

    def test_05_parent_to_other_parent_returns_422(self):
        parent_a, _child_a1, _child_a2, parent_b, _child_b1 = self._create_tree()

        response = self._transfer({
            'from_portfolio_id': parent_a,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': parent_b,
            'to_sub_portfolio_id': None,
            'amount': 50.0,
            'date': '2026-03-13',
            'note': None,
        })

        self.assertEqual(response.status_code, 422, response.get_json())

    def test_06_archived_child_as_source_returns_422(self):
        _parent_a, child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()
        self._archive_child(child_a1)

        response = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 25.0,
            'date': '2026-03-14',
            'note': None,
        })

        self.assertEqual(response.status_code, 422, response.get_json())

    def test_07_archived_child_as_target_returns_422(self):
        _parent_a, child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()
        self._archive_child(child_a2)

        response = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 25.0,
            'date': '2026-03-14',
            'note': None,
        })

        self.assertEqual(response.status_code, 422, response.get_json())

    def test_08_insufficient_cash_returns_422(self):
        _parent_a, child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()

        response = self._transfer({
            'from_portfolio_id': child_a2,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a1,
            'to_sub_portfolio_id': None,
            'amount': 999999.0,
            'date': '2026-03-14',
            'note': None,
        })

        self.assertEqual(response.status_code, 422, response.get_json())

    def test_09_future_date_returns_422(self):
        _parent_a, child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        response = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 25.0,
            'date': tomorrow,
            'note': None,
        })

        self.assertEqual(response.status_code, 422, response.get_json())

    def test_10_delete_transfer_restores_cash_and_deletes_transactions(self):
        _parent_a, child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()
        source_before = self._cash(child_a1)
        target_before = self._cash(child_a2)

        create_response = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 300.0,
            'date': '2026-03-15',
            'note': None,
        })
        self.assertEqual(create_response.status_code, 200, create_response.get_json())
        transfer_id = create_response.get_json()['payload']['transfer_id']

        delete_response = self.client.delete(f'/api/portfolio/transfer/cash/{transfer_id}')
        self.assertEqual(delete_response.status_code, 200, delete_response.get_json())

        self.assertAlmostEqual(self._cash(child_a1), source_before)
        self.assertAlmostEqual(self._cash(child_a2), target_before)
        self.assertEqual(self._tx_for_transfer(transfer_id), [])

    def test_11_delete_non_existing_transfer_returns_422(self):
        response = self.client.delete('/api/portfolio/transfer/cash/does-not-exist')
        self.assertEqual(response.status_code, 422, response.get_json())

    def test_12_backdated_transfer_uses_historical_cash_balance(self):
        _parent_a, child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()

        withdraw_response = self.client.post('/api/portfolio/withdraw', json={
            'portfolio_id': child_a1,
            'amount': 900.0,
            'date': '2026-01-15',
            'sub_portfolio_id': None,
        })
        self.assertEqual(withdraw_response.status_code, 200, withdraw_response.get_json())

        deposit_response = self.client.post('/api/portfolio/deposit', json={
            'portfolio_id': child_a1,
            'amount': 1000.0,
            'date': '2026-03-20',
            'sub_portfolio_id': None,
        })
        self.assertEqual(deposit_response.status_code, 200, deposit_response.get_json())

        response = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 300.0,
            'date': '2026-02-01',
            'note': None,
        })

        self.assertEqual(response.status_code, 422, response.get_json())
        error = response.get_json()['error']
        self.assertIn('Niewystarczająca gotówka na dzień 2026-02-01', error['message'])

    def test_13_backdated_transfer_repairs_cash_state_instead_of_only_applying_delta(self):
        _parent_a, child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()

        deposit_response = self.client.post('/api/portfolio/deposit', json={
            'portfolio_id': child_a1,
            'amount': 200.0,
            'date': '2026-03-20',
            'sub_portfolio_id': None,
        })
        self.assertEqual(deposit_response.status_code, 200, deposit_response.get_json())

        with self.app.app_context():
            db = get_db()
            db.execute('UPDATE portfolios SET current_cash = ? WHERE id = ?', (5000.0, child_a1))
            db.execute('UPDATE portfolios SET current_cash = ? WHERE id = ?', (50.0, child_a2))
            db.commit()

        response = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 300.0,
            'date': '2026-02-01',
            'note': None,
        })

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertAlmostEqual(self._cash(child_a1), 900.0)
        self.assertAlmostEqual(self._cash(child_a2), 800.0)

    def test_14_transfer_validation_uses_same_cash_rules_as_valuation(self):
        _parent_a, child_a1, child_a2, _parent_b, _child_b1 = self._create_tree()

        buy_response = self.client.post('/api/portfolio/buy', json={
            'portfolio_id': child_a1,
            'ticker': 'AAA',
            'quantity': 10,
            'price': 80.0,
            'date': '2026-01-10',
            'sub_portfolio_id': None,
        })
        self.assertEqual(buy_response.status_code, 200, buy_response.get_json())

        transfer_after_buy = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 400.0,
            'date': '2026-01-11',
            'note': None,
        })
        self.assertEqual(transfer_after_buy.status_code, 422, transfer_after_buy.get_json())

        sell_response = self.client.post('/api/portfolio/sell', json={
            'portfolio_id': child_a1,
            'ticker': 'AAA',
            'quantity': 10,
            'price': 30.0,
            'date': '2026-01-12',
            'sub_portfolio_id': None,
        })
        self.assertEqual(sell_response.status_code, 200, sell_response.get_json())

        transfer_after_sell = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 400.0,
            'date': '2026-01-12',
            'note': None,
        })
        self.assertEqual(transfer_after_sell.status_code, 200, transfer_after_sell.get_json())

        dividend_response = self.client.post('/api/portfolio/dividend', json={
            'portfolio_id': child_a1,
            'ticker': 'AAA',
            'amount': 50.0,
            'date': '2026-01-13',
            'sub_portfolio_id': None,
        })
        self.assertEqual(dividend_response.status_code, 201, dividend_response.get_json())

        transfer_after_dividend = self._transfer({
            'from_portfolio_id': child_a1,
            'from_sub_portfolio_id': None,
            'to_portfolio_id': child_a2,
            'to_sub_portfolio_id': None,
            'amount': 120.0,
            'date': '2026-01-14',
            'note': None,
        })
        self.assertEqual(transfer_after_dividend.status_code, 200, transfer_after_dividend.get_json())


if __name__ == '__main__':
    unittest.main()
