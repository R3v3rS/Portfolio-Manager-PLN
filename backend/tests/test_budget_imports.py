import base64
import io
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from database import get_db, reset_budget_data
from tests import test_budget_reserves as fixtures
from routes_budget_imports import imports_bp
from routes_budget_workspace import insert_entry
import budget_bank_import_service as bank
import budget_category_service as categories
import budget_receipts_service as receipts
from budget_import_parser import number, parse_receipt

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lXcAAAAASUVORK5CYII=')
CSV = 'Data;Opis;Odbiorca;Kwota;Waluta;ID\n02.10.2026;Zakupy;LIDL;-146,80;PLN;A1\n02.10.2026;Faktura energia;ENEA SA;-300,00;PLN;A2\n02.10.2026;Pensja;Pracodawca;1500,00;PLN;A3\n'


class BudgetImportTest(unittest.TestCase):
    result = fixtures.BudgetReservesTest.result

    def setUp(self):
        fixtures.BudgetReservesTest.setUp(self)
        self.app.register_blueprint(imports_bp, url_prefix='/api/budget/imports')
        self.app.config['BUDGET_RECEIPT_DIR'] = str(Path(self.temp.name)/'receipts')
        fixtures.FrozenDate.current = date(2026, 10, 3)
        for module in ('budget_import_parser', 'budget_bank_import_service'):
            p = patch(module+'.date', fixtures.FrozenDate); p.start(); self.addCleanup(p.stop)
        self.url = '/api/budget/imports'

    def stage(self, content=CSV, mode='HISTORY', token=None):
        raw = content.encode('utf-8')
        mapping = self.result(self.client.post(self.url+'/csv/preview', data={'file':(io.BytesIO(raw),'bank.csv')}))['mapping']
        data = dict(account_id=self.account, balance_mode=mode, mapping=mapping, request_id=token or str(uuid4()))
        return self.result(self.client.post(self.url+'/csv', data={'file':(io.BytesIO(raw),'bank.csv'),'data':json.dumps(data)}),201)['id']

    def commit(self, session_id, token=None):
        data=dict(version=bank.view(session_id)['version'],request_id=token or str(uuid4()))
        return self.client.post(f'{self.url}/sessions/{session_id}/commit',json=data),data

    def rule(self, pattern='ENEA', **extra):
        data=dict(pattern=pattern,category_id=self.category,match_field='ANY',match_type='CONTAINS',priority=100,active=True,request_id=str(uuid4()))
        data.update(extra)
        return self.result(self.client.post(self.url+'/rules',json=data),201)['id']

    def entry(self, amount=146.8, day='2026-10-02', merchant='LIDL', account=None, effect=1):
        db=get_db()
        entry=insert_entry(db,dict(account_id=account or self.account,kind='EXPENSE',amount_cents=round(amount*100),date=day,
            description=merchant,merchant=merchant,lines=[dict(category_id=self.category,amount_cents=round(amount*100),label='')],cash_effect=effect))
        db.commit();return entry

    def photo(self, text='LIDL\n2026-10-02\nChleb 112,40\nChemia 34,40\nSUMA PLN 146,80', content=PNG):
        with patch('receipt_ocr_service.extract',return_value=(text,[])):
            draft=self.result(self.client.post(self.url+'/receipts',data={'file':(io.BytesIO(content),'paragon.png'),
                'data':json.dumps(dict(account_id=self.account,request_id=str(uuid4())))}),201)['id']
        return draft

    def photo_commit(self, draft, entry_id=None, **extra):
        data=dict(version=receipts.view(draft)['version'],request_id=str(uuid4()),action='MATCH' if entry_id else 'NEW',
            account_id=self.account,amount=146.8,date='2026-10-02',merchant='LIDL',classification_mode='GENERAL',category_id=self.category,balance_mode='HISTORY')
        if entry_id:
            data.update(entry_id=entry_id,entry_version=get_db().execute('SELECT version FROM budget_entries_v2 WHERE id=?',(entry_id,)).fetchone()[0])
        data.update(extra)
        return self.client.post(f'{self.url}/receipts/{draft}/commit',json=data),data

    def test_csv_history_records_spending_without_changing_current_balance(self):
        session=self.stage(); result=self.result(self.commit(session)[0])
        self.assertEqual((result['created'],result['balance']),(3,10000))
        rows=get_db().execute('SELECT * FROM budget_entries_v2').fetchall()
        self.assertTrue(all(r['cash_effect']==0 for r in rows))
        self.assertEqual(sum(r['amount_cents'] for r in rows if r['kind']=='EXPENSE'),44680)
        from budget_summary_service import monthly_budget_totals
        totals=monthly_budget_totals(get_db(),'2026-10')
        self.assertEqual((totals['spent'],totals['income']),(446.8,1500))
        pending=self.result(self.client.get(self.url))
        self.assertEqual(pending['pending_count'],2)
        expense=next(r for r in rows if r['kind']=='EXPENSE')
        self.result(self.client.delete('/api/budget/workspace/entries/'+str(expense['id'])))
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)

    def test_csv_new_cash_is_atomic_and_idempotent(self):
        session=self.stage(mode='APPLY'); response,payload=self.commit(session)
        self.assertEqual(self.result(response)['balance'],11053.2)
        self.assertEqual(self.result(self.client.post(f'{self.url}/sessions/{session}/commit',json=payload))['balance'],11053.2)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],3)
        self.assertEqual(self.client.post(f'{self.url}/sessions/{session}/commit',json=dict(payload,request_id=str(uuid4()))).status_code,409)

    def test_category_rule_normalizes_text_and_is_saved_for_future_imports(self):
        rule=self.rule(pattern='enea')
        session=self.stage(); row=bank.view(session)['rows'][1]
        self.assertEqual(row['category_id'],self.category);self.assertEqual(row['rule_id'],rule)
        self.result(self.commit(session)[0]);self.assertEqual(self.result(self.client.get(self.url))['pending_count'],1)
        self.assertEqual(categories.rule_match(categories.rules(get_db()),self.account,'ÉNEA SA','')[0]['id'],rule)

    def test_bank_rule_and_receipt_keep_the_subcategory_without_double_spending(self):
        child=self.result(self.client.post('/api/budget/workspace/categories',json=dict(name='Sklepy',parent_id=self.category)),201)['id']
        self.rule(pattern='LIDL',category_id=child)
        session=self.stage();self.assertEqual(bank.view(session)['rows'][0]['category_id'],child)
        self.result(self.commit(session)[0])
        db=get_db();entry=db.execute("SELECT id FROM budget_entries_v2 WHERE merchant='LIDL'").fetchone()[0]
        draft=self.photo()
        response,_=self.photo_commit(draft,entry,category_id=child)
        self.result(response)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],3)
        from budget_category_hierarchy_service import category_workspace
        rows={c['id']:c for c in category_workspace(db,'2026-10')}
        self.assertEqual(rows[child]['spent'],146.8)
        self.assertEqual(rows[self.category]['spent'],146.8)
        pending=self.result(self.client.get(self.url))
        self.assertIn(' › Sklepy',next(c['selection_label'] for c in pending['categories'] if c['id']==child))

    def test_rules_scope_priority_conflicts_and_version_guard(self):
        other=get_db().execute("INSERT INTO budget_categories_v2 (name) VALUES ('Jedzenie')").lastrowid;get_db().commit()
        first=self.rule();second=self.rule(category_id=other)
        self.assertTrue(categories.rule_match(categories.rules(get_db()),self.account,'ENEA','')[1])
        self.result(self.client.put(f'{self.url}/rules/{second}',json=dict(pattern='ENEA',category_id=other,priority=101,active=True,version=1)))
        self.assertEqual(categories.rule_match(categories.rules(get_db()),self.account,'ENEA','')[0]['id'],second)
        self.assertEqual(self.client.put(f'{self.url}/rules/{second}',json=dict(pattern='ENEA',category_id=other,version=1)).status_code,409)
        scoped=self.rule('LIDL',account_id=self.account)
        self.assertIsNone(categories.rule_match(categories.rules(get_db()),999,'LIDL','')[0])

    def test_repeated_file_and_overlapping_bank_ids_are_not_booked_twice(self):
        first=self.stage();self.result(self.commit(first)[0])
        second=self.stage();self.assertTrue(all(r['action']=='SKIP' for r in bank.view(second)['rows']))
        row=bank.view(second)['rows'][0]
        self.result(self.client.put(f'{self.url}/sessions/{second}/rows/{row["id"]}',json={'version':bank.view(second)['version'],'action':'NEW'}))
        self.assertEqual(self.commit(second)[0].status_code,409)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],3)

    def test_identical_real_purchases_without_bank_ids_can_remain_separate(self):
        session=self.stage('Data;Opis;Kwota\n02.10.2026;LIDL;-10,00\n02.10.2026;LIDL;-10,00\n')
        self.assertTrue(all(r['action']=='NEW' for r in bank.view(session)['rows']))
        self.assertEqual(self.result(self.commit(session)[0])['created'],2)

    def test_import_links_a_previously_added_receipt_across_booking_date_difference(self):
        entry=self.entry(day='2026-10-01'); balance=get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0]
        session=self.stage('Data;Opis;Odbiorca;Kwota\n02.10.2026;Zakupy;LIDL;-146,80\n',mode='APPLY')
        self.assertEqual(bank.view(session)['rows'][0]['entry_id'],entry)
        self.assertEqual(self.result(self.commit(session)[0])['linked'],1)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],balance)

    def test_photo_after_bank_import_preserves_account_amount_and_cash(self):
        session=self.stage();self.result(self.commit(session)[0]);entry=get_db().execute("SELECT id FROM budget_entries_v2 WHERE merchant='LIDL'").fetchone()[0]
        draft=self.photo();self.assertEqual(receipts.view(draft)['candidates'][0]['id'],entry)
        response,payload=self.photo_commit(draft,entry,classification_mode='SPLIT',lines=[dict(label='Jedzenie',category_id=self.category,amount=112.4),dict(label='Chemia',category_id=self.category,amount=34.4)])
        self.result(response);self.result(self.client.post(f'{self.url}/receipts/{draft}/commit',json=payload))
        db=get_db();self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],3)
        row=db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone()
        self.assertEqual((row['classification_status'],row['account_id'],row['amount_cents']),('SPLIT',self.account,14680))

    def test_manual_general_category_finishes_pending_without_receipt(self):
        session=self.stage();self.result(self.commit(session)[0]);pending=self.result(self.client.get(self.url))['pending']
        self.result(self.client.post(self.url+'/categorize',json=dict(entry_ids=[e['id'] for e in pending],versions={str(e['id']):e['version'] for e in pending},category_id=self.category)))
        self.assertEqual(self.result(self.client.get(self.url))['pending_count'],0)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2 WHERE receipt_filename IS NOT NULL').fetchone()[0],0)

    def test_category_changes_are_atomic_when_one_entry_is_stale(self):
        first=self.entry(amount=10);second=self.entry(amount=20)
        response=self.client.post(self.url+'/categorize',json=dict(entry_ids=[first,second],versions={str(first):1,str(second):99},category_id=self.category))
        self.assertEqual(response.status_code,409)
        self.assertEqual(get_db().execute('SELECT version FROM budget_entries_v2 WHERE id=?',(first,)).fetchone()[0],1)

    def test_bad_receipt_sum_and_mismatched_account_do_not_change_money(self):
        entry=self.entry();draft=self.photo();before=get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0]
        self.assertEqual(self.photo_commit(draft,entry,classification_mode='SPLIT',lines=[dict(label='Zły odczyt',category_id=self.category,amount=100)])[0].status_code,400)
        other=get_db().execute("INSERT INTO budget_accounts (name,balance,currency) VALUES ('Drugie',500,'PLN')").lastrowid;get_db().commit()
        self.assertEqual(self.photo_commit(draft,entry,account_id=other)[0].status_code,400)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],before)
        self.assertEqual(receipts.view(draft)['status'],'PENDING')

    def test_failed_second_bank_row_rolls_back_the_whole_batch(self):
        self.rule();session=self.stage(mode='APPLY')
        original=bank.insert_entry;calls=0
        def fail_second(db,entry):
            nonlocal calls
            calls+=1
            if calls==2:raise RuntimeError('Injected failure')
            return original(db,entry)
        with patch('budget_bank_import_service.insert_entry',side_effect=fail_second):
            with self.assertRaises(RuntimeError):bank.commit(session,dict(version=1,request_id=str(uuid4())))
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_import_sources').fetchone()[0],0)

    def test_changed_balance_requires_review_and_refresh(self):
        session=self.stage(mode='APPLY');self.entry(amount=1)
        self.assertEqual(self.commit(session)[0].status_code,409)
        self.result(self.client.post(f'{self.url}/sessions/{session}/refresh',json=dict(version=1)))
        self.assertEqual(self.result(self.commit(session)[0])['balance'],11052.2)

    def test_internal_transfer_is_never_an_expense_and_links_the_other_bank_leg(self):
        db=get_db();other=db.execute("INSERT INTO budget_accounts (name,balance,currency) VALUES ('Oszczędności',100,'PLN')").lastrowid;db.commit()
        session=self.stage('Data;Opis;Kwota\n02.10.2026;Przelew własny;-200,00\n',mode='APPLY');row=bank.view(session)['rows'][0]
        self.assertEqual(row['action'],'SKIP')
        self.result(self.client.put(f'{self.url}/sessions/{session}/rows/{row["id"]}',json=dict(version=1,action='NEW',kind='TRANSFER',target_account_id=other)))
        self.assertEqual(self.result(self.commit(session)[0])['transfers'],1)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(other,)).fetchone()[0],300)
        raw='Data;Opis;Kwota\n02.10.2026;Przelew własny;200,00\n'.encode()
        mapping=self.result(self.client.post(self.url+'/csv/preview',data={'file':(io.BytesIO(raw),'other.csv')}))['mapping']
        second=self.result(self.client.post(self.url+'/csv',data={'file':(io.BytesIO(raw),'other.csv'),
            'data':json.dumps(dict(account_id=other,balance_mode='APPLY',mapping=mapping,request_id=str(uuid4())))}),201)['id']
        row=bank.view(second)['rows'][0]
        transfer_id=db.execute('SELECT id FROM budget_account_transfers').fetchone()[0]
        self.result(self.client.put(f'{self.url}/sessions/{second}/rows/{row["id"]}',json=dict(version=1,kind='TRANSFER',action='MATCH',transfer_id=transfer_id)))
        self.assertEqual(self.result(self.commit(second)[0])['linked'],1)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts WHERE id=?',(other,)).fetchone()[0],300)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_account_transfers').fetchone()[0],1)

    def test_parser_handles_locale_discount_warnings_and_rejects_nonfinite(self):
        self.assertEqual(number('1 234,56 PLN'),123456)
        self.assertEqual(number('1.234,56'),123456)
        for value in ('NaN','Infinity','1,001','1e5'):
            with self.subTest(value=value):
                with self.assertRaises(Exception):number(value)
        data,warnings=parse_receipt('LIDL\n02.10.2026\nChleb 10,00\nRABAT -1,00\nSUMA PLN 9,00')
        self.assertEqual(data['amount'],9);self.assertTrue(any('Suma odczytanych' in w for w in warnings))

    def test_preview_encoding_profiles_and_invalid_rows(self):
        session=self.stage('Data;Opis;Kwota;Waluta\n02.10.2026;Zakupy;-20,00;EUR\n')
        self.assertTrue(bank.view(session)['rows'][0]['errors']);self.assertEqual(self.commit(session)[0].status_code,400)
        self.assertTrue(self.result(self.client.post(self.url+'/csv/preview',data={'file':(io.BytesIO(CSV.encode()),'bank.csv')}))['mapping'])

    def test_bank_source_cannot_be_edited_into_different_amount(self):
        session=self.stage();self.result(self.commit(session)[0]);row=get_db().execute("SELECT * FROM budget_entries_v2 WHERE merchant='LIDL'").fetchone()
        data=dict(account_id=self.account,kind='EXPENSE',date=row['date'],amount=200,description='LIDL',lines=[dict(category_id=self.category,amount=200)])
        self.assertEqual(self.client.put('/api/budget/workspace/entries/'+str(row['id']),json=data).status_code,400)
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)

    def test_rules_can_classify_existing_pending_expenses_without_cash_movement(self):
        session=self.stage();self.result(self.commit(session)[0]);self.rule()
        pending=self.result(self.client.get(self.url))['pending']
        payload=dict(entry_ids=[e['id'] for e in pending],versions={str(e['id']):e['version'] for e in pending})
        result=self.result(self.client.post(self.url+'/categorize/rules',json=payload))
        self.assertEqual(result,dict(updated=1,unmatched=1))
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(self.result(self.client.get(self.url))['pending_count'],1)

    def test_manual_category_is_preserved_when_rules_are_refreshed(self):
        rule=self.rule();session=self.stage();row=bank.view(session)['rows'][1]
        other=get_db().execute("INSERT INTO budget_categories_v2 (name) VALUES ('Jedzenie')").lastrowid;get_db().commit()
        self.result(self.client.put(f'{self.url}/sessions/{session}/rows/{row["id"]}',json=dict(version=1,category_id=other)))
        self.result(self.client.post(f'{self.url}/sessions/{session}/refresh',json=dict(version=2)))
        self.assertEqual(bank.view(session)['rows'][1]['category_id'],other)
        self.assertTrue(bank.view(session)['rows'][1]['manual_category'])

    def test_refresh_reloads_version_of_an_existing_linked_purchase(self):
        entry=self.entry();session=self.stage()
        categories.categorize(dict(entry_ids=[entry],versions={str(entry):1},category_id=self.category))
        self.assertEqual(self.commit(session)[0].status_code,409)
        self.result(self.client.post(f'{self.url}/sessions/{session}/refresh',json=dict(version=1)))
        self.assertEqual(self.result(self.commit(session)[0])['linked'],1)

    def test_manual_split_of_bank_entry_keeps_cash_and_guards_concurrent_edits(self):
        session=self.stage();self.result(self.commit(session)[0])
        row=get_db().execute("SELECT * FROM budget_entries_v2 WHERE merchant='LIDL'").fetchone()
        data=dict(version=row['version'],account_id=self.account,kind='EXPENSE',date=row['date'],amount=146.8,description='Zakupy',
            lines=[dict(category_id=self.category,amount=100,label='Żywność'),dict(category_id=self.category,amount=46.8,label='Inne')])
        self.result(self.client.put('/api/budget/workspace/entries/'+str(row['id']),json=data))
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(self.client.put('/api/budget/workspace/entries/'+str(row['id']),json=data).status_code,409)
        self.assertEqual(get_db().execute('SELECT classification_status FROM budget_entries_v2 WHERE id=?',(row['id'],)).fetchone()[0],'SPLIT')

    def test_new_rule_reuses_a_category_with_different_letter_case(self):
        self.rule(new_category='ubezpieczenia',category_id=None)
        self.assertEqual(get_db().execute("SELECT COUNT(*) FROM budget_categories_v2 WHERE name='ubezpieczenia' COLLATE NOCASE").fetchone()[0],1)

    def test_replacing_a_receipt_attachment_preserves_original_in_import_history(self):
        entry=self.entry();draft=self.photo();self.result(self.photo_commit(draft,entry)[0])
        previous=get_db().execute('SELECT filename FROM budget_receipt_drafts WHERE id=?',(draft,)).fetchone()[0]
        version=get_db().execute('SELECT version FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone()[0]
        self.result(self.client.post(f'/api/budget/workspace/entries/{entry}/receipt',data={'file':(io.BytesIO(PNG+b'other'),'nowy.png')}))
        self.assertTrue((Path(self.app.config['BUDGET_RECEIPT_DIR'])/previous).is_file())
        self.assertEqual(get_db().execute('SELECT version FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone()[0],version+1)
        with self.client.get(f'{self.url}/receipts/{draft}/file') as response:
            self.assertEqual(response.status_code,200)

    def test_two_bank_rows_cannot_link_the_same_purchase(self):
        entry=self.entry(amount=10)
        session=self.stage('Data;Opis;Kwota;ID\n02.10.2026;LIDL;-10,00;B1\n02.10.2026;LIDL;-10,00;B2\n')
        second=bank.view(session)['rows'][1]
        self.result(self.client.put(f'{self.url}/sessions/{session}/rows/{second["id"]}',json=dict(version=1,action='MATCH',entry_id=entry)))
        self.assertEqual(self.commit(session)[0].status_code,400)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_import_sources').fetchone()[0],0)
        self.assertEqual(bank.view(session)['status'],'PENDING')

    def test_separate_credit_debit_columns_and_utf16(self):
        raw='Data;Opis;Obciążenie;Uznanie\n02.10.2026;Zakupy;20,00;\n02.10.2026;Pensja;;1000,00\n'.encode('utf-16')
        preview=self.result(self.client.post(self.url+'/csv/preview',data={'file':(io.BytesIO(raw),'bank.csv')}))
        self.assertEqual(preview['encoding'],'utf-16')
        session=self.result(self.client.post(self.url+'/csv',data={'file':(io.BytesIO(raw),'bank.csv'),
            'data':json.dumps(dict(mapping=preview['mapping'],account_id=self.account,request_id=str(uuid4())))}),201)['id']
        self.assertEqual([e['bank_kind'] for e in bank.view(session)['rows']],['EXPENSE','INCOME'])
        self.assertEqual(self.result(self.commit(session)[0])['created'],2)

    def test_empty_csv_and_invalid_receipt_metadata_are_validation_errors(self):
        for raw in (b'\xef\xbb\xbf',b'   \n'):
            response=self.client.post(self.url+'/csv/preview',data={'file':(io.BytesIO(raw),'empty.csv')})
            self.assertEqual(response.status_code,400)
        draft=self.photo()
        self.assertEqual(self.photo_commit(draft,merchant={'invalid':'text'})[0].status_code,400)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)

    def test_new_receipt_applies_cash_once_and_rejects_silent_duplicate(self):
        draft=self.photo();response,payload=self.photo_commit(draft,balance_mode='APPLY',expected_balance=10000)
        self.result(response)
        self.result(self.client.post(f'{self.url}/receipts/{draft}/commit',json=payload))
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],9853.2)
        second=self.photo(content=PNG+b'different')
        self.assertEqual(self.photo_commit(second,balance_mode='APPLY',expected_balance=9853.2)[0].status_code,400)
        self.assertEqual(receipts.view(second)['status'],'PENDING')
        self.assertEqual(get_db().execute('SELECT balance FROM budget_accounts').fetchone()[0],9853.2)

    def test_duplicate_photo_reuses_draft_and_reset_removes_import_data(self):
        first=self.photo();self.assertEqual(self.photo(),first)
        self.result(self.photo_commit(first)[0]);self.rule();self.stage()
        reset_budget_data()
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_receipt_drafts').fetchone()[0],0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_import_sessions').fetchone()[0],0)
        self.assertFalse(list(Path(self.app.config['BUDGET_RECEIPT_DIR']).glob('*')))

    def test_delete_pending_receipt_removes_file_and_readout_and_allows_upload_again(self):
        draft=self.photo();db=get_db()
        row=db.execute('SELECT * FROM budget_receipt_drafts WHERE id=?',(draft,)).fetchone()
        path=Path(self.app.config['BUDGET_RECEIPT_DIR'])/row['filename']
        result=self.result(self.client.delete(f'{self.url}/receipts/{draft}?version={row["version"]}'))
        self.assertEqual(result['deleted'],draft)
        self.assertFalse(path.exists())
        self.assertEqual(self.client.get(f'{self.url}/receipts/{draft}').status_code,404)
        self.assertEqual(self.client.get(f'{self.url}/receipts/{draft}/file').status_code,404)
        self.assertEqual(self.result(self.client.get(self.url))['receipts'],[])
        deleted=db.execute('SELECT * FROM budget_receipt_drafts WHERE id=?',(draft,)).fetchone()
        self.assertEqual((deleted['status'],deleted['raw_text'],deleted['data_json']),('DELETED','','{}'))
        self.result(self.client.delete(f'{self.url}/receipts/{draft}?version={row["version"]}'))
        self.assertNotEqual(self.photo(),draft)
        with patch('receipt_ocr_service.extract') as ocr:
            response=self.client.post(self.url+'/receipts',data={'file':(io.BytesIO(PNG),'paragon.png'),
                'data':json.dumps(dict(account_id=self.account,request_id=row['request_id']))})
            self.assertEqual(response.status_code,409);ocr.assert_not_called()
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)

    def test_delete_linked_receipt_keeps_bank_purchase_categories_and_balance(self):
        session=self.stage();self.result(self.commit(session)[0]);db=get_db()
        entry=db.execute("SELECT id FROM budget_entries_v2 WHERE merchant='LIDL'").fetchone()[0]
        draft=self.photo();response,payload=self.photo_commit(draft,entry)
        self.result(response)
        before=dict(db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone())
        lines=[dict(r) for r in db.execute('SELECT * FROM budget_entry_lines_v2 WHERE entry_id=?',(entry,))]
        version=receipts.view(draft)['version']
        self.assertEqual(self.client.delete(f'{self.url}/receipts/{draft}?version={version-1}').status_code,409)
        self.assertTrue((Path(self.app.config['BUDGET_RECEIPT_DIR'])/before['receipt_filename']).exists())
        self.result(self.client.delete(f'{self.url}/receipts/{draft}?version={version}'))
        after=dict(db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone())
        self.assertIsNone(after.pop('receipt_filename'));self.assertIsNone(after.pop('receipt_original_name'))
        before.pop('receipt_filename');before.pop('receipt_original_name')
        self.assertEqual(after.pop('version'),before.pop('version')+1)
        self.assertEqual(after,before)
        self.assertEqual([dict(r) for r in db.execute('SELECT * FROM budget_entry_lines_v2 WHERE entry_id=?',(entry,))],lines)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],3)
        self.assertEqual(self.client.post(f'{self.url}/receipts/{draft}/commit',json=payload).status_code,404)

    def test_delete_receipt_of_new_cash_expense_does_not_reverse_payment(self):
        draft=self.photo();self.result(self.photo_commit(draft,balance_mode='APPLY',expected_balance=10000)[0])
        self.result(self.client.delete(f'{self.url}/receipts/{draft}?version={receipts.view(draft)["version"]}'))
        db=get_db()
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],9853.2)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],1)

    def test_delete_old_receipt_preserves_its_replacement(self):
        entry=self.entry();draft=self.photo();self.result(self.photo_commit(draft,entry)[0])
        self.result(self.client.post(f'/api/budget/workspace/entries/{entry}/receipt',data={'file':(io.BytesIO(PNG+b'new'),'nowy.png')}))
        db=get_db();current=dict(db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone())
        self.result(self.client.delete(f'{self.url}/receipts/{draft}?version={receipts.view(draft)["version"]}'))
        self.assertEqual(dict(db.execute('SELECT * FROM budget_entries_v2 WHERE id=?',(entry,)).fetchone()),current)
        self.assertTrue((Path(self.app.config['BUDGET_RECEIPT_DIR'])/current['receipt_filename']).exists())

    def test_repeat_recognition_updates_only_the_pending_draft(self):
        draft=self.photo();db=get_db();version=receipts.view(draft)['version']
        from tests.test_receipt_recognition import DINO_TEXT
        with patch('receipt_ocr_service.extract',return_value=(DINO_TEXT,[])):
            self.result(self.client.post(f'{self.url}/receipts/{draft}/recognize',json=dict(version=version)))
        data=receipts.view(draft)
        self.assertEqual((data['data']['amount'],data['version'],len(data['data']['lines'])),(41.44,version+1,8))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],10000)

    def test_repeat_recognition_does_not_replace_data_on_failure_or_concurrent_edit(self):
        draft=self.photo();before=receipts.view(draft)
        with patch('receipt_ocr_service.extract',return_value=('', ['Nie odczytano'])):
            self.assertEqual(self.client.post(f'{self.url}/receipts/{draft}/recognize',json=dict(version=before['version'])).status_code,400)
        self.assertEqual(receipts.view(draft),before)
        manual='Poprawiony sklep\n2026-10-02\nSUMA PLN 50,00'
        def concurrent_edit(_):
            receipts.reparse(draft,dict(text=manual,version=before['version']))
            return 'Inny sklep\n2026-10-02\nSUMA PLN 99,00',[]
        with patch('receipt_ocr_service.extract',side_effect=concurrent_edit):
            self.assertEqual(self.client.post(f'{self.url}/receipts/{draft}/recognize',json=dict(version=before['version'])).status_code,409)
        self.assertEqual(receipts.view(draft)['raw_text'],manual)

    def test_repeat_recognition_rejects_committed_and_stale_drafts(self):
        draft=self.photo()
        with patch('receipt_ocr_service.extract') as ocr:
            self.assertEqual(self.client.post(f'{self.url}/receipts/{draft}/recognize',json=dict(version=0)).status_code,409)
            ocr.assert_not_called()
        self.result(self.photo_commit(draft)[0])
        with patch('receipt_ocr_service.extract') as ocr:
            self.assertEqual(self.client.post(f'{self.url}/receipts/{draft}/recognize',json=dict(version=receipts.view(draft)['version'])).status_code,400)
            ocr.assert_not_called()

    def test_apply_bank_history_expense_preserves_source_and_reimport_does_not_debit_again(self):
        session=self.stage();self.result(self.commit(session)[0]);db=get_db()
        row=db.execute("SELECT * FROM budget_entries_v2 WHERE merchant='LIDL'").fetchone()
        result=self.result(self.client.post(f'/api/budget/workspace/entries/{row["id"]}/apply-balance',
            json=dict(version=row['version'],expected_balance=10000)))
        self.assertEqual(result['balance'],9853.2)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_import_sources').fetchone()[0],3)
        again=self.stage(mode='APPLY');self.result(self.commit(again)[0])
        self.assertEqual(db.execute('SELECT balance FROM budget_accounts').fetchone()[0],9853.2)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],3)


if __name__=='__main__':unittest.main()
