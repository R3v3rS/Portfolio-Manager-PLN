import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from flask import Flask

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import get_db, init_db  # noqa: E402
from import_staging_service import ImportStagingService  # noqa: E402


class ImportStagingServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=str(Path(self.temp_dir.name) / 'staging-test.db'))
        self.ctx = self.app.app_context()
        self.ctx.push()
        init_db(self.app)

        db = get_db()
        self.portfolio_id = db.execute(
            "INSERT INTO portfolios (name, current_cash) VALUES ('Main', 0.0)"
        ).lastrowid
        self.sub_portfolio_id = db.execute(
            'INSERT INTO portfolios (name, parent_portfolio_id, current_cash) VALUES (?, ?, ?)',
            ('Sub', self.portfolio_id, 0.0),
        ).lastrowid
        db.execute(
            "INSERT INTO symbol_mappings (symbol_input, ticker, currency) VALUES ('AAPL.US', 'AAPL', 'USD')"
        )
        db.execute(
            "INSERT INTO symbol_mappings (symbol_input, ticker, currency) VALUES ('MSFT.US', 'MSFT', 'USD')"
        )
        db.commit()

    def tearDown(self):
        self.ctx.pop()
        self.temp_dir.cleanup()

    @staticmethod
    def _df(rows):
        return pd.DataFrame(rows)

    def test_create_session_returns_all_rows(self):
        db = get_db()
        db.execute(
            '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost)
               VALUES (?, 'AAPL', 10, 100, 1000)''',
            (self.portfolio_id,),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-01 10:00:00', 'Type': 'Deposit', 'Amount': '1000', 'Comment': ''},
            {'Time': '2026-01-02 10:00:00', 'Type': 'Stock purchase', 'Amount': '500', 'Comment': 'OPEN BUY 5 @ 100', 'Symbol': 'AAPL.US'},
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '300', 'Comment': 'CLOSE SELL 2 @ 150', 'Symbol': 'AAPL.US'},
        ])

        result = ImportStagingService.create_session(self.portfolio_id, df)
        self.assertEqual(len(result['rows']), 3)
        self.assertEqual(result['summary']['conflicts'], 0)
        self.assertEqual(result['summary']['pending'], 3)

    def test_create_session_sell_without_holding_is_conflict(self):
        df = self._df([
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '300', 'Comment': 'CLOSE SELL 2 @ 150', 'Symbol': 'AAPL.US'},
        ])

        result = ImportStagingService.create_session(self.portfolio_id, df)
        row = result['rows'][0]
        self.assertEqual(row['conflict_type'], 'missing_holding')
        self.assertEqual(row['status'], 'pending')
        self.assertEqual(result['summary']['conflicts'], 1)

    def test_create_session_sell_exceeding_holding_is_conflict(self):
        df = self._df([
            {'Time': '2026-01-01 10:00:00', 'Type': 'Stock purchase', 'Amount': '500', 'Comment': 'OPEN BUY 5 @ 100', 'Symbol': 'AAPL.US'},
            {'Time': '2026-01-02 10:00:00', 'Type': 'Stock sell', 'Amount': '1000', 'Comment': 'CLOSE SELL 10 @ 100', 'Symbol': 'AAPL.US'},
        ])

        result = ImportStagingService.create_session(self.portfolio_id, df)
        sell_row = [row for row in result['rows'] if row['type'] == 'SELL'][0]
        self.assertEqual(sell_row['conflict_type'], 'insufficient_qty')

    def test_create_session_detects_database_duplicate(self):
        db = get_db()
        db.execute(
            '''INSERT INTO transactions (portfolio_id, ticker, date, type, quantity, price, total_value)
               VALUES (?, 'AAPL', '2026-01-02 10:00:00', 'BUY', 5, 100, 500)''',
            (self.portfolio_id,),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-02 10:00:00', 'Type': 'Stock purchase', 'Amount': '500', 'Comment': 'OPEN BUY 5 @ 100', 'Symbol': 'AAPL.US'},
        ])

        result = ImportStagingService.create_session(self.portfolio_id, df)
        self.assertEqual(result['rows'][0]['conflict_type'], 'database_duplicate')

    def test_create_session_detects_duplicate_from_other_subportfolio_scope(self):
        db = get_db()
        db.execute(
            '''INSERT INTO transactions (portfolio_id, ticker, date, type, quantity, price, total_value, sub_portfolio_id)
               VALUES (?, 'AAPL', '2026-01-02 10:00:00', 'BUY', 5, 100, 500, ?)''',
            (self.portfolio_id, self.sub_portfolio_id),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-02 10:00:00', 'Type': 'Stock purchase', 'Amount': '500', 'Comment': 'OPEN BUY 5 @ 100', 'Symbol': 'AAPL.US'},
        ])

        result = ImportStagingService.create_session(self.portfolio_id, df)
        self.assertEqual(result['rows'][0]['conflict_type'], 'database_duplicate')

    def test_create_session_reports_file_and_database_duplicate_together(self):
        db = get_db()
        db.execute(
            '''INSERT INTO transactions (portfolio_id, ticker, date, type, quantity, price, total_value)
               VALUES (?, 'AAPL', '2026-01-02 10:00:00', 'BUY', 5, 100, 500)''',
            (self.portfolio_id,),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-02 10:00:00', 'Type': 'Stock purchase', 'Amount': '500', 'Comment': 'OPEN BUY 5 @ 100', 'Symbol': 'AAPL.US'},
            {'Time': '2026-01-02 10:00:00', 'Type': 'Stock purchase', 'Amount': '500', 'Comment': 'OPEN BUY 5 @ 100', 'Symbol': 'AAPL.US'},
        ])

        result = ImportStagingService.create_session(self.portfolio_id, df)
        second_row = result['rows'][1]
        self.assertEqual(second_row['conflict_type'], 'file_internal_duplicate')
        self.assertEqual(second_row['conflict_details']['also_database_duplicate'], True)
        self.assertEqual(second_row['conflict_details']['conflict_types'], ['file_internal_duplicate', 'database_duplicate'])

    def test_assign_row_changes_status(self):
        df = self._df([
            {'Time': '2026-01-01 10:00:00', 'Type': 'Deposit', 'Amount': '100', 'Comment': ''},
        ])
        result = ImportStagingService.create_session(self.portfolio_id, df)

        updated = ImportStagingService.assign_row(result['session_id'], result['rows'][0]['id'], self.sub_portfolio_id)
        self.assertEqual(updated['status'], 'assigned')
        self.assertEqual(updated['target_sub_portfolio_id'], self.sub_portfolio_id)

    def test_assign_row_clears_conflict_if_holding_exists_on_sub(self):
        db = get_db()
        db.execute(
            '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost, sub_portfolio_id)
               VALUES (?, 'AAPL', 3, 100, 300, ?)''',
            (self.portfolio_id, self.sub_portfolio_id),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '300', 'Comment': 'CLOSE SELL 2 @ 150', 'Symbol': 'AAPL.US'},
        ])
        result = ImportStagingService.create_session(self.portfolio_id, df)
        row = result['rows'][0]
        self.assertEqual(row['conflict_type'], 'missing_holding')

        updated = ImportStagingService.assign_row(result['session_id'], row['id'], self.sub_portfolio_id)
        self.assertEqual(updated['status'], 'assigned')
        self.assertIsNone(updated['conflict_type'])

    def test_assign_row_recompute_sell_keeps_insufficient_qty_when_holding_too_small(self):
        db = get_db()
        db.execute(
            '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost, sub_portfolio_id)
               VALUES (?, 'AAPL', 1, 100, 100, ?)''',
            (self.portfolio_id, self.sub_portfolio_id),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '1000', 'Comment': 'CLOSE SELL 10 @ 100', 'Symbol': 'AAPL.US'},
        ])
        result = ImportStagingService.create_session(self.portfolio_id, df)
        row = result['rows'][0]
        self.assertEqual(row['conflict_type'], 'missing_holding')

        updated = ImportStagingService.assign_row(result['session_id'], row['id'], self.sub_portfolio_id)
        self.assertEqual(updated['conflict_type'], 'insufficient_qty')
        self.assertEqual(updated['conflict_details'], {'required_qty': 10.0, 'available_qty': 1.0})

    def test_assign_row_recompute_sell_sets_missing_holding_when_holding_zero(self):
        df = self._df([
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '1000', 'Comment': 'CLOSE SELL 10 @ 100', 'Symbol': 'AAPL.US'},
        ])
        result = ImportStagingService.create_session(self.portfolio_id, df)
        row = result['rows'][0]
        self.assertEqual(row['conflict_type'], 'missing_holding')

        updated = ImportStagingService.assign_row(result['session_id'], row['id'], self.sub_portfolio_id)
        self.assertEqual(updated['conflict_type'], 'missing_holding')
        self.assertEqual(updated['conflict_details'], {'required_qty': 10.0, 'available_qty': 0})

    def test_assign_row_recompute_sell_clears_conflict_when_holding_sufficient(self):
        db = get_db()
        db.execute(
            '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost, sub_portfolio_id)
               VALUES (?, 'AAPL', 15, 100, 1500, ?)''',
            (self.portfolio_id, self.sub_portfolio_id),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '1000', 'Comment': 'CLOSE SELL 10 @ 100', 'Symbol': 'AAPL.US'},
        ])
        result = ImportStagingService.create_session(self.portfolio_id, df)
        row = result['rows'][0]

        updated = ImportStagingService.assign_row(result['session_id'], row['id'], self.sub_portfolio_id)
        self.assertIsNone(updated['conflict_type'])

    def test_assign_row_recompute_sell_for_original_insufficient_qty_conflict(self):
        db = get_db()
        db.execute(
            '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost)
               VALUES (?, 'AAPL', 5, 100, 500)''',
            (self.portfolio_id,),
        )
        db.execute(
            '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost, sub_portfolio_id)
               VALUES (?, 'AAPL', 1, 100, 100, ?)''',
            (self.portfolio_id, self.sub_portfolio_id),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '1000', 'Comment': 'CLOSE SELL 10 @ 100', 'Symbol': 'AAPL.US'},
        ])
        result = ImportStagingService.create_session(self.portfolio_id, df)
        row = result['rows'][0]
        self.assertEqual(row['conflict_type'], 'insufficient_qty')

        updated = ImportStagingService.assign_row(result['session_id'], row['id'], self.sub_portfolio_id)
        self.assertEqual(updated['conflict_type'], 'insufficient_qty')
        self.assertEqual(updated['conflict_details'], {'required_qty': 10.0, 'available_qty': 1.0})

    def test_book_session_books_normal_rows(self):
        df = self._df([
            {'Time': '2026-01-01 10:00:00', 'Type': 'Deposit', 'Amount': '1000', 'Comment': ''},
            {'Time': '2026-01-02 10:00:00', 'Type': 'Stock purchase', 'Amount': '500', 'Comment': 'OPEN BUY 5 @ 100', 'Symbol': 'AAPL.US'},
        ])
        session = ImportStagingService.create_session(self.portfolio_id, df)

        result = ImportStagingService.book_session(session['session_id'])
        self.assertEqual(result['booked'], 2)

        db = get_db()
        cash = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (self.portfolio_id,)).fetchone()['current_cash']
        holding = db.execute('SELECT quantity FROM holdings WHERE portfolio_id = ? AND ticker = ?', (self.portfolio_id, 'AAPL')).fetchone()
        status_rows = db.execute('SELECT status FROM import_staging WHERE import_session_id = ?', (session['session_id'],)).fetchall()
        self.assertAlmostEqual(float(cash), 500.0)
        self.assertAlmostEqual(float(holding['quantity']), 5.0)
        self.assertTrue(all(row['status'] == 'booked' for row in status_rows))

    def test_book_session_skips_unconfirmed_conflicts(self):
        df = self._df([
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '300', 'Comment': 'CLOSE SELL 2 @ 150', 'Symbol': 'AAPL.US'},
        ])
        session = ImportStagingService.create_session(self.portfolio_id, df)

        result = ImportStagingService.book_session(session['session_id'])
        self.assertEqual(result['skipped_conflicts'], 1)

        cash = get_db().execute('SELECT current_cash FROM portfolios WHERE id = ?', (self.portfolio_id,)).fetchone()['current_cash']
        self.assertAlmostEqual(float(cash), 0.0)

    def test_book_session_confirmed_conflict_books_tx_only(self):
        df = self._df([
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '300', 'Comment': 'CLOSE SELL 2 @ 150', 'Symbol': 'AAPL.US'},
        ])
        session = ImportStagingService.create_session(self.portfolio_id, df)
        row_id = session['rows'][0]['id']

        result = ImportStagingService.book_session(session['session_id'], confirmed_row_ids=[row_id])
        self.assertEqual(result['booked_tx_only'], 1)

        db = get_db()
        cash = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (self.portfolio_id,)).fetchone()['current_cash']
        tx_count = db.execute('SELECT COUNT(*) AS c FROM transactions WHERE portfolio_id = ?', (self.portfolio_id,)).fetchone()['c']
        holding_count = db.execute('SELECT COUNT(*) AS c FROM holdings WHERE portfolio_id = ?', (self.portfolio_id,)).fetchone()['c']
        staged = db.execute('SELECT status FROM import_staging WHERE id = ?', (row_id,)).fetchone()['status']

        self.assertAlmostEqual(float(cash), 0.0)
        self.assertEqual(tx_count, 1)
        self.assertEqual(holding_count, 0)
        self.assertEqual(staged, 'booked')

    def test_book_session_confirmed_database_duplicate_books_normally(self):
        db = get_db()
        db.execute(
            '''INSERT INTO transactions (portfolio_id, ticker, date, type, quantity, price, total_value)
               VALUES (?, 'CASH', '2026-01-01 10:00:00', 'DEPOSIT', 1, 1000, 1000)''',
            (self.portfolio_id,),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-01 10:00:00', 'Type': 'Deposit', 'Amount': '1000', 'Comment': ''},
        ])
        session = ImportStagingService.create_session(self.portfolio_id, df)
        row_id = session['rows'][0]['id']
        self.assertEqual(session['rows'][0]['conflict_type'], 'database_duplicate')

        result = ImportStagingService.book_session(session['session_id'], confirmed_row_ids=[row_id])
        self.assertEqual(result['booked'], 1)
        self.assertEqual(result['booked_tx_only'], 0)

        cash = get_db().execute('SELECT current_cash FROM portfolios WHERE id = ?', (self.portfolio_id,)).fetchone()['current_cash']
        self.assertAlmostEqual(float(cash), 1000.0)

    def test_book_session_normal_sell_updates_cash_and_holdings(self):
        db = get_db()
        db.execute(
            '''INSERT INTO holdings (portfolio_id, ticker, quantity, average_buy_price, total_cost)
               VALUES (?, 'AAPL', 10, 100, 1000)''',
            (self.portfolio_id,),
        )
        db.commit()

        df = self._df([
            {'Time': '2026-01-03 10:00:00', 'Type': 'Stock sell', 'Amount': '750', 'Comment': 'CLOSE SELL 5 @ 150', 'Symbol': 'AAPL.US'},
        ])
        session = ImportStagingService.create_session(self.portfolio_id, df)
        result = ImportStagingService.book_session(session['session_id'])
        self.assertEqual(result['booked'], 1)

        db = get_db()
        cash = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (self.portfolio_id,)).fetchone()['current_cash']
        qty = db.execute('SELECT quantity FROM holdings WHERE portfolio_id = ? AND ticker = ?', (self.portfolio_id, 'AAPL')).fetchone()['quantity']
        status = db.execute('SELECT status FROM import_staging WHERE import_session_id = ?', (session['session_id'],)).fetchone()['status']
        self.assertAlmostEqual(float(cash), 750.0)
        self.assertAlmostEqual(float(qty), 5.0)
        self.assertEqual(status, 'booked')

    def test_reject_row_excludes_from_booking(self):
        df = self._df([
            {'Time': '2026-01-01 10:00:00', 'Type': 'Deposit', 'Amount': '1000', 'Comment': ''},
        ])
        session = ImportStagingService.create_session(self.portfolio_id, df)
        row_id = session['rows'][0]['id']

        ImportStagingService.reject_row(session['session_id'], row_id)
        result = ImportStagingService.book_session(session['session_id'])
        self.assertEqual(result['booked'], 0)
        self.assertEqual(result['rejected'], 1)

        tx_count = get_db().execute('SELECT COUNT(*) AS c FROM transactions WHERE portfolio_id = ?', (self.portfolio_id,)).fetchone()['c']
        self.assertEqual(tx_count, 0)

    def test_delete_session_removes_pending_only(self):
        df = self._df([
            {'Time': '2026-01-01 10:00:00', 'Type': 'Deposit', 'Amount': '1000', 'Comment': ''},
            {'Time': '2026-01-02 10:00:00', 'Type': 'Stock sell', 'Amount': '500', 'Comment': 'CLOSE SELL 5 @ 100', 'Symbol': 'AAPL.US'},
        ])
        session = ImportStagingService.create_session(self.portfolio_id, df)

        ImportStagingService.book_session(session['session_id'])
        result = ImportStagingService.delete_session(session['session_id'])
        self.assertEqual(result['deleted'], 1)

        rows = get_db().execute(
            'SELECT status FROM import_staging WHERE import_session_id = ? ORDER BY id',
            (session['session_id'],),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'booked')


if __name__ == '__main__':
    unittest.main()
