import unittest

from price_monitor.alerts import evaluate_quote
from price_monitor.models import PriceConfidence, Quote


def product(target=None, significant=None):
    return {
        "id": "p",
        "alert": {
            "enabled": False,
            "target_price": target,
            "significant_drop_pct": significant,
        },
    }


def quote(price, *, status="OK", confidence=PriceConfidence.EXACT_SKU_PRICE.value):
    return Quote(
        product_id="p",
        platform="jd",
        status=status,
        source="test",
        checked_at="t",
        price=price,
        effective_price=price,
        confidence=confidence,
    )


class AlertInterfaceTests(unittest.TestCase):
    def test_large_price_drop_is_not_rejected_by_price_change(self):
        state = {"last_valid_price": 100.0, "reference_price": 100.0}
        q, events, accepted = evaluate_quote(product(), quote(10), state, now="t")
        self.assertTrue(accepted)
        self.assertEqual("OK", q.status)
        self.assertEqual([], events)
        self.assertEqual({"last_valid_price": 100.0, "reference_price": 100.0}, state)

    def test_target_price_is_reserved_and_does_not_emit_event(self):
        _, events, accepted = evaluate_quote(product(target=80), quote(50), {}, now="t")
        self.assertTrue(accepted)
        self.assertEqual([], events)

    def test_significant_drop_is_reserved_and_does_not_emit_event(self):
        _, events, accepted = evaluate_quote(product(significant=0.08), quote(50), {}, now="t")
        self.assertTrue(accepted)
        self.assertEqual([], events)

    def test_non_ok_quote_is_not_accepted(self):
        _, events, accepted = evaluate_quote(product(), quote(50, status="SOURCE_ERROR"), {}, now="t")
        self.assertFalse(accepted)
        self.assertEqual([], events)


if __name__ == "__main__":
    unittest.main()
