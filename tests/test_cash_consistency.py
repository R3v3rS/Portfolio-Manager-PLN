from unittest.mock import patch

from tests.financial_test_utils import FinancialIntegrationTestBase
from portfolio_service import PortfolioService


class TestCashConsistencyAfterOperations(FinancialIntegrationTestBase):
    @patch('portfolio_trade_service.PriceService.sync_stock_history', return_value=True)
    @patch('portfolio_trade_service.PriceService.fetch_metadata', return_value={'currency': 'PLN', 'company_name': 'Stub Co', 'sector': 'Tech', 'industry': 'Software'})
    def test_cash_consistency_after_operations(self, _meta_mock, _sync_mock):
        parent_id = self.create_parent('Cash Parent')

        with self.app.app_context():
            PortfolioService.deposit_cash(parent_id, 10_000.0, date_str='2026-01-02')
            PortfolioService.buy_stock(parent_id, 'AAPL', quantity=10.0, price=200.0, purchase_date='2026-01-03')
            PortfolioService.sell_stock(parent_id, 'AAPL', quantity=4.0, price=250.0, sell_date='2026-01-04')
            PortfolioService.withdraw_cash(parent_id, 500.0, date_str='2026-01-05')

        txs = self.get_transactions_sorted(parent_id)
        self.assertEqual([tx['type'] for tx in txs], ['DEPOSIT', 'BUY', 'SELL', 'WITHDRAW'])

        cash_deltas = []
        running_cash = 0.0
        for tx in txs:
            amount = float(tx['total_value'])
            if tx['type'] in ('DEPOSIT', 'SELL', 'DIVIDEND', 'INTEREST'):
                delta = amount
            elif tx['type'] in ('WITHDRAW', 'BUY'):
                delta = -amount
            else:
                delta = 0.0
            cash_deltas.append((tx['type'], delta))
            running_cash += delta

        expected_cash = 10_000.0 - (10.0 * 200.0) + (4.0 * 250.0) - 500.0
        stored_cash = self.get_cash(parent_id)

        self.assertAlmostEqual(expected_cash, 8_500.0, places=2)
        self.assertAlmostEqual(running_cash, expected_cash, places=2)
        self.assertAlmostEqual(stored_cash, expected_cash, places=2)
        self.assertLess(next(delta for tx_type, delta in cash_deltas if tx_type == 'BUY'), 0.0)
        self.assertGreater(next(delta for tx_type, delta in cash_deltas if tx_type == 'SELL'), 0.0)
