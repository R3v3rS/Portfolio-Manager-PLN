import json
import sqlite3
import unittest
import tempfile
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from api.exceptions import NotFoundError, ValidationError
from api.response import error_response

from database import get_db, init_db
from routes_dashboard import dashboard_bp
from routes_loans import loans_bp
from routes_budget_workspace import workspace_bp
from tests import test_loans_workspace as fixtures


class LoanNetWorthTest(unittest.TestCase):
    payload = fixtures.LoanWorkspaceTest.payload
    budget_account = fixtures.LoanWorkspaceTest.budget_account

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=str(Path(self.temp.name) / 'loans.db'))
        self.app.register_blueprint(loans_bp, url_prefix='/api/loans')
        self.app.register_blueprint(workspace_bp, url_prefix='/api/budget/workspace')
        self.app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
        self.app.register_error_handler(ValidationError, lambda error: error_response('validation_error', error.message, status=400))
        self.app.register_error_handler(NotFoundError, lambda error: error_response('not_found', error.message, status=404))
        init_db(self.app)
        self.client = self.app.test_client()
        self.loan_id = self.payload(self.client.post('/api/loans/', json={
            'name': 'Raty', 'original_amount': 2641, 'duration_months': 34,
            'start_date': '2025-12-15', 'installment_type': 'EQUAL', 'initial_rate': 0,
        }), 201)['id']

    def toggle(self, value):
        return self.client.put(f'/api/loans/{self.loan_id}/net-worth-inclusion', json={'exclude_from_net_worth': value})

    def test_persisted_setting_is_validated_and_does_not_change_schedule(self):
        url = f'/api/loans/{self.loan_id}/schedule'
        before = self.payload(self.client.get(url))
        self.assertIs(before['loan']['exclude_from_net_worth'], False)
        for value in ('false', 'true', 0, 1, None, {}, []):
            self.assertEqual(self.toggle(value).status_code, 400)
        self.assertEqual(self.client.put(f'/api/loans/{self.loan_id}/net-worth-inclusion', json={}).status_code, 400)
        self.assertEqual(self.client.put('/api/loans/99999/net-worth-inclusion', json={'exclude_from_net_worth': True}).status_code, 404)
        for value in (True, True, False):
            self.assertIs(self.payload(self.toggle(value))['exclude_from_net_worth'], value)
            after = self.payload(self.client.get(url))
            self.assertIs(after['loan']['exclude_from_net_worth'], value)
            self.assertEqual(after['actual'], before['actual'])
            self.assertEqual(after['status'], before['status'])
            self.assertIs(self.payload(self.client.get('/api/loans/'))[0]['exclude_from_net_worth'], value)

    def test_only_net_worth_changes_not_cash_plan_or_next_installments(self):
        self.budget_account()
        old_day = (date.today() - timedelta(days=1)).isoformat()
        with self.app.app_context():
            db = get_db()
            db.execute('INSERT INTO net_worth_snapshots(date,net_worth,total_assets,total_liabilities,recorded_at) VALUES (?,10,20,10,?)', (old_day, old_day))
            db.commit()
        with patch('routes_dashboard.PortfolioService.list_portfolios', return_value=[]):
            before = self.payload(self.client.get('/api/dashboard/global-summary'))
            budget_before = self.payload(self.client.get('/api/budget/workspace/'))
            self.payload(self.toggle(True))
            after = self.payload(self.client.get('/api/dashboard/global-summary'))
            self.assertGreater(before['total_liabilities'], 0)
            self.assertEqual(after['total_liabilities'], 0)
            self.assertEqual(after['net_worth'], after['total_assets'])
            self.assertEqual(after['total_assets'], before['total_assets'])
            self.assertEqual(after['quick_stats'], before['quick_stats'])
            self.assertEqual(after['all_short_term_liabilities'], before['all_short_term_liabilities'])
            self.assertEqual(after['excluded_liabilities'][0]['estimated_balance'], before['total_liabilities'])
            self.assertEqual(self.payload(self.client.get('/api/budget/workspace/')), budget_before)
            with self.app.app_context():
                rows = get_db().execute('SELECT * FROM net_worth_snapshots ORDER BY date').fetchall()
                self.assertEqual(rows[0]['net_worth'], 10)
                self.assertEqual(rows[-1]['net_worth'], after['net_worth'])
                self.assertIn('nie jest uwzględniany', ' '.join(json.loads(rows[-1]['valuation_notes'])))
            self.payload(self.toggle(False))
            self.assertEqual(self.payload(self.client.get('/api/dashboard/global-summary'))['net_worth'], before['net_worth'])

    def test_existing_database_migration_defaults_to_inclusion_and_is_idempotent(self):
        with closing(sqlite3.connect(self.app.config['DATABASE'])) as db:
            db.execute('ALTER TABLE loans DROP COLUMN exclude_from_net_worth')
            db.commit()
        migration_app = Flask('migration')
        migration_app.config['DATABASE'] = self.app.config['DATABASE']
        init_db(migration_app)
        self.assertIs(self.payload(self.client.get('/api/loans/'))[0]['exclude_from_net_worth'], False)
        self.payload(self.toggle(True))
        init_db(migration_app)
        self.assertIs(self.payload(self.client.get('/api/loans/'))[0]['exclude_from_net_worth'], True)

    def test_create_can_explicitly_exclude_a_loan(self):
        response = self.client.post('/api/loans/', json={
            'name': 'Hipoteka', 'original_amount': 10000, 'duration_months': 120,
            'start_date': date.today().isoformat(), 'installment_type': 'EQUAL',
            'initial_rate': 5, 'category': 'HIPOTECZNY', 'exclude_from_net_worth': True,
        })
        loan_id = self.payload(response, 201)['id']
        self.assertIs(self.payload(self.client.get(f'/api/loans/{loan_id}/schedule'))['loan']['exclude_from_net_worth'], True)

    def test_mortgage_exclusion_keeps_other_loan_debt_and_all_installments(self):
        mortgage_id = self.payload(self.client.post('/api/loans/', json={
            'name': 'Hipoteka', 'original_amount': 10000, 'duration_months': 120,
            'start_date': date.today().isoformat(), 'installment_type': 'EQUAL',
            'initial_rate': 5, 'category': 'HIPOTECZNY',
        }), 201)['id']
        with patch('routes_dashboard.PortfolioService.list_portfolios', return_value=[]):
            before = self.payload(self.client.get('/api/dashboard/global-summary'))
            self.payload(self.client.put(f'/api/loans/{mortgage_id}/net-worth-inclusion', json={'exclude_from_net_worth': True}))
            after = self.payload(self.client.get('/api/dashboard/global-summary'))
        self.assertEqual(before['liabilities_breakdown']['long_term'], 10000)
        self.assertEqual(after['liabilities_breakdown']['long_term'], 0)
        self.assertEqual(after['liabilities_breakdown']['short_term'], before['liabilities_breakdown']['short_term'])
        self.assertEqual(after['quick_stats'], before['quick_stats'])
        self.assertAlmostEqual(after['net_worth'], before['net_worth'] + 10000, places=2)
        self.assertIs(self.payload(self.client.get(f'/api/loans/{self.loan_id}/schedule'))['loan']['exclude_from_net_worth'], False)
