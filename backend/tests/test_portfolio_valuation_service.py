import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from portfolio_valuation_service import PortfolioValuationService  # noqa: E402


class PortfolioValuationCashDeltaTestCase(unittest.TestCase):
    def test_cash_delta_transfer_is_neutral(self):
        tx = {'type': 'TRANSFER', 'total_value': 123.45}
        self.assertEqual(PortfolioValuationService.cash_delta(tx), 0.0)


if __name__ == '__main__':
    unittest.main()
