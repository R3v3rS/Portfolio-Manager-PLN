import io
import unittest

from routes_imports import _read_import_dataframe


class ImportFileParsingTestCase(unittest.TestCase):
    def test_read_import_dataframe_detects_tab_delimiter(self):
        content = (
            'Type\tSymbol\tInstrument\tTime\tAmount\tID\tComment\tProduct\n'
            'Stock sell\tDNP.PL\tDino\t2026-03-31 08:42:24\t1,28\t1200224326\tCLOSE BUY 0.0392/0.0951 @ 32.700\tIKE\n'
        )

        df = _read_import_dataframe(io.BytesIO(content.encode('utf-8')))

        self.assertEqual(df.columns.tolist(), ['Type', 'Symbol', 'Instrument', 'Time', 'Amount', 'ID', 'Comment', 'Product'])
        self.assertEqual(df.iloc[0]['Type'], 'Stock sell')
        self.assertEqual(df.iloc[0]['Time'], '2026-03-31 08:42:24')
        self.assertEqual(df.iloc[0]['Amount'], '1,28')

    def test_read_import_dataframe_supports_comma_delimiter(self):
        content = (
            'Type,Time,Amount,Comment\n'
            'Deposit,2026-03-31 08:42:24,12.50,Monthly top-up\n'
        )

        df = _read_import_dataframe(io.BytesIO(content.encode('utf-8')))

        self.assertEqual(df.columns.tolist(), ['Type', 'Time', 'Amount', 'Comment'])
        self.assertEqual(df.iloc[0]['Amount'], '12.50')


if __name__ == '__main__':
    unittest.main()
