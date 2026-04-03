from unittest.mock import patch

from tests.financial_test_utils import FinancialIntegrationTestBase
from portfolio_service import PortfolioService
from portfolio_valuation_service import PortfolioValuationService


class TestParentChildAggregation(FinancialIntegrationTestBase):
    @patch('portfolio_trade_service.PriceService.sync_stock_history', return_value=True)
    @patch('portfolio_trade_service.PriceService.fetch_metadata', return_value={'currency': 'PLN', 'company_name': 'Stub Co', 'sector': 'Tech', 'industry': 'Software'})
    @patch('portfolio_valuation_service.PriceService.get_prices', return_value={'AAPL': 110.0})
    @patch('portfolio_valuation_service.PriceService.get_price_updates', return_value={})
    @patch('portfolio_valuation_service.PriceService.fetch_metadata', return_value=None)
    @patch('portfolio_valuation_service.PriceService.get_quotes', return_value={})
    def test_parent_equals_sum_of_children(self, *_mocks):
        parent_id = self.create_parent('Aggregation Parent')
        child_a_id = self.create_child(parent_id, 'Growth')
        child_b_id = self.create_child(parent_id, 'Income')

        with self.app.app_context():
            PortfolioService.deposit_cash(parent_id, 2_000.0, date_str='2026-01-02', sub_portfolio_id=child_a_id)
            PortfolioService.deposit_cash(parent_id, 1_000.0, date_str='2026-01-02', sub_portfolio_id=child_b_id)
            PortfolioService.buy_stock(parent_id, 'AAPL', quantity=10.0, price=100.0, purchase_date='2026-01-03', sub_portfolio_id=child_a_id)
            PortfolioService.buy_stock(parent_id, 'AAPL', quantity=5.0, price=120.0, purchase_date='2026-01-04', sub_portfolio_id=child_b_id)

            parent_value = PortfolioValuationService.get_portfolio_value(parent_id)
            child_a_value = PortfolioValuationService.get_portfolio_value(child_a_id)
            child_b_value = PortfolioValuationService.get_portfolio_value(child_b_id)

            self.assertAlmostEqual(
                parent_value['portfolio_value'],
                child_a_value['portfolio_value'] + child_b_value['portfolio_value'],
                delta=self.FLOAT_TOLERANCE,
            )

            aggregated = PortfolioValuationService.get_holdings(parent_id, aggregate=True)
            self.assertEqual(len(aggregated), 1)
            aapl = aggregated[0]

            child_a_holding = self.get_holding(parent_id, 'AAPL', sub_portfolio_id=child_a_id)
            child_b_holding = self.get_holding(parent_id, 'AAPL', sub_portfolio_id=child_b_id)
            expected_qty = float(child_a_holding['quantity']) + float(child_b_holding['quantity'])
            expected_cost = float(child_a_holding['total_cost']) + float(child_b_holding['total_cost'])
            expected_avg = expected_cost / expected_qty

            self.assertAlmostEqual(float(aapl['quantity']), expected_qty, places=8)
            self.assertAlmostEqual(float(aapl['total_cost']), expected_cost, places=2)
            self.assertAlmostEqual(float(aapl['average_buy_price']), expected_avg, places=2)
