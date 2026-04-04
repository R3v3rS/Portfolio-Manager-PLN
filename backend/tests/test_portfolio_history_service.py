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
from portfolio_history_service import PortfolioHistoryService  # noqa: E402
from portfolio_valuation_service import PortfolioValuationService  # noqa: E402


class PortfolioHistoryCashConsistencyTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'history-cash-test.db')

        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=self.db_path)

        with self.app.app_context():
            init_db(self.app)
            db = get_db()
            cursor = db.execute(
                'INSERT INTO portfolios (name, account_type, current_cash) VALUES (?, ?, ?)',
                ('Cash Consistency', 'STANDARD', 0.0),
            )
            self.portfolio_id = cursor.lastrowid

            transactions = [
                ('2026-01-01', 'DEPOSIT', 1000.0),
                ('2026-01-02', 'BUY', 500.0),
                ('2026-01-03', 'SELL', 200.0),
                ('2026-01-04', 'DIVIDEND', 50.0),
                ('2026-01-05', 'WITHDRAW', 100.0),
            ]
            for tx_date, tx_type, total_value in transactions:
                db.execute(
                    '''
                    INSERT INTO transactions (portfolio_id, ticker, date, type, quantity, price, total_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (self.portfolio_id, 'CASH', tx_date, tx_type, 0.0, 0.0, total_value),
                )
            db.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_apply_tx_to_rolling_matches_cash_balance_on_date(self):
        state = {
            'cash': 0.0,
            'invested_capital': 0.0,
            'benchmark_shares': 0.0,
            'inflation_shares': 0.0,
            'holdings_qty': {},
        }

        tx_sequence = [
            {'date': '2026-01-01', 'type': 'DEPOSIT', 'total_value': 1000.0, 'quantity': 0.0, 'ticker': 'CASH'},
            {'date': '2026-01-02', 'type': 'BUY', 'total_value': 500.0, 'quantity': 0.0, 'ticker': 'CASH'},
            {'date': '2026-01-03', 'type': 'SELL', 'total_value': 200.0, 'quantity': 0.0, 'ticker': 'CASH'},
            {'date': '2026-01-04', 'type': 'DIVIDEND', 'total_value': 50.0, 'quantity': 0.0, 'ticker': 'CASH'},
            {'date': '2026-01-05', 'type': 'WITHDRAW', 'total_value': 100.0, 'quantity': 0.0, 'ticker': 'CASH'},
        ]

        for tx in tx_sequence:
            PortfolioHistoryService._apply_tx_to_rolling(
                tx,
                state,
                price_getter=lambda _ticker, _date: 0.0,
                benchmark_ticker=None,
            )

        with self.app.app_context():
            cash_on_date = PortfolioValuationService.get_cash_balance_on_date(self.portfolio_id, '2026-01-05')

        self.assertEqual(state['cash'], 650.0)
        self.assertEqual(cash_on_date, 650.0)
        self.assertEqual(state['cash'], cash_on_date)


if __name__ == '__main__':
    unittest.main()
