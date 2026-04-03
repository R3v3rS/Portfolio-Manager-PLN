import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402
from portfolio_service import PortfolioService  # noqa: E402


class FinancialIntegrationTestBase(unittest.TestCase):
    FLOAT_TOLERANCE = 0.01

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'financial-tier1-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    def create_parent(self, name='Parent', created_at='2026-01-01'):
        with self.app.app_context():
            return PortfolioService.create_portfolio(
                name=name,
                initial_cash=0.0,
                account_type='STANDARD',
                created_at=created_at,
            )

    def create_child(self, parent_id, name='Child', created_at='2026-01-01'):
        with self.app.app_context():
            return PortfolioService.create_portfolio(
                name=name,
                initial_cash=0.0,
                account_type='STANDARD',
                created_at=created_at,
                parent_portfolio_id=parent_id,
            )

    def get_transactions_sorted(self, portfolio_id):
        with self.app.app_context():
            db = get_db()
            rows = db.execute(
                'SELECT * FROM transactions WHERE portfolio_id = ? ORDER BY date(date) ASC, id ASC',
                (portfolio_id,),
            ).fetchall()
            return [{key: row[key] for key in row.keys()} for row in rows]

    def get_holding(self, portfolio_id, ticker, sub_portfolio_id=None):
        with self.app.app_context():
            db = get_db()
            if sub_portfolio_id is None:
                row = db.execute(
                    'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id IS NULL',
                    (portfolio_id, ticker),
                ).fetchone()
            else:
                row = db.execute(
                    'SELECT * FROM holdings WHERE portfolio_id = ? AND ticker = ? AND sub_portfolio_id = ?',
                    (portfolio_id, ticker, sub_portfolio_id),
                ).fetchone()
            return ({key: row[key] for key in row.keys()} if row else None)

    def get_cash(self, portfolio_id):
        with self.app.app_context():
            db = get_db()
            row = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
            return float(row['current_cash'])
