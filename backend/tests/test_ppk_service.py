import sys
import unittest
import json
import tempfile
from datetime import date, timedelta
from unittest.mock import patch
from flask import Flask
from database import get_db, init_db
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from modules.ppk.ppk_service import PPKService  # noqa: E402


class PPKServiceParsingTestCase(unittest.TestCase):
    def test_parse_biznesradar_history_maps_polish_date_and_decimal(self):
        html = """
        <table>
          <tr><td>14.04.2026</td><td>20,15</td></tr>
          <tr><td>13.04.2026</td><td>20.03</td></tr>
        </table>
        """

        parsed = PPKService._parse_biznesradar_history(html)

        self.assertEqual(
            parsed,
            [
                {'date': '2026-04-14', 'price': 20.15},
                {'date': '2026-04-13', 'price': 20.03},
            ],
        )


class PPKRefreshTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config['DATABASE'] = str(Path(self.tmp.name)/'ppk.db')
        init_db(self.app)
        self.ctx = self.app.app_context(); self.ctx.push()
        self.db = get_db()
        self.pid = self.db.execute("INSERT INTO portfolios(name,account_type,current_cash) VALUES ('PPK','PPK',0)").lastrowid
        self.db.commit()
        self.monday = date.today() - timedelta(days=date.today().weekday()+7)

    def tearDown(self):
        self.ctx.pop(); self.tmp.cleanup()

    def seed(self, points):
        self.db.execute('INSERT INTO ppk_weekly_history(fund_id,data,last_week,updated_at) VALUES (?,?,?,?)',
                        ('61777738',json.dumps(points),points[-1]['week'],'2020-01-01 00:00:00'))
        self.db.commit()

    def test_newer_quote_in_same_week_replaces_previous_day(self):
        start = self.monday.isoformat(); newer = (self.monday+timedelta(days=3)).isoformat()
        self.seed([{'week': start,'price':27}])
        with patch.object(PPKService,'fetch_daily_history',return_value=[{'date':newer,'price':28}]):
            result = PPKService.update_cache('61777738', start)
        self.assertEqual(result['data'],[{'week':newer,'price':28}])
        self.assertEqual(PPKService.get_cached_price()['date'],newer)

    def test_weekly_gaps_do_not_invent_fresh_quotation_dates(self):
        points = [{'date': self.monday.isoformat(),'price':27},
                  {'date': (self.monday+timedelta(days=10)).isoformat(),'price':28}]
        weekly = PPKService.aggregate_weekly(points)
        self.assertEqual([p['week'] for p in weekly],[p['date'] for p in points])
        self.assertEqual(len(weekly),2)

    def test_older_provider_data_does_not_replace_saved_quote(self):
        saved = date.today().isoformat()
        self.seed([{'week':saved,'price':28}])
        with patch.object(PPKService,'fetch_daily_history',return_value=[{'date':self.monday.isoformat(),'price':25}]):
            result = PPKService.update_cache('61777738', self.monday.isoformat())
        self.assertIn('starszą',result['warning'])
        self.assertEqual(PPKService.get_cached_price(),{'price':28,'date':saved})

    def test_failed_refresh_preserves_cache_and_reports_failure(self):
        self.seed([{'week':self.monday.isoformat(),'price':27}])
        with patch.object(PPKService,'fetch_daily_history',return_value=[]), patch.object(PPKService,'fetch_current_price',side_effect=RuntimeError('offline')):
            result = PPKService.refresh_price(self.pid,force=True)
        self.assertIsNotNone(result['warning'])
        self.assertFalse(result['changed'])
        self.assertEqual(result['currentPrice']['price'],27)

    def test_automatic_refresh_is_shared_and_throttled_but_manual_can_retry(self):
        today = date.today().isoformat()
        # History works even if no contributions have been entered yet.
        with patch.object(PPKService,'fetch_daily_history',return_value=[{'date':today,'price':28}]) as fetch:
            result = PPKService.refresh_price(self.pid)
            PPKService.refresh_price(self.pid)
            self.assertEqual(fetch.call_count,1)
            self.assertTrue(result['changed'])
            PPKService.refresh_price(self.pid,force=True)
            self.assertEqual(fetch.call_count,2)

    def test_official_parser_selects_only_exact_fund_and_valid_dates(self):
        data={'items':[
            {'code':'FZD2060','product':'PPK','currency':'PLN','quoteDate':date.today().isoformat(),'purchasePrice':99},
            {'code':'FZD2055','product':'PPK','currency':'PLN','quoteDate':date.today().isoformat(),'purchasePrice':27.09},
            {'code':'FZD2055','product':'PPK','currency':'PLN','quoteDate':'2099-01-01','purchasePrice':99},
        ]}
        self.assertEqual(PPKService._parse_nn_current(data)['price'],27.09)
        with self.assertRaises(ValueError):
            PPKService._parse_nn_current({'items':[data['items'][0]]})
        history = PPKService._parse_nn_history({'FZD2055':{'graphData':{self.monday.isoformat():27,'2099-01-01':99,'bad':20,date.today().isoformat():float('nan')}}})
        self.assertEqual(len(history),1)

    def test_refresh_route_updates_shared_cache_without_changing_contributions(self):
        from routes_portfolio_base import portfolio_bp
        import routes_ppk
        self.app.register_blueprint(portfolio_bp,url_prefix='/api/portfolio')
        before = [tuple(r) for r in self.db.execute('SELECT * FROM portfolios')]
        with patch.object(PPKService,'fetch_daily_history',return_value=[{'date':date.today().isoformat(),'price':28}]):
            response=self.app.test_client().post(f'/api/portfolio/ppk/prices/refresh/{self.pid}',json={'force':True})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json()['payload']['currentPrice']['price'],28)
        self.assertEqual(before,[tuple(r) for r in self.db.execute('SELECT * FROM portfolios')])
        self.assertEqual(self.db.execute('SELECT count(*) FROM ppk_transactions').fetchone()[0],0)


if __name__ == '__main__':
    unittest.main()
