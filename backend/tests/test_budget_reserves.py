import os
import tempfile
import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from flask import Flask
from api.exceptions import ApiError, NotFoundError, ValidationError
from api.response import error_response
from database import get_db, init_db, reset_budget_data
from routes_budget_reserves import reserves_bp
from routes_budget_workspace import workspace_bp
from budget_summary_service import monthly_budget_totals
import budget_reserves_service as service


class FrozenDate(date):
    current = date(2026,10,2)

    @classmethod
    def today(cls):
        return cls.current


class BudgetReservesTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app=Flask(__name__)
        self.app.config.update(TESTING=True,DATABASE=os.path.join(self.temp.name,'reserves.db'))
        self.app.register_blueprint(reserves_bp,url_prefix='/api/budget/reserves')
        self.app.register_blueprint(workspace_bp,url_prefix='/api/budget/workspace')
        for cls,status in ((ValidationError,400),(NotFoundError,404)):
            self.app.register_error_handler(cls,lambda error,status=status:error_response('invalid',error.message,status=status))
        self.app.register_error_handler(ApiError,lambda error:error_response(error.code,error.message,status=error.status))
        init_db(self.app)
        self.ctx=self.app.app_context();self.ctx.push();self.addCleanup(self.ctx.pop)
        db=get_db()
        self.account=db.execute("INSERT INTO budget_accounts (name,balance,currency) VALUES ('Konto',10000,'PLN')").lastrowid
        self.category=db.execute("INSERT INTO budget_categories_v2 (name) VALUES ('Ubezpieczenia')").lastrowid
        db.commit()
        self.client=self.app.test_client()
        self.base='/api/budget/reserves'
        FrozenDate.current=date(2026,10,2)
        patcher=patch('budget_reserves_service.date',FrozenDate);patcher.start();self.addCleanup(patcher.stop)

    def result(self,response,status=200):
        self.assertEqual(response.status_code,status,response.json)
        return response.json['payload']

    def create(self,**extra):
        data=dict(name='Ubezpieczenie auta',notes='',account_id=self.account,target_amount=2400,
            due_date='2027-09-30',frequency='YEARLY',request_id=str(uuid4()))
        data.update(extra)
        return self.result(self.client.post(self.base,json=data),201)['id']

    def item(self,reserve_id):
        return next(r for r in self.result(self.client.get(self.base))['items'] if r['id']==reserve_id)

    def move(self,reserve_id,kind,amount,**extra):
        data=dict(kind=kind,amount=amount,date=FrozenDate.today().isoformat(),notes='',
            request_id=str(uuid4()),version=self.item(reserve_id)['version'])
        if kind=='SPEND':data['category_id']=self.category
        data.update(extra)
        return self.client.post(f'{self.base}/{reserve_id}/movements',json=data)

    def test_normal_missed_partial_and_large_contributions_recalculate(self):
        exact_year=self.create(due_date='2027-10-02')
        self.assertEqual((self.item(exact_year)['monthly_required'],self.item(exact_year)['months_left']),(200,12))
        first=self.create()
        self.assertEqual((self.item(first)['monthly_required'],self.item(first)['months_left']),(200,12))
        self.result(self.move(first,'ADD',200),201)
        self.assertEqual((self.item(first)['saved'],self.item(first)['monthly_required'],self.item(first)['months_left']),(200,200,11))
        missed=self.create(name='Mieszkanie')
        large=self.create(name='Remont')
        partial=self.create(name='Zakup')
        self.result(self.move(large,'ADD',500),201)
        self.result(self.move(partial,'ADD',50),201)
        self.assertEqual(self.item(large)['monthly_required'],172.73)
        self.assertEqual(self.item(partial)['monthly_required'],213.64)
        FrozenDate.current=date(2026,11,2)
        self.assertEqual(self.item(missed)['monthly_required'],218.19)
        self.assertEqual(self.item(first)['monthly_required'],200)

    def test_earmarking_does_not_book_an_expense_and_reduces_unplanned_money(self):
        reserve=self.create()
        self.result(self.move(reserve,'ADD',500),201)
        db=get_db()
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        totals=monthly_budget_totals(db,'2026-10')
        self.assertEqual((totals['reserved'],totals['to_plan'],totals['spent']),(500,9500,0))
        self.assertEqual(monthly_budget_totals(db,'2026-09')['reserved'],0)
        self.result(self.move(reserve,'RELEASE',500),201)
        self.assertEqual(self.item(reserve)['monthly_required'],200)
        self.assertEqual(monthly_budget_totals(db,'2026-10')['to_plan'],9800)
        self.assertEqual(monthly_budget_totals(db,'2026-10')['reserve_plan_remaining'],200)

    def test_overallocation_release_and_archiving_are_validated(self):
        first=self.create();second=self.create(name='Inna rezerwa')
        self.result(self.move(first,'ADD',9000),201)
        self.assertEqual(self.move(second,'ADD',1000.01).status_code,400)
        self.assertEqual(self.move(first,'RELEASE',9000.01).status_code,400)
        response=self.client.put(f'{self.base}/{first}/archive',json={'archived':True,'version':self.item(first)['version']})
        self.assertEqual(response.status_code,400)
        self.result(self.move(first,'RELEASE',9000),201)
        self.result(self.client.put(f'{self.base}/{first}/archive',json={'archived':True,'version':self.item(first)['version']}))
        self.assertEqual(self.item(first)['status'],'ARCHIVED')
        self.assertEqual(self.move(first,'ADD',10).status_code,400)

    def test_creation_and_movement_retries_are_idempotent_even_after_versions_change(self):
        token=str(uuid4())
        data=dict(name='Auto',notes='',account_id=self.account,target_amount=2400,due_date='2027-09-30',frequency='ONCE',request_id=token)
        reserve=self.result(self.client.post(self.base,json=data),201)['id']
        self.assertEqual(self.result(self.client.post(self.base,json=data),201)['id'],reserve)
        token=str(uuid4());version=self.item(reserve)['version']
        self.result(self.move(reserve,'ADD',200,request_id=token,version=version),201)
        self.result(self.move(reserve,'ADD',200,request_id=token,version=version),201)
        self.assertEqual(self.item(reserve)['saved'],200)
        self.assertEqual(self.move(reserve,'ADD',201,request_id=token,version=version).status_code,409)
        self.assertEqual(self.move(reserve,'ADD',10,version=version).status_code,409)
        self.assertFalse(get_db().in_transaction)

    def test_one_time_payment_books_once_and_releases_surplus(self):
        reserve=self.create(frequency='ONCE')
        self.result(self.move(reserve,'ADD',3000),201)
        token=str(uuid4());version=self.item(reserve)['version']
        paid=self.result(self.move(reserve,'SPEND',2400,request_id=token,version=version),201)
        self.assertEqual(self.result(self.move(reserve,'SPEND',2400,request_id=token,version=version),201),paid)
        item=self.item(reserve)
        self.assertEqual((item['status'],item['saved'],item['monthly_required']),('COMPLETED',0,0))
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],7600)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)
        self.assertEqual(item['movements'][0]['expense_amount'],2400)
        self.assertEqual(item['movements'][0]['amount'],3000)
        for method in ('put','delete'):
            response=getattr(self.client,method)(f'/api/budget/workspace/entries/{paid["budget_entry_id"]}',json={})
            self.assertEqual(response.status_code,400)

    def test_yearly_payment_carries_surplus_and_keeps_prior_cycle_history(self):
        reserve=self.create(due_date='2026-11-15')
        self.result(self.move(reserve,'ADD',3000),201)
        FrozenDate.current=date(2026,11,15)
        self.result(self.move(reserve,'SPEND',2400),201)
        item=self.item(reserve)
        self.assertEqual((item['cycle'],item['due_date'],item['saved'],item['status']),(2,'2027-11-15',600,'ACTIVE'))
        self.assertEqual(item['remaining'],1800)
        self.assertEqual(item['movements'][0]['cycle'],1)
        self.result(self.move(reserve,'ADD',100),201)
        self.assertEqual(self.item(reserve)['movements'][0]['cycle'],2)

    def test_payment_cannot_use_other_reserves_and_errors_roll_back(self):
        reserve=self.create();other=self.create(name='Inne')
        self.result(self.move(other,'ADD',9000),201)
        self.assertEqual(self.move(reserve,'SPEND',2000).status_code,400)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(self.move(reserve,'SPEND',500,category_id=9999).status_code,404)

    def test_insufficient_backing_is_explicit_without_rewriting_recorded_savings(self):
        reserve=self.create()
        self.result(self.move(reserve,'ADD',500),201)
        get_db().execute('UPDATE budget_accounts SET balance=100');get_db().commit()
        result=self.result(self.client.get(self.base))
        self.assertEqual(result['accounts'][0]['available'],-400)
        self.assertTrue(result['warnings'])
        self.assertEqual(self.item(reserve)['saved'],500)
        self.assertEqual(self.move(reserve,'ADD',1).status_code,400)

    def test_due_now_or_overdue_has_no_division_by_zero_and_overfunded_needs_nothing(self):
        reserve=self.create(due_date='2026-10-10')
        self.result(self.move(reserve,'ADD',50),201)
        item=self.item(reserve)
        self.assertEqual((item['months_left'],item['urgent'],item['monthly_required']),(0,True,2350))
        FrozenDate.current=date(2026,11,2)
        self.assertTrue(self.item(reserve)['overdue'])
        self.result(self.move(reserve,'ADD',2400),201)
        self.assertEqual((self.item(reserve)['remaining'],self.item(reserve)['monthly_required'],self.item(reserve)['surplus']),(0,0,50))

    def test_invalid_amounts_dates_foreign_currency_and_account_changes_are_rejected(self):
        reserve=self.create()
        for invalid in (True,'NaN','Infinity','1e100000',-1,0,0.001):
            with self.subTest(amount=invalid):
                self.assertEqual(self.move(reserve,'ADD',invalid).status_code,400)
        self.assertEqual(self.move(reserve,'ADD',5,date='2026-10-03').status_code,400)
        self.assertEqual(self.move(reserve,'ADD',5,date='2026-09-30').status_code,400)
        self.result(self.move(reserve,'ADD',20),201)
        other=get_db().execute("INSERT INTO budget_accounts (name,balance,currency) VALUES ('USD',10000,'USD')").lastrowid;get_db().commit()
        data=dict(name='Auto',notes='',account_id=other,target_amount=2400,due_date='2027-09-30',frequency='ONCE',version=self.item(reserve)['version'])
        self.assertEqual(self.client.put(f'{self.base}/{reserve}',json=data).status_code,400)
        self.assertEqual(self.client.post(self.base,json=dict(data,request_id=str(uuid4()))).status_code,400)

    def test_leap_year_recurrence_and_budget_reset(self):
        reserve=self.create(due_date='2028-02-29')
        row=get_db().execute('SELECT * FROM budget_reserves WHERE id=?',(reserve,)).fetchone()
        self.assertEqual(service._next_year(row,date(2028,2,29)),'2029-02-28')
        self.result(self.move(reserve,'ADD',200),201)
        reset_budget_data()
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserves').fetchone()[0],0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserve_movements').fetchone()[0],0)

    def test_dashboard_links_to_due_contributions_and_completed_saving_plan(self):
        from dashboard_actions_service import workspace as actions
        reserve=self.create()
        with patch('dashboard_actions_service.date',FrozenDate):
            reminder=next(r for r in actions()['items'] if r['source']=='reserve')
        self.assertEqual((reminder['amount'],reminder['due_date'],reminder['href']),(200,'2026-10-02',f'/budget/reserves?reserve={reserve}'))
        self.result(self.move(reserve,'ADD',2400),201)
        with patch('dashboard_actions_service.date',FrozenDate):
            self.assertFalse(any(r['source']=='reserve' for r in actions()['items']))

    def test_settlement_failure_after_inserting_expense_rolls_back_everything(self):
        reserve=self.create()
        self.result(self.move(reserve,'ADD',500),201)
        with patch('budget_reserves_service._next_year',side_effect=ValidationError('Błąd kolejnego terminu')):
            self.assertEqual(self.move(reserve,'SPEND',500).status_code,400)
        self.assertEqual(self.item(reserve)['saved'],500)
        self.assertEqual(self.item(reserve)['cycle'],1)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)


if __name__=='__main__':
    unittest.main()
