import unittest
from datetime import date
from unittest.mock import patch
from test_asset_transfer import AssetTransferTest
from asset_transfer_service import transfer
from portfolio_chart_service import attribution,benchmark_returns
from portfolio_history_service import PortfolioHistoryService as History
from investment_review_service import instrument,strategies

class InvestmentReviewTest(unittest.TestCase):
    setUp=AssetTransferTest.setUp
    tearDown=AssetTransferTest.tearDown
    holding=AssetTransferTest.holding
    prepare=AssetTransferTest.prepare
    quotes=AssetTransferTest.quotes
    stamps=AssetTransferTest.stamps

    def test_asset_entry_and_exit_attribution_and_root_cancel(self):
        transfer(self.prepare());today=date.today()
        prices=({'ABC':'PLN'},{'ABC':{today.isoformat():140}})
        with patch.object(History,'_build_price_context',return_value=prices),self.quotes({'ABC':140}),self.stamps(),patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            child=attribution(self.child,today,today)
            root=attribution(self.pid,today,today)
        self.assertEqual(child['items'][0]['value'],10)
        self.assertEqual(root['items'][0]['value'],80)
        transfer(dict(portfolio_id=self.pid,source_id=self.child,target_id=None,ticker='ABC',quantity=1,expected_quantity=1,price_pln=140))
        with patch.object(History,'_build_price_context',return_value=prices),self.quotes({'ABC':140}),self.stamps(),patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            self.assertEqual(attribution(self.child,today,today)['items'][0]['value'],10)

    def test_monthly_matrix_treats_entry_as_capital(self):
        transfer(self.prepare())
        self.db.execute("UPDATE transactions SET date='2026-09-01' WHERE type IN ('ASSET_IN','ASSET_OUT')");self.db.commit()
        values={'2026-09':{'total_value':130},'2026-10':{'total_value':140}}
        with patch.object(History,'_calculate_historical_metrics',return_value=values):
            matrix=History.get_performance_matrix(self.child)
        self.assertEqual(matrix['2026']['9'],0)
        self.assertAlmostEqual(matrix['2026']['10'],7.69)

    def test_instrument_result_and_strategy_capital(self):
        transfer(self.prepare())
        with self.quotes({'ABC':140}),self.stamps(),patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            child=instrument(self.child,'ABC');root=instrument(self.pid,'ABC');comparison=strategies(self.pid)
        self.assertEqual(child['quantity'],1)
        self.assertEqual(child['total_result'],10)
        self.assertEqual(root['total_result'],80)
        self.assertEqual(child['events'][0]['type'],'ASSET_IN')
        self.assertEqual(comparison['items'][0]['starting_capital'],130)
        self.assertEqual(comparison['items'][0]['result'],10)

    def test_benchmark_percent_uses_dated_fx(self):
        self.prepare()
        prices=({'VT':'USD'},{'VT':{'2026-09-01':100,'2026-09-30':110},'USDPLN=X':{'2026-09-01':4,'2026-09-30':3}})
        with patch.object(History,'_build_price_context',return_value=prices):
            data=benchmark_returns(self.pid,date(2026,9,1),date(2026,9,30),'VT')
        self.assertEqual(data['items'][0]['value'],-17.5)
