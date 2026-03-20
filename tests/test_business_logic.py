import database
from budget_service import BudgetService
from loan_service import LoanService
from portfolio_service import PortfolioService


def test_portfolio_history_and_profit_are_reconstructed_from_transactions(app, seed_reference_data):
    with app.app_context():
        history = PortfolioService.get_portfolio_history(seed_reference_data.simple_portfolio_id)
        profit_history = PortfolioService.get_portfolio_profit_history(seed_reference_data.simple_portfolio_id)

    assert history
    assert history[0]['date'] == '2026-01'
    assert history[-1]['value'] >= history[0]['value']
    assert profit_history[-1]['value'] > 0


def test_xtb_csv_import_uses_symbol_mapping_and_updates_holdings(app, seed_reference_data):
    with app.app_context():
        portfolio_id = PortfolioService.create_portfolio('Imported', 0.0, 'STANDARD', '2026-01-01 00:00:00')
        result = PortfolioService.import_xtb_csv(portfolio_id, seed_reference_data.xtb_frame)
        db = database.get_db()
        holding = db.execute('SELECT ticker, quantity, total_cost FROM holdings WHERE portfolio_id = ?', (portfolio_id,)).fetchone()
        value = PortfolioService.get_portfolio_value(portfolio_id)

    assert result == {'success': True, 'missing_symbols': []}
    assert holding['ticker'] == 'AAA'
    assert float(holding['quantity']) == 5.0
    assert round(float(holding['total_cost']), 2) == 500.0
    assert value['cash_value'] == 502.5


def test_budget_investment_transfers_are_atomic_and_adjust_balances(app, seed_reference_data):
    with app.app_context():
        BudgetService.transfer_to_investment(seed_reference_data.account_id, seed_reference_data.simple_portfolio_id, 200.0, envelope_id=seed_reference_data.envelope_id, date='2026-03-05')
        BudgetService.withdraw_from_investment(seed_reference_data.simple_portfolio_id, seed_reference_data.account_id, 50.0, date='2026-03-06')
        db = database.get_db()
        account = db.execute('SELECT balance FROM budget_accounts WHERE id = ?', (seed_reference_data.account_id,)).fetchone()
        envelope = db.execute('SELECT balance FROM envelopes WHERE id = ?', (seed_reference_data.envelope_id,)).fetchone()
        portfolio = db.execute('SELECT current_cash FROM portfolios WHERE id = ?', (seed_reference_data.simple_portfolio_id,)).fetchone()

    assert float(account['balance']) == 4850.0
    assert float(envelope['balance']) == 800.0
    assert float(portfolio['current_cash']) == 1640.0


def test_loan_schedule_and_dashboard_summary_include_overpayments_and_liabilities(app, seed_reference_data):
    with app.app_context():
        schedule = LoanService.generate_amortization_schedule(seed_reference_data.loan_id)
        client = app.test_client()
        dashboard = client.get('/api/dashboard/global-summary').get_json()

    assert schedule['actual_metrics']['interest_saved'] > 0
    assert any(item.get('is_mid_month') for item in schedule['simulation']['schedule'])
    assert dashboard['total_liabilities'] > 0
    assert dashboard['assets_breakdown']['budget_cash'] >= 0
