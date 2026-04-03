from unittest.mock import patch

from tests.financial_test_utils import FinancialIntegrationTestBase
from portfolio_service import PortfolioService
from portfolio_audit_service import PortfolioAuditService
from database import get_db


class TestRebuildConsistency(FinancialIntegrationTestBase):
    @patch('portfolio_trade_service.PriceService.sync_stock_history', return_value=True)
    @patch('portfolio_trade_service.PriceService.fetch_metadata', return_value={'currency': 'PLN', 'company_name': 'Stub Co', 'sector': 'Tech', 'industry': 'Software'})
    def test_rebuild_matches_holdings_state(self, _meta_mock, _sync_mock):
        parent_id = self.create_parent('Rebuild Parent')

        with self.app.app_context():
            PortfolioService.deposit_cash(parent_id, 10_000.0, date_str='2026-01-02')
            PortfolioService.buy_stock(parent_id, 'AAPL', quantity=10.0, price=100.0, purchase_date='2026-01-03')
            PortfolioService.buy_stock(parent_id, 'AAPL', quantity=5.0, price=120.0, purchase_date='2026-01-04')
            PortfolioService.buy_stock(parent_id, 'MSFT', quantity=2.0, price=200.0, purchase_date='2026-01-05')
            PortfolioService.sell_stock(parent_id, 'AAPL', quantity=8.0, price=130.0, sell_date='2026-01-06')

            db = get_db()
            before_rows = db.execute(
                'SELECT ticker, quantity, total_cost, average_buy_price FROM holdings WHERE portfolio_id = ? ORDER BY ticker ASC',
                (parent_id,),
            ).fetchall()
            before = {r['ticker']: dict(quantity=float(r['quantity']), total_cost=float(r['total_cost']), avg=float(r['average_buy_price'])) for r in before_rows}

            rebuilt = PortfolioAuditService.rebuild_holdings_from_transactions(parent_id)
            rebuilt_holdings = rebuilt['holdings']

            self.assertEqual(set(before.keys()), set(rebuilt_holdings.keys()))
            for ticker in before:
                self.assertAlmostEqual(before[ticker]['quantity'], rebuilt_holdings[ticker]['quantity'], places=8)
                self.assertAlmostEqual(before[ticker]['total_cost'], rebuilt_holdings[ticker]['total_cost'], places=2)
                self.assertAlmostEqual(before[ticker]['avg'], rebuilt_holdings[ticker]['avg_price'], places=2)
