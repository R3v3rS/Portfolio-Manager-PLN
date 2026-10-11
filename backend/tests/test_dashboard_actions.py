import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.exceptions import ApiError, NotFoundError, ValidationError
from api.response import error_response
from database import get_db, init_db
from routes_dashboard import dashboard_bp


class FrozenDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 2)


class DashboardActionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name)/'actions.db'))
        init_db(self.app)
        self.app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
        self.app.register_error_handler(ValidationError, lambda e: error_response('validation_error', str(e), status=400))
        self.app.register_error_handler(NotFoundError, lambda e: error_response('not_found', str(e), status=404))
        self.app.register_error_handler(ApiError, lambda e: error_response(e.code, str(e), status=e.status))
        self.client = self.app.test_client()
        self.frozen = patch('dashboard_actions_service.date', FrozenDate)
        self.frozen.start()
        self.addCleanup(self.frozen.stop)
        with self.app.app_context():
            db = get_db()
            self.portfolio = db.execute("INSERT INTO portfolios(name,current_cash) VALUES ('ETF',1000)").lastrowid
            self.account = db.execute("INSERT INTO budget_accounts(name,balance) VALUES ('Bank',500)").lastrowid
            self.category = db.execute("INSERT INTO budget_categories_v2(name,icon) VALUES ('Bills','House')").lastrowid
            db.commit()

    def tearDown(self):
        self.frozen.stop()
        self.tmp.cleanup()

    def run_sql(self, sql, args=()):
        with self.app.app_context():
            db = get_db()
            result = db.execute(sql, args).lastrowid
            db.commit()
            return result

    def get(self):
        response = self.client.get('/api/dashboard/actions')
        self.assertEqual(response.status_code, 200)
        return response.json['payload']

    def create(self, **values):
        return self.client.post('/api/dashboard/tasks', json={
            'title': 'Check account fees', 'notes': 'Read the fee table', 'category': 'investments',
            'due_date': '2026-10-02', 'priority': 'high',
            'request_id': '00000000-0000-4000-8000-000000000001', **values})

    def bill(self, **changes):
        values = dict(title='Electricity', due_day=31, frequency='MONTHLY', due_month=None, start_month='2026-09', amount=12000)
        values.update(changes)
        return self.run_sql('''INSERT INTO budget_bills_v2
            (title,account_id,category_id,amount_cents,due_day,frequency,due_month,start_month)
            VALUES (?,?,?,?,?,?,?,?)''', (values['title'], self.account, self.category, values['amount'],
                                        values['due_day'], values['frequency'], values['due_month'], values['start_month']))

    def paid_bill(self, bill, month):
        self.run_sql('INSERT INTO budget_bill_payments_v2(bill_id,month,entry_id) VALUES (?,?,999)', (bill, month))

    def journal(self, review_date, status='ACTIVE', archived=0):
        return self.run_sql('''INSERT INTO investor_journal(title,entry_date,kind,status,review_date,is_archived,created_at,updated_at)
            VALUES ('ETF reasoning','2026-01-01','BUY',?,?,?,?,?)''', (status, review_date, archived, '2026-01-01', '2026-01-01'))

    def test_horizon_sorting_and_counts_exclude_closed_and_archived_reviews(self):
        old = self.journal('2026-09-30')
        today = self.journal('2026-10-02')
        self.journal('2026-10-09'); self.journal('2026-11-01'); self.journal('2026-11-02')
        self.journal('2026-09-01', status='CLOSED'); self.journal('2026-09-01', archived=1)
        rows = [r for r in self.get()['items'] if r['source']=='journal']
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['key'], f'journal:{old}')
        self.assertEqual(rows[1]['key'], f'journal:{today}')
        self.assertEqual(rows[0]['timing'], 'overdue')
        self.assertEqual(self.get()['stats']['week'], 2)
        self.assertEqual(self.get()['stats']['overdue'], 1)

    def test_bill_oldest_unpaid_occurrence_clamps_day_and_moves_after_payment(self):
        bill = self.bill()
        row = next(r for r in self.get()['items'] if r['source']=='bill')
        self.assertEqual(row['due_date'], '2026-09-30')
        self.assertIn('month=2026-09', row['href'])
        self.assertEqual(row['amount'], 120)
        self.paid_bill(bill, '2026-09')
        row = next(r for r in self.get()['items'] if r['source']=='bill')
        self.assertEqual(row['due_date'], '2026-10-31')
        self.paid_bill(bill, '2026-10')
        self.assertFalse(any(r['source']=='bill' for r in self.get()['items']))

    def test_paid_deactivated_one_time_and_future_bills_are_not_actions(self):
        paid = self.bill(frequency='ONCE', due_month='2026-09'); self.paid_bill(paid, '2026-09')
        inactive = self.bill(); self.run_sql('UPDATE budget_bills_v2 SET active=0 WHERE id=?', (inactive,))
        self.bill(frequency='ONCE', due_month='2027-01')
        self.bill(start_month='2027-01')
        self.assertFalse(any(r['source']=='bill' for r in self.get()['items']))

    def test_legacy_monthly_bill_does_not_invent_old_occurrences(self):
        self.bill(start_month=None, due_day=1)
        row = next(r for r in self.get()['items'] if r['source']=='bill')
        self.assertEqual(row['due_date'], '2026-10-01')

    def test_recorded_loan_payments_disappear_without_claiming_bank_arrears(self):
        loan = self.run_sql('''INSERT INTO loans(name,original_amount,duration_months,start_date,installment_type)
            VALUES ('Mortgage',12000,24,'2026-01-01','EQUAL')''')
        rows = [r for r in self.get()['items'] if r['source']=='loan']
        self.assertEqual([r['due_date'] for r in rows], ['2026-10-01','2026-11-01'])
        self.assertIn('nie oznacza zaległości', rows[0]['description'])
        self.run_sql('''INSERT INTO loan_installment_payments(loan_id,installment_month,due_date,paid_on,amount_cents)
            VALUES (?,9,'2026-10-01','2026-10-01',50000)''', (loan,))
        rows = [r for r in self.get()['items'] if r['source']=='loan']
        self.assertEqual(len(rows), 1); self.assertEqual(rows[0]['due_date'], '2026-11-01')

    def test_bad_loan_data_reports_partial_workspace_warning(self):
        self.run_sql("INSERT INTO loans(name,original_amount,duration_months,start_date,installment_type) VALUES ('Broken',100,12,'bad-date','EQUAL')")
        data = self.get()
        self.assertEqual(len(data['warnings']), 1)
        self.assertTrue(any(r['source']=='budget_plan' for r in data['items']))

    def test_relevant_radar_import_and_goal_links_only(self):
        self.run_sql("INSERT INTO watchlist(ticker) VALUES ('TEST.L')")
        for ticker in ('TEST.L', 'OLD.L'):
            self.run_sql("INSERT INTO radar_notes(ticker,review_date,updated_at) VALUES (?,'2026-10-02','now')", (ticker,))
        for session, closed in [('open', None), ('closed', 'now')]:
            self.run_sql("INSERT INTO import_sessions(id,portfolio_id,source_file,input_rows,created_at,closed_at) VALUES (?,?,'x.csv',1,'now',?)", (session, self.portfolio, closed))
            self.run_sql("INSERT INTO import_staging(import_session_id,portfolio_id,ticker,type,total_value,date,row_hash,created_at) VALUES (?,?,'ETF','BUY',10,'2026-01-01',?,'now')", (session, self.portfolio, session))
        self.run_sql("INSERT INTO investment_goals(name,target_amount,target_date,created_at,updated_at) VALUES ('Retirement',10000,'2026-10-10','now','now')")
        rows = self.get()['items']
        radar = [r for r in rows if r['source']=='radar']; self.assertEqual(len(radar), 1)
        self.assertEqual(radar[0]['href'], '/radar?ticker=TEST.L')
        imports = [r for r in rows if r['source']=='import']; self.assertEqual(len(imports), 1)
        self.assertIn('import_session=open', imports[0]['href'])
        self.assertEqual(len([r for r in rows if r['source']=='goal']), 1)

    def test_budget_planning_changes_from_unassigned_to_overplanned(self):
        self.assertEqual(next(r for r in self.get()['items'] if r['source']=='budget_plan')['amount'], 500)
        self.run_sql("INSERT INTO budget_plans_v2(month,category_id,amount_cents) VALUES ('2026-10',?,70000)", (self.category,))
        row = next(r for r in self.get()['items'] if r['source']=='budget_plan')
        self.assertEqual(row['amount'], 200); self.assertEqual(row['priority'], 'high')
        self.assertEqual(row['title'], 'Skoryguj plan wydatków')

    def test_manual_retry_edit_conflict_completion_and_restore(self):
        created = self.create(); self.assertEqual(created.status_code, 201)
        task = created.json['payload']['id']
        self.assertEqual(self.create().json['payload']['id'], task)
        self.assertEqual(self.create(title='Changed retry').status_code, 409)
        plan = dict(title='New title', notes='', category='other', due_date=None, priority='normal', version=1)
        self.assertEqual(self.client.put(f'/api/dashboard/tasks/{task}', json=plan).status_code, 200)
        self.assertEqual(self.client.put(f'/api/dashboard/tasks/{task}', json=plan).status_code, 409)
        self.assertEqual(self.client.put(f'/api/dashboard/tasks/{task}/completion', json={'version':1,'completed':True}).status_code,409)
        self.assertEqual(self.client.put(f'/api/dashboard/tasks/{task}/completion', json={'version':2,'completed':True}).status_code,200)
        self.assertEqual(self.get()['stats']['completed'], 1)
        self.assertFalse(any(r['source']=='manual' for r in self.get()['items']))
        self.assertEqual(self.client.put(f'/api/dashboard/tasks/{task}/completion', json={'version':3,'completed':False}).status_code,200)
        manual = next(r for r in self.get()['items'] if r['source']=='manual')
        self.assertEqual(manual['version'], 4); self.assertEqual(manual['timing'], 'unscheduled')

    def test_invalid_requests_rollback_and_missing_task(self):
        for changes in ({'title':' '}, {'notes':1}, {'category':[]}, {'priority':'urgent'}, {'due_date':'2026-2-3'},
                        {'due_date':True}, {'request_id':'bad'}, {'title':'x'*161}):
            with self.subTest(changes=changes):
                self.assertEqual(self.create(**changes).status_code,400)
        self.assertEqual(self.get()['stats']['completed'], 0)
        self.assertFalse(any(r['source']=='manual' for r in self.get()['items']))
        self.assertEqual(self.client.post('/api/dashboard/tasks', json=[]).status_code,400)
        self.assertEqual(self.client.put('/api/dashboard/tasks/999/completion', json={'completed':'yes'}).status_code,400)
        self.assertEqual(self.client.put('/api/dashboard/tasks/999/completion', json={'completed':True,'version':1}).status_code,404)

    def test_action_reads_and_manual_tasks_preserve_financial_records(self):
        tables = ('portfolios','holdings','transactions','budget_accounts','budget_entries_v2','loans','loan_installment_payments','investor_journal')
        def snapshot():
            with self.app.app_context():
                return {table:[tuple(r) for r in get_db().execute(f'SELECT * FROM {table} ORDER BY rowid')] for table in tables}
        before = snapshot()
        with patch('price_service.PriceService.get_prices', side_effect=AssertionError('Must not fetch prices')):
            self.get(); self.create(); self.get()
        self.assertEqual(before, snapshot())


if __name__ == '__main__':
    unittest.main()
