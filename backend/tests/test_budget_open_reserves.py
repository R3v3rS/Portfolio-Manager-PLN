import unittest
from uuid import uuid4
from database import get_db
from tests.test_budget_planning import BudgetPlanningTest
from tests.test_budget_reserves import FrozenDate


class OpenReserveTest(unittest.TestCase):
    result=BudgetPlanningTest.result
    item=BudgetPlanningTest.item
    move=BudgetPlanningTest.move
    plan=BudgetPlanningTest.plan
    bill=BudgetPlanningTest.bill
    forecast=BudgetPlanningTest.forecast
    get_workspace=BudgetPlanningTest.get_workspace

    def setUp(self):
        BudgetPlanningTest.setUp(self)

    def create(self,amount=0,**extra):
        payload=dict(name='Poduszka',notes='',account_id=self.account,open_ended=True,monthly_amount=amount,request_id=str(uuid4()))
        payload.update(extra)
        return self.result(self.client.post(self.base,json=payload),201)['id']

    def test_zero_plan_requires_no_goal_deadline_or_category_and_allows_manual_saving(self):
        reserve=self.create()
        self.assertEqual(self.get_workspace()['totals']['to_plan'],10000)
        self.assertEqual((self.item(reserve)['monthly_required'],self.item(reserve)['urgent'],self.item(reserve)['overdue']),(0,False,False))
        self.result(self.move(reserve,'ADD',333),201)
        self.assertEqual((self.item(reserve)['saved'],self.get_workspace()['totals']['to_plan']),(333,9667))
        self.assertEqual(self.get_workspace()['planning']['reserve_plans'][0]['planned'],0)
        self.assertFalse(any(e['kind'] in ('RESERVE_ADD','RESERVE_COST') for e in self.forecast()['events']))

    def test_fixed_plan_is_not_reduced_by_large_savings_or_missing_months(self):
        reserve=self.create(100)
        self.result(self.move(reserve,'ADD',700),201)
        for month in ('2026-11','2026-12','2027-01'):
            row=self.get_workspace(month)['planning']['reserve_plans'][0]
            self.assertEqual((row['planned'],row['remaining']),(100,100))
        self.assertTrue(all(e['amount']==100 for e in self.forecast()['events'] if e['kind']=='RESERVE_ADD'))

    def test_partial_saving_reduces_only_current_remaining_and_never_cash_twice(self):
        reserve=self.create(100)
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9900)
        self.result(self.move(reserve,'ADD',30),201)
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9900)
        self.assertEqual(self.get_workspace()['planning']['reserve_plans'][0]['remaining'],70)
        self.assertEqual(self.get_workspace()['totals']['balance'],10000)
        FrozenDate.current=FrozenDate(2026,11,3)
        self.assertEqual(self.item(reserve)['monthly_required'],100)

    def test_payment_preserves_unused_reserve_and_does_not_satisfy_saving_plan(self):
        reserve=self.create(100)
        self.result(self.move(reserve,'ADD',500),201)
        FrozenDate.current=FrozenDate(2026,11,3)
        self.result(self.move(reserve,'SPEND',180),201)
        self.assertEqual((self.item(reserve)['saved'],self.item(reserve)['monthly_required'],self.item(reserve)['status']),(320,100,'ACTIVE'))
        self.assertEqual(self.get_workspace('2026-11')['totals']['budget_spent'],0)
        self.assertEqual(self.get_workspace('2026-11')['totals']['to_plan'],9400)

    def test_manual_month_override_rejected_and_default_change_can_be_zero(self):
        reserve=self.create(100)
        self.assertEqual(self.plan(reserve,amount=200).status_code,400)
        self.result(self.client.put(f'{self.base}/{reserve}',json=dict(name='Poduszka',notes='',account_id=self.account,open_ended=True,monthly_amount=0,version=self.item(reserve)['version'])))
        for month in ('2026-10','2026-11'):
            self.assertEqual(self.get_workspace(month)['planning']['reserve_plans'][0]['planned'],0)

    def test_shared_optional_category_does_not_control_or_duplicate_media_limits(self):
        first=self.create(100,category_id=self.category)
        self.create(50,category_id=self.category)
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9850)
        self.assertEqual(self.get_workspace()['categories'][0]['planned'],0)
        self.result(self.move(first,'ADD',100),201)
        self.assertEqual(self.get_workspace()['categories'][0]['spent'],0)
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9850)

    def test_create_retry_and_invalid_amount_are_safe(self):
        payload=dict(name='Poduszka',notes='',account_id=self.account,open_ended=True,monthly_amount=0,request_id=str(uuid4()))
        first=self.result(self.client.post(self.base,json=payload),201)
        self.assertEqual(first,self.result(self.client.post(self.base,json=payload),201))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserves').fetchone()[0],1)
        self.assertEqual(self.client.post(self.base,json=dict(payload,monthly_amount=-1,request_id=str(uuid4()))).status_code,400)

    def test_changing_fixed_amount_keeps_completed_months_plan(self):
        reserve=self.create(100)
        self.result(self.move(reserve,'ADD',150),201)
        FrozenDate.current=FrozenDate(2026,11,3)
        self.result(self.client.put(f'{self.base}/{reserve}',json=dict(name='Poduszka',notes='',account_id=self.account,open_ended=True,monthly_amount=0,version=self.item(reserve)['version'])))
        self.assertEqual(self.get_workspace('2026-10')['planning']['reserve_plans'][0]['planned'],100)
        self.assertEqual(self.get_workspace('2026-11')['planning']['reserve_plans'][0]['planned'],0)
        self.assertEqual((self.item(reserve)['saved'],self.get_workspace()['totals']['balance']),(150,10000))


if __name__=='__main__':unittest.main()
