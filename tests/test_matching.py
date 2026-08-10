import unittest

from price_monitor.matching import shop_matches, title_matches


PRODUCT = {
    "match": {
        "required_title_groups": [
            ["CUKTECH", "酷态科"],
            ["65W"],
            ["氮化镓"],
            ["多口", "2C1A", "三口"],
        ],
        "excluded_title_terms": ["mini", "Ultra", "卡片", "套装"],
    },
    "shops": {"allowed": ["CUKTECH酷态科旗舰店"]},
}


class MatchingTests(unittest.TestCase):
    def test_target_title(self):
        self.assertTrue(
            title_matches("CUKTECH酷态科PD快充65W氮化镓多口充电器", PRODUCT)
        )

    def test_excludes_wrong_variant(self):
        self.assertFalse(
            title_matches("CUKTECH酷态科6号Ultra 65W氮化镓多口充电器", PRODUCT)
        )
        self.assertFalse(
            title_matches("CUKTECH酷态科65W氮化镓多口充电器套装", PRODUCT)
        )

    def test_shop(self):
        self.assertTrue(shop_matches("CUKTECH酷态科旗舰店", PRODUCT))
        self.assertFalse(shop_matches("某某数码专营店", PRODUCT))


if __name__ == "__main__":
    unittest.main()
