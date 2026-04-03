import sys
import unittest
from datetime import date, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from math_utils import xirr  # noqa: E402


class XirrRegressionTests(unittest.TestCase):
    def test_mixed_date_and_datetime(self):
        txns = [
            (date(2020, 1, 1), -1000),
            (datetime(2021, 1, 1, 12, 0), 1100),
        ]

        result = xirr(txns)
        self.assertIsInstance(result, float)


if __name__ == "__main__":
    unittest.main()
