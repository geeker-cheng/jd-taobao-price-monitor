import unittest

from price_monitor.models import PriceConfidence
from price_monitor.sources import MaishouSource


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeMaishouSession:
    def __init__(self, details):
        self.details = details
        self.calls = []

    def post(self, url, headers=None, data=None, json=None, timeout=None):
        if "searchList" in url:
            self.calls.append(("search", data["keyword"]))
            return FakeResponse(
                {
                    "status": "success",
                    "code": 200,
                    "data": list(self.details.values()),
                }
            )

        goods_id = json["goodsId"]
        self.calls.append(("detail", goods_id))
        return FakeResponse(
            {
                "status": "success",
                "code": 200,
                "data": self.details[goods_id],
            }
        )


def x200s_detail(goods_id, stable_id, color, memory, price):
    return {
        "goodsId": goods_id,
        "goodsIdB": stable_id,
        "jdGoodsIdB": stable_id,
        "title": (
            f"vivo X200s {memory} {color} 国家补贴 "
            "蔡司超级潜望长焦 湿手秒开超声波指纹 拍照 AI手机"
        ),
        "shopName": "vivo京东自营旗舰店",
        "actualPrice": str(price),
        "originalPrice": "4699",
        "tagList": ["自营"],
        "shopType": 1,
    }


X200S_PRODUCT = {
    "id": "vivo_x200s_12_512_jd",
    "platform": "jd",
    "identifiers": {"model": "X200s", "memory": "12GB+512GB"},
    "variant": {
        "memory": "12GB+512GB",
        "colors": ["直白", "淡紫", "薄荷蓝", "简黑"],
    },
    "shops": {
        "allowed": ["vivo京东自营旗舰店"],
        "require_self_operated": True,
    },
    "match": {
        "required_title_groups": [
            ["vivo"],
            ["X200s", "X200S"],
            ["12GB+512GB", "12GB512GB", "12G+512G", "12+512G"],
            ["直白", "淡紫", "薄荷蓝", "简黑"],
        ],
        "excluded_title_terms": [
            "12GB+256GB",
            "16GB+512GB",
            "16GB+1TB",
            "二手",
            "官换",
        ],
    },
    "source": {
        "provider": "maishou",
        "discovery_keyword": "vivo X200s",
        "discovery_detail_limit": 6,
        "selection": {
            "mode": "lowest_price",
            "scope": "configured_variant_family",
        },
        "mapping": {
            "verified": False,
            "provider_goods_id": None,
            "provider_goods_id_b": None,
        },
    },
}


class MaishouFamilyTests(unittest.TestCase):
    def test_any_color_family_selects_lowest_valid_12_512_price(self):
        details = {
            "white": x200s_detail("white", "b-white", "直白", "12GB+512GB", 3199),
            "purple": x200s_detail("purple", "b-purple", "淡紫", "12GB+512GB", 2998),
            "blue": x200s_detail("blue", "b-blue", "薄荷蓝", "12GB+512GB", 3099),
            "black": x200s_detail("black", "b-black", "简黑", "12GB+512GB", 3050),
        }
        q = MaishouSource(invite_code="x", session=FakeMaishouSession(details)).fetch(
            X200S_PRODUCT
        )

        self.assertEqual("OK", q.status)
        self.assertEqual(2998.0, q.monitoring_price)
        self.assertIn("淡紫", q.title)
        self.assertEqual(PriceConfidence.PRODUCT_PAGE_PRICE.value, q.confidence)
        self.assertEqual("lowest_price", q.detail["selection_mode"])
        self.assertEqual(4, q.detail["validated_candidate_count"])

    def test_wrong_memory_cannot_win_even_when_cheaper(self):
        details = {
            "wrong": x200s_detail("wrong", "b-wrong", "直白", "12GB+256GB", 1999),
            "right": x200s_detail("right", "b-right", "简黑", "12GB+512GB", 3100),
        }
        session = FakeMaishouSession(details)
        q = MaishouSource(invite_code="x", session=session).fetch(X200S_PRODUCT)

        self.assertEqual("OK", q.status)
        self.assertEqual(3100.0, q.monitoring_price)
        self.assertIn("12GB+512GB", q.title)
        self.assertNotIn(("detail", "wrong"), session.calls)

    def test_normal_jd_products_keep_original_ambiguity_guard(self):
        product = {
            "id": "normal",
            "platform": "jd",
            "identifiers": {},
            "shops": {"allowed": ["vivo京东自营旗舰店"]},
            "match": {
                "required_title_groups": [["vivo"], ["X200s"]],
                "excluded_title_terms": [],
            },
            "source": {
                "provider": "maishou",
                "discovery_keyword": "vivo X200s",
                "mapping": {"verified": False},
            },
        }
        details = {
            "a": x200s_detail("a", "b-a", "直白", "12GB+512GB", 3200),
            "b": x200s_detail("b", "b-b", "简黑", "12GB+512GB", 3150),
        }
        q = MaishouSource(invite_code="x", session=FakeMaishouSession(details)).fetch(product)

        self.assertEqual("AMBIGUOUS_SOURCE_MAPPING", q.status)
        self.assertIsNone(q.monitoring_price)


if __name__ == "__main__":
    unittest.main()
