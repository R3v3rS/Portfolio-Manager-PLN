import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from database import get_db, reset_budget_data
from budget_summary_service import monthly_budget_totals
from monthly_report_service import _budget
import budget_bank_import_service as bank
import budget_reserves_service as reserves
from routes_budget_imports import imports_bp
from tests import test_budget_accounts as account_fixtures
from tests import test_budget_imports as import_fixtures
from tests.test_budget_reserves import FrozenDate


class ReserveTransferFundingTest(unittest.TestCase):
    result=account_fixtures.BudgetAccountsTest.result
    create=account_fixtures.BudgetAccountsTest.create
    item=account_fixtures.BudgetAccountsTest.item
    move=account_fixtures.BudgetAccountsTest.move
    transfer=account_fixtures.BudgetAccountsTest.transfer
    balances=account_fixtures.BudgetAccountsTest.balances
    stage=import_fixtures.BudgetImportTest.stage
    commit=import_fixtures.BudgetImportTest.commit

    def setUp(self):
        account_fixtures.BudgetAccountsTest.setUp(self)
        self.app.register_blueprint(imports_bp,url_prefix='/api/budget/imports')
        self.url='/api/budget/imports'
        for module in ('budget_bank_import_service','budget_import_parser'):
            p=patch(module+'.date',FrozenDate);p.start();self.addCleanup(p.stop)

    def transfer_rule(self,goal,pattern='rezerwa OC auta',**extra):
        data=dict(pattern=pattern,source_account_id=self.account,target_account_id=self.other,
                  reserve_id=goal,active=True,request_id=str(uuid4()))
        data.update(extra)
        return self.result(self.client.post(self.url+'/transfer-rules',json=data),201)['id']

    def csv(self,amount=-150,reference='F1',day='02.10.2026',description='BLIK rezerwa OC auta'):
        return f'Data;Opis;Odbiorca;Kwota;Waluta;ID\n{day};{description};Moje konto;{amount};PLN;{reference}\n'

    def test_funding_counts_monthly_cost_and_target_location_without_cash_loss(self):
        goal=self.create()
        self.result(self.transfer(150,goal,reserve_action='FUND'),201)
        self.assertEqual(self.balances(),[9850,2150])
        self.assertEqual(self.item(goal)['saved'],150)
        self.assertEqual(self.item(goal)['locations'],[dict(account_id=self.other,account_name='Oszczędnościowe',amount=150)])
        self.assertTrue(self.item(goal)['funded_this_month'])
        totals=monthly_budget_totals(get_db(),'2026-10')
        self.assertEqual((totals['balance'],totals['spent'],totals['budget_spent'],totals['reserved'],totals['to_plan']),(12000,0,150,150,11800))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)

    def test_retry_and_moving_existing_reserve_do_not_fund_twice(self):
        goal=self.create();token=str(uuid4())
        for _ in range(2):
            self.result(self.transfer(150,goal,reserve_action='FUND',request_id=token,source_balance=10000,target_balance=2000),201)
        self.result(self.transfer(100,goal,source_account_id=self.other,target_account_id=self.account,
                                  source_balance=2150,target_balance=9850),201)
        self.assertEqual(self.item(goal)['saved'],150)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['budget_spent'],150)
        self.assertEqual(reserves.location_cents(get_db(),goal,self.account),10000)
        self.assertEqual(reserves.location_cents(get_db(),goal,self.other),5000)

    def test_later_payment_only_charges_unfunded_difference_and_report_agrees(self):
        goal=self.create();self.result(self.transfer(150,goal,reserve_action='FUND'),201)
        FrozenDate.current=date(2026,11,2)
        self.result(self.move(goal,'SPEND',225,account_id=self.other),201)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['budget_spent'],150)
        nov=monthly_budget_totals(get_db(),'2026-11')
        self.assertEqual((nov['spent'],nov['reserve_settled'],nov['budget_spent']),(225,150,75))
        report=_budget(get_db(),date(2026,11,1),date(2026,11,30))
        self.assertEqual((report['expenses'],report['budget_spent'],report['budget_net']),(225,75,-75))
        self.assertEqual(self.balances(),[9850,1925])
        self.assertEqual(self.item(goal)['saved'],0)

    def test_full_funding_payment_and_surplus_release_are_not_double_costs(self):
        goal=self.create(frequency='ONCE');self.result(self.transfer(150,goal,reserve_action='FUND'),201)
        FrozenDate.current=date(2026,11,2)
        self.result(self.move(goal,'SPEND',100,account_id=self.other),201)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-11')['budget_spent'],-50)
        self.assertEqual(self.item(goal)['saved'],0)
        self.assertEqual(reserves.location_cents(get_db(),goal,self.other),0)

    def test_annual_payment_covered_in_full_has_zero_new_budget_cost(self):
        goal=self.create();self.result(self.transfer(150,goal,reserve_action='FUND'),201)
        FrozenDate.current=date(2026,11,2)
        self.result(self.move(goal,'SPEND',150,account_id=self.other),201)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-11')['budget_spent'],0)
        self.assertEqual(self.item(goal)['cycle'],2)

    def test_releasing_reserved_cash_refunds_budget_and_plain_transfer_has_no_cost(self):
        goal=self.create();self.result(self.transfer(150,goal,reserve_action='FUND'),201)
        FrozenDate.current=date(2026,11,2)
        self.result(self.move(goal,'RELEASE',50,account_id=self.other),201)
        self.result(self.transfer(100),201)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-11')['budget_spent'],-50)
        self.assertEqual(self.item(goal)['saved'],100)

    def test_manual_funding_validation_rolls_back_cash_and_reserve(self):
        goal=self.create()
        self.assertEqual(self.transfer(150,goal,reserve_action='FUND',version=99).status_code,409)
        self.assertEqual(self.transfer(150,goal,reserve_action='FUND',move_money=False).status_code,400)
        self.assertEqual(self.transfer(10001,goal,reserve_action='FUND').status_code,400)
        self.assertEqual(self.balances(),[10000,2000]);self.assertEqual(self.item(goal)['saved'],0)

    def test_both_bank_sides_link_one_funding_even_with_different_booking_date(self):
        goal=self.create();self.transfer_rule(goal)
        session=self.stage(self.csv(),mode='APPLY')
        row=bank.view(session)['rows'][0]
        self.assertEqual((row['kind'],row['action'],row['reserve_id'],row['target_account_id']),('TRANSFER','NEW',goal,self.other))
        self.result(self.commit(session)[0])
        FrozenDate.current=date(2026,10,3)
        original=self.account;self.account=self.other
        incoming=self.stage(self.csv(amount=150,reference='A1',day='03.10.2026'),mode='APPLY')
        self.account=original
        self.assertEqual(bank.view(incoming)['rows'][0]['action'],'MATCH')
        self.result(self.commit(incoming)[0])
        self.assertEqual(self.balances(),[9850,2150]);self.assertEqual(self.item(goal)['saved'],150)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_account_transfers').fetchone()[0],1)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserve_movements').fetchone()[0],1)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_import_sources').fetchone()[0],2)

    def test_history_import_keeps_current_cash_and_dates_cost_to_payment_month(self):
        goal=self.create();self.transfer_rule(goal)
        session=self.stage(self.csv(day='30.09.2026'))
        self.result(self.commit(session)[0])
        self.assertEqual(self.balances(),[10000,2000])
        self.assertEqual(self.item(goal)['start_date'],'2026-09-30')
        self.assertEqual(monthly_budget_totals(get_db(),'2026-09')['budget_spent'],150)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['budget_spent'],0)

    def test_incoming_bank_import_first_and_two_fundings_share_same_reserve_version(self):
        goal=self.create();self.transfer_rule(goal)
        original=self.account;self.account=self.other
        session=self.stage(self.csv(amount=150),mode='APPLY');self.account=original
        self.result(self.commit(session)[0])
        outgoing=self.stage(self.csv(reference='P1'),mode='APPLY')
        self.assertEqual(bank.view(outgoing)['rows'][0]['action'],'MATCH')
        self.result(self.commit(outgoing)[0])
        multi=self.stage(self.csv(amount=-25,reference='P2')+self.csv(amount=-50,reference='P3').split('\n')[1]+'\n',mode='APPLY')
        self.result(self.commit(multi)[0])
        self.assertEqual(self.item(goal)['saved'],225);self.assertEqual(self.balances(),[9775,2225])
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['budget_spent'],225)

    def test_changed_reserve_requires_refresh_and_multirow_import_is_atomic(self):
        goal=self.create();self.transfer_rule(goal)
        session=self.stage(self.csv(),mode='APPLY')
        self.result(self.move(goal,'ADD',10),201)
        self.assertEqual(self.commit(session)[0].status_code,409)
        self.assertEqual(self.balances(),[10000,2000])
        bank.refresh(session,dict(version=bank.view(session)['version']))
        self.result(self.commit(session)[0]);self.assertEqual(self.item(goal)['saved'],160)
        content=self.csv(reference='F2')+self.csv(amount=-5000,reference='F3').split('\n')[1]+'\n'
        bad=self.stage(content)
        self.assertEqual(self.commit(bad)[0].status_code,400)
        self.assertEqual(self.item(goal)['saved'],160);self.assertEqual(self.balances(),[9850,2150])

    def test_ambiguous_rules_and_short_oc_pattern_do_not_silently_fund(self):
        goal=self.create();self.transfer_rule(goal,pattern='OC')
        self.assertEqual(bank.view(self.stage(self.csv(description='BLIK BLOC zakup')))['rows'][0]['kind'],'EXPENSE')
        other=self.create(name='Drugie auto');self.transfer_rule(other,pattern='OC auta')
        row=bank.view(self.stage(self.csv()))['rows'][0]
        self.assertEqual((row['kind'],row['action']),('TRANSFER','SKIP'))
        self.assertTrue(any('Kilka reguł' in w for w in row['warnings']))

    def test_rule_can_be_paused_and_budget_reset_removes_transfer_rules(self):
        goal=self.create();rule=self.transfer_rule(goal)
        pending=self.stage(self.csv())
        self.result(self.client.put(f'{self.url}/transfer-rules/{rule}',json=dict(pattern='rezerwa OC auta',source_account_id=self.account,
            target_account_id=self.other,reserve_id=goal,active=False,version=1)))
        self.assertEqual(bank.view(self.stage(self.csv()))['rows'][0]['kind'],'EXPENSE')
        bank.refresh(pending,dict(version=bank.view(pending)['version']))
        row=bank.view(pending)['rows'][0]
        self.assertEqual((row['action'],row.get('reserve_id')),('SKIP',None))
        self.assertEqual(self.client.put(f'{self.url}/transfer-rules/{rule}',json=dict(pattern='OC',source_account_id=self.account,
            target_account_id=self.other,reserve_id=goal,active=True,version=1)).status_code,409)
        reset_budget_data()
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserve_transfer_rules').fetchone()[0],0)

    def test_rule_without_a_real_purpose_is_rejected(self):
        goal=self.create()
        response=self.client.post(self.url+'/transfer-rules',json=dict(pattern='!!!',source_account_id=self.account,
            target_account_id=self.other,reserve_id=goal,active=True,request_id=str(uuid4())))
        self.assertEqual(response.status_code,400)

    def test_insurance_import_first_can_settle_reserve_without_second_payment(self):
        goal=self.create();self.result(self.transfer(150,goal,reserve_action='FUND'),201)
        FrozenDate.current=date(2026,11,2)
        original=self.account;self.account=self.other
        session=self.stage(self.csv(amount=-150,reference='INSURANCE',day='02.11.2026',description='Opłata polisy rocznej'),mode='APPLY')
        self.account=original;self.result(self.commit(session)[0])
        entry=get_db().execute('SELECT * FROM budget_entries_v2').fetchone()
        lines=[tuple(r) for r in get_db().execute('SELECT * FROM budget_entry_lines_v2')]
        before=self.balances()
        self.result(self.move(goal,'SPEND',150,account_id=self.other,existing_entry_id=entry['id'],entry_version=entry['version']),201)
        self.assertEqual(self.balances(),before)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)
        self.assertEqual([tuple(r) for r in get_db().execute('SELECT * FROM budget_entry_lines_v2')],lines)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-11')['budget_spent'],0)
        self.assertEqual(self.item(goal)['saved'],0)
        self.assertEqual(self.move(goal,'SPEND',150,account_id=self.other,existing_entry_id=entry['id'],entry_version=entry['version']).status_code,400)

    def test_linked_payment_works_when_bank_cash_is_already_zero_and_checks_version(self):
        from routes_budget_workspace import insert_entry
        db=get_db();db.execute('UPDATE budget_accounts SET balance=0 WHERE id=?',(self.other,));db.commit()
        goal=self.create();self.result(self.transfer(150,goal,reserve_action='FUND'),201)
        entry=insert_entry(db,dict(account_id=self.other,kind='EXPENSE',amount_cents=15000,date='2026-10-02',description='OC',
            merchant='Ubezpieczyciel',lines=[dict(category_id=self.category,amount_cents=15000,label='')]))
        db.commit()
        self.assertEqual(self.balances()[1],0)
        self.assertEqual(self.move(goal,'SPEND',150,account_id=self.other,existing_entry_id=entry,entry_version=999).status_code,409)
        self.assertEqual(self.item(goal)['saved'],150)
        self.assertEqual(self.move(goal,'SPEND',149,account_id=self.other,existing_entry_id=entry,entry_version=1).status_code,400)
        self.result(self.move(goal,'SPEND',150,account_id=self.other,existing_entry_id=entry,entry_version=1),201)
        self.assertEqual(self.balances()[1],0)
        self.assertEqual(monthly_budget_totals(db,'2026-10')['budget_spent'],150)


if __name__=='__main__':
    unittest.main()
