import sys
import unittest
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from portfolio_import_service import PortfolioImportService  # noqa: E402


class PortfolioImportServiceHelpersTestCase(unittest.TestCase):
    def test_try_parse_float_supports_common_import_formats(self):
        self.assertEqual(PortfolioImportService._try_parse_float('123.45'), 123.45)
        self.assertEqual(PortfolioImportService._try_parse_float('1 234,56'), 1234.56)
        self.assertIsNone(PortfolioImportService._try_parse_float('2026-03-31 08:42:24'))

    def test_select_column_prefers_numeric_candidate_for_amount(self):
        df = pd.DataFrame(
            {
                'Amount': ['2026-03-31 08:42:24', '2026-03-31 09:00:00'],
                'Profit': ['12,50', '-2,00'],
            }
        )
        normalized_columns = {str(col).strip().lower(): col for col in df.columns}

        selected = PortfolioImportService._select_column(
            normalized_columns,
            ['amount', 'profit'],
            df=df,
            numeric_preferred=True,
        )

        self.assertEqual(selected, 'Profit')

    def test_parse_xtb_quantity_standard_format(self):
        qty = PortfolioImportService._parse_xtb_quantity('OPEN BUY 0.0089 @ 32.660', 1)
        self.assertEqual(qty, 0.0089)

    def test_parse_xtb_quantity_fractional_close_uses_numerator_only(self):
        qty = PortfolioImportService._parse_xtb_quantity('CLOSE BUY 1/5 @ 35.000', 2)
        self.assertEqual(qty, 1.0)

    def test_parse_xtb_quantity_handles_spaces_and_commas(self):
        qty = PortfolioImportService._parse_xtb_quantity(' CLOSE  BUY   1,25 / 10 @ 35,000 ', 3)
        self.assertEqual(qty, 1.25)

    def test_parse_xtb_quantity_raises_for_invalid_comment(self):
        with self.assertRaisesRegex(ValueError, 'Could not parse quantity'):
            PortfolioImportService._parse_xtb_quantity('OPEN BUY @ 32.660', 4)


if __name__ == '__main__':
    unittest.main()
