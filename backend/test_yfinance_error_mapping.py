import unittest
import sys
from pathlib import Path

import requests

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from integrations.yfinance_error_mapping import (
    UpstreamErrorCode,
    UpstreamErrorContext,
    build_yfinance_error,
    classify_yfinance_error,
)


class YfinanceErrorMappingTestCase(unittest.TestCase):
    def setUp(self):
        self.context = UpstreamErrorContext(
            provider='yfinance',
            symbol='AAPL',
            interval='1d',
            operation='download_prices',
        )

    def test_classifies_network_timeout(self):
        code = classify_yfinance_error(requests.ReadTimeout('request timed out'), self.context)
        self.assertEqual(code, UpstreamErrorCode.NETWORK_TIMEOUT)

    def test_classifies_rate_limit_from_message(self):
        code = classify_yfinance_error(Exception('Too many requests: rate limit exceeded'), self.context)
        self.assertEqual(code, UpstreamErrorCode.RATE_LIMIT)

    def test_classifies_symbol_not_found(self):
        code = classify_yfinance_error(Exception('No timezone found, symbol may be delisted'), self.context)
        self.assertEqual(code, UpstreamErrorCode.SYMBOL_NOT_FOUND)

    def test_build_error_returns_code_and_messages(self):
        classified = build_yfinance_error(Exception('unexpected format in upstream payload'), self.context)

        self.assertEqual(classified.code, UpstreamErrorCode.UPSTREAM_SCHEMA_CHANGE)
        self.assertTrue(classified.user_message)
        self.assertIn('provider=yfinance', classified.technical_message)
        self.assertIn('code=UPSTREAM_SCHEMA_CHANGE', classified.technical_message)


if __name__ == '__main__':
    unittest.main()
