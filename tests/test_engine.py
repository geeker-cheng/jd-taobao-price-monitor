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
    def test_engine_persists_valid_quote(self):
        config = {
            "history_limit": 10,
            "products": [
                {
                    "id": "x",
                    "enabled": True,
                    "status": "MONITORING",
                    "platform": "jd",
                    "alert": {
                        "target_price": None,
                        "significant_drop_pct": None,
                        "anomaly_drop_pct": 0.25,
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
            price=80,
            effective_price=80,
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
            self.assertEqual(1, len(store.history["products"]["x"]))


if __name__ == "__main__":
    unittest.main()
