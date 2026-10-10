import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from flask import Flask

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api.exceptions import ValidationError
from api.response import error_response
from database import get_db, init_db
from routes_dashboard import dashboard_bp


class FrozenDate(date):
    @classmethod
    def today(cls):
        return cls(2026,10,2)


class MonthlyReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True,DATABASE=str(Path(self.tmp.name)/'report.db'))
        init_db(self.app)
        self.app.register_blueprint(dashboard_bp,url_prefix='/api/dashboard')
        self.app.register_error_handler(ValidationError,lambda e:error_response('validation_error',str(e),status=400))
        self.client = self.app.test_client()
        # The report and its delegated valuation must share the same test clock.
        for module in ('monthly_report_service','actual_results_service','special_account_results'):
            frozen = patch(module+'.date',FrozenDate); frozen.start(); self.addCleanup(frozen.stop)
        self.ctx = self.app.app_context(); self.ctx.push()
        self.db = get_db()
        self.account = self.sql("INSERT INTO budget_accounts(name,balance) VALUES ('Bank',0)")
        self.category = self.sql("INSERT INTO budget_categories_v2(name) VALUES ('Groceries')")
        self.portfolio = self.sql("INSERT INTO portfolios(name,account_type) VALUES ('ETF','STANDARD')")

    def tearDown(self):
        self.ctx.pop(); self.tmp.cleanup()

    def sql(self,sql,args=()):
        result=self.db.execute(sql,args).lastrowid; self.db.commit(); return result

    def get(self,month='2026-09'):
        response=self.client.get('/api/dashboard/monthly-report'+('' if month is None else '?month='+month))
        self.assertEqual(response.status_code,200)
        return response.json['payload']

    def entry(self,day,kind,amount,category=True):
        entry=self.sql('''INSERT INTO budget_entries_v2(account_id,kind,amount_cents,date,description)
            VALUES (?,?,?,?,'Recorded entry')''',(self.account,kind,amount,day))
        if category and kind=='EXPENSE':
            self.sql('INSERT INTO budget_entry_lines_v2(entry_id,category_id,amount_cents) VALUES (?,?,?)',(entry,self.category,amount))
        return entry

    def tx(self,day,kind,value,ticker='CASH',quantity=0,portfolio=None,transfer=None):
        return self.sql('''INSERT INTO transactions(portfolio_id,ticker,date,type,quantity,price,total_value,transfer_id)
            VALUES (?,?,?,?,?,0,?,?)''',(portfolio or self.portfolio,ticker,day,kind,quantity,value,transfer))

    def test_default_last_complete_month_and_strict_validation(self):
        self.assertEqual(self.get(None)['month'],'2026-09')
        for month in ('2026-13','2026-1','2026-11','0000-01','1999-12','bad','2026-09-01',''):
            with self.subTest(month=month):
                self.assertEqual(self.client.get('/api/dashboard/monthly-report?month='+month).status_code,400)

    def test_partial_month_compares_equal_elapsed_days_and_excludes_future_records(self):
        self.entry('2026-09-01','INCOME',10000)
        self.entry('2026-09-30','INCOME',90000)
        self.entry('2026-10-01','INCOME',20000)
        self.entry('2026-10-03','INCOME',50000)
        report=self.get('2026-10')
        self.assertTrue(report['period']['partial'])
        self.assertEqual(report['period']['end'],'2026-10-02')
        self.assertEqual(report['period']['previous_end'],'2026-09-02')
        self.assertEqual(report['budget']['income'],200)
        self.assertEqual(report['budget']['previous']['income'],100)
        self.assertEqual(report['budget']['changes']['income'],100)

    def test_full_month_comparison_and_categories_do_not_count_transfers_as_expenses(self):
        self.entry('2026-08-31','INCOME',90000)
        self.entry('2026-09-01','INCOME',100000)
        self.entry('2026-09-02','EXPENSE',20000)
        self.entry('2026-09-03','EXPENSE',1000,category=False)
        self.sql("INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES (?,'2026-09',15000)",(self.category,))
        self.sql('''INSERT INTO budget_investment_transfers(account_id,portfolio_id,investment_transaction_id,budget_transaction_id,direction,amount_cents,date,description)
            VALUES (?,?,999,999,'OUT',30000,'2026-09-03','Investment transfer')''',(self.account,self.portfolio))
        report=self.get()
        self.assertFalse(report['period']['partial'])
        self.assertEqual(report['budget']['expenses'],210)
        self.assertEqual(report['budget']['net'],790)
        self.assertEqual(report['budget']['transfer_to_investments'],300)
        self.assertEqual(report['budget']['previous']['income'],900)
        self.assertEqual(sum(r['spent'] for r in report['budget']['categories']),210)
        self.assertTrue(any(r['name']=='Bez kategorii' for r in report['budget']['categories']))
        self.assertTrue(any('Groceries' in r['text'] for r in report['insights']))

    def test_capital_deposits_are_not_profit_and_paired_transfers_are_not_external(self):
        other=self.sql("INSERT INTO portfolios(name,account_type) VALUES ('Other','STANDARD')")
        self.tx('2026-08-01','DEPOSIT',100)
        self.tx('2026-09-01','DEPOSIT',100)
        self.tx('2026-09-02','WITHDRAW',40,transfer='pair')
        self.tx('2026-09-02','DEPOSIT',40,portfolio=other,transfer='pair')
        report=self.get()
        self.assertEqual(report['investments']['operations']['deposits'],100)
        self.assertEqual(report['investments']['operations']['withdrawals'],0)
        self.assertEqual(report['investments']['operations']['internal_transfers'],40)
        self.assertEqual(report['investments']['performance']['profit'],0)

    def test_nested_portfolio_is_valued_once_and_missing_prices_withhold_total_profit(self):
        child=self.sql("INSERT INTO portfolios(name,account_type,parent_portfolio_id) VALUES ('Child','STANDARD',?)",(self.portfolio,))
        self.tx('2026-08-01','DEPOSIT',100,portfolio=child)
        self.tx('2026-08-02','BUY',100,ticker='ABC',quantity=1,portfolio=child)
        self.sql("INSERT INTO asset_metadata(ticker,currency,updated_at) VALUES ('ABC','PLN','now')")
        self.sql("INSERT INTO stock_prices(ticker,date,close_price) VALUES ('ABC','2026-08-31',100)")
        report=self.get()
        self.assertEqual(len(report['investments']['performance']['items']),1)
        self.assertIsNone(report['investments']['performance']['profit'])
        self.sql("INSERT INTO stock_prices(ticker,date,close_price) VALUES ('ABC','2026-09-30',120)")
        report=self.get()
        self.assertEqual(report['investments']['performance']['profit'],20)

    def test_current_cash_inconsistency_withholds_profit(self):
        self.tx('2026-10-01','DEPOSIT',100)
        self.sql('UPDATE portfolios SET current_cash=120 WHERE id=?',(self.portfolio,))
        report=self.get('2026-10')
        self.assertIsNone(report['investments']['performance']['profit'])
        self.assertEqual(report['investments']['performance']['items'][0]['status'],'inconsistent')

    def test_wealth_requires_exact_boundary_snapshots(self):
        for day,value in [('2026-08-30',100),('2026-09-20',130)]:
            self.sql('INSERT INTO net_worth_snapshots(date,net_worth,total_assets,total_liabilities,recorded_at) VALUES (?,?,?,0,?)',(day,value,value,day))
        report=self.get()
        self.assertIsNone(report['wealth']['change']); self.assertEqual(report['wealth']['latest']['date'],'2026-09-20')
        for day,value in [('2026-08-31',110),('2026-09-30',140)]:
            self.sql('INSERT INTO net_worth_snapshots(date,net_worth,total_assets,total_liabilities,recorded_at) VALUES (?,?,?,0,?)',(day,value,value,day))
        self.assertEqual(self.get()['wealth']['change'],30)

    def test_actual_loan_cash_is_separate_from_schedule_and_budget(self):
        loan=self.sql("INSERT INTO loans(name,original_amount,duration_months,start_date,installment_type) VALUES ('Loan',1200,12,'2026-01-15','EQUAL')")
        entry=self.entry('2026-09-03','EXPENSE',10000)
        self.sql('''INSERT INTO loan_installment_payments(loan_id,installment_month,due_date,paid_on,amount_cents,budget_entry_id)
            VALUES (?,7,'2026-08-15','2026-09-03',10000,?)''',(loan,entry))
        self.sql("INSERT INTO loan_overpayments(loan_id,amount,date) VALUES (?,50,'2026-09-04')",(loan,))
        # A payment made in October cannot confirm the installment at September-end.
        self.sql('''INSERT INTO loan_installment_payments(loan_id,installment_month,due_date,paid_on,amount_cents)
            VALUES (?,8,'2026-09-15','2026-10-01',10000)''',(loan,))
        report=self.get()
        self.assertEqual(report['loans']['paid_amount'],100)
        self.assertEqual(report['loans']['overpaid_amount'],50)
        self.assertEqual(report['loans']['items'][0]['scheduled_count'],1)
        self.assertEqual(report['loans']['without_record'],1)
        self.assertEqual(report['budget']['expenses'],100)
        self.assertEqual(report['loans']['items'][0]['budget_linked_amount'],100)

    def test_archived_journal_history_and_ppk_contributions_remain_in_report(self):
        entry=self.sql('''INSERT INTO investor_journal(title,entry_date,kind,status,is_archived,created_at,updated_at)
            VALUES ('Decision','2026-09-10','BUY','CLOSED',1,'now','now')''')
        self.sql('''INSERT INTO investor_journal_reviews(entry_id,review_date,outcome,notes,lessons,entry_status,created_at)
            VALUES (?,'2026-09-20','CONFIRMED','Facts','Lesson','CLOSED','now')''',(entry,))
        ppk=self.sql("INSERT INTO portfolios(name,account_type) VALUES ('PPK','PPK')")
        self.sql("INSERT INTO ppk_transactions(portfolio_id,date,employee_units,employer_units,price_per_unit) VALUES (?,'2026-09-05',2,3,100)",(ppk,))
        report=self.get()
        self.assertEqual(report['journal']['reviews'][0]['lessons'],'Lesson')
        self.assertEqual(len(report['journal']['entries']),1)
        self.assertEqual(report['investments']['ppk']['employee_contributions'],200)
        self.assertEqual(report['investments']['ppk']['employer_contributions'],300)
        self.assertEqual(report['investments']['performance']['excluded_count'],0)
        self.assertFalse(report['investments']['performance']['complete'])

    def test_ppk_price_growth_excludes_both_contributions_and_future_prices(self):
        import json
        pid=self.sql("INSERT INTO portfolios(name,account_type) VALUES ('PPK','PPK')")
        self.sql("INSERT INTO ppk_transactions(portfolio_id,date,employee_units,employer_units,price_per_unit) VALUES (?,'2026-08-05',2,3,100)",(pid,))
        self.sql("INSERT INTO ppk_transactions(portfolio_id,date,employee_units,employer_units,price_per_unit) VALUES (?,'2026-09-10',1,1,110)",(pid,))
        self.sql("INSERT INTO ppk_weekly_history(fund_id,data,last_week) VALUES ('61777738',?,'2026-10-01')",
            (json.dumps([dict(week='2026-08-31',price=100),dict(week='2026-09-30',price=120),dict(week='2026-10-01',price=999)]),))
        report=self.get(); item=next(r for r in report['investments']['performance']['items'] if r['id']==pid)
        self.assertEqual(item['opening_value'],500)
        self.assertEqual(item['closing_value'],840)
        self.assertEqual(item['profit'],120)  # 840-500-220, not the 340 increase in value.
        self.assertEqual(report['investments']['performance']['profit'],120)

    def test_stale_ppk_price_shows_estimate_but_withholds_total_and_rate(self):
        import json
        pid=self.sql("INSERT INTO portfolios(name,account_type) VALUES ('PPK','PPK')")
        self.sql("INSERT INTO ppk_transactions(portfolio_id,date,employee_units,employer_units,price_per_unit) VALUES (?,'2026-08-05',2,3,100)",(pid,))
        self.sql("INSERT INTO ppk_weekly_history(fund_id,data,last_week) VALUES ('61777738',?,'2026-09-17')",
            (json.dumps([dict(week='2026-08-31',price=100),dict(week='2026-09-17',price=110)]),))
        report=self.get(); item=next(r for r in report['investments']['performance']['items'] if r['id']==pid)
        self.assertEqual(item['estimated_profit'],50)
        self.assertIsNone(item['profit']); self.assertIsNone(item['return_percent'])
        self.assertIsNone(report['investments']['performance']['profit'])
        self.assertTrue(any('2026-09-17' in w for w in item['warnings']))

    def test_bonds_daily_accrual_counts_existing_capital_once_and_skips_future_purchase(self):
        from bond_service import BondService
        from uuid import uuid4
        pid=self.sql("INSERT INTO portfolios(name,account_type) VALUES ('Bonds','BONDS')")
        for day in ('2026-09-01','2026-10-01'):
            BondService.create(dict(portfolio_id=pid,name='EDO test',kind='EDO',quantity=1,nominal=100,purchase_price=100,
                purchase_date=day,interest_rate=6,tax_rate=19,redemption_fee=3,fee_policy='CAP_INTEREST',
                acquisition='EXISTING',payout_account_id=None,forecast_enabled=False,notes='',request_id=str(uuid4())))
        report=self.get(); item=next(r for r in report['investments']['performance']['items'] if r['id']==pid)
        self.assertEqual(item['opening_value'],0)
        self.assertAlmostEqual(item['closing_value'],100+round(6*29/365*.81,2),places=2)
        self.assertAlmostEqual(item['profit'],round(6*29/365*.81,2),places=2)

    def test_wealth_history_is_dated_and_retains_recorded_asset_breakdown(self):
        import json
        self.sql('''INSERT INTO net_worth_snapshots(date,net_worth,total_assets,total_liabilities,recorded_at,assets_breakdown)
            VALUES ('2026-08-20',100,120,20,'now',?)''',(json.dumps(dict(ppk=20,bonds=100)),))
        self.sql("INSERT INTO net_worth_snapshots(date,net_worth,total_assets,total_liabilities,recorded_at) VALUES ('2026-09-15',140,160,20,'now')")
        report=self.get()
        self.assertIsNone(report['wealth']['change'])
        self.assertEqual(report['wealth']['observed_change'],40)
        self.assertEqual(report['wealth']['history'][0]['assets_breakdown']['ppk'],20)
        self.assertEqual(report['wealth']['history'][-1]['date'],'2026-09-15')

    def test_report_is_read_only_and_never_fetches_quotes(self):
        tables=[r['name'] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        def snapshot():
            return {t:[tuple(r) for r in self.db.execute(f'SELECT * FROM "{t}" ORDER BY rowid')] for t in tables}
        before=snapshot()
        with patch('price_service.PriceService.get_prices',side_effect=AssertionError('No network')):
            self.get(); self.get('2026-10')
        self.assertEqual(before,snapshot())


if __name__=='__main__':
    unittest.main()
