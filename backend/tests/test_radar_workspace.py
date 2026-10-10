import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import get_db, init_db
from routes_radar import radar_bp
from price_service import PriceService
from api.exceptions import ValidationError, NotFoundError


class RadarWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=os.path.join(self.temp.name, 'radar.db'))
        self.app.register_blueprint(radar_bp, url_prefix='/api/radar')
        self.app.register_error_handler(ValidationError, lambda error: ({'error': str(error)}, 400))
        self.app.register_error_handler(NotFoundError, lambda error: ({'error': str(error)}, 404))
        init_db(self.app)
        self.client = self.app.test_client()
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO watchlist (ticker) VALUES ('ABC')")
            db.commit()

    def test_uses_persisted_quotes_with_original_timestamp_without_provider_calls(self):
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO radar_cache (ticker, price, last_updated_at) VALUES ('ABC', 90, '2026-01-01 12:00:00')")
            db.execute("INSERT INTO quotes_cache (ticker, level, price, change_1d, updated_at) VALUES ('ABC', 'full', 110, 0, '2026-04-01T15:00:00')")
            db.execute("INSERT INTO asset_metadata (ticker, company_name, currency, updated_at) VALUES ('ABC', 'Example', 'USD', '2026-04-01')")
            db.commit()
        with patch.object(PriceService, 'refresh_radar_data') as refresh:
            data = self.client.get('/api/radar/').get_json()['payload'][0]
        refresh.assert_not_called()
        self.assertEqual(data['price'], 110)
        self.assertEqual(data['change_1d'], 0)
        self.assertEqual(data['currency'], 'USD')
        self.assertEqual(data['last_updated_at'], '2026-04-01T15:00:00')

    def test_newer_price_does_not_reuse_older_percentage_changes(self):
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO quotes_cache (ticker, level, price, change_1d, updated_at) VALUES ('ABC', 'full', 110, 5, '2026-04-01 12:00:00')")
            db.execute("INSERT INTO price_cache (ticker, price, updated_at) VALUES ('ABC', 115, '2026-04-01T15:00:00')")
            db.commit()
        item = self.client.get('/api/radar/').get_json()['payload'][0]
        self.assertEqual(item['price'], 115)
        self.assertIsNone(item['change_1d'])

    def test_missing_momentum_uses_history_near_quote_date(self):
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO price_cache (ticker, price, updated_at) VALUES ('ABC', 120, '2026-09-22T15:00:00')")
            for day, price in (('2026-08-21', 100), ('2026-09-15', 110), ('2025-08-01', 50)):
                db.execute('INSERT INTO stock_prices (ticker, date, close_price) VALUES (?, ?, ?)', ('ABC', day, price))
            db.commit()
        item = self.client.get('/api/radar/').get_json()['payload'][0]
        self.assertAlmostEqual(item['change_1m'], 20)
        self.assertAlmostEqual(item['change_7d'], (120 / 110 - 1) * 100)
        self.assertIsNone(item['change_1y'])
        self.assertIsNone(item['change_1d'])

    def test_notes_persist_and_can_disable_target(self):
        notes = {'thesis': 'My idea', 'invalidation': 'Lower margin', 'review_date': '2026-12-01', 'target_price': 123.45, 'target_direction': 'above'}
        response = self.client.post('/api/radar/notes/ABC', json=notes)
        self.assertEqual(response.status_code, 200)
        item = self.client.get('/api/radar/').get_json()['payload'][0]
        self.assertEqual(item['notes']['thesis'], 'My idea')
        self.assertEqual(item['notes']['target_price'], 123.45)
        notes['target_price'] = None
        self.client.post('/api/radar/notes/ABC', json=notes)
        self.assertIsNone(self.client.get('/api/radar/').get_json()['payload'][0]['notes']['target_price'])

    def test_invalid_notes_are_rejected(self):
        for payload in ({'target_price': -1}, {'target_price': True}, {'target_direction': 'sideways'}, {'review_date': '2026-02-31'}, {'thesis': 'a' * 4001}):
            with self.subTest(payload=str(payload)[:80]):
                self.assertEqual(self.client.post('/api/radar/notes/ABC', json=payload).status_code, 400)

    def test_history_excludes_invalid_and_future_prices(self):
        today = date.today()
        with self.app.app_context():
            db = get_db()
            for offset, price in ((-2, 100), (-1, 0), (0, 110), (1, 120)):
                db.execute('INSERT INTO stock_prices (ticker, date, close_price) VALUES (?, ?, ?)', ('ABC', (today + timedelta(days=offset)).isoformat(), price))
            db.commit()
        history = self.client.get('/api/radar/history/ABC').get_json()['payload']
        self.assertEqual([point['close_price'] for point in history], [100, 110])
        self.assertEqual(history[-1]['date'], today.isoformat())

    def test_missing_fundamentals_and_etf_do_not_get_low_scores(self):
        info = {'returnOnEquity': .2, 'profitMargins': .2, 'freeCashflow': 10, 'revenueGrowth': .2, 'earningsGrowth': .2, 'debtToEquity': 50, 'currentRatio': 2, 'beta': .8}
        for values, ticker, expected in (({}, 'ABC', None), (info, 'ABC', 100), ({**info, 'quoteType': 'ETF'}, 'FUND', None)):
            with self.subTest(ticker=ticker, expected=expected):
                provider = Mock(info=values)
                provider.history.return_value = pd.DataFrame()
                with patch('price_service.yf.Ticker', return_value=provider):
                    result = PriceService.get_stock_analysis(ticker)
                self.assertIsNotNone(result)
                self.assertEqual(result['score'], expected)


if __name__ == '__main__':
    unittest.main()
