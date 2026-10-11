"""Fixed payment timing must not masquerade as shopping overspending."""
import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4
from database import get_db
from tests import test_budget_planning as fixtures
from tests.test_budget_reserves import FrozenDate
from routes_budget_imports import imports_bp
from budget_chart_service import fixed_summary,comparison_date


class ChartPaceTests(unittest.TestCase):
    result=fixtures.BudgetPlanningTest.result
    get_workspace=fixtures.BudgetPlanningTest.get_workspace
    expense=fixtures.BudgetPlanningTest.expense
    bill=fixtures.BudgetPlanningTest.bill
    create_reserve=fixtures.BudgetPlanningTest.create_reserve
    item=fixtures.BudgetPlanningTest.item
    move=fixtures.BudgetPlanningTest.move

    def setUp(self):
        fixtures.BudgetPlanningTest.setUp(self)
        FrozenDate.current=date(2026,10,8)
        timer=patch('budget_chart_service.date',FrozenDate);timer.start();self.addCleanup(timer.stop)
        self.app.register_blueprint(imports_bp,url_prefix='/api/budget/imports')
        db=get_db()
        self.shopping=db.execute("INSERT INTO budget_categories_v2(name) VALUES('Jedzenie')").lastrowid
        db.execute("INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,'2026-10',31000)",(self.shopping,));db.commit()

    def payment(self,bill,amount):
        return self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-08',amount=amount,request_id=str(uuid4()))),201)['entry_id']

    def test_early_rent_moves_allowance_and_is_not_daily_shopping(self):
        bill=self.bill(title='Czynsz',amount=773,due_day=10)
        self.payment(bill,773)
        self.expense(80,category=self.shopping,day='2026-10-08')
        workspace=self.get_workspace();points=workspace['chart']
        self.assertEqual((points[6]['cash_plan'],points[7]['cash_plan']),(70,853))
        self.assertEqual((points[7]['cash_spent'],points[7]['daily_spent'],points[7]['daily_plan']),(853,80,80))
        self.assertEqual(workspace['bills'][0]['paid_on'],'2026-10-08')
        self.assertEqual(workspace['fixed_costs']['early_count'],1)
        self.assertEqual(workspace['fixed_costs']['pending'],0)
        self.assertIsNone(points[8]['daily_spent'])

    def test_unpaid_bill_keeps_due_date(self):
        self.bill(amount=773,due_day=10)
        points=self.get_workspace()['chart']
        self.assertEqual((points[7]['cash_plan'],points[9]['cash_plan']),(80,873))
        self.assertEqual(comparison_date('2026-10-10','2026-10-15'),'2026-10-10')

    def test_higher_payment_does_not_raise_chart_plan_and_snapshot_survives_edit(self):
        bill=self.bill(amount=773,due_day=10,variable_amount=True)
        self.payment(bill,850)
        workspace=self.get_workspace()
        self.assertEqual((workspace['chart'][7]['cash_plan'],workspace['chart'][7]['cash_spent']),(853,850))
        self.assertEqual((workspace['chart'][-1]['cash_plan'],workspace['chart'][-1]['daily_plan']),(1083,310))
        self.assertEqual(workspace['fixed_costs']['over_plan'],77)
        current=workspace['bills'][0]
        self.result(self.client.put(f'/api/budget/workspace/bills/{bill}',json=dict(title='Czynsz',amount=900,due_day=10,frequency='MONTHLY',start_month='2026-10',account_id=self.account,category_id=self.category,variable_amount=True,version=current['version'])))
        updated=self.get_workspace()
        self.assertEqual(updated['bills'][0]['planned_amount'],773)
        self.assertEqual(updated['chart'][-1]['cash_plan'],1083)

    def test_refunds_keep_purchase_kind_and_reserve_spending_is_excluded(self):
        bill=self.bill(amount=100,due_day=10)
        entry=self.payment(bill,100)
        purchase=self.expense(50,category=self.shopping,day='2026-10-08')
        # Refunds are actual linked expense credits; imported fixed refunds must
        # stay out of daily shopping and shopping refunds reduce its total.
        db=get_db()
        from routes_budget_workspace import insert_entry
        for original,amount,category in ((entry,20,self.category),(purchase,10,self.shopping)):
            refunded=insert_entry(db,dict(kind='INCOME',account_id=self.account,amount_cents=amount*100,date='2026-10-08',description='Zwrot',merchant=None,lines=[dict(category_id=category,amount_cents=amount*100,label='')]))
            db.execute('INSERT INTO budget_purchase_refunds VALUES(?,?,?,?)',(refunded,original,str(uuid4()),'{}'))
        db.commit()
        reserve=self.create_reserve(name='Media',monthly_amount=250,category_id=self.category)
        self.result(self.move(reserve,'SPEND',20,date='2026-10-08'),201)
        self.result(self.move(reserve,'ADD',30,date='2026-10-08'),201)
        point=self.get_workspace()['chart'][7]
        self.assertEqual((point['daily_spent'],point['daily_plan']),(40,80))
        self.assertEqual(point['cash_spent'],140)

    def test_shared_category_keeps_nominal_daily_allowance_after_bill_overrun(self):
        db=get_db();db.execute('DELETE FROM budget_plans_v2')
        db.execute("INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,'2026-10',100000)",(self.category,));db.commit()
        bill=self.bill(amount=773,due_day=10,variable_amount=True)
        self.payment(bill,850)
        workspace=self.get_workspace()
        self.assertEqual(workspace['chart'][-1]['daily_plan'],227)
        self.assertEqual(workspace['chart'][-1]['cash_plan'],1000)

    def test_paid_loan_advances_plan_with_bill_and_summary_counts_each_once(self):
        bill=dict(amount=773,planned_amount=773,status='PAID',due_date='2026-10-10',paid_on='2026-10-08')
        loan=dict(amount=200,paid=True,paid_amount=210,date='2026-10-15',paid_on='2026-10-08')
        summary=fixed_summary([bill],[loan])
        self.assertEqual((summary['planned'],summary['paid'],summary['pending'],summary['over_plan'],summary['early_count']),(973,983,0,10,2))

    def test_past_month_has_complete_series_and_future_month_has_no_actual_spending(self):
        FrozenDate.current=date(2026,11,3)
        historical=self.get_workspace()['chart']
        future=self.get_workspace('2026-12')['chart']
        self.assertIsNotNone(historical[-1]['daily_spent'])
        self.assertTrue(all(p['daily_spent'] is None for p in future))
