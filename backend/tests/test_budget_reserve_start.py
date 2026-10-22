"""A future monthly envelope starts planning then, without rewriting real costs."""
import unittest
from uuid import uuid4

from database import get_db
from tests import test_budget_planning as fixtures
from tests.test_budget_reserves import FrozenDate


class ReserveStartTest(unittest.TestCase):
    setUp=fixtures.BudgetPlanningTest.setUp
    result=fixtures.BudgetPlanningTest.result
    create_reserve=fixtures.BudgetPlanningTest.create_reserve
    item=fixtures.BudgetPlanningTest.item
    move=fixtures.BudgetPlanningTest.move
    plan=fixtures.BudgetPlanningTest.plan
    bill=fixtures.BudgetPlanningTest.bill
    expense=fixtures.BudgetPlanningTest.expense
    get_workspace=fixtures.BudgetPlanningTest.get_workspace
    forecast=fixtures.BudgetPlanningTest.forecast

    def media(self,**extra):
        return self.create_reserve(name='Woda Listopad - Styczeń',monthly_amount=140,
            category_id=self.category,monthly_start_month='2026-11',**extra)

    def update(self,reserve,**extra):
        payload=dict(name='Woda Listopad - Styczeń',notes='',account_id=self.account,frequency='YEARLY',
            monthly_amount=140,category_id=self.category,monthly_start_month='2026-11',version=self.item(reserve)['version'])
        payload.update(extra)
        return self.client.put(f'{self.base}/{reserve}',json=payload)

    def test_new_future_pool_does_not_claim_october_payment_or_create_october_plan(self):
        self.expense(374.20,day='2026-10-03')
        before=self.get_workspace()
        reserve=self.media()
        october=self.get_workspace()
        self.assertEqual(october['planning']['reserve_plans'],[])
        self.assertEqual(october['totals']['spent'],374.20)
        self.assertEqual(october['totals']['to_plan'],before['totals']['to_plan'])
        item=self.item(reserve)
        self.assertEqual((item['month_planned'],item['month_allocated'],item['monthly_required'],item['saved']),(0,0,0,0))
        self.assertFalse(item['monthly_started'])
        self.assertEqual(item['next_contribution_date'],'2026-11-01')
        for month in ('2026-11','2026-12','2027-01'):
            row=self.get_workspace(month)['planning']['reserve_plans'][0]
            self.assertEqual((row['planned'],row['remaining']),(140,140))

    def test_changing_empty_pool_start_preserves_cash_and_actual_history(self):
        self.expense(374.20,day='2026-10-03')
        reserve=self.create_reserve(name='Woda',monthly_amount=140,category_id=self.category)
        db=get_db();before=[tuple(r) for r in db.execute('SELECT * FROM budget_entries_v2')]
        balance=self.get_workspace()['totals']['balance']
        self.result(self.update(reserve))
        self.assertEqual(self.get_workspace()['planning']['reserve_plans'],[])
        self.assertEqual(self.get_workspace()['totals']['balance'],balance)
        self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM budget_entries_v2')],before)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_reserve_movements').fetchone()[0],0)

    def test_forecast_starts_november_and_keeps_month_override(self):
        reserve=self.media()
        self.assertEqual(self.plan(reserve,amount=99).status_code,400)
        self.result(self.plan(reserve,amount=125,month='2026-11'))
        events=[e for e in self.forecast()['events'] if e['kind']=='RESERVE_ADD']
        self.assertEqual(events[0]['scheduled_date'][:7],'2026-11')
        self.assertEqual(events[0]['amount'],125)
        self.assertEqual(events[1]['amount'],140)
        self.assertFalse(any(e['scheduled_date'][:7]=='2026-10' for e in events))

    def test_start_month_activates_plan_without_claiming_prior_month_expense(self):
        self.expense(374.20,day='2026-10-03')
        reserve=self.media()
        FrozenDate.current=FrozenDate(2026,11,3)
        item=self.item(reserve)
        self.assertTrue(item['monthly_started'])
        self.assertEqual((item['month_planned'],item['month_allocated'],item['monthly_required']),(140,0,140))
        self.result(self.move(reserve,'ADD',50),201)
        self.assertEqual(self.item(reserve)['monthly_required'],90)

    def test_start_of_open_ended_fixed_reserve_is_also_respected(self):
        reserve=self.create_reserve(name='Poduszka',open_ended=True,monthly_amount=100,monthly_start_month='2026-11')
        self.assertEqual(self.get_workspace()['totals']['to_plan'],10000)
        self.assertEqual(self.item(reserve)['monthly_required'],0)
        self.assertEqual(self.get_workspace('2026-11')['planning']['reserve_plans'][0]['planned'],100)
        self.assertTrue(all(e['scheduled_date'][:7]>='2026-11' for e in self.forecast()['events'] if e['kind']=='RESERVE_ADD'))

    def test_start_with_financial_history_cannot_be_shifted_silently(self):
        reserve=self.create_reserve(name='Woda',monthly_amount=140,category_id=self.category)
        self.result(self.move(reserve,'ADD',100),201)
        before=self.get_workspace()['totals']
        self.assertEqual(self.update(reserve).status_code,400)
        self.assertEqual(self.get_workspace()['totals'],before)
        self.assertEqual(self.item(reserve)['monthly_start_month'],'2026-10')
        FrozenDate.current=FrozenDate(2026,11,3)
        self.result(self.update(reserve,monthly_start_month='2026-10',monthly_amount=150))
        self.assertEqual(self.get_workspace('2026-10')['planning']['reserve_plans'][0]['planned'],140)

    def test_invalid_start_months_are_rejected_without_creating_a_reserve(self):
        for month in ('2026-13','2026-11-01','1999-12','2026-09',False):
            payload=dict(name='Woda',monthly_amount=140,category_id=self.category,account_id=self.account,
                monthly_start_month=month,request_id=str(uuid4()))
            self.assertEqual(self.client.post(self.base,json=payload).status_code,400,month)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserves').fetchone()[0],0)

    def test_existing_october_bill_remains_in_forecast_before_november_pool(self):
        reserve=self.media()
        self.bill(title='Woda',amount=180,reserve_id=reserve)
        db=get_db();db.execute('INSERT INTO budget_plans_v2 VALUES(?,?,?)',(self.category,'2026-10',20000));db.commit()
        data=self.forecast()
        self.assertTrue(any(e['kind']=='RESERVE_COST' and e['scheduled_date'][:7]=='2026-10' and e['amount']==180 for e in data['events']))
        self.assertEqual(next(r for r in data['month_plans'] if r['month']=='2026-10')['ordinary_limit'],20)

    def test_converted_reserve_keeps_previous_month_history_with_later_start(self):
        FrozenDate.current=FrozenDate(2026,9,3)
        reserve=self.create_reserve(name='Woda',category_id=self.category,due_date='2027-01-31')
        self.result(self.move(reserve,'ADD',100),201)
        previous=self.get_workspace('2026-09')
        FrozenDate.current=FrozenDate(2026,10,3)
        self.result(self.update(reserve))
        self.assertEqual(self.get_workspace()['planning']['reserve_plans'],[])
        old=self.get_workspace('2026-09')
        self.assertEqual(old['categories'],previous['categories'])
        for field in ('planned','funded','remaining','monthly_amount'):
            self.assertEqual(old['planning']['reserve_plans'][0][field],previous['planning']['reserve_plans'][0][field])
        self.assertEqual(self.item(reserve)['saved'],100)
