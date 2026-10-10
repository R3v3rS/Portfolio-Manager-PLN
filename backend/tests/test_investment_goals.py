import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import date

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import get_db, init_db
from api.exceptions import NotFoundError, ValidationError
from api.response import error_response
from routes_investment_goals import goals_bp


class InvestmentGoalsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name) / 'goals.db'))
        init_db(self.app)
        self.app.register_blueprint(goals_bp, url_prefix='/api/investment-goals')
        self.app.register_error_handler(ValidationError, lambda e: error_response('validation_error', str(e), status=400))
        self.app.register_error_handler(NotFoundError, lambda e: error_response('not_found', str(e), status=404))
        self.client = self.app.test_client()
        with self.app.app_context():
            db = get_db()
            self.parent = db.execute("INSERT INTO portfolios(name,account_type,current_cash) VALUES ('IKE','IKE',100)").lastrowid
            self.child = db.execute("INSERT INTO portfolios(name,account_type,current_cash,parent_portfolio_id) VALUES ('ETF','STANDARD',200,?)", (self.parent,)).lastrowid
            self.savings = db.execute("INSERT INTO portfolios(name,account_type,current_cash) VALUES ('Savings','SAVINGS',500)").lastrowid
            db.execute('''INSERT INTO holdings(portfolio_id,sub_portfolio_id,ticker,quantity,average_buy_price,total_cost,currency)
                VALUES (?,?,'ABC',2,10,20,'USD')''', (self.parent, self.child))
            stamp=date.today().isoformat()+'T12:00:00'
            db.executemany('INSERT INTO price_cache(ticker,price,updated_at) VALUES (?,?,?)', [('ABC',20,stamp),('USDPLN=X',4,stamp)])
            db.commit()
        self.plan = dict(name='Home', description='My goal', target_amount=10000, target_date='2031-10-01', monthly_contribution=100, annual_return=0, portfolio_ids=[self.parent, self.savings], target_allocation={'stocks':40,'bonds':20,'ppk':0,'savings':30,'cash':10})

    def tearDown(self):
        self.tmp.cleanup()

    def create(self, **changes):
        return self.client.post('/api/investment-goals/', json={**self.plan, **changes})

    def goals(self):
        response = self.client.get('/api/investment-goals/')
        self.assertEqual(response.status_code, 200)
        return response.json['payload']

    def test_create_update_and_archive_persist_without_touching_finances(self):
        with self.app.app_context():
            db = get_db()
            before = {table: [tuple(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in ('portfolios','holdings','transactions')}
        created = self.create()
        self.assertEqual(created.status_code, 201)
        goal_id = created.json['payload']['id']
        goal = self.goals()['goals'][0]
        self.assertAlmostEqual(goal['current_value'], 959.2)
        self.assertEqual(goal['allocation']['cash'], 300)
        self.assertEqual(goal['allocation']['savings'], 500)
        self.assertAlmostEqual(goal['allocation']['stocks'], 159.2)
        self.assertEqual(self.client.put(f'/api/investment-goals/{goal_id}', json={**self.plan, 'name':'Retirement','portfolio_ids':[self.child]}).status_code, 200)
        updated = self.goals()['goals'][0]
        self.assertEqual(updated['name'], 'Retirement')
        self.assertEqual(updated['portfolio_ids'], [self.child])
        self.assertAlmostEqual(updated['current_value'], 359.2)
        for archive in (True, False):
            self.assertEqual(self.client.put(f'/api/investment-goals/{goal_id}/archive', json={'archived':archive}).status_code, 200)
            self.assertEqual(self.goals()['goals'][0]['is_archived'], archive)
        with self.app.app_context():
            db = get_db()
            self.assertEqual(before, {table: [tuple(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in before})

    def test_parent_and_child_cannot_double_count_capital(self):
        for ids in ([self.parent,self.child], [self.parent,self.parent]):
            with self.subTest(ids=ids):
                self.assertEqual(self.create(portfolio_ids=ids).status_code, 400)
        self.assertEqual(self.goals()['goals'], [])

    def test_invalid_values_do_not_partially_save(self):
        cases = [{'name':' '}, {'target_amount':float('nan')}, {'annual_return':float('inf')}, {'target_amount':True}, {'target_amount':0}, {'monthly_contribution':-1}, {'annual_return':-100}, {'target_date':'2031-02-30'}, {'portfolio_ids':[]}, {'portfolio_ids':[self.parent+.5]}, {'portfolio_ids':[99999]}, {'target_allocation':{'cash':100}}, {'target_allocation':{'stocks':50,'bonds':20,'ppk':0,'savings':30,'cash':10}}]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.create(**case).status_code, 400)
        self.assertEqual(self.goals()['goals'], [])

    def test_invalid_update_keeps_original_plan_and_links(self):
        goal_id = self.create().json['payload']['id']
        self.assertEqual(self.client.put(f'/api/investment-goals/{goal_id}', json={**self.plan, 'portfolio_ids':[99999]}).status_code, 400)
        self.assertEqual(self.goals()['goals'][0]['portfolio_ids'], self.plan['portfolio_ids'])

    def test_missing_fx_disables_projection_instead_of_assuming_one(self):
        self.create()
        with self.app.app_context():
            db = get_db(); db.execute("DELETE FROM price_cache WHERE ticker='USDPLN=X'"); db.commit()
        goal = self.goals()['goals'][0]
        self.assertIsNone(goal['current_value'])
        self.assertTrue(goal['warnings'])

    def test_missing_legacy_currency_uses_persisted_asset_metadata(self):
        with self.app.app_context():
            db = get_db()
            db.execute('UPDATE holdings SET currency=NULL')
            db.execute("INSERT INTO asset_metadata(ticker,currency,updated_at) VALUES ('ABC','USD','2026-10-01')")
            db.commit()
        self.create()
        self.assertAlmostEqual(self.goals()['goals'][0]['current_value'], 959.2)

    def test_cross_goal_overlap_is_reported_and_archive_removes_warning(self):
        first = self.create(name='First').json['payload']['id']
        self.create(name='Second', portfolio_ids=[self.child])
        self.assertEqual(self.goals()['goals'][0]['overlapping_goals'], ['First'])
        self.client.put(f'/api/investment-goals/{first}/archive', json={'archived':True})
        self.assertEqual(self.goals()['goals'][0]['overlapping_goals'], [])

    def test_archived_or_removed_portfolio_keeps_goal_but_reports_missing_value(self):
        self.create()
        with self.app.app_context():
            db = get_db(); db.execute('UPDATE portfolios SET is_archived=1 WHERE id=?', (self.parent,)); db.commit()
        result = self.goals()
        self.assertIsNone(result['goals'][0]['current_value'])
        self.assertNotIn(self.child, [p['id'] for p in result['portfolios']])
        self.assertEqual(self.create(portfolio_ids=[self.child]).status_code, 400)

    def test_ppk_bonds_and_savings_use_existing_models_without_network(self):
        with self.app.app_context():
            db = get_db()
            ppk = db.execute("INSERT INTO portfolios(name,account_type) VALUES ('PPK','PPK')").lastrowid
            bonds = db.execute("INSERT INTO portfolios(name,account_type,current_cash) VALUES ('Bonds','BONDS',100)").lastrowid
            today=date.today().isoformat()
            db.execute('INSERT INTO ppk_weekly_history(fund_id,data,last_week,updated_at) VALUES (?,?,?,?)', ('61777738',json.dumps([{'week':today,'price':100}]),today,today))
            db.commit()
        with patch('investment_goals_service.PPKService.get_portfolio_summary', return_value={'totalNetValue':1000}), patch('investment_goals_service.BondService.get_bonds', return_value=[{'total_value':2000}]):
            self.create(portfolio_ids=[ppk,bonds,self.savings])
            goal = self.goals()['goals'][0]
        self.assertEqual(goal['current_value'], 3600)
        self.assertEqual(goal['allocation']['ppk'], 1000)
        self.assertEqual(goal['allocation']['bonds'], 2000)

    def test_update_missing_and_bad_archive_return_domain_errors(self):
        self.assertEqual(self.client.put('/api/investment-goals/9999',json=self.plan).status_code, 404)
        goal_id = self.create().json['payload']['id']
        self.assertEqual(self.client.put(f'/api/investment-goals/{goal_id}/archive',json={'archived':'false'}).status_code, 400)
