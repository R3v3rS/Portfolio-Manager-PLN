import os
import sys
import tempfile
import unittest
import io
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402
from import_staging_service import ImportBookingError  # noqa: E402


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

    def test_book_route_returns_422_with_row_errors_on_booking_error(self):
        with patch(
            'routes_imports.ImportStagingService.book_session',
            side_effect=ImportBookingError('Booking failed', ['row_id=1: db locked']),
        ):
            response = self.client.post('/api/portfolio/import/staging/sess-booking-error/book', json={})

        self.assertEqual(response.status_code, 422, response.get_json())
        error_payload = response.get_json()['error']
        self.assertEqual(error_payload['code'], 'BOOKING_ERROR')
        self.assertEqual(error_payload['message'], 'Booking failed')
        self.assertEqual(error_payload['details']['row_errors'], ['row_id=1: db locked'])

    def test_book_route_returns_404_for_missing_session(self):
        response = self.client.post('/api/portfolio/import/staging/sess-missing/book', json={})

        self.assertEqual(response.status_code, 404, response.get_json())
        error_payload = response.get_json()['error']
        self.assertEqual(error_payload['code'], 'not_found')
        self.assertEqual(error_payload['message'], 'Session not found')

    def test_book_route_returns_200_for_successful_booking(self):
        session_id = 'sess-book-success'
        with self.app.app_context():
            db = get_db()
            db.execute(
                '''INSERT INTO import_staging (
                       import_session_id, portfolio_id, ticker, type, quantity, price, total_value, date,
                       target_sub_portfolio_id, status, conflict_type, conflict_details, row_hash, source_file, created_at
                   ) VALUES (?, ?, 'CASH', 'DEPOSIT', 1, 100, 100, '2026-01-01',
                             NULL, 'pending', NULL, NULL, ?, 'test.csv', '2026-01-01T10:00:00')''',
                (session_id, self.parent_id, f'{session_id}-deposit'),
            )
            db.commit()

        response = self.client.post(f'/api/portfolio/import/staging/{session_id}/book', json={})

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()['payload']
        self.assertEqual(payload['booked'], 1)
        self.assertEqual(payload['booked_tx_only'], 0)
        self.assertEqual(payload['errors'], [])


class RoutesImportsValidationErrorsTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'routes-imports-validation-test.db')

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
            self.archived_child_id = db.execute(
                "INSERT INTO portfolios (name, parent_portfolio_id, current_cash, is_archived) VALUES ('Archived Child', ?, 0.0, 1)",
                (self.parent_id,),
            ).lastrowid
            db.commit()

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    def _post_staging_import(self, *, csv_text: str, mode: str = 'staging', sub_portfolio_id: int | None = None):
        payload = {
            'portfolio_id': str(self.parent_id),
            'mode': mode,
            'file': (io.BytesIO(csv_text.encode('utf-8')), 'xtb.csv'),
        }
        if sub_portfolio_id is not None:
            payload['sub_portfolio_id'] = str(sub_portfolio_id)
        return self.client.post(
            '/api/portfolio/import/staging',
            data=payload,
            content_type='multipart/form-data',
        )

    def test_staging_import_returns_400_for_missing_required_csv_columns(self):
        response = self._post_staging_import(
            csv_text='Symbol,Price\nAAPL,100\n',
            mode='staging',
        )

        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'IMPORT_VALIDATION_ERROR')
        self.assertIn('Missing required columns', error['message'])

    def test_direct_import_returns_400_for_invalid_sub_portfolio_id(self):
        response = self._post_staging_import(
            csv_text='Time,Type,Amount\n2026-01-01,Deposit,100\n',
            mode='direct',
            sub_portfolio_id=self.invalid_child_id,
        )

        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'IMPORT_VALIDATION_ERROR')
        self.assertEqual(error['message'], 'Invalid sub-portfolio for this parent')

    def test_direct_import_returns_400_for_archived_sub_portfolio(self):
        response = self._post_staging_import(
            csv_text='Time,Type,Amount\n2026-01-01,Deposit,100\n',
            mode='direct',
            sub_portfolio_id=self.archived_child_id,
        )

        self.assertEqual(response.status_code, 400, response.get_json())
        error = response.get_json()['error']
        self.assertEqual(error['code'], 'IMPORT_VALIDATION_ERROR')
        self.assertEqual(error['message'], 'Cannot import to an archived sub-portfolio')


