"""Purchases belong to their month; paying a card never books them again."""
import io
import json
import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from database import get_db
from tests import test_budget_reserves as fixtures
from routes_budget_accounts import accounts_bp
from routes_budget_imports import imports_bp
from routes_dashboard import dashboard_bp
from budget_summary_service import monthly_budget_totals
from api.exceptions import ValidationError
import budget_accounts_service as accounts
import budget_bank_import_service as bank
import cash_forecast_service as forecast


class BudgetCreditCardTest(unittest.TestCase):
    result = fixtures.BudgetReservesTest.result

    def setUp(self):
        fixtures.BudgetReservesTest.setUp(self)
        self.app.register_blueprint(accounts_bp, url_prefix='/api/budget/accounts')
        self.app.register_blueprint(imports_bp, url_prefix='/api/budget/imports')
        self.app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
        for module in ('budget_accounts_service', 'cash_forecast_service', 'routes_budget_workspace',
                       'budget_refunds_service', 'budget_bank_import_service'):
            p = patch(module+'.date', fixtures.FrozenDate)
            p.start(); self.addCleanup(p.stop)
        self.card = self.result(self.client.post('/api/budget/accounts/', json=dict(
            name='Kredytówka', balance=0, account_type='CREDIT_CARD', request_id=str(uuid4()))), 201)['id']

    def purchase(self, amount=300, day='2026-10-01'):
        return self.result(self.client.post('/api/budget/workspace/entries', json=dict(
            account_id=self.card, kind='EXPENSE', amount=amount, date=day,
            description='Zakup kartą', category_id=self.category, request_id=str(uuid4()))), 201)['id']

    def payment(self, amount=300, **extra):
        balances = {r['id']:r['balance'] for r in get_db().execute('SELECT id,balance FROM budget_accounts')}
        data = dict(source_account_id=self.account, target_account_id=self.card,
            amount=amount, date=fixtures.FrozenDate.today().isoformat(), notes='', move_money=True,
            reserve_id=None, source_balance=balances[self.account], target_balance=balances[self.card], request_id=str(uuid4()))
        data.update(extra)
        return self.client.post('/api/budget/accounts/transfers', json=data), data

    def test_october_purchase_november_payment_counts_expense_and_debt_once(self):
        self.purchase()
        before = monthly_budget_totals(get_db(), '2026-10')
        self.assertEqual((before['spent'], before['income'], before['balance'], before['to_plan']), (300, 0, 9700, 9700))
        self.assertEqual((before['cash_balance'], before['credit_card_debt']), (10000, 300))
        fixtures.FrozenDate.current = date(2026, 11, 2)
        response, payload = self.payment()
        self.result(response, 201)
        self.result(self.client.post('/api/budget/accounts/transfers', json=payload), 201)
        self.assertEqual([r[0] for r in get_db().execute('SELECT balance FROM budget_accounts ORDER BY id')], [9700, 0])
        october = monthly_budget_totals(get_db(), '2026-10')
        november = monthly_budget_totals(get_db(), '2026-11')
        self.assertEqual((october['spent'], october['income'], october['to_plan']), (300, 0, before['to_plan']))
        self.assertEqual((november['spent'], november['income'], november['to_plan']), (0, 0, 9700))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_entries_v2').fetchone()[0], 1)
        view = accounts.workspace()
        self.assertEqual(view['history'][0]['kind'], 'CARD_PAYMENT')
        self.assertEqual(view['warnings'], [])

    def test_initial_debt_and_signed_corrections_are_not_monthly_expenses(self):
        payload = dict(name='Druga karta', balance=-450, account_type='CREDIT_CARD', request_id=str(uuid4()))
        card = self.result(self.client.post('/api/budget/accounts/', json=payload), 201)['id']
        self.assertEqual(self.result(self.client.post('/api/budget/accounts/', json=payload), 201)['id'], card)
        view = next(a for a in accounts.workspace()['accounts'] if a['id']==card)
        self.assertEqual(view['opening_balance'], -450)
        self.result(self.client.post(f'/api/budget/accounts/{card}/opening-balance', json=dict(balance=-500,
            expected_balance=-450, expected_opening_id=view['opening_record_id'], notes='', request_id=str(uuid4()))), 201)
        self.result(self.client.post(f'/api/budget/accounts/{card}/reconcile', json=dict(balance=-490,
            expected_balance=-500, notes='Sprawdzone w banku', request_id=str(uuid4()))), 201)
        totals = monthly_budget_totals(get_db(), '2026-10')
        self.assertEqual((totals['spent'], totals['income'], totals['to_plan']), (0, 0, 9510))
        self.assertEqual(len(accounts.workspace()['history']), 1)
        self.assertEqual(self.client.post('/api/budget/accounts/', json=dict(name='Zwykłe',balance=-1,request_id=str(uuid4()))).status_code, 400)

    def test_partial_payment_overpayment_and_stale_balance_are_safe(self):
        self.purchase()
        response, payload = self.payment(100)
        self.result(response, 201)
        before = accounts.workspace()['totals']
        self.assertEqual(self.payment(201)[0].status_code, 400)
        payload.update(request_id=str(uuid4()))
        self.assertEqual(self.client.post('/api/budget/accounts/transfers', json=payload).status_code, 409)
        self.assertEqual(accounts.workspace()['totals'], before)
        self.assertEqual(before['credit_card_debt'], 200)
        self.assertEqual(before['balance'], 9700)

    def test_payment_cannot_use_earmarked_cash_or_card_as_source(self):
        self.purchase()
        reserve = fixtures.BudgetReservesTest.create(self)
        self.result(fixtures.BudgetReservesTest.move(self, reserve, 'ADD', 9900), 201)
        self.assertEqual(self.payment()[0].status_code, 400)
        self.assertEqual(self.payment(1, source_account_id=self.card, target_account_id=self.account,
            source_balance=-300, target_balance=10000)[0].status_code, 400)
        self.assertEqual(accounts.workspace()['totals']['credit_card_debt'], 300)

    item = fixtures.BudgetReservesTest.item

    def test_cards_cannot_hold_reserves_even_with_positive_overpayment(self):
        get_db().execute('UPDATE budget_accounts SET balance=500 WHERE id=?', (self.card,)); get_db().commit()
        response = self.client.post('/api/budget/reserves', json=dict(name='Cel', account_id=self.card,
            target_amount=1200, due_date='2027-10-02', frequency='ONCE', request_id=str(uuid4())))
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(self.card, [a['id'] for a in fixtures.service.workspace()['accounts']])

    def test_planned_income_and_purchase_reserves_require_own_cash_accounts(self):
        import expected_income_service
        import budget_planning_service
        with self.assertRaises(ValidationError):
            expected_income_service.save(dict(name='Wpływ',account_id=self.card,amount=300,start_date='2026-11-01',
                end_date=None,frequency='ONCE',request_id=str(uuid4())))
        with self.assertRaises(ValidationError):
            budget_planning_service.save_purchase(dict(name='Zakup',account_id=self.card,amount=300,low=300,high=300,
                due_date='2026-11-01',category_id=self.category,status='PLANNED',notes='',request_id=str(uuid4())))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_reserves').fetchone()[0], 0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM budget_expected_incomes').fetchone()[0], 0)

    def test_refund_reduces_spending_and_card_debt_without_income(self):
        entry = self.purchase()
        self.result(self.client.post(f'/api/budget/workspace/entries/{entry}/refunds', json=dict(
            amount=75, date='2026-10-02', account_id=self.card, category_id=self.category,
            version=1, balance_mode='APPLY', expected_balance=-300, request_id=str(uuid4()))), 201)
        totals = monthly_budget_totals(get_db(), '2026-10')
        self.assertEqual((totals['spent'], totals['income'], totals['refunds'], totals['credit_card_debt']), (225, 0, 75, 225))

    def test_forecast_keeps_signed_total_but_does_not_report_card_as_cash_shortage(self):
        self.purchase()
        data = forecast.workspace({'variable_monthly':0})
        self.assertEqual(data['opening']['balance'], 9700)
        card = next(a for a in data['account_forecasts'] if a['id']==self.card)
        self.assertEqual(card['account_type'], 'CREDIT_CARD')
        self.assertTrue(all(s['first_shortfall'] is None for s in card['summaries']))
        self.assertEqual(data['transfer_suggestions'], [])
        self.assertFalse(any('Kredytówka: brak' in w for w in data['warnings']))
        self.assertTrue(any('nie zakłada terminu spłaty' in w for w in data['warnings']))

    def test_net_worth_classifies_card_as_liability_and_does_not_double_deduct(self):
        self.purchase()
        with patch('routes_dashboard.PortfolioService.list_portfolios', return_value=[]):
            data = self.result(self.client.get('/api/dashboard/global-summary'))
        self.assertEqual((data['total_assets'], data['total_liabilities'], data['net_worth']), (10000, 300, 9700))
        self.assertEqual(data['assets_breakdown']['budget_cash'], 10000)
        self.result(self.payment()[0],201)
        with patch('routes_dashboard.PortfolioService.list_portfolios', return_value=[]):
            paid = self.result(self.client.get('/api/dashboard/global-summary'))
        self.assertEqual((paid['total_assets'], paid['total_liabilities'], paid['net_worth']), (9700, 0, 9700))

    def test_regular_income_on_card_is_rejected_with_transfer_guidance(self):
        response = self.client.post('/api/budget/workspace/entries', json=dict(account_id=self.card,kind='INCOME',
            amount=300,date='2026-10-02',description='Spłata'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(monthly_budget_totals(get_db(), '2026-10')['income'], 0)

    def test_imported_card_payment_is_reviewed_and_linked_without_double_booking(self):
        self.purchase()
        self.result(self.payment()[0], 201)
        csv='Data;Opis;Odbiorca;Kwota;Waluta;ID\n02.10.2026;Spłata karty;BANK;300,00;PLN;CARD1\n'
        raw=csv.encode('utf-8')
        preview=self.result(self.client.post('/api/budget/imports/csv/preview',data={'file':(io.BytesIO(raw),'card.csv')}))
        stage=dict(account_id=self.card,balance_mode='APPLY',mapping=preview['mapping'],request_id=str(uuid4()))
        session=self.result(self.client.post('/api/budget/imports/csv',data={'file':(io.BytesIO(raw),'card.csv'),'data':json.dumps(stage)}),201)['id']
        view=bank.view(session);row=view['rows'][0]
        self.assertEqual(row['action'], 'SKIP')
        transfer_id=get_db().execute('SELECT id FROM budget_account_transfers').fetchone()[0]
        bank.update_row(session,row['id'],dict(version=view['version'],kind='TRANSFER',action='MATCH',transfer_id=transfer_id))
        data=bank.commit(session,dict(version=bank.view(session)['version'],request_id=str(uuid4())))
        self.assertEqual((data['created'],data['linked']), (0,1))
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['balance'],9700)

    def test_bank_side_card_payment_cannot_be_imported_as_another_expense(self):
        self.purchase()
        self.result(self.payment()[0],201)
        raw='Data;Opis;Odbiorca;Kwota;Waluta;ID\n02.10.2026;Spłata zadłużenia karty kredytowej;BANK;-300,00;PLN;BANK1\n'.encode('utf-8')
        preview=self.result(self.client.post('/api/budget/imports/csv/preview',data={'file':(io.BytesIO(raw),'bank.csv')}))
        stage=dict(account_id=self.account,balance_mode='APPLY',mapping=preview['mapping'],request_id=str(uuid4()))
        session=self.result(self.client.post('/api/budget/imports/csv',data={'file':(io.BytesIO(raw),'bank.csv'),'data':json.dumps(stage)}),201)['id']
        view=bank.view(session);row=view['rows'][0]
        self.assertEqual(row['action'],'SKIP')
        bank.update_row(session,row['id'],dict(version=view['version'],action='NEW'))
        with self.assertRaises(ValidationError):
            bank.commit(session,dict(version=bank.view(session)['version'],request_id=str(uuid4())))
        bank.update_row(session,row['id'],dict(version=bank.view(session)['version'],kind='TRANSFER',action='NEW',target_account_id=self.card))
        with self.assertRaises(ValidationError):
            bank.commit(session,dict(version=bank.view(session)['version'],request_id=str(uuid4())))
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['spent'],300)
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['balance'],9700)
        transfer_id=get_db().execute('SELECT id FROM budget_account_transfers').fetchone()[0]
        bank.update_row(session,row['id'],dict(version=bank.view(session)['version'],action='MATCH',transfer_id=transfer_id))
        result=bank.commit(session,dict(version=bank.view(session)['version'],request_id=str(uuid4())))
        self.assertEqual((result['linked'],result['created'],result['transfers']),(1,0,0))
        self.assertEqual(monthly_budget_totals(get_db(),'2026-10')['balance'],9700)
