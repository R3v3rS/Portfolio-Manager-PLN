import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1] / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402
from constants import SUBPORTFOLIOS_ALLOWED_TYPES  # noqa: E402
from database import init_db  # noqa: E402


class ConfigEndpointTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'config-endpoint-test.db')

        warmup_patcher = patch('app.PriceService.warmup_cache', return_value=None)
        self.addCleanup(warmup_patcher.stop)
        warmup_patcher.start()

        self.app = create_app()
        self.app.config.update(TESTING=True, DATABASE=self.db_path)
        with self.app.app_context():
            init_db(self.app)

        self.client = self.app.test_client()
        self.addCleanup(self.temp_dir.cleanup)

    def test_config_returns_allowed_subportfolio_types_from_constants(self):
        response = self.client.get('/api/portfolio/config')

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()['payload']
        self.assertEqual(payload['subportfolios_allowed_types'], SUBPORTFOLIOS_ALLOWED_TYPES)


if __name__ == '__main__':
    unittest.main()
