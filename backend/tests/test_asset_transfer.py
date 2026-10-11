import unittest
from datetime import date
from unittest.mock import patch
from test_investment_corrections import InvestmentCorrectionsTest
from asset_transfer_service import transfer,strategy_basis
from portfolio_valuation_service import PortfolioValuationService as Value
from portfolio_audit_service import PortfolioAuditService as Audit
from portfolio_trade_service import PortfolioTradeService as Trade
from api.exceptions import ValidationError


class AssetTransferTest(unittest.TestCase):
    setUp=InvestmentCorrectionsTest.setUp
    tearDown=InvestmentCorrectionsTest.tearDown
    holding=InvestmentCorrectionsTest.holding
    quotes=InvestmentCorrectionsTest.quotes
    stamps=InvestmentCorrectionsTest.stamps

    def prepare(self):
        self.holding()
        today=date.today().isoformat()
        self.db.execute("INSERT INTO transactions(portfolio_id,ticker,date,type,quantity,price,total_value) VALUES(?,'CASH',?,'DEPOSIT',1,250,250)",(self.pid,today))
        self.db.execute("INSERT INTO transactions(portfolio_id,ticker,date,type,quantity,price,total_value) VALUES(?,'ABC',?,'BUY',2,100,200)",(self.pid,today))
        self.child=self.db.execute("INSERT INTO portfolios(name,account_type,parent_portfolio_id,current_cash) VALUES('Nowe','IKE',?,0)",(self.pid,)).lastrowid
        self.db.commit()
        return dict(portfolio_id=self.pid,source_id=None,target_id=self.child,ticker='ABC',quantity=1,price_pln=130,expected_quantity=2)

    def test_transfer_preserves_original_cost_cash_and_starts_child_at_market_value(self):
        result=transfer(self.prepare())
        self.assertEqual(result['entry_value'],130)
        self.assertEqual(result['original_cost'],100)
        self.assertEqual(self.db.execute('SELECT SUM(total_cost) FROM holdings').fetchone()[0],200)
        with self.quotes({'ABC':130}),self.stamps(),patch('portfolio_valuation_service.PriceService.get_quotes_lite',return_value={}):
            child=Value.get_portfolio_value(self.child,cached_prices_only=True)
            root=Value.get_portfolio_value(self.pid,cached_prices_only=True)
            h=Value.get_holdings(self.child,cached_prices_only=True)[0]
        self.assertEqual(child['total_result'],0)
        self.assertEqual(child['net_contributions'],130)
        self.assertEqual(h['total_cost'],130)
        self.assertEqual(h['profit_loss'],0)
        self.assertEqual(root['total_result'],60)
        self.assertEqual(root['net_contributions'],250)
        self.assertEqual(root['open_positions_result'],60)
        self.assertEqual(root['cash_value'],50)
        self.assertTrue(Audit.audit_portfolio_integrity(self.child)['is_consistent'])
        self.assertTrue(Audit.audit_portfolio_integrity(self.pid)['is_consistent'])

    def test_child_sale_has_new_strategy_profit_but_keeps_original_account_profit(self):
        transfer(self.prepare())
        Trade.sell_stock(self.pid,'ABC',1,140,date.today().isoformat(),sub_portfolio_id=self.child)
        row=self.db.execute("SELECT * FROM transactions WHERE type='SELL'").fetchone()
        self.assertEqual(row['realized_profit'],40)
        _,profits=strategy_basis(self.db,self.pid,self.child)
        self.assertEqual(profits[row['id']],10)
        self.assertTrue(Audit.audit_portfolio_integrity(self.child)['is_consistent'])
        from routes_history import closed_position_cycles, closed_positions
        with self.app.test_request_context():
            cycles=closed_position_cycles(self.child)[0].get_json()['payload']
            positions=closed_positions(self.child)[0].get_json()['payload']
        self.assertEqual(cycles['total_historical_profit'],10)
        self.assertEqual(cycles['positions'][0]['invested_capital'],130)
        self.assertEqual(positions['total_historical_profit'],10)

    def test_partial_transfer_repeated_request_and_cross_account_are_rejected(self):
        payload=self.prepare();transfer(payload)
        with self.assertRaises(ValidationError):transfer(payload)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM transactions WHERE type IN ('ASSET_IN','ASSET_OUT')").fetchone()[0],2)
        payload.update(expected_quantity=1,target_id=99999)
        with self.assertRaises(ValidationError):transfer(payload)
        self.assertEqual(self.db.execute('SELECT SUM(quantity) FROM holdings').fetchone()[0],2)

    def test_reverse_transfer_does_not_change_total_original_cost(self):
        transfer(self.prepare())
        transfer(dict(portfolio_id=self.pid,source_id=self.child,target_id=None,ticker='ABC',quantity=1,price_pln=140,expected_quantity=1))
        self.assertEqual(self.db.execute('SELECT SUM(total_cost) FROM holdings').fetchone()[0],200)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM holdings').fetchone()[0],1)
