import os
import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import get_db, init_db  # noqa: E402
from portfolio_audit_service import PortfolioAuditService  # noqa: E402


class PortfolioAuditRebuildCashConsistencyTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'audit-rebuild-cash-test.db')

        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=self.db_path)

        with self.app.app_context():
            init_db(self.app)
            db = get_db()
            cursor = db.execute(
                'INSERT INTO portfolios (name, account_type, current_cash) VALUES (?, ?, ?)',
                ('Audit Cash Rebuild', 'STANDARD', 0.0),
            )
            self.portfolio_id = cursor.lastrowid

            transactions = [
                ('2026-01-01', 'DEPOSIT', 'CASH', 0.0, 0.0, 1000.0),
                ('2026-01-02', 'BUY', 'AAPL', 1.0, 400.0, 400.0),
                ('2026-01-03', 'SELL', 'AAPL', 1.0, 200.0, 200.0),
                ('2026-01-04', 'DIVIDEND', 'AAPL', 0.0, 0.0, 30.0),
                ('2026-01-05', 'WITHDRAW', 'CASH', 0.0, 0.0, 100.0),
            ]

            for tx_date, tx_type, ticker, quantity, price, total_value in transactions:
                db.execute(
                    '''
                    INSERT INTO transactions (portfolio_id, ticker, date, type, quantity, price, total_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (self.portfolio_id, ticker, tx_date, tx_type, quantity, price, total_value),
                )

            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_rebuild_holdings_from_transactions_cash_uses_cash_delta_rules(self):
        with self.app.app_context():
            rebuilt = PortfolioAuditService.rebuild_holdings_from_transactions(self.portfolio_id)

        self.assertEqual(rebuilt['cash'], 730.0)


if __name__ == '__main__':
    unittest.main()
