import os
import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.exceptions import NotFoundError, ValidationError  # noqa: E402
from api.exceptions import ApiError  # noqa: E402
from api.response import error_response  # noqa: E402
from database import init_db  # noqa: E402
from loan_service import LoanService  # noqa: E402
from routes_budget_workspace import workspace_bp  # noqa: E402
from routes_loans import loans_bp  # noqa: E402
from routes_cash_forecast import forecast_bp  # noqa: E402


class LoanWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        app = Flask(__name__)
        app.config.update(TESTING=True, DATABASE=os.path.join(self.temp.name, 'loans.db'))
        app.register_blueprint(loans_bp, url_prefix='/api/loans')
        app.register_blueprint(workspace_bp, url_prefix='/api/budget/workspace')
        app.register_blueprint(forecast_bp, url_prefix='/api/budget/forecast')
        app.register_error_handler(ValidationError, lambda error: error_response('validation_error', error.message, status=400))
        app.register_error_handler(NotFoundError, lambda error: error_response('not_found', error.message, status=404))
        app.register_error_handler(ApiError, lambda error: error_response(error.code,error.message,status=error.status))
        init_db(app)
        self.app = app
        self.client = app.test_client()
        self.loan_id = self.payload(self.client.post('/api/loans/', json={
            'name': 'Raty 0%', 'original_amount': 2641,
            'duration_months': 34, 'start_date': '2025-12-15',
            'installment_type': 'EQUAL', 'initial_rate': 0, 'category': 'RATY_0',
        }), 201)['id']

    def payload(self, response, status=200):
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()['payload']

    def budget_account(self):
        return self.payload(self.client.post('/api/budget/workspace/accounts', json={
            'name': 'Osobiste', 'balance': 1000,
        }), 201)['id']

    def test_link_imported_payment_and_undo_preserve_the_expense_and_balance(self):
        account=self.budget_account();url=f'/api/loans/{self.loan_id}/payments'
        workspace=self.payload(self.client.get('/api/budget/workspace?month=2026-10'))
        category=next(c['id'] for c in workspace['categories'] if c['name']=='Rachunki')
        entry=self.payload(self.client.post('/api/budget/workspace/entries',json=dict(kind='EXPENSE',account_id=account,amount=77.68,date='2025-12-15',description='Rata z banku',lines=[dict(category_id=category,amount=77.68,label='Bank')])),201)['id']
        data=dict(installment_month=1,paid_on='2025-12-15',amount=77.68,account_id=account)
        self.assertEqual(self.client.post(url,json=data).status_code,400)
        candidates=self.payload(self.client.get(f'/api/loans/{self.loan_id}/payment-candidates',query_string=dict(account_id=account,paid_on=data['paid_on'],amount=data['amount'])))['items']
        self.assertEqual(len(candidates),1)
        payment=self.payload(self.client.post(url,json=dict(data,existing_entry_id=entry,entry_version=candidates[0]['version'])),201)
        self.assertEqual(payment['budget_entry_id'],entry)
        self.payload(self.client.delete(f'{url}/{payment["id"]}'))
        after=self.payload(self.client.get('/api/budget/workspace?month=2025-12'))
        self.assertEqual(len(after['entries']),1)
        self.assertEqual(after['entries'][0]['lines'][0]['label'],'Bank')
        self.assertEqual(after['totals']['spent'],77.68)
        self.assertEqual(after['accounts'][0]['balance'],922.32)

    def test_renaming_loan_category_does_not_change_plan_or_daily_forecast(self):
        self.budget_account();before=self.payload(self.client.get('/api/budget/workspace?month=2026-10'))
        category=next(c for c in before['categories'] if c['name']=='Rachunki')
        self.payload(self.client.put(f'/api/budget/workspace/plans/{category["id"]}',json=dict(month='2026-10',amount=1000)))
        before=self.payload(self.client.get('/api/budget/workspace?month=2026-10'))
        self.payload(self.client.put(f'/api/budget/workspace/categories/{category["id"]}',json=dict(name='Opłaty',parent_id=None,version=category['version'])))
        after=self.payload(self.client.get('/api/budget/workspace?month=2026-10'))
        self.assertEqual(before['totals']['planned'],after['totals']['planned'])
        self.assertEqual(after['planning']['loans'][0]['category_id'],category['id'])
        self.assertEqual(after['chart'][-1]['cash_plan'],before['chart'][-1]['cash_plan'])

    def test_link_saved_payment_is_idempotent_and_keeps_historical_expense_cash_effect(self):
        account=self.budget_account();url=f'/api/loans/{self.loan_id}/payments'
        data=dict(installment_month=1,paid_on='2025-12-15',amount=77.68)
        payment=self.payload(self.client.post(url,json=data),201)
        from database import get_db
        from routes_budget_workspace import insert_entry
        with self.app.app_context():
            db=get_db()
            category=db.execute('SELECT category_id FROM loan_budget_settings WHERE loan_id=?',(self.loan_id,)).fetchone()[0]
            entry=insert_entry(db,dict(kind='EXPENSE',account_id=account,amount_cents=7768,date=data['paid_on'],description='Historyczny import',merchant=None,cash_effect=0,lines=[dict(category_id=category,label='Import',amount_cents=7768)]))
            db.commit()
        values=dict(data,payment_id=payment['id'],apply_to_budget=True,account_id=account,existing_entry_id=entry,entry_version=1)
        first=self.payload(self.client.post(url,json=values),201)
        self.assertEqual(first,self.payload(self.client.post(url,json=values),201))
        self.payload(self.client.delete(f'{url}/{payment["id"]}'))
        with self.app.app_context():
            db=get_db()
            self.assertEqual(db.execute('SELECT cash_effect FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(account,)).fetchone()[0],1000)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)

    def test_link_failure_rolls_back_reclassification_and_cannot_reuse_a_linked_expense(self):
        account=self.budget_account();url=f'/api/loans/{self.loan_id}/payments'
        from database import get_db
        from routes_budget_workspace import insert_entry
        with self.app.app_context():
            db=get_db();category=db.execute("INSERT INTO budget_categories_v2(name) VALUES('Zakupy')").lastrowid
            entry=insert_entry(db,dict(kind='EXPENSE',account_id=account,amount_cents=7768,date='2025-12-15',description='Import',merchant=None,lines=[dict(category_id=category,label='Bank',amount_cents=7768)]))
            db.execute("CREATE TRIGGER fail_loan_link BEFORE INSERT ON loan_installment_payments BEGIN SELECT RAISE(ABORT,'failed'); END");db.commit()
        values=dict(installment_month=1,paid_on='2025-12-15',amount=77.68,account_id=account,existing_entry_id=entry,entry_version=1)
        with self.assertRaises(Exception):self.client.post(url,json=values)
        with self.app.app_context():
            db=get_db()
            self.assertEqual(tuple(db.execute('SELECT category_id,label FROM budget_entry_lines_v2 WHERE entry_id=?',(entry,)).fetchone()),(category,'Bank'))
            self.assertEqual(db.execute('SELECT version FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone()[0],1)
            self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(account,)).fetchone()[0],922.32)
            db.execute('DROP TRIGGER fail_loan_link');db.commit()
        # A stale selection must not be applied.
        self.assertEqual(self.client.post(url,json=dict(values,entry_version=0)).status_code,409)
        self.payload(self.client.post(url,json=values),201)
        # The same imported payment cannot cover a different installment.
        self.assertEqual(self.client.post(url,json=dict(values,installment_month=2,entry_version=2)).status_code,400)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM loan_installment_payments').fetchone()[0],1)

    def test_migration_recovers_each_loans_account_without_rebooking_payments(self):
        account=self.budget_account()
        other=self.payload(self.client.post('/api/budget/workspace/accounts',json=dict(name='Alior',balance=500)),201)['id']
        second=self.payload(self.client.post('/api/loans/',json=dict(name='Mieszkanie',original_amount=2641,duration_months=34,start_date='2025-12-15',installment_type='EQUAL',initial_rate=0)),201)['id']
        for loan,target in ((self.loan_id,other),(second,account)):
            self.payload(self.client.post(f'/api/loans/{loan}/payments',json=dict(installment_month=1,paid_on='2025-12-15',amount=77.68,account_id=target)),201)
        from database import get_db
        from loan_budget_service import initialize
        with self.app.app_context():
            db=get_db();db.execute('DELETE FROM loan_budget_settings')
            before=[tuple(r) for r in db.execute('SELECT id,balance FROM budget_accounts ORDER BY id')]
            initialize(db);initialize(db);db.commit()
            self.assertEqual([tuple(r) for r in db.execute('SELECT id,balance FROM budget_accounts ORDER BY id')],before)
            self.assertEqual(dict(db.execute('SELECT loan_id,account_id FROM loan_budget_settings')),{self.loan_id:other,second:account})
            self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],2)

    def test_individual_account_settings_reach_forecast_without_modifying_balances(self):
        account=self.budget_account()
        other=self.payload(self.client.post('/api/budget/workspace/accounts',json=dict(name='Alior',balance=500)),201)['id']
        schedule=self.payload(self.client.get(f'/api/loans/{self.loan_id}/schedule'))
        config=schedule['budget_settings']
        self.payload(self.client.put(f'/api/loans/{self.loan_id}/budget-settings',json=dict(account_id=other,category_id=config['category_id'],version=config['version'])))
        forecast=self.payload(self.client.get('/api/budget/forecast'))
        self.assertTrue(any(e['kind']=='LOAN' for e in forecast['events']))
        self.assertTrue(all(e['account_id']==other for e in forecast['events'] if e['kind']=='LOAN'))
        from database import get_db
        with self.app.app_context():
            balances={r['id']:r['balance'] for r in get_db().execute('SELECT id,balance FROM budget_accounts')}
        self.assertEqual(balances,{account:1000,other:500})

    def test_missing_settings_can_be_saved_and_stale_settings_are_rejected(self):
        account=self.budget_account()
        from database import get_db
        with self.app.app_context():
            db=get_db();db.execute('DELETE FROM loan_budget_settings');db.commit()
        config=self.payload(self.client.get(f'/api/loans/{self.loan_id}/schedule'))['budget_settings']
        self.assertEqual(config['version'],0)
        values=dict(account_id=account,category_id=config['category_id'],version=0)
        saved=self.payload(self.client.put(f'/api/loans/{self.loan_id}/budget-settings',json=values))
        self.assertEqual(saved['account_id'],account)
        self.assertEqual(self.client.put(f'/api/loans/{self.loan_id}/budget-settings',json=dict(values,account_id=None)).status_code,409)

    def test_apply_existing_payment_to_budget_once_and_reverse_once(self):
        account=self.budget_account();url=f'/api/loans/{self.loan_id}/payments'
        data=dict(installment_month=1,paid_on='2025-12-15',amount=77.68)
        payment=self.payload(self.client.post(url,json=data),201)
        self.assertIsNone(payment['budget_entry_id'])
        values=dict(data,payment_id=payment['id'],apply_to_budget=True,account_id=account)
        applied=self.payload(self.client.post(url,json=values),201)
        self.assertEqual(applied,self.payload(self.client.post(url,json=values),201))
        from database import get_db
        with self.app.app_context():
            db=get_db()
            self.assertEqual(db.execute('SELECT COUNT(*) FROM loan_installment_payments').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(account,)).fetchone()[0],922.32)
        self.payload(self.client.delete(f'{url}/{payment["id"]}'))
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts WHERE id=?',(account,)).fetchone()[0],1000)

    def test_apply_existing_payment_requires_matching_amount_date_and_valid_account(self):
        account=self.budget_account();url=f'/api/loans/{self.loan_id}/payments'
        data=dict(installment_month=1,paid_on='2025-12-15',amount=77.68)
        payment=self.payload(self.client.post(url,json=data),201)
        values=dict(data,payment_id=payment['id'],apply_to_budget=True,account_id=account)
        for change in (dict(amount=80),dict(paid_on='2025-12-16'),dict(account_id=None),dict(account_id=99999)):
            self.assertEqual(self.client.post(url,json=dict(values,**change)).status_code,400)
        from database import get_db
        with self.app.app_context():
            db=get_db();self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(account,)).fetchone()[0],1000)

    def test_estimate_uses_last_completed_date_and_oversized_simulation_is_rejected(self):
        with self.app.app_context():
            status = LoanService.get_status(self.loan_id, as_of='2026-09-30')
        self.assertEqual(status['estimated_balance'], 1941.91)
        self.assertEqual(status['next_due_date'], '2026-10-15')
        scenario = self.payload(self.client.get(
            f'/api/loans/{self.loan_id}/schedule?monthly_overpayment=100&simulated_action=REDUCE_TERM'
        ))
        self.assertEqual(scenario['actual']['schedule'][10]['remaining_balance'],
                         scenario['baseline']['schedule'][10]['remaining_balance'])
        self.assertNotEqual(scenario['actual']['schedule'][-1]['date'],
                            scenario['simulation']['schedule'][-1]['date'])
        response = self.client.get(
            f'/api/loans/{self.loan_id}/schedule?sim_amount=3000&sim_date=2026-10-01'
        )
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            loan = LoanService.get_loan_details(self.loan_id)
            rows, _, _ = LoanService.calculate_schedule(
                loan, LoanService.get_loan_rates(self.loan_id),
                [{'amount': 3000, 'date': '2026-10-01', 'type': 'REDUCE_TERM'}],
            )
        self.assertTrue(all(row['installment'] >= 0 and row['remaining_balance'] >= 0 for row in rows))

    def test_installment_and_overpayment_link_to_new_budget_once_and_can_be_undone(self):
        account_id = self.budget_account()
        url = f'/api/loans/{self.loan_id}/payments'
        payment = self.payload(self.client.post(url, json={
            'installment_month': 1, 'paid_on': '2026-01-15',
            'account_id': account_id,
        }), 201)
        self.assertIsNotNone(payment['budget_entry_id'])
        self.assertEqual(self.client.post(url, json={
            'installment_month': 1, 'paid_on': '2026-01-15',
            'account_id': account_id,
        }).status_code, 400)
        budget = self.payload(self.client.get('/api/budget/workspace/?month=2026-01'))
        self.assertEqual(budget['totals']['balance'], 922.32)
        self.assertEqual(len(budget['entries']), 1)
        self.assertEqual(self.client.delete(
            f'/api/budget/workspace/entries/{payment["budget_entry_id"]}'
        ).status_code, 400)
        self.payload(self.client.delete(f'{url}/{payment["id"]}'))
        budget = self.payload(self.client.get('/api/budget/workspace/?month=2026-01'))
        self.assertEqual(budget['totals']['balance'], 1000)
        self.assertEqual(budget['entries'], [])

        overpayment = self.payload(self.client.post(f'/api/loans/{self.loan_id}/overpayments', json={
            'amount': 100, 'date': '2026-02-20', 'type': 'REDUCE_TERM', 'account_id': account_id,
        }), 201)
        budget = self.payload(self.client.get('/api/budget/workspace/?month=2026-02'))
        self.assertEqual(budget['totals']['balance'], 900)
        self.payload(self.client.delete(
            f'/api/loans/{self.loan_id}/overpayments/{overpayment["id"]}'
        ))
        self.assertEqual(self.payload(self.client.get('/api/budget/workspace/?month=2026-02'))['totals']['balance'], 1000)

    def test_next_installment_skips_early_payment_and_returns_after_undo(self):
        payment = self.payload(self.client.post(f'/api/loans/{self.loan_id}/payments', json={
            'installment_month': 10, 'paid_on': '2026-10-10',
        }), 201)
        with self.app.app_context():
            status = LoanService.get_status(self.loan_id, as_of='2026-10-10')
        self.assertEqual(status['next_due_date'], '2026-11-15')
        self.payload(self.client.delete(f'/api/loans/{self.loan_id}/payments/{payment["id"]}'))
        with self.app.app_context():
            status = LoanService.get_status(self.loan_id, as_of='2026-10-15')
        self.assertEqual(status['next_due_date'], '2026-10-15')

    def test_overpayment_links_existing_expense_once_and_undo_preserves_cash(self):
        account=self.budget_account()
        category=self.payload(self.client.post('/api/budget/workspace/categories',json={'name':'Gry'}),201)['id']
        entry=self.payload(self.client.post('/api/budget/workspace/entries',json=dict(
            account_id=account,kind='EXPENSE',amount=10.38,date='2026-09-10',description='Rata extra',
            lines=[dict(category_id=category,amount=10.38)])),201)['id']
        url=f'/api/loans/{self.loan_id}/overpayments'
        values=dict(amount=10.38,date='2026-09-10',account_id=account)
        self.assertEqual(self.client.post(url,json=values).status_code,409)
        payment=self.payload(self.client.post(url,json=dict(values,existing_entry_id=entry,entry_version=1)),201)
        self.assertEqual(self.client.post(url,json=dict(values,existing_entry_id=entry,entry_version=1)).status_code,409)
        budget=self.payload(self.client.get('/api/budget/workspace?month=2026-09'))
        self.assertEqual((budget['totals']['balance'],budget['totals']['spent'],len(budget['entries'])),(989.62,10.38,1))
        self.assertEqual(budget['entries'][0]['loan_id'],self.loan_id)
        self.payload(self.client.delete(url+f'/{payment["id"]}'))
        restored=self.payload(self.client.get('/api/budget/workspace?month=2026-09'))
        self.assertEqual(restored['totals']['balance'],989.62)
        self.assertEqual(restored['entries'][0]['lines'][0]['category_id'],category)
        self.assertIsNone(restored['entries'][0]['loan_id'])

    def test_confirmed_balance_is_separate_from_estimate(self):
        self.payload(self.client.post(f'/api/loans/{self.loan_id}/balance-checks', json={
            'balance': 1900, 'checked_on': '2026-09-20',
        }), 201)
        schedule = self.payload(self.client.get(f'/api/loans/{self.loan_id}/schedule'))
        self.assertEqual(schedule['status']['confirmed_balance'], 1900)
        self.assertEqual(schedule['status']['confirmed_on'], '2026-09-20')
        self.assertNotEqual(schedule['status']['estimated_balance'], 1900)


if __name__ == '__main__':
    unittest.main()
