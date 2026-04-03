import io

from unittest.mock import patch

from tests.financial_test_utils import FinancialIntegrationTestBase
from portfolio_service import PortfolioService
from database import get_db


class TestIdempotency(FinancialIntegrationTestBase):
    @patch('portfolio_trade_service.PriceService.sync_stock_history', return_value=True)
    @patch('portfolio_trade_service.PriceService.fetch_metadata', return_value={'currency': 'PLN', 'company_name': 'Stub Co', 'sector': 'Tech', 'industry': 'Software'})
    def test_buy_idempotency(self, _meta_mock, _sync_mock):
        parent_id = self.create_parent('Idempotency Parent')

        with self.app.app_context():
            PortfolioService.deposit_cash(parent_id, 5_000.0, date_str='2026-01-02')

        payload = {
            'portfolio_id': parent_id,
            'ticker': 'AAPL',
            'quantity': 10,
            'price': 100,
            'date': '2026-01-03',
            'commission': 0,
            'auto_fx_fees': False,
        }

        first = self.client.post('/api/portfolio/buy', json=payload)
        second = self.client.post('/api/portfolio/buy', json=payload)

        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertEqual(second.status_code, 200, second.get_json())

        with self.app.app_context():
            db = get_db()
            buy_rows = db.execute(
                "SELECT id FROM transactions WHERE portfolio_id = ? AND type = 'BUY' ORDER BY date(date), id",
                (parent_id,),
            ).fetchall()
            holding = db.execute(
                "SELECT quantity FROM holdings WHERE portfolio_id = ? AND ticker = 'AAPL' AND sub_portfolio_id IS NULL",
                (parent_id,),
            ).fetchone()

        # Tier-1 expectation: duplicate retry must not double position.
        self.assertEqual(len(buy_rows), 1)
        self.assertAlmostEqual(float(holding['quantity']), 10.0, places=8)

    @patch('portfolio_import_service.PortfolioImportService.resolve_symbol_mapping')
    def test_import_idempotency(self, mock_resolve_symbol):
        parent_id = self.create_parent('Import Parent')

        class _Mapping:
            ticker = 'AAPL'
            currency = 'PLN'

        mock_resolve_symbol.return_value = _Mapping()

        csv_bytes = (
            'Time,Type,Amount,Comment,Symbol\n'
            '2026-01-02,Deposit,2000,,\n'
            '2026-01-03,Stock purchase,1000,BUY 10 @ 100,AAPL\n'
        ).encode('utf-8')

        response_1 = self.client.post(
            f'/api/portfolio/{parent_id}/import/xtb',
            data={'file': (io.BytesIO(csv_bytes), 'import.csv')},
            content_type='multipart/form-data',
        )
        response_2 = self.client.post(
            f'/api/portfolio/{parent_id}/import/xtb',
            data={'file': (io.BytesIO(csv_bytes), 'import.csv')},
            content_type='multipart/form-data',
        )

        self.assertEqual(response_1.status_code, 200, response_1.get_json())
        self.assertEqual(response_2.status_code, 200, response_2.get_json())

        with self.app.app_context():
            db = get_db()
            tx_rows = db.execute('SELECT type, ticker, quantity, total_value FROM transactions WHERE portfolio_id = ? ORDER BY date(date), id', (parent_id,)).fetchall()
            holdings = db.execute(
                "SELECT quantity, total_cost FROM holdings WHERE portfolio_id = ? AND ticker = 'AAPL' AND sub_portfolio_id IS NULL",
                (parent_id,),
            ).fetchone()

        # Expect exactly one DEPOSIT and one BUY after importing identical file twice.
        self.assertEqual(len(tx_rows), 2)
        self.assertEqual([r['type'] for r in tx_rows], ['DEPOSIT', 'BUY'])
        self.assertAlmostEqual(float(holdings['quantity']), 10.0, places=8)
        self.assertAlmostEqual(float(holdings['total_cost']), 1000.0, places=2)