class RoutesImportsTargetSubPortfolioValidationTestCase(unittest.TestCase):
    def setUp(self):
        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def _assert_invalid_payload_returns_422(self, payload):
        with patch('routes_imports.ImportStagingService.assign_row') as assign_row_mock, patch(
            'routes_imports.ImportStagingService.assign_all'
        ) as assign_all_mock:
            row_response = self.client.put('/api/portfolio/import/staging/sess-1/rows/1/assign', json=payload)
            all_response = self.client.put('/api/portfolio/import/staging/sess-1/assign-all', json=payload)

        self.assertEqual(row_response.status_code, 422, row_response.get_json())
        self.assertEqual(all_response.status_code, 422, all_response.get_json())
        self.assertEqual(row_response.get_json()['error']['code'], 'invalid_sub_portfolio')
        self.assertEqual(all_response.get_json()['error']['code'], 'invalid_sub_portfolio')
        assign_row_mock.assert_not_called()
        assign_all_mock.assert_not_called()

    def test_target_sub_portfolio_id_rejects_non_numeric_string(self):
        self._assert_invalid_payload_returns_422({'target_sub_portfolio_id': 'abc'})

    def test_target_sub_portfolio_id_rejects_float(self):
        self._assert_invalid_payload_returns_422({'target_sub_portfolio_id': 1.5})

    def test_target_sub_portfolio_id_rejects_non_positive_integer(self):
        self._assert_invalid_payload_returns_422({'target_sub_portfolio_id': -1})

    def test_target_sub_portfolio_id_accepts_positive_integer(self):
        with patch('routes_imports.ImportStagingService.assign_row', return_value={'ok': True}) as assign_row_mock, patch(
            'routes_imports.ImportStagingService.assign_all', return_value={'ok': True}
        ) as assign_all_mock:
            row_response = self.client.put(
                '/api/portfolio/import/staging/sess-1/rows/1/assign',
                json={'target_sub_portfolio_id': 5},
            )
            all_response = self.client.put(
                '/api/portfolio/import/staging/sess-1/assign-all',
                json={'target_sub_portfolio_id': 5},
            )

        self.assertEqual(row_response.status_code, 200, row_response.get_json())
        self.assertEqual(all_response.status_code, 200, all_response.get_json())
        assign_row_mock.assert_called_once_with(session_id='sess-1', row_id=1, target_sub_portfolio_id=5)
        assign_all_mock.assert_called_once_with(session_id='sess-1', target_sub_portfolio_id=5)

    def test_target_sub_portfolio_id_null_passes_none_to_service(self):
        with patch('routes_imports.ImportStagingService.assign_row', return_value={'ok': True}) as assign_row_mock, patch(
            'routes_imports.ImportStagingService.assign_all', return_value={'ok': True}
        ) as assign_all_mock:
            row_response = self.client.put('/api/portfolio/import/staging/sess-1/rows/1/assign', json={'target_sub_portfolio_id': None})
            all_response = self.client.put('/api/portfolio/import/staging/sess-1/assign-all', json={'target_sub_portfolio_id': None})

        self.assertEqual(row_response.status_code, 200, row_response.get_json())
        self.assertEqual(all_response.status_code, 200, all_response.get_json())
        assign_row_mock.assert_called_once_with(session_id='sess-1', row_id=1, target_sub_portfolio_id=None)
        assign_all_mock.assert_called_once_with(session_id='sess-1', target_sub_portfolio_id=None)


if __name__ == '__main__':
    unittest.main()
