import unittest
from uuid import uuid4
from database import get_db
from tests.test_budget_planning import BudgetPlanningTest
from tests.test_budget_reserves import FrozenDate


class BudgetMediaTest(unittest.TestCase):
    result=BudgetPlanningTest.result
    create_reserve=BudgetPlanningTest.create_reserve
    item=BudgetPlanningTest.item
    move=BudgetPlanningTest.move
    plan=BudgetPlanningTest.plan
    bill=BudgetPlanningTest.bill
    get_workspace=BudgetPlanningTest.get_workspace
    forecast=BudgetPlanningTest.forecast
    expense=BudgetPlanningTest.expense

    def setUp(self):
        BudgetPlanningTest.setUp(self)

    def media(self,amount=250,**extra):
        return self.create_reserve(name='Prąd',monthly_amount=amount,category_id=self.category,**extra)

    def test_default_repeats_and_override_only_affects_selected_current_month(self):
        reserve=self.media()
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9750)
        self.result(self.plan(reserve,amount=220))
        for month,amount in [('2026-10',220),('2026-11',250)]:
            data=self.get_workspace(month)
            self.assertEqual(data['planning']['reserve_plans'][0]['planned'],amount)
            self.assertEqual(data['totals']['to_plan'],10000-amount)
        self.assertEqual(self.get_workspace('2026-09')['totals']['to_plan'],10000)

    def test_matching_category_limit_is_one_pool_not_double_commitment(self):
        reserve=self.media()
        db=get_db();db.execute('INSERT INTO budget_plans_v2 VALUES(?,?,?)',(self.category,'2026-10',25000));db.commit()
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9750)
        self.result(self.plan(reserve,amount=220))
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9780)
        self.result(self.plan(reserve,amount=250,version=1))
        self.result(self.move(reserve,'ADD',250),201)
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9750)
        self.assertEqual(self.get_workspace()['categories'][0]['spent'],250)

    def test_payment_consumes_only_earmark_and_keeps_monthly_envelope_active(self):
        reserve=self.media()
        self.result(self.move(reserve,'ADD',250),201)
        self.result(self.move(reserve,'SPEND',180),201)
        data=self.get_workspace()
        self.assertEqual((data['totals']['spent'],data['totals']['budget_spent'],data['totals']['reserved'],data['totals']['to_plan']),(180,250,70,9750))
        self.assertEqual((self.item(reserve)['status'],self.item(reserve)['saved']),('ACTIVE',70))
        self.assertEqual((data['categories'][0]['spent'],data['categories'][0]['actual_spent']),(250,180))
        media=next(r for r in data['planning']['month_plan'] if r['kind']=='MEDIA')
        self.assertEqual((media['planned'],media['done'],media['remaining']),(250,250,0))
        self.assertEqual(next(r for r in data['planning']['month_plan'] if r['kind']=='DAILY')['remaining'],0)

    def test_current_unfunded_payment_leaves_only_difference_to_put_aside(self):
        reserve=self.media()
        self.result(self.move(reserve,'SPEND',180),201)
        row=self.get_workspace()['planning']['reserve_plans'][0]
        self.assertEqual((row['funded'],row['remaining']),(180,70))
        self.result(self.move(reserve,'ADD',70),201)
        self.assertEqual(self.get_workspace()['totals']['budget_spent'],250)
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9750)

    def test_large_late_invoice_uses_prior_savings_and_only_current_allocation(self):
        reserve=self.media()
        self.result(self.move(reserve,'ADD',250),201)
        FrozenDate.current=FrozenDate(2026,11,3)
        self.result(self.move(reserve,'ADD',250),201)
        self.result(self.move(reserve,'SPEND',420),201)
        data=self.get_workspace('2026-11')
        self.assertEqual((data['totals']['budget_spent'],data['totals']['reserved'],data['totals']['to_plan']),(250,80,9500))
        self.assertEqual(self.get_workspace('2026-10')['totals']['budget_spent'],250)

    def test_uncovered_large_invoice_costs_only_actual_shortfall_extra(self):
        reserve=self.media()
        self.result(self.move(reserve,'ADD',250),201)
        self.result(self.move(reserve,'SPEND',400),201)
        data=self.get_workspace()
        self.assertEqual((data['totals']['budget_spent'],data['totals']['to_plan']),(400,9600))
        self.assertEqual(self.item(reserve)['saved'],0)

    def test_quarterly_variable_bill_can_use_monthly_envelope(self):
        reserve=self.media(140)
        self.result(self.move(reserve,'ADD',140),201)
        bill=self.bill(title='Woda',frequency='QUARTERLY',amount=420,reserve_id=reserve,variable_amount=True)
        data=dict(month='2026-10',date='2026-10-03',amount=400,version=1,reserve_version=self.item(reserve)['version'],request_id=str(uuid4()))
        url=f'/api/budget/workspace/bills/{bill}/pay'
        self.result(self.client.post(url,json=data),201)
        self.result(self.client.post(url,json=data),201)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)
        self.assertEqual(self.get_workspace()['totals']['budget_spent'],400)
        self.assertEqual(self.item(reserve)['status'],'ACTIVE')

    def test_imported_payment_is_linked_without_second_balance_change(self):
        reserve=self.media()
        self.result(self.move(reserve,'ADD',250),201)
        entry=self.expense(180,day='2026-10-03')
        before=self.get_workspace()['totals']['balance']
        self.result(self.move(reserve,'SPEND',180,existing_entry_id=entry,entry_version=1),201)
        self.assertEqual(self.get_workspace()['totals']['balance'],before)
        self.assertEqual(self.get_workspace()['totals']['budget_spent'],250)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)

    def test_forecast_uses_default_and_override_without_fake_deadline_or_daily_duplicate(self):
        reserve=self.media()
        self.result(self.plan(reserve,amount=220))
        forecast=self.forecast()
        adds=[r for r in forecast['events'] if r['kind']=='RESERVE_ADD']
        self.assertEqual(next(r for r in adds if r['scheduled_date'][:7]=='2026-10')['amount'],220)
        self.assertEqual(next(r for r in adds if r['scheduled_date'][:7]=='2026-11')['amount'],250)
        self.assertFalse(any(r['kind'] in ('DAILY','RESERVE_COST') for r in forecast['events']))
        self.bill(title='Prąd',amount=180,reserve_id=reserve,variable_amount=True)
        forecast=self.forecast()
        self.assertFalse(any(r['kind'] in ('DAILY','BILL') for r in forecast['events']))
        self.assertEqual(next(r for r in forecast['events'] if r['kind']=='RESERVE_COST')['amount'],180)

    def test_zero_override_and_default_update_and_category_validation(self):
        reserve=self.media()
        self.result(self.plan(reserve,amount=0))
        self.assertEqual(self.get_workspace()['totals']['to_plan'],10000)
        row=self.item(reserve)
        self.result(self.client.put(f'{self.base}/{reserve}',json=dict(name='Prąd',notes='',account_id=self.account,frequency='YEARLY',monthly_amount=300,category_id=self.category,version=row['version'])))
        self.assertEqual(self.get_workspace('2026-11')['planning']['reserve_plans'][0]['planned'],300)
        duplicate=self.client.post(self.base,json=dict(name='Druga',notes='',account_id=self.account,frequency='YEARLY',monthly_amount=100,category_id=self.category,request_id=str(uuid4())))
        self.assertEqual(duplicate.status_code,400)

    def test_monthly_bill_failure_rolls_back_payment_cash_and_earmark(self):
        from budget_bills_service import pay
        reserve=self.media()
        self.result(self.move(reserve,'ADD',250),201)
        bill=self.bill(title='Prąd',amount=180,reserve_id=reserve,variable_amount=True)
        db=get_db();db.execute("CREATE TRIGGER fail_bill BEFORE INSERT ON budget_bill_payments_v2 BEGIN SELECT RAISE(ABORT,'fail'); END");db.commit()
        with self.assertRaises(Exception):
            pay(bill,dict(month='2026-10',date='2026-10-03',amount=180,version=1,reserve_version=2,request_id=str(uuid4())))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        self.assertEqual((self.item(reserve)['saved'],self.get_workspace()['totals']['balance']),(250,10000))

    def test_forecast_after_unfunded_invoice_only_sets_aside_remaining_pool(self):
        reserve=self.media()
        self.result(self.move(reserve,'SPEND',180),201)
        forecast=self.forecast()
        first=next(e for e in forecast['events'] if e['kind']=='RESERVE_ADD')
        self.assertEqual(first['amount'],70)

    def test_partial_correction_below_completed_amount_keeps_real_savings(self):
        reserve=self.media()
        self.result(self.move(reserve,'ADD',250),201)
        self.result(self.plan(reserve,amount=220))
        self.assertEqual((self.item(reserve)['saved'],self.get_workspace()['totals']['to_plan']),(250,9750))
        self.result(self.move(reserve,'RELEASE',30),201)
        self.assertEqual((self.item(reserve)['saved'],self.get_workspace()['totals']['budget_spent'],self.get_workspace()['totals']['to_plan']),(220,220,9780))

    def test_converting_existing_reserve_keeps_earmarks_cash_and_previous_month(self):
        FrozenDate.current=FrozenDate(2026,9,3)
        reserve=self.create_reserve(name='Woda kwartał',category_id=self.category,target_amount=420,frequency='ONCE',due_date='2026-12-30')
        self.result(self.move(reserve,'ADD',140),201)
        previous=self.get_workspace('2026-09')
        FrozenDate.current=FrozenDate(2026,10,3)
        row=self.item(reserve)
        self.result(self.client.put(f'{self.base}/{reserve}',json=dict(name='Woda',notes='',account_id=self.account,monthly_amount=140,frequency='ONCE',category_id=self.category,version=row['version'])))
        self.assertEqual((self.item(reserve)['saved'],self.get_workspace()['totals']['balance']),(140,10000))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserve_movements').fetchone()[0],1)
        self.assertEqual(self.get_workspace('2026-09')['categories'],previous['categories'])
        historical=self.get_workspace('2026-09')['planning']['reserve_plans'][0]
        for key in ('planned','recommended','funded','remaining','monthly_amount'):
            self.assertEqual(historical[key],previous['planning']['reserve_plans'][0][key],key)
        self.assertEqual(self.get_workspace()['planning']['reserve_plans'][0]['remaining'],140)


if __name__=='__main__': unittest.main()
