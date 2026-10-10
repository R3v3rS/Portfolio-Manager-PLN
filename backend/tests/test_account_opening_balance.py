import json
import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from tests import test_budget_accounts as fixtures
from database import get_db
from routes_budget_workspace import insert_entry
from monthly_report_service import _budget
from budget_summary_service import monthly_budget_totals
import budget_accounts_service as accounts
import budget_import_schema


class OpeningBalanceTest(unittest.TestCase):
    setUp=fixtures.BudgetAccountsTest.setUp
    result=fixtures.BudgetAccountsTest.result
    reconcile=fixtures.BudgetAccountsTest.reconcile
    balances=fixtures.BudgetAccountsTest.balances
    transfer=fixtures.BudgetAccountsTest.transfer

    def post(self, account_id=None, **extra):
        account_id=account_id or self.account
        account=next(a for a in accounts.workspace()['accounts'] if a['id']==account_id)
        data=dict(balance=912,expected_balance=account['balance'],expected_opening_id=account['opening_record_id'],notes='',request_id=str(uuid4()))
        data.update(extra)
        return self.client.post(f'/api/budget/accounts/{account_id}/opening-balance',json=data)

    def expense(self, amount=65):
        db=get_db()
        entry=insert_entry(db,dict(account_id=self.account,kind='EXPENSE',amount_cents=round(amount*100),date='2026-10-01',
            description='Zwift',merchant=None,lines=[dict(category_id=self.category,amount_cents=round(amount*100),label='')]))
        db.commit();return entry

    def alior(self):
        db=get_db();db.execute('UPDATE budget_accounts SET balance=0 WHERE id=?',(self.account,));db.commit()
        self.expense()
        return self.result(self.reconcile(847,notes='Poczatkowa kwota'),201)['id']

    def test_912_opening_with_65_expense_preserves_847_and_removes_only_correction(self):
        source=self.alior();db=get_db()
        entry_before=[tuple(r) for r in db.execute('SELECT * FROM budget_entries_v2')]
        line_before=[tuple(r) for r in db.execute('SELECT * FROM budget_entry_lines_v2')]
        self.result(self.post(from_reconciliation_id=source),201)
        account=accounts.workspace()['accounts'][0]
        self.assertEqual((account['balance'],account['opening_balance'],account['opening_date']),(847,912,'2026-10-01'))
        self.assertEqual(accounts.workspace()['history'],[])
        self.assertEqual(entry_before,[tuple(r) for r in db.execute('SELECT * FROM budget_entries_v2')])
        self.assertEqual(line_before,[tuple(r) for r in db.execute('SELECT * FROM budget_entry_lines_v2')])
        report=_budget(db,date(2026,10,1),date(2026,10,31))
        self.assertEqual((report['income'],report['expenses'],report['balance_adjustments'],report['balance_checks']),(0,65,0,0))
        self.assertEqual(monthly_budget_totals(db,'2026-10')['income'],0)
        self.assertEqual(db.execute('SELECT record_type FROM budget_account_reconciliations WHERE id=?',(source,)).fetchone()[0],'OPENING')

    def test_new_account_has_opening_metadata_without_a_history_record(self):
        data=dict(name='Alior',balance=912,request_id=str(uuid4()))
        created=self.result(self.client.post('/api/budget/accounts/',json=data),201)
        self.assertEqual(self.result(self.client.post('/api/budget/accounts/',json=data),201),created)
        account=next(a for a in accounts.workspace()['accounts'] if a['id']==created['id'])
        self.assertEqual((account['balance'],account['opening_balance']),(912,912))
        self.assertEqual(accounts.workspace()['history'],[])
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)

    def test_setting_opening_keeps_booked_expense_and_later_real_correction(self):
        self.expense();self.result(self.post(balance=912),201)
        self.assertEqual(self.balances(),[847,2000])
        self.result(self.reconcile(800),201)
        self.result(self.post(balance=1000),201)
        self.assertEqual(self.balances(),[888,2000])
        history=accounts.workspace()['history']
        self.assertEqual(len(history),1);self.assertEqual(history[0]['amount'],-47)
        report=_budget(get_db(),date(2026,10,1),date(2026,10,31))
        self.assertEqual((report['expenses'],report['balance_adjustments']),(65,-47))

    def test_retries_and_stale_cash_or_opening_state_are_protected(self):
        token=str(uuid4())
        first=self.result(self.post(request_id=token,expected_balance=10000,expected_opening_id=None),201)
        self.assertEqual(self.result(self.post(request_id=token,expected_balance=10000,expected_opening_id=None),201),first)
        self.assertEqual(self.post(balance=913,request_id=token,expected_balance=10000,expected_opening_id=None).status_code,409)
        self.assertEqual(self.post(expected_balance=10000).status_code,409)
        self.assertEqual(self.post(expected_opening_id=None).status_code,409)
        self.assertEqual(self.post(expected_opening_id=True).status_code,400)
        self.assertEqual(self.balances(),[912,2000])

    def test_conversion_cannot_hide_another_accounts_record_or_repeat_as_new_request(self):
        source=self.alior();token=str(uuid4())
        self.assertEqual(self.post(self.other,from_reconciliation_id=source).status_code,400)
        first=self.result(self.post(from_reconciliation_id=source,request_id=token,expected_balance=847,expected_opening_id=None),201)
        self.assertEqual(self.result(self.post(from_reconciliation_id=source,request_id=token,expected_balance=847,expected_opening_id=None),201),first)
        self.assertEqual(self.post(from_reconciliation_id=source).status_code,400)
        self.assertEqual(self.balances(),[847,2000])

    def test_failed_conversion_rolls_back_source_and_balance(self):
        source=self.alior();db=get_db();before=tuple(db.execute('SELECT * FROM budget_account_reconciliations WHERE id=?',(source,)).fetchone())
        with patch('budget_accounts_service._now',return_value=None):
            with self.assertRaises(Exception):
                accounts.set_opening_balance(self.account,dict(from_reconciliation_id=source,expected_balance=847,
                    expected_opening_id=None,notes='',request_id=str(uuid4())))
        self.assertEqual(tuple(db.execute('SELECT * FROM budget_account_reconciliations WHERE id=?',(source,)).fetchone()),before)
        self.assertEqual(self.balances(),[847,2000])

    def test_known_legacy_creation_migrates_without_cash_or_identity_changes(self):
        db=get_db();token=str(uuid4())
        payload=json.dumps(dict(operation='CREATE',name='Konto',balance=10000))
        row=db.execute('''INSERT INTO budget_account_reconciliations
            (account_id,previous_balance_cents,observed_balance_cents,difference_cents,date,notes,request_id,request_payload,created_at)
            VALUES (?,1000000,1000000,0,'2026-10-02','Saldo początkowe przy dodaniu konta',?,?,'2026-10-02')''',(self.account,token,payload)).lastrowid
        db.commit();budget_import_schema.initialize(db);budget_import_schema.initialize(db)
        record=db.execute('SELECT * FROM budget_account_reconciliations WHERE id=?',(row,)).fetchone()
        self.assertEqual((record['record_type'],record['opening_balance_cents'],record['request_id'],record['difference_cents']),('OPENING',1000000,token,0))
        self.assertEqual(accounts.workspace()['history'],[])
        self.assertEqual(self.balances(),[10000,2000])

    def test_internal_transfers_and_history_only_imports_are_preserved_when_setting_opening(self):
        self.result(self.transfer(100),201)
        db=get_db();insert_entry(db,dict(account_id=self.account,kind='EXPENSE',amount_cents=5000,date='2026-10-01',
            description='Historia',merchant=None,cash_effect=0,lines=[dict(category_id=self.category,amount_cents=5000,label='')]))
        db.commit();self.result(self.post(balance=912),201)
        self.assertEqual(self.balances(),[812,2100])
        self.assertEqual(len(accounts.workspace()['history']),1)


if __name__=='__main__':unittest.main()
