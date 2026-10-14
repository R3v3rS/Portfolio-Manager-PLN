"""Regression scenarios from the October budget audit, on disposable databases."""
import unittest
from uuid import uuid4
from unittest.mock import patch
from tests import test_budget_planning as fixtures
from tests.test_budget_reserves import FrozenDate
from tests import budget_audit_scenarios as audit
from database import get_db


class BudgetAuditRegressions(unittest.TestCase):
    setUp=fixtures.BudgetPlanningTest.setUp
    result=fixtures.BudgetPlanningTest.result
    create_reserve=fixtures.BudgetPlanningTest.create_reserve
    item=fixtures.BudgetPlanningTest.item
    move=fixtures.BudgetPlanningTest.move
    bill=fixtures.BudgetPlanningTest.bill
    get_workspace=fixtures.BudgetPlanningTest.get_workspace
    forecast=fixtures.BudgetPlanningTest.forecast
    expense=fixtures.BudgetPlanningTest.expense
    plan=fixtures.BudgetPlanningTest.plan
    policy=fixtures.BudgetPlanningTest.policy

    def test_manual_cap_funded_bill_keeps_free_money_stable(self):
        values=audit.manual_limit_funded_bill(self)
        self.assertEqual((values['to_plan_before_payment'],values['to_plan_after_payment']),(9600,9600))
        self.assertEqual(self.get_workspace()['chart'][2]['budget_spent'],400)
        self.assertEqual(self.get_workspace()['chart'][-1]['budget_plan'],400)

    def test_fixed_deposit_is_not_satisfied_by_bill_payment(self):
        values=audit.linked_open(self)
        self.assertEqual((values['still_to_save'],values['to_plan'],values['extra']),(100,9800,100))

    def test_history_survives_new_default_and_archive(self):
        values=audit.media_history(self)
        self.assertEqual((values['october_plan_before'],values['october_plan_after']),(250,250))
        reserve=get_db().execute('SELECT id FROM budget_reserves').fetchone()[0]
        self.result(self.move(reserve,'RELEASE',250,date='2026-11-03'),201)
        self.result(self.client.put(f'{self.base}/{reserve}/archive',json=dict(archived=True,version=self.item(reserve)['version'])))
        self.assertEqual(self.get_workspace('2026-10')['totals']['planned'],250)

    def test_manual_retry_changes_cash_once_and_rejects_changed_payload(self):
        values=audit.retry_manual(self)
        self.assertEqual((values['first'],values['spent'],values['balance']),(values['second'],100,9900))
        db=get_db();saved=db.execute('SELECT request_id FROM budget_entry_requests').fetchone()[0]
        payload=dict(kind='EXPENSE',account_id=self.account,amount=200,date='2026-10-03',description='Inny',category_id=self.category,request_id=saved)
        self.assertEqual(self.client.post('/api/budget/workspace/entries',json=payload).status_code,409)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],9900)

    def test_future_entry_rejected_without_cash_change(self):
        response=self.client.post('/api/budget/workspace/entries',json=dict(kind='EXPENSE',account_id=self.account,amount=100,date='2026-10-20',description='Przyszła płatność',category_id=self.category))
        self.assertEqual(response.status_code,400)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)

    def test_media_creation_retry_succeeds(self):
        values=audit.media_retry(self)
        self.assertEqual((values['first_status'],values['retry_status'],values['reserve_count']),(201,201,1))

    def test_variable_bill_replaces_automatic_estimate_but_keeps_manual_buffer(self):
        values=audit.variable_bill(self)
        self.assertEqual(values['auto_category_plan'],180)
        daily=next(r for r in values['month_plan'] if r['kind']=='DAILY')
        self.assertEqual((daily['planned'],daily['done'],daily['remaining']),(0,0,0))
        self.result(self.client.put(f'/api/budget/workspace/plans/{self.category}',json=dict(month='2026-10',amount=250)))
        daily=next(r for r in self.get_workspace()['planning']['month_plan'] if r['kind']=='DAILY')
        self.assertEqual((daily['planned'],daily['remaining']),(70,70))

    def _reverse(self,entry):
        url=f'/api/budget/workspace/entries/{entry}'
        view=self.result(self.client.get(url+'/settlement-preview'))
        payload=dict(view,request_id=str(uuid4()))
        response=self.client.post(url+'/reverse-settlement',json=payload)
        self.result(response)
        self.result(self.client.post(url+'/reverse-settlement',json=payload))
        return view

    def test_undo_created_payment_restores_cash_reserve_and_bill(self):
        reserve=self.create_reserve(frequency='ONCE',target_amount=400,due_date='2026-10-15')
        self.result(self.move(reserve,'ADD',400),201)
        bill=self.bill(amount=400,frequency='ONCE',due_month='2026-10',reserve_id=reserve)
        payload=dict(month='2026-10',date='2026-10-03',request_id=str(uuid4()),version=1,reserve_version=2)
        entry=self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=payload),201)['entry_id']
        view=self._reverse(entry)
        self.assertEqual((view['balance_before'],view['balance_after'],view['restored_reserve']),(9600,10000,400))
        self.assertEqual((self.item(reserve)['saved'],self.item(reserve)['status']),(400,'ACTIVE'))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        self.assertEqual(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=payload).status_code,409)

    def test_undo_link_keeps_existing_expense_and_cash(self):
        entry=self.expense(180,day='2026-10-03')
        bill=self.bill(amount=180)
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03',existing_entry_id=entry,entry_version=1,request_id=str(uuid4()))),201)
        view=self._reverse(entry)
        self.assertFalse(view['delete_expense'])
        self.assertEqual((view['balance_before'],view['balance_after']),(9820,9820))
        self.assertEqual(self.get_workspace()['totals']['spent'],180)
        self.assertEqual(len(self.get_workspace()['bills'][0]['payment_candidates']),1)

    def test_closed_snapshot_reports_correction_without_rebooking(self):
        entry=self.expense(100)
        self.result(self.policy())
        self.result(self.client.put(f'/api/budget/workspace/plans/{self.category}',json=dict(month='2026-09',amount=250)))
        self.result(self.client.post(self.planning+'/close-month',json=dict(month='2026-09',request_id=str(uuid4()))),201)
        self.assertFalse(self.get_workspace('2026-09')['planning']['month_review']['closing_snapshot']['changed'])
        self.result(self.client.put(f'/api/budget/workspace/entries/{entry}',json=dict(account_id=self.account,kind='EXPENSE',amount=180,date='2026-09-20',description='Korekta',category_id=self.category,version=1)))
        snapshot=self.get_workspace('2026-09')['planning']['month_review']['closing_snapshot']
        self.assertTrue(snapshot['changed'])
        self.assertEqual(snapshot['differences']['spent'],80)
        self.assertEqual(self.get_workspace()['categories'][0]['carryover'],150)

    def test_shared_parent_cap_removes_only_the_funded_part_once(self):
        db=get_db()
        child=db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES('OC',?)",(self.category,)).lastrowid;db.commit()
        reserve=self.create_reserve(target_amount=400,frequency='ONCE',due_date='2026-10-15',category_id=child)
        self.result(self.move(reserve,'ADD',200),201)
        bill=self.bill(amount=400,frequency='ONCE',due_month='2026-10',reserve_id=reserve,category_id=child)
        self.result(self.client.put(f'/api/budget/workspace/plans/{self.category}',json=dict(month='2026-10',amount=1000)))
        before=self.get_workspace()['totals']['to_plan']
        self.assertEqual(before,9000)
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03',version=1,reserve_version=2,request_id=str(uuid4()))),201)
        workspace=self.get_workspace()
        self.assertEqual(workspace['totals']['to_plan'],before)
        self.assertEqual(sum(r['month_cost'] or 0 for r in workspace['planning']['month_plan']),workspace['totals']['budget_spent'])

    def test_reserve_match_is_only_a_suggestion_then_linking_keeps_cash(self):
        reserve=self.create_reserve(name='Prąd',monthly_amount=250,category_id=self.category)
        self.result(self.move(reserve,'ADD',250),201)
        entry=self.expense(180,day='2026-10-03')
        match=self.get_workspace()['planning']['payment_matches'][0]
        self.assertEqual((match['kind'],match['id'],match['candidates'][0]['id']),('RESERVE',reserve,entry))
        self.assertEqual(self.item(reserve)['saved'],250)
        self.result(self.move(reserve,'SPEND',180,date='2026-10-03',existing_entry_id=entry,entry_version=1),201)
        self.assertEqual((self.item(reserve)['saved'],self.get_workspace()['totals']['balance']),(70,9820))
        view=self._reverse(entry)
        self.assertEqual(view['restored_reserve'],180)
        self.assertEqual((self.item(reserve)['saved'],self.get_workspace()['totals']['balance']),(250,9820))

    def test_undo_rejects_stale_preview_without_changing_any_ledger(self):
        reserve=self.create_reserve(open_ended=True,monthly_amount=100)
        self.result(self.move(reserve,'ADD',100),201)
        entry=self.result(self.move(reserve,'SPEND',100),201)['budget_entry_id']
        url=f'/api/budget/workspace/entries/{entry}'
        preview=self.result(self.client.get(url+'/settlement-preview'))
        self.expense(10,day='2026-10-03')
        self.assertEqual(self.client.post(url+'/reverse-settlement',json=dict(preview,request_id=str(uuid4()))).status_code,409)
        self.assertEqual((self.item(reserve)['saved'],self.get_workspace()['totals']['balance']),(0,9890))

    def test_undo_yearly_payment_restores_cycle_and_anniversary(self):
        reserve=self.create_reserve(target_amount=400,frequency='YEARLY',due_date='2026-10-15')
        self.result(self.move(reserve,'ADD',500),201)
        entry=self.result(self.move(reserve,'SPEND',400),201)['budget_entry_id']
        self.assertEqual(self.item(reserve)['cycle'],2)
        self._reverse(entry)
        restored=self.item(reserve)
        self.assertEqual((restored['cycle'],restored['saved'],restored['due_date']),(1,500,'2026-10-15'))
