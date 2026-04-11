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


class TransactionsSubportfolioTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'transactions-subportfolio-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    def _create_parent(self, name='Parent'):
        response = self.client.post('/api/portfolio/create', json={
            'name': name,
            'initial_cash': 0.0,
            'account_type': 'STANDARD',
            'created_at': '2026-01-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _create_child(self, parent_id, name='Child'):
        response = self.client.post(f'/api/portfolio/{parent_id}/children', json={
            'name': name,
            'initial_cash': 0.0,
            'created_at': '2026-01-01',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()['payload']['id']

    def _insert_transaction(
        self,
        portfolio_id,
        ticker,
        tx_type,
        date,
        total_value,
        quantity=0.0,
        price=0.0,
        realized_profit=0.0,
        sub_portfolio_id=None,
    ):
        with self.app.app_context():
            db = get_db()
            db.execute(
                '''
                INSERT INTO transactions (
                    portfolio_id, ticker, date, type, quantity, price,
                    total_value, realized_profit, commission, sub_portfolio_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                ''',
                (
                    portfolio_id,
                    ticker,
                    date,
                    tx_type,
                    quantity,
                    price,
                    total_value,
                    realized_profit,
                    sub_portfolio_id,
                ),
            )
            db.commit()

    def _insert_holding(self, portfolio_id, ticker, quantity, total_cost, sub_portfolio_id=None):
        with self.app.app_context():
            db = get_db()
            db.execute(
                '''
                INSERT INTO holdings (
                    portfolio_id, ticker, quantity, average_buy_price, total_cost,
                    company_name, currency, instrument_currency, avg_buy_price_native,
                    avg_buy_fx_rate, sub_portfolio_id
                )
                VALUES (?, ?, ?, ?, ?, ?, 'PLN', 'PLN', ?, 1, ?)
                ''',
                (
                    portfolio_id,
                    ticker,
                    quantity,
                    total_cost / quantity,
                    total_cost,
                    f'{ticker} Corp',
                    total_cost / quantity,
                    sub_portfolio_id,
                ),
            )
            db.commit()

    def test_transactions_endpoint_parent_and_child_scope(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id, name='Growth')

        self._insert_transaction(parent_id, 'CASH', 'DEPOSIT', '2026-01-01', 1000.0, sub_portfolio_id=None)
        self._insert_transaction(parent_id, 'AAPL', 'BUY', '2026-01-10', 300.0, quantity=3, price=100, sub_portfolio_id=None)
        self._insert_transaction(parent_id, 'MSFT', 'BUY', '2026-01-12', 400.0, quantity=2, price=200, sub_portfolio_id=child_id)

        parent_response = self.client.get(f'/api/portfolio/transactions/{parent_id}')
        self.assertEqual(parent_response.status_code, 200, parent_response.get_json())
        parent_txs = parent_response.get_json()['payload']['transactions']
        self.assertEqual([tx['ticker'] for tx in parent_txs], ['MSFT', 'AAPL', 'CASH'])
        self.assertEqual(parent_txs[0]['sub_portfolio_id'], child_id)
        self.assertTrue(all(tx['portfolio_id'] == parent_id for tx in parent_txs))

        child_response = self.client.get(f'/api/portfolio/transactions/{child_id}')
        self.assertEqual(child_response.status_code, 200, child_response.get_json())
        child_txs = child_response.get_json()['payload']['transactions']
        self.assertEqual(len(child_txs), 1)
        self.assertEqual(child_txs[0]['ticker'], 'MSFT')
        self.assertEqual(child_txs[0]['portfolio_id'], parent_id)
        self.assertEqual(child_txs[0]['sub_portfolio_id'], child_id)

    @patch('portfolio_valuation_service.PriceService.get_prices', return_value={'AAPL': 110.0, 'MSFT': 220.0})
    @patch('portfolio_valuation_service.PriceService.get_price_updates', return_value={})
    @patch('portfolio_valuation_service.PriceService.fetch_metadata', return_value=None)
    def test_holdings_endpoint_parent_and_child_scope(self, *_mocks):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id, name='Income')

        self._insert_holding(parent_id, 'AAPL', quantity=2, total_cost=200.0, sub_portfolio_id=None)
        self._insert_holding(parent_id, 'MSFT', quantity=1, total_cost=150.0, sub_portfolio_id=child_id)

        parent_response = self.client.get(f'/api/portfolio/holdings/{parent_id}')
        self.assertEqual(parent_response.status_code, 200, parent_response.get_json())
        parent_holdings = parent_response.get_json()['payload']['holdings']
        # Parent now sees both its own holdings and child's holdings
        self.assertEqual(len(parent_holdings), 2)
        tickers = sorted([h['ticker'] for h in parent_holdings])
        self.assertEqual(tickers, ['AAPL', 'MSFT'])

        child_response = self.client.get(f'/api/portfolio/holdings/{child_id}')
        self.assertEqual(child_response.status_code, 200, child_response.get_json())
        child_holdings = child_response.get_json()['payload']['holdings']
        self.assertEqual(len(child_holdings), 1)
        self.assertEqual(child_holdings[0]['ticker'], 'MSFT')
        self.assertEqual(child_holdings[0]['sub_portfolio_id'], child_id)

    @patch('portfolio_history_service.InflationService.get_inflation_series', return_value=[])
    @patch('portfolio_history_service.PriceService.get_tickers_requiring_history_sync', return_value=[])
    def test_history_monthly_endpoint_parent_and_child_scope(self, *_mocks):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)

        self._insert_transaction(parent_id, 'CASH', 'DEPOSIT', '2026-01-05', 100.0, sub_portfolio_id=None)
        self._insert_transaction(parent_id, 'CASH', 'DEPOSIT', '2026-01-06', 300.0, sub_portfolio_id=child_id)

        parent_response = self.client.get(f'/api/portfolio/history/monthly/{parent_id}')
        self.assertEqual(parent_response.status_code, 200, parent_response.get_json())
        parent_history = parent_response.get_json()['payload']['history']
        self.assertGreaterEqual(len(parent_history), 1)
        parent_jan = next((entry for entry in parent_history if entry['date'] == '2026-01'), None)
        self.assertIsNotNone(parent_jan)
        # Parent now aggregates all deposits (100 + 300 = 400)
        self.assertEqual(parent_jan['value'], 400.0)

        child_response = self.client.get(f'/api/portfolio/history/monthly/{child_id}')
        self.assertEqual(child_response.status_code, 200, child_response.get_json())
        child_history = child_response.get_json()['payload']['history']
        self.assertGreaterEqual(len(child_history), 1)
        child_jan = next((entry for entry in child_history if entry['date'] == '2026-01'), None)
        self.assertIsNotNone(child_jan)
        self.assertEqual(child_jan['value'], 300.0)

    def test_closed_positions_endpoint_parent_and_child_scope(self):
        parent_id = self._create_parent()
        child_id = self._create_child(parent_id)

        self._insert_transaction(parent_id, 'AAPL', 'BUY', '2026-01-10', 1000.0, quantity=10, price=100, sub_portfolio_id=None)
        self._insert_transaction(parent_id, 'AAPL', 'SELL', '2026-02-10', 1200.0, quantity=10, price=120, realized_profit=200.0, sub_portfolio_id=None)

        self._insert_transaction(parent_id, 'MSFT', 'BUY', '2026-01-15', 2000.0, quantity=20, price=100, sub_portfolio_id=child_id)
        self._insert_transaction(parent_id, 'MSFT', 'SELL', '2026-02-15', 2500.0, quantity=20, price=125, realized_profit=500.0, sub_portfolio_id=child_id)

        parent_response = self.client.get(f'/api/portfolio/{parent_id}/closed-positions')
        self.assertEqual(parent_response.status_code, 200, parent_response.get_json())
        parent_payload = parent_response.get_json()['payload']
        # Parent now aggregates closed positions from child too
        self.assertEqual(len(parent_payload['positions']), 2)
        tickers = sorted([p['ticker'] for p in parent_payload['positions']])
        self.assertEqual(tickers, ['AAPL', 'MSFT'])
        self.assertEqual(parent_payload['total_historical_profit'], 700.0)

        child_response = self.client.get(f'/api/portfolio/{child_id}/closed-positions')
        self.assertEqual(child_response.status_code, 200, child_response.get_json())
        child_payload = child_response.get_json()['payload']
        self.assertEqual(len(child_payload['positions']), 1)
        self.assertEqual(child_payload['positions'][0]['ticker'], 'MSFT')
        self.assertEqual(child_payload['total_historical_profit'], 500.0)


if __name__ == '__main__':
    unittest.main()
