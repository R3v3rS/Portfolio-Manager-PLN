import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from flask import Flask
from database import get_db, init_db, reset_budget_data
from budget_summary_service import monthly_budget_totals
import budget_reserves_service as reserves
import budget_accounts_service as accounts
from routes_budget_accounts import accounts_bp
from tests import test_budget_reserves as fixtures


class BudgetAccountsTest(unittest.TestCase):
    result=fixtures.BudgetReservesTest.result
    create=fixtures.BudgetReservesTest.create
    item=fixtures.BudgetReservesTest.item
    move=fixtures.BudgetReservesTest.move

    def setUp(self):
        fixtures.BudgetReservesTest.setUp(self)
        self.app.register_blueprint(accounts_bp,url_prefix='/api/budget/accounts')
        self.other=get_db().execute("INSERT INTO budget_accounts (name,balance,currency) VALUES ('Oszczędnościowe',2000,'PLN')").lastrowid
        get_db().commit()
        patcher=patch('budget_accounts_service.date',fixtures.FrozenDate);patcher.start();self.addCleanup(patcher.stop)

    def transfer(self,amount=100,reserve_id=None,**extra):
        db=get_db()
        data=dict(source_account_id=self.account,target_account_id=self.other,amount=amount,date=fixtures.FrozenDate.today().isoformat(),
            notes='',move_money=True,reserve_id=reserve_id,request_id=str(uuid4()),
            source_balance=db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],
            target_balance=db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.other,)).fetchone()[0])
        if reserve_id is not None:data['version']=self.item(reserve_id)['version']
        data.update(extra)
        return self.client.post('/api/budget/accounts/transfers',json=data)

    def reconcile(self,balance,**extra):
        data=dict(balance=balance,expected_balance=get_db().execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],notes='Sprawdzono w banku',request_id=str(uuid4()))
        data.update(extra)
        return self.client.post(f'/api/budget/accounts/{self.account}/reconcile',json=data)

    def balances(self):
        return [r[0] for r in get_db().execute('SELECT balance FROM budget_accounts ORDER BY id')]

    def test_internal_transfer_preserves_total_and_is_not_income_or_expense(self):
        self.result(self.transfer(500),201)
        self.assertEqual(self.balances(),[9500,2500])
        totals=monthly_budget_totals(get_db(),'2026-10')
        self.assertEqual((totals['balance'],totals['income'],totals['spent']),(12000,0,0))
        self.assertEqual(accounts.workspace()['history'][0]['kind'],'TRANSFER')

    def test_partial_reserve_transfer_preserves_plan_and_funding_state(self):
        goal=self.create();self.result(self.move(goal,'ADD',600),201)
        before=self.item(goal)
        self.result(self.transfer(250,goal),201)
        after=self.item(goal)
        self.assertEqual(self.balances(),[9750,2250])
        for key in ('saved','monthly_required','months_left','funded_this_month','next_contribution_date'):
            self.assertEqual(after[key],before[key])
        self.assertEqual([(r['account_id'],r['amount']) for r in after['locations']],[(self.account,350),(self.other,250)])
        self.assertEqual(reserves.reserved_cents(get_db(),self.account),35000)
        self.assertEqual(reserves.reserved_cents(get_db(),self.other),25000)
        self.assertEqual(reserves.reserved_cents(get_db()),60000)
        self.assertEqual(accounts.workspace()['accounts'][1]['allocations'][0]['amount'],250)

    def test_location_only_changes_earmarks_and_checks_target_backing(self):
        goal=self.create();self.result(self.move(goal,'ADD',3000),201)
        self.assertEqual(self.transfer(2000.01,goal,move_money=False).status_code,400)
        self.result(self.transfer(700,goal,move_money=False),201)
        self.assertEqual(self.balances(),[10000,2000])
        self.assertEqual(self.item(goal)['saved'],3000)
        self.assertEqual(accounts.workspace()['history'][0]['kind'],'LOCATION')
        self.assertEqual(self.transfer(1,move_money=False).status_code,400)

    def test_free_transfer_cannot_consume_reserves_and_reserve_amount_is_checked(self):
        goal=self.create();self.result(self.move(goal,'ADD',9900),201)
        self.assertEqual(self.transfer(100.01).status_code,400)
        self.assertEqual(self.transfer(9900.01,goal).status_code,400)
        self.assertEqual(self.balances(),[10000,2000])
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_account_transfers').fetchone()[0],0)

    def test_retries_versions_and_stale_balances_are_safe(self):
        token=str(uuid4())
        self.result(self.transfer(100,request_id=token,source_balance=10000,target_balance=2000),201)
        self.result(self.transfer(100,request_id=token,source_balance=10000,target_balance=2000),201)
        self.assertEqual(self.balances(),[9900,2100])
        self.assertEqual(self.transfer(101,request_id=token).status_code,409)
        self.assertEqual(self.transfer(10,source_balance=10000).status_code,409)
        goal=self.create();self.result(self.move(goal,'ADD',50),201)
        self.assertEqual(self.transfer(1,goal,version=1).status_code,409)
        self.assertFalse(get_db().in_transaction)

    def test_reconciliation_is_explicit_idempotent_and_preserves_previous_period(self):
        token=str(uuid4())
        self.result(self.reconcile(9200,request_id=token,expected_balance=10000),201)
        self.result(self.reconcile(9200,request_id=token,expected_balance=10000),201)
        self.assertEqual(self.balances(),[9200,2000])
        self.assertEqual(monthly_budget_totals(get_db(),'2026-09')['to_plan'],12000)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['to_plan'],11200)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        from monthly_report_service import _budget
        report=_budget(get_db(),date(2026,10,1),date(2026,10,31))
        self.assertEqual((report['income'],report['expenses'],report['balance_adjustments'],report['balance_checks']),(0,0,-800,1))
        self.assertEqual(self.reconcile(9100,expected_balance=10000).status_code,409)

    def test_difference_requires_reason_and_inadequate_reserves_raise_warning(self):
        goal=self.create();self.result(self.move(goal,'ADD',500),201)
        self.assertEqual(self.reconcile(200,notes='').status_code,400)
        self.result(self.reconcile(200),201)
        self.assertTrue(accounts.workspace()['warnings'])
        self.assertEqual(self.item(goal)['saved'],500)
        self.assertEqual(self.transfer(100,goal).status_code,400)
        self.result(self.transfer(100,goal,move_money=False),201)
        self.assertEqual(self.balances(),[200,2000])

    def test_zero_difference_confirms_balance(self):
        self.result(self.reconcile(10000,notes=''),201)
        workspace=accounts.workspace()
        self.assertEqual(workspace['accounts'][0]['verified_on'],'2026-10-02')
        self.assertEqual(workspace['history'][0]['amount'],0)

    def test_multi_account_contributions_release_and_changing_default_keep_locations(self):
        goal=self.create();self.result(self.move(goal,'ADD',300),201)
        self.result(self.move(goal,'ADD',200,account_id=self.other),201)
        self.assertEqual(self.move(goal,'RELEASE',201,account_id=self.other).status_code,400)
        self.result(self.move(goal,'RELEASE',50,account_id=self.other),201)
        item=self.item(goal)
        plan={k:item[k] for k in ('name','notes','account_id','target_amount','due_date','frequency')}
        plan.update(account_id=self.other,version=item['version'])
        self.result(self.client.put(f'{self.base}/{goal}',json=plan))
        self.assertEqual(self.item(goal)['locations'],item['locations'])
        self.assertEqual(self.item(goal)['saved'],450)

    def test_multi_account_payment_books_one_expense_and_releases_earmarks(self):
        goal=self.create(frequency='ONCE');self.result(self.move(goal,'ADD',300),201)
        self.result(self.move(goal,'ADD',500,account_id=self.other),201)
        token=str(uuid4());version=self.item(goal)['version']
        self.result(self.move(goal,'SPEND',700,account_id=self.other,request_id=token,version=version),201)
        self.result(self.move(goal,'SPEND',700,account_id=self.other,request_id=token,version=version),201)
        self.assertEqual(self.balances(),[10000,1300])
        self.assertEqual(self.item(goal)['locations'],[])
        self.assertEqual(self.item(goal)['saved'],0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)
        self.assertEqual(sum(m['expense_amount'] or 0 for m in self.item(goal)['movements']),700)

    def test_payment_does_not_borrow_other_reserves_on_paying_account(self):
        goal=self.create();other=self.create(name='Inna')
        self.result(self.move(goal,'ADD',1000),201)
        self.result(self.move(other,'ADD',1900,account_id=self.other),201)
        self.assertEqual(self.move(goal,'SPEND',500,account_id=self.other).status_code,400)
        self.assertEqual(self.balances(),[10000,2000])

    def test_annual_payment_consumes_locations_once_and_leaves_surplus(self):
        goal=self.create();self.result(self.move(goal,'ADD',600),201)
        self.result(self.move(goal,'ADD',500,account_id=self.other),201)
        self.result(self.move(goal,'SPEND',800,account_id=self.other),201)
        item=self.item(goal)
        self.assertEqual((item['saved'],item['cycle']),(300,2))
        self.assertEqual(item['locations'],[dict(account_id=self.account,account_name='Konto',amount=300)])
        self.assertFalse(item['funded_this_month'])
        self.assertEqual(self.balances(),[10000,1200])

    def test_return_transfer_preserves_locations_and_foreign_currency_is_rejected(self):
        goal=self.create();self.result(self.move(goal,'ADD',500),201)
        self.result(self.transfer(200,goal),201)
        self.result(self.transfer(200,goal,source_account_id=self.other,target_account_id=self.account,source_balance=2200,target_balance=9800),201)
        self.assertEqual(self.balances(),[10000,2000])
        self.assertEqual(self.item(goal)['locations'],[dict(account_id=self.account,account_name='Konto',amount=500)])
        db=get_db();foreign=db.execute("INSERT INTO budget_accounts (name,balance,currency) VALUES ('USD',1000,'USD')").lastrowid;db.commit()
        self.assertEqual(self.transfer(target_account_id=foreign,target_balance=1000).status_code,400)
        self.assertEqual(self.item(goal)['saved'],500)

    def test_failed_transfer_rolls_back_both_balances_and_history(self):
        goal=self.create();self.result(self.move(goal,'ADD',500),201)
        with patch('budget_accounts_service._now',return_value=None):
            with self.assertRaises(Exception):accounts.transfer(dict(source_account_id=self.account,target_account_id=self.other,
                amount=100,date='2026-10-02',notes='',move_money=True,reserve_id=goal,version=self.item(goal)['version'],
                source_balance=10000,target_balance=2000,request_id=str(uuid4())))
        self.assertEqual(self.balances(),[10000,2000])
        self.assertEqual(self.item(goal)['saved'],500)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_account_transfers').fetchone()[0],0)

    def test_validation_chronology_creation_retry_and_reset(self):
        for fields in ({'source_account_id':self.other},{'amount':True},{'amount':float('inf')},{'date':'2026-10-03'},{'move_money':'yes'}):
            with self.subTest(fields=fields):self.assertEqual(self.transfer(**fields).status_code,400)
        self.result(self.reconcile(10000),201)
        self.assertEqual(self.transfer(date='2026-10-01').status_code,400)
        data=dict(name='Gotówka',balance=50,request_id=str(uuid4()))
        first=self.result(self.client.post('/api/budget/accounts/',json=data),201)
        self.assertEqual(first,self.result(self.client.post('/api/budget/accounts/',json=data),201))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_accounts').fetchone()[0],3)
        reset_budget_data()
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_account_reconciliations').fetchone()[0],0)

    def test_existing_movements_migrate_to_original_account(self):
        goal=self.create();self.result(self.move(goal,'ADD',200),201)
        get_db().execute('ALTER TABLE budget_reserve_movements DROP COLUMN account_id');get_db().commit()
        migration_app=Flask('migration');migration_app.config['DATABASE']=self.app.config['DATABASE']
        init_db(migration_app)
        self.assertEqual(self.item(goal)['locations'],[dict(account_id=self.account,account_name='Konto',amount=200)])


if __name__=='__main__':unittest.main()
