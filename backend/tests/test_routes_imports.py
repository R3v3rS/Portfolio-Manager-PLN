import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402


class RoutesImportsAssignAllTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'routes-imports-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)
            db = get_db()
            self.parent_id = db.execute(
                "INSERT INTO portfolios (name, current_cash) VALUES ('Parent', 0.0)"
            ).lastrowid
            self.valid_child_id = db.execute(
                "INSERT INTO portfolios (name, parent_portfolio_id, current_cash) VALUES ('Child', ?, 0.0)",
                (self.parent_id,),
            ).lastrowid
            other_parent_id = db.execute(
                "INSERT INTO portfolios (name, current_cash) VALUES ('Other Parent', 0.0)"
            ).lastrowid
            self.invalid_child_id = db.execute(
                "INSERT INTO portfolios (name, parent_portfolio_id, current_cash) VALUES ('Foreign Child', ?, 0.0)",
                (other_parent_id,),
            ).lastrowid
            db.commit()

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    def _insert_staging_row(self, session_id: str, *, status: str = 'pending') -> None:
        with self.app.app_context():
            db = get_db()
            db.execute(
                '''INSERT INTO import_staging (
                       import_session_id, portfolio_id, ticker, type, quantity, price, total_value, date,
                       target_sub_portfolio_id, status, conflict_type, conflict_details, row_hash, source_file, created_at
                   ) VALUES (?, ?, 'AAPL', 'BUY', 1, 100, 100, '2026-01-01',
                             NULL, ?, NULL, NULL, ?, 'test.csv', '2026-01-01T10:00:00')''',
                (session_id, self.parent_id, status, f'{session_id}-{status}'),
            )
            db.commit()

    def test_assign_all_route_propagates_invalid_subportfolio_as_422(self):
        self._insert_staging_row('sess-invalid-sub')

        response = self.client.put(
            '/api/portfolio/import/staging/sess-invalid-sub/assign-all',
            json={'target_sub_portfolio_id': self.invalid_child_id},
        )

        self.assertEqual(response.status_code, 422, response.get_json())
        payload = response.get_json()['error']
        self.assertEqual(payload['code'], 'invalid_sub_portfolio')

    def test_assign_all_route_skips_booked_rows_and_assigns_remaining(self):
        session_id = 'sess-booked'
        self._insert_staging_row(session_id, status='booked')
        self._insert_staging_row(session_id, status='pending')

        response = self.client.put(
            f'/api/portfolio/import/staging/{session_id}/assign-all',
            json={'target_sub_portfolio_id': self.valid_child_id},
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()['payload']
        self.assertEqual(result['assigned'], 1)
        self.assertEqual(result['skipped'], 1)


if __name__ == '__main__':
    unittest.main()
