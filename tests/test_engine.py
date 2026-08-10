import tempfile
import unittest

from price_monitor.engine import MonitorEngine
from price_monitor.models import PriceConfidence, Quote
from price_monitor.state import StateStore


class FixedSource:
    def __init__(self, quote=None, error=None):
        self.quote = quote
        self.error = error

    def fetch(self, product):
        if self.error:
            raise self.error
        return self.quote


def product(product_id, platform, provider):
    return {
        "id": product_id,
        "enabled": True,
        "status": "MONITORING",
        "platform": platform,
        "source": {"provider": provider},
        "alert": {"enabled": False, "target_price": None, "significant_drop_pct": None},
    }


def quote(product_id, platform, price, source="fake"):
    return Quote(
        product_id=product_id,
        platform=platform,
        status="OK",
        source=source,
        checked_at="t",
        price=price,
        effective_price=price,
        confidence=PriceConfidence.EXACT_SKU_PRICE.value,
        canonical_sku="sku" if platform == "jd" else None,
    )


class EngineTests(unittest.TestCase):
    def test_large_price_drop_is_persisted(self):
        config = {"history_limit": 10, "products": [product("x", "jd", "maishou")]}
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(td)
            MonitorEngine(config, store, sources={"jd": FixedSource(quote("x", "jd", 100))}).run(now="2026-01-01T00:00:00+00:00")
            MonitorEngine(config, store, sources={"jd": FixedSource(quote("x", "jd", 10))}).run(now="2026-01-01T01:00:00+00:00")
            self.assertEqual([100, 10], [x["monitoring_price"] for x in store.history["products"]["x"]])

    def test_same_price_does_not_duplicate_history(self):
        config = {"history_limit": 10, "products": [product("x", "jd", "maishou")]}
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(td)
            src = FixedSource(quote("x", "jd", 80))
            MonitorEngine(config, store, sources={"jd": src}).run(now="2026-01-01T00:00:00+00:00")
            MonitorEngine(config, store, sources={"jd": src}).run(now="2026-01-01T01:00:00+00:00")
            self.assertEqual(1, len(store.history["products"]["x"]))
            self.assertEqual("2026-01-01T01:00:00+00:00", store.status["products"]["x"]["last_checked_at"])

    def test_one_platform_failure_does_not_block_other_platform(self):
        config = {"history_limit": 10, "products": [product("j", "jd", "maishou"), product("t", "taobao", "haodanku")]}
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(td)
            result = MonitorEngine(
                config,
                store,
                sources={
                    "jd": FixedSource(error=RuntimeError("down")),
                    "taobao": FixedSource(quote("t", "taobao", 108, source="haodanku")),
                },
            ).run(now="2026-01-01T00:00:00+00:00")
            self.assertEqual("SOURCE_ERROR", result["products"]["j"]["status"])
            self.assertEqual("OK", result["products"]["t"]["status"])
            self.assertNotIn("j", store.history.get("products", {}))
            self.assertEqual(1, len(store.history["products"]["t"]))

    def test_both_platform_failures_are_recorded_without_history(self):
        config = {"history_limit": 10, "products": [product("j", "jd", "maishou"), product("t", "taobao", "haodanku")]}
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(td)
            result = MonitorEngine(
                config,
                store,
                sources={"jd": FixedSource(error=RuntimeError("j")), "taobao": FixedSource(error=RuntimeError("t"))},
            ).run(now="2026-01-01T00:00:00+00:00")
            self.assertEqual("SOURCE_ERROR", result["products"]["j"]["status"])
            self.assertEqual("SOURCE_ERROR", result["products"]["t"]["status"])
            self.assertEqual({}, store.history.get("products", {}))
            self.assertEqual(1, store.health["sources"]["maishou"]["consecutive_failures"])
            self.assertEqual(1, store.health["sources"]["haodanku"]["consecutive_failures"])


if __name__ == "__main__":
    unittest.main()
