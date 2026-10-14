"""Regression tests for the investment audit; all writes use temporary databases."""
import json
import sqlite3
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from flask import Flask
from api.exceptions import ValidationError,ApiError
from api.response import error_response
from database import get_db,init_db
from price_service import PriceService
from portfolio_trade_service import PortfolioTradeService as Trade
from portfolio_valuation_service import PortfolioValuationService as Valuation
from actual_results_service import analyze
from bond_service import BondService
from tests.investment_fixtures import parent,transaction
from uuid import uuid4
import routes_transactions


class InvestmentAuditFixes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=Flask(__name__)
        self.app.config.update(TESTING=True,DATABASE=str(Path(self.temp.name)/'audit.db'))
        init_db(self.app)
        self.app.register_blueprint(routes_transactions.portfolio_bp,url_prefix='/api/portfolio')
        self.app.register_error_handler(ValidationError,lambda e:error_response('validation_error',e.message,status=400))
        self.app.register_error_handler(ApiError,lambda e:error_response(e.code,e.message,status=e.status))
        self.context=self.app.app_context();self.context.push()
        self.db=get_db();self.client=self.app.test_client()

    def tearDown(self):
        self.context.pop();self.temp.cleanup()

    def test_history_refresh_before_lock_rechecks_available_cash(self):
        pid=parent(self.db,100)
        original=PriceService.sync_stock_history
        frame=pd.DataFrame({'Close':[80.]},index=pd.to_datetime(['2026-10-07']))
        def refresh(ticker,start):
            self.assertFalse(self.db.in_transaction)
            original(ticker,start)
            peer=sqlite3.connect(self.app.config['DATABASE'])
            try:
                with peer:
                    peer.execute('UPDATE portfolios SET current_cash=current_cash-80 WHERE id=?',(pid,))
                    transaction(peer,pid,'WITHDRAW',80,day='2026-10-07')
            finally:peer.close()
        with patch.object(PriceService,'_download_with_retry',return_value=frame),patch.object(PriceService,'sync_stock_history',side_effect=refresh):
            with self.assertRaises(ValueError):Trade.buy_stock(pid,'AUDIT.WA',1,80,'2026-10-07')
        self.assertEqual(self.db.execute('SELECT current_cash FROM portfolios WHERE id=?',(pid,)).fetchone()[0],20)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM transactions WHERE type='BUY'").fetchone()[0],0)

    def test_price_history_quality_runs_after_download_without_obsolete_arguments(self):
        parent(self.db)
        frame=pd.DataFrame({'Close':[80.]},index=pd.to_datetime(['2026-10-07']))
        with patch.object(PriceService,'_download_with_retry',return_value=frame),patch.object(PriceService,'audit_price_history_quality',wraps=PriceService.audit_price_history_quality) as audit:
            PriceService.sync_stock_history('AUDIT.WA','2026-10-07')
            audit.assert_called_once_with(days=30,jump_threshold_percent=25.0,refresh_flagged=False)

    def test_concurrent_withdrawal_rechecks_cash_after_lock(self):
        pid=parent(self.db,100)
        db=self.db;path=self.app.config['DATABASE']
        class CompetingWithdrawal:
            def execute(self,sql,params=()):
                if sql=='BEGIN IMMEDIATE':
                    peer=sqlite3.connect(path)
                    try:
                        with peer:
                            transaction(peer,pid,'WITHDRAW',80,day='2026-10-07')
                            peer.execute('UPDATE portfolios SET current_cash=20 WHERE id=?',(pid,))
                    finally:peer.close()
                return db.execute(sql,params)
            def rollback(self):db.rollback()
            def commit(self):db.commit()
        with patch('portfolio_trade_service.get_db',return_value=CompetingWithdrawal()):
            with self.assertRaises(ValueError):Trade.withdraw_cash(pid,80,'2026-10-07')
        self.assertEqual(db.execute('SELECT current_cash FROM portfolios WHERE id=?',(pid,)).fetchone()[0],20)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM transactions WHERE type='WITHDRAW'").fetchone()[0],1)

    def test_sale_rechecks_units_after_lock(self):
        pid=parent(self.db,80);transaction(self.db,pid,'BUY',80,1,'AUDIT.WA')
        self.db.execute('UPDATE portfolios SET current_cash=0 WHERE id=?',(pid,))
        self.db.execute("INSERT INTO holdings(portfolio_id,ticker,quantity,average_buy_price,total_cost,currency) VALUES(?,'AUDIT.WA',1,80,80,'PLN')",(pid,));self.db.commit()
        db=self.db;path=self.app.config['DATABASE']
        class CompetingSale:
            def execute(self,sql,params=()):
                if sql=='BEGIN IMMEDIATE':
                    peer=sqlite3.connect(path)
                    try:
                        with peer:
                            transaction(peer,pid,'SELL',100,1,'AUDIT.WA')
                            peer.execute('UPDATE portfolios SET current_cash=100 WHERE id=?',(pid,))
                            peer.execute('DELETE FROM holdings WHERE portfolio_id=?',(pid,))
                    finally:peer.close()
                return db.execute(sql,params)
            def rollback(self):db.rollback()
            def commit(self):db.commit()
        with patch('portfolio_trade_service.get_db',return_value=CompetingSale()):
            with self.assertRaises(ValueError):Trade.sell_stock(pid,'AUDIT.WA',1,100,'2026-10-07')
        self.assertEqual(db.execute("SELECT COUNT(*) FROM transactions WHERE type='SELL'").fetchone()[0],1)
        self.assertEqual(db.execute('SELECT current_cash FROM portfolios WHERE id=?',(pid,)).fetchone()[0],100)

    def test_failed_retry_key_rolls_back_purchase_then_retry_books_once(self):
        pid=parent(self.db)
        payload=dict(portfolio_id=pid,ticker='AUDIT.WA',quantity=1,price=100,date='2026-10-07')
        with patch.object(PriceService,'sync_stock_history',return_value=None):
            with patch('routes_transactions._store_idempotent_response',side_effect=RuntimeError('injected')):
                with self.assertRaises(RuntimeError):self.client.post('/api/portfolio/buy',json=payload,headers={'Idempotency-Key':'retry'})
            self.assertEqual(self.db.execute('SELECT current_cash FROM portfolios WHERE id=?',(pid,)).fetchone()[0],1000)
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM holdings').fetchone()[0],0)
            for _ in range(2):
                self.assertEqual(self.client.post('/api/portfolio/buy',json=payload,headers={'Idempotency-Key':'retry'}).status_code,201)
            self.assertEqual(self.client.post('/api/portfolio/buy',json=dict(payload,price=200),headers={'Idempotency-Key':'retry'}).status_code,409)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM transactions WHERE type='BUY'").fetchone()[0],1)

    def test_future_and_invalid_dates_rejected_without_financial_writes(self):
        pid=parent(self.db)
        with patch.object(PriceService,'sync_stock_history') as refresh:
            for invalid in ((date.today()+timedelta(days=1)).isoformat(),'bad-date'):
                for method,args in ((Trade.buy_stock,(pid,'AUDIT.WA',1,100,invalid)),(Trade.sell_stock,(pid,'AUDIT.WA',1,100,invalid)),(Trade.deposit_cash,(pid,100,invalid)),(Trade.withdraw_cash,(pid,100,invalid)),(Trade.record_dividend,(pid,'AUDIT.WA',10,invalid))):
                    with self.assertRaises(ValidationError):method(*args)
            refresh.assert_not_called()
        self.assertEqual(self.db.execute('SELECT current_cash FROM portfolios WHERE id=?',(pid,)).fetchone()[0],1000)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0],1)

    def test_archived_child_is_excluded_from_parent_xirr(self):
        pid=parent(self.db,100)
        for archived in (0,1):
            child=self.db.execute("INSERT INTO portfolios(name,account_type,parent_portfolio_id,current_cash,is_archived) VALUES('Child','STANDARD',?,100,?)",(pid,archived)).lastrowid
            transaction(self.db,pid,'DEPOSIT',100,sub=child)
        self.db.commit()
        value=Valuation.get_portfolio_value(pid,cached_prices_only=True)
        self.assertEqual(value['portfolio_value'],200)
        self.assertEqual(value['investment_result'],0)
        self.assertEqual(value['xirr_percent'],0)

    def test_bond_custody_is_reconciled_separately_from_stock_holdings(self):
        pid=parent(self.db)
        self.db.execute("UPDATE portfolios SET account_type='BONDS' WHERE id=?",(pid,));self.db.commit()
        bond=BondService.create(dict(portfolio_id=pid,name='Test',kind='CUSTOM',quantity=1,nominal=100,purchase_price=100,
            purchase_date='2026-10-07',maturity_date='2027-10-07',interest_rate=5,acquisition='BUY',request_id=str(uuid4())))
        result=analyze([pid])
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['reconciliation']['positions_mismatch'],[])
        self.assertIsNotNone(result['dietz_percent'])
        self.db.execute('UPDATE bonds SET quantity=2 WHERE id=?',(bond['id'],));self.db.commit()
        self.assertEqual(analyze([pid])['reconciliation']['positions_mismatch'],['BOND:'+str(bond['id'])])

    def test_old_ppk_month_warning_does_not_block_lifetime_xirr(self):
        pid=parent(self.db,0)
        self.db.execute("UPDATE portfolios SET account_type='PPK' WHERE id=?",(pid,))
        self.db.execute("INSERT INTO ppk_transactions(portfolio_id,date,employee_units,employer_units,price_per_unit) VALUES(?,'2024-01-02',1,1,100)",(pid,))
        history=[{'week':'2024-01-02','price':100},{'week':'2025-12-23','price':110},{'week':date.today().isoformat(),'price':120}]
        self.db.execute("INSERT INTO ppk_weekly_history(fund_id,data,last_week) VALUES('61777738',?,?)",(json.dumps(history),date.today().isoformat()));self.db.commit()
        result=analyze([pid])
        self.assertIsNotNone(result['xirr_percent'])
        self.assertIsNotNone(result['dietz_percent'])
        december=next(m for m in result['months'] if m['date']=='2025-12-31')
        self.assertIsNone(december['return_percent'])
        self.assertTrue(result['warnings'])
        self.db.execute("UPDATE ppk_weekly_history SET data=?",(json.dumps(history[:-1]),));self.db.commit()
        self.assertIsNone(analyze([pid])['xirr_percent'])
