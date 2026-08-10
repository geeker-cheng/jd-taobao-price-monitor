import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from price_monitor.security import redact_text, sanitize_data, scan_state_directory


class SecurityTests(unittest.TestCase):
    def test_redacts_env_secret_and_sensitive_query_parameter(self):
        secret = "haodanku-secret-123"
        with patch.dict(os.environ, {"HAODANKU_API_KEY": secret}, clear=False):
            text = f"500 error for https://example.test/path?apikey={secret}&x=1"
            redacted = redact_text(text)
            self.assertNotIn(secret, redacted)
            self.assertIn("apikey=***", redacted)

    def test_nested_sensitive_fields_are_masked(self):
        value = {
            "error": "https://x.test/?token=abcdef",
            "response": {"authorization": "Bearer abcdef", "inviteCode": "private-code"},
        }
        safe = sanitize_data(value)
        self.assertEqual("***", safe["response"]["authorization"])
        self.assertEqual("***", safe["response"]["inviteCode"])
        self.assertIn("token=***", safe["error"])

    def test_state_scan_reports_only_filename_not_secret(self):
        secret = "secret-value-987"
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"HAODANKU_API_KEY": secret}, clear=False
        ):
            path = Path(td, "price_status.json")
            path.write_text(
                json.dumps({"error": f"https://x.test/?apikey={secret}"}),
                encoding="utf-8",
            )
            issues = scan_state_directory(td)
            self.assertEqual(["price_status.json"], issues)
            self.assertNotIn(secret, repr(issues))


if __name__ == "__main__":
    unittest.main()
