import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402


@pytest.fixture()
def app_with_db():
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, 'buy-race-condition-test.db')

    with patch('app.PriceService.warmup_cache', return_value=None):
        app = create_app()

    app.config.update(TESTING=True, DATABASE=db_path)
    with app.app_context():
        init_db(app)

    try:
        yield app
    finally:
        temp_dir.cleanup()


def _create_portfolio(client, initial_cash=1000.0):
    response = client.post(
        '/api/portfolio/create',
        json={
            'name': 'Race Condition Portfolio',
            'initial_cash': initial_cash,
            'account_type': 'STANDARD',
            'created_at': '2026-04-04',
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()['payload']['id']


@patch('portfolio_trade_service.PriceService.sync_stock_history', return_value=None)
@patch('portfolio_trade_service.PriceService.fetch_metadata', return_value={'currency': 'PLN'})
def test_buy_race_condition_allows_only_one_success_and_preserves_cash(
    _metadata_mock,
    _sync_mock,
    app_with_db,
):
    app = app_with_db
    portfolio_id = _create_portfolio(app.test_client(), initial_cash=1000.0)

    payload = {
        'portfolio_id': portfolio_id,
        'ticker': 'PKN',
        'quantity': 1,
        'price': 800,
        'date': '2026-04-04',
        'commission': 0,
    }

    barrier = Barrier(5)

    def worker():
        client = app.test_client()
        barrier.wait(timeout=5)
        response = client.post('/api/portfolio/buy', json=payload)
        body = response.get_json(silent=True) or {}
        return response.status_code, body

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _i: worker(), range(5)))

    successes = [body for status, body in results if status in (200, 201)]
    failures = [body for status, body in results if status in (400, 422)]

    assert len(successes) == 1, results
    assert len(failures) == 4, results

    for failure_body in failures:
        error_message = (failure_body.get('error') or {}).get('message', '')
        assert 'Insufficient' in error_message

    with app.app_context():
        db = get_db()
        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        assert float(portfolio['current_cash']) == pytest.approx(200.0)

        buys = db.execute(
            'SELECT COUNT(*) AS cnt FROM transactions WHERE portfolio_id = ? AND ticker = ? AND type = ?',
            (portfolio_id, 'PKN', 'BUY'),
        ).fetchone()
        assert int(buys['cnt']) == 1
