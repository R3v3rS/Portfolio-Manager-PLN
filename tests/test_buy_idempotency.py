import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from database import get_db, init_db  # noqa: E402


@pytest.fixture()
def client_with_db():
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, 'buy-idempotency-test.db')

    with patch('app.PriceService.warmup_cache', return_value=None):
        app = create_app()

    app.config.update(TESTING=True, DATABASE=db_path)
    with app.app_context():
        init_db(app)

    client = app.test_client()
    try:
        yield app, client
    finally:
        temp_dir.cleanup()


def _create_portfolio(client, initial_cash=10_000.0):
    response = client.post(
        '/api/portfolio/create',
        json={
            'name': 'Idempotency Portfolio',
            'initial_cash': initial_cash,
            'account_type': 'STANDARD',
            'created_at': '2026-01-01',
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()['payload']['id']


@patch('portfolio_trade_service.PriceService.sync_stock_history', return_value=None)
@patch('portfolio_trade_service.PriceService.fetch_metadata', return_value={'currency': 'PLN'})
def test_buy_idempotency_replay_returns_original_result_without_duplicate_side_effects(
    _metadata_mock,
    _sync_mock,
    client_with_db,
):
    app, client = client_with_db
    portfolio_id = _create_portfolio(client)

    payload = {
        'portfolio_id': portfolio_id,
        'ticker': 'AAPL',
        'quantity': 2,
        'price': 100,
        'date': '2026-01-15',
        'commission': 5,
    }
    headers = {'Idempotency-Key': 'buy-aapl-2026-01-15-001'}

    first_response = client.post('/api/portfolio/buy', json=payload, headers=headers)
    assert first_response.status_code == 201, first_response.get_json()

    second_response = client.post('/api/portfolio/buy', json=payload, headers=headers)
    assert second_response.status_code in (200, 201, 209), second_response.get_json()
    assert second_response.get_json() == first_response.get_json()

    with app.app_context():
        db = get_db()
        buy_rows = db.execute(
            'SELECT id, total_value FROM transactions WHERE portfolio_id = ? AND ticker = ? AND type = ?',
            (portfolio_id, 'AAPL', 'BUY'),
        ).fetchall()
        assert len(buy_rows) == 1
        assert float(buy_rows[0]['total_value']) == pytest.approx(205.0)

        holding = db.execute(
            'SELECT quantity, total_cost FROM holdings WHERE portfolio_id = ? AND ticker = ?',
            (portfolio_id, 'AAPL'),
        ).fetchone()
        assert holding is not None
        assert float(holding['quantity']) == pytest.approx(2.0)
        assert float(holding['total_cost']) == pytest.approx(205.0)

        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
        assert float(portfolio['current_cash']) == pytest.approx(10_000.0 - 205.0)


@patch('portfolio_trade_service.PriceService.sync_stock_history', return_value=None)
@patch('portfolio_trade_service.PriceService.fetch_metadata', return_value={'currency': 'PLN'})
def test_buy_idempotency_rejects_same_key_with_different_payload(
    _metadata_mock,
    _sync_mock,
    client_with_db,
):
    _app, client = client_with_db
    portfolio_id = _create_portfolio(client)

    headers = {'Idempotency-Key': 'buy-aapl-different-body'}

    first_response = client.post(
        '/api/portfolio/buy',
        json={
            'portfolio_id': portfolio_id,
            'ticker': 'AAPL',
            'quantity': 1,
            'price': 100,
            'date': '2026-01-16',
        },
        headers=headers,
    )
    assert first_response.status_code == 201, first_response.get_json()

    second_response = client.post(
        '/api/portfolio/buy',
        json={
            'portfolio_id': portfolio_id,
            'ticker': 'AAPL',
            'quantity': 2,
            'price': 100,
            'date': '2026-01-16',
        },
        headers=headers,
    )
    assert second_response.status_code == 409, second_response.get_json()
    error = second_response.get_json()['error']
    assert error['code'] == 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'
