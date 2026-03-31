import sys
import unittest
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent
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


if __name__ == '__main__':
    unittest.main()
