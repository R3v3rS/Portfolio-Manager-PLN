import unittest
from datetime import date
from uuid import uuid4

from tests import test_budget_workspace as workspace_tests
from api.exceptions import ApiError
from api.response import error_response
from database import get_db
from budget_category_hierarchy_service import category_workspace
from budget_category_service import save_rule, rules
from monthly_report_service import _budget


class BudgetSubcategoriesTest(unittest.TestCase):
    payload = workspace_tests.BudgetWorkspaceTest.payload
    setup_account = workspace_tests.BudgetWorkspaceTest.setup_account

    def setUp(self):
        workspace_tests.BudgetWorkspaceTest.setUp(self)
        self.app.register_error_handler(ApiError, lambda e: error_response(e.code, e.message, status=e.status))
        self.account, cats = self.setup_account()
        self.transport = cats['Transport']
        self.fuel = self.child('Paliwo')
        self.tickets = self.child('Bilety')

    def child(self, name, parent=None):
        return self.payload(self.client.post(self.base+'/categories', json={
            'name': name, 'parent_id': self.transport if parent is None else parent}), 201)['id']

    def plan(self, category_id, amount):
        self.payload(self.client.put(self.base+f'/plans/{category_id}', json={'month':'2026-09','amount':amount}))

    def expense(self, category_id, amount, day='2026-09-10'):
        return self.payload(self.client.post(self.base+'/entries', json=dict(account_id=self.account, kind='EXPENSE',
            amount=amount,date=day,description='Transport',lines=[dict(category_id=category_id,amount=amount)])),201)['id']

    def snapshot(self):
        return self.payload(self.client.get(self.base+'?month=2026-09'))

    def test_parent_spending_contains_general_and_children_once(self):
        self.plan(self.transport,1000); self.plan(self.fuel,600); self.plan(self.tickets,100)
        self.expense(self.transport,25); self.expense(self.fuel,200); self.expense(self.tickets,30)
        data=self.snapshot(); rows={c['id']:c for c in data['categories']}
        self.assertEqual(rows[self.transport]['spent'],255)
        self.assertEqual(rows[self.transport]['direct_spent'],25)
        self.assertEqual(rows[self.fuel]['spent'],200)
        self.assertEqual(rows[self.fuel]['selection_label'],'Transport › Paliwo')
        self.assertEqual(rows[self.transport]['selection_label'],'Transport › Ogólnie')
        self.assertEqual(data['totals']['planned'],1000)
        self.assertEqual(data['totals']['spent'],255)
        self.assertEqual(data['totals']['balance'],745)
        self.assertEqual(rows[self.transport]['remaining'],745)

    def test_children_exceed_shared_cap_and_root_bills_raise_plan(self):
        self.plan(self.transport,500); self.plan(self.fuel,600); self.plan(self.tickets,100)
        self.payload(self.client.post(self.base+'/bills',json=dict(title='Parking',account_id=self.account,
            category_id=self.transport,amount=50,due_day=20,frequency='ONCE',due_month='2026-09')),201)
        self.payload(self.client.post(self.base+'/bills',json=dict(title='Bilet miesięczny',account_id=self.account,
            category_id=self.tickets,amount=120,due_day=20,frequency='ONCE',due_month='2026-09')),201)
        data=self.snapshot();rows={c['id']:c for c in data['categories']}
        self.assertEqual(data['totals']['planned'],770)
        self.assertEqual(rows[self.transport]['planned_bills'],170)
        self.assertEqual(rows[self.transport]['children_plan'],720)
        self.assertEqual(rows[self.tickets]['planned'],120)

    def test_report_partial_period_and_root_plan_do_not_double_count(self):
        self.plan(self.transport,1000);self.plan(self.fuel,600)
        self.expense(self.fuel,12.34,'2026-09-02');self.expense(self.tickets,56.78,'2026-09-25')
        with self.app.app_context():
            report=_budget(get_db(),date(2026,9,1),date(2026,9,10))
        self.assertEqual(report['planned'],1000)
        self.assertEqual(report['expenses'],12.34)
        rows={c['id']:c for c in report['categories']}
        self.assertEqual(rows[self.transport]['spent'],12.34)
        self.assertEqual(rows[self.fuel]['spent'],12.34)

    def test_parent_change_preserves_entries_plans_and_rule_target(self):
        self.expense(self.fuel,100);self.plan(self.fuel,200)
        with self.app.app_context():
            rule=save_rule(dict(pattern='ORLEN',category_id=self.fuel,request_id=str(uuid4())))
        other=self.payload(self.client.post(self.base+'/categories',json={'name':'Samochód'}),201)['id']
        self.payload(self.client.put(self.base+f'/categories/{self.fuel}',json=dict(name='Tankowanie',parent_id=other,version=1)))
        data=self.snapshot();rows={c['id']:c for c in data['categories']}
        self.assertEqual(rows[self.transport]['spent'],0);self.assertEqual(rows[other]['spent'],100)
        self.assertEqual(rows[self.fuel]['manual_plan'],200)
        self.assertEqual(data['totals']['spent'],100);self.assertEqual(data['totals']['balance'],900)
        with self.app.app_context():
            target=next(r for r in rules(get_db()) if r['id']==rule['id'])
            self.assertEqual(target['category_id'],self.fuel)
            self.assertEqual(target['category_name'],'Samochód › Tankowanie')

    def test_invalid_hierarchy_and_stale_edit_leave_data_unchanged(self):
        for parent in (self.fuel,self.transport):
            response=self.client.put(self.base+f'/categories/{self.transport}',json=dict(name='Transport',parent_id=parent,version=1))
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.client.post(self.base+'/categories',json={'name':'Trzeci poziom','parent_id':self.fuel}).status_code,400)
        self.assertEqual(self.client.post(self.base+'/categories',json={'name':'Bad','parent_id':True}).status_code,400)
        self.assertEqual(self.client.post(self.base+'/categories',json={'name':'Bad','parent_id':999999}).status_code,404)
        self.payload(self.client.put(self.base+f'/categories/{self.fuel}',json=dict(name='Paliwo nowe',parent_id=self.transport,version=1)))
        self.assertEqual(self.client.put(self.base+f'/categories/{self.fuel}',json=dict(name='Stare',parent_id=None,version=1)).status_code,409)
        self.assertEqual(next(c for c in self.snapshot()['categories'] if c['id']==self.fuel)['name'],'Paliwo nowe')

    def test_copy_preserves_caps_and_tree_order(self):
        self.plan(self.transport,1000);self.plan(self.fuel,600)
        self.payload(self.client.post(self.base+'/plans/copy',json={'source':'2026-09','target':'2026-10'}))
        data=self.payload(self.client.get(self.base+'?month=2026-10'))
        self.assertEqual(data['totals']['planned'],1000)
        ids=[c['id'] for c in data['categories']]
        self.assertEqual(ids[ids.index(self.transport)+1:ids.index(self.transport)+3],[self.fuel,self.tickets])

    def test_reading_hierarchy_does_not_mutate_cash_or_categories(self):
        with self.app.app_context():
            db=get_db(); before=db.total_changes
            category_workspace(db,'2026-09');category_workspace(db,'2026-09')
            self.assertEqual(db.total_changes,before)


if __name__=='__main__':
    unittest.main()
