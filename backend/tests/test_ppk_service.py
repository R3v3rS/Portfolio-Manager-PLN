import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from modules.ppk.ppk_service import PPKService  # noqa: E402


class PPKServiceParsingTestCase(unittest.TestCase):
    def test_parse_biznesradar_history_maps_polish_date_and_decimal(self):
        html = """
        <table>
          <tr><td>14.04.2026</td><td>20,15</td></tr>
          <tr><td>13.04.2026</td><td>20.03</td></tr>
        </table>
        """

        parsed = PPKService._parse_biznesradar_history(html)

        self.assertEqual(
            parsed,
            [
                {'date': '2026-04-14', 'price': 20.15},
                {'date': '2026-04-13', 'price': 20.03},
            ],
        )


if __name__ == '__main__':
    unittest.main()
