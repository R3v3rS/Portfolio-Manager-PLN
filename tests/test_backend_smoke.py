import database


def test_dashboard_global_summary_smoke(client, seed_reference_data):
    response = client.get('/api/dashboard/global-summary')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['total_assets'] > 0
    assert payload['total_liabilities'] > 0


def test_portfolio_list_smoke(client, seed_reference_data):
    response = client.get('/api/portfolio/list')

    assert response.status_code == 200
    assert any(p['id'] == seed_reference_data.simple_portfolio_id for p in response.get_json()['portfolios'])


def test_portfolio_create_buy_and_value_smoke(client):
    response = client.post('/api/portfolio/create', json={'name': 'Smoke', 'initial_cash': 300.0, 'created_at': '2026-03-01'})
    assert response.status_code == 201

    created_id = response.get_json()['id']
    buy_response = client.post('/api/portfolio/buy', json={
        'portfolio_id': created_id,
        'ticker': 'AAA',
        'quantity': 1,
        'price': 100.0,
        'date': '2026-03-02',
        'commission': 0.0,
    })
    value_response = client.get(f'/api/portfolio/value/{created_id}')

    assert buy_response.status_code == 200
    assert value_response.status_code == 200
    assert value_response.get_json()['portfolio_value'] >= 100.0


def test_budget_transfer_endpoints_smoke(client, app, seed_reference_data):
    portfolio_response = client.post('/api/portfolio/create', json={'name': 'Transfer Smoke', 'initial_cash': 100.0, 'created_at': '2026-03-01'})
    portfolio_id = portfolio_response.get_json()['id']

    transfer_response = client.post('/api/budget/transfer-to-portfolio', json={
        'budget_account_id': seed_reference_data.account_id,
        'portfolio_id': portfolio_id,
        'amount': 150.0,
        'envelope_id': seed_reference_data.envelope_id,
        'date': '2026-03-03',
    })
    withdraw_response = client.post('/api/budget/withdraw-from-portfolio', json={
        'budget_account_id': seed_reference_data.account_id,
        'portfolio_id': portfolio_id,
        'amount': 50.0,
        'date': '2026-03-04',
    })

    assert transfer_response.status_code == 200
    assert withdraw_response.status_code == 200

    with app.app_context():
        db = database.get_db()
        budget_transactions = db.execute('SELECT COUNT(*) AS c FROM budget_transactions').fetchone()['c']
        portfolio_transactions = db.execute('SELECT COUNT(*) AS c FROM transactions WHERE portfolio_id = ?', (portfolio_id,)).fetchone()['c']

    assert budget_transactions >= 2
    assert portfolio_transactions >= 3


def test_loans_schedule_smoke(client, seed_reference_data):
    response = client.get(f'/api/loans/{seed_reference_data.loan_id}/schedule')

    assert response.status_code == 200
    assert 'simulation' in response.get_json()


def test_radar_endpoints_smoke(client, seed_reference_data):
    radar_response = client.get('/api/radar/')
    refresh_response = client.post('/api/radar/refresh', json={})

    assert radar_response.status_code == 200
    assert {item['ticker'] for item in radar_response.get_json()} == {'AAA', 'EUR_ETF'}
    assert refresh_response.status_code == 200
    assert set(refresh_response.get_json()['tickers']) == {'AAA', 'EUR_ETF'}


def test_symbol_map_smoke(client, seed_reference_data):
    response = client.get('/api/symbol-map')

    assert response.status_code == 200
    assert response.get_json()[0]['symbol_input'] == 'AAA US'
