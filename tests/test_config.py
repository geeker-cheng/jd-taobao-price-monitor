import tempfile
import unittest
from pathlib import Path

from price_monitor.config import ConfigError, load_config, monitorable_products


class ConfigTests(unittest.TestCase):
    def test_current_config_valid_and_has_only_supported_platforms(self):
        cfg = load_config("config/products.yaml")
        self.assertEqual({"jd", "taobao"}, {p["platform"] for p in cfg["products"]})
        self.assertEqual(2, len(monitorable_products(cfg)))

    def test_rejects_pdd(self):
        text = """
products:
  - id: x
    enabled: true
    status: MONITORING
    platform: pdd
    source: {provider: anything}
    match: {required_title_groups: [[x]]}
    shops: {allowed: [x]}
    alert: {enabled: false}
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "products.yaml"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_reserved_alert_interface_accepts_null_threshold_fields(self):
        cfg = load_config("config/products.yaml")
        for product in cfg["products"]:
            self.assertFalse(product["alert"]["enabled"])
            self.assertIsNone(product["alert"]["target_price"])
            self.assertIsNone(product["alert"]["significant_drop_pct"])
            self.assertNotIn("anomaly_drop_pct", product["alert"])


if __name__ == "__main__":
    unittest.main()
