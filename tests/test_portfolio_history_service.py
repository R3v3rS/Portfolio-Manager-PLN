import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import date, timedelta
from time import perf_counter

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from portfolio_history_service import PortfolioHistoryService  # noqa: E402
from portfolio_trade_service import PortfolioTradeService  # noqa: E402


class PortfolioHistoryServiceLoggingTestCase(unittest.TestCase):
    @patch('portfolio_history_service.logger.exception')
    @patch('builtins.print')
    @patch('portfolio_history_service.PriceService.fetch_metadata', return_value={'currency': 'USD'})
    @patch('portfolio_history_service.PriceService.get_tickers_requiring_history_sync', return_value=['AAPL', 'MSFT'])
    @patch('portfolio_history_service.PriceService.sync_stock_history')
    @patch('portfolio_history_service.get_db')
    def test_build_price_context_logs_sync_errors_and_continues(
        self,
        mock_get_db,
        mock_sync_stock_history,
        _mock_get_tickers_requiring_sync,
        _mock_fetch_metadata,
        mock_print,
        mock_logger_exception,
    ):
        db = MagicMock()
        mock_get_db.return_value = db

        empty_rows = MagicMock()
        empty_rows.fetchall.return_value = []
        db.execute.return_value = empty_rows

        mock_sync_stock_history.side_effect = [Exception('network down'), None]

        PortfolioHistoryService._build_price_context(
            portfolio_id=1,
            tickers={'AAPL', 'MSFT'},
            start_date='2026-01-01',
            account_type='STANDARD',
            benchmark_ticker=None,
        )

        self.assertEqual(mock_sync_stock_history.call_count, 2)
        mock_print.assert_not_called()
        mock_logger_exception.assert_called_once()

        call_args, _call_kwargs = mock_logger_exception.call_args
        self.assertEqual(call_args[0], "Failed to sync history for %s: %s")
        self.assertEqual(call_args[1], 'AAPL')
        self.assertEqual(str(call_args[2]), 'network down')


