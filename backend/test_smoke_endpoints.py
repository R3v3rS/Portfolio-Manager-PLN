import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402
from portfolio_service import PortfolioService  # noqa: E402


class BackendSmokeEndpointsTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'smoke-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()

        metadata = {'currency': 'PLN', 'company_name': 'Apple Inc.', 'sector': 'Technology', 'industry': 'Consumer Electronics'}
        metadata_patcher = patch('portfolio_trade_service.PriceService.fetch_metadata', return_value=metadata)
        valuation_metadata_patcher = patch('portfolio_valuation_service.PriceService.fetch_metadata', return_value=metadata)
        history_patcher = patch('portfolio_trade_service.PriceService.sync_stock_history', return_value=None)
        valuation_prices_patcher = patch('portfolio_valuation_service.PriceService.get_prices', return_value={'AAPL': 110.0})
        valuation_updates_patcher = patch('portfolio_valuation_service.PriceService.get_price_updates', return_value={'AAPL': '2026-03-21T00:00:00'})
        radar_refresh_patcher = patch(
            'routes_radar.PriceService.refresh_radar_data',
            return_value={
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
            },
        )
        radar_cached_patcher = patch(
            'routes_radar.PriceService.get_cached_radar_data',
            return_value={
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
            },
        )

        self.patchers = [
            metadata_patcher,
            history_patcher,
            valuation_metadata_patcher,
            valuation_prices_patcher,
            valuation_updates_patcher,
            radar_refresh_patcher,
            radar_cached_patcher,
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.addCleanup(self.temp_dir.cleanup)

    def seed_budget_account(self):
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO budget_accounts (name, balance, currency) VALUES (?, ?, ?)", ('Main budget', 1000.0, 'PLN'))
            db.execute("INSERT INTO envelope_categories (name, icon) VALUES (?, ?)", ('Investments', '📈'))
            db.commit()
            account_id = db.execute("SELECT id FROM budget_accounts WHERE name = ?", ('Main budget',)).fetchone()['id']
            category_id = db.execute("SELECT id FROM envelope_categories WHERE name = ?", ('Investments',)).fetchone()['id']
            return account_id, category_id

    def seed_portfolio_with_cash(self):
        response = self.client.post('/api/portfolio/create', json={
            'name': 'Smoke Portfolio',
            'initial_cash': 500.0,
            'account_type': 'STANDARD',
            'created_at': '2026-03-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def seed_loan(self):
        response = self.client.post('/api/loans/', json={
            'name': 'Mortgage',
            'original_amount': 120000.0,
            'duration_months': 120,
            'start_date': '2026-01-01',
            'installment_type': 'EQUAL',
            'initial_rate': 7.2,
            'category': 'HIPOTECZNY',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def add_watchlist_ticker(self, ticker='AAPL'):
        response = self.client.post('/api/radar/watchlist', json={'ticker': ticker})
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()['payload']['message'], 'Added to watchlist')

    def test_critical_backend_smoke_endpoints(self):
        account_id, _category_id = self.seed_budget_account()
        portfolio_id = self.seed_portfolio_with_cash()
        loan_id = self.seed_loan()
        self.add_watchlist_ticker('AAPL')

        response = self.client.get('/api/dashboard/global-summary')
        self.assertEqual(response.status_code, 200, response.get_json())
        dashboard = response.get_json()['payload']
        self.assertIn('net_worth', dashboard)
        self.assertIn('assets_breakdown', dashboard)
        self.assertIn('quick_stats', dashboard)

        response = self.client.get('/api/portfolio/list')
        self.assertEqual(response.status_code, 200, response.get_json())
        portfolios = response.get_json()['payload']['portfolios']
        self.assertEqual(len(portfolios), 1)
        self.assertEqual(portfolios[0]['id'], portfolio_id)

        response = self.client.post('/api/portfolio/buy', json={
            'portfolio_id': portfolio_id,
            'ticker': 'AAPL',
            'quantity': 2,
            'price': 100.0,
            'date': '2026-03-02',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['payload']['message'], 'Buy successful')

        response = self.client.post('/api/portfolio/sell', json={
            'portfolio_id': portfolio_id,
            'ticker': 'AAPL',
            'quantity': 1,
            'price': 120.0,
            'date': '2026-03-03',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['payload']['message'], 'Sell successful')

        response = self.client.get(f'/api/portfolio/value/{portfolio_id}')
        self.assertEqual(response.status_code, 200, response.get_json())
        value_payload = response.get_json()['payload']
        self.assertAlmostEqual(value_payload['cash_value'], 420.0)
        self.assertAlmostEqual(value_payload['holdings_value'], 110.0)
        self.assertAlmostEqual(value_payload['portfolio_value'], 530.0)

        response = self.client.post('/api/budget/transfer-to-portfolio', json={
            'budget_account_id': account_id,
            'portfolio_id': portfolio_id,
            'amount': 100.0,
            'description': 'Top-up',
            'date': '2026-03-04',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(
            response.get_json()['payload']['message'],
            'Transfer to Investment Portfolio successful',
        )

        response = self.client.post('/api/budget/withdraw-from-portfolio', json={
            'budget_account_id': account_id,
            'portfolio_id': portfolio_id,
            'amount': 50.0,
            'description': 'Cash back',
            'date': '2026-03-05',
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(
            response.get_json()['payload']['message'],
            'Withdrawal from Investment Portfolio successful',
        )

        response = self.client.get(f'/api/loans/{loan_id}/schedule')
        self.assertEqual(response.status_code, 200, response.get_json())
        schedule_payload = response.get_json()['payload']
        self.assertIn('baseline', schedule_payload)
        self.assertIn('simulation', schedule_payload)

        response = self.client.get('/api/radar/')
        self.assertEqual(response.status_code, 200, response.get_json())
        radar_items = response.get_json()['payload']
        self.assertEqual(len(radar_items), 1)
        self.assertEqual(radar_items[0]['ticker'], 'AAPL')
        self.assertTrue(radar_items[0]['is_watched'])

        response = self.client.post('/api/radar/refresh', json={})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['payload']['tickers'], ['AAPL'])

        response = self.client.get('/api/symbol-map')
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['payload'], [])

        response = self.client.get('/api/symbol-map/')
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['payload'], [])

    def test_invalid_buy_payload_returns_validation_error(self):
        portfolio_id = self.seed_portfolio_with_cash()

        response = self.client.post('/api/portfolio/buy', json={
            'portfolio_id': portfolio_id,
            'ticker': 'AAPL',
            'price': 100.0,
        })

        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'quantity')

    def test_invalid_sell_payload_returns_validation_error(self):
        portfolio_id = self.seed_portfolio_with_cash()

        response = self.client.post('/api/portfolio/sell', json={
            'portfolio_id': portfolio_id,
            'ticker': 'AAPL',
            'quantity': -1,
            'price': 120.0,
        })

        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'quantity')

    def test_invalid_budget_transfer_payload_returns_validation_error(self):
        account_id, _category_id = self.seed_budget_account()
        portfolio_id = self.seed_portfolio_with_cash()

        response = self.client.post('/api/budget/transfer-to-portfolio', json={
            'budget_account_id': account_id,
            'portfolio_id': portfolio_id,
            'amount': -10.0,
        })

        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'amount')

    def test_missing_budget_transfer_field_returns_validation_error(self):
        _account_id, _category_id = self.seed_budget_account()
        portfolio_id = self.seed_portfolio_with_cash()

        response = self.client.post('/api/budget/transfer-to-portfolio', json={
            'portfolio_id': portfolio_id,
            'amount': 25.0,
        })

        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'budget_account_id')

    def test_loan_schedule_rejects_invalid_simulation_inputs(self):
        loan_id = self.seed_loan()

        response = self.client.get(f'/api/loans/{loan_id}/schedule?sim_amount=0')
        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'sim_amount')

        response = self.client.get(f'/api/loans/{loan_id}/schedule?sim_amount=500')
        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'sim_date')

        response = self.client.get(f'/api/loans/{loan_id}/schedule?monthly_overpayment=-10')
        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'monthly_overpayment')

        response = self.client.get(f'/api/loans/{loan_id}/schedule?sim_amount=500&sim_date=2026-02-15&simulated_action=INVALID')
        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'simulated_action')

    def test_loan_mutations_validate_positive_amounts_and_missing_loans(self):
        response = self.client.post('/api/loans/', json={
            'name': 'Zero loan',
            'original_amount': 0,
            'duration_months': 12,
            'start_date': '2026-01-01',
            'installment_type': 'EQUAL',
            'initial_rate': 7.2,
        })
        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'original_amount')

        loan_id = self.seed_loan()

        response = self.client.post(f'/api/loans/{loan_id}/overpayments', json={
            'amount': 0,
            'date': '2026-02-10',
        })
        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'validation_error')
        self.assertEqual(error['details']['field'], 'amount')

        response = self.client.post('/api/loans/9999/rates', json={
            'interest_rate': 5.5,
            'valid_from_date': '2026-02-01',
        })
        self.assertEqual(response.status_code, 404, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'not_found')
        self.assertEqual(error['details']['loan_id'], 9999)

    def test_xtb_import_missing_symbols_returns_consistent_error_details(self):
        portfolio_id = self.seed_portfolio_with_cash()

        with patch('routes_imports.PortfolioService.import_xtb_csv', return_value={'success': False, 'missing_symbols': ['XTB.US']}):
            response = self.client.post(
                f'/api/portfolio/{portfolio_id}/import/xtb',
                data={'file': (io.BytesIO(b'symbol\nXTB.US\n'), 'xtb.csv')},
                content_type='multipart/form-data',
            )

        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'IMPORT_VALIDATION_ERROR')
        self.assertEqual(error['message'], 'Missing symbol mappings')
        self.assertEqual(error['details'], {'missing_symbols': ['XTB.US']})

    def test_xtb_import_invalid_csv_returns_consistent_error_details(self):
        portfolio_id = self.seed_portfolio_with_cash()

        with patch('routes_imports.pd.read_csv', side_effect=ValueError('Invalid CSV format')):
            response = self.client.post(
                f'/api/portfolio/{portfolio_id}/import/xtb',
                data={'file': (io.BytesIO(b'not,a,valid,csv'), 'xtb.csv')},
                content_type='multipart/form-data',
            )

        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'xtb_import_invalid_csv')
        self.assertEqual(error['message'], 'Invalid CSV format')
        self.assertEqual(error['details'], {})

    def test_xtb_import_conflicts_return_warning_without_confirmations(self):
        portfolio_id = self.seed_portfolio_with_cash()

        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO symbol_mappings (symbol_input, ticker, currency) VALUES (?, ?, ?)",
                ('AAPL.US', 'AAPL', 'USD'),
            )
            db.execute(
                '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, 'AAPL', 'BUY', 1.0, 100.0, 100.0, '2026-03-10 10:00:00'),
            )
            db.commit()

            df = pd.DataFrame([
                {
                    'Time': '2026-03-10 10:00:00',
                    'Type': 'Stock purchase',
                    'Symbol': 'AAPL.US',
                    'Amount': '-100.0',
                    'Comment': 'OPEN BUY 1 @ 100',
                },
            ])

            result = PortfolioService.import_xtb_csv(portfolio_id, df)

        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'warning')
        self.assertEqual(len(result['potential_conflicts']), 1)
        self.assertEqual(result['potential_conflicts'][0]['conflict_type'], 'database_duplicate')

    def test_xtb_import_mixed_conflict_confirmation_imports_only_confirmed_duplicates(self):
        portfolio_id = self.seed_portfolio_with_cash()

        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO symbol_mappings (symbol_input, ticker, currency) VALUES (?, ?, ?)",
                ('AAPL.US', 'AAPL', 'USD'),
            )
            db.execute(
                '''INSERT INTO transactions (portfolio_id, ticker, type, quantity, price, total_value, date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (portfolio_id, 'AAPL', 'BUY', 1.0, 100.0, 100.0, '2026-03-10 10:00:00'),
            )
            db.commit()

            df = pd.DataFrame([
                {
                    'Time': '2026-03-10 10:00:00',
                    'Type': 'Stock purchase',
                    'Symbol': 'AAPL.US',
                    'Amount': '-100.0',
                    'Comment': 'OPEN BUY 1 @ 100',
                },
                {
                    'Time': '2026-03-10 10:00:00',
                    'Type': 'Stock purchase',
                    'Symbol': 'AAPL.US',
                    'Amount': '-100.0',
                    'Comment': 'OPEN BUY 1 @ 100',
                },
            ])

            warning = PortfolioService.import_xtb_csv(portfolio_id, df)
            row_hash = warning['potential_conflicts'][0]['row_hash']
            result = PortfolioService.import_xtb_csv(portfolio_id, df, confirmed_hashes=[row_hash])

            count_after_import = db.execute(
                "SELECT COUNT(*) AS cnt FROM transactions WHERE portfolio_id = ? AND ticker = ? AND type = ?",
                (portfolio_id, 'AAPL', 'BUY'),
            ).fetchone()['cnt']
            holdings_qty = db.execute(
                "SELECT quantity FROM holdings WHERE portfolio_id = ? AND ticker = ?",
                (portfolio_id, 'AAPL'),
            ).fetchone()['quantity']

        self.assertTrue(warning['success'])
        self.assertEqual(warning['status'], 'warning')
        self.assertEqual(len(warning['potential_conflicts']), 2)
        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(count_after_import, 2)
        self.assertEqual(float(holdings_qty), 1.0)


    def test_global_error_handlers_preserve_contract_and_status_codes(self):
        @self.app.route('/__test/value-error')
        def _value_error_route():
            raise ValueError('Bad input provided')

        @self.app.route('/__test/unhandled-error')
        def _unhandled_error_route():
            raise RuntimeError('sensitive internal message')

        response = self.client.get('/__test/value-error')
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(response.get_json()['error']['code'], 'value_error')
        self.assertEqual(response.get_json()['error']['message'], 'Bad input provided')

        response = self.client.get('/__test/unhandled-error')
        self.assertEqual(response.status_code, 500, response.get_json())
        self.assertEqual(response.get_json()['error']['code'], 'internal_error')
        self.assertEqual(response.get_json()['error']['message'], 'Internal server error')
        self.assertNotIn('sensitive internal message', str(response.get_json()))

        response = self.client.get('/missing-route-for-http-exception')
        self.assertEqual(response.status_code, 404, response.get_json())
        self.assertEqual(response.get_json()['error']['code'], 'http_404')

if __name__ == '__main__':
    unittest.main()
