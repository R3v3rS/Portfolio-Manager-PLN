import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402


class ApiContractEndpointsTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'api-contract-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()

        metadata = {
            'currency': 'PLN',
            'company_name': 'Apple Inc.',
            'sector': 'Technology',
            'industry': 'Consumer Electronics',
        }
        stock_analysis = {
            'ticker': 'AAPL',
            'summary': 'Bullish',
            'price': 111.0,
        }
        radar_snapshot = {
            'AAPL': {
                'price': 111.0,
                'change_1d': 1.2,
                'change_7d': 2.5,
                'change_1m': 3.0,
                'change_1y': 12.0,
                'next_earnings': '2026-05-01',
                'ex_dividend_date': '2026-04-01',
                'dividend_yield': 0.015,
                'last_updated_at': '2026-03-21T00:00:00',
            }
        }

        self.patchers = [
            patch('portfolio_trade_service.PriceService.fetch_metadata', return_value=metadata),
            patch('portfolio_valuation_service.PriceService.fetch_metadata', return_value=metadata),
            patch('price_service.PriceService.sync_stock_history', return_value=None),
            patch('portfolio_valuation_service.PriceService.get_prices', return_value={'AAPL': 110.0}),
            patch('portfolio_valuation_service.PriceService.get_price_updates', return_value={'AAPL': '2026-03-21T00:00:00'}),
            patch('routes_radar.PriceService.refresh_radar_data', return_value=radar_snapshot),
            patch('routes_radar.PriceService.get_cached_radar_data', return_value=radar_snapshot),
            patch('routes_radar.PriceService.get_stock_analysis', return_value=stock_analysis),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.addCleanup(self.temp_dir.cleanup)

        self.account_id = self.create_budget_account('Primary budget', 1000.0)
        self.secondary_account_id = self.create_budget_account('Secondary budget', 250.0)
        self.category_id = self.create_budget_category('Investments')
        self.envelope_id = self.create_envelope('Core envelope')

        self.portfolio_id = self.create_portfolio('Core Portfolio', 1000.0, 'STANDARD')
        self.savings_portfolio_id = self.create_portfolio('Savings Portfolio', 500.0, 'SAVINGS')
        self.ppk_portfolio_id = self.create_portfolio('PPK Portfolio', 0.0, 'PPK')
        self.loan_id = self.create_loan('Mortgage')

        self.contract_request_builders, self.non_contract_assertions = self.build_contract_request_builders()

    def assert_contract(self, response, route_key):
        self.assertTrue(response.is_json, f'{route_key} did not return JSON: {response.status_code} {response.data!r}')
        body = response.get_json()
        self.assertIsInstance(body, dict, f'{route_key} did not return a JSON object: {body!r}')

        has_payload = 'payload' in body
        has_error = 'error' in body

        self.assertTrue(has_payload or has_error, f'{route_key} missing payload/error envelope: {body!r}')
        self.assertFalse(has_payload and has_error, f'{route_key} returned both payload and error: {body!r}')

        if has_error:
            error = body['error']
            self.assertIsInstance(error, dict, f'{route_key} error body must be an object: {body!r}')
            self.assertIn('code', error, f'{route_key} error missing code: {body!r}')
            self.assertIn('message', error, f'{route_key} error missing message: {body!r}')
            self.assertIn('details', error, f'{route_key} error missing details: {body!r}')
            self.assertIsInstance(error['details'], dict, f'{route_key} error details must be an object: {body!r}')

    def create_budget_account(self, name, balance):
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                'INSERT INTO budget_accounts (name, balance, currency) VALUES (?, ?, ?)',
                (name, balance, 'PLN'),
            )
            db.commit()
            return cursor.lastrowid

    def create_budget_category(self, name):
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                'INSERT INTO envelope_categories (name, icon) VALUES (?, ?)',
                (name, '📈'),
            )
            db.commit()
            return cursor.lastrowid

    def create_envelope(self, name):
        with self.app.app_context():
            db = get_db()
            cursor = db.execute(
                '''
                INSERT INTO envelopes (category_id, account_id, name, icon, target_amount, type, target_month, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (self.category_id, self.account_id, name, '✉️', 300.0, 'MONTHLY', '2026-03', 'ACTIVE'),
            )
            db.commit()
            return cursor.lastrowid

    def create_portfolio(self, name, initial_cash, account_type):
        response = self.client.post(
            '/api/portfolio/create',
            json={
                'name': name,
                'initial_cash': initial_cash,
                'account_type': account_type,
                'created_at': '2026-03-01',
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assert_contract(response, ('/api/portfolio/create', 'POST'))
        return response.get_json()['payload']['id']

    def create_loan(self, name):
        response = self.client.post(
            '/api/loans/',
            json={
                'name': name,
                'original_amount': 120000.0,
                'duration_months': 120,
                'start_date': '2026-01-01',
                'installment_type': 'EQUAL',
                'initial_rate': 7.2,
                'category': 'HIPOTECZNY',
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assert_contract(response, ('/api/loans/', 'POST'))
        return response.get_json()['payload']['id']

    def add_watchlist_ticker(self, ticker):
        response = self.client.post('/api/radar/watchlist', json={'ticker': ticker})
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assert_contract(response, ('/api/radar/watchlist', 'POST'))

    def create_symbol_mapping(self, symbol_input, ticker, currency='USD'):
        response = self.client.post(
            '/api/symbol-map',
            json={'symbol_input': symbol_input, 'ticker': ticker, 'currency': currency},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assert_contract(response, ('/api/symbol-map', 'POST'))
        return response.get_json()['payload']['id']

    def create_disposable_loan(self):
        return self.create_loan('Disposable Loan')

    def create_disposable_portfolio(self):
        return self.create_portfolio('Disposable Portfolio', 50.0, 'STANDARD')

    def create_child_portfolio(self, parent_id, name='Disposable Child Portfolio'):
        response = self.client.post(
            f'/api/portfolio/{parent_id}/children',
            json={
                'name': name,
                'initial_cash': 25.0,
                'created_at': '2026-03-22',
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assert_contract(response, (f'/api/portfolio/{parent_id}/children', 'POST'))
        return response.get_json()['payload']['id']

    def get_portfolio_transaction_ids(self, portfolio_id, limit=2):
        with self.app.app_context():
            db = get_db()
            rows = db.execute(
                'SELECT id FROM transactions WHERE portfolio_id = ? ORDER BY id ASC LIMIT ?',
                (portfolio_id, limit),
            ).fetchall()
            return [row['id'] for row in rows]

    def assert_monitoring_dashboard_response(self, response, route_key):
        self.assertEqual(response.status_code, 200, f'{route_key} failed: {response.status_code} {response.data!r}')
        self.assertIn('text/html', response.content_type, f'{route_key} should return HTML dashboard')

    def assert_monitoring_stats_response(self, response, route_key):
        self.assertEqual(response.status_code, 200, f'{route_key} failed: {response.status_code} {response.data!r}')
        self.assertTrue(response.is_json, f'{route_key} did not return JSON stats: {response.data!r}')
        self.assertIsInstance(response.get_json(), dict, f'{route_key} did not return JSON object stats')

    def build_contract_request_builders(self):
        child_portfolio_id = self.create_child_portfolio(self.portfolio_id, 'Assignment Child')

        self.client.post(
            '/api/portfolio/buy',
            json={
                'portfolio_id': self.portfolio_id,
                'ticker': 'AAPL',
                'quantity': 2,
                'price': 100.0,
                'date': '2026-03-02',
            },
        )
        self.client.post(
            '/api/portfolio/sell',
            json={
                'portfolio_id': self.portfolio_id,
                'ticker': 'AAPL',
                'quantity': 1,
                'price': 120.0,
                'date': '2026-03-03',
            },
        )
        self.client.post(
            '/api/portfolio/dividend',
            json={
                'portfolio_id': self.portfolio_id,
                'ticker': 'AAPL',
                'amount': 15.0,
                'date': '2026-03-04',
            },
        )
        self.client.post(
            '/api/portfolio/bonds',
            json={
                'portfolio_id': self.portfolio_id,
                'name': 'EDO Bond',
                'principal': 1000.0,
                'interest_rate': 6.0,
                'purchase_date': '2026-03-05',
            },
        )
        self.client.post(
            '/api/portfolio/ppk/transactions',
            json={
                'portfolio_id': self.ppk_portfolio_id,
                'date': '2026-03-06',
                'employeeUnits': 10,
                'employerUnits': 5,
                'pricePerUnit': 45.0,
            },
        )
        self.add_watchlist_ticker('AAPL')
        transaction_ids = self.get_portfolio_transaction_ids(self.portfolio_id, limit=2)

        transfer_response = self.client.post(
            '/api/portfolio/transfer/cash',
            json={
                'from_portfolio_id': self.portfolio_id,
                'to_portfolio_id': self.portfolio_id,
                'to_sub_portfolio_id': child_portfolio_id,
                'amount': 10.0,
                'date': '2026-03-07',
                'note': 'Seed transfer for delete route',
            },
        )
        self.assertEqual(transfer_response.status_code, 200, transfer_response.get_json())
        self.assert_contract(transfer_response, ('/api/portfolio/transfer/cash', 'POST'))
        transfer_id = transfer_response.get_json()['payload']['transfer_id']

        non_contract_assertions = {
            ('/monitoring', 'GET'): self.assert_monitoring_dashboard_response,
            ('/monitoring/stats', 'GET'): self.assert_monitoring_stats_response,
        }

        return {
            ('/', 'GET'): lambda: self.client.get('/'),
            ('/monitoring', 'GET'): lambda: self.client.get('/monitoring'),
            ('/monitoring/stats', 'GET'): lambda: self.client.get('/monitoring/stats'),
            ('/api/budget/account-transfer', 'POST'): lambda: self.client.post(
                '/api/budget/account-transfer',
                json={
                    'from_account_id': self.account_id,
                    'to_account_id': self.secondary_account_id,
                    'amount': 25.0,
                    'description': 'Internal transfer',
                    'date': '2026-03-10',
                },
            ),
            ('/api/budget/accounts', 'GET'): lambda: self.client.get('/api/budget/accounts'),
            ('/api/budget/accounts', 'POST'): lambda: self.client.post(
                '/api/budget/accounts',
                json={'name': 'Contract Account', 'balance': 123.45, 'currency': 'PLN'},
            ),
            ('/api/budget/allocate', 'POST'): lambda: self.client.post(
                '/api/budget/allocate',
                json={'envelope_id': self.envelope_id, 'amount': 50.0, 'date': '2026-03-10'},
            ),
            ('/api/budget/analytics', 'GET'): lambda: self.client.get(
                '/api/budget/analytics?account_id={}&year=2026&month=3'.format(self.account_id)
            ),
            ('/api/budget/borrow', 'POST'): lambda: self.client.post(
                '/api/budget/borrow',
                json={
                    'source_envelope_id': self.envelope_id,
                    'amount': 20.0,
                    'reason': 'Bridge cash flow',
                    'due_date': '2026-04-01',
                },
            ),
            ('/api/budget/budget/clone', 'POST'): lambda: self.client.post(
                '/api/budget/budget/clone',
                json={'account_id': self.account_id, 'from_month': '2026-03', 'to_month': '2026-04'},
            ),
            ('/api/budget/categories', 'GET'): lambda: self.client.get('/api/budget/categories'),
            ('/api/budget/categories', 'POST'): lambda: self.client.post(
                '/api/budget/categories',
                json={'name': 'Travel', 'icon': '✈️'},
            ),
            ('/api/budget/envelopes', 'GET'): lambda: self.client.get(f'/api/budget/envelopes?account_id={self.account_id}'),
            ('/api/budget/envelopes', 'POST'): lambda: self.client.post(
                '/api/budget/envelopes',
                json={
                    'category_id': self.category_id,
                    'account_id': self.account_id,
                    'name': 'Vacation',
                    'icon': '🏖️',
                    'target_amount': 400.0,
                    'type': 'MONTHLY',
                    'target_month': '2026-05',
                },
            ),
            ('/api/budget/envelopes/<int:envelope_id>', 'PATCH'): lambda: self.client.patch(
                f'/api/budget/envelopes/{self.envelope_id}',
                json={'target_amount': 325.0, 'name': 'Core envelope updated'},
            ),
            ('/api/budget/envelopes/close', 'POST'): lambda: self.client.post(
                '/api/budget/envelopes/close',
                json={'envelope_id': self.envelope_id},
            ),
            ('/api/budget/expense', 'POST'): lambda: self.client.post(
                '/api/budget/expense',
                json={
                    'account_id': self.account_id,
                    'amount': 30.0,
                    'description': 'Groceries',
                    'envelope_id': self.envelope_id,
                    'date': '2026-03-11',
                },
            ),
            ('/api/budget/income', 'POST'): lambda: self.client.post(
                '/api/budget/income',
                json={'account_id': self.account_id, 'amount': 500.0, 'description': 'Salary', 'date': '2026-03-09'},
            ),
            ('/api/budget/repay', 'POST'): lambda: self.client.post(
                '/api/budget/repay',
                json={'loan_id': 999999, 'amount': 10.0},
            ),
            ('/api/budget/reset', 'POST'): lambda: self.client.post('/api/budget/reset'),
            ('/api/budget/summary', 'GET'): lambda: self.client.get(f'/api/budget/summary?account_id={self.account_id}&month=2026-03'),
            ('/api/budget/transactions', 'GET'): lambda: self.client.get(f'/api/budget/transactions?account_id={self.account_id}'),
            ('/api/budget/transfer-to-portfolio', 'POST'): lambda: self.client.post(
                '/api/budget/transfer-to-portfolio',
                json={
                    'budget_account_id': self.account_id,
                    'portfolio_id': self.portfolio_id,
                    'amount': 100.0,
                    'description': 'Top-up',
                    'date': '2026-03-12',
                },
            ),
            ('/api/budget/withdraw-from-portfolio', 'POST'): lambda: self.client.post(
                '/api/budget/withdraw-from-portfolio',
                json={
                    'budget_account_id': self.account_id,
                    'portfolio_id': self.portfolio_id,
                    'amount': 50.0,
                    'description': 'Cash back',
                    'date': '2026-03-13',
                },
            ),
            ('/api/dashboard/global-summary', 'GET'): lambda: self.client.get('/api/dashboard/global-summary'),
            ('/api/analytics/summary', 'GET'): lambda: self.client.get('/api/analytics/summary?portfolio_id=1'),
            ('/api/ai/portfolio-analysis', 'POST'): lambda: self.client.post(
                '/api/ai/portfolio-analysis',
                json={'portfolio_id': 1, 'question': 'test'},
            ),
            ('/api/loans/', 'GET'): lambda: self.client.get('/api/loans/'),
            ('/api/loans/', 'POST'): lambda: self.client.post(
                '/api/loans/',
                json={
                    'name': 'Contract Loan',
                    'original_amount': 50000.0,
                    'duration_months': 60,
                    'start_date': '2026-02-01',
                    'installment_type': 'EQUAL',
                    'initial_rate': 5.0,
                    'category': 'GOTOWKOWY',
                },
            ),
            ('/api/loans/<int:loan_id>', 'DELETE'): lambda: self.client.delete(f'/api/loans/{self.create_disposable_loan()}'),
            ('/api/loans/<int:loan_id>/overpayments', 'POST'): lambda: self.client.post(
                f'/api/loans/{self.loan_id}/overpayments',
                json={'amount': 1000.0, 'date': '2026-03-15', 'type': 'REDUCE_TERM'},
            ),
            ('/api/loans/<int:loan_id>/rates', 'POST'): lambda: self.client.post(
                f'/api/loans/{self.loan_id}/rates',
                json={'interest_rate': 6.5, 'valid_from_date': '2026-04-01'},
            ),
            ('/api/loans/<int:loan_id>/schedule', 'GET'): lambda: self.client.get(f'/api/loans/{self.loan_id}/schedule'),
            ('/api/portfolio/<int:portfolio_id>', 'DELETE'): lambda: self.client.delete(
                f'/api/portfolio/{self.create_disposable_portfolio()}'
            ),
            ('/api/portfolio/<int:portfolio_id>/audit', 'GET'): lambda: self.client.get(
                f'/api/portfolio/{self.portfolio_id}/audit'
            ),
            ('/api/portfolio/admin/price-history-audit', 'GET'): lambda: self.client.get(
                '/api/portfolio/admin/price-history-audit'
            ),
            ('/api/portfolio/<int:portfolio_id>/clear', 'POST'): lambda: self.client.post(
                f'/api/portfolio/{self.create_disposable_portfolio()}/clear'
            ),
            ('/api/portfolio/<int:portfolio_id>/closed-position-cycles', 'GET'): lambda: self.client.get(
                f'/api/portfolio/{self.portfolio_id}/closed-position-cycles'
            ),
            ('/api/portfolio/<int:portfolio_id>/closed-positions', 'GET'): lambda: self.client.get(
                f'/api/portfolio/{self.portfolio_id}/closed-positions'
            ),
            ('/api/portfolio/<int:portfolio_id>/archive', 'POST'): lambda: self.client.post(
                f'/api/portfolio/{self.create_child_portfolio(self.portfolio_id, "Archived Child")}/archive'
            ),
            ('/api/portfolio/<int:portfolio_id>/import/xtb', 'POST'): lambda: self.client.post(
                f'/api/portfolio/{self.portfolio_id}/import/xtb',
                data={},
                content_type='multipart/form-data',
            ),
            ('/api/portfolio/import/staging', 'POST'): lambda: self.client.post(
                '/api/portfolio/import/staging',
                data={
                    'portfolio_id': self.portfolio_id,
                    'file': (io.BytesIO(b'Symbol,Open time,Type,Volume,Price\nAAPL.US,2026-03-01 10:00:00,buy,1,100\n'), 'staging.csv'),
                },
                content_type='multipart/form-data',
            ),
            ('/api/portfolio/import/staging/<session_id>', 'GET'): lambda: self.client.get(
                '/api/portfolio/import/staging/non-existent-session'
            ),
            ('/api/portfolio/import/staging/<session_id>/rows/<int:row_id>/assign', 'PUT'): lambda: self.client.put(
                '/api/portfolio/import/staging/non-existent-session/rows/1/assign',
                json={'target_sub_portfolio_id': child_portfolio_id},
            ),
            ('/api/portfolio/import/staging/<session_id>/assign-all', 'PUT'): lambda: self.client.put(
                '/api/portfolio/import/staging/non-existent-session/assign-all',
                json={'target_sub_portfolio_id': child_portfolio_id},
            ),
            ('/api/portfolio/import/staging/<session_id>/rows/<int:row_id>', 'DELETE'): lambda: self.client.delete(
                '/api/portfolio/import/staging/non-existent-session/rows/1'
            ),
            ('/api/portfolio/import/staging/<session_id>/book', 'POST'): lambda: self.client.post(
                '/api/portfolio/import/staging/non-existent-session/book',
                json={'confirmed_row_ids': [1]},
            ),
            ('/api/portfolio/import/staging/<session_id>', 'DELETE'): lambda: self.client.delete(
                '/api/portfolio/import/staging/non-existent-session'
            ),
            ('/api/portfolio/<int:portfolio_id>/performance', 'GET'): lambda: self.client.get(
                f'/api/portfolio/{self.portfolio_id}/performance'
            ),
            ('/api/portfolio/<int:portfolio_id>/rebuild', 'POST'): lambda: self.client.post(
                f'/api/portfolio/{self.portfolio_id}/rebuild'
            ),
            ('/api/portfolio/<int:parent_id>/children', 'POST'): lambda: self.client.post(
                f'/api/portfolio/{self.portfolio_id}/children',
                json={'name': 'Contract Child', 'initial_cash': 15.0, 'created_at': '2026-03-23'},
            ),
            ('/api/portfolio/allocation/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/allocation/{self.portfolio_id}'
            ),
            ('/api/portfolio/audit/consistency', 'GET'): lambda: self.client.get('/api/portfolio/audit/consistency'),
            ('/api/portfolio/bonds', 'POST'): lambda: self.client.post(
                '/api/portfolio/bonds',
                json={
                    'portfolio_id': self.portfolio_id,
                    'name': 'COI Bond',
                    'principal': 1500.0,
                    'interest_rate': 5.5,
                    'purchase_date': '2026-03-16',
                },
            ),
            ('/api/portfolio/bonds/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/bonds/{self.portfolio_id}'
            ),
            ('/api/portfolio/buy', 'POST'): lambda: self.client.post(
                '/api/portfolio/buy',
                json={
                    'portfolio_id': self.portfolio_id,
                    'ticker': 'AAPL',
                    'quantity': 1,
                    'price': 101.0,
                    'date': '2026-03-17',
                },
            ),
            ('/api/portfolio/create', 'POST'): lambda: self.client.post(
                '/api/portfolio/create',
                json={
                    'name': 'Contract Portfolio',
                    'initial_cash': 10.0,
                    'account_type': 'STANDARD',
                    'created_at': '2026-03-17',
                },
            ),
            ('/api/portfolio/config', 'GET'): lambda: self.client.get('/api/portfolio/config'),
            ('/api/portfolio/deposit', 'POST'): lambda: self.client.post(
                '/api/portfolio/deposit',
                json={'portfolio_id': self.portfolio_id, 'amount': 200.0, 'date': '2026-03-18'},
            ),
            ('/api/portfolio/dividend', 'POST'): lambda: self.client.post(
                '/api/portfolio/dividend',
                json={
                    'portfolio_id': self.portfolio_id,
                    'ticker': 'AAPL',
                    'amount': 5.0,
                    'date': '2026-03-18',
                },
            ),
            ('/api/portfolio/dividends/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/dividends/{self.portfolio_id}'
            ),
            ('/api/portfolio/dividends/monthly/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/dividends/monthly/{self.portfolio_id}'
            ),
            ('/api/portfolio/history/<string:ticker>', 'GET'): lambda: self.client.get('/api/portfolio/history/AAPL'),
            ('/api/portfolio/history/monthly/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/history/monthly/{self.portfolio_id}?benchmark=SPY'
            ),
            ('/api/portfolio/history/profit/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/history/profit/{self.portfolio_id}?days=30'
            ),
            ('/api/portfolio/history/value/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/history/value/{self.portfolio_id}?days=30'
            ),
            ('/api/portfolio/holdings/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/holdings/{self.portfolio_id}?refresh=0'
            ),
            ('/api/portfolio/limits', 'GET'): lambda: self.client.get('/api/portfolio/limits'),
            ('/api/portfolio/list', 'GET'): lambda: self.client.get('/api/portfolio/list'),
            ('/api/portfolio/ppk/transactions', 'POST'): lambda: self.client.post(
                '/api/portfolio/ppk/transactions',
                json={
                    'portfolio_id': self.ppk_portfolio_id,
                    'date': '2026-03-19',
                    'employeeUnits': 2,
                    'employerUnits': 1,
                    'pricePerUnit': 46.0,
                },
            ),
            ('/api/portfolio/ppk/transactions/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/ppk/transactions/{self.ppk_portfolio_id}?current_price=47.5'
            ),
            ('/api/portfolio/ppk/performance/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/ppk/performance/{self.ppk_portfolio_id}'
            ),
            ('/api/portfolio/savings/interest/manual', 'POST'): lambda: self.client.post(
                '/api/portfolio/savings/interest/manual',
                json={'portfolio_id': self.savings_portfolio_id, 'amount': 12.0, 'date': '2026-03-20'},
            ),
            ('/api/portfolio/savings/rate', 'POST'): lambda: self.client.post(
                '/api/portfolio/savings/rate',
                json={'portfolio_id': self.savings_portfolio_id, 'rate': 5.25},
            ),
            ('/api/portfolio/sell', 'POST'): lambda: self.client.post(
                '/api/portfolio/sell',
                json={
                    'portfolio_id': self.portfolio_id,
                    'ticker': 'AAPL',
                    'quantity': 1,
                    'price': 121.0,
                    'date': '2026-03-21',
                },
            ),
            ('/api/portfolio/transactions/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/transactions/{self.portfolio_id}'
            ),
            ('/api/portfolio/transactions/<int:transaction_id>/assign', 'PUT'): lambda: self.client.put(
                f'/api/portfolio/transactions/{transaction_ids[0]}/assign',
                json={'sub_portfolio_id': child_portfolio_id},
            ),
            ('/api/portfolio/transactions/all', 'GET'): lambda: self.client.get('/api/portfolio/transactions/all'),
            ('/api/portfolio/transactions/assign-bulk', 'POST'): lambda: self.client.post(
                '/api/portfolio/transactions/assign-bulk',
                json={'transaction_ids': transaction_ids, 'sub_portfolio_id': None},
            ),
            ('/api/portfolio/transfer/cash', 'POST'): lambda: self.client.post(
                '/api/portfolio/transfer/cash',
                json={
                    'from_portfolio_id': self.portfolio_id,
                    'to_portfolio_id': self.portfolio_id,
                    'to_sub_portfolio_id': child_portfolio_id,
                    'amount': 10.0,
                    'date': '2026-03-24',
                },
            ),
            ('/api/portfolio/transfer/cash/<string:transfer_id>', 'DELETE'): lambda: self.client.delete(
                f'/api/portfolio/transfer/cash/{transfer_id}'
            ),
            ('/api/portfolio/jobs/<string:job_id>', 'GET'): lambda: self.client.get('/api/portfolio/jobs/non-existent-job'),
            ('/api/portfolio/value/<int:portfolio_id>', 'GET'): lambda: self.client.get(
                f'/api/portfolio/value/{self.portfolio_id}'
            ),
            ('/api/portfolio/withdraw', 'POST'): lambda: self.client.post(
                '/api/portfolio/withdraw',
                json={'portfolio_id': self.portfolio_id, 'amount': 25.0, 'date': '2026-03-22'},
            ),
            ('/api/radar/', 'GET'): lambda: self.client.get('/api/radar/'),
            ('/api/radar/analysis/<ticker>', 'GET'): lambda: self.client.get('/api/radar/analysis/AAPL'),
            ('/api/radar/refresh', 'POST'): lambda: self.client.post('/api/radar/refresh', json={}),
            ('/api/radar/watchlist', 'POST'): lambda: self.client.post('/api/radar/watchlist', json={'ticker': 'MSFT'}),
            ('/api/radar/watchlist/<ticker>', 'DELETE'): lambda: self.client.delete('/api/radar/watchlist/AAPL'),
            ('/api/symbol-map', 'GET'): lambda: self.client.get('/api/symbol-map'),
            ('/api/symbol-map', 'POST'): lambda: self.client.post(
                '/api/symbol-map',
                json={'symbol_input': 'AAPL.US', 'ticker': 'AAPL', 'currency': 'USD'},
            ),
            ('/api/symbol-map/<int:mapping_id>', 'PUT'): lambda: self.client.put(
                f'/api/symbol-map/{self.create_symbol_mapping("MSFT.US", "MSFT")}',
                json={'ticker': 'MSFT', 'currency': 'USD'},
            ),
            ('/api/symbol-map/<int:mapping_id>', 'DELETE'): lambda: self.client.delete(
                f'/api/symbol-map/{self.create_symbol_mapping("GOOG.US", "GOOG")}'
            ),
        }, non_contract_assertions

    def test_all_registered_endpoints_follow_the_api_contract(self):
        expected_routes = {
            (rule.rule, method)
            for rule in self.app.url_map.iter_rules()
            if rule.endpoint != 'static'
            for method in sorted(rule.methods - {'HEAD', 'OPTIONS'})
        }

        self.assertEqual(
            expected_routes,
            set(self.contract_request_builders.keys()),
            'Every registered endpoint must have a contract assertion request builder.',
        )

        for route_key, request_builder in sorted(self.contract_request_builders.items()):
            with self.subTest(route=route_key):
                response = request_builder()
                custom_assertion = self.non_contract_assertions.get(route_key)
                if custom_assertion:
                    custom_assertion(response, route_key)
                else:
                    self.assert_contract(response, route_key)


if __name__ == '__main__':
    unittest.main()
