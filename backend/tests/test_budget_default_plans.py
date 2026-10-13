import unittest
from unittest.mock import patch
from uuid import uuid4
from database import get_db, reset_budget_data
from tests import test_budget_planning as fixtures
from tests.test_budget_reserves import FrozenDate
from budget_default_plan_service import resolve


class DefaultPlansTest(unittest.TestCase):
    result=fixtures.BudgetPlanningTest.result
    get_workspace=fixtures.BudgetPlanningTest.get_workspace
    bill=fixtures.BudgetPlanningTest.bill
    forecast=fixtures.BudgetPlanningTest.forecast
    create_reserve=fixtures.BudgetPlanningTest.create_reserve

    def setUp(self):
        fixtures.BudgetPlanningTest.setUp(self)
        patcher=patch('budget_default_plan_service.date',FrozenDate);patcher.start();self.addCleanup(patcher.stop)
        self.url='/api/budget/workspace/plans'
        db=get_db()
        self.other=db.execute("INSERT INTO budget_categories_v2(name) VALUES('Jedzenie')").lastrowid
        db.commit()

    def save(self,category,amount,start='2026-10',**extra):
        record=next(r for r in self.result(self.client.get(self.url+'/defaults?month='+start))['items'] if r['category_id']==category)
        return self.client.put(self.url+'/defaults',json=dict(start_month=start,items=[dict(category_id=category,amount=amount,revision=record['revision'])],**extra))

    def test_dated_defaults_monthly_zero_and_reset_are_shared_with_forecast(self):
        self.result(self.save(self.category,500))
        self.result(self.save(self.other,1000))
        self.result(self.save(self.other,1100,'2027-01'))
        db=get_db()
        db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-12',0)",(self.other,));db.commit()
        self.assertEqual(resolve(db,'2026-09')[0],{})
        self.assertEqual(resolve(db,'2026-11')[0],{self.category:50000,self.other:100000})
        self.assertEqual(resolve(db,'2026-12')[0][self.other],0)
        self.assertEqual(resolve(db,'2027-01')[0][self.other],110000)
        november=self.get_workspace('2026-11')
        self.assertEqual(november['totals']['planned'],1500)
        self.assertEqual(next(c for c in november['categories'] if c['id']==self.other)['plan_source'],'DEFAULT')
        rows={r['month']:r for r in self.forecast()['month_plans']}
        self.assertEqual([rows[m]['ordinary_limit'] for m in ('2026-11','2026-12','2027-01')],[1500,500,1600])
        self.result(self.client.delete(self.url+f'/{self.other}?month=2026-12'))
        self.assertEqual(resolve(db,'2026-12')[0][self.other],100000)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)

    def test_partial_future_plan_inherits_each_missing_category_and_labels_estimates(self):
        db=get_db()
        db.executemany('INSERT INTO budget_plans_v2 VALUES(?,?,?)',[(self.category,'2026-10',50000),(self.other,'2026-10',100000),(self.category,'2026-11',20000),(self.category,'2026-12',0)])
        db.commit()
        rows={r['month']:r for r in self.forecast()['month_plans']}
        self.assertEqual(rows['2026-11']['ordinary_limit'],1200)
        self.assertEqual(rows['2026-12']['ordinary_limit'],1000)
        food=next(c for c in rows['2026-11']['categories'] if c['category_id']==self.other)
        self.assertEqual((food['source'],food['source_month']),('ESTIMATE','2026-10'))
        self.assertEqual(self.get_workspace('2026-11')['totals']['planned'],200)

    def test_recurring_bills_once_bills_and_default_cap_are_never_summed_twice(self):
        self.result(self.save(self.category,1000))
        self.bill(amount=250)
        self.bill(title='Jednorazowy',frequency='ONCE',due_month='2026-10',amount=100)
        forecast=self.forecast()
        rows={r['month']:r for r in forecast['month_plans']}
        self.assertEqual((rows['2026-10']['ordinary_limit'],rows['2026-10']['bills']),(650,350))
        self.assertEqual((rows['2026-11']['ordinary_limit'],rows['2026-11']['bills']),(750,250))
        self.assertEqual(self.get_workspace('2026-11')['totals']['planned'],1000)

    def test_old_child_estimate_cannot_raise_a_real_future_shared_cap(self):
        db=get_db()
        child=db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES('Podkategoria',?)",(self.category,)).lastrowid
        db.executemany('INSERT INTO budget_plans_v2 VALUES(?,?,?)',[(self.category,'2026-10',45000),(child,'2026-10',30000),
            (self.other,'2026-10',50000),(self.category,'2026-11',20000)])
        db.commit()
        november=next(r for r in self.forecast()['month_plans'] if r['month']=='2026-11')
        self.assertEqual(november['ordinary_limit'],700)
        self.assertEqual(next(c for c in november['categories'] if c['category_id']==child)['source'],'NONE')
        # A deliberately configured child default is a real plan, unlike a guess.
        self.result(self.save(child,300))
        november=next(r for r in self.forecast()['month_plans'] if r['month']=='2026-11')
        self.assertEqual(november['ordinary_limit'],800)

    def test_range_copy_reviews_and_preserves_existing_zero_and_retries_once(self):
        self.result(self.save(self.category,500))
        db=get_db();db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-12',0)",(self.category,));db.commit()
        values=dict(source='2026-10',start='2026-11',months=12,replace=False,category_ids=[self.category])
        preview=self.result(self.client.post(self.url+'/copy-preview',json=values))
        self.assertEqual((preview['copied'],preview['skipped']),(11,1))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_plans_v2').fetchone()[0],1)
        request={**values,'token':preview['token'],'request_id':str(uuid4())}
        expected=self.result(self.client.post(self.url+'/copy-range',json=request))
        self.assertEqual(expected,self.result(self.client.post(self.url+'/copy-range',json=request)))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_plans_v2').fetchone()[0],12)
        self.assertEqual(resolve(db,'2026-12')[0][self.category],0)
        self.assertEqual(resolve(db,'2027-10')[0][self.category],50000)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)

    def test_changed_preview_rejected_atomically_and_explicit_replace_supported(self):
        self.result(self.save(self.category,500))
        values=dict(source='2026-10',start='2026-11',months=3,replace=True,category_ids=[self.category])
        preview=self.result(self.client.post(self.url+'/copy-preview',json=values))
        db=get_db();db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-12',20000)",(self.category,));db.commit()
        stale={**values,'token':preview['token'],'request_id':str(uuid4())}
        self.assertEqual(self.client.post(self.url+'/copy-range',json=stale).status_code,409)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_plans_v2').fetchone()[0],1)
        preview=self.result(self.client.post(self.url+'/copy-preview',json=values))
        self.assertIn('REPLACE',[r['action'] for r in preview['rows']])
        self.result(self.client.post(self.url+'/copy-range',json={**values,'token':preview['token'],'request_id':str(uuid4())}))
        self.assertEqual(resolve(db,'2026-12')[0][self.category],50000)

    def test_stale_default_and_past_start_are_rejected(self):
        record=next(r for r in self.result(self.client.get(self.url+'/defaults?month=2026-10'))['items'] if r['category_id']==self.category)
        self.result(self.save(self.category,500))
        stale=dict(start_month='2026-11',items=[dict(category_id=self.category,amount=900,revision=record['revision'])])
        self.assertEqual(self.client.put(self.url+'/defaults',json=stale).status_code,409)
        self.assertEqual(self.save(self.category,500,'2026-09').status_code,400)
        self.assertEqual(resolve(get_db(),'2026-11')[0][self.category],50000)

    def test_invalid_second_default_rolls_back_the_entire_save(self):
        rows=self.result(self.client.get(self.url+'/defaults?month=2026-10'))['items']
        first=next(r for r in rows if r['category_id']==self.category)
        values=dict(start_month='2026-10',items=[dict(category_id=self.category,amount=100,revision=first['revision']),
            dict(category_id=self.other,amount=200,revision='stale')])
        self.assertEqual(self.client.put(self.url+'/defaults',json=values).status_code,409)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_default_plans').fetchone()[0],0)

    def test_monthly_media_are_not_copied_or_given_an_extra_default(self):
        self.create_reserve(name='Prąd',monthly_amount=250,category_id=self.category)
        self.assertEqual(self.save(self.category,800).status_code,400)
        db=get_db();db.execute("INSERT INTO budget_plans_v2 VALUES(?,'2026-10',80000)",(self.category,));db.commit()
        values=dict(source='2026-10',start='2026-11',months=3,replace=False,category_ids=[self.category])
        preview=self.result(self.client.post(self.url+'/copy-preview',json=values))
        self.assertEqual((preview['copied'],preview['skipped']),(0,3))
        self.assertTrue(all(r['action']=='MANAGED' for r in preview['rows']))
        november=next(r for r in self.forecast()['month_plans'] if r['month']=='2026-11')
        self.assertEqual((november['ordinary_limit'],november['reserves']),(0,250))

    def test_closed_months_cannot_be_replanned_by_a_new_default(self):
        db=get_db()
        db.execute("INSERT INTO budget_month_closings(month,request_id,request_payload,created_at) VALUES('2026-10',?,'{}','2026-10-03')",(str(uuid4()),));db.commit()
        self.assertEqual(self.save(self.category,500).status_code,400)
        self.result(self.save(self.category,500,'2026-11'))
        self.assertEqual(resolve(db,'2026-10')[0],{})

    def test_rollover_uses_default_and_saved_decision_remains_frozen(self):
        self.result(self.save(self.category,100))
        db=get_db();db.execute("INSERT INTO budget_category_policies(category_id,mode,start_month) VALUES(?,'ROLLOVER','2026-10')",(self.category,));db.commit()
        category=next(c for c in self.get_workspace('2026-11')['categories'] if c['id']==self.category)
        self.assertEqual((category['manual_plan'],category['carryover'],category['planned']),(100,100,200))

    def test_reset_clears_new_settings_and_requests(self):
        self.result(self.save(self.category,100))
        db=get_db();reset_budget_data();db.commit()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_default_plans').fetchone()[0],0)
