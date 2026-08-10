import tempfile
import unittest
from pathlib import Path

from price_monitor.config import ConfigError, load_config, monitorable_products


BASE = """
history_limit: 365
products:
  - id: x
    enabled: true
    status: MONITORING
    platform: jd
    source: {provider: maishou}
    match: {required_title_groups: [[x]]}
    shops: {allowed: [x]}
    alert: {enabled: false, target_price: null, significant_drop_pct: null}
"""


class ConfigTests(unittest.TestCase):
    def load_text(self, text):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td, "products.yaml")
            path.write_text(text, encoding="utf-8")
            return load_config(path)

    def test_current_config_valid_and_has_only_supported_platforms(self):
        cfg = load_config("config/products.yaml")
        self.assertEqual({"jd", "taobao"}, {p["platform"] for p in cfg["products"]})
        self.assertEqual(3, len(monitorable_products(cfg)))
        x200s = next(p for p in cfg["products"] if p["id"] == "vivo_x200s_12_512_jd")
        self.assertEqual("lowest_price", x200s["source"]["selection"]["mode"])
        self.assertEqual("12GB+512GB", x200s["variant"]["memory"])
        self.assertEqual({"直白", "淡紫", "薄荷蓝", "简黑"}, set(x200s["variant"]["colors"]))

    def test_rejects_pdd(self):
        with self.assertRaises(ConfigError):
            self.load_text(BASE.replace("platform: jd", "platform: pdd"))

    def test_history_limit_is_sample_count_positive_integer(self):
        with self.assertRaises(ConfigError):
            self.load_text(BASE.replace("history_limit: 365", "history_limit: 0"))

    def test_alert_interface_cannot_be_enabled_yet(self):
        with self.assertRaises(ConfigError):
            self.load_text(BASE.replace("enabled: false, target_price", "enabled: true, target_price"))


if __name__ == "__main__":
    unittest.main()
