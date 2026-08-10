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
    alert: {anomaly_drop_pct: 0.25}
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "products.yaml"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
