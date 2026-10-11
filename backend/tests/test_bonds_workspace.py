import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from flask import Flask

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import get_db,init_db
from bond_service import BondService
from bond_model import estimate,shift
from api.exceptions import ValidationError
from portfolio_valuation_service import PortfolioValuationService
from portfolio_audit_service import PortfolioAuditService
from cash_forecast_service import workspace as cash_forecast
from dashboard_actions_service import workspace as actions_workspace

class BondWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=Flask(__name__);self.app.config.update(TESTING=True,DATABASE=str(Path(self.tmp.name)/'bonds.db'))
        init_db(self.app);self.context=self.app.app_context();self.context.push()
        self.db=get_db()
        self.pid=self.db.execute("INSERT INTO portfolios(name,account_type,current_cash,total_deposits) VALUES('Bonds','BONDS',1000,1000)").lastrowid
        self.db.execute("INSERT INTO transactions(portfolio_id,ticker,type,quantity,price,total_value,date) VALUES(?,'CASH','DEPOSIT',1,1000,1000,'2025-01-01')",(self.pid,))
        self.account=self.db.execute("INSERT INTO budget_accounts(name,balance,currency) VALUES('PKO',100,'PLN')").lastrowid
        self.db.commit()
        self.plan=dict(portfolio_id=self.pid,name='EDO TEST',kind='EDO',quantity=10,nominal=100,purchase_price=100,
            purchase_date='2025-01-01',interest_rate=6,tax_rate=19,redemption_fee=3,fee_policy='CAP_INTEREST',
            acquisition='BUY',payout_account_id=None,forecast_enabled=False,notes='',request_id=str(uuid4()))
    def tearDown(self):self.context.pop();self.tmp.cleanup()
    def create(self,**extra):return BondService.create(dict(self.plan,**extra))['id']
    def bond(self):return BondService.get_bonds(self.pid)[0]
    def cash(self):return self.db.execute('SELECT current_cash FROM portfolios WHERE id=?',(self.pid,)).fetchone()[0]
    def value(self):return PortfolioValuationService._calculate_single_portfolio_value(dict(self.db.execute('SELECT * FROM portfolios WHERE id=?',(self.pid,)).fetchone()),True)
    def settle(self,bid,**extra):
        payload=dict(kind='REDEEM',date=date.today().isoformat(),net_amount=1060,quantity=10,version=self.bond()['version'],confirmed_actual=True,request_id=str(uuid4()))
        payload.update(extra)
        return BondService.settle(bid,payload)

    def test_purchase_spends_cash_without_fictitious_profit(self):
        self.create(purchase_date=date.today().isoformat())
        self.assertEqual(self.cash(),0);self.assertEqual(self.value()['portfolio_value'],1000);self.assertEqual(self.value()['total_result'],0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0],2)

    def test_existing_assets_add_contribution_but_not_cash_or_budget_income(self):
        self.create(acquisition='EXISTING',purchase_date=date.today().isoformat())
        self.assertEqual(self.cash(),1000);self.assertEqual(self.value()['portfolio_value'],2000);self.assertEqual(self.value()['total_result'],0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)

    def test_purchase_replay_is_idempotent(self):
        a=BondService.create(self.plan);self.assertEqual(BondService.create(self.plan),a)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM bonds').fetchone()[0],1)

    def test_insufficient_cash_rolls_back_everything(self):
        with self.assertRaises(ValidationError):self.create(quantity=11)
        self.assertEqual(self.cash(),1000);self.assertEqual(self.db.execute('SELECT COUNT(*) FROM bonds').fetchone()[0],0)

    def test_dates_and_nan_are_rejected_before_writes(self):
        for values in (dict(purchase_date='not-a-date'),dict(purchase_date='2099-01-01'),dict(interest_rate=float('nan')),dict(quantity=1.5),dict(kind='BAD')):
            with self.assertRaises(ValidationError):self.create(**values)
        self.assertEqual(self.cash(),1000)

    def test_wrong_portfolio_type_is_rejected(self):
        self.db.execute("UPDATE portfolios SET account_type='STANDARD' WHERE id=?",(self.pid,));self.db.commit()
        with self.assertRaises(ValidationError):self.create()

    def test_annual_accrual_is_visible_before_capitalization(self):
        self.create();b=self.bond();view=estimate(b,[],[],date(2025,7,2))
        self.assertAlmostEqual(view['accrued_interest'],29.92,places=2);self.assertEqual(view['capitalized_interest'],0)
        self.assertGreater(view['estimated_interest_net'],0);self.assertEqual(self.cash(),0)

    def test_edo_capitalizes_and_applies_period_rate(self):
        self.create();b=self.bond();view=estimate(b,[dict(period=2,rate=5),dict(period=3,rate=4)],[],date(2027,1,1))
        self.assertEqual(view['capitalized_interest'],113);self.assertEqual(view['accrued_interest'],113)
        self.assertEqual(view['total_value'],1113);self.assertEqual(view['warnings'],[])

    def test_missing_period_rate_is_disclosed(self):
        self.create();self.assertTrue(self.bond()['warnings']);self.assertTrue(self.bond()['periods'][1]['assumed'])

    def test_interest_stops_at_maturity(self):
        self.create(kind='TOS');b=self.bond()
        x=estimate(b,[],[],date(2028,1,1));y=estimate(b,[],[],date(2035,1,1))
        self.assertEqual(x['total_value'],y['total_value']);self.assertEqual(y['status'],'MATURED');self.assertEqual(y['early_redemption_fee'],0)

    def test_coupon_moves_receivable_into_cash_only_once(self):
        bid=self.create(kind='COI');b=self.bond();before=self.value()['portfolio_value']
        data=dict(kind='COUPON',period=1,date='2026-01-01',net_amount=48.6,quantity=10,version=b['version'],request_id=str(uuid4()))
        BondService.settle(bid,data);self.assertEqual(BondService.settle(bid,data)['received'],48.6)
        self.assertEqual(self.cash(),48.6);self.assertTrue(self.bond()['periods'][0]['paid'])
        self.assertAlmostEqual(self.value()['portfolio_value'],before-11.4,places=2)

    def test_partial_redemption_reduces_quantity_and_cost(self):
        bid=self.create();self.settle(bid,quantity=4,net_amount=430)
        self.assertEqual(self.bond()['remaining_quantity'],6);self.assertEqual(self.bond()['cost_remaining'],600);self.assertEqual(self.cash(),430)

    def test_full_redemption_closes_assets(self):
        bid=self.create();self.settle(bid)
        self.assertEqual(self.bond()['status'],'CLOSED');self.assertEqual(self.bond()['total_value'],0);self.assertEqual(self.cash(),1060)
        self.assertEqual(self.value()['total_result'],60)

    def test_stale_version_and_double_coupon_rejected(self):
        bid=self.create(kind='COI');b=self.bond()
        data=dict(kind='COUPON',period=1,date='2026-01-01',net_amount=48.6,quantity=10,version=b['version'],request_id=str(uuid4()))
        BondService.settle(bid,data)
        with self.assertRaises(ValidationError):BondService.settle(bid,dict(data,request_id=str(uuid4())))
        with self.assertRaises(ValidationError):BondService.settle(bid,dict(data,version=self.bond()['version'],request_id=str(uuid4())))

    def test_cancel_restores_cash_and_preserves_audit(self):
        bid=self.create();BondService.cancel(bid,dict(version=1,request_id=str(uuid4())))
        self.assertEqual(self.cash(),1000);self.assertEqual(self.bond()['status'],'VOID');self.assertEqual(self.value()['total_result'],0)
        self.assertEqual(len(self.bond()['events']),2)

    def test_cannot_cancel_after_payout(self):
        bid=self.create();self.settle(bid)
        with self.assertRaises(ValidationError):BondService.cancel(bid,dict(version=2,request_id=str(uuid4())))

    def test_reconciliation_never_creates_equity_holdings_for_bonds(self):
        self.create();rebuilt=PortfolioAuditService.rebuild_holdings_from_transactions(self.pid)
        self.assertEqual(rebuilt['cash'],0);self.assertEqual(rebuilt['holdings'],{})

    def test_cash_transfer_from_payout_is_atomic_and_not_income(self):
        bid=self.create(payout_account_id=self.account);self.settle(bid,transfer_to_budget=True)
        self.assertEqual(self.cash(),0);self.assertEqual(self.db.execute('SELECT balance FROM budget_accounts WHERE id=?',(self.account,)).fetchone()[0],1160)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM budget_investment_transfers').fetchone()[0],1)

    def test_transfer_failure_rolls_back_redemption_and_cash(self):
        bid=self.create(payout_account_id=self.account)
        self.db.execute("UPDATE budget_accounts SET currency='EUR' WHERE id=?",(self.account,));self.db.commit()
        with self.assertRaises(ValidationError):self.settle(bid,transfer_to_budget=True)
        self.assertEqual(self.cash(),0);self.assertEqual(self.bond()['remaining_quantity'],10);self.assertEqual(len(self.bond()['events']),1)

    def test_import_preview_and_atomic_duplicate_guard(self):
        text='name;kind;quantity;purchase_price;purchase_date;interest_rate\nTOS test;TOS;2;100;2025-01-01;6\n'
        rows=BondService.preview_import(self.pid,text)['rows'];self.assertFalse(rows[0]['duplicate'])
        BondService.import_rows(dict(portfolio_id=self.pid,rows=[rows[0]['plan']],request_id=str(uuid4())))
        self.assertTrue(BondService.preview_import(self.pid,text)['rows'][0]['duplicate']);self.assertEqual(self.cash(),1000)
        with self.assertRaises(ValidationError):BondService.import_rows(dict(portfolio_id=self.pid,rows=[dict(rows[0]['plan'],name='New'),rows[0]['plan']],request_id=str(uuid4())))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM bonds').fetchone()[0],1)

    def test_forecast_requires_opt_in_and_does_not_book_interest(self):
        self.create(kind='COI',payout_account_id=self.account)
        self.assertFalse([e for e in cash_forecast()['events'] if e['key'].startswith('bond:')])
        self.db.execute('UPDATE bonds SET forecast_enabled=1');self.db.commit()
        view=cash_forecast();events=[e for e in view['events'] if e['key'].startswith('bond:')]
        self.assertTrue(events);self.assertEqual(events[0]['account_id'],self.account);self.assertEqual(self.cash(),0)
        self.assertTrue([a for a in actions_workspace()['items'] if a['source']=='bond'])

    def test_calendar_anchor_handles_leap_year_and_month_end(self):
        self.assertEqual(shift(date(2024,2,29),12),date(2025,2,28))
        self.assertEqual(shift(date(2026,1,31),2),date(2026,3,31))

    def test_fee_cap_does_not_consume_principal(self):
        self.create(purchase_date=date.today().isoformat());b=self.bond()
        view=estimate(b,[],[],date.today());self.assertEqual(view['early_redemption_net'],1000);self.assertEqual(view['early_redemption_fee'],0)

    def test_corrupt_legacy_date_does_not_block_other_positions(self):
        self.create()
        self.db.execute("INSERT INTO bonds(portfolio_id,name,principal,interest_rate,purchase_date) VALUES(?,'Old',100,6,'bad-date')",(self.pid,));self.db.commit()
        rows=BondService.get_bonds(self.pid)
        self.assertEqual(len(rows),2);self.assertEqual(next(b for b in rows if b['name']=='Old')['total_value'],100)

    def test_confirmed_rate_changes_current_accrual_and_replays_safely(self):
        bid=self.create();data=dict(period=2,rate=4,version=1,request_id=str(uuid4()))
        BondService.rate(bid,data);BondService.rate(bid,data)
        self.assertEqual(self.bond()['current_rate'],4);self.assertEqual(self.bond()['warnings'],[])

    def test_edit_terms_preserves_cash_and_rejects_booked_amount_change(self):
        bid=self.create();payload=dict(self.plan,version=1,name='Correct series',request_id=str(uuid4()))
        BondService.update(bid,payload);self.assertEqual(self.cash(),0);self.assertEqual(self.bond()['name'],'Correct series')
        with self.assertRaises(ValidationError):BondService.update(bid,dict(payload,quantity=9,version=2,request_id=str(uuid4())))

    def test_coupon_receivable_is_not_double_counted_in_projection(self):
        self.create(kind='COI');view=BondService.workspace(self.pid)
        point=view['forecast'][-1]
        position=self.bond();expected=estimate(position,[],position['events'],date.fromisoformat(point['date']))
        self.assertAlmostEqual(point['value']+point['coupons'],expected['estimated_value_net'],places=2)

    def test_http_lifecycle_and_iso_date_serialization(self):
        from routes import portfolio_bp
        from api.response import error_response
        from api.exceptions import NotFoundError
        self.app.register_blueprint(portfolio_bp,url_prefix='/api/portfolio')
        self.app.register_error_handler(ValidationError,lambda e:error_response('validation_error',str(e),status=400))
        self.app.register_error_handler(NotFoundError,lambda e:error_response('not_found',str(e),status=404))
        client=self.app.test_client()
        response=client.post('/api/portfolio/bonds',json=self.plan)
        self.assertEqual(response.status_code,201,response.get_json());bid=response.get_json()['payload']['id']
        result=client.get(f'/api/portfolio/bonds/workspace/{self.pid}')
        self.assertEqual(result.status_code,200,result.get_json());self.assertEqual(result.get_json()['payload']['items'][0]['purchase_date'],'2025-01-01')
        preview=client.get(f'/api/portfolio/bonds/position/{bid}/estimate?date=2025-07-02')
        self.assertEqual(preview.status_code,200);self.assertEqual(preview.get_json()['payload']['capitalized_interest'],0)

    def test_historical_payout_does_not_add_cash_again(self):
        bid=self.create(acquisition='EXISTING');self.settle(bid,history_only=True)
        self.assertEqual(self.cash(),1000);self.assertEqual(self.bond()['total_value'],0)
        self.assertEqual(self.value()['total_result'],60)
        self.assertEqual(self.db.execute('SELECT balance FROM budget_accounts').fetchone()[0],100)

    def test_editing_label_does_not_erase_confirmed_period_rates(self):
        bid=self.create();BondService.rate(bid,dict(period=2,rate=4,version=1,request_id=str(uuid4())))
        BondService.update(bid,dict(self.plan,name='Updated',version=2,request_id=str(uuid4())))
        self.assertEqual(self.bond()['current_rate'],4)

    def test_monthly_bond_fee_cap_applies_only_to_first_month(self):
        self.create(kind='ROR',purchase_date='2025-01-01',redemption_fee=.5,fee_policy='FIRST_PERIOD')
        b=self.bond()
        first=estimate(b,[],[],date(2025,1,2))
        second=estimate(b,[],[dict(kind='COUPON',date='2025-02-01',quantity=10,period=1,net_amount=4.05)],date(2025,2,2))
        self.assertLess(first['early_redemption_fee'],5)
        self.assertEqual(second['early_redemption_fee'],5)
        self.assertLess(second['early_redemption_net'],1000)

    def test_future_schedule_compounds_without_adding_future_interest_today(self):
        self.create(kind='TOS');b=self.bond()
        view=estimate(b,[],[],date(2025,7,2))
        self.assertEqual(view['capitalized_interest'],0)
        self.assertEqual(view['periods'][1]['gross'],63.6)
        self.assertEqual(view['periods'][2]['gross'],67.4)
        self.assertEqual(view['accrued_interest'],29.92)

    def test_calendar_keeps_overdue_unpaid_coupons(self):
        self.create(kind='COI')
        events=BondService.workspace(self.pid)['events']
        self.assertTrue(any(e['kind']=='COUPON' and e['date']=='2026-01-01' for e in events))

if __name__=='__main__':unittest.main()
