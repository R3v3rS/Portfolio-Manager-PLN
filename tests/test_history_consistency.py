from datetime import date
from unittest.mock import patch

from tests.financial_test_utils import FinancialIntegrationTestBase
from portfolio_service import PortfolioService


class TestHistoryConsistency(FinancialIntegrationTestBase):
    @patch('portfolio_history_service.date')
    @patch('portfolio_history_service.PortfolioValuationService.get_portfolio_value')
    @patch('portfolio_history_service.PortfolioHistoryService._build_price_context')
    @patch('portfolio_trade_service.PriceService.sync_stock_history', return_value=True)
    @patch('portfolio_trade_service.PriceService.fetch_metadata', return_value={'currency': 'PLN', 'company_name': 'Stub Co', 'sector': 'Tech', 'industry': 'Software'})
    def test_history_matches_current_portfolio_value(
        self,
        _meta_mock,
        _sync_mock,
        mock_build_price_context,
        mock_live_value,
        mock_date,
    ):
        parent_id = self.create_parent('History Parent')

        with self.app.app_context():
            PortfolioService.deposit_cash(parent_id, 10_000.0, date_str='2026-04-01')
            PortfolioService.buy_stock(parent_id, 'AAPL', quantity=10.0, price=100.0, purchase_date='2026-04-02')
            PortfolioService.sell_stock(parent_id, 'AAPL', quantity=2.0, price=110.0, sell_date='2026-04-03')
            PortfolioService.withdraw_cash(parent_id, 500.0, date_str='2026-04-03')

        fixed_today = date(2026, 4, 3)
        mock_date.today.return_value = fixed_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # Only historical prices up to 2026-04-03 are available (no future leakage).
        mock_build_price_context.return_value = (
            {'AAPL': 'PLN'},
            {'AAPL': {'2026-04-02': 100.0, '2026-04-03': 110.0}},
        )

        current_value = 10_000.0 - 1_000.0 + 220.0 - 500.0 + (8.0 * 110.0)
        mock_live_value.return_value = {
            'portfolio_value': current_value,
            'net_contributions': 9_500.0,
        }

        with self.app.app_context():
            history = PortfolioService.get_portfolio_profit_history_daily(parent_id, days=3, metric='value')

        self.assertEqual(len(history), 3)
        self.assertEqual(history[-1]['date'], '2026-04-03')
        self.assertAlmostEqual(history[-1]['value'], current_value, delta=self.FLOAT_TOLERANCE)

        # Invested capital should respect DEPOSIT/WITHDRAW only (10_000 - 500 = 9_500).
        self.assertEqual(mock_live_value.return_value['net_contributions'], 9_500.0)

        # Verify no call attempted with a future start date and prices stop at fixed_today.
        args, _kwargs = mock_build_price_context.call_args
        self.assertEqual(str(args[2]), '2026-04-01')
        self.assertNotIn('2026-04-04', mock_build_price_context.return_value[1]['AAPL'])
