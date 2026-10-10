import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import get_db, init_db
from api.exceptions import ApiError, NotFoundError, ValidationError
from api.response import error_response
from routes_investor_journal import journal_bp


class InvestorJournalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True,DATABASE=str(Path(self.tmp.name)/'journal.db'))
        init_db(self.app)
        self.app.register_blueprint(journal_bp,url_prefix='/api/investor-journal')
        self.app.register_error_handler(ValidationError,lambda e:error_response('validation_error',str(e),status=400))
        self.app.register_error_handler(NotFoundError,lambda e:error_response('not_found',str(e),status=404))
        self.app.register_error_handler(ApiError,lambda e:error_response(e.code,str(e),status=e.status))
        self.client=self.app.test_client()
        with self.app.app_context():
            db=get_db()
            self.portfolio=db.execute("INSERT INTO portfolios(name,current_cash) VALUES ('IKE',100)").lastrowid
            db.commit()
        self.plan=dict(title='ETF thesis',entry_date='2025-01-01',kind='BUY',status='ACTIVE',ticker='cspx.l',portfolio_id=self.portfolio,
                       confidence=4,thesis='Original reasoning',risks='Market decline',invalidation='Thesis changes',exit_plan='Review first',review_date='2026-01-01',tags=['ETF','etf','Long term'])

    def tearDown(self):
        self.tmp.cleanup()

    def create(self,**changes):
        return self.client.post('/api/investor-journal/',json={**self.plan,**changes})

    def detail(self,entry_id):
        response=self.client.get(f'/api/investor-journal/{entry_id}')
        self.assertEqual(response.status_code,200)
        return response.json['payload']

    def review(self,entry_id,version=1,**changes):
        return self.client.post(f'/api/investor-journal/{entry_id}/reviews',json=dict(version=version,review_date='2026-01-01',outcome='CONFIRMED',notes='New facts',lessons='Avoid assumptions',entry_status='ACTIVE',next_review_date='2027-01-01',**changes))

    def test_create_edit_and_original_snapshot_persist_without_financial_writes(self):
        with self.app.app_context():
            before={t:[tuple(r) for r in get_db().execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in ('portfolios','holdings','transactions')}
        result=self.create();self.assertEqual(result.status_code,201)
        entry_id=result.json['payload']['id'];entry=self.detail(entry_id)
        self.assertEqual(entry['ticker'],'CSPX.L');self.assertEqual(entry['tags'],['ETF','Long term'])
        self.assertEqual(entry['portfolio_name'],'IKE');self.assertTrue(entry['review_due'])
        changed=self.client.put(f'/api/investor-journal/{entry_id}',json={**self.plan,'version':1,'thesis':'Revised reasoning'})
        self.assertEqual(changed.status_code,200)
        entry=self.detail(entry_id)
        self.assertEqual(entry['version'],2);self.assertEqual(entry['thesis'],'Revised reasoning')
        self.assertEqual(entry['revisions'][-1]['snapshot']['thesis'],'Original reasoning')
        with self.app.app_context():
            self.assertEqual(before,{t:[tuple(r) for r in get_db().execute(f'SELECT * FROM {t} ORDER BY rowid')] for t in before})

    def test_review_append_preserves_thesis_and_advances_schedule(self):
        entry_id=self.create().json['payload']['id']
        self.assertEqual(self.review(entry_id).status_code,201)
        entry=self.detail(entry_id)
        self.assertEqual(entry['thesis'],'Original reasoning');self.assertEqual(entry['review_date'],'2027-01-01')
        self.assertEqual(entry['version'],2);self.assertEqual(entry['review_count'],1)
        self.assertEqual(entry['reviews'][0]['lessons'],'Avoid assumptions');self.assertFalse(entry['review_due'])

    def test_backdated_review_does_not_replace_newer_schedule_or_status(self):
        entry_id=self.create().json['payload']['id']
        self.review(entry_id)
        response=self.client.post(f'/api/investor-journal/{entry_id}/reviews',json={'version':2,'review_date':'2025-06-01','outcome':'NOTE','notes':'Historical note','entry_status':'CLOSED','next_review_date':None})
        self.assertEqual(response.status_code,201)
        entry=self.detail(entry_id)
        self.assertEqual(entry['status'],'ACTIVE');self.assertEqual(entry['review_date'],'2027-01-01')
        self.assertEqual(entry['review_count'],2);self.assertEqual(entry['reviews'][0]['review_date'],'2026-01-01')

    def test_stale_edit_archive_or_review_cannot_overwrite_or_duplicate(self):
        entry_id=self.create().json['payload']['id'];self.review(entry_id)
        requests=[lambda:self.client.put(f'/api/investor-journal/{entry_id}',json={**self.plan,'version':1}),
                  lambda:self.client.put(f'/api/investor-journal/{entry_id}/archive',json={'version':1,'archived':True}),
                  lambda:self.review(entry_id)]
        for request in requests:
            self.assertEqual(request().status_code,409)
        entry=self.detail(entry_id)
        self.assertEqual(entry['version'],2);self.assertFalse(entry['is_archived']);self.assertEqual(entry['review_count'],1)

    def test_archive_restore_and_export_keep_complete_history(self):
        entry_id=self.create().json['payload']['id'];self.review(entry_id)
        self.assertEqual(self.client.put(f'/api/investor-journal/{entry_id}/archive',json={'version':2,'archived':True}).status_code,200)
        self.assertEqual(self.client.get('/api/investor-journal/').json['payload']['total'],0)
        self.assertEqual(self.client.get('/api/investor-journal/?archived=1').json['payload']['total'],1)
        self.assertEqual(self.review(entry_id,version=3).status_code,400)
        exported=self.client.get('/api/investor-journal/export').json['payload']
        self.assertEqual(exported['schema_version'],1);self.assertEqual(len(exported['entries'][0]['reviews']),1)
        self.assertEqual(len(exported['entries'][0]['revisions']),3)
        self.assertEqual(self.client.put(f'/api/investor-journal/{entry_id}/archive',json={'version':3,'archived':False}).status_code,200)
        self.assertEqual(self.detail(entry_id)['version'],4)

    def test_validation_errors_do_not_leave_partial_records(self):
        for changes in [{'title':''},{'confidence':True},{'confidence':6},{'portfolio_id':True},{'portfolio_id':9999},{'kind':'UNKNOWN'},
                        {'status':'UNKNOWN'},{'entry_date':'2099-01-01'},{'entry_date':'20260101'},{'review_date':'2024-01-01'},
                        {'ticker':'<script>'},{'tags':['x'*26]},{'tags':['a']*9},{'thesis':False},{'risks':'x'*5001}]:
            with self.subTest(changes=changes):self.assertEqual(self.create(**changes).status_code,400)
        self.assertEqual(self.client.get('/api/investor-journal/').json['payload']['total'],0)
        with self.app.app_context():self.assertEqual(get_db().execute('SELECT COUNT(*) FROM investor_journal_revisions').fetchone()[0],0)

    def test_invalid_review_and_entry_date_edit_leave_existing_history_intact(self):
        entry_id=self.create().json['payload']['id']
        bad=self.client.post(f'/api/investor-journal/{entry_id}/reviews',json={'version':1,'review_date':'2024-01-01','outcome':'NOTE','notes':'Old','entry_status':'ACTIVE'})
        self.assertEqual(bad.status_code,400);self.assertEqual(self.detail(entry_id)['version'],1)
        self.review(entry_id)
        response=self.client.put(f'/api/investor-journal/{entry_id}',json={**self.plan,'version':2,'entry_date':'2026-02-01','review_date':None})
        self.assertEqual(response.status_code,400);self.assertEqual(self.detail(entry_id)['version'],2)

    def test_unicode_search_and_filters_and_closed_entry_not_due(self):
        self.create(title='Żółta teza',tags=['Długoterminowe'])
        self.create(title='Closed',status='CLOSED')
        result=self.client.get('/api/investor-journal/?q=ŻÓŁTA&tag=długoterminowe').json['payload']
        self.assertEqual(result['total'],1)
        due=self.client.get('/api/investor-journal/?due=1').json['payload']
        self.assertEqual(due['total'],1);self.assertEqual(due['stats']['closed'],1)
        filtered=self.client.get(f'/api/investor-journal/?ticker=CSPX.L&portfolio={self.portfolio}&status=ACTIVE').json['payload']
        self.assertEqual(filtered['total'],1)

    def test_portfolio_archive_preserves_existing_note_but_blocks_new_assignment(self):
        entry_id=self.create().json['payload']['id']
        with self.app.app_context():get_db().execute('UPDATE portfolios SET is_archived=1 WHERE id=?',(self.portfolio,));get_db().commit()
        self.assertEqual(self.create().status_code,400)
        self.assertEqual(self.client.put(f'/api/investor-journal/{entry_id}',json={**self.plan,'version':1,'title':'Correction'}).status_code,200)
        self.assertEqual(self.detail(entry_id)['portfolio_archived'],1)

    def test_pagination_is_stable_and_invalid_filters_rejected(self):
        with self.app.app_context():
            db=get_db()
            db.executemany("INSERT INTO investor_journal(title,entry_date,kind,status,created_at,updated_at) VALUES (?,'2026-01-01','NOTE','WATCHING','2026-01-01','2026-01-01')",[(f'Note {i}',) for i in range(55)]);db.commit()
        first=self.client.get('/api/investor-journal/').json['payload'];second=self.client.get('/api/investor-journal/?page=2').json['payload']
        self.assertEqual(first['total'],55);self.assertEqual(len(first['entries']),50);self.assertEqual(len(second['entries']),5)
        self.assertFalse({e['id'] for e in first['entries']}&{e['id'] for e in second['entries']})
        for query in ['page=0','page=bad','status=bad','due=bad','archived=bad','portfolio=bad']:
            self.assertEqual(self.client.get('/api/investor-journal/?'+query).status_code,400)

    def test_missing_record_and_malformed_json(self):
        self.assertEqual(self.client.get('/api/investor-journal/99999').status_code,404)
        self.assertEqual(self.client.post('/api/investor-journal/',json=[]).status_code,400)
        entry_id=self.create().json['payload']['id']
        self.assertEqual(self.client.put(f'/api/investor-journal/{entry_id}',json={**self.plan,'version':False}).status_code,400)
