import base64
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.exceptions import NotFoundError, ValidationError  # noqa: E402
from api.response import error_response  # noqa: E402
from database import get_db, init_db, reset_budget_data  # noqa: E402
from routes_budget_workspace import workspace_bp  # noqa: E402


class BudgetWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            DATABASE=os.path.join(self.temp.name, 'budget.db'),
            BUDGET_RECEIPT_DIR=os.path.join(self.temp.name, 'receipts'),
        )
        app.register_blueprint(workspace_bp, url_prefix='/api/budget/workspace')
        app.register_error_handler(ValidationError, lambda error: error_response('validation_error', error.message, status=400))
        app.register_error_handler(NotFoundError, lambda error: error_response('not_found', error.message, status=404))
        init_db(app)
        self.app = app
        self.client = app.test_client()
        self.base = '/api/budget/workspace'

    def payload(self, response, status=200):
        self.assertEqual(response.status_code, status, response.json)
        return response.json['payload']

    def setup_account(self):
        account = self.payload(self.client.post(self.base + '/accounts', json={
            'name': 'Konto osobiste', 'balance': 1000,
        }), 201)
        snapshot = self.payload(self.client.get(self.base + '?month=2026-09'))
        return account['id'], {category['name']: category['id'] for category in snapshot['categories']}

    def test_plan_and_receipt_lines_change_spending_once_and_edits_reconcile_balance(self):
        account_id, categories = self.setup_account()
        food_id = categories['Jedzenie']
        self.payload(self.client.put(self.base + f'/plans/{food_id}', json={
            'month': '2026-09', 'amount': 500,
        }))
        entry = {
            'account_id': account_id, 'kind': 'EXPENSE', 'amount': 25,
            'date': '2026-09-10', 'description': 'Zakupy', 'merchant': 'Sklep',
            'lines': [
                {'category_id': food_id, 'amount': 10, 'label': 'Chleb'},
                {'category_id': food_id, 'amount': 15, 'label': 'Warzywa'},
            ],
        }
        invalid = self.client.post(self.base + '/entries', json={
            **entry, 'lines': [{'category_id': food_id, 'amount': 20}],
        })
        self.assertEqual(invalid.status_code, 400)
        entry_id = self.payload(self.client.post(self.base + '/entries', json=entry), 201)['id']
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lXcAAAAASUVORK5CYII='
        )
        self.payload(self.client.post(
            self.base + f'/entries/{entry_id}/receipt',
            data={'file': (io.BytesIO(png), 'zakupy.png', 'image/png')},
            content_type='multipart/form-data',
        ))
        snapshot = self.payload(self.client.get(self.base + '?month=2026-09'))
        food = next(category for category in snapshot['categories'] if category['id'] == food_id)
        self.assertEqual((food['planned'], food['spent'], food['remaining']), (500, 25, 475))
        self.assertEqual(snapshot['totals']['balance'], 975)
        self.assertTrue(snapshot['entries'][0]['has_receipt'])
        receipt_response = self.client.get(self.base + f'/entries/{entry_id}/receipt')
        self.assertEqual(receipt_response.data, png)
        receipt_response.close()

        entry['amount'] = 30
        entry['lines'][1]['amount'] = 20
        self.payload(self.client.put(self.base + f'/entries/{entry_id}', json=entry))
        self.assertEqual(self.payload(self.client.get(self.base + '?month=2026-09'))['totals']['balance'], 970)
        self.payload(self.client.delete(self.base + f'/entries/{entry_id}'))
        snapshot = self.payload(self.client.get(self.base + '?month=2026-09'))
        self.assertEqual(snapshot['totals']['balance'], 1000)
        self.assertEqual(snapshot['totals']['spent'], 0)

    def test_bill_is_planned_without_moving_money_and_payment_cannot_duplicate(self):
        account_id, categories = self.setup_account()
        bill_id = self.payload(self.client.post(self.base + '/bills', json={
            'title': 'Internet', 'account_id': account_id,
            'category_id': categories['Rachunki'], 'amount': 120,
            'due_day': 30, 'frequency': 'ONCE', 'due_month': '2026-02',
        }), 201)['id']
        snapshot = self.payload(self.client.get(self.base + '?month=2026-02'))
        self.assertEqual(snapshot['bills'][0]['due_date'], '2026-02-28')
        self.assertEqual(snapshot['totals']['planned'], 120)
        self.assertEqual(snapshot['totals']['balance'], 1000)
        entry_id = self.payload(self.client.post(self.base + f'/bills/{bill_id}/pay', json={
            'month': '2026-02', 'date': '2026-02-20',
        }), 201)['entry_id']
        self.assertEqual(self.client.post(self.base + f'/bills/{bill_id}/pay', json={
            'month': '2026-02', 'date': '2026-02-20',
        }).status_code, 400)
        snapshot = self.payload(self.client.get(self.base + '?month=2026-02'))
        self.assertEqual(snapshot['totals']['balance'], 880)
        self.assertEqual(snapshot['totals']['spent'], 120)
        self.assertEqual(snapshot['bills'][0]['status'], 'PAID')
        from uuid import uuid4
        self.assertEqual(self.client.delete(self.base + f'/entries/{entry_id}').status_code,400)
        preview=self.payload(self.client.get(self.base+f'/entries/{entry_id}/settlement-preview'))
        self.payload(self.client.post(self.base+f'/entries/{entry_id}/reverse-settlement',json=dict(preview,request_id=str(uuid4()))))
        snapshot = self.payload(self.client.get(self.base + '?month=2026-02'))
        self.assertEqual(snapshot['totals']['balance'], 1000)
        self.assertNotEqual(snapshot['bills'][0]['status'], 'PAID')

    def test_monthly_bill_starts_in_selected_month(self):
        account_id, categories = self.setup_account()
        bill_id = self.payload(self.client.post(self.base + '/bills', json={
            'title': 'Czynsz', 'account_id': account_id,
            'category_id': categories['Mieszkanie'], 'amount': 600,
            'due_day': 5, 'frequency': 'MONTHLY', 'start_month': '2026-09',
        }), 201)['id']
        august = self.payload(self.client.get(self.base + '?month=2026-08'))
        self.assertEqual(august['bills'], [])
        self.assertEqual(august['totals']['planned'], 0)
        september = self.payload(self.client.get(self.base + '?month=2026-09'))
        self.assertEqual(september['bills'][0]['id'], bill_id)
        self.assertEqual(september['totals']['planned'], 600)
        self.assertEqual(self.client.post(self.base + f'/bills/{bill_id}/pay', json={
            'month': '2026-08', 'date': '2026-08-05',
        }).status_code, 400)

    def test_budget_reset_keeps_portfolios(self):
        self.setup_account()
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO portfolios (name) VALUES ('IKE')")
            db.commit()
            reset_budget_data()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM portfolios').fetchone()[0], 1)
            for table in ('budget_accounts', 'budget_categories_v2', 'budget_plans_v2',
                          'budget_entries_v2', 'budget_entry_lines_v2', 'budget_bills_v2'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
