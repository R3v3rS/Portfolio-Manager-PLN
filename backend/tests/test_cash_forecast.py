import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4
from flask import Flask
from database import get_db,reset_budget_data
from tests import test_budget_reserves as fixtures
from routes_cash_forecast import forecast_bp
import cash_forecast_service as service
import expected_income_service as incomes
from routes_budget_workspace import insert_entry


class CashForecastTest(unittest.TestCase):
    result=fixtures.BudgetReservesTest.result
    create_reserve=fixtures.BudgetReservesTest.create
    item=fixtures.BudgetReservesTest.item
    move=fixtures.BudgetReservesTest.move

    def setUp(self):
        fixtures.BudgetReservesTest.setUp(self)
        self.app.register_blueprint(forecast_bp,url_prefix='/api/budget/forecast')
        fixtures.FrozenDate.current=date(2026,10,3)
        for module in ('cash_forecast_service','expected_income_service'):
            patcher=patch(module+'.date',fixtures.FrozenDate);patcher.start();self.addCleanup(patcher.stop)
        self.url='/api/budget/forecast'

    def forecast(self,**options):return service.workspace(options)

    def income(self,**extra):
        data=dict(name='Pensja',account_id=self.account,amount=3000,start_date='2026-10-10',end_date=None,frequency='MONTHLY',request_id=str(uuid4()))
        data.update(extra)
        return self.result(self.client.post(self.url+'/incomes',json=data),201)['id']

    def receipt(self,income_id,**extra):
        row=get_db().execute('SELECT version FROM budget_expected_incomes WHERE id=?',(income_id,)).fetchone()
        data=dict(occurrence_date='2026-10-10',amount=2800,date='2026-10-03',version=row[0],request_id=str(uuid4()));data.update(extra)
        return self.client.post(f'{self.url}/incomes/{income_id}/receive',json=data)

    def bill(self,**extra):
        values=dict(title='Internet',account_id=self.account,category_id=self.category,amount=100,due_day=15,frequency='MONTHLY',start_month='2026-10');values.update(extra)
        return self.result(self.client.post('/api/budget/workspace/bills',json=values),201)['id']

    def loan(self,**extra):
        db=get_db();values=dict(name='Kredyt',original_amount=12000,duration_months=12,start_date='2026-09-10',installment_type='EQUAL');values.update(extra)
        keys=','.join(values);marks=','.join('?' for _ in values)
        loan_id=db.execute(f'INSERT INTO loans ({keys}) VALUES ({marks})',tuple(values.values())).lastrowid
        db.execute('INSERT INTO loan_rates (loan_id,interest_rate,valid_from_date) VALUES (?,0,?)',(loan_id,values['start_date']));db.commit();return loan_id

    def test_exact_horizons_and_planned_income_does_not_write_cash(self):
        self.income();self.bill()
        result=self.forecast()
        self.assertEqual([(s['days'],s['date']) for s in result['summaries']],[(30,'2026-11-02'),(90,'2027-01-01'),(365,'2027-10-03')])
        self.assertEqual([s['balance'] for s in result['summaries']],[12900,18700,44800])
        self.assertEqual(len(result['points']),366)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)

    def test_missing_accounts_have_no_fabricated_balance(self):
        get_db().execute('DELETE FROM budget_accounts');get_db().commit()
        result=self.forecast()
        self.assertTrue(all(s['balance'] is None for s in result['summaries']))
        self.assertTrue(result['warnings'])

    def test_receipt_books_once_and_removes_only_that_planned_occurrence(self):
        income=self.income();token=str(uuid4())
        first=self.result(self.receipt(income,request_id=token,version=1),201)
        self.assertEqual(first,self.result(self.receipt(income,request_id=token,version=1),201))
        forecast=self.forecast()
        self.assertEqual(forecast['opening']['balance'],12800)
        self.assertEqual(forecast['summaries'][0]['totals']['INCOME'],0)
        self.assertEqual(forecast['summaries'][1]['totals']['INCOME'],6000)
        self.assertEqual(self.receipt(income,request_id=token,version=1,amount=2799).status_code,409)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)

    def test_linking_existing_income_does_not_duplicate_and_delete_reopens_plan(self):
        income=self.income();db=get_db()
        entry=insert_entry(db,dict(account_id=self.account,kind='INCOME',amount_cents=250000,date='2026-10-03',description='Pensja',merchant=None,lines=[]));db.commit()
        self.result(self.receipt(income,existing_entry_id=entry),201)
        self.assertEqual(self.forecast()['opening']['balance'],12500)
        self.assertEqual(self.forecast()['summaries'][0]['totals']['INCOME'],0)
        self.assertEqual(self.client.put(f'/api/budget/workspace/entries/{entry}',json={}).status_code,400)
        self.result(self.client.delete(f'/api/budget/workspace/entries/{entry}'))
        self.assertEqual(self.forecast()['opening']['balance'],10000)
        self.assertEqual(self.forecast()['summaries'][0]['totals']['INCOME'],3000)

    def test_overdue_income_is_not_assumed_and_monthly_day_recovers_after_february(self):
        income=self.income(start_date='2026-10-03')
        fixtures.FrozenDate.current=date(2026,10,4)
        forecast=self.forecast()
        self.assertTrue(forecast['incomes'][0]['overdue'])
        self.assertFalse(any(e['kind']=='INCOME' and e['scheduled_date']=='2026-10-03' for e in forecast['events']))
        row=dict(start_date='2027-01-31',end_date=None,frequency='MONTHLY')
        self.assertEqual(list(incomes.occurrences(row,'2027-01-01','2027-04-30')),['2027-01-31','2027-02-28','2027-03-31','2027-04-30'])
        self.assertEqual(self.receipt(income,occurrence_date='2026-10-05').status_code,400)

    def test_future_booked_entries_are_undone_and_projected_once_with_daily_plan(self):
        db=get_db()
        insert_entry(db,dict(account_id=self.account,kind='INCOME',amount_cents=50000,date='2026-10-20',description='Future income',merchant=None,lines=[]))
        insert_entry(db,dict(account_id=self.account,kind='EXPENSE',amount_cents=10000,date='2026-10-21',description='Future expense',merchant=None,
            lines=[dict(category_id=self.category,amount_cents=10000,label='')]));db.commit()
        result=self.forecast(variable_monthly=300)
        self.assertEqual(result['opening']['balance'],10000)
        end=next(p for p in result['points'] if p['date']=='2026-10-31')
        self.assertEqual(end['balance'],10200)
        self.assertEqual(sum(e['amount'] for e in result['events'] if e['kind']=='DAILY' and e['date']<='2026-10-31'),200)

    def test_paid_bills_and_loan_installments_are_not_counted_twice(self):
        bill=self.bill(due_day=10);loan=self.loan()
        db=get_db()
        db.execute('INSERT INTO loan_installment_payments (loan_id,installment_month,due_date,paid_on,amount_cents) VALUES (?,1,?,?,100000)',(loan,'2026-10-10','2026-10-03'));db.commit()
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03')),201)
        result=self.forecast()
        self.assertEqual(result['opening']['balance'],9900)
        self.assertEqual(result['summaries'][0]['totals']['BILL'],0)
        self.assertEqual(result['summaries'][0]['totals']['LOAN'],0)
        self.assertEqual(result['summaries'][1]['totals']['LOAN'],2000)

    def test_legacy_future_paid_bill_is_counted_once_but_new_future_payment_is_rejected(self):
        bill=self.bill(due_day=10)
        self.assertEqual(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-11',date='2026-11-10')).status_code,400)
        db=get_db()
        entry=insert_entry(db,dict(account_id=self.account,kind='EXPENSE',amount_cents=10000,date='2026-11-10',description='Dawny wpis',merchant=None,lines=[dict(category_id=self.category,amount_cents=10000,label='')]))
        db.execute('INSERT INTO budget_bill_payments_v2(bill_id,month,entry_id) VALUES(?,?,?)',(bill,'2026-11',entry));db.commit()
        result=self.forecast()
        self.assertEqual(result['opening']['balance'],10000)
        november=[e for e in result['events'] if e['kind']=='BILL' and e['date'][:7]=='2026-11']
        self.assertEqual(len(november),1);self.assertTrue(november[0]['recorded'])

    def test_reserve_deposits_change_available_only_and_expense_is_single_cash_flow(self):
        goal=self.create_reserve(target_amount=600,due_date='2026-11-02',frequency='ONCE')
        result=self.forecast()
        before=next(p for p in result['points'] if p['date']=='2026-10-04')
        self.assertEqual((before['balance'],before['reserved'],before['available']),(10000,600,9400))
        after=result['summaries'][0]
        self.assertEqual((after['balance'],after['reserved'],after['available']),(9400,0,9400))
        self.assertEqual((after['totals']['RESERVE_ADD'],after['totals']['RESERVE_COST']),(600,600))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserve_movements').fetchone()[0],0)

    def test_annual_reserve_advances_simulated_cycle_without_mutating_plan(self):
        goal=self.create_reserve(target_amount=600,due_date='2026-11-15')
        self.result(self.move(goal,'ADD',800),201)
        result=self.forecast();costs=[e for e in result['events'] if e['kind']=='RESERVE_COST']
        self.assertEqual([(e['date'],e['amount']) for e in costs],[('2026-11-15',600)])
        self.assertTrue(any(e['kind']=='RESERVE_ADD' and e['date']>'2026-11-15' for e in result['events']))
        self.assertTrue(all(p['reserved']>=0 for p in result['points']))
        self.assertEqual((self.item(goal)['saved'],self.item(goal)['cycle']),(800,1))

    def test_goal_transfers_are_net_of_booked_funding_and_overlap_is_not_summed(self):
        db=get_db();portfolio=db.execute("INSERT INTO portfolios (name,account_type) VALUES ('Inwestycje','STANDARD')").lastrowid
        for name,monthly in (('Emerytura',500),('Wolność',700)):
            goal=db.execute('''INSERT INTO investment_goals (name,target_amount,target_date,monthly_contribution,created_at,updated_at)
                VALUES (?,100000,'2028-01-01',?,'2026-10-03','2026-10-03')''',(name,monthly)).lastrowid
            db.execute('INSERT INTO investment_goal_portfolios VALUES (?,?)',(goal,portfolio))
        investment=db.execute("""INSERT INTO transactions (portfolio_id,ticker,type,quantity,price,total_value,date)
            VALUES (?,'CASH','DEPOSIT',1,200,200,'2026-10-02')""",(portfolio,)).lastrowid
        budget=db.execute("""INSERT INTO budget_transactions (type,amount,account_id,description,date)
            VALUES ('EXPENSE',200,?,'Wpłata do inwestycji','2026-10-02')""",(self.account,)).lastrowid
        db.execute('''INSERT INTO budget_investment_transfers
            (account_id,portfolio_id,investment_transaction_id,budget_transaction_id,direction,amount_cents,date,description,request_id)
            VALUES (?,?,?,?,'OUT',20000,'2026-10-02','Wpłata do inwestycji','done')''',
            (self.account,portfolio,investment,budget))
        db.execute('UPDATE budget_accounts SET balance=balance-200 WHERE id=?',(self.account,));db.commit()
        result=self.forecast()
        self.assertEqual(result['summaries'][0]['totals']['GOAL'],500)
        self.assertEqual(result['summaries'][1]['totals']['GOAL'],1900)
        self.assertTrue(any('wspólnymi portfelami' in w for w in result['warnings']))

    def test_scenarios_exclusions_minimum_and_buffer(self):
        income=self.income();bill=self.bill(amount=11000)
        result=self.forecast(income_percent=80,buffer=2000)
        self.assertEqual(result['summaries'][0]['balance'],1400)
        self.assertEqual(result['summaries'][0]['first_below_buffer'],'2026-10-15')
        self.assertEqual(result['summaries'][0]['minimum'],1400)
        excluded=self.forecast(excluded=f'bill:{bill},income:{income}')
        self.assertEqual(excluded['summaries'][0]['balance'],10000)
        self.assertFalse(any(e['kind'] in ('INCOME','BILL') for e in excluded['events']))

    def test_variable_budget_excludes_fixed_costs_and_already_spent(self):
        self.bill(amount=200)
        db=get_db();db.execute('INSERT INTO budget_plans_v2 VALUES (?,\'2026-10\',100000)',(self.category,))
        insert_entry(db,dict(account_id=self.account,kind='EXPENSE',amount_cents=10000,date='2026-10-02',description='Zwykłe wydatki',merchant=None,
            lines=[dict(category_id=self.category,amount_cents=10000,label='')]));db.commit()
        result=self.forecast()
        self.assertEqual(result['options']['default_variable_monthly'],800)
        self.assertEqual(sum(e['amount'] for e in result['events'] if e['kind']=='DAILY' and e['date']<='2026-10-31'),700)

    def test_shared_parent_limit_subtracts_child_bills_once_and_future_fallback(self):
        db=get_db()
        child=db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES ('Bilet',?)",(self.category,)).lastrowid
        db.commit()
        self.bill(amount=200,category_id=child)
        db.execute("INSERT INTO budget_plans_v2 VALUES (?,'2026-10',100000)",(self.category,))
        db.execute("INSERT INTO budget_plans_v2 VALUES (?,'2026-10',60000)",(child,));db.commit()
        result=self.forecast()
        self.assertEqual(result['options']['default_variable_monthly'],800)
        self.assertEqual(sum(e['amount'] for e in result['events'] if e['kind']=='DAILY' and e['date']<='2026-10-31'),800)
        self.assertEqual(sum(e['amount'] for e in result['events'] if e['kind']=='DAILY' and e['date'].startswith('2026-11')),800)

    def test_loan_category_moved_below_a_parent_is_subtracted_once(self):
        db=get_db()
        child=db.execute("INSERT INTO budget_categories_v2(name,parent_id) VALUES ('Rachunki',?)",(self.category,)).lastrowid
        db.commit()
        self.bill(amount=100,category_id=child);self.loan()
        db.execute("INSERT INTO budget_plans_v2 VALUES (?,'2026-10',200000)",(self.category,))
        db.execute("INSERT INTO budget_plans_v2 VALUES (?,'2026-10',120000)",(child,));db.commit()
        self.assertEqual(self.forecast()['options']['default_variable_monthly'],900)

    def test_validation_idempotent_creation_and_archive(self):
        token=str(uuid4());income=self.income(request_id=token)
        self.assertEqual(income,self.income(request_id=token))
        for options in ({'income_percent':'NaN'},{'income_percent':201},{'variable_monthly':'Infinity'},{'buffer':-.01},{'excluded':'bad:1'}):
            with self.subTest(options=options):self.assertEqual(self.client.get(self.url,query_string=options).status_code,400)
        self.assertEqual(self.receipt(income,date='2026-10-04').status_code,400)
        self.assertEqual(self.receipt(income,version=99).status_code,409)
        self.result(self.client.put(f'{self.url}/incomes/{income}/active',json=dict(active=False,version=1)))
        self.assertFalse(self.forecast()['events'])
        self.assertEqual(self.receipt(income).status_code,400)

    def test_receipt_failure_rolls_back_income_and_balance_and_reset_clears_plans(self):
        income=self.income()
        with patch('expected_income_service._now',return_value=None):
            with self.assertRaises(Exception):incomes.receive(income,dict(occurrence_date='2026-10-10',amount=3000,date='2026-10-03',version=1,request_id=str(uuid4())))
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        reset_budget_data()
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_expected_incomes').fetchone()[0],0)

    def test_reading_forecast_is_read_only(self):
        self.income();self.bill();self.loan();self.create_reserve()
        db=get_db();before=db.total_changes
        with patch('cash_forecast_service.LoanService.get_loan_rates',wraps=service.LoanService.get_loan_rates):
            self.result(self.client.get(self.url));self.result(self.client.get(self.url))
        self.assertEqual(db.total_changes,before)
        self.assertFalse(db.in_transaction)


    def test_editing_payday_does_not_recreate_a_settled_month(self):
        income=self.income();self.result(self.receipt(income),201)
        data=dict(name='Pensja',account_id=self.account,amount=3200,start_date='2026-10-15',end_date=None,frequency='MONTHLY',version=2)
        self.result(self.client.put(f'{self.url}/incomes/{income}',json=data))
        result=self.forecast()
        self.assertFalse(any(e['kind']=='INCOME' and e['date'].startswith('2026-10') for e in result['events']))
        self.assertEqual(result['incomes'][0]['next_occurrence'],'2026-11-15')
        self.assertEqual(self.receipt(income,occurrence_date='2026-10-15').status_code,409)
        self.assertEqual(self.client.put(f'{self.url}/incomes/{income}',json=dict(data,frequency='ONCE',version=3)).status_code,400)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],12800)

    def test_missing_loan_rate_warns_and_does_not_guess_an_installment(self):
        loan=self.loan();db=get_db();db.execute('DELETE FROM loan_rates WHERE loan_id=?',(loan,));db.commit()
        result=self.forecast()
        self.assertFalse(any(e['kind']=='LOAN' for e in result['events']))
        self.assertTrue(any('brak pełnego harmonogramu lub oprocentowania' in w for w in result['warnings']))


if __name__=='__main__':unittest.main()
