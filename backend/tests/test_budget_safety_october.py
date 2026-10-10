"""Budget audit regressions, using temporary databases only."""
import unittest
from uuid import uuid4

from api.exceptions import ValidationError
from database import get_db
from tests import test_budget_planning as fixtures
from budget_category_service import categorize
from budget_transfer_service import transfer_investment_cash


class BudgetSafetyOctoberTest(unittest.TestCase):
    setUp=fixtures.BudgetPlanningTest.setUp
    result=fixtures.BudgetPlanningTest.result
    get_workspace=fixtures.BudgetPlanningTest.get_workspace
    expense=fixtures.BudgetPlanningTest.expense
    forecast=fixtures.BudgetPlanningTest.forecast
    bill=fixtures.BudgetPlanningTest.bill
    create_reserve=fixtures.BudgetPlanningTest.create_reserve
    item=fixtures.BudgetPlanningTest.item
    move=fixtures.BudgetPlanningTest.move

    def add_category(self,name,limit=0):
        db=get_db()
        ident=db.execute('INSERT INTO budget_categories_v2(name) VALUES(?)',(name,)).lastrowid
        if limit:db.execute("INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,'2026-10',?)",(ident,limit*100))
        db.commit();return ident

    def daily_left(self,**options):
        return round(sum(e['amount'] for e in self.forecast(**options)['events'] if e['kind']=='DAILY' and e['date'][:7]=='2026-10'),2)

    def test_unplanned_purchase_does_not_spend_another_category_allowance(self):
        self.add_category('Jedzenie',300)
        self.expense(100,day='2026-10-03')
        self.assertEqual(self.daily_left(),300)
        self.assertEqual(self.get_workspace()['totals']['remaining_commitments'],300)
        end=next(p for p in self.forecast()['points'] if p['date']=='2026-10-31')
        self.assertEqual(end['available'],9600)
        # A user-entered scenario deliberately replaces category limits.
        self.assertEqual(self.daily_left(variable_monthly=300),200)

    def test_category_overrun_does_not_reduce_other_root_or_future_allowance(self):
        overspent=self.add_category('Rozrywka',300)
        self.add_category('Jedzenie',200)
        self.expense(400,category=overspent,day='2026-10-03')
        self.assertEqual(self.daily_left(),200)
        november=[e for e in self.forecast()['events'] if e['kind']=='DAILY' and e['date'][:7]=='2026-11']
        self.assertEqual(round(sum(e['amount'] for e in november),2),500)

    def test_media_purchase_does_not_reduce_food_plan(self):
        self.add_category('Jedzenie',300)
        self.create_reserve(name='Prąd',monthly_amount=250,category_id=self.category)
        self.expense(180,day='2026-10-03')
        self.assertEqual(self.daily_left(),300)
        reserves=[e for e in self.forecast()['events'] if e['kind']=='RESERVE_ADD' and e['date'][:7]=='2026-10']
        self.assertEqual(round(sum(e['amount'] for e in reserves),2),70)

    def test_refund_in_unplanned_category_does_not_raise_food_allowance(self):
        self.add_category('Jedzenie',300)
        purchase=self.expense(100,day='2026-10-03')
        self.result(self.client.post(f'/api/budget/workspace/entries/{purchase}/refunds',json=dict(
            version=1,amount=100,date='2026-10-03',account_id=self.account,category_id=self.category,
            expected_balance=9900,balance_mode='APPLY',request_id=str(uuid4()))),201)
        self.assertEqual(self.daily_left(),300)

    def test_pausing_a_paid_bill_does_not_restore_its_spent_daily_allowance(self):
        db=get_db()
        db.execute("INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES(?,'2026-10',100000)",(self.category,));db.commit()
        bill=self.bill(amount=100)
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03')),201)
        db.execute('UPDATE budget_bills_v2 SET active=0 WHERE id=?',(bill,));db.commit()
        self.assertEqual(self.daily_left(),900)
        self.assertEqual(self.get_workspace()['totals']['remaining_commitments'],900)

    def test_wrong_bill_category_is_rejected_without_cash_or_link_change(self):
        other=self.add_category('Jedzenie',300)
        entry=self.expense(100,category=other,day='2026-10-03')
        bill=self.bill(amount=100)
        response=self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(
            month='2026-10',date='2026-10-03',existing_entry_id=entry,entry_version=1))
        self.assertEqual(response.status_code,400)
        db=get_db()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_bill_payments_v2').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],9900)

    def test_paid_bill_cannot_be_recategorized_to_reopen_fixed_allowance(self):
        other=self.add_category('Jedzenie',300)
        bill=self.bill(amount=100)
        entry=self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03')),201)['entry_id']
        version=get_db().execute('SELECT version FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone()[0]
        with self.assertRaises(ValidationError):
            categorize(dict(entry_ids=[entry],versions={str(entry):version},category_id=other))
        self.assertEqual(get_db().execute('SELECT category_id FROM budget_entry_lines_v2 WHERE entry_id=?',(entry,)).fetchone()[0],self.category)

    def test_unassigned_bank_payment_gets_bill_category_and_undo_restores_it(self):
        from budget_category_service import unassigned_category
        from routes_budget_workspace import insert_entry
        db=get_db();unassigned=unassigned_category(db)
        entry=insert_entry(db,dict(account_id=self.account,kind='EXPENSE',amount_cents=10000,date='2026-10-03',description='Faktura',merchant=None,
            lines=[dict(category_id=unassigned,amount_cents=10000,label='Opis z banku')]))
        db.commit();bill=self.bill(amount=100)
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03',existing_entry_id=entry,entry_version=1)),201)
        self.assertEqual(self.get_workspace()['totals']['remaining_commitments'],0)
        self.assertEqual(db.execute('SELECT category_id FROM budget_entry_lines_v2 WHERE entry_id=?',(entry,)).fetchone()[0],self.category)
        view=self.result(self.client.get(f'/api/budget/workspace/entries/{entry}/settlement-preview'))
        self.result(self.client.post(f'/api/budget/workspace/entries/{entry}/reverse-settlement',json=dict(view,request_id=str(uuid4()))))
        restored=db.execute('SELECT category_id,label FROM budget_entry_lines_v2 WHERE entry_id=?',(entry,)).fetchone()
        self.assertEqual(tuple(restored),(unassigned,'Opis z banku'))
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],9900)

    def test_bill_editor_cannot_move_paid_history_to_another_category(self):
        other=self.add_category('Jedzenie',300)
        bill=self.bill(amount=100)
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03')),201)
        version=get_db().execute('SELECT version FROM budget_bills_v2 WHERE id=?',(bill,)).fetchone()[0]
        response=self.client.put(f'/api/budget/workspace/bills/{bill}',json=dict(title='Internet',amount=100,due_day=15,frequency='MONTHLY',start_month='2026-10',account_id=self.account,category_id=other,version=version))
        self.assertEqual(response.status_code,400)
        self.assertEqual(get_db().execute('SELECT category_id FROM budget_bills_v2 WHERE id=?',(bill,)).fetchone()[0],self.category)

    def test_bill_editor_cannot_detach_paid_reserve_and_rewrite_funding_history(self):
        reserve=self.create_reserve(frequency='ONCE',target_amount=100,due_date='2026-10-15')
        self.result(self.move(reserve,'ADD',100),201)
        bill=self.bill(amount=100,due_day=15,frequency='ONCE',due_month='2026-10',reserve_id=reserve)
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03')),201)
        version=get_db().execute('SELECT version FROM budget_bills_v2 WHERE id=?',(bill,)).fetchone()[0]
        response=self.client.put(f'/api/budget/workspace/bills/{bill}',json=dict(title='Internet',amount=100,due_day=15,frequency='ONCE',due_month='2026-10',account_id=self.account,category_id=self.category,reserve_id=None,version=version))
        self.assertEqual(response.status_code,400)
        self.assertEqual(get_db().execute('SELECT reserve_id FROM budget_bills_v2 WHERE id=?',(bill,)).fetchone()[0],reserve)

    def test_investment_transfer_cannot_use_reserved_money(self):
        reserve=self.create_reserve(open_ended=True,monthly_amount=0)
        self.result(self.move(reserve,'ADD',9000),201)
        db=get_db();portfolio=db.execute("INSERT INTO portfolios(name,account_type) VALUES('IKE','IKE')").lastrowid;db.commit()
        with self.assertRaises(ValidationError):
            transfer_investment_cash(self.account,portfolio,2000,'OUT','Wpłata',date='2026-10-03')
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],10000)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_investment_transfers').fetchone()[0],0)
        transfer_investment_cash(self.account,portfolio,1000,'OUT','Wpłata',date='2026-10-03',request_id='permitted')
        transfer_investment_cash(self.account,portfolio,1000,'OUT','Wpłata',date='2026-10-03',request_id='permitted')
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],9000)
        self.assertFalse(db.in_transaction)

    def test_deletion_failure_rolls_back_balance_and_expense(self):
        entry=self.expense(100,day='2026-10-03')
        db=get_db()
        db.execute("CREATE TEMP TRIGGER reject_entry_delete BEFORE DELETE ON budget_entries_v2 BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        with self.assertRaises(Exception):self.client.delete(f'/api/budget/workspace/entries/{entry}')
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],9900)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entry_lines_v2 WHERE entry_id=?',(entry,)).fetchone()[0],1)
