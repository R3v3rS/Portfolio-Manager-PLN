import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from database import get_db
from tests import test_cash_forecast as forecast_fixtures
from tests import test_budget_reserves as fixtures
from routes_budget_planning import planning_bp
from budget_summary_service import monthly_budget_totals
from budget_category_hierarchy_service import category_workspace
from budget_bills_service import pay


class BudgetPlanningTest(unittest.TestCase):
    result=fixtures.BudgetReservesTest.result
    create_reserve=fixtures.BudgetReservesTest.create
    item=fixtures.BudgetReservesTest.item
    move=fixtures.BudgetReservesTest.move
    income=forecast_fixtures.CashForecastTest.income
    bill=forecast_fixtures.CashForecastTest.bill
    forecast=forecast_fixtures.CashForecastTest.forecast

    def setUp(self):
        forecast_fixtures.CashForecastTest.setUp(self)
        self.app.register_blueprint(planning_bp,url_prefix='/api/budget/planning')
        for module in ('budget_planning_service','budget_bills_service','routes_budget_workspace'):
            patcher=patch(module+'.date',fixtures.FrozenDate);patcher.start();self.addCleanup(patcher.stop)
        self.planning='/api/budget/planning'

    def get_workspace(self,month='2026-10'):
        return self.result(self.client.get('/api/budget/workspace',query_string={'month':month}))

    def plan(self,reserve,amount=500,**extra):
        data=dict(month='2026-10',amount=amount,priority=1,version=0);data.update(extra)
        return self.client.put(f'{self.planning}/reserve-plans/{reserve}',json=data)

    def policy(self,category=None,**extra):
        data=dict(mode='ROLLOVER',start_month='2026-09',version=0);data.update(extra)
        return self.client.put(f'{self.planning}/category-policies/{category or self.category}',json=data)

    def deferred_limit(self):
        db=get_db()
        db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-09',10000)",(self.category,));db.commit()
        self.expense(30)
        self.result(self.policy(mode='DECIDE'))
        return dict(month='2026-09',request_id=str(uuid4()),category_versions={str(self.category):1},amounts={str(self.category):70})

    def test_closed_savings_decision_survives_switch_to_rollover(self):
        values=self.deferred_limit();values['decisions']={str(self.category):dict(destination='SAVINGS',account_id=self.account)}
        self.result(self.client.post(self.planning+'/close-month',json=values),201)
        self.result(self.policy(mode='ROLLOVER',version=1))
        self.assertEqual(next(c for c in self.get_workspace()['categories'] if c['id']==self.category)['carryover'],0)
        self.assertEqual(get_db().execute('SELECT SUM(amount_cents) FROM budget_reserve_movements').fetchone()[0],7000)

    def test_closed_rollover_decision_survives_switch_to_reset_and_late_expense(self):
        values=self.deferred_limit();values['decisions']={str(self.category):dict(destination='ROLLOVER')}
        self.result(self.client.post(self.planning+'/close-month',json=values),201)
        self.result(self.policy(mode='RESET',start_month='2026-10',version=1))
        self.expense(5)
        self.assertEqual(next(c for c in self.get_workspace()['categories'] if c['id']==self.category)['carryover'],70)

    def test_automatic_rollover_is_also_frozen_when_policy_changes(self):
        values=self.deferred_limit()
        self.result(self.policy(mode='ROLLOVER',version=1))
        values.update(category_versions={},amounts={});values.pop('decisions',None)
        self.result(self.client.post(self.planning+'/close-month',json=values),201)
        self.result(self.policy(mode='RESET',version=2))
        self.assertEqual(next(c for c in self.get_workspace()['categories'] if c['id']==self.category)['carryover'],70)

    def test_migration_preserves_legacy_automatic_closings_and_explicit_choices(self):
        values=self.deferred_limit()
        self.result(self.policy(mode='ROLLOVER',version=1))
        values.update(category_versions={},amounts={})
        self.result(self.client.post(self.planning+'/close-month',json=values),201)
        db=get_db()
        # Before this migration, automatic rollover had only a snapshot, not an item.
        db.execute('DELETE FROM budget_month_closing_items WHERE category_id=?',(self.category,))
        from budget_rollover_service import freeze_legacy_closings
        freeze_legacy_closings(db);freeze_legacy_closings(db);db.commit()
        self.result(self.policy(mode='RESET',version=2))
        self.assertEqual(next(c for c in self.get_workspace()['categories'] if c['id']==self.category)['carryover'],70)

    def test_deferred_choice_is_required_and_rollover_starts_only_after_closing(self):
        values=self.deferred_limit();db=get_db()
        self.assertEqual(next(c for c in self.get_workspace()['categories'] if c['id']==self.category)['carryover'],0)
        self.assertEqual(self.client.post(self.planning+'/close-month',json=values).status_code,400)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_month_closings').fetchone()[0],0)
        values['decisions']={str(self.category):dict(destination='ROLLOVER')}
        self.result(self.client.post(self.planning+'/close-month',json=values),201)
        self.result(self.client.post(self.planning+'/close-month',json=values),201)
        self.assertEqual(next(c for c in self.get_workspace()['categories'] if c['id']==self.category)['carryover'],70)
        self.assertEqual(next(c for c in self.get_workspace('2026-11')['categories'] if c['id']==self.category)['carryover'],0)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],9970)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_reserve_movements').fetchone()[0],0)

    def test_deferred_savings_and_investments_earmark_cash_without_income_or_purchase(self):
        for kind in ('SAVINGS','INVESTMENTS'):
            with self.subTest(kind=kind):
                # Each test instance uses one purpose; clear only its test closing.
                if kind=='INVESTMENTS':
                    db=get_db();db.execute('DELETE FROM budget_month_closing_items');db.execute('DELETE FROM budget_month_closings');db.execute('DELETE FROM budget_month_snapshots');db.execute('DELETE FROM budget_reserve_movements');db.execute('DELETE FROM budget_reserves');db.commit()
                    values=dict(month='2026-09',request_id=str(uuid4()),category_versions={str(self.category):1},amounts={str(self.category):70})
                else: values=self.deferred_limit()
                values['decisions']={str(self.category):dict(destination=kind,account_id=self.account)}
                self.result(self.client.post(self.planning+'/close-month',json=values),201)
                self.result(self.client.post(self.planning+'/close-month',json=values),201)
                db=get_db();reserve=db.execute('SELECT * FROM budget_reserves').fetchone()
                self.assertEqual((reserve['open_ended'],reserve['monthly_amount_cents']),(1,0))
                self.assertEqual(self.item(reserve['id'])['saved'],70)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_reserve_movements').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],9970)

    def test_deferred_existing_reserve_and_reset(self):
        values=self.deferred_limit();reserve=self.create_reserve()
        values['decisions']={str(self.category):dict(destination='RESERVE',reserve_id=reserve)}
        self.result(self.client.post(self.planning+'/close-month',json=values),201)
        self.assertEqual(self.item(reserve)['saved'],70)

    def test_deferred_reset_leaves_cash_free(self):
        values=self.deferred_limit();values['decisions']={str(self.category):dict(destination='RESET')}
        self.result(self.client.post(self.planning+'/close-month',json=values),201)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserve_movements').fetchone()[0],0)
        self.assertEqual(next(c for c in self.get_workspace()['categories'] if c['id']==self.category)['carryover'],0)

    def test_deferred_invalid_and_stale_choices_roll_back_without_new_reserves(self):
        values=self.deferred_limit()
        for choice,status in ((dict(destination='WRONG'),400),(dict(destination='SAVINGS',account_id=999999),404),(dict(destination='RESERVE',reserve_id=999999),400)):
            self.assertEqual(self.client.post(self.planning+'/close-month',json=dict(values,decisions={str(self.category):choice})).status_code,status)
        self.expense(1)
        self.assertEqual(self.client.post(self.planning+'/close-month',json=dict(values,decisions={str(self.category):dict(destination='SAVINGS',account_id=self.account)})).status_code,409)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_month_closings').fetchone()[0],0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserves').fetchone()[0],0)

    def test_deferred_insufficient_cash_rolls_back_generated_purpose(self):
        values=self.deferred_limit();db=get_db()
        db.execute('UPDATE budget_accounts SET balance=1 WHERE id=?',(self.account,));db.commit()
        values['decisions']={str(self.category):dict(destination='INVESTMENTS',account_id=self.account)}
        self.assertEqual(self.client.post(self.planning+'/close-month',json=values).status_code,400)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_reserves').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_month_closings').fetchone()[0],0)

    def purchase(self,**extra):
        data=dict(name='Wakacje',amount=1200,low=900,high=1800,due_date='2026-12-15',account_id=self.account,
                  category_id=self.category,status='PLANNED',notes='',request_id=str(uuid4()));data.update(extra)
        return self.client.post(self.planning+'/purchases',json=data)

    def expense(self,amount,category=None,day='2026-09-20'):
        return self.result(self.client.post('/api/budget/workspace/entries',json=dict(kind='EXPENSE',account_id=self.account,
            amount=amount,date=day,description='Zakupy',lines=[dict(category_id=category or self.category,amount=amount,label='')])),201)['id']

    def test_reserve_plan_is_remaining_commitment_not_a_second_expense(self):
        reserve=self.create_reserve()
        self.result(self.plan(reserve))
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['to_plan'],9500)
        self.result(self.move(reserve,'ADD',200),201)
        totals=monthly_budget_totals(get_db(),'2026-10')
        self.assertEqual((totals['reserved'],totals['reserve_plan_remaining'],totals['to_plan']),(200,300,9500))
        self.result(self.move(reserve,'ADD',400),201)
        totals=monthly_budget_totals(get_db(),'2026-10')
        self.assertEqual((totals['reserve_plan_remaining'],totals['to_plan']),(0,9400))
        self.result(self.move(reserve,'RELEASE',200),201)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['to_plan'],9500)
        self.assertEqual(self.plan(reserve,version=0).status_code,409)
        self.assertEqual(self.plan(reserve,month='2026-09',version=1).status_code,400)
        self.assertEqual(self.plan(reserve,priority=True,version=1).status_code,400)

    def test_forecast_uses_partial_explicit_reserve_plan_and_zero_is_respected(self):
        reserve=self.create_reserve(target_amount=1200,due_date='2027-10-02')
        self.result(self.plan(reserve,amount=500))
        self.result(self.move(reserve,'ADD',100),201)
        forecast=self.forecast()
        self.assertEqual(sum(e['amount'] for e in forecast['events'] if e['kind']=='RESERVE_ADD' and e['date'][:7]=='2026-10'),400)
        self.result(self.plan(reserve,amount=0,version=1))
        self.assertFalse(any(e['kind']=='RESERVE_ADD' and e['date'][:7]=='2026-10' for e in self.forecast()['events']))

    def test_quarterly_yearly_short_months_and_promotional_price(self):
        quarterly=self.bill(frequency='QUARTERLY',due_day=31,amount=50,promotion_end='2027-01-31',regular_amount=80,end_month='2027-04')
        annual=self.bill(title='OC',frequency='YEARLY',due_day=31,amount=300)
        october=self.get_workspace()
        self.assertEqual(len(october['bills']),2)
        self.assertEqual(self.get_workspace('2026-11')['bills'],[])
        self.assertEqual(self.get_workspace('2027-01')['bills'][0]['amount'],50)
        april=self.get_workspace('2027-04')['bills'][0]
        self.assertEqual((april['due_date'],april['amount']),('2027-04-30',80))
        self.assertEqual(self.get_workspace('2027-07')['bills'],[])
        catalog=october['planning']['bill_catalog']
        self.assertEqual(next(b for b in catalog if b['id']==quarterly)['annual_cost'],180)
        self.assertEqual(next(b for b in catalog if b['id']==annual)['annual_cost'],300)

    def test_variable_bill_payment_retry_records_actual_amount_once(self):
        bill=self.bill(variable_amount=True)
        data=dict(month='2026-10',date='2026-10-03',amount=123.45,version=1,request_id=str(uuid4()))
        url=f'/api/budget/workspace/bills/{bill}/pay'
        first=self.result(self.client.post(url,json=data),201)
        self.assertEqual(first,self.result(self.client.post(url,json=data),201))
        self.assertEqual(self.client.post(url,json=dict(data,amount=99)).status_code,409)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],9876.55)
        self.assertEqual(self.get_workspace()['bills'][0]['amount'],123.45)

    def test_linked_bill_reserve_single_cost_and_atomic_payment(self):
        reserve=self.create_reserve(frequency='ONCE',target_amount=600,due_date='2026-10-15')
        self.result(self.move(reserve,'ADD',600),201)
        bill=self.bill(frequency='ONCE',due_month='2026-10',due_day=15,amount=600,reserve_id=reserve)
        forecast=self.forecast()
        self.assertEqual(sum(e['amount'] for e in forecast['events'] if e['kind']=='BILL'),0)
        self.assertEqual(sum(e['amount'] for e in forecast['events'] if e['kind']=='RESERVE_COST'),600)
        self.assertEqual(self.get_workspace()['totals']['planned'],0)
        data=dict(month='2026-10',date='2026-10-03',version=1,reserve_version=2,request_id=str(uuid4()))
        db=get_db()
        db.execute("CREATE TRIGGER fail_payment BEFORE INSERT ON budget_bill_payments_v2 BEGIN SELECT RAISE(ABORT,'failed'); END");db.commit()
        with self.assertRaises(Exception):pay(bill,data)
        self.assertEqual(self.item(reserve)['saved'],600)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        db.execute('DROP TRIGGER fail_payment');db.commit()
        url=f'/api/budget/workspace/bills/{bill}/pay'
        self.result(self.client.post(url,json=data),201);self.result(self.client.post(url,json=data),201)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],9400)
        totals=self.get_workspace()['totals']
        self.assertEqual((totals['budget_spent'],totals['reserve_settled']),(600,600))

    def test_rollover_shared_parent_uses_children_once_and_never_changes_cash(self):
        db=get_db();child=db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES('Paliwo',?)",(self.category,)).lastrowid
        db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-09',100000)",(self.category,))
        db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-09',60000)",(child,))
        db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-10',100000)",(self.category,));db.commit()
        self.expense(300,child);self.expense(100)
        self.result(self.policy())
        self.assertEqual(self.policy(child).status_code,400)
        row=next(c for c in category_workspace(db,'2026-10') if c['id']==self.category)
        self.assertEqual((row['carryover'],row['planned']),(600,1600))
        before=db.total_changes;self.get_workspace();self.forecast()
        self.assertEqual(before,db.total_changes)
        self.expense(800)
        self.assertEqual(next(c for c in category_workspace(db,'2026-10') if c['id']==self.category)['carryover'],0)

    def test_bill_due_this_month_and_reserve_plan_do_not_duplicate_commitment(self):
        reserve=self.create_reserve(frequency='ONCE',target_amount=600,due_date='2026-10-15')
        self.result(self.move(reserve,'ADD',200),201)
        self.bill(frequency='ONCE',due_month='2026-10',due_day=15,amount=600,reserve_id=reserve)
        self.result(self.plan(reserve,amount=600))
        totals=self.get_workspace()['totals']
        self.assertEqual((totals['planned'],totals['reserve_plan_remaining'],totals['reserve_plan_extra'],totals['to_plan']),(400,400,0,9400))
        self.result(self.move(reserve,'ADD',400),201)
        self.assertEqual(self.get_workspace()['totals']['to_plan'],9400)

    def test_annual_bill_anchor_survives_reserve_next_cycle(self):
        reserve=self.create_reserve(target_amount=600,due_date='2026-10-15')
        bill=self.bill(frequency='YEARLY',start_month='2026-10',due_day=15,amount=600,reserve_id=reserve)
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03',version=1,reserve_version=1)),201)
        self.assertEqual(self.item(reserve)['due_date'],'2027-10-15')
        self.result(self.client.put(f'/api/budget/workspace/bills/{bill}',json=dict(title='OC',account_id=self.account,
            category_id=self.category,amount=600,due_day=15,frequency='YEARLY',start_month='2026-10',reserve_id=reserve,version=2)))
        row=self.item(reserve)
        self.assertEqual(self.client.put(f'{self.base}/{reserve}',json=dict(name='OC',notes='',account_id=self.account,
            target_amount=700,due_date=row['due_date'],frequency='YEARLY',version=row['version'])).status_code,400)

    def test_explicit_reserve_payment_settles_linked_bill_without_second_expense(self):
        reserve=self.create_reserve(frequency='ONCE',target_amount=600,due_date='2026-10-15')
        self.bill(frequency='ONCE',due_month='2026-10',due_day=15,amount=600,reserve_id=reserve)
        self.result(self.move(reserve,'SPEND',600),201)
        self.assertEqual(self.get_workspace()['bills'][0]['status'],'PAID')
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)

    def test_month_close_preview_conflict_idempotence_and_current_month_rejected(self):
        reserve=self.create_reserve()
        db=get_db();db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-09',10000)",(self.category,));db.commit()
        self.result(self.policy(mode='RESERVE',reserve_id=reserve))
        values=dict(month='2026-09',category_versions={str(self.category):1},amounts={str(self.category):100},request_id=str(uuid4()))
        url=self.planning+'/close-month'
        self.assertEqual(self.client.post(url,json=dict(values,amounts={str(self.category):101})).status_code,409)
        first=self.result(self.client.post(url,json=values),201)
        self.assertEqual(first,self.result(self.client.post(url,json=values),201))
        self.assertEqual(self.item(reserve)['saved'],100)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(self.client.post(url,json=dict(values,request_id=str(uuid4()))).status_code,400)
        self.assertEqual(self.client.post(url,json=dict(values,month='2026-10')).status_code,400)

    def test_month_close_insufficient_money_rolls_back_all_categories(self):
        first=self.create_reserve();second=self.create_reserve(name='Mieszkanie')
        db=get_db();other=db.execute("INSERT INTO budget_categories_v2(name) VALUES('Dom')").lastrowid
        for c in (self.category,other):db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-09',600000)",(c,))
        db.commit()
        self.result(self.policy(mode='RESERVE',reserve_id=first))
        self.result(self.policy(other,mode='RESERVE',reserve_id=second))
        response=self.client.post(self.planning+'/close-month',json=dict(month='2026-09',request_id=str(uuid4()),
            category_versions={str(self.category):1,str(other):1},amounts={str(self.category):6000,str(other):6000}))
        self.assertEqual(response.status_code,400,response.json)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_month_closings').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_reserve_movements').fetchone()[0],0)

    def test_purchase_states_retry_and_read_only_cost_simulation(self):
        token=str(uuid4());purchase=self.result(self.purchase(request_id=token),201)['id']
        self.assertEqual(purchase,self.result(self.purchase(request_id=token),201)['id'])
        self.result(self.purchase(status='IDEA',name='Laptop'),201)
        db=get_db();self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_reserves').fetchone()[0],1)
        before=db.total_changes
        simulation=self.forecast(purchase_id=purchase,purchase_amount=900,purchase_date='2027-01-15')
        costs=[e for e in simulation['events'] if e['kind']=='RESERVE_COST']
        self.assertEqual([(e['amount'],e['date']) for e in costs],[(900,'2027-01-15')])
        self.assertEqual(before,db.total_changes)
        row=db.execute('SELECT * FROM budget_purchase_plans WHERE id=?',(purchase,)).fetchone()
        self.assertEqual((row['amount_cents'],row['due_date']),(120000,'2026-12-15'))
        self.assertEqual(self.client.get(self.url,query_string={'purchase_id':purchase,'purchase_amount':'NaN'}).status_code,400)

    def test_purchase_reserve_version_and_funded_cancellation_guard(self):
        purchase=self.result(self.purchase(),201)['id']
        row=self.get_workspace()['planning']['purchases'][0]
        self.result(self.move(row['reserve_id'],'ADD',100),201)
        data=dict(name='Wakacje',amount=1200,low=900,high=1800,due_date='2026-12-15',account_id=self.account,
                  category_id=self.category,status='CANCELLED',notes='',version=1,reserve_version=1)
        self.assertEqual(self.client.put(f'{self.planning}/purchases/{purchase}',json=data).status_code,409)
        self.assertEqual(self.client.put(f'{self.planning}/purchases/{purchase}',json=dict(data,reserve_version=2)).status_code,400)
        self.result(self.move(row['reserve_id'],'RELEASE',100),201)
        self.result(self.client.put(f'{self.planning}/purchases/{purchase}',json=dict(data,reserve_version=3)))
        self.assertFalse(any(e['kind']=='RESERVE_COST' for e in self.forecast()['events']))

    def test_paycycle_clamps_month_end_and_accounts_sum_to_global_forecast(self):
        income=self.income()
        db=get_db();second=db.execute("INSERT INTO budget_accounts(name,balance,currency) VALUES('Drugi',100,'PLN')").lastrowid;db.commit()
        self.result(self.client.put(self.planning+'/settings',json=dict(pay_day=31,income_id=income,spending_account_id=second,loan_account_id=second,version=1)))
        cycle=self.get_workspace('2027-02')['planning']['cycle']
        self.assertEqual((cycle['start'],cycle['end']),('2027-02-28','2027-03-30'))
        self.bill(account_id=second,amount=200)
        data=self.forecast(variable_monthly=300)
        for i,point in enumerate(data['points']):
            for field in ('balance','reserved','available'):
                self.assertAlmostEqual(sum(a['points'][i][field] for a in data['account_forecasts']),point[field],places=2)
        target=next(a for a in data['account_forecasts'] if a['id']==second)
        self.assertLess(target['summaries'][0]['minimum'],0)
        self.assertEqual(data['transfer_suggestions'][0]['target_account_id'],second)
        self.assertGreater(data['summaries'][0]['balance'],0)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(second,)).fetchone()[0],100)

    def test_transfer_suggestion_does_not_use_donor_earmarked_money(self):
        reserve=self.create_reserve(target_amount=10000,due_date='2028-10-02')
        self.result(self.move(reserve,'ADD',9990),201)
        db=get_db();second=db.execute("INSERT INTO budget_accounts(name,balance,currency) VALUES('Drugi',100,'PLN')").lastrowid;db.commit()
        self.bill(account_id=second,amount=200)
        forecast=self.forecast()
        self.assertLessEqual(sum(s['amount'] for s in forecast['transfer_suggestions']),10)
        self.assertTrue(any('którego nie pokrywają' in w for w in forecast['warnings']))


if __name__=='__main__':unittest.main()
