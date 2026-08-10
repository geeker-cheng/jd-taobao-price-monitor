import copy
import os
import unittest
from unittest.mock import patch

import requests

from price_monitor.models import PriceConfidence
from price_monitor.sources.haodanku import HaodankuSource
from price_monitor.sources.maishou import (
    DEFAULT_PUBLIC_INVITE_CODE,
    DISCOVERY_DETAIL_LIMIT,
    TIMEOUT,
    MaishouSource,
)


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
                "data": [{
                    "itemid": "opaque",
                    "itemtitle": "【CUKTECH酷态科】PD快充65W氮化镓多口充电器BBJ",
                    "shopname": "CUKTECH酷态科旗舰店",
                    "itemprice": "108",
                    "itemendprice": "108",
                }],
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
    def __init__(self, details, *, transport_failures=None):
        self.details = details
        self.transport_failures = set(transport_failures or [])
        self.calls = []

    def post(self, url, headers=None, data=None, json=None, timeout=None):
        if "searchList" in url:
            self.calls.append(("search", data["keyword"], timeout))
            return FakeResponse({
                "status": "success",
                "code": 200,
                "data": list(self.details.values()),
            })
        goods_id = json["goodsId"]
        self.calls.append(("detail", goods_id, timeout))
        if goods_id in self.transport_failures:
            raise requests.ConnectTimeout(f"timeout for {goods_id}")
        if goods_id not in self.details:
            return FakeResponse({
                "status": "error", "code": 422,
                "message": "商品不存在", "data": None,
            })
        return FakeResponse({
            "status": "success", "code": 200,
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
        "discovery_keyword": "酷态科 65W 氮化镓",
        "mapping": {
            "verified": False,
            "provider_goods_id": None,
            "provider_goods_id_b": None,
        },
    },
    "shops": {"allowed": ["CUKTECH酷态科京东自营旗舰店"]},
    "match": {
        "required_title_groups": [
            ["CUKTECH", "酷态科"], ["65W"], ["氮化镓"], ["多口", "三口", "Type-C"]
        ],
        "excluded_title_terms": ["mini", "Ultra", "卡片", "套装"],
    },
}


