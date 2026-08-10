import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from price_monitor.state import StateStore


class PublicStateGuardTests(unittest.TestCase):
    def test_state_writer_redacts_secret_before_disk(self):
        secret = "super-private-key-12345"
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"HAODANKU_API_KEY": secret}, clear=False
        ):
            store = StateStore(td)
            store.set_status(
                "p",
                {
                    "status": "SOURCE_ERROR",
                    "detail": {
                        "error": f"500 for https://x.test/?apikey={secret}&foo=1"
                    },
                },
            )
            store.save("2026-01-01T00:00:00+00:00")
            text = Path(td, "price_status.json").read_text(encoding="utf-8")
            self.assertNotIn(secret, text)
            self.assertIn("apikey=***", text)
            data = json.loads(text)
            self.assertEqual("SOURCE_ERROR", data["products"]["p"]["status"])


if __name__ == "__main__":
    unittest.main()
