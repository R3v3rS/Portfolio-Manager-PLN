import unittest
from unittest.mock import patch
from contextlib import ExitStack
from test_asset_transfer import AssetTransferTest
from asset_transfer_service import transfer
from strategy_archive_service import archive,snapshot
from portfolio_valuation_service import PortfolioValuationService as Value
from portfolio_audit_service import PortfolioAuditService as Audit
from api.exceptions import ValidationError


class StrategyArchiveTest(unittest.TestCase):
    setUp=AssetTransferTest.setUp
    tearDown=AssetTransferTest.tearDown
    holding=AssetTransferTest.holding
    prepare=AssetTransferTest.prepare
    quotes=AssetTransferTest.quotes
    stamps=AssetTransferTest.stamps

    def reports(self):
        stack=ExitStack()
        stack.enter_context(patch('portfolio_history_service.PortfolioHistoryService._calculate_historical_metrics',return_value={}))
        stack.enter_context(patch('portfolio_history_service.PortfolioHistoryService.get_portfolio_profit_history_daily',return_value=[]))
        stack.enter_context(patch('actual_results_service.analyze',return_value={'frozen':True}))
        return stack

    def seed(self):
        transfer(self.prepare())
        self.db.execute('UPDATE portfolios SET current_cash=20 WHERE id=?',(self.child,))
        self.db.execute('UPDATE portfolios SET current_cash=30 WHERE id=?',(self.pid,))
        for sub,kind in ((self.child,'DEPOSIT'),(None,'WITHDRAW')):
            self.db.execute("INSERT INTO transactions(portfolio_id,sub_portfolio_id,ticker,type,quantity,price,total_value,date,transfer_id) VALUES(?,?,'CASH',?,1,20,20,date('now'),'test-cash')",(self.pid,sub,kind))
        self.db.commit()

    def test_archive_returns_assets_and_cash_once_and_freezes_result(self):
        self.seed()
        with self.quotes({'ABC':140}),self.stamps(),patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}),self.reports():
            before=Value.get_portfolio_value(self.pid,cached_prices_only=True)
            archive(self.child)
            after=Value.get_portfolio_value(self.pid,cached_prices_only=True)
        self.assertEqual(before['portfolio_value'],after['portfolio_value'])
        self.assertAlmostEqual(before['net_contributions'],after['net_contributions'])
        self.assertAlmostEqual(before['total_result'],after['total_result'])
        self.assertEqual(after['cash_value'],50)
        self.assertEqual(self.db.execute('SELECT SUM(total_cost) FROM holdings').fetchone()[0],200)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM holdings WHERE sub_portfolio_id=?',(self.child,)).fetchone()[0],0)
        self.assertEqual(snapshot(self.child,'value')['total_result'],10)
        with self.quotes({'ABC':999}):
            self.assertEqual(Value.get_portfolio_value(self.child)['total_result'],10)
        count=self.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
        archive(self.child)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0],count)
        self.assertTrue(Audit.audit_portfolio_integrity(self.pid)['is_consistent'])
        self.assertTrue(Audit.audit_portfolio_integrity(self.child)['is_consistent'])

    def test_missing_quote_does_not_archive_or_move_assets(self):
        self.seed()
        with self.quotes({}),self.stamps(),patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            with self.assertRaises(ValidationError): archive(self.child)
        self.assertFalse(self.db.execute('SELECT is_archived FROM portfolios WHERE id=?',(self.child,)).fetchone()[0])
        self.assertEqual(self.db.execute('SELECT quantity FROM holdings WHERE sub_portfolio_id=?',(self.child,)).fetchone()[0],1)

    def test_real_reports_can_be_serialized_and_parent_analysis_keeps_archived_history(self):
        self.seed()
        from actual_results_service import analyze
        with self.quotes({'ABC':140}),self.stamps(),patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}),patch('price_service.PriceService.fetch_metadata',return_value={'currency':'PLN','company_name':'ABC','sector':'Test','industry':'Test'}),patch('price_service.PriceService.get_tickers_requiring_history_sync',return_value=[]):
            before=analyze([self.pid])
            archive(self.child)
            after=analyze([self.pid])
        self.assertIsNotNone(snapshot(self.child,'results'))
        self.assertEqual(before['net_deposits'],after['net_deposits'])
        self.assertEqual(before['closing_value'],after['closing_value'])

    def test_failure_after_asset_movement_rolls_back_everything(self):
        self.seed()
        self.db.execute('UPDATE portfolios SET current_cash=-1 WHERE id=?',(self.child,));self.db.commit()
        count=self.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
        with self.quotes({'ABC':140}),self.stamps(),patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}),self.reports():
            with self.assertRaises(ValidationError): archive(self.child)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0],count)
        self.assertEqual(self.db.execute('SELECT quantity FROM holdings WHERE sub_portfolio_id=?',(self.child,)).fetchone()[0],1)
        self.assertIsNone(snapshot(self.child,'value'))
