import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.exceptions import ApiError, ValidationError, NotFoundError
from api.response import error_response
from database import get_db, init_db
from routes_analytics import analytics_bp
from routes_budget import budget_bp
from routes_budget_workspace import workspace_bp
from routes_dashboard import dashboard_bp
from services.analytics.market_data_adapter import MarketDataAdapter
from services.analytics.performance_metrics import portfolio_var
from portfolio_core_service import PortfolioCoreService


class FinancialIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=os.path.join(self.temp.name, 'test.db'))
        init_db(self.app)
        self.app.register_blueprint(analytics_bp)
        self.app.register_blueprint(budget_bp, url_prefix='/api/budget')
        self.app.register_blueprint(workspace_bp, url_prefix='/api/budget/workspace')
        self.app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
        self.app.register_error_handler(ApiError, lambda error: error_response(error.code, error.message, status=error.status))
        self.app.register_error_handler(ValidationError, lambda error: error_response('validation_error', error.message, status=400))
        self.app.register_error_handler(NotFoundError, lambda error: error_response('not_found', error.message, status=404))
        self.client = self.app.test_client()
        with self.app.app_context():
            db = get_db()
            self.root = db.execute("INSERT INTO portfolios (name, account_type) VALUES ('Inwestycje', 'STANDARD')").lastrowid
            self.child = db.execute("INSERT INTO portfolios (name, account_type, parent_portfolio_id) VALUES ('Dywidendowe', 'STANDARD', ?)", (self.root,)).lastrowid
            db.commit()
        self.account = self.payload(self.client.post('/api/budget/workspace/accounts', json={'name': 'Osobiste', 'balance': 1000}), 201)['id']
        dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=40)
        self.history = pd.Series(np.tile([-0.01, 0.012], 20), index=dates)
        quotes = patch('services.analytics.market_data_adapter.PriceService.get_prices', return_value={'USDPLN=X': 4.0})
        quotes.start()
        self.addCleanup(quotes.stop)

    def payload(self, response, status=200):
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()['payload']

    def holding(self, ticker, quantity=10, currency='PLN', child=None):
        with self.app.app_context():
            db = get_db()
            db.execute('''INSERT INTO holdings (portfolio_id, sub_portfolio_id, ticker, quantity,
                          average_buy_price, total_cost, sector, currency) VALUES (?, ?, ?, ?, 10, ?, 'Test', ?)''',
                       (self.root, child, ticker, quantity, quantity * 10, currency))
            db.execute('INSERT INTO price_cache (ticker, price) VALUES (?, 10)', (ticker,))
            db.commit()

    def transfer(self, **overrides):
        return self.client.post('/api/budget/transfer-to-portfolio', json={
            'budget_account_id': self.account, 'portfolio_id': self.child, 'amount': 100,
            'date': '2026-09-15', 'request_id': 'transfer-1', **overrides,
        })

    def test_child_scope_and_empty_results_are_not_safe_zeroes(self):
        self.holding('CHILD', child=self.child)
        self.holding('ROOT')
        with patch.object(MarketDataAdapter, 'get_historical_returns', return_value={'CHILD': self.history, 'ROOT': self.history}):
            result = self.payload(self.client.get(f'/api/analytics/summary?portfolio_id={self.child}'))
        self.assertEqual((result['portfolio_id'], result['sub_portfolio_id']), (self.root, self.child))
        self.assertEqual([row['ticker'] for row in result['diversification']['by_asset']], ['CHILD'])
        self.assertEqual(result['risk']['data_points'], 40)
        self.assertIsNotNone(result['performance']['sharpe_ratio'])
        with patch.object(MarketDataAdapter, 'get_historical_returns', return_value={'CHILD': self.history, 'ROOT': self.history}):
            cached = self.payload(self.client.get(f'/api/analytics/summary?portfolio_id={self.child}'))
            self.assertTrue(cached['cached'])
            with self.app.app_context():
                db = get_db()
                db.execute('UPDATE holdings SET quantity = 20 WHERE ticker = ?', ('CHILD',))
                db.commit()
            changed = self.payload(self.client.get(f'/api/analytics/summary?portfolio_id={self.child}'))
            self.assertFalse(changed['cached'])
            self.assertEqual(changed['risk']['portfolio_value'], 200)
        with self.app.app_context():
            db = get_db()
            empty = db.execute("INSERT INTO portfolios (name) VALUES ('Pusty')").lastrowid
            db.commit()
        result = self.payload(self.client.get(f'/api/analytics/summary?portfolio_id={empty}'))
        self.assertIsNone(result['risk']['var_1d_pct'])
        self.assertIsNone(result['performance']['max_drawdown']['value'])
        self.assertIsNone(result['diversification']['score'])
        self.assertEqual(result['performance']['data_status'], 'no_holdings')
        self.assertEqual(self.client.get(f'/api/analytics/summary?portfolio_id={empty}&sub_portfolio_id={self.child}').status_code, 400)

    def test_missing_history_does_not_become_a_zero_return(self):
        self.holding('COMPLETE')
        self.holding('MISSING')
        with patch.object(MarketDataAdapter, 'get_historical_returns', return_value={'COMPLETE': self.history}):
            result = self.payload(self.client.get(f'/api/analytics/summary?portfolio_id={self.root}'))
        self.assertEqual(result['risk']['data_points'], 0)
        self.assertIsNone(result['risk']['var_1d_pct'])
        self.assertIsNone(result['performance']['sharpe_ratio'])

    def test_currency_weights_and_var_include_fx(self):
        self.holding('USD_ASSET', currency='USD')
        self.holding('PLN_ASSET')
        zeros = self.history * 0
        fx_history = pd.Series(np.log1p(np.tile([-0.01, 0.01], 20)), index=self.history.index)
        with self.app.app_context(), patch.object(MarketDataAdapter, 'get_historical_returns', return_value={
                'USD_ASSET': zeros, 'PLN_ASSET': zeros, 'USDPLN=X': fx_history}):
            snapshot = MarketDataAdapter.get_holdings_snapshot(self.root)
            self.assertAlmostEqual(next(row['weight'] for row in snapshot if row['ticker'] == 'USD_ASSET'), 0.8)
            result = portfolio_var(self.root)
        self.assertEqual(result['portfolio_value'], 500)
        self.assertAlmostEqual(result['var_1d_pct'], -0.008)
        self.assertAlmostEqual(result['var_1d_pln'], -4)

    def test_transfers_link_child_history_and_are_idempotent_without_income_or_spending(self):
        self.payload(self.transfer())
        self.payload(self.transfer())
        result = self.payload(self.client.get('/api/budget/workspace?month=2026-09'))
        self.assertEqual(result['totals']['balance'], 900)
        self.assertEqual((result['totals']['income'], result['totals']['spent']), (0, 0))
        self.assertEqual(len(result['entries']), 1)
        self.assertEqual((result['entries'][0]['kind'], result['entries'][0]['direction']), ('TRANSFER', 'OUT'))
        with self.app.app_context():
            db = get_db()
            row = db.execute("SELECT portfolio_id, sub_portfolio_id FROM transactions WHERE type = 'DEPOSIT'").fetchone()
            self.assertEqual(tuple(row), (self.root, self.child))
            self.assertEqual(db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (self.child,)).fetchone()[0], 100)
        self.payload(self.client.post('/api/budget/withdraw-from-portfolio', json={
            'portfolio_id': self.root, 'sub_portfolio_id': self.child, 'budget_account_id': self.account,
            'amount': 40, 'date': '2026-09-16', 'request_id': 'withdraw-1',
        }))
        result = self.payload(self.client.get('/api/budget/workspace?month=2026-09'))
        self.assertEqual(result['totals']['balance'], 940)
        self.assertEqual(len(result['entries']), 2)
        self.assertEqual((result['totals']['income'], result['totals']['spent']), (0, 0))
        before = self.payload(self.client.get('/api/budget/workspace?month=2026-08'))
        self.assertEqual(before['totals']['to_plan'], 1000)
        dashboard = self.payload(self.client.get('/api/dashboard/global-summary'))
        self.assertEqual(dashboard['total_assets'], 1000)

    def test_failed_or_reused_transfer_does_not_move_money(self):
        self.assertEqual(self.transfer(amount=2000).status_code, 400)
        self.assertEqual(self.transfer(amount=0.001).status_code, 400)
        self.payload(self.transfer())
        self.assertEqual(self.transfer(amount=101).status_code, 400)
        result = self.payload(self.client.get('/api/budget/workspace?month=2026-09'))
        self.assertEqual((result['totals']['balance'], len(result['entries'])), (900, 1))

    def test_clearing_portfolio_cannot_remove_one_side_of_a_linked_transfer(self):
        self.payload(self.transfer())
        with self.app.app_context():
            with self.assertRaises(ApiError) as raised:
                PortfolioCoreService.clear_portfolio_data(self.root)
            self.assertEqual(raised.exception.code, 'LINKED_BUDGET_TRANSFER')
            db = get_db()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_investment_transfers').fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM transactions WHERE type = 'DEPOSIT'").fetchone()[0], 1)

    def test_plan_does_not_reduce_assets_and_dashboard_matches_new_budget(self):
        result = self.payload(self.client.get('/api/budget/workspace'))
        category = result['categories'][0]['id']
        self.payload(self.client.put(f'/api/budget/workspace/plans/{category}', json={'month': result['month'], 'amount': 250}))
        workspace = self.payload(self.client.get('/api/budget/workspace'))
        dashboard = self.payload(self.client.get('/api/dashboard/global-summary'))
        self.assertEqual(dashboard['total_assets'], 1000)
        self.assertEqual(dashboard['quick_stats']['free_pool'], 750)
        self.assertEqual(dashboard['quick_stats']['free_pool'], workspace['totals']['to_plan'])

    def test_expected_income_changes_planning_and_dashboard_actions_without_increasing_assets(self):
        snapshot = self.payload(self.client.get('/api/budget/workspace'))
        month = snapshot['month']
        self.payload(self.client.put(f'/api/budget/workspace/plans/{snapshot["categories"][0]["id"]}',
                                    json={'month': month, 'amount': 1500}))
        with self.app.app_context():
            db = get_db()
            db.execute('''INSERT INTO budget_expected_incomes
                (name,account_id,amount_cents,start_date,frequency,request_id,request_payload,created_at,updated_at)
                VALUES ('Pensja',?,610000,?,'MONTHLY','planned-income','{}',?,?)''',
                (self.account, month+'-10', month+'-01', month+'-01'))
            db.commit()
        workspace = self.payload(self.client.get('/api/budget/workspace'))
        dashboard = self.payload(self.client.get('/api/dashboard/global-summary'))
        self.assertEqual((dashboard['total_assets'], workspace['totals']['income']), (1000, 0))
        self.assertEqual((dashboard['quick_stats']['expected_income'], dashboard['quick_stats']['free_pool']), (6100, 5600))
        self.assertEqual(dashboard['quick_stats']['free_pool'], workspace['totals']['to_plan'])
        actions = self.payload(self.client.get('/api/dashboard/actions'))
        planning = next(a for a in actions['items'] if a['source'] == 'budget_plan')
        self.assertEqual((planning['title'], planning['amount']), ('Rozdziel środki w budżecie', 5600))


if __name__ == '__main__':
    unittest.main()
