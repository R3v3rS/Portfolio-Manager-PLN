import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd
from flask import Flask
from openpyxl import Workbook
from werkzeug.datastructures import FileStorage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import get_db, init_db
from import_staging_service import ImportStagingService, ImportBookingError
from xtb_file_reader import read_xtb_file


def export_file(rows=None, *, sheet_name='Cash Operations', bad_dimensions=False):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(['Account number', 'demo-ike'])
    sheet.append(['Cash Operations'])
    sheet.append(['Date from (UTC)', '2026-07-03 22:00:00'])
    sheet.append(['Date to (UTC)', '2026-10-04 17:54:36'])
    sheet.append(['Type', 'Instrument', 'Ticker', 'Time', 'Amount', 'ID', 'Comment', 'Product'])
    for row in rows or [['Stock purchase', 'Dino', 'DNP.PL', '2026-09-01 10:00:00.123', -10, '0001', 'OPEN BUY 0.5 @ 20', 'IKE']]:
        sheet.append(row)
    sheet.append(['Total', None, None, None, 99999])
    for name in ('Open Positions', 'Closed Positions'):
        workbook.create_sheet(name).append(['Ignore these entirely'])
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    if bad_dimensions:
        source = ZipFile(io.BytesIO(stream.getvalue()))
        rewritten = io.BytesIO()
        with ZipFile(rewritten, 'w') as target:
            for name in source.namelist():
                content = source.read(name)
                if name == 'xl/worksheets/sheet1.xml':
                    import re
                    content = re.sub(rb'<dimension ref="[^"]+"', b'<dimension ref="A1"', content)
                target.writestr(name, content)
        source.close()
        stream = rewritten
    stream.seek(0)
    return FileStorage(stream=stream, filename='export.xlsx')


class XtbXlsxImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=str(Path(self.temp.name) / 'test.db'))
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        init_db(self.app)
        db = get_db()
        self.portfolio = db.execute("INSERT INTO portfolios(name,account_type,current_cash) VALUES('IKE','IKE',100)").lastrowid
        db.execute("INSERT INTO symbol_mappings(symbol_input,ticker,currency) VALUES('DINO','DNP.WA','PLN')")
        db.commit()

    def session(self, rows=None, **options):
        frame = read_xtb_file(export_file(rows, **options))
        return ImportStagingService.create_session(self.portfolio, frame, source_file='export.xlsx')

    def test_reads_cash_operations_despite_incorrect_used_range(self):
        session = self.session(bad_dimensions=True)
        row = session['rows'][0]
        self.assertEqual(session['summary']['input_rows'], 1)
        self.assertEqual(row['ticker'], 'DNP.WA')
        self.assertEqual(row['quantity'], 0.5)
        self.assertEqual(row['total_value'], 10)
        self.assertEqual(row['source_operation_id'], '0001')
        self.assertEqual(row['source_row_number'], 6)
        self.assertEqual(row['instrument_name'], 'Dino')
        self.assertEqual(row['conflict_type'], None)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM transactions').fetchone()[0], 0)
        self.assertEqual(get_db().execute('SELECT current_cash FROM portfolios').fetchone()[0], 100)

    def test_missing_cash_sheet_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Cash Operations'):
            read_xtb_file(export_file(sheet_name='History'))

    def test_corrupt_xlsx_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'XLSX'):
            read_xtb_file(FileStorage(stream=io.BytesIO(b'not a workbook'), filename='bad.xlsx'))

    def test_csv_bom_semicolon_and_text_ids(self):
        content = '\ufeffType;Time;Amount;Ticker;Comment;ID\nStock purchase;2026-09-01;-10,00;DNP.PL;OPEN BUY 0.5 @ 20;0001\n'
        frame = read_xtb_file(FileStorage(stream=io.BytesIO(content.encode()), filename='export.csv'))
        session = ImportStagingService.create_session(self.portfolio, frame)
        self.assertEqual(session['rows'][0]['ticker'], 'DNP.WA')
        self.assertEqual(session['rows'][0]['source_operation_id'], '0001')
        self.assertEqual(session['rows'][0]['total_value'], 10)

    def test_reimport_by_id_never_changes_cash_twice(self):
        first = self.session()
        self.assertEqual(ImportStagingService.book_session(first['session_id'])['booked'], 1)
        second = self.session()
        self.assertEqual(second['rows'][0]['conflict_type'], 'database_duplicate')
        self.assertEqual(ImportStagingService.book_session(second['session_id'])['booked'], 0)
        skipped = ImportStagingService.book_session(second['session_id'], [second['rows'][0]['id']])
        self.assertEqual(skipped['duplicate_skipped'], 1)
        db = get_db()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0], 1)
        self.assertEqual(db.execute('SELECT current_cash FROM portfolios').fetchone()[0], 90)
        self.assertEqual(db.execute('SELECT xtb_account,xtb_operation_id FROM transactions').fetchone()[:], ('demo-ike', '0001'))

    def test_two_identical_fills_with_distinct_ids_are_both_valid(self):
        rows = [['Stock purchase', 'Dino', 'DNP.PL', '2026-09-01 10:00:00', -10, str(i), 'OPEN BUY 0.5 @ 20', 'IKE'] for i in (1, 2)]
        first = self.session([rows[0]])
        ImportStagingService.book_session(first['session_id'])
        second = self.session([rows[1]])
        self.assertEqual(second['rows'][0]['conflict_type'], None)
        self.assertEqual(ImportStagingService.book_session(second['session_id'])['booked'], 1)
        self.assertEqual(get_db().execute('SELECT quantity FROM holdings').fetchone()[0], 1)

    def test_identical_cash_operations_with_distinct_ids_are_valid(self):
        rows = [['Free funds interest', '', '', '2026-09-01 10:00:00', 0.5, str(i), '', 'IKE'] for i in (1, 2)]
        session = self.session(rows)
        self.assertTrue(all(row['conflict_type'] is None for row in session['rows']))
        self.assertEqual(ImportStagingService.book_session(session['session_id'])['booked'], 2)

    def test_repeated_id_in_same_file_is_a_duplicate_even_for_stocks(self):
        row = ['Stock purchase', 'Dino', 'DNP.PL', '2026-09-01 10:00:00', -10, '1', 'OPEN BUY 0.5 @ 20', 'IKE']
        session = self.session([row, row])
        self.assertEqual(session['rows'][1]['conflict_type'], 'file_internal_duplicate')
        self.assertEqual(ImportStagingService.book_session(session['session_id'])['booked'], 1)

    def test_changed_data_for_same_id_is_blocked_even_when_confirmed(self):
        first = self.session()
        ImportStagingService.book_session(first['session_id'])
        changed = self.session([['Stock purchase', 'Dino', 'DNP.PL', '2026-09-01 10:00:00.123', -20, '0001', 'OPEN BUY 0.5 @ 20', 'IKE']])
        self.assertEqual(changed['rows'][0]['conflict_type'], 'source_mismatch')
        self.assertEqual(ImportStagingService.book_session(changed['session_id'], [changed['rows'][0]['id']])['booked'], 0)
        self.assertEqual(get_db().execute('SELECT current_cash FROM portfolios').fetchone()[0], 90)

    def test_concurrent_previews_are_rechecked_when_booking(self):
        first, second = self.session(), self.session()
        ImportStagingService.book_session(first['session_id'])
        result = ImportStagingService.book_session(second['session_id'])
        self.assertEqual(result['booked'], 0)
        self.assertEqual(result['session']['rows'][0]['conflict_type'], 'database_duplicate')

    def test_matching_broker_id_does_not_consume_a_different_legacy_fill(self):
        first = self.session()
        ImportStagingService.book_session(first['session_id'])
        db = get_db()
        db.execute('INSERT INTO transactions(portfolio_id,ticker,type,date,quantity,price,total_value) VALUES(?,\'DNP.WA\',\'BUY\',\'2026-09-01 10:00:00\',0.5,20,10)', (self.portfolio,))
        db.commit()
        row = ['Stock purchase', 'Dino', 'DNP.PL', '2026-09-01 10:00:00.123', -10, '0002', 'OPEN BUY 0.5 @ 20', 'IKE']
        frame = read_xtb_file(export_file([row]))
        first_row = read_xtb_file(export_file()).iloc[0].to_dict()
        frame = pd.concat([pd.DataFrame([first_row]), frame], ignore_index=True)
        frame.attrs['source_account'] = 'demo-ike'
        session = ImportStagingService.create_session(self.portfolio, frame)
        self.assertEqual([row['conflict_type'] for row in session['rows']], ['database_duplicate', 'database_duplicate'])

    def test_wrong_destination_account_is_rejected_before_creating_session(self):
        db = get_db()
        db.execute("UPDATE portfolios SET account_type='STANDARD'")
        db.commit()
        with self.assertRaisesRegex(ValueError, 'Typ rachunku'):
            self.session()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM import_sessions').fetchone()[0], 0)

    def test_unknown_symbol_does_not_use_similar_name(self):
        session = self.session([['Stock purchase', 'Dino', 'XYZ.PL', '2026-09-01', -10, '2', 'OPEN BUY 0.5 @ 20', 'IKE']])
        self.assertEqual(session['rows'][0]['conflict_type'], 'missing_symbol')

    def test_failed_booking_rolls_back_source_ids_and_financial_data(self):
        rows = [['Free funds interest', '', '', '2026-09-01', 1, str(i), '', 'IKE'] for i in (1, 2)]
        session = self.session(rows)
        original = ImportStagingService._book_single_row
        def fail_second(row, db, book_tx_only=False):
            if row['source_operation_id'] == '2':
                raise ValueError('simulated failure')
            return original(row, db, book_tx_only)
        with patch.object(ImportStagingService, '_book_single_row', side_effect=fail_second):
            with self.assertRaises(ImportBookingError):
                ImportStagingService.book_session(session['session_id'])
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM transactions').fetchone()[0], 0)
        self.assertEqual(get_db().execute('SELECT current_cash FROM portfolios').fetchone()[0], 100)


if __name__ == '__main__':
    unittest.main()
