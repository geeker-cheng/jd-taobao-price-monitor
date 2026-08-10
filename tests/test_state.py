import tempfile
import unittest

from price_monitor.state import StateStore


class StateTests(unittest.TestCase):
    def test_round_trip_and_history_limit(self):
        with tempfile.TemporaryDirectory() as td:
            store = StateStore(td)
            store.set_status("p", {"status": "OK"})
            store.append_history("p", {"price": 1}, limit=2)
            store.append_history("p", {"price": 2}, limit=2)
            store.append_history("p", {"price": 3}, limit=2)
            store.product_alert_state("p")["target_armed"] = False
            store.save("now")

            loaded = StateStore(td)
            self.assertEqual("OK", loaded.status["products"]["p"]["status"])
            self.assertEqual([2, 3], [x["price"] for x in loaded.history["products"]["p"]])
            self.assertFalse(loaded.alert["products"]["p"]["target_armed"])


if __name__ == "__main__":
    unittest.main()
