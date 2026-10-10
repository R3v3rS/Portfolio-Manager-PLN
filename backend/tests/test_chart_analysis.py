import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import get_db, init_db
from portfolio_history_service import PortfolioHistoryService as History
from portfolio_chart_service import attribution
from routes_dashboard import dashboard_bp
from routes_history import portfolio_bp


class ChartAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name) / 'charts.db'))
        init_db(self.app)
        self.app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
        self.app.register_blueprint(portfolio_bp, url_prefix='/api/portfolio')
        with self.app.app_context():
            db = get_db()
            self.parent = db.execute("INSERT INTO portfolios(name, account_type) VALUES ('Parent', 'STANDARD')").lastrowid
            self.child = db.execute("INSERT INTO portfolios(name, account_type, parent_portfolio_id) VALUES ('Child', 'STANDARD', ?)", (self.parent,)).lastrowid
            db.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def insert(self, day, kind, amount, ticker='CASH', quantity=0, child=None):
        db = get_db()
        db.execute('''INSERT INTO transactions(portfolio_id, sub_portfolio_id, ticker, date, type, quantity, price, total_value)
                      VALUES (?, ?, ?, ?, ?, ?, 0, ?)''', (self.parent, child, ticker, day, kind, quantity, amount))
        db.commit()

    def test_missing_fx_is_not_a_rate_of_one(self):
        value, missing = History._holding_value({'ABC': 2}, {'ABC': 'USD'}, lambda ticker, day: 100 if ticker == 'ABC' else 0, date(2026, 1, 31))
        self.assertEqual(value, 0)
        self.assertEqual(missing, ['ABC'])

    def test_zero_holding_needs_no_price_but_positive_holding_does(self):
        self.assertEqual(History._holding_value({'ABC': 0}, {}, lambda *args: 0, date.today()), (0, []))
        self.assertEqual(History._holding_value({'ABC': 1}, {}, lambda *args: 0, date.today()), (0, ['ABC']))

    def test_benchmark_uses_fx_at_the_date(self):
        price = History._benchmark_price('ABC', {'ABC': 'USD'}, lambda ticker, day: 100 if ticker == 'ABC' else 4.2, date(2026, 1, 31))
        self.assertEqual(price, 420)

    def test_monthly_return_weights_dates_and_excludes_orphans(self):
        with self.app.app_context():
            self.insert('2026-01-01', 'DEPOSIT', 1000)
            self.insert('2026-01-16', 'DEPOSIT', 200, child=self.child)
            self.insert('2026-01-01', 'DEPOSIT', 99999, child=999999)
            with patch.object(History, '_calculate_historical_metrics', return_value={'2026-01': {'total_value': 1300}}):
                result = History.get_performance_matrix(self.parent)
            expected = round(100 / (1000 * 30 / 31 + 200 * 15 / 31) * 100, 2)
            self.assertEqual(result['2026']['1'], expected)

    def test_missing_valuation_invalidates_linked_ytd(self):
        with self.app.app_context(), patch.object(History, '_calculate_historical_metrics', return_value={
            '2026-01': {'total_value': None}, '2026-02': {'total_value': 1000}, '2026-03': {'total_value': 1100}}):
            result = History.get_performance_matrix(self.parent)
        self.assertIsNone(result['2026']['1'])
        self.assertIsNone(result['2026']['2'])
        self.assertEqual(result['2026']['3'], 10)
        self.assertIsNone(result['2026']['YTD'])

    def test_attribution_includes_closed_positions_and_dividends(self):
        with self.app.app_context():
            self.insert('2026-01-02', 'BUY', 100, 'ABC', 1)
            self.insert('2026-01-03', 'SELL', 160, 'ABC', 1)
            self.insert('2026-01-04', 'DIVIDEND', 10, 'ABC')
            with patch.object(History, '_build_price_context', return_value=({'ABC': 'PLN'}, {})):
                result = attribution(self.parent, date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(result['items'][0]['value'], 70)
        self.assertEqual(result['items'][0]['dividends'], 10)
        self.assertEqual(result['items'][0]['closing_value'], 0)

    def test_attribution_reports_missing_opening_price(self):
        with self.app.app_context():
            self.insert('2025-12-02', 'BUY', 100, 'ABC', 1)
            with patch.object(History, '_build_price_context', return_value=({'ABC': 'PLN'}, {'ABC': {'2026-01-31': 160}})):
                result = attribution(self.parent, date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['missing_tickers'], ['ABC'])
        self.assertEqual(result['items'], [])

    def test_wealth_starts_with_observation_and_updates_once_per_day(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/api/dashboard/net-worth-history').json['payload']['history'], [])
        with patch('routes_dashboard.PortfolioService.list_portfolios', return_value=[]):
            self.assertEqual(client.get('/api/dashboard/global-summary').status_code, 200)
            self.assertEqual(client.get('/api/dashboard/global-summary').status_code, 200)
        points = client.get('/api/dashboard/net-worth-history').json['payload']['history']
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['date'], date.today().isoformat())
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM transactions').fetchone()[0], 0)

    def test_pln_price_history_uses_past_fx_and_reports_missing_dates(self):
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO asset_metadata(ticker, currency, updated_at) VALUES ('ABC', 'USD', '2026-01-01')")
            db.executemany('INSERT INTO stock_prices(ticker, date, close_price) VALUES (?, ?, ?)', [
                ('ABC', '2026-01-01', 10), ('ABC', '2026-01-03', 12), ('ABC', '2026-01-11', 13),
                ('USDPLN=X', '2026-01-02', 4), ('USDPLN=X', '2026-01-10', 4.2),
            ])
            db.commit()
        with patch('routes_history.PriceService.get_tickers_requiring_history_sync', return_value=[]), patch('routes_history.PriceService.should_refresh_stock_history', return_value=False):
            response = self.app.test_client().get('/api/portfolio/history/ABC?quote=PLN')
        self.assertEqual(response.status_code, 200)
        payload = response.json['payload']
        self.assertEqual(payload['currency'], 'PLN')
        self.assertEqual(payload['history'][0]['date'], '2026-01-03')
        self.assertEqual(payload['missing_fx_dates'], ['2026-01-01'])
        self.assertEqual(payload['history'][0]['close_price'], 48)
        self.assertAlmostEqual(payload['history'][1]['close_price'], 54.6)

    def test_drawdown_chart_and_metric_use_identical_model(self):
        import numpy as np
        import pandas as pd
        from services.analytics.performance_metrics import calculate_performance_summary
        returns = pd.Series(np.log1p([-.02, .01] * 20), index=pd.date_range('2026-01-01', periods=40))
        snapshot = [{'ticker': 'ABC', 'weight': 1, 'quantity': 1, 'currency': 'PLN', 'current_value_pln': 100}]
        with patch('services.analytics.performance_metrics.MarketDataAdapter.get_holdings_snapshot', return_value=snapshot), patch('services.analytics.performance_metrics._weighted_returns', return_value=returns):
            result = calculate_performance_summary(self.parent)
        self.assertEqual(len(result['drawdown_series']), 41)
        self.assertAlmostEqual(min(point['value'] for point in result['drawdown_series']), result['max_drawdown']['value'] * 100, places=4)
