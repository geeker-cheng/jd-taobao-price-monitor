import unittest

from price_monitor.models import PriceConfidence
from price_monitor.sources.haodanku import HaodankuSource
from price_monitor.sources.maishou import MaishouSource


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self.body


class FakeHaodankuSession:
    def get(self, url, params=None, timeout=None):
        if "supersearch" in url:
            return FakeResponse({
                "code": 1,
                "data": [
                    {
                        "itemid": "opaque",
                        "itemtitle": "【CUKTECH酷态科】PD快充65W氮化镓多口充电器BBJ",
                        "shopname": "CUKTECH酷态科旗舰店",
                        "itemprice": "108",
                        "itemendprice": "108",
                    }
                ],
            })
        return FakeResponse({
            "code": 1,
            "data": {
                "itemid": "opaque",
                "itemtitle": "【CUKTECH酷态科】PD快充65W氮化镓多口充电器BBJ",
                "shopname": "CUKTECH酷态科旗舰店",
                "itemprice": "108",
                "itemendprice": "108",
                "couponmoney": "0",
            },
        })


class FakeMaishouSession:
    def __init__(self, details):
        self.details = details

    def post(self, url, headers=None, data=None, json=None, timeout=None):
        if "searchList" in url:
            return FakeResponse({
                "status": "success",
                "code": 200,
                "data": list(self.details.values()),
            })
        goods_id = json["goodsId"]
        return FakeResponse({
            "status": "success",
            "code": 200,
            "data": self.details[goods_id],
        })


TMALL_PRODUCT = {
    "id": "tb",
    "platform": "taobao",
    "identifiers": {"model": "AD653C"},
    "source": {"provider": "haodanku", "search_keywords": ["酷态科 65W 氮化镓"]},
    "shops": {"allowed": ["CUKTECH酷态科旗舰店"]},
    "match": {
        "required_title_groups": [
            ["CUKTECH", "酷态科"], ["65W"], ["氮化镓"], ["多口", "三口", "2C1A"]
        ],
        "excluded_title_terms": ["mini", "Ultra", "卡片", "套装"],
    },
}


JD_PRODUCT = {
    "id": "jd",
    "platform": "jd",
    "identifiers": {"sku_id": "100068768088"},
    "source": {
        "provider": "maishou",
        "search_keywords": ["酷态科 65W 氮化镓"],
        "mapping": {"verified": False, "provider_goods_id": None},
    },
    "shops": {"allowed": ["CUKTECH酷态科京东自营旗舰店"]},
    "match": {
        "required_title_groups": [
            ["CUKTECH", "酷态科"], ["65W"], ["氮化镓"], ["多口", "三口", "Type-C"]
        ],
        "excluded_title_terms": ["mini", "Ultra", "卡片", "套装"],
    },
}


class SourceTests(unittest.TestCase):
    def test_haodanku_is_product_page_confidence(self):
        src = HaodankuSource(api_key="x", session=FakeHaodankuSession())
        q = src.fetch(TMALL_PRODUCT)
        self.assertEqual("OK", q.status)
        self.assertEqual(PriceConfidence.PRODUCT_PAGE_PRICE.value, q.confidence)
        self.assertEqual(108.0, q.monitoring_price)

    def test_maishou_multiple_matches_are_ambiguous(self):
        details = {
            "g1": {
                "goodsId": "g1", "goodsIdB": "b1", "jdGoodsIdB": "b1",
                "title": "CUKTECH酷态科65W氮化镓多口Type-C充电器",
                "shopName": "CUKTECH酷态科京东自营旗舰店",
                "actualPrice": "86.2", "originalPrice": "93.2",
                "tagList": ["自营"], "shopType": 1,
            },
            "g2": {
                "goodsId": "g2", "goodsIdB": "b2", "jdGoodsIdB": "b2",
                "title": "CUKTECH酷态科65W氮化镓多口Type-C充电器",
                "shopName": "CUKTECH酷态科京东自营旗舰店",
                "actualPrice": "77.7", "originalPrice": "77.7",
                "tagList": ["自营"], "shopType": 1,
            },
        }
        src = MaishouSource(invite_code="own-code", session=FakeMaishouSession(details))
        q = src.fetch(JD_PRODUCT)
        self.assertEqual("AMBIGUOUS_SOURCE_MAPPING", q.status)
        self.assertIsNone(q.monitoring_price)

    def test_maishou_does_not_use_public_code_fallback(self):
        src = MaishouSource(invite_code="", session=FakeMaishouSession({}))
        q = src.fetch(JD_PRODUCT)
        self.assertEqual("CONFIG_REQUIRED", q.status)
        self.assertEqual("MAISHOU_INVITE_CODE", q.detail["required_secret"])


if __name__ == "__main__":
    unittest.main()
