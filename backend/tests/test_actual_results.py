import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from actual_results_service import analyze, modified_dietz, money_weighted
from database import get_db, init_db
from api.exceptions import NotFoundError, ValidationError
from api.response import error_response
from routes_history import portfolio_bp
from routes_investment_goals import goals_bp


class ActualResultsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name) / 'results.db'))
        init_db(self.app)
        self.app.register_blueprint(portfolio_bp, url_prefix='/api/portfolio')
        self.app.register_blueprint(goals_bp, url_prefix='/api/investment-goals')
        self.app.register_error_handler(ValidationError, lambda e: error_response('validation_error', str(e), status=400))
        self.app.register_error_handler(NotFoundError, lambda e: error_response('not_found', str(e), status=404))
        self.ctx = self.app.app_context(); self.ctx.push()
        db = get_db()
        self.parent = db.execute("INSERT INTO portfolios(name,account_type) VALUES ('Parent','IKE')").lastrowid
        self.child = db.execute("INSERT INTO portfolios(name,account_type,parent_portfolio_id) VALUES ('Child','IKE',?)", (self.parent,)).lastrowid
        db.execute("INSERT INTO asset_metadata(ticker,currency,updated_at) VALUES ('ABC','PLN','2026-01-01')")
        db.executemany('INSERT INTO stock_prices(ticker,date,close_price) VALUES (?,?,?)', [('ABC','2025-12-31',100),('ABC','2026-01-31',120)])
        db.commit()

    def tearDown(self):
        self.ctx.pop(); self.tmp.cleanup()

    def tx(self, day, kind, amount, ticker='CASH', quantity=0, child=None, transfer=None, realized=0, commission=0):
        db = get_db()
        db.execute('''INSERT INTO transactions(portfolio_id,sub_portfolio_id,ticker,date,type,quantity,price,total_value,transfer_id,realized_profit,commission)
            VALUES (?,?,?,?,?,?,0,?,?,?,?)''', (self.parent,child,ticker,day,kind,quantity,amount,transfer,realized,commission))
        db.commit()

    def test_deposit_is_not_profit_and_dietz_weights_its_date(self):
        self.tx('2026-01-01','DEPOSIT',100)
        self.tx('2026-01-01','BUY',100,'ABC',1)
        self.tx('2026-01-16','DEPOSIT',100)
        result = analyze([self.parent], '2026-01-02', '2026-01-31')
        self.assertEqual(result['opening_value'],100)
        self.assertEqual(result['closing_value'],220)
        self.assertEqual(result['profit'],20)
        self.assertAlmostEqual(result['dietz_percent'],20 / 150 * 100, places=4)
        self.assertIsNone(result['xirr_percent'])

    def test_closed_position_and_income_remain_in_result_without_double_counting(self):
        self.tx('2025-12-01','DEPOSIT',100)
        self.tx('2025-12-02','BUY',100,'ABC',1)
        self.tx('2026-01-10','SELL',149,'ABC',1,realized=49,commission=1)
        self.tx('2026-01-11','DIVIDEND',10,'ABC')
        self.tx('2026-01-12','INTEREST',2)
        self.tx('2026-01-20','WITHDRAW',50)
        result = analyze([self.parent], '2026-01-01', '2026-01-31')
        self.assertEqual(result['profit'],61)
        self.assertEqual(result['closing_value'],111)
        self.assertEqual(result['dividends'],10)
        self.assertEqual(result['interest'],2)
        self.assertEqual(result['recorded_commissions'],1)
        self.assertEqual(result['realized_profit'],49)

    def test_internal_transfer_excluded_but_flow_into_child_is_external_for_child(self):
        self.tx('2026-01-01','DEPOSIT',100)
        self.tx('2026-01-02','WITHDRAW',40,transfer='pair')
        self.tx('2026-01-02','DEPOSIT',40,child=self.child,transfer='pair')
        parent = analyze([self.parent,self.child], '2026-01-01', '2026-01-31')
        child = analyze([self.child], '2026-01-01', '2026-01-31')
        self.assertEqual(parent['deposits'],100)
        self.assertEqual(parent['withdrawals'],0)
        self.assertEqual(parent['internal_transfer_amount'],40)
        self.assertEqual(parent['closing_value'],100)
        self.assertEqual(child['deposits'],40)
        self.assertEqual(child['internal_transfer_amount'],0)

    def test_missing_fx_and_unknown_currency_do_not_create_zero_profit(self):
        self.tx('2025-12-01','DEPOSIT',100)
        self.tx('2025-12-02','BUY',100,'ABC',1)
        get_db().execute("UPDATE asset_metadata SET currency='USD' WHERE ticker='ABC'")
        result = analyze([self.parent], '2026-01-01', '2026-01-31')
        self.assertIsNone(result['profit']); self.assertIsNone(result['dietz_percent'])
        self.assertEqual(result['status'],'partial')
        get_db().execute("DELETE FROM asset_metadata WHERE ticker='ABC'")
        self.assertIsNone(analyze([self.parent], '2026-01-01', '2026-01-31')['profit'])

    def test_cash_inconsistency_blocks_rates_and_analysis_never_writes(self):
        self.tx('2025-01-01','DEPOSIT',100)
        get_db().execute('UPDATE portfolios SET current_cash=120 WHERE id=?', (self.parent,)); get_db().commit()
        tables = ['transactions','holdings','portfolios','investment_goals','portfolio_history_cache','price_cache']
        before = {table:[tuple(r) for r in get_db().execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in tables}
        result = analyze([self.parent])
        self.assertEqual(result['status'],'inconsistent')
        self.assertEqual(result['reconciliation']['cash_difference'],20)
        self.assertIsNone(result['dietz_percent']); self.assertIsNone(result['xirr_percent'])
        self.assertEqual(before, {table:[tuple(r) for r in get_db().execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in tables})

    def test_position_inconsistency_blocks_rates_even_with_matching_cash(self):
        self.tx('2025-01-01','DEPOSIT',100)
        self.tx('2025-01-01','BUY',100,'ABC',1)
        get_db().execute('INSERT INTO holdings(portfolio_id,ticker,quantity,average_buy_price,total_cost,currency) VALUES (?,\'ABC\',2,100,200,\'PLN\')', (self.parent,))
        result = analyze([self.parent])
        self.assertEqual(result['reconciliation']['positions_mismatch'],['ABC'])
        self.assertIsNone(result['dietz_percent'])

    def test_nonpositive_base_and_short_history_are_unavailable(self):
        self.assertIsNone(modified_dietz(0,100,[(date(2026,1,31),100)],date(2026,1,31),date(2026,1,31)))
        self.assertIsNone(money_weighted([(date(2026,1,1),-100),(date(2026,2,1),110)]))

    def test_closed_asset_needs_no_fresh_price_after_sale(self):
        self.tx('2025-01-01','DEPOSIT',100)
        self.tx('2025-01-02','BUY',100,'ABC',1)
        self.tx('2026-01-03','SELL',120,'ABC',1)
        result = analyze([self.parent], '2026-01-01', '2026-03-31')
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['profit'],20)
        self.assertIsNotNone(result['dietz_percent'])

    def test_xirr_checks_unique_solution_and_dates(self):
        self.assertAlmostEqual(money_weighted([(date(2025,1,1),-100),(date(2026,1,1),110)]),10,places=4)
        self.assertAlmostEqual(money_weighted([(date(2025,1,1),-100),(date(2026,1,1),90)]),-10,places=4)
        # Two positive IRRs: 10% and 20%; don't select one arbitrarily.
        self.assertIsNone(money_weighted([(date(2025,1,1),-100),(date(2026,1,1),230),(date(2027,1,1),-132)]))

    def test_monthly_profit_telescopes_and_partial_month_is_not_best_month(self):
        self.tx('2026-01-01','DEPOSIT',100)
        self.tx('2026-01-15','INTEREST',1)
        self.tx('2026-02-15','INTEREST',2)
        self.tx('2026-03-01','INTEREST',10)
        result = analyze([self.parent], '2026-01-01', '2026-03-02')
        self.assertEqual(sum(m['profit'] for m in result['months']),result['profit'])
        self.assertTrue(result['months'][-1]['partial_month'])
        self.assertEqual(result['best_month']['date'],'2026-02-28')

    def test_ppk_without_price_is_incomplete_not_a_false_zero_return(self):
        get_db().execute("UPDATE portfolios SET account_type='PPK' WHERE id=?", (self.parent,))
        result = analyze([self.parent], '2026-01-01', '2026-01-31')
        get_db().execute("INSERT INTO ppk_transactions(portfolio_id,date,employee_units,employer_units,price_per_unit) VALUES (?,'2026-01-01',1,1,100)", (self.parent,))
        result = analyze([self.parent], '2026-01-01', '2026-01-31')
        self.assertEqual(result['status'],'partial')
        self.assertIsNone(result['profit']); self.assertIsNone(result['xirr_percent'])

    def test_routes_validate_dates_and_goal_scope(self):
        self.tx('2026-01-01','DEPOSIT',100)
        client = self.app.test_client()
        self.assertEqual(client.get(f'/api/portfolio/history/results/{self.parent}?from=wrong').status_code,400)
        self.assertEqual(client.get(f'/api/portfolio/history/results/{self.parent}?from=2026-02-01&to=2026-01-01').status_code,400)
        self.assertEqual(client.get('/api/investment-goals/9999/results').status_code,404)
        goal = get_db().execute("INSERT INTO investment_goals(name,target_amount,target_date,created_at,updated_at) VALUES ('Home',1000,'2030-01-01','2026-01-01','2026-01-01')").lastrowid
        get_db().execute('INSERT INTO investment_goal_portfolios(goal_id,portfolio_id) VALUES (?,?)',(goal,self.parent));get_db().commit()
        response = client.get(f'/api/investment-goals/{goal}/results?from=2026-01-01&to=2026-01-31')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['payload']['deposits'],100)