class PortfolioHistoryServiceRollingParityTestCase(unittest.TestCase):
    def _legacy_daily(self, transactions, price_history, ticker_currency, days, account_type, live_value):
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        date_points = [start_date + timedelta(days=offset) for offset in range(days)]

        def get_price_at_date(ticker, target_date):
            target_str = target_date.strftime('%Y-%m-%d')
            if ticker not in price_history or not price_history[ticker]:
                return 0
            if target_str in price_history[ticker]:
                return price_history[ticker][target_str]
            past_dates = [d for d in price_history[ticker].keys() if d <= target_str]
            if past_dates:
                return price_history[ticker][max(past_dates)]
            return 0

        result = []
        for point_date in date_points:
            current_cash = 0.0
            invested_capital = 0.0
            holdings_qty = {}
            for t in transactions:
                t_date = date.fromisoformat(str(t['date']).split(' ')[0].split('T')[0])
                if t_date > point_date:
                    continue
                t_val = float(t['total_value'])
                t_qty = float(t['quantity'])
                t_ticker = t['ticker']
                if t['type'] in ['DEPOSIT', 'SELL', 'DIVIDEND', 'INTEREST']:
                    current_cash += t_val
                elif t['type'] in ['WITHDRAW', 'BUY']:
                    current_cash -= t_val
                if t['type'] == 'DEPOSIT':
                    invested_capital += t_val
                elif t['type'] == 'WITHDRAW':
                    invested_capital -= t_val
                if t_ticker != 'CASH':
                    if t['type'] == 'BUY':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) + t_qty
                    elif t['type'] == 'SELL':
                        holdings_qty[t_ticker] = holdings_qty.get(t_ticker, 0.0) - t_qty
            total_value = current_cash
            if account_type not in ['SAVINGS', 'BONDS']:
                for ticker, qty in holdings_qty.items():
                    if qty > 0.0001:
                        native_price = get_price_at_date(ticker, point_date)
                        currency = ticker_currency.get(ticker, 'PLN')
                        fx_rate = 1.0 if currency == 'PLN' else get_price_at_date(f"{currency}PLN=X", point_date)
                        if fx_rate <= 0:
                            fx_rate = 1.0
                        gross_value_pln = qty * native_price * fx_rate
                        net_value_pln = gross_value_pln - PortfolioTradeService._calculate_fx_fee(gross_value_pln, currency)
                        total_value += net_value_pln
            if point_date == end_date and live_value:
                total_value = float(live_value.get('portfolio_value', total_value))
                live_invested = live_value.get('invested_capital') or live_value.get('net_contributions')
                if live_invested is not None:
                    invested_capital = float(live_invested)
            result.append(round(total_value - invested_capital, 2))
        return result

    @patch('portfolio_history_service.date')
    @patch('portfolio_history_service.PortfolioValuationService.get_portfolio_value')
    @patch('portfolio_history_service.PortfolioHistoryService._build_price_context')
    @patch('portfolio_history_service.get_db')
    def test_daily_history_matches_legacy_algorithm(
        self,
        mock_get_db,
        mock_build_price_context,
        mock_live_value,
        mock_date,
    ):
        fixed_today = date(2026, 4, 3)
        mock_date.today.return_value = fixed_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        transactions = [
            {'ticker': 'CASH', 'type': 'DEPOSIT', 'quantity': 0, 'total_value': 10000, 'date': '2026-03-28'},
            {'ticker': 'AAPL', 'type': 'BUY', 'quantity': 10, 'total_value': 5000, 'date': '2026-03-29'},
            {'ticker': 'AAPL', 'type': 'SELL', 'quantity': 2, 'total_value': 1200, 'date': '2026-03-31'},
            {'ticker': 'CASH', 'type': 'DIVIDEND', 'quantity': 0, 'total_value': 100, 'date': '2026-04-01'},
            {'ticker': 'CASH', 'type': 'WITHDRAW', 'quantity': 0, 'total_value': 300, 'date': '2026-04-02'},
        ]

        portfolio_row = {'id': 1, 'account_type': 'STANDARD', 'parent_portfolio_id': None}
        db = MagicMock()
        mock_get_db.return_value = db

        portfolio_cursor = MagicMock()
        portfolio_cursor.fetchone.return_value = portfolio_row
        tx_cursor = MagicMock()
        tx_cursor.fetchall.return_value = transactions
        db.execute.side_effect = [portfolio_cursor, tx_cursor]

        prices = {
            'AAPL': {
                '2026-03-29': 500,
                '2026-03-31': 600,
                '2026-04-03': 590,
            },
            'USDPLN=X': {
                '2026-03-29': 4.0,
                '2026-03-31': 4.1,
                '2026-04-03': 4.05,
            },
        }
        ticker_currency = {'AAPL': 'USD'}
        mock_build_price_context.return_value = (ticker_currency, prices)
        live_value = {'portfolio_value': 25200, 'net_contributions': 9700}
        mock_live_value.return_value = live_value

        expected = self._legacy_daily(transactions, prices, ticker_currency, 7, 'STANDARD', live_value)
        actual = PortfolioHistoryService.get_portfolio_profit_history_daily(1, days=7, metric='profit')
        self.assertEqual(expected, [row['value'] for row in actual])

    @patch('portfolio_history_service.date')
    @patch('portfolio_history_service.PortfolioValuationService.get_portfolio_value', return_value=None)
    @patch('portfolio_history_service.InflationService.get_inflation_series')
    @patch('portfolio_history_service.PortfolioHistoryService._build_price_context')
    @patch('portfolio_history_service.get_db')
    def test_monthly_history_rolling_matches_legacy_invariants(
        self,
        mock_get_db,
        mock_build_price_context,
        mock_inflation_series,
        _mock_live_value,
        mock_date,
    ):
        fixed_today = date(2026, 4, 3)
        mock_date.today.return_value = fixed_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        portfolio_row = {'id': 1, 'account_type': 'STANDARD', 'created_at': '2026-01-01', 'parent_portfolio_id': None}
        transactions = [
            {'ticker': 'CASH', 'type': 'DEPOSIT', 'quantity': 0, 'total_value': 1000, 'date': '2026-01-10'},
            {'ticker': 'AAA', 'type': 'BUY', 'quantity': 2, 'total_value': 400, 'date': '2026-01-12'},
            {'ticker': 'CASH', 'type': 'DEPOSIT', 'quantity': 0, 'total_value': 500, 'date': '2026-02-04'},
            {'ticker': 'AAA', 'type': 'SELL', 'quantity': 1, 'total_value': 250, 'date': '2026-02-20'},
        ]

        db = MagicMock()
        mock_get_db.return_value = db
        p_cur = MagicMock()
        p_cur.fetchone.return_value = portfolio_row
        t_cur = MagicMock()
        t_cur.fetchall.return_value = transactions
        db.execute.side_effect = [p_cur, t_cur]

        mock_build_price_context.return_value = (
            {'AAA': 'PLN'},
            {'AAA': {'2026-01-31': 220, '2026-02-28': 240, '2026-04-03': 250}},
        )
        mock_inflation_series.return_value = [
            {'date': '2026-01', 'index_value': 100.0},
            {'date': '2026-02', 'index_value': 101.0},
            {'date': '2026-03', 'index_value': 102.0},
            {'date': '2026-04', 'index_value': 103.0},
        ]
        PortfolioHistoryService.clear_cache(1)
        monthly = PortfolioHistoryService._calculate_historical_metrics(1, benchmark_ticker='__INFLATION__')
        self.assertEqual(sorted(monthly.keys()), ['2026-01', '2026-02', '2026-03', '2026-04'])
        self.assertAlmostEqual(monthly['2026-02']['net_contributions'], 1500.0)
        self.assertIn('benchmark_inflation_value', monthly['2026-04'])

    def test_benchmark_shows_operation_reduction(self):
        points = 365
        tx_count = 500
        legacy_ops = points * tx_count
        rolling_ops = points + tx_count
        print(f"ops_before={legacy_ops} ops_after={rolling_ops}")
        self.assertLess(rolling_ops, legacy_ops)

        transactions = []
        start = date(2025, 1, 1)
        for i in range(tx_count):
            transactions.append({
                'ticker': 'CASH',
                'type': 'DEPOSIT',
                'quantity': 0.0,
                'total_value': 10.0,
                'date': (start + timedelta(days=i % points)).isoformat(),
            })
        price_index = PortfolioHistoryService._build_sorted_price_index({})
        date_points = [start + timedelta(days=i) for i in range(points)]

        legacy_start = perf_counter()
        for point in date_points:
            _cash = 0.0
            for t in transactions:
                if date.fromisoformat(t['date']) <= point:
                    _cash += t['total_value']
        legacy_elapsed = perf_counter() - legacy_start

        rolling_start = perf_counter()
        tx_idx = 0
        ordered = sorted(transactions, key=lambda x: x['date'])
        _cash = 0.0
        cache = {}
        for point in date_points:
            while tx_idx < len(ordered) and date.fromisoformat(ordered[tx_idx]['date']) <= point:
                _cash += ordered[tx_idx]['total_value']
                tx_idx += 1
            _ = PortfolioHistoryService._price_at(price_index, 'NONE', point, cache)
        rolling_elapsed = perf_counter() - rolling_start
        print(f"time_before={legacy_elapsed:.6f}s time_after={rolling_elapsed:.6f}s")

        self.assertLess(rolling_elapsed, legacy_elapsed)

    @patch('portfolio_history_service.date')
    @patch('portfolio_history_service.PortfolioValuationService.get_portfolio_value', return_value=None)
    @patch('portfolio_history_service.PortfolioHistoryService._build_price_context')
    @patch('portfolio_history_service.get_db')
    def test_long_sparse_daily_history(self, mock_get_db, mock_build_price_context, _mock_live, mock_date):
        fixed_today = date(2026, 4, 3)
        mock_date.today.return_value = fixed_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        portfolio_row = {'id': 11, 'account_type': 'STANDARD', 'parent_portfolio_id': None}
        transactions = [{'id': 1, 'ticker': 'CASH', 'type': 'DEPOSIT', 'quantity': 0, 'total_value': 1000, 'date': '2023-01-01'}]
        db = MagicMock()
        mock_get_db.return_value = db
        p_cur = MagicMock(); p_cur.fetchone.return_value = portfolio_row
        t_cur = MagicMock(); t_cur.fetchall.return_value = transactions
        db.execute.side_effect = [p_cur, t_cur]
        mock_build_price_context.return_value = ({}, {})

        data = PortfolioHistoryService.get_portfolio_profit_history_daily(11, days=365, metric='value')
        self.assertEqual(len(data), 365)
        self.assertTrue(all(item['value'] == 1000 for item in data))

    @patch('portfolio_history_service.date')
    @patch('portfolio_history_service.PortfolioValuationService.get_portfolio_value', return_value=None)
    @patch('portfolio_history_service.PortfolioHistoryService._build_price_context')
    @patch('portfolio_history_service.get_db')
    def test_multi_ticker_daily_runs_and_returns_points(self, mock_get_db, mock_build_price_context, _mock_live, mock_date):
        fixed_today = date(2026, 4, 3)
        mock_date.today.return_value = fixed_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        portfolio_row = {'id': 12, 'account_type': 'STANDARD', 'parent_portfolio_id': None}
        tickers = [f"T{i}" for i in range(25)]
        transactions = [{'id': 1, 'ticker': 'CASH', 'type': 'DEPOSIT', 'quantity': 0, 'total_value': 50000, 'date': '2026-01-01'}]
        tx_id = 2
        for i, ticker in enumerate(tickers):
            transactions.append({'id': tx_id, 'ticker': ticker, 'type': 'BUY', 'quantity': 1, 'total_value': 100 + i, 'date': '2026-01-02'})
            tx_id += 1
        db = MagicMock()
        mock_get_db.return_value = db
        p_cur = MagicMock(); p_cur.fetchone.return_value = portfolio_row
        t_cur = MagicMock(); t_cur.fetchall.return_value = transactions
        db.execute.side_effect = [p_cur, t_cur]
        price_history = {ticker: {'2026-01-02': 100 + i, '2026-04-03': 110 + i} for i, ticker in enumerate(tickers)}
        mock_build_price_context.return_value = ({ticker: 'PLN' for ticker in tickers}, price_history)

        data = PortfolioHistoryService.get_portfolio_profit_history_daily(12, days=90, metric='value')
        self.assertEqual(len(data), 90)
        self.assertGreater(data[-1]['value'], data[0]['value'])

    @patch('portfolio_history_service.date')
    @patch('portfolio_history_service.PortfolioValuationService.get_portfolio_value', return_value=None)
    @patch('portfolio_history_service.PortfolioHistoryService._build_price_context')
    @patch('portfolio_history_service.get_db')
    def test_fx_consistency_uses_latest_rate_without_future_leakage(self, mock_get_db, mock_build_price_context, _mock_live, mock_date):
        fixed_today = date(2026, 4, 3)
        mock_date.today.return_value = fixed_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        portfolio_row = {'id': 13, 'account_type': 'STANDARD', 'parent_portfolio_id': None}
        transactions = [
            {'id': 1, 'ticker': 'CASH', 'type': 'DEPOSIT', 'quantity': 0, 'total_value': 1000, 'date': '2026-03-25'},
            {'id': 2, 'ticker': 'ABC', 'type': 'BUY', 'quantity': 1, 'total_value': 1000, 'date': '2026-03-25'},
        ]
        db = MagicMock()
        mock_get_db.return_value = db
        p_cur = MagicMock(); p_cur.fetchone.return_value = portfolio_row
        t_cur = MagicMock(); t_cur.fetchall.return_value = transactions
        db.execute.side_effect = [p_cur, t_cur]
        price_history = {
            'ABC': {'2026-03-25': 100, '2026-04-03': 100},
            'USDPLN=X': {'2026-03-25': 4.0, '2026-03-30': 4.2, '2026-04-03': 4.1},
        }
        mock_build_price_context.return_value = ({'ABC': 'USD'}, price_history)
        data = PortfolioHistoryService.get_portfolio_profit_history_daily(13, days=10, metric='value')
        day_2026_03_29 = [x for x in data if x['date'] == '2026-03-29'][0]
        day_2026_03_31 = [x for x in data if x['date'] == '2026-03-31'][0]
        expected_29 = 100 * 4.0 - PortfolioTradeService._calculate_fx_fee(100 * 4.0, 'USD')
        expected_31 = 100 * 4.2 - PortfolioTradeService._calculate_fx_fee(100 * 4.2, 'USD')
        self.assertAlmostEqual(day_2026_03_29['value'], expected_29, places=2)
        self.assertAlmostEqual(day_2026_03_31['value'], expected_31, places=2)

    @patch('portfolio_history_service.date')
    @patch('portfolio_history_service.PortfolioValuationService.get_portfolio_value', return_value=None)
    @patch('portfolio_history_service.PortfolioHistoryService._build_price_context')
    @patch('portfolio_history_service.get_db')
    def test_buy_before_window_sell_inside_window(self, mock_get_db, mock_build_price_context, _mock_live, mock_date):
        fixed_today = date(2026, 4, 3)
        mock_date.today.return_value = fixed_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
        portfolio_row = {'id': 14, 'account_type': 'STANDARD', 'parent_portfolio_id': None}
        transactions = [
            {'id': 1, 'ticker': 'CASH', 'type': 'DEPOSIT', 'quantity': 0, 'total_value': 1000, 'date': '2026-03-15'},
            {'id': 2, 'ticker': 'AAA', 'type': 'BUY', 'quantity': 10, 'total_value': 500, 'date': '2026-03-16'},
            {'id': 3, 'ticker': 'AAA', 'type': 'SELL', 'quantity': 4, 'total_value': 240, 'date': '2026-04-01'},
        ]
        db = MagicMock()
        mock_get_db.return_value = db
        p_cur = MagicMock(); p_cur.fetchone.return_value = portfolio_row
        t_cur = MagicMock(); t_cur.fetchall.return_value = transactions
        db.execute.side_effect = [p_cur, t_cur]
        mock_build_price_context.return_value = ({'AAA': 'PLN'}, {'AAA': {'2026-03-31': 60, '2026-04-03': 60}})
        data = PortfolioHistoryService.get_portfolio_profit_history_daily(14, days=7, metric='value')
        before_sell = [x for x in data if x['date'] == '2026-03-31'][0]
        after_sell = [x for x in data if x['date'] == '2026-04-01'][0]
        self.assertAlmostEqual(before_sell['value'], 1100.0, places=2)
        self.assertAlmostEqual(after_sell['value'], 1100.0, places=2)


if __name__ == '__main__':
    unittest.main()
