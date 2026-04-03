import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from portfolio_history_service import PortfolioHistoryService  # noqa: E402


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


if __name__ == '__main__':
    unittest.main()
