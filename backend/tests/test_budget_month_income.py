"""Monthly income planning is independent of opening balances and past savings."""
import unittest
from datetime import date
from tests import test_budget_planning as fixtures
from tests.test_budget_reserves import FrozenDate
from database import get_db
from routes_budget_workspace import insert_entry


class MonthIncomeTests(unittest.TestCase):
    setUp=fixtures.BudgetPlanningTest.setUp
    result=fixtures.BudgetPlanningTest.result
    get_workspace=fixtures.BudgetPlanningTest.get_workspace
    expense=fixtures.BudgetPlanningTest.expense
    income=fixtures.BudgetPlanningTest.income
    create_reserve=fixtures.BudgetPlanningTest.create_reserve
    item=fixtures.BudgetPlanningTest.item
    move=fixtures.BudgetPlanningTest.move
    bill=fixtures.BudgetPlanningTest.bill

    def test_month_income_excludes_opening_balance_and_counts_plan_and_overspending(self):
        db=get_db()
        insert_entry(db,dict(kind='INCOME',account_id=self.account,amount_cents=100000,date='2026-10-03',description='Pensja',merchant=None,lines=[]))
        db.execute("INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,'2026-10',60000)",(self.category,));db.commit()
        self.expense(100,day='2026-10-03')
        totals=self.get_workspace()['totals']
        self.assertEqual((totals['monthly_income_total'],totals['monthly_income_to_plan'],totals['to_plan']),(1000,400,10400))
        db.execute('UPDATE budget_accounts SET balance=balance+5000');db.commit()
        self.assertEqual(self.get_workspace()['totals']['monthly_income_to_plan'],400)
        self.expense(600,day='2026-10-03')
        self.assertEqual(self.get_workspace()['totals']['monthly_income_to_plan'],300)

    def test_pending_income_is_replaced_by_received_income_without_double_counting(self):
        self.income(amount=1000)
        self.assertEqual(self.get_workspace()['totals']['monthly_income_to_plan'],1000)
        db=get_db();income=db.execute('SELECT id FROM budget_expected_incomes').fetchone()[0]
        self.result(self.client.post(f'/api/budget/forecast/incomes/{income}/receive',json=dict(occurrence_date='2026-10-10',date='2026-10-03',amount=1000,version=1,request_id='d1fd25dc-e43a-4480-8dd9-f9c2b839e821')),201)
        totals=self.get_workspace()['totals']
        self.assertEqual((totals['income'],totals['expected_income'],totals['monthly_income_to_plan']),(1000,0,1000))

    def test_releasing_previous_month_savings_does_not_create_month_income(self):
        reserve=self.create_reserve(target_amount=500,due_date='2027-03-10',frequency='ONCE')
        self.result(self.move(reserve,'ADD',200),201)
        FrozenDate.current=date(2026,11,3)
        self.result(self.move(reserve,'RELEASE',100),201)
        totals=self.get_workspace('2026-11')['totals']
        self.assertEqual(totals['monthly_income_cost'],0)
        self.assertEqual(totals['monthly_income_to_plan'],-totals['monthly_income_remaining_plan'])

    def test_old_reserve_payment_excludes_its_covered_cost_and_released_surplus(self):
        reserve=self.create_reserve(target_amount=200,due_date='2026-11-15',frequency='ONCE')
        self.result(self.move(reserve,'ADD',200),201)
        FrozenDate.current=date(2026,11,3)
        self.result(self.move(reserve,'SPEND',100),201)
        totals=self.get_workspace('2026-11')['totals']
        self.assertEqual((totals['spent'],totals['monthly_income_cost']),(100,0))

    def test_current_reserve_deposit_and_payment_count_once(self):
        reserve=self.create_reserve(target_amount=200,due_date='2026-10-15',frequency='ONCE')
        self.result(self.move(reserve,'ADD',200),201)
        self.result(self.move(reserve,'SPEND',100),201)
        self.assertEqual(self.get_workspace()['totals']['monthly_income_cost'],100)

    def test_one_off_bill_is_in_one_month_only_and_paid_history_cannot_be_hidden(self):
        bill=self.bill(title='Jednorazowy zakup',frequency='ONCE',due_month='2026-10',due_day=20,amount=100)
        self.assertEqual(len(self.get_workspace()['bills']),1)
        self.assertEqual(self.get_workspace('2026-11')['bills'],[])
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03')),201)
        payload=dict(title='Jednorazowy zakup',frequency='ONCE',due_month='2026-11',due_day=20,amount=100,account_id=self.account,category_id=self.category,version=2)
        self.assertEqual(self.client.put(f'/api/budget/workspace/bills/{bill}',json=payload).status_code,400)
        self.assertEqual(self.get_workspace()['bills'][0]['status'],'PAID')

    def test_paid_bill_inside_category_limit_does_not_spend_month_income_twice(self):
        self.income(amount=1000)
        db=get_db();db.execute("INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,'2026-10',40000)",(self.category,));db.commit()
        bill=self.bill(amount=250)
        before=self.get_workspace()['totals']['monthly_income_to_plan']
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03')),201)
        self.assertEqual((before,self.get_workspace()['totals']['monthly_income_to_plan']),(600,600))
