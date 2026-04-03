import sys
import unittest
from datetime import date, datetime
from pathlib import Path

import pytest

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


def test_amount_nan():
    with pytest.raises(TypeError):
        xirr([(date(2020, 1, 1), float("nan")), (date(2021, 1, 1), 100)])


def test_amount_inf():
    with pytest.raises(TypeError):
        xirr([(date(2020, 1, 1), float("inf")), (date(2021, 1, 1), 100)])


def test_guess_nan():
    with pytest.raises(TypeError):
        xirr([(date(2020, 1, 1), -100), (date(2021, 1, 1), 200)], guess=float("nan"))


def test_guess_bool():
    with pytest.raises(TypeError):
        xirr([(date(2020, 1, 1), -100), (date(2021, 1, 1), 200)], guess=True)


if __name__ == "__main__":
    unittest.main()
