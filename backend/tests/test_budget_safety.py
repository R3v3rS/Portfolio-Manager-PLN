import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from database import get_db
from routes_budget_imports import imports_bp
from routes_budget_workspace import insert_entry
from tests import test_budget_planning as planning
from tests import test_budget_imports as imports
from tests import test_budget_reserves as reserves
from tests import test_cash_forecast as forecast_fixtures


class BudgetSafetyTest(unittest.TestCase):
    result=planning.BudgetPlanningTest.result
    create_reserve=planning.BudgetPlanningTest.create_reserve
    item=planning.BudgetPlanningTest.item
    move=planning.BudgetPlanningTest.move
    income=planning.BudgetPlanningTest.income
    bill=planning.BudgetPlanningTest.bill
    forecast=planning.BudgetPlanningTest.forecast
    get_workspace=planning.BudgetPlanningTest.get_workspace
    plan=planning.BudgetPlanningTest.plan
    expense=planning.BudgetPlanningTest.expense
    loan=forecast_fixtures.CashForecastTest.loan
    stage=imports.BudgetImportTest.stage
    commit=imports.BudgetImportTest.commit
    rule=imports.BudgetImportTest.rule

    def setUp(self):
        planning.BudgetPlanningTest.setUp(self)
        self.app.register_blueprint(imports_bp,url_prefix='/api/budget/imports')
        self.url='/api/budget/imports'
        for module in ('budget_refunds_service','budget_bank_import_service','budget_summary_service'):
            p=patch(module+'.date',reserves.FrozenDate);p.start();self.addCleanup(p.stop)

    def refund(self,purchase,amount=40,**extra):
        db=get_db()
        data=dict(amount=amount,date='2026-10-03',account_id=self.account,category_id=self.category,
            balance_mode='APPLY',expected_balance=db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],
            version=db.execute('SELECT version FROM budget_entries_v2 WHERE id=?',(purchase,)).fetchone()[0],request_id=str(uuid4()))
        data.update(extra)
        return self.client.post(f'/api/budget/workspace/entries/{purchase}/refunds',json=data),data

    def test_refund_reduces_expenses_and_category_without_creating_income(self):
        purchase=self.expense(100,day='2026-10-02')
        response,data=self.refund(purchase)
        refund=self.result(response,201)['id']
        self.result(self.client.post(f'/api/budget/workspace/entries/{purchase}/refunds',json=data),201)
        w=self.get_workspace()
        self.assertEqual((w['totals']['balance'],w['totals']['spent'],w['totals']['income'],w['totals']['refunds']),(9940,60,0,40))
        self.assertEqual(w['categories'][0]['spent'],60)
        self.assertEqual(w['totals']['period_spending']['spent'],60)
        self.assertEqual(next(e for e in w['entries'] if e['id']==refund)['kind'],'REFUND')
        self.assertEqual(self.client.delete(f'/api/budget/workspace/entries/{purchase}').status_code,400)
        self.assertEqual(self.refund(purchase,61)[0].status_code,400)
        self.result(self.client.delete(f'/api/budget/workspace/entries/{refund}'))
        self.assertEqual(self.get_workspace()['totals']['spent'],100)
        self.assertEqual(self.get_workspace()['totals']['balance'],9900)

    def test_refund_from_older_month_reduces_this_month_not_the_purchase_month(self):
        purchase=self.expense(100,day='2026-09-30')
        self.result(self.refund(purchase,25)[0],201)
        self.assertEqual(self.get_workspace('2026-09')['totals']['spent'],100)
        self.assertEqual((self.get_workspace()['totals']['spent'],self.get_workspace()['totals']['income']),(-25,0))

    def test_imported_refund_is_reclassified_without_second_credit(self):
        purchase=self.expense(100,day='2026-10-02');db=get_db()
        income=insert_entry(db,dict(account_id=self.account,kind='INCOME',amount_cents=4000,date='2026-10-03',description='Zwrot sklepu',merchant=None,lines=[]));db.commit()
        self.assertEqual(self.get_workspace()['totals']['income'],40)
        self.result(self.refund(purchase,existing_entry_id=income,entry_version=1)[0],201)
        self.assertEqual((self.get_workspace()['totals']['balance'],self.get_workspace()['totals']['income']),(9940,0))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],2)

    def test_stale_balance_and_invalid_refund_do_not_write_anything(self):
        purchase=self.expense(100,day='2026-10-02')
        self.assertEqual(self.refund(purchase,expected_balance=10000)[0].status_code,409)
        self.assertEqual(self.refund(purchase,amount=101)[0].status_code,400)
        self.assertEqual(self.refund(purchase,date='2026-10-01')[0].status_code,400)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)

    def test_bill_match_after_import_does_not_duplicate_spending_or_cash(self):
        bill=self.bill(title='ENEA',amount=250)
        session=self.stage('Data;Opis;Odbiorca;Kwota;Waluta;ID\n02.10.2026;Faktura ENEA;ENEA;-250,00;PLN;E1\n',mode='APPLY')
        imported=self.result(self.commit(session)[0]);w=self.get_workspace()
        self.assertEqual(imported['bill_matches'][0]['bill_id'],bill)
        candidate=w['bills'][0]['payment_candidates'][0]
        data=dict(month='2026-10',date=candidate['date'],amount=250,version=w['bills'][0]['version'],request_id=str(uuid4()))
        url=f'/api/budget/workspace/bills/{bill}/pay'
        self.assertEqual(self.client.post(url,json=data).status_code,409)
        data.update(existing_entry_id=candidate['id'],entry_version=candidate['version'])
        first=self.result(self.client.post(url,json=data),201)
        self.assertEqual(first,self.result(self.client.post(url,json=data),201))
        self.assertEqual((self.get_workspace()['totals']['spent'],self.get_workspace()['totals']['balance']),(250,9750))
        self.assertEqual(self.get_workspace()['bills'][0]['status'],'PAID')
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)

    def test_matching_bill_and_reserve_settles_the_existing_expense_once(self):
        reserve=self.create_reserve(target_amount=250,due_date='2026-10-15',frequency='ONCE')
        self.result(self.move(reserve,'ADD',250),201)
        bill=self.bill(title='OC',amount=250,due_day=15,frequency='ONCE',due_month='2026-10',reserve_id=reserve)
        entry=self.expense(250,day='2026-10-03')
        w=self.get_workspace();b=w['bills'][0]
        self.result(self.client.post(f'/api/budget/workspace/bills/{bill}/pay',json=dict(month='2026-10',date='2026-10-03',amount=250,version=b['version'],reserve_version=b['reserve_version'],existing_entry_id=entry,entry_version=1,request_id=str(uuid4()))),201)
        w=self.get_workspace()
        self.assertEqual((w['totals']['spent'],w['totals']['budget_spent'],w['totals']['balance']),(250,250,9750))
        self.assertEqual(w['planning']['month_plan'][2]['done'],250)
        self.assertEqual(w['planning']['month_plan'][1]['done'],0)

    def test_unplanned_and_over_limit_expenses_use_available_money(self):
        db=get_db();db.execute('UPDATE budget_accounts SET balance=1000');db.commit()
        self.expense(100,day='2026-10-02')
        self.assertEqual(self.get_workspace()['totals']['to_plan'],900)
        self.result(self.client.put(f'/api/budget/workspace/plans/{self.category}',json=dict(month='2026-10',amount=50)))
        self.assertEqual(self.get_workspace()['totals']['to_plan'],900)
        self.result(self.client.put(f'/api/budget/workspace/plans/{self.category}',json=dict(month='2026-10',amount=200)))
        self.assertEqual(self.get_workspace()['totals']['to_plan'],800)

    def test_loans_are_in_the_monthly_plan_without_duplicating_manual_caps(self):
        self.loan();db=get_db()
        db.execute('UPDATE budget_categories_v2 SET name=? WHERE id=?',('Rachunki',self.category));db.commit()
        self.result(self.client.put(f'/api/budget/workspace/plans/{self.category}',json=dict(month='2026-10',amount=1000)))
        w=self.get_workspace()
        self.assertEqual((w['totals']['planned'],w['totals']['to_plan']),(1000,9000))
        self.assertEqual(w['planning']['loans'][0]['amount'],1000)
        self.assertEqual(w['planning']['month_plan'][1]['planned'],0)

    def test_automatic_reserve_partial_deposit_matches_forecast_and_explicit_zero(self):
        reserve=self.create_reserve(target_amount=1200,due_date='2027-02-01',frequency='ONCE')
        before=self.get_workspace()['planning']['reserve_plans'][0]
        self.assertEqual((before['automatic'],before['planned'],before['remaining']),(True,300,300))
        self.result(self.move(reserve,'ADD',100),201)
        w=self.get_workspace();r=w['planning']['reserve_plans'][0]
        self.assertEqual((r['planned'],r['funded'],r['remaining'],w['totals']['to_plan']),(300,100,200,9700))
        self.assertEqual(sum(e['amount'] for e in self.forecast()['events'] if e['kind']=='RESERVE_ADD' and e['date'][:7]=='2026-10'),200)
        self.result(self.plan(reserve,amount=0))
        self.assertEqual(self.get_workspace()['totals']['reserve_plan_remaining'],0)
        self.assertFalse(any(e['kind']=='RESERVE_ADD' and e['date'][:7]=='2026-10' for e in self.forecast()['events']))

    def test_spending_in_loan_category_does_not_release_unpaid_installment(self):
        self.loan();db=get_db()
        db.execute('UPDATE budget_categories_v2 SET name=? WHERE id=?',('Rachunki',self.category));db.commit()
        self.expense(100,day='2026-10-02')
        self.assertEqual(self.get_workspace()['totals']['to_plan'],8900)
        self.assertEqual(self.get_workspace()['totals']['remaining_commitments'],1000)

    def test_historical_automatic_plan_retains_missing_contribution_for_closing(self):
        reserves.FrozenDate.current=date(2026,9,2)
        reserve=self.create_reserve(target_amount=2400,due_date='2027-09-01',frequency='ONCE')
        self.result(self.move(reserve,'ADD',100),201)
        reserves.FrozenDate.current=date(2026,10,3)
        review=self.get_workspace('2026-09')['planning']['month_review']
        self.assertEqual(review['missing_reserves'][0]['remaining'],100)

    def test_month_checklist_and_stale_review_prevent_unseen_closing(self):
        self.bill();self.loan();self.create_reserve()
        review=self.get_workspace()['planning']['month_review']
        self.assertEqual((len(review['unpaid_bills']),len(review['unpaid_loans']),len(review['missing_reserves'])),(1,1,1))
        old=self.get_workspace('2026-09')['planning']['month_review']['token']
        self.expense(10,day='2026-09-30')
        response=self.client.post(self.planning+'/close-month',json=dict(month='2026-09',category_versions={},amounts={},request_id=str(uuid4()),review_token=old))
        self.assertEqual(response.status_code,409)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_month_closings').fetchone()[0],0)

    def test_same_rule_is_not_added_twice_and_conflict_requires_manual_choice(self):
        first=self.rule('ENEA');self.assertEqual(self.rule('enea'),first)
        other=get_db().execute("INSERT INTO budget_categories_v2(name) VALUES('Jedzenie')").lastrowid;get_db().commit()
        response=self.client.post(self.url+'/rules',json=dict(pattern='enea',category_id=other,match_field='ANY',match_type='CONTAINS',priority=100,active=True,request_id=str(uuid4())))
        self.result(response,201)
        from budget_category_service import rule_match,rules
        chosen,warnings=rule_match(rules(get_db()),self.account,'ENEA','')
        self.assertIsNone(chosen)
        self.assertTrue(warnings)
