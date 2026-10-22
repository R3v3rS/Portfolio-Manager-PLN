import unittest
from uuid import uuid4
from unittest.mock import patch
from database import get_db
from tests import test_budget_planning as planning_tests
from tests.test_budget_reserves import FrozenDate


class BudgetUsabilityTest(unittest.TestCase):
    setUp = planning_tests.BudgetPlanningTest.setUp
    result = planning_tests.BudgetPlanningTest.result
    get_workspace = planning_tests.BudgetPlanningTest.get_workspace
    expense = planning_tests.BudgetPlanningTest.expense
    income = planning_tests.BudgetPlanningTest.income
    bill = planning_tests.BudgetPlanningTest.bill

    def prepare(self, source=500, target=100):
        db = get_db()
        other = db.execute("INSERT INTO budget_categories_v2(name) VALUES('Druga kategoria')").lastrowid
        for category, amount in ((self.category, source), (other, target)):
            db.execute('INSERT INTO budget_plans_v2 VALUES(?,?,?)', (category, '2026-10', amount*100))
        db.commit()
        return dict(month='2026-10', source_id=self.category, target_id=other, amount=50)

    def preview(self, data):
        return self.client.post('/api/budget/workspace/plans/transfer-preview', json=data)

    def transfer(self, data, token, request_id=None):
        return self.client.post('/api/budget/workspace/plans/transfer', json={**data, 'token': token, 'request_id': request_id or str(uuid4())})

    def test_transfer_keeps_total_cash_and_history_and_is_idempotent(self):
        data = self.prepare()
        before = self.get_workspace()
        db = get_db(); changes = db.total_changes
        view = self.result(self.preview(data))
        self.assertEqual(db.total_changes, changes)
        self.assertEqual((view['source_after'], view['target_after'], view['total_after']), (450, 150, 600))
        request_id = str(uuid4())
        first = self.result(self.transfer(data, view['token'], request_id))
        self.assertEqual(self.result(self.transfer(data, view['token'], request_id)), first)
        after = self.get_workspace()
        self.assertEqual(after['accounts'], before['accounts'])
        self.assertEqual(after['entries'], before['entries'])
        self.assertEqual(after['totals']['planned'], before['totals']['planned'])
        self.assertEqual(after['totals']['to_plan'], before['totals']['to_plan'])
        self.assertEqual(self.transfer({**data, 'amount':60}, view['token'], request_id).status_code, 409)

    def test_stale_spending_preview_does_not_change_any_limit(self):
        data = self.prepare()
        view = self.result(self.preview(data))
        self.expense(10, day='2026-10-03')
        before = [tuple(row) for row in get_db().execute('SELECT * FROM budget_plans_v2')]
        self.assertEqual(self.transfer(data, view['token']).status_code, 409)
        self.assertEqual([tuple(row) for row in get_db().execute('SELECT * FROM budget_plans_v2')], before)

    def test_cannot_move_spent_or_committed_money(self):
        data = self.prepare(source=150)
        self.bill(amount=100)
        self.expense(10, day='2026-10-03')
        self.assertEqual(self.preview({**data, 'amount':41}).status_code, 400)
        self.result(self.preview({**data, 'amount':40}))

    def test_shared_parent_cap_cannot_produce_a_phantom_transfer(self):
        data = self.prepare(source=300)
        db = get_db()
        child = db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES('Podkategoria',?)", (self.category,)).lastrowid
        db.execute('INSERT INTO budget_plans_v2 VALUES(?,?,?)', (child,'2026-10',20000));db.commit()
        child_data = {**data, 'source_id':child}
        view = self.result(self.preview(child_data))
        self.assertEqual(view['related_limits'], [dict(name='Ubezpieczenia',before=300,after=250)])
        self.result(self.transfer(child_data, view['token']))
        self.assertEqual(get_db().execute('SELECT amount_cents FROM budget_plans_v2 WHERE category_id=?', (child,)).fetchone()[0], 15000)
        # Moving the root's unallocated allowance preserves the child's new limit.
        view = self.result(self.preview(data))
        self.result(self.transfer(data, view['token']))
        self.assertEqual(get_db().execute('SELECT amount_cents FROM budget_plans_v2 WHERE category_id=?', (child,)).fetchone()[0], 15000)

    def test_moves_between_two_children_and_updates_both_shared_caps(self):
        data = self.prepare(source=300)
        db = get_db()
        source = db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES('Źródło',?)", (self.category,)).lastrowid
        target = db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES('Cel',?)", (data['target_id'],)).lastrowid
        for child, amount in ((source,20000),(target,4000)):
            db.execute('INSERT INTO budget_plans_v2 VALUES(?,?,?)', (child,'2026-10',amount))
        db.commit()
        data = {**data, 'source_id':source, 'target_id':target}
        view = self.result(self.preview(data))
        self.assertEqual(len(view['updates']), 4)
        self.result(self.transfer(data, view['token']))
        categories = {row['id']:row for row in self.get_workspace()['categories']}
        self.assertEqual((categories[source]['planned'],categories[target]['planned']), (150,90))
        self.assertEqual((categories[self.category]['planned'],categories[categories[target]['parent_id']]['planned']), (250,150))

    def test_moves_within_a_shared_parent_without_counting_it_twice(self):
        data = self.prepare(source=300)
        db = get_db()
        children = []
        for name, amount in (('A',20000),('B',10000)):
            child = db.execute('INSERT INTO budget_categories_v2(name,parent_id) VALUES(?,?)', (name,self.category)).lastrowid
            db.execute('INSERT INTO budget_plans_v2 VALUES(?,?,?)', (child,'2026-10',amount));children.append(child)
        db.commit()
        data = {**data,'source_id':children[0],'target_id':children[1]}
        self.expense(100,category=children[0],day='2026-10-03')
        self.expense(200,category=children[1],day='2026-10-03')
        view = self.result(self.preview(data))
        self.assertEqual((view['total_before'],view['total_after']), (400,400))
        self.result(self.transfer(data, view['token']))
        categories = {row['id']:row for row in self.get_workspace()['categories']}
        self.assertEqual(categories[self.category]['planned'],300)
        self.assertEqual([categories[child]['planned'] for child in children], [150,150])

    def test_child_transfer_also_protects_the_parents_spent_money(self):
        data = self.prepare(source=300)
        db = get_db()
        child = db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES('Podkategoria',?)", (self.category,)).lastrowid
        db.execute('INSERT INTO budget_plans_v2 VALUES(?,?,?)', (child,'2026-10',20000));db.commit()
        self.expense(180,day='2026-10-03')
        self.assertEqual(self.preview({**data,'source_id':child,'amount':130}).status_code,400)

    def test_failure_rolls_back_child_and_shared_parent_changes(self):
        data = self.prepare(source=300)
        db = get_db()
        child = db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES('Podkategoria',?)", (self.category,)).lastrowid
        db.execute('INSERT INTO budget_plans_v2 VALUES(?,?,?)', (child,'2026-10',20000));db.commit()
        data = {**data,'source_id':child}
        view = self.result(self.preview(data))
        db.execute("CREATE TRIGGER fail_transfer BEFORE INSERT ON budget_plan_transfer_requests BEGIN SELECT RAISE(ABORT,'injected'); END");db.commit()
        before = [tuple(row) for row in db.execute('SELECT * FROM budget_plans_v2')]
        with self.assertRaises(Exception): self.transfer(data,view['token'])
        self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM budget_plans_v2')],before)

    def test_failure_of_request_record_rolls_back_both_changes(self):
        data = self.prepare(); view = self.result(self.preview(data))
        db = get_db()
        db.execute("CREATE TRIGGER fail_transfer BEFORE INSERT ON budget_plan_transfer_requests BEGIN SELECT RAISE(ABORT,'injected'); END");db.commit()
        before = [tuple(r) for r in db.execute('SELECT * FROM budget_plans_v2')]
        with self.assertRaises(Exception): self.transfer(data, view['token'])
        self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM budget_plans_v2')], before)

    def test_year_plan_has_twelve_months_and_is_read_only(self):
        self.prepare(); self.bill(amount=100); self.income(amount=1000)
        db = get_db(); before = db.total_changes
        year = self.result(self.client.get('/api/budget/workspace/plans/year?start=2026-10'))
        self.assertEqual(len(year['months']), 12)
        self.assertEqual((year['months'][0]['month'], year['months'][-1]['month']), ('2026-10', '2027-09'))
        self.assertEqual(year['months'][0]['ordinary'], 500)
        self.assertEqual(year['months'][0]['payments'], 100)
        self.assertEqual(year['months'][0]['cost'], 600)
        self.assertEqual(db.total_changes, before)
        self.assertFalse(db.in_transaction)

    def test_past_closed_range_cannot_be_edited(self):
        data = self.prepare()
        with patch('budget_default_plan_service.date', FrozenDate):
            self.assertEqual(self.preview({**data, 'month':'2026-09'}).status_code, 400)
