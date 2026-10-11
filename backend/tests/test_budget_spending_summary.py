import sqlite3
import unittest
from datetime import date

from budget_summary_service import period_spending


class BudgetSpendingSummaryTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.execute('''CREATE TABLE budget_entries_v2 (
            date TEXT, kind TEXT, amount_cents INTEGER, cash_effect INTEGER)''')
        self.db.execute('''CREATE TABLE budget_reserve_movements (
            date TEXT, kind TEXT, budget_cost_cents INTEGER)''')
        self.db.execute('ALTER TABLE budget_entries_v2 ADD COLUMN id INTEGER')
        self.db.execute('CREATE TABLE budget_purchase_refunds(entry_id INTEGER)')

    def test_counts_recorded_expenses_once_and_excludes_future_and_other_months(self):
        self.db.executemany('INSERT INTO budget_entries_v2(date,kind,amount_cents,cash_effect) VALUES (?,?,?,?)', [
            ('2026-09-30', 'EXPENSE', 90000, 1),
            ('2026-10-01', 'EXPENSE', 2000, 1),
            ('2026-10-03', 'EXPENSE', 4144, 0),  # History without another balance debit.
            ('2026-10-03', 'INCOME', 610000, 1),
            ('2026-10-04', 'EXPENSE', 5000, 1),
            ('2026-11-01', 'EXPENSE', 8000, 1),
        ])
        summary = period_spending(self.db, '2026-10', date(2026, 10, 3))
        self.assertEqual((summary['spent'], summary['expense_count']), (61.44, 2))
        self.assertEqual(summary['through'], '2026-10-03')
        past = period_spending(self.db, '2026-10', date(2026, 11, 10))
        self.assertEqual((past['spent'], past['through']), (111.44, '2026-10-31'))
        future = period_spending(self.db, '2026-11', date(2026, 10, 3))
        self.assertEqual((future['spent'], future['expense_count'], future['through']), (0, 0, None))

    def test_reserves_are_separate_and_settlement_is_not_counted_twice(self):
        self.db.execute("INSERT INTO budget_entries_v2(date,kind,amount_cents,cash_effect) VALUES ('2026-10-03','EXPENSE',20000,1)")
        self.db.executemany('INSERT INTO budget_reserve_movements VALUES (?,?,?)', [
            ('2026-09-30', 'ADD', 10000),
            ('2026-10-01', 'ADD', 43500),
            ('2026-10-03', 'SPEND', -20000),
            ('2026-10-03', 'RELEASE', -1000),
            ('2026-10-04', 'ADD', 30000),
        ])
        summary = period_spending(self.db, '2026-10', date(2026, 10, 3))
        self.assertEqual(summary['spent'], 200)
        self.assertEqual(summary['reserve_contributions'], 435)
        self.assertEqual(summary['reserve_settled'], 200)
        self.assertEqual(summary['reserve_released'], 10)
        self.assertEqual(summary['budget_spent'], 425)


if __name__ == '__main__':
    unittest.main()