def jd_detail(goods_id, stable_id, price, *, title=None):
    return {
        "goodsId": goods_id,
        "goodsIdB": stable_id,
        "jdGoodsIdB": stable_id,
        "title": title or "CUKTECH酷态科65W氮化镓多口Type-C充电器",
        "shopName": "CUKTECH酷态科京东自营旗舰店",
        "actualPrice": str(price),
        "originalPrice": str(price),
        "tagList": ["自营"],
        "shopType": 1,
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
            "g1": jd_detail("g1", "b1", 86.2),
            "g2": jd_detail("g2", "b2", 77.7),
        }
        src = MaishouSource(invite_code="own-code", session=FakeMaishouSession(details))
        q = src.fetch(JD_PRODUCT)
        self.assertEqual("AMBIGUOUS_SOURCE_MAPPING", q.status)
        self.assertIsNone(q.monitoring_price)

    def test_known_candidates_are_probed_before_search(self):
        product = copy.deepcopy(JD_PRODUCT)
        product["source"]["known_candidates"] = [
            {"goods_id": "g1", "goods_id_b": "b1"},
            {"goods_id": "g2", "goods_id_b": "b2"},
        ]
        session = FakeMaishouSession({
            "g1": jd_detail("g1", "b1", 86.2),
            "g2": jd_detail("g2", "b2", 77.7),
        })
        q = MaishouSource(invite_code="x", session=session).fetch(product)
        self.assertEqual("AMBIGUOUS_SOURCE_MAPPING", q.status)
        self.assertEqual(["detail", "detail"], [call[0] for call in session.calls])
        self.assertEqual("known_candidates", q.detail["candidate_source"])

    def test_known_candidate_transport_error_does_not_fall_back_to_search(self):
        product = copy.deepcopy(JD_PRODUCT)
        product["source"]["known_candidates"] = [
            {"goods_id": "g1", "goods_id_b": "b1"},
            {"goods_id": "g2", "goods_id_b": "b2"},
        ]
        session = FakeMaishouSession(
            {
                "g1": jd_detail("g1", "b1", 86.2),
                "g2": jd_detail("g2", "b2", 77.7),
            },
            transport_failures={"g1"},
        )
        q = MaishouSource(invite_code="x", session=session).fetch(product)
        self.assertEqual("SOURCE_ERROR", q.status)
        self.assertIsNone(q.monitoring_price)
        self.assertNotIn("search", [call[0] for call in session.calls])
        self.assertEqual("known_candidate_detail", q.detail["stage"])

    def test_stale_known_candidate_uses_single_discovery_query(self):
        product = copy.deepcopy(JD_PRODUCT)
        product["source"]["known_candidates"] = [
            {"goods_id": "stale", "goods_id_b": "old"}
        ]
        session = FakeMaishouSession({
            "fresh": jd_detail("fresh", "new", 78),
        })
        q = MaishouSource(invite_code="x", session=session).fetch(product)
        self.assertEqual("OK", q.status)
        self.assertEqual(PriceConfidence.UNVERIFIED.value, q.confidence)
        search_calls = [call for call in session.calls if call[0] == "search"]
        self.assertEqual(1, len(search_calls))
        self.assertEqual("酷态科 65W 氮化镓", search_calls[0][1])

    def test_verified_stable_mapping_uses_only_matching_known_candidate(self):
        product = copy.deepcopy(JD_PRODUCT)
        product["source"]["known_candidates"] = [
            {"goods_id": "g1", "goods_id_b": "b1"},
            {"goods_id": "g2", "goods_id_b": "b2"},
        ]
        product["source"]["mapping"] = {
            "verified": True,
            "provider_goods_id": None,
            "provider_goods_id_b": "b2",
        }
        session = FakeMaishouSession({
            "g1": jd_detail("g1", "b1", 86.2),
            "g2": jd_detail("g2-new-prefix", "b2", 77.7),
        })
        session.details["g2"] = jd_detail("g2-new-prefix", "b2", 77.7)
        q = MaishouSource(invite_code="x", session=session).fetch(product)
        self.assertEqual("OK", q.status)
        self.assertEqual(PriceConfidence.EXACT_SKU_PRICE.value, q.confidence)
        self.assertEqual(77.7, q.monitoring_price)
        self.assertEqual("b2", q.detail["goods_id_b"])
        self.assertEqual([("detail", "g2", TIMEOUT)], session.calls)

    def test_verified_mapping_transport_error_fails_fast(self):
        product = copy.deepcopy(JD_PRODUCT)
        product["source"]["known_candidates"] = [
            {"goods_id": "g2", "goods_id_b": "b2"},
        ]
        product["source"]["mapping"] = {
            "verified": True,
            "provider_goods_id": None,
            "provider_goods_id_b": "b2",
        }
        session = FakeMaishouSession(
            {"g2": jd_detail("g2", "b2", 77.7)},
            transport_failures={"g2"},
        )
        q = MaishouSource(invite_code="x", session=session).fetch(product)
        self.assertEqual("SOURCE_ERROR", q.status)
        self.assertEqual("verified_mapping_detail", q.detail["stage"])
        self.assertNotIn("search", [call[0] for call in session.calls])

    def test_verified_mapping_recovers_same_stable_id_with_one_search(self):
        product = copy.deepcopy(JD_PRODUCT)
        product["source"]["known_candidates"] = [
            {"goods_id": "stale", "goods_id_b": "b2"},
        ]
        product["source"]["mapping"] = {
            "verified": True,
            "provider_goods_id": None,
            "provider_goods_id_b": "b2",
        }
        session = FakeMaishouSession({
            "fresh": jd_detail("fresh", "b2", 78.0),
        })
        q = MaishouSource(invite_code="x", session=session).fetch(product)
        self.assertEqual("OK", q.status)
        self.assertEqual(PriceConfidence.EXACT_SKU_PRICE.value, q.confidence)
        self.assertEqual(78.0, q.monitoring_price)
        search_calls = [call for call in session.calls if call[0] == "search"]
        self.assertEqual(1, len(search_calls))

    def test_verified_mapping_never_substitutes_another_candidate(self):
        product = copy.deepcopy(JD_PRODUCT)
        product["source"]["known_candidates"] = [
            {"goods_id": "stale", "goods_id_b": "b2"},
        ]
        product["source"]["mapping"] = {
            "verified": True,
            "provider_goods_id": None,
            "provider_goods_id_b": "b2",
        }
        session = FakeMaishouSession({
            "other": jd_detail("other", "b3", 60.0),
        })
        q = MaishouSource(invite_code="x", session=session).fetch(product)
        self.assertEqual("MAPPED_ENTITY_NOT_FOUND", q.status)
        self.assertIsNone(q.monitoring_price)
        self.assertEqual("b2", q.detail["mapped_goods_id_b"])

    def test_maishou_network_budget_constants_are_short(self):
        self.assertLessEqual(TIMEOUT[0], 3)
        self.assertLessEqual(TIMEOUT[1], 5)
        self.assertLessEqual(DISCOVERY_DETAIL_LIMIT, 3)

    def test_maishou_uses_disclosed_public_default(self):
        with patch.dict(os.environ, {"MAISHOU_INVITE_CODE": ""}):
            src = MaishouSource(session=FakeMaishouSession({}))
        self.assertEqual("6110440", DEFAULT_PUBLIC_INVITE_CODE)
        self.assertEqual(DEFAULT_PUBLIC_INVITE_CODE, src.invite_code)

    def test_maishou_environment_overrides_public_default(self):
        with patch.dict(os.environ, {"MAISHOU_INVITE_CODE": "own-code"}):
            src = MaishouSource(session=FakeMaishouSession({}))
        self.assertEqual("own-code", src.invite_code)

    def test_maishou_explicit_code_overrides_environment(self):
        with patch.dict(os.environ, {"MAISHOU_INVITE_CODE": "env-code"}):
            src = MaishouSource(invite_code="explicit-code", session=FakeMaishouSession({}))
        self.assertEqual("explicit-code", src.invite_code)


if __name__ == "__main__":
    unittest.main()
