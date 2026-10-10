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
from database import init_db  # noqa: E402
from loan_service import LoanService  # noqa: E402
from routes_budget_workspace import workspace_bp  # noqa: E402
from routes_loans import loans_bp  # noqa: E402


class LoanWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        app = Flask(__name__)
        app.config.update(TESTING=True, DATABASE=os.path.join(self.temp.name, 'loans.db'))
        app.register_blueprint(loans_bp, url_prefix='/api/loans')
        app.register_blueprint(workspace_bp, url_prefix='/api/budget/workspace')
        app.register_error_handler(ValidationError, lambda error: error_response('validation_error', error.message, status=400))
        app.register_error_handler(NotFoundError, lambda error: error_response('not_found', error.message, status=404))
        init_db(app)
        self.app = app
        self.client = app.test_client()
        self.loan_id = self.payload(self.client.post('/api/loans/', json={
            'name': 'Raty 0%', 'original_amount': 2641,
            'duration_months': 34, 'start_date': '2025-12-15',
            'installment_type': 'EQUAL', 'initial_rate': 0, 'category': 'RATY_0',
        }), 201)['id']

    def payload(self, response, status=200):
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()['payload']

    def budget_account(self):
        return self.payload(self.client.post('/api/budget/workspace/accounts', json={
            'name': 'Osobiste', 'balance': 1000,
        }), 201)['id']

    def test_estimate_uses_last_completed_date_and_oversized_simulation_is_rejected(self):
        with self.app.app_context():
            status = LoanService.get_status(self.loan_id, as_of='2026-09-30')
        self.assertEqual(status['estimated_balance'], 1941.91)
        self.assertEqual(status['next_due_date'], '2026-10-15')
        scenario = self.payload(self.client.get(
            f'/api/loans/{self.loan_id}/schedule?monthly_overpayment=100&simulated_action=REDUCE_TERM'
        ))
        self.assertEqual(scenario['actual']['schedule'][10]['remaining_balance'],
                         scenario['baseline']['schedule'][10]['remaining_balance'])
        self.assertNotEqual(scenario['actual']['schedule'][-1]['date'],
                            scenario['simulation']['schedule'][-1]['date'])
        response = self.client.get(
            f'/api/loans/{self.loan_id}/schedule?sim_amount=3000&sim_date=2026-10-01'
        )
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            loan = LoanService.get_loan_details(self.loan_id)
            rows, _, _ = LoanService.calculate_schedule(
                loan, LoanService.get_loan_rates(self.loan_id),
                [{'amount': 3000, 'date': '2026-10-01', 'type': 'REDUCE_TERM'}],
            )
        self.assertTrue(all(row['installment'] >= 0 and row['remaining_balance'] >= 0 for row in rows))

    def test_installment_and_overpayment_link_to_new_budget_once_and_can_be_undone(self):
        account_id = self.budget_account()
        url = f'/api/loans/{self.loan_id}/payments'
        payment = self.payload(self.client.post(url, json={
            'installment_month': 1, 'paid_on': '2026-01-15',
            'account_id': account_id,
        }), 201)
        self.assertIsNotNone(payment['budget_entry_id'])
        self.assertEqual(self.client.post(url, json={
            'installment_month': 1, 'paid_on': '2026-01-15',
            'account_id': account_id,
        }).status_code, 400)
        budget = self.payload(self.client.get('/api/budget/workspace/?month=2026-01'))
        self.assertEqual(budget['totals']['balance'], 922.32)
        self.assertEqual(len(budget['entries']), 1)
        self.assertEqual(self.client.delete(
            f'/api/budget/workspace/entries/{payment["budget_entry_id"]}'
        ).status_code, 400)
        self.payload(self.client.delete(f'{url}/{payment["id"]}'))
        budget = self.payload(self.client.get('/api/budget/workspace/?month=2026-01'))
        self.assertEqual(budget['totals']['balance'], 1000)
        self.assertEqual(budget['entries'], [])

        overpayment = self.payload(self.client.post(f'/api/loans/{self.loan_id}/overpayments', json={
            'amount': 100, 'date': '2026-02-20', 'type': 'REDUCE_TERM', 'account_id': account_id,
        }), 201)
        budget = self.payload(self.client.get('/api/budget/workspace/?month=2026-02'))
        self.assertEqual(budget['totals']['balance'], 900)
        self.payload(self.client.delete(
            f'/api/loans/{self.loan_id}/overpayments/{overpayment["id"]}'
        ))
        self.assertEqual(self.payload(self.client.get('/api/budget/workspace/?month=2026-02'))['totals']['balance'], 1000)

    def test_next_installment_skips_early_payment_and_returns_after_undo(self):
        payment = self.payload(self.client.post(f'/api/loans/{self.loan_id}/payments', json={
            'installment_month': 10, 'paid_on': '2026-10-10',
        }), 201)
        with self.app.app_context():
            status = LoanService.get_status(self.loan_id, as_of='2026-10-10')
        self.assertEqual(status['next_due_date'], '2026-11-15')
        self.payload(self.client.delete(f'/api/loans/{self.loan_id}/payments/{payment["id"]}'))
        with self.app.app_context():
            status = LoanService.get_status(self.loan_id, as_of='2026-10-15')
        self.assertEqual(status['next_due_date'], '2026-10-15')

    def test_confirmed_balance_is_separate_from_estimate(self):
        self.payload(self.client.post(f'/api/loans/{self.loan_id}/balance-checks', json={
            'balance': 1900, 'checked_on': '2026-09-20',
        }), 201)
        schedule = self.payload(self.client.get(f'/api/loans/{self.loan_id}/schedule'))
        self.assertEqual(schedule['status']['confirmed_balance'], 1900)
        self.assertEqual(schedule['status']['confirmed_on'], '2026-09-20')
        self.assertNotEqual(schedule['status']['estimated_balance'], 1900)


if __name__ == '__main__':
    unittest.main()
