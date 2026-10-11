import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from flask import Flask
import pandas as pd

from database import get_db, init_db
from modules.ppk.ppk_calculation import PPKCalculation
from portfolio_core_service import PortfolioCoreService
from portfolio_trade_service import PortfolioTradeService
from portfolio_valuation_service import PortfolioValuationService as Valuation
from investment_goals_service import _own_snapshot
from actual_results_service import analyze
from services.analytics.performance_metrics import calculate_performance_summary, portfolio_var


class InvestmentCorrectionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name)/'investments.db'))
        init_db(self.app)
        self.ctx = self.app.app_context(); self.ctx.push()
        self.db = get_db()
        self.pid = self.db.execute("INSERT INTO portfolios(name,account_type,current_cash) VALUES ('Emerytura','IKE',50)").lastrowid
        self.db.commit()

    def tearDown(self):
        self.ctx.pop(); self.tmp.cleanup()

    def holding(self, currency='PLN', pid=None, child=None):
        self.db.execute('''INSERT INTO holdings(portfolio_id,sub_portfolio_id,ticker,quantity,average_buy_price,total_cost,currency)
            VALUES (?,?,'ABC',2,100,200,?)''', (pid or self.pid,child,currency))
        self.db.commit()

    def quotes(self, prices):
        return patch('portfolio_valuation_service.PriceService.get_prices', return_value=prices)

    def stamps(self):
        return patch('portfolio_valuation_service.PriceService.get_price_updates', return_value={'ABC':date.today().isoformat(),'USDPLN=X':date.today().isoformat()})

    def test_ppk_uses_current_employer_units_for_zus_and_tax_only_paid_profit(self):
        rows = [dict(employee_units=10,employer_units=5,price_per_unit=100)]
        up = PPKCalculation.calculate_metrics(rows,Decimal('120'))
        self.assertEqual(up['totalCurrentValue'],1800)
        self.assertEqual(up['employerToZUS'],180)
        self.assertEqual(up['withdrawalTax'],51.30)
        self.assertEqual(up['totalNetValue'],1568.70)
        self.assertEqual(up['totalProfit'],300)
        down = PPKCalculation.calculate_metrics(rows,Decimal('80'))
        self.assertEqual(down['totalNetValue'],1080)
        self.assertEqual(down['employerToZUS'],120)
        self.assertEqual(down['withdrawalTax'],0)

    def test_ppk_missing_price_preserves_capital_but_withholds_valuation(self):
        result = PPKCalculation.calculate_metrics([dict(employee_units=10,employer_units=5,price_per_unit=100)])
        self.assertEqual(result['totalPurchaseValue'],1500)
        self.assertIsNone(result['totalCurrentValue'])
        self.assertIsNone(result['totalNetValue'])
        self.assertIsNone(result['totalProfit'])

    def test_missing_quote_is_not_purchase_price_and_includes_cash_subtotal(self):
        self.holding()
        before = [tuple(r) for r in self.db.execute('SELECT * FROM holdings')]
        with self.quotes({}), self.stamps(), patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            holding = Valuation.get_holdings(self.pid,cached_prices_only=True)[0]
            result = Valuation.get_portfolio_value(self.pid,cached_prices_only=True)
        self.assertIsNone(holding['current_price']); self.assertIsNone(holding['profit_loss'])
        self.assertEqual(result['valuation_status'],'incomplete')
        self.assertIsNone(result['portfolio_value']); self.assertIsNone(result['total_result'])
        self.assertEqual(result['available_value'],50)
        self.assertEqual(before,[tuple(r) for r in self.db.execute('SELECT * FROM holdings')])

    def test_missing_fx_is_never_pln_one(self):
        self.holding('USD')
        with self.quotes({'ABC':120}), self.stamps(), patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            self.assertIsNone(PortfolioTradeService._get_fx_rates_to_pln({'USD'},cached_only=True)['USD'])
            result = Valuation.get_portfolio_value(self.pid,cached_prices_only=True)
        self.assertEqual(result['valuation_status'],'incomplete'); self.assertIsNone(result['portfolio_value'])
        self.assertTrue(any('USD' in w for w in result['valuation_warnings']))

    def test_parent_missing_child_withholds_total_and_allocation(self):
        child = self.db.execute("INSERT INTO portfolios(name,account_type,parent_portfolio_id,current_cash) VALUES ('ETF','IKE',?,10)",(self.pid,)).lastrowid
        self.holding(child=child)
        with self.quotes({}), self.stamps(), patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            result = Valuation.get_portfolio_value(self.pid,cached_prices_only=True)
        self.assertIsNone(result['portfolio_value']); self.assertEqual(result['available_value'],60)
        self.assertTrue(all(r['share_pct'] is None for r in result['breakdown']))

    def test_incomplete_global_valuation_does_not_write_net_worth_observation(self):
        from routes_dashboard import dashboard_bp
        self.app.register_blueprint(dashboard_bp,url_prefix='/api/dashboard')
        self.holding()
        with self.quotes({}), self.stamps(), patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            response = self.app.test_client().get('/api/dashboard/global-summary')
        self.assertEqual(response.status_code,200)
        value = response.json['payload']
        self.assertEqual(value['valuation_status'],'incomplete')
        self.assertIsNone(value['net_worth']); self.assertIsNone(value['total_assets'])
        self.assertEqual(value['available_assets'],50)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM net_worth_snapshots').fetchone()[0],0)

    def test_tax_account_type_survives_rename_and_internal_strategy_transfer(self):
        child = self.db.execute("INSERT INTO portfolios(name,account_type,parent_portfolio_id) VALUES ('ETF','STANDARD',?)",(self.pid,)).lastrowid
        rows = [(self.pid,None,'DEPOSIT',100,None,'2026-01-01'),(self.pid,None,'WITHDRAW',40,'pair','2026-01-02'),
                (self.pid,child,'DEPOSIT',40,'pair','2026-01-02'),(self.pid,None,'DEPOSIT',999,None,'2027-01-01')]
        self.db.executemany("INSERT INTO transactions(portfolio_id,sub_portfolio_id,type,total_value,transfer_id,date,ticker,quantity,price) VALUES (?,?,?,?,?,?,'CASH',0,0)", rows)
        first = PortfolioCoreService.get_tax_limits()
        self.db.execute("UPDATE portfolios SET name='Dowolna nazwa' WHERE id=?",(self.pid,))
        self.assertEqual(PortfolioCoreService.get_tax_limits()['IKE']['deposited'],100)
        self.assertEqual(first,PortfolioCoreService.get_tax_limits())

    def test_old_goal_quote_warns_and_old_summary_xirr_is_empty(self):
        self.holding()
        self.db.execute("INSERT INTO price_cache(ticker,price,updated_at) VALUES ('ABC',120,'2020-01-01')")
        buckets, warnings = _own_snapshot(dict(self.db.execute('SELECT * FROM portfolios WHERE id=?',(self.pid,)).fetchone()))
        self.assertEqual(buckets['stocks'],240); self.assertTrue(warnings)
        with self.quotes({'ABC':120}), patch('portfolio_valuation_service.PriceService.get_price_updates',return_value={'ABC':'2020-01-01'}), patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            result = Valuation.get_portfolio_value(self.pid,cached_prices_only=True)
        self.assertEqual(result['valuation_status'],'stale'); self.assertIsNone(result['xirr_percent'])

    def test_goal_ppk_result_counts_employer_contributions_as_capital(self):
        self.db.execute("UPDATE portfolios SET account_type='PPK',current_cash=0 WHERE id=?",(self.pid,))
        self.db.execute("INSERT INTO ppk_transactions(portfolio_id,date,employee_units,employer_units,price_per_unit) VALUES (?,'2026-01-01',10,5,10)",(self.pid,))
        self.db.execute("INSERT INTO ppk_weekly_history(fund_id,data,last_week) VALUES ('61777738',?,'2026-01-31')",(json.dumps([dict(week='2026-01-31',price=15)]),))
        result = analyze([self.pid],'2026-01-01','2026-01-31')
        self.assertEqual(result['closing_value'],225); self.assertEqual(result['deposits'],150)
        self.assertEqual(result['profit'],75); self.assertEqual(result['status'],'ok')
        self.assertEqual(sum(m['profit'] for m in result['months']),75)

    def test_empty_portfolio_has_unavailable_xirr(self):
        self.db.execute('UPDATE portfolios SET current_cash=0 WHERE id=?',(self.pid,))
        self.assertIsNone(Valuation.get_portfolio_value(self.pid,cached_prices_only=True)['xirr_percent'])

    def test_ppk_summary_does_not_count_cash_deposit_as_fund_profit(self):
        self.db.execute("UPDATE portfolios SET account_type='PPK' WHERE id=?",(self.pid,))
        self.db.execute("INSERT INTO transactions(portfolio_id,ticker,type,total_value,date,quantity,price) VALUES (?,'CASH','DEPOSIT',50,'2026-01-01',0,0)",(self.pid,))
        self.db.execute("INSERT INTO ppk_transactions(portfolio_id,date,employee_units,employer_units,price_per_unit) VALUES (?,'2026-01-01',10,5,100)",(self.pid,))
        self.db.execute("INSERT INTO ppk_weekly_history(fund_id,data,last_week) VALUES ('61777738',?,?)",(json.dumps([dict(week=date.today().isoformat(),price=120)]),date.today().isoformat()))
        result = Valuation.get_portfolio_value(self.pid,cached_prices_only=True)
        self.assertEqual(result['asset_value'],1850)
        self.assertEqual(result['withdrawable_value'],1618.7)
        self.assertEqual(result['net_contributions'],1550)
        self.assertEqual(result['investment_result'],300)

    def test_mixed_goal_supports_bonds_and_cash_without_duplicate_purchase_capital(self):
        from bond_service import BondService
        from uuid import uuid4
        self.db.execute("INSERT INTO transactions(portfolio_id,ticker,type,total_value,date,quantity,price) VALUES (?,'CASH','DEPOSIT',50,'2026-08-01',0,0)",(self.pid,))
        bond_id = self.db.execute("INSERT INTO portfolios(name,account_type) VALUES ('Obligacje','BONDS')").lastrowid
        self.db.commit()
        BondService.create(dict(portfolio_id=bond_id,name='EDO test',kind='EDO',quantity=1,nominal=100,purchase_price=100,
            purchase_date='2026-09-01',interest_rate=6,tax_rate=19,redemption_fee=3,fee_policy='CAP_INTEREST',
            acquisition='EXISTING',payout_account_id=None,forecast_enabled=False,notes='',request_id=str(uuid4())))
        result = analyze([self.pid,bond_id],'2026-09-01','2026-09-30')
        self.assertEqual(result['opening_value'],50)
        self.assertEqual(result['deposits'],100)
        self.assertAlmostEqual(result['closing_value'],150.39,places=2)
        self.assertAlmostEqual(result['profit'],.39,places=2)
        self.assertNotEqual(result['status'],'unsupported')

    def test_risk_exposes_actual_common_session_dates_for_selected_year(self):
        returns = pd.Series([.01,-.02,.005]*40,index=pd.bdate_range('2026-04-20',periods=120))
        snapshot = [dict(ticker='ABC',weight=1,current_value_pln=200,currency='PLN')]
        with patch('services.analytics.performance_metrics.MarketDataAdapter.get_holdings_snapshot',return_value=snapshot), patch('services.analytics.performance_metrics._weighted_returns',return_value=returns):
            for result in (calculate_performance_summary(self.pid),portfolio_var(self.pid)):
                self.assertEqual(result['data_points'],120)
                self.assertEqual(result['observed_from'],'2026-04-20')
                self.assertEqual(result['observed_to'],returns.index[-1].date().isoformat())


if __name__ == '__main__':
    unittest.main()
