import unittest

from database import get_db
from budget_summary_service import monthly_budget_totals
from routes_budget_workspace import insert_entry
from tests import test_cash_forecast as fixtures


class BudgetPlannedIncomeTest(unittest.TestCase):
    setUp = fixtures.CashForecastTest.setUp
    result = fixtures.CashForecastTest.result
    income = fixtures.CashForecastTest.income
    receipt = fixtures.CashForecastTest.receipt
    create_reserve = fixtures.CashForecastTest.create_reserve
    item = fixtures.CashForecastTest.item
    move = fixtures.CashForecastTest.move

    def totals(self, month='2026-10'):
        return self.result(self.client.get('/api/budget/workspace/', query_string={'month': month}))['totals']

    def test_real_budget_example_includes_only_this_months_expected_income_and_is_read_only(self):
        db = get_db()
        db.execute('UPDATE budget_accounts SET balance=1502.01 WHERE id=?', (self.account,))
        insert_entry(db, dict(account_id=self.account, kind='EXPENSE', amount_cents=32947,
            date='2026-10-01', description='Wydatki', merchant=None,
            lines=[dict(category_id=self.category, amount_cents=32947, label='')]))
        db.execute("INSERT INTO budget_plans_v2(category_id,month,amount_cents) VALUES (?,'2026-10',446300)", (self.category,))
        db.commit()
        reserve = self.create_reserve(target_amount=1000, due_date='2026-11-30', frequency='ONCE')
        self.result(self.move(reserve, 'ADD', 435), 201)
        self.income(amount=6100)
        self.income(name='800+', amount=1600, start_date='2026-11-20')
        before = db.total_changes
        result = self.totals()
        self.assertEqual((result['balance'], result['income'], result['spent'], result['planned'], result['reserved']),
                         (1172.54, 0, 329.47, 4463, 435))
        self.assertEqual((result['expected_income'], result['to_plan']), (6100, 2639.01))
        self.assertEqual(db.total_changes, before)
        self.assertEqual(self.totals('2026-11')['expected_income'], 7700)

    def test_receiving_income_replaces_the_plan_with_actual_cash_once(self):
        income = self.income()
        before = self.totals()
        self.assertEqual((before['balance'], before['income'], before['expected_income'], before['to_plan']),
                         (10000, 0, 3000, 13000))
        self.result(self.receipt(income, amount=3000), 201)
        after = self.totals()
        self.assertEqual((after['balance'], after['income'], after['expected_income'], after['to_plan']),
                         (13000, 3000, 0, 13000))
        self.assertEqual(self.totals('2026-11')['expected_income'], 3000)

    def test_lower_receipt_does_not_leave_a_phantom_difference_in_expected_income(self):
        income = self.income()
        self.result(self.receipt(income, amount=2800), 201)
        totals = self.totals()
        self.assertEqual((totals['balance'], totals['expected_income'], totals['to_plan']), (12800, 0, 12800))

    def test_linking_existing_income_does_not_duplicate_cash_and_deleting_reopens_plan(self):
        income = self.income()
        db = get_db()
        entry = insert_entry(db, dict(account_id=self.account, kind='INCOME', amount_cents=250000,
            date='2026-10-03', description='Pensja z banku', merchant=None, lines=[]))
        db.commit()
        self.result(self.receipt(income, existing_entry_id=entry), 201)
        totals = self.totals()
        self.assertEqual((totals['balance'], totals['expected_income'], totals['to_plan']), (12500, 0, 12500))
        self.result(self.client.delete(f'/api/budget/workspace/entries/{entry}'))
        reopened = self.totals()
        self.assertEqual((reopened['balance'], reopened['expected_income'], reopened['to_plan']), (10000, 3000, 13000))

    def test_inactive_one_off_end_dates_and_short_months_use_actual_occurrences(self):
        paused = self.income(amount=900)
        self.result(self.client.put(f'{self.url}/incomes/{paused}/active', json=dict(active=False, version=1)))
        self.income(amount=100, frequency='ONCE', start_date='2026-10-31')
        self.income(amount=200, frequency='MONTHLY', start_date='2026-10-31', end_date='2027-03-30')
        self.income(amount=400, start_date='2026-12-10')
        self.assertEqual(self.totals()['expected_income'], 300)
        self.assertEqual(self.totals('2026-11')['expected_income'], 200)
        self.assertEqual(self.totals('2027-02')['expected_income'], 600)
        self.assertEqual(self.totals('2027-03')['expected_income'], 400)
        self.assertEqual(self.totals('2026-09')['expected_income'], 0)

    def test_editing_payday_does_not_recreate_income_from_an_already_received_month(self):
        income = self.income()
        self.result(self.receipt(income, amount=3000), 201)
        self.result(self.client.put(f'{self.url}/incomes/{income}', json=dict(
            name='Pensja', account_id=self.account, amount=3200, start_date='2026-10-15',
            end_date=None, frequency='MONTHLY', version=2)))
        self.assertEqual(self.totals()['expected_income'], 0)
        self.assertEqual(self.totals('2026-11')['expected_income'], 3200)


if __name__ == '__main__':
    unittest.main()
