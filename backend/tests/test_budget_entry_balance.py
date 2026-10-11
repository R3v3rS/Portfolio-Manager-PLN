import sqlite3
import unittest

from database import get_db
from routes_budget_workspace import insert_entry
from tests import test_budget_reserves as fixtures
from budget_entry_balance_service import apply


class BudgetEntryBalanceTest(unittest.TestCase):
    result = fixtures.BudgetReservesTest.result

    def setUp(self):
        fixtures.BudgetReservesTest.setUp(self)
        self.db = get_db()
        self.entry = insert_entry(self.db, dict(account_id=self.account, kind='EXPENSE', amount_cents=4144,
            date='2026-10-02', description='Dino', merchant='Dino', cash_effect=0,
            lines=[dict(category_id=self.category, amount_cents=4144, label='Zakupy')]))
        self.db.execute("UPDATE budget_entries_v2 SET receipt_filename='original.jpg' WHERE id=?", (self.entry,))
        self.db.commit()
        self.url=f'/api/budget/workspace/entries/{self.entry}/apply-balance'

    def balance(self):
        return self.db.execute('SELECT balance FROM budget_accounts WHERE id=?', (self.account,)).fetchone()[0]

    def test_apply_is_once_only_and_preserves_the_expense_split_and_attachment(self):
        before=dict(self.db.execute('SELECT * FROM budget_entries_v2 WHERE id=?', (self.entry,)).fetchone())
        lines=[tuple(r) for r in self.db.execute('SELECT * FROM budget_entry_lines_v2 WHERE entry_id=?', (self.entry,))]
        payload=dict(version=before['version'],expected_balance=10000)
        first=self.result(self.client.post(self.url,json=payload))
        self.assertEqual((first['applied'], first['balance']), (True,9958.56))
        self.assertFalse(self.result(self.client.post(self.url,json=payload))['applied'])
        self.assertEqual(self.balance(),9958.56)
        after=dict(self.db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(self.entry,)).fetchone())
        self.assertEqual(after.pop('cash_effect'),1);self.assertEqual(before.pop('cash_effect'),0)
        self.assertEqual(after.pop('version'),before.pop('version')+1)
        self.assertEqual(after,before)
        self.assertEqual([tuple(r) for r in self.db.execute('SELECT * FROM budget_entry_lines_v2 WHERE entry_id=?',(self.entry,))],lines)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)
        self.result(self.client.delete(f'/api/budget/workspace/entries/{self.entry}'))
        self.assertEqual(self.balance(),10000)

    def test_stale_version_balance_and_invalid_snapshot_do_not_debit_cash(self):
        for payload, status in ((dict(version=0,expected_balance=10000),409),
                                 (dict(version=1,expected_balance=9999),409),
                                 (dict(version=1,expected_balance=True),400),
                                 (dict(version=1),400),
                                 (dict(expected_balance=10000),409)):
            self.assertEqual(self.client.post(self.url,json=payload).status_code,status)
            self.assertEqual(self.balance(),10000)

    def test_failed_update_rolls_back_the_cash_deduction(self):
        self.db.execute("CREATE TRIGGER reject_cash_effect BEFORE UPDATE OF cash_effect ON budget_entries_v2 BEGIN SELECT RAISE(ABORT,'test failure'); END")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            apply(self.entry, dict(version=1,expected_balance=10000))
        self.assertEqual(self.balance(),10000)
        self.assertEqual(self.db.execute('SELECT cash_effect FROM budget_entries_v2 WHERE id=?',(self.entry,)).fetchone()[0],0)

    def test_income_and_missing_entry_cannot_be_applied_as_expenses(self):
        self.db.execute("UPDATE budget_entries_v2 SET kind='INCOME' WHERE id=?",(self.entry,));self.db.commit()
        self.assertEqual(self.client.post(self.url,json=dict(version=1,expected_balance=10000)).status_code,400)
        self.assertEqual(self.client.post('/api/budget/workspace/entries/99999/apply-balance',json=dict(version=1,expected_balance=10000)).status_code,404)
        self.assertEqual(self.balance(),10000)


if __name__=='__main__':
    unittest.main()
