"""Receipts, surplus decisions, unchanged cash and all-or-nothing bulk funding."""
import json
import unittest
from uuid import uuid4

from database import get_db
from tests import test_budget_reserves as fixtures
from tests.test_budget_reserves import FrozenDate
from budget_reserve_funding_service import budget_pool
from budget_settlement_service import preview as undo_preview, reverse


class ReserveOperationsTest(unittest.TestCase):
    setUp=fixtures.BudgetReservesTest.setUp
    result=fixtures.BudgetReservesTest.result
    create=fixtures.BudgetReservesTest.create
    item=fixtures.BudgetReservesTest.item
    move=fixtures.BudgetReservesTest.move

    def payload(self,reserve,kind,amount,**extra):
        return dict(kind=kind,amount=amount,date=FrozenDate.today().isoformat(),notes='',category_id=self.category,
                    version=self.item(reserve)['version'],**extra)

    def test_preview_rolls_back_everything_and_matches_water_receipt(self):
        reserve=self.create(frequency='ONCE',target_amount=382)
        self.result(self.move(reserve,'ADD',382),201)
        db=get_db(); before=db.total_changes
        counts={t:db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('budget_entries_v2','budget_reserve_movements','budget_reserve_operation_receipts','budget_reserve_plan_history')}
        draft=self.payload(reserve,'SPEND',374.2)
        view=self.result(self.client.post(f'{self.base}/{reserve}/preview',json=draft))
        self.assertEqual((view['reserve_before'],view['reserve_after'],view['surplus'],view['available_change']),(382,0,7.8,7.8))
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],10000)
        for table,count in counts.items():self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],count)
        self.assertFalse(db.in_transaction)
        data=dict(draft,expected_state=view['expected_state'],request_id=str(uuid4()))
        result=self.result(self.client.post(f'{self.base}/{reserve}/movements',json=data),201)
        self.assertEqual(result['summary']['accounts'],view['accounts'])
        self.assertEqual(self.result(self.client.post(f'{self.base}/{reserve}/movements',json=data),201),result)
        item=self.item(reserve)
        s=item['month_statement']
        self.assertEqual((s['opening'],s['added'],s['used'],s['released'],s['ending'],s['payments']),(0,382,374.2,7.8,0,374.2))
        payment=next(e for e in item['journal'] if e['kind']=='SPEND')
        self.assertEqual(payment['summary']['surplus'],7.8)
        self.assertEqual(payment['budget_entry_id'],result['budget_entry_id'])
        self.assertGreater(db.total_changes,before)

    def test_existing_import_never_debits_cash_twice(self):
        from routes_budget_workspace import insert_entry
        r=self.create(frequency='ONCE',target_amount=382);self.result(self.move(r,'ADD',382),201)
        db=get_db();entry=insert_entry(db,dict(kind='EXPENSE',account_id=self.account,amount_cents=37420,date='2026-10-02',description='Woda z banku',merchant=None,lines=[dict(category_id=self.category,amount_cents=37420,label='')]))
        db.commit();balance=db.execute('SELECT balance FROM budget_accounts').fetchone()[0]
        data=self.payload(r,'SPEND',374.2,existing_entry_id=entry,entry_version=1)
        view=self.result(self.client.post(f'{self.base}/{r}/preview',json=data))
        self.assertTrue(view['existing_expense']);self.assertEqual(view['accounts'][0]['balance_before'],view['accounts'][0]['balance_after'])
        self.result(self.move(r,'SPEND',374.2,existing_entry_id=entry,entry_version=1),201)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],balance)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)

    def test_legacy_water_settlement_has_receipt_without_rewriting_history(self):
        r=self.create(frequency='ONCE',target_amount=382);self.result(self.move(r,'ADD',382),201)
        self.result(self.move(r,'SPEND',374.2),201)
        db=get_db();db.execute('DELETE FROM budget_reserve_operation_receipts');db.commit()
        entry=next(e for e in self.item(r)['journal'] if e['kind']=='SPEND')
        self.assertEqual(entry['summary']['surplus'],7.8)
        self.assertEqual(entry['summary']['reserve_before'],382)

    def test_surplus_transfer_keeps_budget_pool_once_and_can_be_reversed(self):
        source=self.create(frequency='ONCE',target_amount=382)
        target=self.create(name='Serwis auta',frequency='ONCE')
        self.result(self.move(source,'ADD',382),201)
        result=self.result(self.move(source,'SPEND',374.2,surplus_mode='RESERVE',surplus_reserve_id=target,surplus_reserve_version=self.item(target)['version']),201)
        db=get_db();entry=result['budget_entry_id']
        self.assertEqual((self.item(source)['saved'],self.item(target)['saved']),(0,7.8))
        self.assertEqual(budget_pool(db,target),780)
        self.assertEqual(result['summary']['available_change'],0)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],9625.8)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_account_transfers').fetchone()[0],0)
        view=undo_preview(db,entry);reverse(entry,dict(view,request_id=str(uuid4())))
        self.assertEqual((self.item(source)['saved'],self.item(target)['saved']),(382,0))
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(db.execute('SELECT cancelled FROM budget_reserve_operation_receipts WHERE entry_id=?',(entry,)).fetchone()[0],1)

    def test_target_changes_block_undo_and_invalid_target_rolls_back_payment(self):
        s=self.create(frequency='ONCE');t=self.create(name='Cel')
        self.result(self.move(s,'ADD',3000),201)
        rejected=self.move(s,'SPEND',2400,surplus_mode='RESERVE',surplus_reserve_id=t,surplus_reserve_version=0)
        self.assertEqual(rejected.status_code,409)
        self.assertEqual(self.item(s)['saved'],3000)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        result=self.result(self.move(s,'SPEND',2400,surplus_mode='RESERVE',surplus_reserve_id=t,surplus_reserve_version=1),201)
        self.result(self.move(t,'ADD',1),201)
        with self.assertRaisesRegex(Exception,'docelową rezerwę'):undo_preview(get_db(),result['budget_entry_id'])

    def test_one_time_keep_opens_explicit_next_cycle_and_undo_restores_anchor(self):
        s=self.create(frequency='ONCE');self.result(self.move(s,'ADD',3000),201)
        result=self.result(self.move(s,'SPEND',2400,surplus_mode='KEEP',next_due_date='2028-01-01'),201)
        current=self.item(s)
        self.assertEqual((current['saved'],current['status'],current['cycle'],current['due_date']),(600,'ACTIVE',2,'2028-01-01'))
        view=undo_preview(get_db(),result['budget_entry_id']);reverse(result['budget_entry_id'],dict(view,request_id=str(uuid4())))
        self.assertEqual((self.item(s)['cycle'],self.item(s)['due_date']),(1,'2027-09-30'))

    def test_yearly_free_keeps_cycle_and_frees_only_extra(self):
        s=self.create();self.result(self.move(s,'ADD',3000),201)
        result=self.result(self.move(s,'SPEND',2400,surplus_mode='FREE'),201)
        self.assertEqual((self.item(s)['saved'],self.item(s)['cycle']),(0,2))
        self.assertEqual(result['summary']['available_change'],600)

    def test_stale_account_preview_is_rejected_before_writing(self):
        s=self.create();draft=self.payload(s,'ADD',100)
        view=self.result(self.client.post(f'{self.base}/{s}/preview',json=draft))
        db=get_db();db.execute('UPDATE budget_accounts SET balance=balance-1');db.commit()
        response=self.move(s,'ADD',100,expected_state=view['expected_state'])
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.item(s)['saved'],0)

    def test_batch_is_atomic_idempotent_and_creates_no_cash_movements(self):
        a=self.create(name='Auto');b=self.create(name='Mieszkanie')
        data=dict(date='2026-10-02',rows=[dict(reserve_id=i,account_id=self.account,amount=100,version=1) for i in (a,b)])
        view=self.result(self.client.post(self.base+'/funding-preview',json=data))
        self.assertEqual(self.item(a)['saved'],0)
        payload=dict(data,expected_state=view['expected_state'],request_id=str(uuid4()))
        first=self.result(self.client.post(self.base+'/funding',json=payload),201)
        self.assertEqual(self.result(self.client.post(self.base+'/funding',json=payload),201),first)
        self.assertEqual((self.item(a)['saved'],self.item(b)['saved']),(100,100))
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        invalid=dict(date='2026-10-02',rows=[dict(reserve_id=a,account_id=self.account,amount=10,version=2),dict(reserve_id=b,account_id=self.account,amount=99999,version=2)])
        self.assertEqual(self.client.post(self.base+'/funding-preview',json=invalid).status_code,400)
        self.assertEqual(self.item(a)['saved'],100)

    def test_proposal_respects_priority_and_available_cash_on_each_account(self):
        from budget_planning_service import save_reserve_plan
        a=self.create(name='Mniej ważna');b=self.create(name='Pilna')
        for r,priority in ((a,3),(b,1)):
            save_reserve_plan(r,dict(month='2026-10',amount=100,priority=priority,version=0))
        db=get_db();db.execute('UPDATE budget_accounts SET balance=150');db.commit()
        plan=self.result(self.client.get(self.base+'/funding-plan'))
        self.assertEqual([(r['reserve_id'],r['proposed']) for r in plan['rows']],[(b,100),(a,50)])
        data=dict(date='2026-10-02',rows=[dict(reserve_id=a,account_id=self.account,amount=10,version=1)]*2)
        self.assertEqual(self.client.post(self.base+'/funding-preview',json=data).status_code,400)
        self.assertEqual(self.item(a)['saved'],0)

    def test_invalid_second_position_rolls_back_an_actual_batch_and_stale_preview_is_rejected(self):
        a=self.create(name='Auto');b=self.create(name='Mieszkanie')
        data=dict(date='2026-10-02',rows=[dict(reserve_id=r,account_id=self.account,amount=100,version=1) for r in (a,b)])
        view=self.result(self.client.post(self.base+'/funding-preview',json=data))
        invalid=dict(data,rows=[data['rows'][0],dict(data['rows'][1],amount=99999)],expected_state=view['expected_state'],request_id=str(uuid4()))
        self.assertEqual(self.client.post(self.base+'/funding',json=invalid).status_code,400)
        self.assertEqual((self.item(a)['saved'],self.item(b)['saved']),(0,0))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserve_operation_receipts').fetchone()[0],0)
        self.result(self.move(b,'ADD',1),201)
        stale=dict(data,expected_state=view['expected_state'],request_id=str(uuid4()))
        self.assertEqual(self.client.post(self.base+'/funding',json=stale).status_code,409)
        self.assertEqual(self.item(a)['saved'],0)

    def test_additional_deposit_does_not_pretend_to_execute_a_zero_monthly_plan(self):
        r=self.create(open_ended=True,monthly_amount=0)
        self.result(self.move(r,'ADD',100),201)
        s=self.item(r)['month_statement']
        self.assertEqual((s['planned'],s['funded'],s['extra'],s['added']),(0,0,100,100))

    def test_future_media_pool_is_not_proposed_before_start(self):
        self.create(monthly_amount=140,category_id=self.category,monthly_start_month='2026-11')
        self.assertEqual(self.result(self.client.get(self.base+'/funding-plan'))['rows'],[])

    def test_transfer_and_funding_are_one_journal_event_and_months_reconcile(self):
        from budget_accounts_service import transfer
        reserve=self.create();db=get_db()
        target=db.execute("INSERT INTO budget_accounts(name,balance,currency) VALUES('Drugi',0,'PLN')").lastrowid;db.commit()
        transfer(dict(source_account_id=self.account,target_account_id=target,amount=200,date='2026-10-02',notes='',move_money=True,
            source_balance=10000,target_balance=0,reserve_id=reserve,version=1,reserve_action='FUND',request_id=str(uuid4())))
        item=self.item(reserve)
        self.assertEqual(len(item['journal']),1)
        self.assertEqual((item['journal'][0]['kind'],item['month_statement']['added']),('FUND',200))
        november=self.result(self.client.get(self.base+'?month=2026-11'))['items'][0]['month_statement']
        self.assertEqual((november['opening'],november['ending']),(200,200))

    def test_surplus_transfer_uses_existing_locations_and_undo_restores_both(self):
        source=self.create(frequency='ONCE');target=self.create(name='Drugi cel')
        db=get_db();other=db.execute("INSERT INTO budget_accounts(name,balance,currency) VALUES('Inny bank',10000,'PLN')").lastrowid;db.commit()
        self.result(self.move(source,'ADD',100),201);self.result(self.move(source,'ADD',400,account_id=other),201)
        result=self.result(self.move(source,'SPEND',200,surplus_mode='RESERVE',surplus_reserve_id=target,surplus_reserve_version=1),201)
        self.assertEqual(self.item(target)['locations'],[dict(account_id=other,account_name='Inny bank',amount=300)])
        view=undo_preview(db,result['budget_entry_id']);reverse(result['budget_entry_id'],dict(view,request_id=str(uuid4())))
        self.assertEqual(self.item(source)['saved'],500)
