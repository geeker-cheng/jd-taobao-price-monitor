import unittest

from price_monitor.alerts import evaluate_quote
from price_monitor.models import PriceConfidence, Quote


def product(target=None, significant=None, anomaly=0.25, allow_page=False):
    return {
        "id": "p",
        "alert": {
            "target_price": target,
            "significant_drop_pct": significant,
            "anomaly_drop_pct": anomaly,
            "allow_product_page_alerts": allow_page,
        },
    }


def quote(price, confidence=PriceConfidence.EXACT_SKU_PRICE.value):
    return Quote(
        product_id="p",
        platform="jd",
        status="OK",
        source="test",
        checked_at="t",
        price=price,
        effective_price=price,
        confidence=confidence,
    )


class AlertTests(unittest.TestCase):
    def test_gradual_drop_uses_reference_not_last_sample(self):
        p = product(significant=0.08, anomaly=0.25)
        state = {
            "target_armed": True,
            "last_valid_price": None,
            "reference_price": None,
        }
        all_events = []
        for value in (1000, 970, 940, 910):
            q, events, accepted = evaluate_quote(p, quote(value), state, now="t")
            self.assertTrue(accepted)
            all_events.extend(events)
        sig = [x for x in all_events if x.event_type == "SIGNIFICANT_DROP"]
        self.assertEqual(1, len(sig))
        self.assertAlmostEqual(0.09, sig[0].drop_pct)

    def test_target_fires_once_and_rearms_after_rise(self):
        p = product(target=80)
        state = {
            "target_armed": True,
            "last_valid_price": None,
            "reference_price": None,
        }
        events = []
        for value in (90, 79, 75, 85, 78):
            _, current, _ = evaluate_quote(p, quote(value), state, now="t")
            events.extend(current)
        target = [x for x in events if x.event_type == "TARGET_REACHED"]
        self.assertEqual(2, len(target))

    def test_anomaly_is_rejected_and_does_not_move_baseline(self):
        p = product(anomaly=0.25)
        state = {
            "target_armed": True,
            "last_valid_price": 100.0,
            "reference_price": 100.0,
        }
        q, events, accepted = evaluate_quote(p, quote(60), state, now="t")
        self.assertFalse(accepted)
        self.assertEqual("ANOMALY", q.status)
        self.assertEqual([], events)
        self.assertEqual(100.0, state["last_valid_price"])
        self.assertEqual(100.0, state["reference_price"])

    def test_product_page_target_is_candidate_by_default(self):
        p = product(target=80, allow_page=False)
        state = {
            "target_armed": True,
            "last_valid_price": None,
            "reference_price": None,
        }
        _, events, accepted = evaluate_quote(
            p,
            quote(78, PriceConfidence.PRODUCT_PAGE_PRICE.value),
            state,
            now="t",
        )
        self.assertTrue(accepted)
        self.assertEqual("CANDIDATE_TARGET_REACHED", events[0].event_type)
        self.assertFalse(events[0].formal)


if __name__ == "__main__":
    unittest.main()
