import unittest
from datetime import date,timedelta
from unittest.mock import patch
from test_investment_corrections import InvestmentCorrectionsTest
from portfolio_valuation_service import PortfolioValuationService as Valuation
from portfolio_trade_service import PortfolioTradeService
from manual_stock_prices import save
from api.exceptions import ApiError,ValidationError


class ManualStockPriceTest(unittest.TestCase):
    setUp=InvestmentCorrectionsTest.setUp
    tearDown=InvestmentCorrectionsTest.tearDown
    holding=InvestmentCorrectionsTest.holding
    quotes=InvestmentCorrectionsTest.quotes
    stamps=InvestmentCorrectionsTest.stamps

    def view(self,prices=None):
        with self.quotes(prices or {}),self.stamps(),patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={'ABC':{'prev_close':100}}):
            return Valuation.get_holdings(self.pid,cached_prices_only=True),Valuation.get_portfolio_value(self.pid,cached_prices_only=True)

    def test_purchase_reference_is_visible_but_not_a_zero_market_return(self):
        self.holding()
        rows,value=self.view()
        self.assertEqual(rows[0]['price_basis'],'purchase')
        self.assertEqual(rows[0]['estimated_current_value'],200)
        self.assertIsNone(rows[0]['current_value'])
        self.assertIsNone(rows[0]['profit_loss'])
        self.assertIsNone(value['portfolio_value'])
        self.assertEqual(value['estimated_portfolio_value'],250)
        self.assertEqual(value['reference_positions_count'],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM stock_prices').fetchone()[0],0)

    def test_manual_quote_has_its_own_date_and_no_fake_daily_change(self):
        self.holding();stamp=date.today().isoformat()
        save('ABC',dict(price=150,date=stamp,version=0))
        rows,value=self.view({'ABC':120})
        self.assertEqual(rows[0]['price_basis'],'manual')
        self.assertEqual(rows[0]['price_last_updated_at'],stamp)
        self.assertEqual(rows[0]['current_value'],300)
        self.assertEqual(rows[0]['profit_loss'],100)
        self.assertIsNone(rows[0]['change_1d_percent'])
        self.assertEqual(value['valuation_status'],'stale')
        self.assertIsNone(value['xirr_percent'])
        self.assertEqual(self.db.execute('SELECT current_cash FROM portfolios WHERE id=?',(self.pid,)).fetchone()[0],50)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0],0)

    def test_clear_returns_to_provider_and_keeps_version_guard(self):
        self.holding();payload=dict(price=150,date=date.today().isoformat(),version=0)
        save('ABC',payload)
        with self.assertRaises(ApiError):save('ABC',payload)
        save('ABC',dict(version=1),clear=True)
        rows,value=self.view({'ABC':120})
        self.assertEqual(rows[0]['current_value'],240)
        self.assertEqual(rows[0]['price_basis'],'market')
        self.assertEqual(rows[0]['manual_price_version'],2)

    def test_invalid_prices_and_future_dates_are_rejected(self):
        self.holding()
        for price in [0,-1,True,float('nan'),float('inf')]:
            with self.subTest(price=price),self.assertRaises(ValidationError):save('ABC',dict(price=price,date=date.today().isoformat()))
        with self.assertRaises(ValidationError):save('ABC',dict(price=120,date=(date.today()+timedelta(days=1)).isoformat()))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM manual_stock_prices').fetchone()[0],0)

    def test_sale_uses_actual_transaction_price_without_quotes(self):
        self.holding();save('ABC',dict(price=150,date=date.today().isoformat()))
        with patch('portfolio_trade_service.PriceService.get_prices',side_effect=AssertionError('No quote needed')):
            PortfolioTradeService.sell_stock(self.pid,'ABC',1,110)
        tx=self.db.execute("SELECT * FROM transactions WHERE type='SELL'").fetchone()
        self.assertEqual(tx['realized_profit'],10)
        self.assertEqual(self.db.execute('SELECT total_cost FROM holdings').fetchone()[0],100)
        self.assertEqual(self.db.execute('SELECT current_cash FROM portfolios WHERE id=?',(self.pid,)).fetchone()[0],160)

    def test_missing_fx_is_not_replaced_by_a_fake_rate(self):
        self.holding('USD')
        rows,value=self.view()
        self.assertIsNone(rows[0]['estimated_current_value'])
        self.assertIsNone(value['estimated_portfolio_value'])

    def test_parent_aggregates_cost_references_once(self):
        child=self.db.execute("INSERT INTO portfolios(name,account_type,parent_portfolio_id,current_cash) VALUES('Child','IKE',?,10)",(self.pid,)).lastrowid
        self.db.commit();self.holding(child=child)
        _,value=self.view()
        self.assertEqual(value['estimated_portfolio_value'],260)
        self.assertEqual(value['reference_positions_count'],1)

if __name__=='__main__':unittest.main()
