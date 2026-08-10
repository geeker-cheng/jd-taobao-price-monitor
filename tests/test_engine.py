import tempfile
import unittest

from price_monitor.engine import MonitorEngine
from price_monitor.models import PriceConfidence, Quote
from price_monitor.state import StateStore


class FixedSource:
    def __init__(self, quote):
        self.quote = quote

    def fetch(self, product):
        return self.quote


class EngineTests(unittest.TestCase):
    def test_engine_persists_valid_quote_without_alert_evaluation(self):
        config = {
            "history_limit": 10,
            "products": [
                {
                    "id": "x",
                    "enabled": True,
                    "status": "MONITORING",
                    "platform": "jd",
                    "alert": {
                        "enabled": False,
                        "target_price": 100,
                        "significant_drop_pct": 0.01,
                    },
                }
            ],
        }
        q = Quote(
            product_id="x",
            platform="jd",
            status="OK",
            source="fake",
            checked_at="t",
            price=10,
            effective_price=10,
            confidence=PriceConfidence.EXACT_SKU_PRICE.value,
        )
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(td)
            result = MonitorEngine(
                config,
                store,
                sources={"jd": FixedSource(q)},
            ).run(now="t")
            self.assertEqual("OK", result["products"]["x"]["status"])
            self.assertTrue(result["products"]["x"]["accepted_sample"])
            self.assertEqual([], result["products"]["x"]["events"])
            self.assertEqual([], result["events"])
            self.assertEqual(1, len(store.history["products"]["x"]))
            self.assertEqual({}, store.alert["products"]["x"])


if __name__ == "__main__":
    unittest.main()
