import sqlite3
from contextlib import closing
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from flask import Flask
from database import init_db,get_db
from api.exceptions import ValidationError
import backup_service as backups

class BackupTest(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.path=Path(self.tmp.name)/'app.db'
        self.app=Flask(__name__);self.app.config.update(DATABASE=str(self.path),TESTING=True);init_db(self.app)
        with self.app.app_context():
            db=get_db();db.execute("INSERT INTO portfolios(name,account_type,current_cash) VALUES('Test','IKE',123)");db.commit()
    def tearDown(self):self.tmp.cleanup()
    def cash(self):
        with closing(sqlite3.connect(self.path)) as db:return db.execute('SELECT current_cash FROM portfolios').fetchone()[0]

    def test_restore_preserves_rescue_copy(self):
        name=backups.create(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE portfolios SET current_cash=456');db.commit()
        result=backups.restore(self.path,name)
        self.assertEqual(self.cash(),123)
        with closing(sqlite3.connect(backups.directory(self.path)/result['rescue_copy'])) as db:self.assertEqual(db.execute('SELECT current_cash FROM portfolios').fetchone()[0],456)

    def test_daily_and_schema_copies_are_deduplicated(self):
        backups.automatic(self.path,before_update=True);backups.automatic(self.path,before_update=True)
        self.assertEqual(len(backups.workspace(self.path)['items']),2)

    def test_retention_never_removes_manual(self):
        manual=backups.create(self.path)
        for _ in range(16):backups.create(self.path,'daily')
        items=backups.workspace(self.path)['items']
        self.assertEqual(len([i for i in items if i['kind']=='daily']),14)
        self.assertIn(manual,[i['name'] for i in items])

    def test_invalid_file_and_escape_do_not_change_database(self):
        (backups.directory(self.path)/'manual-invalid.db').write_text('bad')
        for name in ('../app.db','manual-invalid.db','manual-not-found.db'):
            with self.assertRaises(ValidationError):backups.restore(self.path,name)
        self.assertEqual(self.cash(),123)

    def test_unrelated_database_with_matching_table_names_is_rejected(self):
        path=backups.directory(self.path)/'manual-wrong-schema.db'
        with closing(sqlite3.connect(path)) as db:
            for table in ('portfolios','holdings','transactions'):db.execute(f'CREATE TABLE {table}(id INTEGER)')
            db.commit()
        with self.assertRaises(ValidationError):backups.restore(self.path,path.name)
        self.assertEqual(self.cash(),123)

    def test_diagnostic_databases_are_not_restore_candidates(self):
        import shutil
        path=backups.directory(self.path)/'audit-rehearsal.db'
        shutil.copy2(self.path,path)
        self.assertNotIn(path.name,[i['name'] for i in backups.workspace(self.path)['items']])
        with self.assertRaises(ValidationError):backups.restore(self.path,path.name)

    def test_restore_route_requires_confirmation_and_local_origin(self):
        from routes_backups import backups_bp
        from api.response import error_response
        self.app.register_blueprint(backups_bp)
        @self.app.errorhandler(ValidationError)
        def error(e):return error_response('validation_error',str(e))
        client=self.app.test_client();name=backups.create(self.path)
        self.assertEqual(client.post('/api/backups/restore',json={'name':name}).status_code,400)
        self.assertEqual(client.post('/api/backups/restore',headers={'Origin':'https://external.example'},json={'name':name,'confirmation':'PRZYWRÓĆ'}).status_code,400)
        response=client.post('/api/backups/restore',json={'name':name,'confirmation':'PRZYWRÓĆ'})
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(self.cash(),123)

    def test_failed_schema_upgrade_restores_previous_state(self):
        from routes_backups import backups_bp
        from api.response import error_response
        from unittest.mock import patch
        self.app.register_blueprint(backups_bp)
        @self.app.errorhandler(ValidationError)
        def error(e):return error_response('validation_error',str(e))
        name=backups.create(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE portfolios SET current_cash=456');db.commit()
        with patch('database.init_db',side_effect=[RuntimeError('upgrade failed'),None]):
            response=self.app.test_client().post('/api/backups/restore',json={'name':name,'confirmation':'PRZYWRÓĆ'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.cash(),456)
