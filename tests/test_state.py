import tempfile
import unittest
from pathlib import Path

from price_monitor.state import StateStore


class StateTests(unittest.TestCase):
    def sample(self, price):
        return {
            "checked_at": "t",
            "status": "OK",
            "price": price,
            "effective_price": price,
            "monitoring_price": price,
            "confidence": "EXACT_SKU_PRICE",
            "source": "test",
            "canonical_sku": "1",
            "provider_stable_id": "stable",
        }

    def test_history_deduplicates_same_logical_sample_and_limits_rows(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(td)
            self.assertTrue(store.append_history("p", self.sample(1), limit=2))
            duplicate = self.sample(1)
            duplicate["checked_at"] = "later"
            self.assertFalse(store.append_history("p", duplicate, limit=2))
            self.assertTrue(store.append_history("p", self.sample(2), limit=2))
            self.assertTrue(store.append_history("p", self.sample(3), limit=2))
            store.save("now")
            loaded = StateStore(td)
            self.assertEqual([2, 3], [x["price"] for x in loaded.history["products"]["p"]])

    def test_source_health_recovers_and_resets_failures(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(td)
            store.update_source_health("maishou", checked_at="t1", ok=False, status="SOURCE_ERROR", error="x")
            store.update_source_health("maishou", checked_at="t2", ok=False, status="SOURCE_ERROR", error="y")
            self.assertEqual(2, store.health["sources"]["maishou"]["consecutive_failures"])
            store.update_source_health("maishou", checked_at="t3", ok=True, status="OK")
            health = store.health["sources"]["maishou"]
            self.assertEqual(0, health["consecutive_failures"])
            self.assertEqual("t3", health["last_success_at"])
            self.assertIsNone(health["last_error"])

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "price_history.json").write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValueError):
                StateStore(td)

    def test_save_without_dirty_state_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(td)
            self.assertEqual([], store.save("now"))
            self.assertFalse(Path(td, "price_status.json").exists())


if __name__ == "__main__":
    unittest.main()
